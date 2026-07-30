# Stage 5 — Runner Presentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Digital rain plays as a curtain around `matrixlang run` on a capable terminal, and not one escape byte reaches a non-TTY.

**Architecture:** Three new modules with a strict purity gradient. `ansi.py` builds escape strings and detects colour capability from an environment passed in as a parameter. `rain.py` simulates the falling field — deterministic given a seed, with no time, no terminal, and no ANSI. `curtain.py` is the only impure module: it owns the frame loop, the clock, the writer, and the `try/finally` that always restores the terminal. The CLI calls one function.

**Tech Stack:** Python ≥3.11, standard library only. pytest as the sole dev dependency.

**Reference:** `docs/superpowers/specs/2026-07-30-stage-5-runner-presentation-design.md` (decisions S5-1…S5-4). Parent spec Stage 5 done-when: *"it reads as the film's aesthetic and remains debuggable."* §4.2 R-03: rain in the runner, never the editor. §3: terminal rain is solved work — do not rebuild it.

## Global Constraints

- **Standard library only** in `src/matrixlang/`. pytest is a dev dependency and must never be imported by shipped code. No third-party dependencies anywhere.
- **Katakana literals live ONLY in `src/matrixlang/glyphs.py`.** `tests/test_architecture.py::test_only_glyphs_contains_a_katakana_character` enforces this over every `src/matrixlang/*.py`. `RAIN_ALPHABET` is built with `chr()` from codepoints, so it adds no literal — keep it that way.
- **The presentation layer never reaches the interpreter.** `ansi` imports nothing; `rain` imports only `glyphs`; `curtain` imports only `ansi` and `rain`. Extend `tests/test_architecture.py`'s `_ALLOWED` in the same task that adds each module — `test_every_module_has_an_entry_in_the_allow_table` fails otherwise.
- **`detect_color_mode` takes the environment as a parameter and never reads `os.environ`.** That is what makes capability detection table-testable. Same rule for TTY-ness: it is `writer.isatty()`, never a global.
- **When stdout is not a TTY, `matrixlang run` writes zero escape bytes.** This is the "remains debuggable" contract. It is pinned by a teeth-checked test.
- **The terminal is restored unconditionally.** `curtain.play` wraps its loop in `try/finally`; the `finally` writes show-cursor and leave-alternate-screen on every exit path including `KeyboardInterrupt`.
- **Never raise Python's recursion limit**, and never call `time.sleep` outside `curtain.play`'s injected `sleep` parameter — a test that really sleeps is a test nobody runs.
- **Tests are written before implementation, in every task.**
- **Commit at the end of every task.**

**Refinement of the spec's timing note:** the spec says "roughly 1.6 seconds at ~24 fps." This plan uses **30 fps × 50 ticks = 1.67 s**, which honours the stated duration. The constants live in exactly two places (`rain.SPAWN_END_TICK` / `rain.MAX_TICKS` and `curtain.FRAME_SECONDS`) and are the numbers most likely to want tuning once the effect is watchable.

**Environment note for every task:** run tests with `.venv/bin/python -m pytest`. Never run `pip install`, never create a venv, never add a conftest.py. Known machine fault: if `import matrixlang` fails with ModuleNotFoundError, run `chflags -R nohidden .venv` and continue (note it in your report). Any other import failure: report BLOCKED.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `src/matrixlang/ansi.py` | Create: `ColorMode`, `detect_color_mode`, escape-string builders, `fg`. Imports nothing |
| `src/matrixlang/rain.py` | Create: `Cell`, `Frame`, `RainField`. Pure simulation. Imports `glyphs` |
| `src/matrixlang/curtain.py` | Create: `should_play`, `play`, `play_if_supported`. The only impure module |
| `src/matrixlang/glyphs.py` | Modify: add `RAIN_ALPHABET` |
| `src/matrixlang/cli.py` | Modify: `run` gains `--no-rain`; `_command_run` plays the curtain after parse |
| `tests/test_ansi.py` | Create: capability table, escape strings, colour ramps |
| `tests/test_rain.py` | Create: field invariants under a fixed seed |
| `tests/test_curtain.py` | Create: the player, with both teeth-checks |
| `tests/test_glyphs.py` | Modify: `RAIN_ALPHABET` coverage |
| `tests/test_cli.py` | Modify: the non-TTY guarantee and `--no-rain` |
| `tests/test_architecture.py` | Modify: `_ALLOWED` gains three modules, `cli` gains one member |
| `README.md` | Modify: status, usage, attribution |

**Why three modules rather than one.** The effect is an animation, and animations are notoriously untested. Splitting on purity is what makes it testable: the field is a function of its seed, the escapes are functions of their arguments, and only the ~40-line player needs fakes. A single `rain.py` doing all three jobs would be the one file in this codebase with no way to assert on its behaviour.

---

### Task 1: `ansi.py` — escape sequences and colour capability

**Files:**
- Create: `src/matrixlang/ansi.py`, `tests/test_ansi.py`
- Modify: `tests/test_architecture.py`

