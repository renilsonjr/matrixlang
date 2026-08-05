"""The playground's Python half — the only code the browser calls.

This runs inside Pyodide, but it is ordinary CPython: `tests/test_site_glue.py`
imports and exercises it directly, which is why the playground's logic is
covered by the existing suite instead of by a browser-automation rig.

**It owns no language logic.** Scribe writes the program, the real lexer and
parser read it, the real interpreter runs it, and `server.sse.payload` decides
the wire shape. This module only sequences those calls. That is the whole
reason the page cannot drift from the language the way `web/interpreter.js`
did (see the commit that deleted it, and TECHNICAL-OVERVIEW §5.7).
"""

from matrixlang.interpreter import Interpreter
from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.scribe import ScribeProgram, scribe

from server.sse import payload

# Well below the CLI's 200,000. A reader on a phone should get "that loops
# forever" in a moment rather than a frozen tab, and the page has no
# Ctrl-C. Mirrors why operator/validate.py caps its dry run.
BROWSER_MAX_STEPS = 20_000


class _Collector:
    """An EventSink that keeps the wire shape rather than printing.

    `emit` calls `sse.payload` for the same reason `server/runs.py` does:
    it is the only place the browser's message shape is built. §5.7 records
    what happened the one time that shape existed in two places.
    """

    def __init__(self) -> None:
        self.events: list[dict] = []

    def emit(self, event) -> None:
        self.events.append(payload(event))


def write(request: str) -> dict:
    """Ask Scribe for a program. Never raises."""
    result = scribe(request)
    if isinstance(result, ScribeProgram):
        return {"ok": True, "source": result.source}
    return {"ok": False, "error": result.reason, "hint": result.closest}


def run(source: str, max_steps: int = BROWSER_MAX_STEPS) -> list[dict]:
    """Execute `source`, returning every event in wire shape. Never raises.

    A failure is the last event rather than an exception, so the JS side
    has one list to walk and no error path of its own.
    """
    from matrixlang.errors import MatrixLangError, recursion_guard

    sink = _Collector()
    try:
        with recursion_guard():
            program = parse(lex(source))
    except MatrixLangError as error:
        return [{"kind": "error", "message": f"[line {error.line}, column {error.column}] {error.message}"}]

    try:
        Interpreter(sink=sink, max_steps=max_steps).run(program)
    except MatrixLangError as error:
        sink.events.append(
            {"kind": "error", "message": f"[line {error.line}, column {error.column}] {error.message}"}
        )
    return sink.events
