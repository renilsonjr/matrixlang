"""Interactive MatrixLang session.

Buffers input while a block is open, so a `dejavu` loop can be typed at the
prompt and watched running — which is the point of Stage 3.

Depth is counted over the TOKEN stream, not over raw text: a `#` comment or
a string containing the word "flatline" must not close a block.
"""

import sys
from typing import TextIO

from matrixlang.errors import MatrixLangError, recursion_guard
from matrixlang.input import StdinSource
from matrixlang.interpreter import Interpreter
from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.render import render_glyph
from matrixlang.tokens import TokenType

PROMPT = "> "
CONTINUATION = "... "

_OPENERS = (TokenType.REDPILL, TokenType.DEJAVU)

_FACE_COMMANDS: dict[str, str] = {":ascii": "ascii", ":glyph": "glyph"}


class Repl:
    def __init__(
        self,
        out: TextIO | None = None,
        err: TextIO | None = None,
        in_: TextIO | None = None,
    ) -> None:
        self._out = sys.stdout if out is None else out
        # Diagnostics go to stderr, matching the CLI and what the README
        # promises. Sharing one stream with program output meant
        # `matrixlang repl > session.txt` captured the errors into the file
        # and left the terminal with no sign anything had gone wrong.
        self._err = sys.stderr if err is None else err
        # Shares the prompt's stream: a `jackin` during execution consumes
        # the next line typed. At a terminal that is exactly right. Piping a
        # script into the REPL interleaves program input with program source,
        # which is a documented sharp edge rather than something special-cased
        # -- branching language behaviour on whether stdin is a TTY would be
        # worse than the edge.
        #
        # The stream is threaded through rather than hardcoded to
        # sys.stdin: `repl(in_=...)` reads program source from its own
        # stream, and a session reading source from one place and input
        # from another shares nothing. Unset, this is sys.stdin as before.
        self.interpreter = Interpreter(out=self._out, source=StdinSource(in_))
        self._buffer: list[str] = []
        self._face = "ascii"

    def feed(self, line: str) -> bool:
        """Take one line. Return True if more input is needed."""
        if not self._buffer and line.strip() in _FACE_COMMANDS:
            self._face = _FACE_COMMANDS[line.strip()]
            return False
        self._buffer.append(line)
        source = "\n".join(self._buffer) + "\n"

        try:
            depth = _open_blocks(source)
        except MatrixLangError as error:
            self._fail(error)
            return False

        if depth > 0:
            return True

        try:
            with recursion_guard():
                tree = parse(lex(source))
        except MatrixLangError as error:
            self._fail(error)
            return False

        if self._face == "glyph":
            # The echo precedes execution: it shows what is about to run,
            # and still appears when execution then fails. Guarded
            # separately from parsing: a long same-precedence chain parses
            # ITERATIVELY (one frame per chain) but render_glyph walks it
            # recursively, so this can fail even when parsing did not.
            try:
                with recursion_guard():
                    echo = render_glyph(tree)
            except MatrixLangError as error:
                self._fail(error)
                return False
            print(echo, end="", file=self._out)

        try:
            self.interpreter.run(tree)
        except MatrixLangError as error:
            self._fail(error)
        self._buffer.clear()
        return False

    def _fail(self, error: MatrixLangError) -> None:
        print(f"matrixlang: {error}", file=self._err)
        self._buffer.clear()


def _open_blocks(source: str) -> int:
    """How many blocks are still open, counted over tokens."""
    depth = 0
    for token in lex(source):
        if token.type in _OPENERS:
            depth += 1
        elif token.type is TokenType.FLATLINE:
            depth -= 1
    return max(depth, 0)


def repl(
    in_: TextIO | None = None,
    out: TextIO | None = None,
    err: TextIO | None = None,
) -> int:
    """Run an interactive session until end of input."""
    source = sys.stdin if in_ is None else in_
    sink = sys.stdout if out is None else out
    session = Repl(
        out=sink, err=sys.stderr if err is None else err, in_=source
    )
    needs_more = False

    while True:
        print(CONTINUATION if needs_more else PROMPT, end="", file=sink)
        sink.flush()
        line = source.readline()
        if not line:
            print(file=sink)
            return 0
        needs_more = session.feed(line.rstrip("\n"))
