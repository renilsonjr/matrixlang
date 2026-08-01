"""The HTTP surface. Standard library only.

Three endpoints, and no more than the browser needs:

    POST /api/chat    {"request": "..."}  -> a program Operator wrote
    POST /api/run     {"source":  "..."}  -> {"run": "<id>"}
    GET  /api/events?run=<id>             -> text/event-stream

The stream's frames are `statement`, `output`, and `error`, and it
**always ends with `done`** — including after an error. One terminator
means a client's read loop is "until done" and nothing else, rather than
two conditions that can disagree.

Only the third is unusual, and it is **one-directional** — the server
pushes execution events and the browser never pushes back on that
channel. That is precisely what Server-Sent Events are for, and why this
needs no framework: `BaseHTTPRequestHandler` writing `data:` lines is the
whole implementation.

Everything else on `GET` is the UI, served from `web-ui/` on disk. Paths
are resolved and checked against that directory: the browser supplies
them, so they are untrusted input like any other.

**Loopback only.** This runs untrusted generated code on the machine's
own owner's behalf, with no authentication. Binding anything but
localhost would put an unauthenticated code-execution endpoint on the
network, which OP-13 explicitly deferred.
"""

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlparse

from server.runs import Runs
from server.sse import DONE, frame

UI = Path(__file__).resolve().parent.parent / "web-ui"

_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
}

HOST = "127.0.0.1"
DEFAULT_PORT = 8420

_RUNS = Runs()


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    # --- routing ---------------------------------------------------------

    def do_POST(self) -> None:  # noqa: N802 - BaseHTTPRequestHandler's name
        route = urlparse(self.path).path
        if route == "/api/run":
            self._run()
        elif route == "/api/chat":
            self._chat()
        else:
            self._json(404, {"error": "not found"})

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path == "/api/events":
            self._events(parse_qs(parsed.query).get("run", [""])[0])
        else:
            self._static(parsed.path)

    # --- endpoints -------------------------------------------------------

    def _run(self) -> None:
        body = self._body()
        if body is None:
            return
        source = body.get("source")
        if not isinstance(source, str) or not source.strip():
            self._json(400, {"error": "a 'source' string is required"})
            return
        self._json(200, {"run": _RUNS.start(source).id})

    def _chat(self) -> None:
        """Ask Operator for a program.

        Never 500s on a missing key or a missing SDK: those are ordinary
        states of a local install, and the browser needs something to
        show rather than a stack trace.
        """
        body = self._body()
        if body is None:
            return
        request = body.get("request")
        if not isinstance(request, str) or not request.strip():
            self._json(400, {"error": "a 'request' string is required"})
            return

        from matrixlang.operator.client import AnthropicClient
        from matrixlang.operator.loop import run as run_operator

        outcome = run_operator(request, AnthropicClient())
        if outcome.succeeded:
            self._json(200, {
                "ok": True,
                "source": outcome.source,
                "attempts": _attempts(outcome),
            })
        else:
            self._json(200, {
                "ok": False,
                "error": outcome.failure.message if outcome.failure else "no program",
                "attempts": _attempts(outcome),
            })

    def _events(self, run_id: str) -> None:
        run = _RUNS.get(run_id)
        if run is None:
            self._json(404, {"error": "unknown run"})
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream")
        # Without these an intermediary or the browser itself may buffer
        # the response, and a stream that arrives all at once is not one.
        self.send_header("Cache-Control", "no-cache")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("Connection", "close")
        self.end_headers()

        while True:
            event = run.next(timeout=1.0)
            if event["kind"] == "done":
                self._write(DONE)
                return
            self._write(frame(json.dumps(event)))
            if event["kind"] == "error":
                self._write(DONE)
                return

    def _static(self, route: str) -> None:
        """Serve the UI from disk, refusing anything outside it.

        The path comes from the browser, so it is untrusted. Resolving it
        and checking containment is the check that matters — a prefix
        test on the raw string is defeated by `..`, by an encoded `..`,
        and by a symlink.
        """
        name = unquote(route).lstrip("/") or "index.html"
        try:
            target = (UI / name).resolve()
            target.relative_to(UI.resolve())
        except (ValueError, OSError):
            self._json(403, {"error": "forbidden"})
            return
        if not target.is_file():
            self._json(404, {"error": "not found"})
            return

        body = target.read_bytes()
        self.send_response(200)
        self.send_header(
            "Content-Type", _TYPES.get(target.suffix, "application/octet-stream")
        )
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    # --- plumbing --------------------------------------------------------

    def _body(self) -> dict | None:
        length = int(self.headers.get("Content-Length") or 0)
        try:
            parsed = json.loads(self.rfile.read(length) or b"{}")
        except (ValueError, UnicodeDecodeError):
            self._json(400, {"error": "body must be JSON"})
            return None
        if not isinstance(parsed, dict):
            self._json(400, {"error": "body must be a JSON object"})
            return None
        return parsed

    def _json(self, status: int, payload: dict) -> None:
        encoded = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def _write(self, text: str) -> None:
        self.wfile.write(text.encode())
        self.wfile.flush()

    def log_message(self, *args) -> None:
        """Silence the default stderr access log; the tests bind real ports."""


def _attempts(outcome) -> list[dict]:
    """Every attempt, so a caller can see what a session actually cost."""
    return [
        {
            "number": attempt.number,
            "stage": attempt.failure.stage.name if attempt.failure else "VALID",
            "diagnostic": attempt.failure.as_diagnostic() if attempt.failure else None,
        }
        for attempt in outcome.attempts
    ]


def serve(port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    """A server bound and ready. The caller owns the loop."""
    return ThreadingHTTPServer((HOST, port), Handler)
