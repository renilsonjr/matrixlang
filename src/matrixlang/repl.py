"""Interactive MatrixLang session.

Buffers input while a block is open, so a `dejavu` loop can be typed at the
prompt and watched running — which is the point of Stage 3.

Depth is counted over the TOKEN stream, not over raw text: a `#` comment or
a string containing the word "flatline" must not close a block.
"""

import sys
from typing import TextIO

from matrixlang.errors import MatrixLangError
from matrixlang.interpreter import Interpreter
from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.tokens import TokenType

PROMPT = "> "
CONTINUATION = "... "

_OPENERS = (TokenType.REDPILL, TokenType.DEJAVU)


class Repl:
    def __init__(self, out: TextIO | None = None) -> None:
        self._out = sys.stdout if out is None else out
        self.interpreter = Interpreter(out=self._out)
        self._buffer: list[str] = []

    def feed(self, line: str) -> bool:
        """Take one line. Return True if more input is needed."""
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
            self.interpreter.run(parse(lex(source)))
        except MatrixLangError as error:
            self._fail(error)
        self._buffer.clear()
        return False

    def _fail(self, error: MatrixLangError) -> None:
        print(f"matrixlang: {error}", file=self._out)
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


def repl(in_: TextIO | None = None, out: TextIO | None = None) -> int:
    """Run an interactive session until end of input."""
    source = sys.stdin if in_ is None else in_
    sink = sys.stdout if out is None else out
    session = Repl(out=sink)
    needs_more = False

    while True:
        print(CONTINUATION if needs_more else PROMPT, end="", file=sink)
        sink.flush()
        line = source.readline()
        if not line:
            print(file=sink)
            return 0
        needs_more = session.feed(line.rstrip("\n"))
