"""OP-D — the HTTP surface, over a real socket.

The only tests in this project that bind a port. Everything they check is
the wiring: routes, status codes, content types, and that the SSE stream
actually streams. What the frames *contain* is settled in
`test_server_sse.py` without a socket.
"""

import json
import threading
import urllib.error
import urllib.request

import pytest

from server.app import serve


@pytest.fixture
def base_url():
    httpd = serve(port=0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}"
    httpd.shutdown()
    httpd.server_close()


def post(url, payload):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        return response.status, json.loads(response.read())


# --- Running a program --------------------------------------------------


def test_posting_a_program_returns_a_run_id(base_url):
    status, body = post(f"{base_url}/api/run", {"source": 'trace "hi"\n'})
    assert status == 200
    assert body["run"]


def test_the_events_endpoint_streams_server_sent_events(base_url):
    _, body = post(f"{base_url}/api/run", {"source": 'trace "wake up, Neo"\n'})
    with urllib.request.urlopen(f"{base_url}/api/events?run={body['run']}", timeout=5) as r:
        assert r.headers["Content-Type"] == "text/event-stream"
        # Reject buffering proxies and browser caches: an SSE response
        # that gets cached or buffered never arrives.
        assert r.headers["Cache-Control"] == "no-cache"
        text = r.read().decode()
    assert "data: " in text
    assert text.endswith("\n\n")


def test_the_stream_carries_the_programs_output_and_ends(base_url):
    _, body = post(f"{base_url}/api/run", {"source": 'trace "wake up, Neo"\n'})
    with urllib.request.urlopen(f"{base_url}/api/events?run={body['run']}", timeout=5) as r:
        frames = [
            json.loads(line[6:])
            for line in r.read().decode().splitlines()
            if line.startswith("data: ")
        ]
    assert any(f["kind"] == "output" and f["text"] == "wake up, Neo" for f in frames)
    assert frames[-1]["kind"] == "done"


def test_a_program_that_fails_streams_an_error_frame(base_url):
    _, body = post(f"{base_url}/api/run", {"source": "trace nope\n"})
    with urllib.request.urlopen(f"{base_url}/api/events?run={body['run']}", timeout=5) as r:
        frames = [
            json.loads(line[6:])
            for line in r.read().decode().splitlines()
            if line.startswith("data: ")
        ]
    # The stream always ends with `done`, so a client has exactly one
    # terminator to look for; an `error` frame precedes it.
    assert frames[-1]["kind"] == "done"
    assert frames[-2]["kind"] == "error"
    assert "not declared" in frames[-2]["message"]


# --- Chat ---------------------------------------------------------------


def test_chat_reports_when_no_key_is_configured(base_url):
    # The server must not 500 because an optional dependency is absent.
    status, body = post(f"{base_url}/api/chat", {"request": "count to three"})
    assert status == 200
    assert body["ok"] is False
    assert "matrixlang[bot]" in body["error"] or "api" in body["error"].lower()


# --- Errors -------------------------------------------------------------


def test_an_unknown_path_is_404(base_url):
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(f"{base_url}/nope", timeout=5)
    assert excinfo.value.code == 404


def test_an_unknown_run_is_404(base_url):
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(f"{base_url}/api/events?run=nope", timeout=5)
    assert excinfo.value.code == 404


def test_a_malformed_body_is_400_not_500(base_url):
    request = urllib.request.Request(
        f"{base_url}/api/run",
        data=b"{not json",
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(request, timeout=5)
    assert excinfo.value.code == 400


def test_a_run_with_no_source_is_400(base_url):
    request = urllib.request.Request(
        f"{base_url}/api/run",
        data=json.dumps({}).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with pytest.raises(urllib.error.HTTPError) as excinfo:
        urllib.request.urlopen(request, timeout=5)
    assert excinfo.value.code == 400


# --- It stays local -----------------------------------------------------


def test_the_server_binds_loopback_only():
    # OP-13: local-first. Binding 0.0.0.0 would expose an unauthenticated
    # code-execution endpoint to the network.
    from server.app import HOST

    assert HOST in ("127.0.0.1", "localhost")


# --- Serving the UI (OP-E) ----------------------------------------------


def test_the_root_serves_the_page(base_url):
    with urllib.request.urlopen(f"{base_url}/", timeout=5) as r:
        assert r.status == 200
        assert r.headers["Content-Type"].startswith("text/html")
        body = r.read().decode()
    assert "<title>" in body


def test_static_assets_are_served_with_their_own_type(base_url):
    for path, expected in (("/style.css", "text/css"), ("/app.js", "javascript")):
        with urllib.request.urlopen(base_url + path, timeout=5) as r:
            assert r.status == 200
            assert expected in r.headers["Content-Type"]


def test_a_path_outside_the_ui_directory_is_refused(base_url):
    # The UI directory is served from disk; a traversal must not escape it.
    for attempt in ("/../pyproject.toml", "/..%2Fpyproject.toml", "//etc/passwd"):
        try:
            with urllib.request.urlopen(base_url + attempt, timeout=5) as r:
                assert "hatchling" not in r.read().decode()
        except urllib.error.HTTPError as error:
            assert error.code in (400, 403, 404)


def test_the_page_talks_only_to_this_server(base_url):
    # OP-1: local. A UI that reaches an external origin would quietly
    # undo the whole reason this is not hosted.
    with urllib.request.urlopen(f"{base_url}/app.js", timeout=5) as r:
        source = r.read().decode()
    assert "http://" not in source.replace("http://127.0.0.1", "")
    assert "https://" not in source
