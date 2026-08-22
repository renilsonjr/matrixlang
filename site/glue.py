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

from matrixlang.input import BufferSource, ListSource
from matrixlang.interpreter import Interpreter
from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.pytrans import Translated, translate
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


class _NeedsInput(Exception):
    """The program asked for a line the reader has not given yet.

    Not a MatrixLangError, and deliberately not the interpreter's own "no
    input left to read" diagnostic: control flow that depended on the
    wording of an error message would change behaviour the day somebody
    reworded it. Same shape as values.CyclicValue and values.Incomparable
    -- a signal raised low and caught high -- except this one passes
    THROUGH the interpreter rather than being caught by it.

    Three things make escaping mid-execution from arbitrary depth safe, and
    all three are properties of `interpreter.py` that a future change could
    take away: it opens no context manager (no `with` anywhere), it catches
    nothing broad enough to swallow this (`_Jackout`, `RecursionError`,
    `CyclicValue`, `TooManyDigits`, `ValueError`, `Incomparable` -- never a
    bare `Exception`), and its one `finally` restores `self._env` after a
    call frame, which is correct on any exception. Whatever state a
    half-finished run leaves behind lives on the `Interpreter` instance,
    and `run()` builds a fresh one every round, so none of it outlives the
    escape.
    """


class _InteractiveSource:
    """Answers so far. Asking past the end suspends rather than fails.

    The browser cannot block, so a program that wants a fourth answer is
    stopped, the reader is asked, and the whole program is re-run with
    four answers. That is honest only because MatrixLang is deterministic
    with `trace` as its only effect -- see tests/test_site_glue.py's
    determinism tests, which fail if that ever stops being true.

    **Two channels, never one.** The Input box is text and is read through
    `BufferSource`; each typed answer is already exactly one line and is
    yielded verbatim. Flattening the two into one string and re-splitting
    it does not compose: a box ending in a newline -- the common case, the
    box is a <textarea> and readers press Enter -- shifted every later
    answer by one, and a blank answer joined to nothing and vanished, so
    the reader pressed Answer and watched the same question come back.

    The box side wraps a `BufferSource` rather than splitting `text`
    itself: the same Input box must read the same lines whether or not
    `interactive=True`, and `BufferSource`'s splitting (via
    `matrixlang.input._split_lines`) already differs from
    `str.splitlines()` on purpose -- `str.splitlines` also breaks on \\v,
    \\f, \\x85 and U+2028/9, which `readline` treats as ordinary
    characters inside a line. Re-deriving that logic here, or reaching
    into the private helper, is exactly how the two would drift apart
    again; delegating to `BufferSource` makes that impossible.
    """

    def __init__(self, text: str, answers=None) -> None:
        self._buffer = BufferSource(text)
        # Converted once, here. `answers` arrives from Pyodide as a JsProxy
        # over a live JS array, not a list: indexing it lazily would both
        # retain a proxy past the call that owns it and read an array the
        # page goes on mutating between rounds. `ListSource` yields each
        # element as one line and splits nothing, which is the guarantee
        # the answers channel exists to make.
        self._typed = ListSource(list(answers) if answers else [])

    def next_line(self) -> str | None:
        # Both sources return None to mean "exhausted", per the InputSource
        # protocol -- but that branch is unreachable from here: it is turned
        # into _NeedsInput before it can leave this method, so this source
        # never actually returns None.
        line = self._buffer.next_line()
        if line is None:
            line = self._typed.next_line()
        if line is None:
            raise _NeedsInput
        return line


def write(request: str) -> dict:
    """Ask Scribe for a program. Never raises."""
    result = scribe(request)
    if isinstance(result, ScribeProgram):
        return {"ok": True, "source": result.source}
    return {"ok": False, "error": result.reason, "hint": result.closest}


