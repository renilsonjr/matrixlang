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


# Two screens' worth. A line falls vertically and takes seconds to do it,
# so more than this can never be read before it is replaced -- a larger cap
# would buy memory pressure and nothing else. Recursion is what makes this
# necessary: fib(10) alone emits 366 lines.
MAX_HISTORY = 200


# Output falls slower so results linger: a value is the thing a reader
# came for, and source scrolls past constantly. Halved from the original
# pair, which crossed the field in well under a second and read as a wipe
# rather than as rain.
_SPEED = {Kind.SOURCE: 0.45, Kind.OUTPUT: 0.22}

# Every stream draws its own multiplier. Without it the field held exactly
# two speeds, so every source line sat on the identical row as every other
# one and the whole thing read as a block of plain text sliding down.
#
# The range is chosen so `SOURCE * JITTER[0] > OUTPUT * JITTER[1]` — the
# two bands do not overlap, so "output falls slower than source" stays a
# guarantee rather than becoming a tendency.
JITTER = (0.7, 1.3)

# How many lines may start falling on one frame. Releasing every queued
# line at once was the other half of the lockstep: they all began at the
# same row on the same frame. A trickle desynchronises them immediately,
# and the jitter widens the gap from there.
SPAWNS_PER_FRAME = 2

# The brightness ramp is a fixed number of cells, not a fraction of the
# line. Scaling it to the line meant a 3-glyph line faded over 3 cells and
# a 20-glyph line over 20, so the head falloff depended on the content.
TRAIL = 6

# ...and it bottoms out here rather than at zero. A long line must stay
# readable all the way up, or the cascade stops carrying the program.
FLOOR = 0.28


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

    def __init__(self, col: int, text: str, kind: Kind, speed: float) -> None:
        self.col = col
        self.kind = kind
        self._text = text
        self._speed = speed
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
        visible: list[Cell] = []
        for index, char in enumerate(self._text):
            offset = len(self._text) - 1 - index
            row = head - offset
            if 0 <= row < height:
                visible.append(
                    Cell(
                        row=row,
                        col=self.col,
                        glyph=char,
                        level=max(FLOOR, 1.0 - offset / TRAIL),
                        kind=self.kind,
                    )
                )
        return visible

    def is_finished(self, height: int) -> bool:
        """True once the topmost character has fallen past the bottom."""
        return int(self._head) - (len(self._text) - 1) >= height


