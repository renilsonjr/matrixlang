"""The cascade IS the program: watch software execute as falling glyphs.

EXPERIMENT for issue #22. Not part of the shipped package.

The Stage 5 curtain is decoration -- random glyphs, no connection to your
code, played before execution. This is the opposite: every falling column
carries real content from the program, so what you are watching IS the
software rather than an animation behind it.

Two kinds of column, distinguished by colour:

  SOURCE  a line of the program in its glyph face          (green)
  OUTPUT  a value the program actually produced, transliterated  (white)

Output columns are brighter and fall slower, so results surface out of the
source rather than being lost in it. That is the readout of state from the
parent spec section 1.1 -- Cypher watching the Matrix and seeing what it
means, not what it says.

    python experiments/glyph_terminal/live.py                 animate
    python experiments/glyph_terminal/live.py --frames 3      dump frames as
                                                              text, no ANSI

The --frames mode exists so the content can be verified without a terminal:
it prints the composed grid as plain characters, which is checkable in a
pipe or a test.
"""

import argparse
import io
import os
import random
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from matrixlang import ansi  # noqa: E402
from matrixlang.ansi import ColorMode  # noqa: E402
from matrixlang.errors import MatrixLangError  # noqa: E402
from matrixlang.interpreter import Interpreter  # noqa: E402
from matrixlang.lexer import lex  # noqa: E402
from matrixlang.parser import parse  # noqa: E402
from matrixlang.render import render_glyph  # noqa: E402

from translit import transliterate  # noqa: E402

FRAME_SECONDS = 1 / 24
SOURCE = "source"
OUTPUT = "output"

PROGRAM = """\
construct name = "Neo"
construct n = 0
dejavu n < 4
  redpill n == 2
    trace "wake up, " + name
  bluepill
    trace n
  flatline
  n = n + 1
flatline
"""


def content_of(source: str) -> list[tuple[str, str]]:
    """The program's own material: its glyph source, and what it produced.

    Returns (kind, text) pairs. This is the whole idea in one function --
    the cascade draws from here instead of from a random alphabet.
    """
    tree = parse(lex(source))
    items = [(SOURCE, line) for line in render_glyph(tree).splitlines() if line.strip()]

    buffer = io.StringIO()
    try:
        Interpreter(out=buffer).run(tree)
    except MatrixLangError as error:
        # Diagnostics stay plain. The static spike showed why: transliterated,
        # they are unreadable AND unmatchable against ASCII identifiers in the
        # source. They are not cascade material.
        print(f"matrixlang: {error}", file=sys.stderr)

    items += [(OUTPUT, transliterate(line)) for line in buffer.getvalue().splitlines()]
    return items


class Column:
    """One falling stream carrying one real line of the program."""

    def __init__(self, col: int, kind: str, text: str, speed: float) -> None:
        self.col = col
        self.kind = kind
        self.text = text
        self._speed = speed
        self._head = 0.0

    def advance(self) -> None:
        self._head += self._speed

    def cells(self, height: int) -> list[tuple[int, int, str, float]]:
        """(row, col, char, brightness) for the visible part of this column.

        The line is laid out so it reads TOP-TO-BOTTOM in its natural order:
        text[0] sits at the top of the trail and the last character rides the
        head. The obvious implementation -- text[0] at the head -- renders
        every line backwards, which is fatal here in a way it never was for
        the decorative rain: nobody reads random glyphs, but the whole point
        of this mode is that the falling columns ARE the program.
        """
        head = int(self._head)
        last = len(self.text) - 1
        out = []
        for offset, char in enumerate(self.text):
            row = head - (last - offset)
            if 0 <= row < height and char != " ":
                # Brightness rises toward the head; output columns keep a
                # higher floor so results stay readable against the source.
                floor = 0.55 if self.kind is OUTPUT else 0.0
                level = max(floor, 1.0 - (last - offset) / max(len(self.text), 1))
                out.append((row, self.col, char, level))
        return out

    def finished(self, height: int) -> bool:
        return int(self._head) - len(self.text) >= height


class LiveField:
    def __init__(self, width: int, height: int, items, rng: random.Random) -> None:
        self.width = width
        self.height = height
        self._items = items
        self._rng = rng
        self._columns: list[Column] = []
        self._free = [c for c in range(width) if c % 3 == 0]
        rng.shuffle(self._free)
        self._queue = list(items)
        rng.shuffle(self._queue)

    def advance(self) -> list[tuple[int, int, str, float]]:
        self._spawn()
        for column in self._columns:
            column.advance()
        cells = [cell for column in self._columns for cell in column.cells(self.height)]
        # A finished column releases its x back to the pool. Returning it any
        # earlier would let two streams share a column and overwrite each
        # other -- the same defect the Stage 5 review found in the real rain,
        # where it was invisible because random glyphs all look alike. Here it
        # would silently corrupt a line of the program.
        alive = []
        for column in self._columns:
            if column.finished(self.height):
                self._free.append(column.col)
            else:
                alive.append(column)
        self._columns = alive
        return cells

    def _spawn(self) -> None:
        if not self._free or self._rng.random() > 0.55:
            return
        if not self._queue:                       # cycle the program forever
            self._queue = list(self._items)
            self._rng.shuffle(self._queue)
        kind, text = self._queue.pop()
        # Output falls slower so it lingers and reads.
        speed = (
            self._rng.uniform(0.4, 0.7) if kind is OUTPUT
            else self._rng.uniform(0.7, 1.4)
        )
        self._columns.append(Column(self._free.pop(0), kind, text, speed))


def paint(cells, mode: ColorMode) -> str:
    parts = []
    for row, col, char, level in cells:
        parts.append(ansi.move(row, col) + ansi.fg(level, mode) + char)
    return "".join(parts)


def animate(items, seconds: float) -> None:
    width, height = shutil.get_terminal_size()
    mode = ansi.detect_color_mode(os.environ, sys.stdout.isatty())
    if mode is ColorMode.NONE:
        print("Not a TTY (or NO_COLOR/TERM=dumb). Try --frames 3 instead.")
        return
    field = LiveField(width, height, items, random.Random())
    sys.stdout.write(ansi.enter_alt_screen() + ansi.hide_cursor() + ansi.clear())
    deadline = time.monotonic() + seconds
    try:
        while time.monotonic() < deadline:
            sys.stdout.write(ansi.clear() + paint(field.advance(), mode))
            sys.stdout.flush()
            time.sleep(FRAME_SECONDS)
    except KeyboardInterrupt:
        pass
    finally:
        sys.stdout.write(ansi.reset() + ansi.show_cursor() + ansi.leave_alt_screen())
        sys.stdout.flush()


def dump(items, frames: int) -> None:
    """Compose frames as plain text so the content is checkable in a pipe."""
    width, height = 72, 14
    field = LiveField(width, height, items, random.Random(7))
    for number in range(1, frames + 1):
        grid = [[" "] * width for _ in range(height)]
        for row, col, char, _level in field.advance():
            grid[row][col] = char
        print(f"\n--- frame {number} " + "-" * (width - 14))
        for line in grid:
            print("".join(line).rstrip())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--frames", type=int, help="dump N frames as text and exit")
    ap.add_argument("--seconds", type=float, default=8.0, help="how long to animate")
    args = ap.parse_args()

    items = content_of(PROGRAM)
    print(f"{len(items)} lines of program material "
          f"({sum(1 for k, _ in items if k is OUTPUT)} of them output)",
          file=sys.stderr)

    if args.frames:
        dump(items, args.frames)
    else:
        animate(items, args.seconds)


if __name__ == "__main__":
    main()