**Interfaces:**
- Consumes: nothing.
- Produces:
  - `ColorMode` enum with members `TRUECOLOR`, `COLOR256`, `BASIC`, `NONE`
  - `detect_color_mode(env: Mapping[str, str], isatty: bool) -> ColorMode`
  - `enter_alt_screen() -> str`, `leave_alt_screen() -> str`, `hide_cursor() -> str`, `show_cursor() -> str`, `clear() -> str`, `reset() -> str`
  - `move(row: int, col: int) -> str` — 0-indexed in, 1-indexed ANSI out
  - `fg(level: float, mode: ColorMode) -> str` — brightness 0.0–1.0 to colour

- [ ] **Step 1: Write the failing tests**

Create `tests/test_ansi.py`:

```python
"""The escape layer: pure strings in, pure strings out.

detect_color_mode takes the environment as an argument precisely so this
file can hand it fixtures instead of mutating os.environ.
"""

import pytest

from matrixlang.ansi import ColorMode, detect_color_mode, fg, move


@pytest.mark.parametrize(
    "env, isatty, expected",
    [
        ({"TERM": "xterm-256color"}, False, ColorMode.NONE),
        ({"NO_COLOR": "1", "TERM": "xterm-256color"}, True, ColorMode.NONE),
        ({"NO_COLOR": "", "TERM": "xterm-256color"}, True, ColorMode.NONE),
        ({"TERM": "dumb"}, True, ColorMode.NONE),
        ({}, True, ColorMode.NONE),
        ({"TERM": "xterm", "COLORTERM": "truecolor"}, True, ColorMode.TRUECOLOR),
        ({"TERM": "xterm", "COLORTERM": "24bit"}, True, ColorMode.TRUECOLOR),
        ({"TERM": "xterm-256color"}, True, ColorMode.COLOR256),
        ({"TERM": "xterm"}, True, ColorMode.BASIC),
    ],
)
def test_capability_detection(env, isatty, expected):
    assert detect_color_mode(env, isatty) is expected


def test_no_color_is_honoured_even_when_empty():
    # The NO_COLOR standard is presence-based: an empty value still means
    # "no colour". Testing `if env.get("NO_COLOR")` instead of
    # `if "NO_COLOR" in env` would silently ignore the empty case.
    assert detect_color_mode({"NO_COLOR": "", "TERM": "xterm"}, True) is ColorMode.NONE


def test_move_converts_zero_indexed_cells_to_one_indexed_ansi():
    # The field thinks in 0-indexed rows; ANSI counts from 1. An off-by-one
    # here writes the top row off-screen and is invisible in a screenshot.
    assert move(0, 0) == "\x1b[1;1H"
    assert move(3, 7) == "\x1b[4;8H"


def test_none_mode_produces_no_colour_at_all():
    assert fg(1.0, ColorMode.NONE) == ""


def test_basic_mode_separates_head_from_trail():
    assert fg(1.0, ColorMode.BASIC) == "\x1b[1;32m"
    assert fg(0.5, ColorMode.BASIC) == "\x1b[32m"


def test_256_mode_uses_the_cube_and_a_white_head():
    assert fg(1.0, ColorMode.COLOR256) == "\x1b[38;5;231m"
    assert fg(0.5, ColorMode.COLOR256).startswith("\x1b[38;5;")


def test_truecolor_head_is_near_white():
    assert fg(1.0, ColorMode.TRUECOLOR) == "\x1b[38;2;215;255;215m"


def test_truecolor_green_rises_monotonically_with_level():
    # The gradient IS the effect: if brightness does not increase toward
    # the head, the column reads as a uniform smear.
    def green(level):
        return int(fg(level, ColorMode.TRUECOLOR).split(";")[3])

    levels = [0.1, 0.3, 0.5, 0.7, 0.9]
    greens = [green(level) for level in levels]
    assert greens == sorted(greens)
    assert len(set(greens)) == len(greens)
```

In `tests/test_architecture.py`, add to `_ALLOWED`:

```python
    "ansi": set(),
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_ansi.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'matrixlang.ansi'`.

- [ ] **Step 3: Write the module**

Create `src/matrixlang/ansi.py`:

