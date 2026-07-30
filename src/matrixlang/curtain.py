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
    # reset() first: a bold or coloured SGR state left by the shell must
    # not bleed into the field (pairs with the BASIC-mode fix above).
    writer.write(
        ansi.reset() + ansi.enter_alt_screen() + ansi.hide_cursor() + ansi.clear()
    )
    try:
        while not field.is_done():
            writer.write(_draw(field.advance(), mode))
            writer.flush()
            sleep(FRAME_SECONDS)
    finally:
        # Unconditional. A normal end, an exception and a KeyboardInterrupt
        # all leave the terminal exactly as we found it.
        try:
            writer.write(ansi.reset() + ansi.show_cursor() + ansi.leave_alt_screen())
            writer.flush()
        except Exception:
            # A restore that fails for the same reason the loop failed
            # (broken pipe, EIO) must not replace the original exception
            # with a more confusing one.
            pass


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
