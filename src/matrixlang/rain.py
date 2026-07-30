"""The digital-rain field: a pure, deterministic simulation.

No time, no terminal, no ANSI. advance() returns the cells to paint and
erase for one frame; who draws them, how fast and in what colour is the
player's problem (curtain.py). Everything here is a function of the seed,
so a field is reproducible on any machine — which is the whole reason the
tests can assert on an animation.

Rendering is sparse by construction: a column reports work only on the
tick its head crosses into a new row, so a frame is O(active columns),
never O(screen area).
"""

from dataclasses import dataclass
from random import Random

from matrixlang.glyphs import RAIN_ALPHABET

# Phase boundaries, in ticks. Columns are born up to SPAWN_END_TICK; after
# it the field drains, and that drain is the dissolve. MAX_TICKS is the
# hard stop: at curtain.FRAME_SECONDS (1/30) it caps the curtain at 1.67s.
SPAWN_END_TICK = 20
MAX_TICKS = 50

MIN_TRAIL = 3
MAX_TRAIL = 14

_RAMP_TICKS = 12
_SPAWN_FRACTION = 0.05
_MUTATION_CHANCE = 0.12

# Speed is expressed as how many ticks a column takes to cross the screen,
# NOT as rows per tick, so the drain closes in a bounded number of ticks at
# any terminal height. A fixed rows-per-tick speed drains a 12-row test
# field fine and strands a 50-row terminal still full of rain when
# MAX_TICKS expires. Trail length is capped at half the height for the
# same reason.
_FAST_CROSSING_TICKS = 8
_SLOW_CROSSING_TICKS = 18


@dataclass(frozen=True)
class Cell:
    """One glyph to draw. `level` is 1.0 at the head, falling to the tail."""

    row: int
    col: int
    glyph: str
    level: float


@dataclass(frozen=True)
class Frame:
    paint: tuple[Cell, ...]
    erase: tuple[tuple[int, int], ...]


class _Column:
    """One falling stream, occupying a single screen column."""

    def __init__(self, col: int, speed: float, length: int, rng: Random) -> None:
        self.col = col
        self._speed = speed
        self._length = length
        self._rng = rng
        self._head = 0.0
        self._row = -1
        self._previous_row = -1
        self._glyphs: dict[int, str] = {}

    def advance(self) -> bool:
        """Move the head. True if it crossed into a new row."""
        previous = self._row
        self._head += self._speed
        row = int(self._head)
        if row == previous:
            return False
        # Fill EVERY row crossed, not just the new head: a speed above 1.0
        # skips rows, and a skipped row would have no glyph to draw.
        for crossed in range(previous + 1, row + 1):
            self._glyphs[crossed] = self._rng.choice(RAIN_ALPHABET)
        self._previous_row = previous
        self._row = row
        self._mutate()
        return True

    def _mutate(self) -> None:
        """Occasionally re-roll one trail glyph, so the column shimmers."""
        if self._glyphs and self._rng.random() < _MUTATION_CHANCE:
            row = self._rng.choice(list(self._glyphs))
            self._glyphs[row] = self._rng.choice(RAIN_ALPHABET)

    def cells(self, height: int) -> list[Cell]:
        """The visible trail, head first."""
        visible: list[Cell] = []
        for offset in range(self._length):
            row = self._row - offset
            if 0 <= row < height:
                visible.append(
                    Cell(row, self.col, self._glyphs[row], 1.0 - offset / self._length)
                )
        return visible

    def tail_row(self) -> int:
        """The row that just fell off the end of the trail."""
        return self._row - self._length

    def vacated(self, height: int) -> list[int]:
        """Every row that left the trail on the last advance.

        One row per tick is not enough: a head moving `speed` rows drops
        `speed` rows off the tail, and erasing only the last of them
        leaves the rest lit until the curtain ends.
        """
        start = self._previous_row - self._length + 1
        stop = self._row - self._length + 1
        return [row for row in range(start, stop) if 0 <= row < height]

    def is_finished(self, height: int) -> bool:
        return self.tail_row() >= height


class RainField:
    def __init__(self, width: int, height: int, rng: Random) -> None:
        self.width = width
        self.height = height
        self._rng = rng
        self._tick = 0
        self._columns: list[_Column] = []
        # A shuffled pool of x positions, consumed and never reused. Two
        # columns sharing an x would erase each other's cells.
        self._free = list(range(width))
        rng.shuffle(self._free)

    @property
    def active(self) -> int:
        return len(self._columns)

    def advance(self) -> Frame:
        self._tick += 1
        self._spawn()
        paint: list[Cell] = []
        erase: list[tuple[int, int]] = []
        for column in self._columns:
            if not column.advance():
                continue
            paint.extend(column.cells(self.height))
            erase.extend((row, column.col) for row in column.vacated(self.height))
        self._columns = [c for c in self._columns if not c.is_finished(self.height)]
        return Frame(tuple(paint), tuple(erase))

    def is_done(self) -> bool:
        if self._tick >= MAX_TICKS:
            return True
        return self._tick > SPAWN_END_TICK and not self._columns

    def _spawn(self) -> None:
        if self._tick > SPAWN_END_TICK:
            return
        # Ramp the birth rate so the field builds in waves rather than
        # appearing as one slab (design S5-4, "density waves").
        ramp = min(self._tick / _RAMP_TICKS, 1.0)
        births = max(1, int(self.width * _SPAWN_FRACTION * ramp))
        for _ in range(births):
            if not self._free:
                return
            self._columns.append(
                _Column(
                    self._free.pop(),
                    self._speed(),
                    self._trail(),
                    self._rng,
                )
            )

    def _speed(self) -> float:
        """Rows per tick, derived from a crossing time so the drain always
        closes within MAX_TICKS whatever the terminal height."""
        crossing = self._rng.uniform(_FAST_CROSSING_TICKS, _SLOW_CROSSING_TICKS)
        return self.height / crossing

    def _trail(self) -> int:
        """Trail length, never more than half the screen — a trail longer
        than the screen would still be draining when MAX_TICKS expired."""
        longest = max(MIN_TRAIL, min(MAX_TRAIL, self.height // 2))
        return self._rng.randint(MIN_TRAIL, longest)