```python
"""ANSI escape sequences and terminal colour capability.

Pure string construction: every function here returns text and writes
nothing. Capability detection takes the environment as a parameter and
never reads os.environ, which is what makes it table-testable.

This module imports nothing from the toolchain — the presentation layer
must never be able to reach the interpreter.
"""

from collections.abc import Mapping
from enum import Enum, auto

CSI = "\x1b["


class ColorMode(Enum):
    TRUECOLOR = auto()
    COLOR256 = auto()
    BASIC = auto()
    NONE = auto()


def detect_color_mode(env: Mapping[str, str], isatty: bool) -> ColorMode:
    """How much colour this terminal can show. NONE means: no rain.

    NONE is the single answer to "there should be no rain" — it absorbs
    the non-TTY case, the NO_COLOR opt-out and dumb terminals, so no
    caller has to re-check any of them.
    """
    if not isatty:
        return ColorMode.NONE
    # Presence, not truthiness: NO_COLOR="" still means no colour.
    if "NO_COLOR" in env:
        return ColorMode.NONE
    term = env.get("TERM", "")
    if term in ("", "dumb"):
        return ColorMode.NONE
    if env.get("COLORTERM", "") in ("truecolor", "24bit"):
        return ColorMode.TRUECOLOR
    if "256color" in term:
        return ColorMode.COLOR256
    return ColorMode.BASIC


def enter_alt_screen() -> str:
    return f"{CSI}?1049h"


def leave_alt_screen() -> str:
    return f"{CSI}?1049l"


def hide_cursor() -> str:
    return f"{CSI}?25l"


def show_cursor() -> str:
    return f"{CSI}?25h"


def clear() -> str:
    return f"{CSI}2J"


def reset() -> str:
    return f"{CSI}0m"


def move(row: int, col: int) -> str:
    """Cursor to a 0-indexed cell. ANSI itself counts from 1."""
    return f"{CSI}{row + 1};{col + 1}H"


# Above this brightness a cell is the column's head and burns near-white.
_HEAD_LEVEL = 0.95

# Greens from the xterm-256 cube, dimmest first.
_C256_RAMP = (22, 28, 34, 40, 46, 83, 120, 157)


def fg(level: float, mode: ColorMode) -> str:
    """Foreground colour for a brightness in 0.0-1.0. 1.0 is the head."""
    if mode is ColorMode.NONE:
        return ""
    if mode is ColorMode.BASIC:
        return f"{CSI}1;32m" if level >= _HEAD_LEVEL else f"{CSI}32m"
    if mode is ColorMode.COLOR256:
        if level >= _HEAD_LEVEL:
            return f"{CSI}38;5;231m"
        index = min(int(level * len(_C256_RAMP)), len(_C256_RAMP) - 1)
        return f"{CSI}38;5;{_C256_RAMP[index]}m"
    if level >= _HEAD_LEVEL:
        return f"{CSI}38;2;215;255;215m"
    return f"{CSI}38;2;{int(20 * level)};{int(60 + 195 * level)};{int(40 * level)}m"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_ansi.py tests/test_architecture.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/ansi.py tests/test_ansi.py tests/test_architecture.py
git commit -m "feat: ANSI escapes and colour-capability detection"
```

---

### Task 2: `rain.py` — the field simulation

**Files:**
- Create: `src/matrixlang/rain.py`, `tests/test_rain.py`
- Modify: `src/matrixlang/glyphs.py`, `tests/test_glyphs.py`, `tests/test_architecture.py`

**Interfaces:**
- Consumes: `RAIN_ALPHABET` from `matrixlang.glyphs` (added in this task).
- Produces:
  - `RAIN_ALPHABET: tuple[str, ...]` in `glyphs.py` — the full U+FF66–FF9D block, 56 chars
  - `Cell(row: int, col: int, glyph: str, level: float)` — frozen dataclass
  - `Frame(paint: tuple[Cell, ...], erase: tuple[tuple[int, int], ...])` — frozen dataclass
  - `RainField(width: int, height: int, rng: Random)` with `advance() -> Frame`, `is_done() -> bool`, and an `active` property returning the live column count
  - Module constants `SPAWN_END_TICK = 20`, `MAX_TICKS = 50`, `MIN_TRAIL = 3`, `MAX_TRAIL = 14`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_glyphs.py` (it already imports `GLYPHS`; add `RAIN_ALPHABET` to that import):

```python
def test_the_rain_alphabet_is_the_whole_katakana_block():
    # 56 characters, U+FF66-FF9D inclusive. The 32 language slots would
    # read as a repeating pattern in a full-screen field, not as rain.
    assert len(RAIN_ALPHABET) == 56
    assert all(len(glyph) == 1 for glyph in RAIN_ALPHABET)
    assert all(0xFF66 <= ord(glyph) <= 0xFF9D for glyph in RAIN_ALPHABET)


def test_every_language_glyph_is_in_the_rain_alphabet():
    # The table is a subset of the block the rain draws from, so the rain
    # and the language cannot drift onto different alphabets.
    assert set(GLYPHS.values()) <= set(RAIN_ALPHABET)
```

Create `tests/test_rain.py`:

```python
"""Field invariants under a fixed seed.

The field is a pure function of its seed, which is the only reason an
animation can be asserted on at all: RainField(w, h, Random(7)) advanced
N times produces the same cells on every machine, every run.
"""

from random import Random

from matrixlang.glyphs import RAIN_ALPHABET
from matrixlang.rain import MAX_TICKS, MAX_TRAIL, SPAWN_END_TICK, RainField


def frames(seed: int, ticks: int, width: int = 40, height: int = 12):
    field = RainField(width, height, Random(seed))
    return [field.advance() for _ in range(ticks)]


def test_the_field_is_deterministic_for_a_seed():
    # No shrinking, no reruns: a seed reproduces its animation exactly.
    assert frames(7, 20) == frames(7, 20)


def test_different_seeds_produce_different_fields():
    assert frames(1, 20) != frames(2, 20)