def translate_python(source: str) -> dict:
    """Ask the translator for a program. Never raises.

    The wire shape mirrors `write()`: a flag plus either source or the
    reasons it could not be produced. Refusals come back as a list because
    the translator collects every one -- a reader fixing a long program
    should see all of it at once.

    The broad `except Exception` below is deliberate, not laziness. "Never
    raises" has now been broken five times in this project, four of them by
    a failure nobody predicted -- pytrans/translate.py itself just needed a
    widened `ast.parse` catch and a recursion guard for two more nobody
    foresaw when it was written. Under Pyodide there is no console the
    reader is looking at for an escaped exception to land in; it is an
    unhandled browser traceback in their tab. Catching everything here is
    what makes the promise structurally true -- good for whatever gap
    remains today and whatever new one Python 3.next introduces -- rather
    than true only for the failure modes this module's authors happened to
    think of before shipping it.
    """
    try:
        result = translate(source)
    except Exception as error:  # deliberately broad -- see the comment above
        return {
            "ok": False,
            "refusals": [
                {"reason": f"could not translate: {error}", "line": 1, "column": 1, "idiom": ""}
            ],
        }
    if isinstance(result, Translated):
        return {"ok": True, "source": result.source}
    return {
        "ok": False,
        "refusals": [
            {
                "reason": r.reason,
                "line": r.line,
                "column": r.column,
                "idiom": r.idiom or "",
            }
            for r in result.items
        ],
    }


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
    source: str,
    stdin: str = "",
    interactive: bool = False,  # Both before max_steps -- do not "tidy"
    answers=None,               # this order; the test below pins it.
    max_steps: int = BROWSER_MAX_STEPS,
    # The JavaScript side calls this positionally, and a JS `undefined`
    # argument arrives here as Python `None`. `interpreter.py` treats
    # `max_steps=None` as *no step limit at all*. If `max_steps` came
    # before `interactive` and `answers`, the browser's call would have to
    # pass it explicitly on every call just to reach them; with both here
    # instead, a positional `glue.run(src, stdin, true, answers)` never has
    # to touch `max_steps`, so it can never accidentally send `None` and
    # silently delete the runaway-loop protection -- in the one feature
    # that adds a way to loop forever asking questions.
    #
    # `tests/test_site_glue.py::test_run_takes_interactive_and_answers_
    # positionally_in_that_order` calls this the way the page does, so a
    # reorder breaks a test rather than only contradicting this comment.
) -> list[dict]:
    """Execute `source`, returning every event in wire shape. Never raises.

    A failure is the last event rather than an exception, so the JS side
    has one list to walk and no error path of its own.

    `stdin` is whatever the reader typed into the input box, supplied up
    front, and is read through `BufferSource` in every mode. `answers` is
    the separate, ordered list of lines the reader gave one at a time when
    the page asked; each is one line exactly as typed and is never re-split.
    They stay two arguments because they are two kinds of thing -- see
    `_InteractiveSource` for what merging them cost.

    `interactive=True` changes only what happens when both run out. The
    browser cannot block -- JavaScript is single-threaded, so a read that
    waited would freeze the tab and the cascade drawing in it -- so instead
    of the "no input left to read" error, the events so far come back with
    a terminal {"kind": "needs_input"}, and the caller is expected to ask
    the reader and re-run from the start with one more answer. Callers that
    do not opt in see exactly the old behaviour, and `answers` is ignored.
    """
    from matrixlang.errors import MatrixLangError, recursion_guard

    sink = _Collector()
    try:
        with recursion_guard():
            program = parse(lex(source))
    except MatrixLangError as error:
        return [{"kind": "error", "message": f"[line {error.line}, column {error.column}] {error.message}"}]

    source_for_run = (
        _InteractiveSource(stdin, answers) if interactive else BufferSource(stdin)
    )
    try:
        Interpreter(
            sink=sink, max_steps=max_steps, source=source_for_run
        ).run(program)
    except _NeedsInput:
        # Caught in the same try that catches MatrixLangError: run() promises
        # never to raise, and that promise has been broken three times before
        # by exceptions nobody expected to reach here.
        sink.events.append({"kind": "needs_input"})
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

    The interactive page no longer reaches either sentence: with
    `interactive=True` the shortfall becomes a `needs_input` marker and a
    question, never `_EXHAUSTED`, so there is no error to hint at. What still
    reaches here is every non-interactive caller -- the tests below, and any
    embedder that runs `glue.run` without opting in. Kept rather than deleted
    because that path is the one this module has always promised, and the
    hint is still right for it.
    """
    if _EXHAUSTED not in error.message:
        return ""
    if stdin.strip():
        return " — the program read more lines than the Input box holds"
    return " — the Input box beside the editor is empty"
