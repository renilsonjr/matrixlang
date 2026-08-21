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
    """Lines from a list, each element one line, nothing split.

    The tests use it, and so does the playground: `site/glue.py` gives it the
    answers a reader typed one at a time, precisely because it splits nothing.
    An answer is already exactly one line, and putting it back through a
    splitter is what once made a blank answer vanish and shifted every answer
    after a box that ended in a newline.
    """

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

    Splits on newlines and nothing else, matching `StdinSource` exactly.
    These two are the surfaces a reader chooses between -- the same input
    pasted into the browser box or piped at a terminal must yield the same
    lines, or a program means different things on the two. `str.splitlines`
    would not: it also breaks on \\v, \\f, \\x85 and U+2028/9, which
    `readline` treats as ordinary characters inside a line.
    """

    def __init__(self, text: str) -> None:
        super().__init__(_split_lines(text))


def _split_lines(text: str) -> list[str]:
    """`text` as the lines `StdinSource` would have read from it."""
    if text == "":
        return []
    # A trailing newline ends the last line rather than starting an empty
    # one -- readline() returns "" at end of stream, not one more line.
    if text.endswith("\n"):
        text = text[:-1]
    # `.rstrip("\r")` for the same reason StdinSource does: CRLF text
    # must not leave a carriage return glued to every line.
    return [line.rstrip("\r") for line in text.split("\n")]


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