def test_every_painted_cell_is_on_screen():
    # A cell outside the buffer is a cursor move into someone else's
    # terminal. The alternate screen contains the damage but not the bug.
    for frame in frames(3, MAX_TICKS, width=40, height=12):
        for cell in frame.paint:
            assert 0 <= cell.row < 12
            assert 0 <= cell.col < 40


def test_every_erased_cell_is_on_screen():
    for frame in frames(3, MAX_TICKS, width=40, height=12):
        for row, col in frame.erase:
            assert 0 <= row < 12
            assert 0 <= col < 40


def test_every_glyph_comes_from_the_rain_alphabet():
    alphabet = set(RAIN_ALPHABET)
    for frame in frames(4, MAX_TICKS):
        for cell in frame.paint:
            assert cell.glyph in alphabet


def test_levels_stay_in_range():
    for frame in frames(5, MAX_TICKS):
        for cell in frame.paint:
            assert 0.0 < cell.level <= 1.0


def test_each_column_has_exactly_one_head_and_it_is_the_brightest():
    # The head is what makes it read as the film rather than as falling
    # text. Within one column's cells in one frame, the topmost row must
    # carry the highest level.
    for frame in frames(6, 30):
        by_column: dict[int, list] = {}
        for cell in frame.paint:
            by_column.setdefault(cell.col, []).append(cell)
        for cells in by_column.values():
            head = max(cells, key=lambda c: c.level)
            assert head.row == max(c.row for c in cells)
            assert head.level == 1.0


def test_columns_are_born_staggered_not_all_at_once():
    # Density waves (design S5-4). If every column existed at tick 1 the
    # field would appear as a single slab.
    field = RainField(40, 12, Random(8))
    field.advance()
    early = field.active
    for _ in range(11):
        field.advance()
    assert early < field.active


def test_no_two_cells_ever_collide_in_a_frame():
    # Two columns sharing an x would erase each other's cells, and the
    # erase list carries no identity, so the corruption would be silent.
    # Asserted on the observable output rather than on the column list:
    # a duplicate (row, col) in one frame IS the bug.
    for frame in frames(9, MAX_TICKS):
        positions = [(cell.row, cell.col) for cell in frame.paint]
        assert len(positions) == len(set(positions))


def test_the_field_stops_spawning_and_then_drains():
    # The drain phase IS the dissolve: after spawning ends the screen
    # empties on its own before the player restores the terminal.
    field = RainField(40, 12, Random(10))
    for _ in range(SPAWN_END_TICK):
        field.advance()
    assert field.active > 0
    while not field.is_done():
        field.advance()
    assert field.active == 0


def test_the_field_always_terminates():
    # is_done must go true within MAX_TICKS whatever the seed, or the
    # curtain hangs the terminal it is drawing on.
    for seed in range(20):
        field = RainField(40, 12, Random(seed))
        ticks = 0
        while not field.is_done():
            field.advance()
            ticks += 1
            assert ticks <= MAX_TICKS, f"seed {seed} never finished"


def test_a_frame_is_bounded_by_its_columns_not_by_the_screen():
    # Sparse by construction: work is O(active columns x trail), never
    # O(screen area). A frame bigger than that means something started
    # repainting the whole field.
    field = RainField(80, 24, Random(11))
    for _ in range(MAX_TICKS):
        before = field.active
        frame = field.advance()
        assert len(frame.paint) <= max(before, field.active) * MAX_TRAIL


def test_the_curtain_clears_a_tall_terminal_too():
    # The drain must close on any supported height, not just the 12-row
    # field the other tests use. Column speed scales with height for
    # exactly this reason; a fixed speed would strand a 50-row screen
    # full of rain when MAX_TICKS expired.
    for height in (8, 12, 24, 50):
        field = RainField(80, height, Random(12))
        while not field.is_done():
            field.advance()
        assert field.active == 0, f"height {height} still had columns"
