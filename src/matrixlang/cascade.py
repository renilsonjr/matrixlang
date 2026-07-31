"""The content-carrying field: which glyph sits in which cell, and how bright.

The Stage 5 rain was decorative — random glyphs from the katakana block,
falling before the program ran. This is the opposite: every column carries
real material, a line of the program in its glyph face or a value the
program actually produced.

That difference is not cosmetic, it is a correctness requirement. Random
glyphs all look alike, so the decorative field could tolerate two streams
sharing a column or a line rendering backwards and nobody would see it.
Here those bugs silently corrupt the program on screen. Both were real
defects in the spike, and both have a regression test.

Pure and deterministic given a seed, with no Tk, no clock and no colour,
for the same reason rain.py was: everything a viewer actually sees is
decided here, so the window stays a thin edge that can be left untested.
"""

from dataclasses import dataclass
from enum import Enum, auto
from random import Random

from matrixlang.events import Event, Output, Statement
from matrixlang.nodes import Program, Stmt
from matrixlang.render import render_glyph
from matrixlang.translit import transliterate


class Kind(Enum):
    SOURCE = auto()
    OUTPUT = auto()


# Output falls slower so results linger: a value is the thing a reader
# came for, and source scrolls past constantly.
_SPEED = {Kind.SOURCE: 0.9, Kind.OUTPUT: 0.45}


@dataclass(frozen=True)
class Cell:
    """One glyph to draw. `level` is 1.0 at the head, falling up the trail."""

    row: int
    col: int
    glyph: str
    level: float
    kind: Kind


class _Stream:
    """One line of text, falling down a single reserved column.

    The column is reserved for the stream's whole life. Returning it to the
    pool at spawn time — which is what the spike did first — lets two
    streams share a column and overwrite each other.
    """

    def __init__(self, col: int, text: str, kind: Kind) -> None:
        self.col = col
        self.kind = kind
        self._text = text
        self._speed = _SPEED[kind]
        self._head = -1.0

    def advance(self) -> None:
        self._head += self._speed

    def cells(self, height: int) -> list[Cell]:
        """The visible characters.

        Character 0 sits highest and the last character leads the fall, so
        reading the column downward gives the line in natural order. The
        obvious layout — first character at the head — renders every line
        backwards.
        """
        head = int(self._head)
        length = len(self._text)
        visible: list[Cell] = []
        for index, char in enumerate(self._text):
            offset = length - 1 - index
            row = head - offset
            if 0 <= row < height:
                visible.append(
                    Cell(
                        row=row,
                        col=self.col,
                        glyph=char,
                        level=1.0 - offset / length,
                        kind=self.kind,
                    )
                )
        return visible

    def is_finished(self, height: int) -> bool:
        """True once the topmost character has fallen past the bottom."""
        return int(self._head) - (len(self._text) - 1) >= height


class CascadeField:
    def __init__(self, width: int, height: int, rng: Random) -> None:
        self.width = width
        self.height = height
        self._rng = rng
        self._streams: list[_Stream] = []
        self._waiting: list[tuple[str, Kind]] = []
        # Output is remembered, not merely shown. A falling column is gone
        # once it leaves the screen, and output that cannot be read after
        # the program ends is output the viewer never got.
        self._transcript: list[str] = []

    # --- input ----------------------------------------------------------

    def add(self, text: str, kind: Kind) -> None:
        """Queue a line. It falls as soon as a column frees up."""
        if text:
            self._waiting.append((text, kind))

    def consume(self, event: Event) -> None:
        """Turn an execution event into falling text.

        `Error` is deliberately absent: diagnostics are plain text in the
        status strip, never transliterated. The spike proved a glyph
        diagnostic hides the line number, the misspelled name and the
        remedy all at once.
        """
        if isinstance(event, Output):
            glyphs = transliterate(event.text)
            self._transcript.append(glyphs)
            self.add(glyphs, Kind.OUTPUT)
        elif isinstance(event, Statement) and event.node is not None:
            self.add(_header(event.node), Kind.SOURCE)

    def transcript(self) -> list[str]:
        """Every output line the program produced, in glyphs, in order."""
        return list(self._transcript)

    # --- simulation -----------------------------------------------------

    def advance(self) -> tuple[Cell, ...]:
        self._retire()
        self._spawn()
        for stream in self._streams:
            stream.advance()
        cells: list[Cell] = []
        for stream in self._streams:
            cells.extend(stream.cells(self.height))
        return tuple(cells)

    def is_empty(self) -> bool:
        return not self._streams and not self._waiting

    def _retire(self) -> None:
        self._streams = [s for s in self._streams if not s.is_finished(self.height)]

    def _spawn(self) -> None:
        occupied = {stream.col for stream in self._streams}
        free = [col for col in range(self.width) if col not in occupied]
        self._rng.shuffle(free)
        while self._waiting and free:
            text, kind = self._waiting.pop(0)
            self._streams.append(_Stream(free.pop(), text, kind))


def _header(stmt: Stmt) -> str:
    """A statement's own first line, in the glyph face.

    Rendering a block statement yields its entire body, and every body
    statement emits its own event. Taking the header alone is what stops
    each line of a loop from appearing twice.
    """
    rendered = render_glyph(Program([stmt]))
    lines = [line.strip() for line in rendered.splitlines() if line.strip()]
    return lines[0] if lines else ""
