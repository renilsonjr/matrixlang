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

from matrixlang.input import BufferSource
from matrixlang.interpreter import Interpreter
from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.render import render_glyph
from matrixlang.scribe import ScribeProgram, scribe
from matrixlang.translit import table_for_readers, transliterate, untransliterate

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


def glyph(source: str) -> dict:
    """The glyph face of arbitrary source, rendered by Python. Never raises.

    The editor toggle shows this face *beside* what the reader typed; it
    never rewrites the editor. Rendering happens here rather than in
    JavaScript because the browser may draw but must not own the
    transliteration table (§5.7, site/checks/no_semantics.py).
    """
    from matrixlang.errors import MatrixLangError

    try:
        program = parse(lex(source))
    except MatrixLangError as error:
        return {"ok": False, "error": f"[line {error.line}, column {error.column}] {error.message}"}
    return {"ok": True, "glyph": render_glyph(program)}


def transliterate_text(text: str) -> str:
    """The glyph face of arbitrary text, for the Transliterator tab.

    Calls the real table rather than a JS copy of it — a JS copy is the
    exact shape of thing site/checks/no_semantics.py exists to block (see
    the playground-tabs-and-transliterator design doc, TT-9).
    """
    return transliterate(text)


def untransliterate_text(glyphs: str) -> str:
    """The inverse of transliterate_text()."""
    return untransliterate(glyphs)


def readers_table() -> str:
    """The full reversible table, for the Transliterator's disclosure panel."""
    return table_for_readers()


def operator_prompt(request: str) -> str:
    """The full context Operator is asked with, built by the package.

    `prompt.build` reads the keyword list from `tokens` so the prompt
    cannot drift from the language; assembling it in JavaScript would
    undo that. It returns one string with the request already in it —
    there is no separate system prompt — so the caller sends it as the
    only user message.

    Importing `operator.prompt` pulls in no SDK: `operator/client.py` is
    the only module that touches `anthropic`, and it imports it inside
    the function that calls it.
    """
    from matrixlang.operator.prompt import build

    return build(request)


def run(
    source: str, stdin: str = "", max_steps: int = BROWSER_MAX_STEPS
) -> list[dict]:
    """Execute `source`, returning every event in wire shape. Never raises.

    A failure is the last event rather than an exception, so the JS side
    has one list to walk and no error path of its own.

    `stdin` is whatever the reader typed into the input box, supplied up
    front. The browser cannot block -- JavaScript is single-threaded, so a
    read that waited would freeze the tab and the cascade drawing in it --
    so input is buffered rather than prompted for.
    """
    from matrixlang.errors import MatrixLangError, recursion_guard

    sink = _Collector()
    try:
        with recursion_guard():
            program = parse(lex(source))
    except MatrixLangError as error:
        return [{"kind": "error", "message": f"[line {error.line}, column {error.column}] {error.message}"}]

    try:
        Interpreter(
            sink=sink, max_steps=max_steps, source=BufferSource(stdin)
        ).run(program)
    except MatrixLangError as error:
        message = f"[line {error.line}, column {error.column}] {error.message}"
        sink.events.append({"kind": "error", "message": message + _input_hint(error, stdin)})
    return sink.events


# The interpreter's own wording. It stays surface-neutral because the CLI and
# the REPL read it too, so `glue.py` is where a browser-specific "and here is
# the box" belongs -- this module IS the browser's half.
#
# Matching on the phrase duplicates a string from interpreter.py. The tests in
# tests/test_site_glue.py run a real program to exhaustion rather than
# asserting on a literal, so rewording the diagnostic there turns this hint
# off loudly instead of silently.
_EXHAUSTED = "no input left to read"


def _input_hint(error, stdin: str) -> str:
    """Name the box, for the one error whose fix is a box the reader can see.

    Empty. A reader who never filled it in has been told what went wrong and
    not where to fix it, which is exactly how this failed on the live page:
    the box's placeholder read as content, so the box looked answered.

    Part-filled is a different mistake and gets a different sentence, because
    "the box is empty" would simply be false.
    """
    if _EXHAUSTED not in error.message:
        return ""
    if stdin.strip():
        return " — the program read more lines than the Input box holds"
    return " — the Input box beside the editor is empty"