```

In `tests/test_architecture.py`, add to `_ALLOWED`:

```python
    "rain": {"glyphs"},
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_rain.py tests/test_glyphs.py -v`
Expected: `test_rain.py` FAILS with `ModuleNotFoundError: No module named 'matrixlang.rain'`; the two new `test_glyphs.py` tests FAIL on the `RAIN_ALPHABET` import.

- [ ] **Step 3: Add `RAIN_ALPHABET` to `glyphs.py`**

Append to `src/matrixlang/glyphs.py`, after the `REVERSE` line:

```python
# The rain alphabet (Stage 5). The whole half-width katakana block, of
# which the 32 language slots above are a subset: a field built from 32
# repeating characters reads as a pattern, not as rain. Built from
# codepoints rather than literals, so the block stays greppable and this
# file remains the only place a glyph is chosen.
RAIN_ALPHABET: tuple[str, ...] = tuple(chr(code) for code in range(0xFF66, 0xFF9E))
```

- [ ] **Step 4: Write the field**

Create `src/matrixlang/rain.py`:

```python
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
        self._glyphs: dict[int, str] = {}

    def advance(self) -> bool:
        """Move the head. True if it crossed into a new row."""
        self._head += self._speed
        row = int(self._head)
        if row == self._row:
            return False
        # Fill EVERY row crossed, not just the new head: a speed above 1.0
        # skips rows, and a skipped row would have no glyph to draw.
        for crossed in range(self._row + 1, row + 1):
            self._glyphs[crossed] = self._rng.choice(RAIN_ALPHABET)
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
            tail = column.tail_row()
            if 0 <= tail < self.height:
                erase.append((tail, column.col))
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
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_rain.py tests/test_glyphs.py tests/test_architecture.py -v`
Expected: all PASS.

- [ ] **Step 6: Teeth-check the head invariant**

The head is what makes the effect read as the film. Prove the test can see it: in `_Column.cells`, temporarily change the level expression from `1.0 - offset / self._length` to the constant `1.0`. Run
`.venv/bin/python -m pytest tests/test_rain.py::test_each_column_has_exactly_one_head_and_it_is_the_brightest -v`.
Expected: FAIL (every cell ties at 1.0, so `max` no longer picks the top row). Revert.

If it does NOT fail, the test is decorative — fix the test before proceeding.

- [ ] **Step 7: Commit**

```bash
git add src/matrixlang/rain.py src/matrixlang/glyphs.py tests/test_rain.py tests/test_glyphs.py tests/test_architecture.py
git commit -m "feat: the rain field — a deterministic, sparse simulation"
```

---

### Task 3: `curtain.py` — the player

The only impure module in the stage, and the one that can wreck a terminal.

**Files:**
- Create: `src/matrixlang/curtain.py`, `tests/test_curtain.py`
- Modify: `tests/test_architecture.py`

**Interfaces:**
- Consumes: `ansi` (all builders, `ColorMode`, `detect_color_mode`) and `rain` (`RainField`, `Frame`).
- Produces:
  - `FRAME_SECONDS = 1 / 30`, `MIN_WIDTH = 20`, `MIN_HEIGHT = 8`
  - `should_play(mode: ColorMode, size: tuple[int, int]) -> bool`
  - `play(writer: TextIO, size: tuple[int, int], mode: ColorMode, sleep: Callable[[float], None], rng: Random) -> None`
  - `play_if_supported(writer: TextIO, env: Mapping[str, str], size: tuple[int, int], sleep: Callable[[float], None] = time.sleep, rng: Random | None = None) -> bool` — returns whether it played

**Note on `play_if_supported`.** The spec names `should_play` and `play`; this adds the two-line composition of them so `cli.py` imports `curtain` alone and the "should there be rain" policy stays out of the CLI. That keeps the dependency graph exactly as the spec states it.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_curtain.py`:

```python
"""The player. Every impure thing is injected, so these run headless.

Two of these carry teeth-checks, because both guard failures are silent:
a stranded terminal looks fine until you type, and escape bytes in a pipe
look fine until something downstream parses them.
"""

import io
from random import Random

import pytest

from matrixlang import ansi
from matrixlang.ansi import ColorMode
from matrixlang.curtain import play, play_if_supported, should_play


class FakeTty(io.StringIO):
    """A writer that claims to be a terminal."""

    def isatty(self) -> bool:
        return True


def nap(_seconds: float) -> None:
    """An injected sleep that does not sleep. A test that waits is a test
    nobody runs."""


def test_should_play_requires_colour_and_room():
    assert should_play(ColorMode.TRUECOLOR, (80, 24)) is True
    assert should_play(ColorMode.NONE, (80, 24)) is False
    assert should_play(ColorMode.BASIC, (19, 24)) is False
    assert should_play(ColorMode.BASIC, (80, 7)) is False


def test_the_curtain_enters_and_leaves_the_alternate_screen():
    # The alternate screen is what guarantees zero scrollback residue:
    # the program's output is the only thing on the user's real screen.
    writer = FakeTty()
    play(writer, (40, 12), ColorMode.BASIC, nap, Random(1))
    output = writer.getvalue()
    assert output.startswith(ansi.enter_alt_screen())
    assert output.endswith(ansi.leave_alt_screen())
    assert ansi.hide_cursor() in output
    assert ansi.show_cursor() in output


def test_the_curtain_actually_draws_something():
    writer = FakeTty()
    play(writer, (40, 12), ColorMode.TRUECOLOR, nap, Random(2))
    assert "\x1b[38;2;" in writer.getvalue()


def test_the_curtain_terminates():
    # A player that never returns hangs the run it was decorating.
    writer = FakeTty()
    play(writer, (40, 12), ColorMode.BASIC, nap, Random(3))
    assert len(writer.getvalue()) > 0


def test_the_terminal_is_restored_even_when_the_loop_raises():
    # THE guard. A presentation layer that can strand a terminal is worse
    # than no presentation layer, and the failure is invisible until the
    # user's next keystroke does not echo.
    writer = FakeTty()

    def explode(_seconds: float) -> None:
        raise RuntimeError("frame loop exploded")

    with pytest.raises(RuntimeError):
        play(writer, (40, 12), ColorMode.BASIC, explode, Random(4))

    output = writer.getvalue()
    assert ansi.show_cursor() in output
    assert ansi.leave_alt_screen() in output


def test_the_terminal_is_restored_on_keyboard_interrupt():
    writer = FakeTty()

    def interrupt(_seconds: float) -> None:
        raise KeyboardInterrupt

    with pytest.raises(KeyboardInterrupt):
        play(writer, (40, 12), ColorMode.BASIC, interrupt, Random(5))

    assert ansi.leave_alt_screen() in writer.getvalue()


def test_a_non_tty_gets_no_curtain_and_not_one_byte():
    # The debuggability contract, at its source. StringIO.isatty() is
    # False, so detect_color_mode returns NONE however capable TERM looks.
    writer = io.StringIO()
    played = play_if_supported(
        writer, {"TERM": "xterm-256color"}, (80, 24), sleep=nap, rng=Random(6)
    )
    assert played is False
    assert writer.getvalue() == ""


def test_no_color_suppresses_the_curtain_on_a_real_tty():
    writer = FakeTty()
    played = play_if_supported(
        writer, {"TERM": "xterm-256color", "NO_COLOR": "1"}, (80, 24),
        sleep=nap, rng=Random(7),
    )
    assert played is False
    assert writer.getvalue() == ""


def test_a_tiny_terminal_gets_no_curtain():
    writer = FakeTty()
    played = play_if_supported(
        writer, {"TERM": "xterm-256color"}, (10, 4), sleep=nap, rng=Random(8)
    )
    assert played is False
    assert writer.getvalue() == ""


def test_a_capable_tty_does_get_a_curtain():
    writer = FakeTty()
    played = play_if_supported(
        writer, {"TERM": "xterm-256color"}, (40, 12), sleep=nap, rng=Random(9)
    )
    assert played is True
    assert ansi.enter_alt_screen() in writer.getvalue()
```

