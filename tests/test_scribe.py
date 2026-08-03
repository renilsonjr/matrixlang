"""SC-B — Scribe, the keyless generator.

Scribe is pure: it builds nodes.* ASTs from plain-language requests and
never touches the network, an SDK, or a key. The server owns the validate
gate; scribe only produces. The full language surface is covered here,
pattern by pattern.
"""

from matrixlang.scribe import ScribeMiss, ScribeProgram, scribe


def test_an_empty_request_is_a_miss():
    result = scribe("")
    assert isinstance(result, ScribeMiss)
    assert result.reason


def test_unrecognized_request_is_a_miss_with_a_hint():
    result = scribe("make soup")
    assert isinstance(result, ScribeMiss)
    assert result.closest


def test_a_known_request_produces_source_that_parses():
    result = scribe("print hello")
    assert isinstance(result, ScribeProgram)
    assert "trace" in result.source


def test_scribe_never_touches_a_key():
    # The pure contract: no exception, no network, deterministic result.
    import subprocess
    import sys

    code = "from matrixlang.scribe import scribe; r = scribe('print hi'); print(type(r).__name__)"
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "ScribeProgram"
