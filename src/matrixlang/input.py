"""Where a running program's input comes from.

The mirror of `events.py`. That module exists because printing decides
*where* output goes at the point that knows least about it; reading is the
same decision in the other direction. The interpreter asks for a line and
never learns whether it came from a terminal, a textarea, or a list in a
test.

`next_line` returns None for "exhausted", never a sentinel string: a blank
line is real input, and "" would make the two indistinguishable.

Pure protocol and data, like `tokens.py` and `nodes.py`. Imports nothing
from the interpreter.
"""

import sys
from typing import Protocol, Sequence, TextIO


class InputSource(Protocol):
    """Anything a running program can read lines from."""

    def next_line(self) -> str | None: ...


class EmptySource:
    """No input at all. The Interpreter's default.

    The default is deliberately NOT StdinSource. A default that read a
    terminal would hang any caller that forgot to pass a source --
    including `operator/validate.py`'s dry run, which executes untrusted
    candidate programs inside a server request.
    """

    def next_line(self) -> str | None:
        return None


class ListSource:
    """Lines from a list. What the tests use."""

    def __init__(self, lines: Sequence[str]) -> None:
        self._lines = list(lines)
        self._index = 0

    def next_line(self) -> str | None:
        if self._index >= len(self._lines):
            return None
        line = self._lines[self._index]
        self._index += 1
        return line


class BufferSource(ListSource):
    """Lines from text supplied before the program ran. The browser's.

    Never blocks, which is the whole reason the playground can offer input:
    JavaScript is single-threaded, so a read that waited would freeze the
    tab and the cascade drawing in it.
    """

    def __init__(self, text: str) -> None:
        super().__init__(text.splitlines())


class StdinSource:
    """Lines from a stream, normally the real stdin. The CLI's and REPL's.

    May block, which is correct at a terminal and nowhere else.
    """

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = sys.stdin if stream is None else stream

    def next_line(self) -> str | None:
        line = self._stream.readline()
        # readline() returns "" only at end of stream; a blank line is
        # "\n". Testing for "" rather than falsiness keeps them apart.
        if line == "":
            return None
        return line.rstrip("\r\n")


class ConstantSource:
    """The same line, forever. Used by the validate gate.

    A dry run asks "does this parse and execute without crashing", not
    "what does this print". Immediate exhaustion would answer a question
    nobody asked and reject correct programs for lacking input the gate
    never had. Bounded by the caller's step limit, so it cannot hang.
    """

    def __init__(self, line: str) -> None:
        self._line = line

    def next_line(self) -> str | None:
        return self._line