In `tests/test_architecture.py`, add to `_ALLOWED`:

```python
    "curtain": {"ansi", "rain"},
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_curtain.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'matrixlang.curtain'`.

- [ ] **Step 3: Write the player**

Create `src/matrixlang/curtain.py`:

```python
"""The player: the only part of the rain that touches a terminal.

Everything impure is a parameter — the writer, the clock, the terminal
size, the colour mode, the RNG — so the tests run headless and instantly.

The one non-negotiable is the finally. Whatever happens in the loop, the
cursor comes back and the alternate screen is left: a presentation layer
that can strand a terminal is worse than no presentation layer.
"""

import time
from collections.abc import Callable, Mapping
from random import Random
from typing import TextIO

from matrixlang import ansi
from matrixlang.ansi import ColorMode
from matrixlang.rain import Frame, RainField

FRAME_SECONDS = 1 / 30

# Below this the field has no room to read as rain, so we skip it rather
# than draw three sad columns.
MIN_WIDTH = 20
MIN_HEIGHT = 8


def should_play(mode: ColorMode, size: tuple[int, int]) -> bool:
    """Whether a curtain is appropriate at all.

    No TTY test here: detect_color_mode already collapses non-TTY,
    NO_COLOR and TERM=dumb into NONE, so NONE is the single answer to
    "there should be no rain."
    """
    width, height = size
    return mode is not ColorMode.NONE and width >= MIN_WIDTH and height >= MIN_HEIGHT


def play(
    writer: TextIO,
    size: tuple[int, int],
    mode: ColorMode,
    sleep: Callable[[float], None],
    rng: Random,
) -> None:
    """Run the curtain, restoring the terminal however this exits."""
    width, height = size
    field = RainField(width, height, rng)
    writer.write(ansi.enter_alt_screen() + ansi.hide_cursor() + ansi.clear())
    try:
        while not field.is_done():
            writer.write(_draw(field.advance(), mode))
            writer.flush()
            sleep(FRAME_SECONDS)
    finally:
        # Unconditional. A normal end, an exception and a KeyboardInterrupt
        # all leave the terminal exactly as we found it.
        writer.write(ansi.reset() + ansi.show_cursor() + ansi.leave_alt_screen())
        writer.flush()


def _draw(frame: Frame, mode: ColorMode) -> str:
    """One frame as a single string — one write, no partial repaints."""
    parts: list[str] = []
    for row, col in frame.erase:
        parts.append(ansi.move(row, col) + " ")
    for cell in frame.paint:
        parts.append(
            ansi.move(cell.row, cell.col) + ansi.fg(cell.level, mode) + cell.glyph
        )
    return "".join(parts)


def play_if_supported(
    writer: TextIO,
    env: Mapping[str, str],
    size: tuple[int, int],
    sleep: Callable[[float], None] = time.sleep,
    rng: Random | None = None,
) -> bool:
    """Play a curtain if this terminal supports one. True if it played."""
    mode = ansi.detect_color_mode(env, writer.isatty())
    if not should_play(mode, size):
        return False
    play(writer, size, mode, sleep, rng if rng is not None else Random())
    return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_curtain.py tests/test_architecture.py -v`