class CascadeField:
    def __init__(
        self,
        width: int,
        height: int,
        rng: Random,
        loop: bool = False,
        glyph_source: bool = True,
    ) -> None:
        self.width = width
        self.height = height
        self._rng = rng
        self._loop = loop
        # A pure glyph wall. D-03 keeps identifiers Latin in the glyph
        # *face* because in the editor "the only Latin text is the thing
        # you need to find" — but the cascade is not the editor, and the
        # editing surface shows the real source alongside it. Set False to
        # get the plain glyph face back, Latin identifiers and all.
        self._glyph_source = glyph_source
        # Everything ever added, so a looping field can replay it. This is
        # the only thing that falls: nothing random is ever generated, so
        # the cascade carries the program and nothing else.
        self._history: list[tuple[str, Kind]] = []
        self._streams: list[_Stream] = []
        self._waiting: list[tuple[str, Kind]] = []


    # --- input ----------------------------------------------------------

    def add(self, text: str, kind: Kind) -> None:
        """Queue a line. It falls as soon as a column frees up."""
        if text:
            self._waiting.append((text, kind))
            self._history.append((text, kind))
            if len(self._history) > MAX_HISTORY:
                del self._history[: len(self._history) - MAX_HISTORY]

    def consume(self, event: Event) -> None:
        """Turn an execution event into falling text.

        `Error` is deliberately absent: diagnostics are plain text in the
        status strip, never transliterated. The spike proved a glyph
        diagnostic hides the line number, the misspelled name and the
        remedy all at once.
        """
        if isinstance(event, Output):
            self.add(transliterate(event.text), Kind.OUTPUT)
        elif isinstance(event, Statement) and event.node is not None:
            self.add(_header(event.node, self._glyph_source), Kind.SOURCE)

    # --- simulation -----------------------------------------------------

    def advance(self) -> tuple[Cell, ...]:
        # Order matters, and the obvious order is wrong. Retiring first
        # uses last frame's positions, so the frame on which a stream moves
        # fully off screen draws nothing and is only retired the frame
        # after — one blank frame at every handover. Move, then retire on
        # the positions that just happened, then refill.
        for stream in self._streams:
            stream.advance()
        self._retire()
        self._replay()
        # New streams advance immediately, or they contribute nothing to
        # the frame that created them and the blank frame comes back.
        for stream in self._spawn():
            stream.advance()

        cells: list[Cell] = []
        for stream in self._streams:
            cells.extend(stream.cells(self.height))
        return tuple(cells)

    def _replay(self) -> None:
        """Re-queue the whole program once it has all fallen off.

        A screen that stops is not a cascade, and the alternative — filler
        glyphs behind static output — puts decoration back in a project
        whose whole premise is that the cascade carries the program. So the
        program's own material is what repeats.

        A program that produced nothing has nothing to replay, and must not
        spin on an empty history.
        """
        if self._loop and self._history and not self._streams and not self._waiting:
            self._waiting.extend(self._history)

    def is_empty(self) -> bool:
        return not self._streams and not self._waiting

    def _retire(self) -> None:
        self._streams = [s for s in self._streams if not s.is_finished(self.height)]

    def _spawn(self) -> list[_Stream]:
        """Start every queued line that has a column free. Returns the new ones."""
        occupied = {stream.col for stream in self._streams}
        free = [col for col in range(self.width) if col not in occupied]
        self._rng.shuffle(free)
        started: list[_Stream] = []
        while self._waiting and free and len(started) < SPAWNS_PER_FRAME:
            text, kind = self._waiting.pop(0)
            speed = _SPEED[kind] * self._rng.uniform(*JITTER)
            stream = _Stream(free.pop(), text, kind, speed)
            self._streams.append(stream)
            started.append(stream)
        return started


def _header(stmt: Stmt, glyph_source: bool = True) -> str:
    """A statement's own first line, in the glyph face.

    Rendering a block statement yields its entire body, and every body
    statement emits its own event. Taking the header alone is what stops
    each line of a loop from appearing twice.

    With `glyph_source`, the Latin left over in that face — identifiers and
    string contents — is transliterated too, giving a wall with no Latin in
    it at all.

    Transliterating **on top of the glyph face**, rather than transliterating
    the ASCII source, is deliberate. The alternative spells `construct` out
    as nine glyphs: it decodes perfectly but doubles every line, and since a
    line falls vertically, height is length — a 30-row field stops fitting
    whole statements. It also erases the 54-slot table from the screen, which
    is the notation that makes this MatrixLang rather than generic rain.

    The cost, stated because it is real: a naive decode of a source line
    recovers identifiers and strings but garbles keywords, because the two
    tables overlap — the glyph the language assigns to `construct` means a
    letter in the display table. Output carries no language glyphs and stays
    exactly decodable, and output is the half anyone would want to read back.
    """
    rendered = render_glyph(Program([stmt]))
    lines = [line.strip() for line in rendered.splitlines() if line.strip()]
    header = lines[0] if lines else ""
    # escape_glyphs=False: this line is already full of the language's own
    # glyphs, and escaping each one would double its height on screen —
    # the exact cost that decided against spelling `construct` out. The
    # line is documented as not decodable anyway (the two tables overlap),
    # so the escape would buy a property it does not have. Output, which
    # does have it, is transliterated with the guarantee intact.
    return transliterate(header, escape_glyphs=False) if glyph_source else header
