"""Error hierarchy for the MatrixLang toolchain.

Every error carries a line and column. Stage 2 and Stage 3 add siblings to
LexError rather than inventing their own reporting.
"""

import contextlib


class MatrixLangError(Exception):
    """Base class for every error raised by MatrixLang."""

    def __init__(self, message: str, line: int, column: int) -> None:
        self.message = message
        self.line = line
        self.column = column
        super().__init__(f"[line {line}, column {column}] {message}")


class LexError(MatrixLangError):
    """The scanner could not turn the source into tokens."""


class ParseError(MatrixLangError):
    """The parser could not build a tree from the tokens."""


class RuntimeErrorML(MatrixLangError):
    """Execution reached something the language forbids.

    Named with the ML suffix because `RuntimeError` is a Python builtin and
    shadowing it here would make `except RuntimeError` ambiguous for every
    future reader.
    """


class TooDeepError(MatrixLangError):
    """A RecursionError, converted at a boundary with no statement to blame.

    Interpreter.run has its own guard (interpreter.py) that turns a
    RecursionError into a RuntimeErrorML carrying the failing statement's
    real line/column, because it catches inside a per-statement loop and
    always has a "current statement" to point at. Lexing, parsing, and
    rendering have no such loop — each is one recursive descent over the
    whole input — so by the time RecursionError reaches the surface there
    is no honest position left to report. Line 0 / column 0 would look
    like a real position and send a reader hunting for a line that has
    nothing to do with the failure; leaving line/column as None says
    plainly that no position is available, while keeping the same
    `matrixlang: ` prefix and exit-1 contract as every other
    MatrixLangError (both read it through str(), never through
    line/column directly).
    """

    def __init__(self, message: str = "input is nested too deeply to process") -> None:
        self.message = message
        self.line = None
        self.column = None
        Exception.__init__(self, message)


@contextlib.contextmanager
def recursion_guard():
    """Wrap a recursive call so a RecursionError becomes a TooDeepError.

    One shared helper instead of copy-pasting `except RecursionError` at
    every call site that lexes/parses/renders untrusted input (cli.py,
    repl.py): `TooDeepError` is a `MatrixLangError`, so it flows straight
    into the `except MatrixLangError` handling those call sites already
    have — no new except clauses needed there.
    """
    try:
        yield
    except RecursionError:
        raise TooDeepError() from None