Expected: all PASS.

- [ ] **Step 5: Teeth-check both guards**

Two injections, one at a time, each reverted before the next:

1. **Restore.** In `play`, remove the `try`/`finally` so the restore line runs only on the normal path (dedent it to follow the loop). Run
   `.venv/bin/python -m pytest tests/test_curtain.py -v`.
   Expected: `test_the_terminal_is_restored_even_when_the_loop_raises` and
   `test_the_terminal_is_restored_on_keyboard_interrupt` both FAIL. Revert.
2. **Non-TTY.** In `play_if_supported`, replace `if not should_play(mode, size):` with `if False:`. Run the same command.
   Expected: `test_a_non_tty_gets_no_curtain_and_not_one_byte`, `test_no_color_suppresses_the_curtain_on_a_real_tty` and `test_a_tiny_terminal_gets_no_curtain` FAIL. Revert.

If either injection does not fail its tests, the guard is unproven — fix the test before proceeding.

- [ ] **Step 6: Run the full suite, then commit**

Run: `.venv/bin/python -m pytest`
Expected: all PASS.

```bash
git add src/matrixlang/curtain.py tests/test_curtain.py tests/test_architecture.py
git commit -m "feat: the curtain player, with an unconditional terminal restore"
```

---

### Task 4: CLI integration

**Files:**
- Modify: `src/matrixlang/cli.py`, `tests/test_cli.py`, `tests/test_architecture.py`

**Interfaces:**
- Consumes: `play_if_supported` from `matrixlang.curtain`.
- Produces: `matrixlang run FILE [--no-rain]`. `_command_run(path: str, rain: bool = True) -> int`.

**How "the REPL never rains" is enforced.** `_ALLOWED["repl"]` is left untouched, so it does
not list `curtain`. `tests/test_architecture.py::test_module_imports_stay_inside_the_planned_graph`
fails the moment `repl.py` imports the player. R-03 is an import-graph assertion here, not a
comment — do not add `curtain` to the repl entry.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli.py`, and add `from matrixlang import cli` beside the existing `from matrixlang.cli import main`:

```python
def test_run_writes_no_escape_bytes_under_capture(source_file, capsys):
    # THE debuggability contract, end to end. pytest's captured stdout is
    # not a TTY, which is exactly the situation of `run prog.rain > out`.
    exit_code = main(["run", source_file("trace 1\ntrace 2\n")])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "1\n2\n"
    assert "\x1b" not in captured.out
    assert "\x1b" not in captured.err


