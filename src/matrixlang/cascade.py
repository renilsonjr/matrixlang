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
from math import floor
from random import Random

from matrixlang.events import Event, Output, Statement
from matrixlang.glyphs import AMBIENT_ALPHABET
from matrixlang.nodes import Program, Stmt
from matrixlang.render import render_glyph
from matrixlang.translit import transliterate


class Kind(Enum):
    SOURCE = auto()
    OUTPUT = auto()
    AMBIENT = auto()


# Ambient never rises above this, so it cannot be mistaken for the head of
# a stream carrying your program. Legibility of the real material is what
# the whole two-layer split exists to protect.
AMBIENT_LEVEL = 0.3


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


class _Ambient:
    """A column of filler glyphs that falls forever.

    Behind the program's material, never in front of it. It exists so the
    window keeps moving once a program has finished — a screen that stops
    is not a cascade — and for no other reason, which is why it is opt-in
    and capped at `AMBIENT_LEVEL`.
    """

    def __init__(self, col: int, height: int, rng: Random) -> None:
        self.col = col
        self._height = height
        self._rng = rng
        self._speed = rng.uniform(0.25, 0.7)
        self._length = rng.randint(3, max(4, height // 2))
        # Starts already on screen, staggered. Starting above the top means
        # the window is blank for the first second, which is precisely the
        # thing ambient exists to prevent.
        self._head = rng.uniform(0.0, float(height))
        self._glyphs: dict[int, str] = {}
        for row in range(floor(self._head) - self._length + 1, floor(self._head) + 1):
            self._glyphs[row] = rng.choice(AMBIENT_ALPHABET)

    def advance(self) -> None:
        # floor, not int(): int() truncates toward zero, so a head moving
        # through negative rows reports the same row twice and skips the
        # fill. Every row the head crosses must get a glyph or the trail
        # has holes in it.
        previous = floor(self._head)
        self._head += self._speed
        row = floor(self._head)
        for crossed in range(previous + 1, row + 1):
            self._glyphs[crossed] = self._rng.choice(AMBIENT_ALPHABET)
        if row - self._length >= self._height:
            # Recycle rather than accumulate: an unbounded glyph dict is a
            # slow leak in a window that may stay open for hours. Re-enters
            # from just above the top so the column is never absent for long.
            self._head = float(-self._length)
            self._glyphs.clear()

    def cells(self) -> list[Cell]:
        head = floor(self._head)
        visible = []
        for offset in range(self._length):
            row = head - offset
            if 0 <= row < self._height and row in self._glyphs:
                visible.append(
                    Cell(
                        row=row,
                        col=self.col,
                        glyph=self._glyphs[row],
                        level=AMBIENT_LEVEL * (1.0 - offset / self._length),
                        kind=Kind.AMBIENT,
                    )
                )
        return visible


class CascadeField:
    def __init__(
        self, width: int, height: int, rng: Random, ambient: int = 0
    ) -> None:
        self.width = width
        self.height = height
        self._rng = rng
        # Distinct columns, sampled without replacement. Picking each one
        # independently lets two ambient columns land on the same x and
        # overwrite each other — the same defect the spike hit with
        # program streams, and just as invisible in filler glyphs.
        self._ambient = [
            _Ambient(col, height, rng)
            for col in rng.sample(range(width), min(ambient, width))
        ]
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

        # Ambient is a layer behind, never a peer. Program material wins
        # any cell they both want: the whole point of the two layers is
        # that filler can never obscure a line of your program.
        taken = {(cell.row, cell.col) for cell in cells}
        for column in self._ambient:
            column.advance()
            cells.extend(
                cell
                for cell in column.cells()
                if (cell.row, cell.col) not in taken
            )
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