def test_run_consults_the_curtain_by_default(source_file, capsys, monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(
        cli, "play_if_supported", lambda *args, **kwargs: calls.append(args) or False
    )
    assert main(["run", source_file("trace 1\n")]) == 0
    assert len(calls) == 1


def test_no_rain_skips_the_curtain_entirely(source_file, capsys, monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(
        cli, "play_if_supported", lambda *args, **kwargs: calls.append(args) or False
    )
    assert main(["run", "--no-rain", source_file("trace 1\n")]) == 0
    assert calls == []
    assert capsys.readouterr().out == "1\n"


def test_a_parse_error_costs_no_animation(source_file, capsys, monkeypatch):
    # Rain plays after the parse. A program that cannot run must report
    # that immediately, not after a second and a half of decoration.
    calls: list[tuple] = []
    monkeypatch.setattr(
        cli, "play_if_supported", lambda *args, **kwargs: calls.append(args) or False
    )
    assert main(["run", source_file("construct = 5\n")]) == 1
    assert calls == []


def test_ctrl_c_during_the_curtain_exits_130(source_file, capsys, monkeypatch):
    def interrupt(*_args, **_kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli, "play_if_supported", interrupt)
    assert main(["run", source_file("trace 1\n")]) == 130
    assert capsys.readouterr().out == ""


def test_only_run_takes_the_rain_flag(source_file):
    # R-03: rain in the runner, never the editor. The flag exists on run
    # and nowhere else.
    with pytest.raises(SystemExit) as excinfo:
        main(["render", "--face", "ascii", "--no-rain", source_file("trace 1\n")])
    assert excinfo.value.code == 2
```

In `tests/test_architecture.py`, change the cli entry:

```python
    "cli": {
        "curtain", "errors", "interpreter", "lexer", "parser", "render",
        "repl", "treeview",
    },
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: the curtain tests FAIL (`cli` has no attribute `play_if_supported`), and `--no-rain` FAILS as an unrecognized argument.

- [ ] **Step 3: Wire the CLI**

In `src/matrixlang/cli.py`:

1. Add to the imports:

```python
import os
import shutil

from matrixlang.curtain import play_if_supported
```

2. Give `run` its flag, directly after `run_parser.add_argument("path", ...)`:

```python
    run_parser.add_argument(
        "--no-rain",
        action="store_true",
        help="Skip the digital rain and execute immediately.",
    )
```

3. Change the `run` dispatch line:

```python
    if args.command == "run":
        return _command_run(args.path, rain=not args.no_rain)
```

4. Replace `_command_run` with:

```python
def _command_run(path: str, rain: bool = True) -> int:
    source = _read_source(path)
    if source is None:
        return 2

    try:
        with recursion_guard():
            tree = parse(lex(source))
    except MatrixLangError as error:
        print(f"matrixlang: {error}", file=sys.stderr)
        return 1

    # After the parse, before execution: a program that cannot run should
    # say so immediately rather than after a second of decoration. The
    # curtain declines itself on a non-TTY, so redirected output is clean
    # without this call site knowing anything about terminals.
    if rain:
        try:
            play_if_supported(sys.stdout, os.environ, shutil.get_terminal_size())
        except KeyboardInterrupt:
            # play() has already restored the terminal in its finally.
            return 130

    # Execution is deliberately outside the parse try-block: a program that
    # fails partway has already printed real output, and that output stays.
    try:
        run_program(tree)
    except MatrixLangError as error:
        print(f"matrixlang: {error}", file=sys.stderr)
        return 1
    return 0
```

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: all PASS, including every pre-existing `run` test unchanged — those tests are themselves the regression guard that output is untouched.

- [ ] **Step 5: See it for real**

The tests are all headless, so look at it once with your own eyes:

```bash
.venv/bin/matrixlang run examples/hello.rain
```

Expected: about 1.7 seconds of green rain on a cleared screen, then the screen restores and the program's output appears on your normal prompt with no leftover rain in the scrollback. Then confirm the contract:

```bash
.venv/bin/matrixlang run examples/hello.rain | cat
```

Expected: output only, instantly, no escape sequences. Report both results.

- [ ] **Step 6: Commit**

```bash
git add src/matrixlang/cli.py tests/test_cli.py tests/test_architecture.py
git commit -m "feat(cli): run plays the rain curtain; --no-rain opts out"
```

---

### Task 5: Attribution, README and v0.5.0

**Files:**
- Modify: `README.md`, `pyproject.toml`, `src/matrixlang/__init__.py`

**Interfaces:** none — documentation and metadata only. Do not change any file under `src/matrixlang/` other than the `__init__.py` version string.

- [ ] **Step 1: Bump the version**

In `pyproject.toml` line 3 and `src/matrixlang/__init__.py` line 3, change `0.4.0` to `0.5.0`.

- [ ] **Step 2: Update the README status line**

Replace `Stage 4 — bidirectional glyph rendering. One tree, two faces.` with:

```markdown
Stage 5 — runner presentation. The language runs, and it rains.
```

- [ ] **Step 3: Document the runner**

Replace this paragraph:

```markdown
`run` executes a program. `repl` starts an interactive session — blocks span
multiple lines, so a `dejavu` loop can be typed at the prompt.
```

with:

````markdown
`run` executes a program, preceded by a curtain of digital rain. `repl`
starts an interactive session — blocks span multiple lines, so a `dejavu`
loop can be typed at the prompt. The REPL never rains: motion and
legibility are adversaries, so the rain belongs to the runner and not to
the editing surface.

The curtain draws on the alternate screen buffer, so it leaves nothing in
your scrollback, and it declines itself whenever it would be unwelcome —
a redirected or piped stdout, `NO_COLOR`, `TERM=dumb`, or a terminal too
small to read. `matrixlang run prog.rain > out.txt` writes exactly the
bytes it always did:

```bash
.venv/bin/matrixlang run --no-rain examples/hello.rain
```

`--no-rain` skips it while you are iterating.
````

- [ ] **Step 4: Add the attribution section**

Insert a new section immediately before `## Development`:

```markdown
## The glyphs

The falling characters are Unicode half-width katakana (U+FF66–FF9D), not
the film's own glyphs.

The real ones were reverse-engineered by
[Rezmason/matrix](https://github.com/Rezmason/matrix) from an archived
promotional asset: mirrored katakana scanned out of a Japanese cookbook,
plus characters from Susan Kare's Chicago typeface and the expanded set
from *Resurrections*. That work is the reference for what the film's code
actually looks like, and this project is indebted to it.

It is not, however, a font. The glyphs live as WebGL vector and texture
data, so putting them in a terminal would mean building a typeface —
a separate project, not a stage of this one. Half-width katakana render
today in any terminal with zero font work, and the mapping table is
deliberately swappable if that ever changes.

Terminal digital rain is solved work with many good implementations
(TMatrix, green_rain, RGB-digital-rain). Nothing here tries to improve on
them; the rain exists because this language earned a presentation layer,
and it is the last thing built rather than the first.
```

- [ ] **Step 5: Run the full suite and check the README renders**

Run: `.venv/bin/python -m pytest`
Expected: all PASS. Report the final count.

Re-read your README edits and confirm the fences nest correctly — Step 3's block is wrapped in an outer ```` ```` ```` fence purely so its inner ```` ``` ```` bash block displays in this plan. **Do not copy the outer fence into the README**; insert only its contents.

- [ ] **Step 6: Commit**

```bash
git add README.md pyproject.toml src/matrixlang/__init__.py
git commit -m "chore: v0.5.0 — Stage 5, the rain runner"
```
