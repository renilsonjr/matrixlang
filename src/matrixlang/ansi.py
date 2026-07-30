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
        # SGR 1 (bold) is set-only; nothing about SGR 32 (green) clears it.
        # _draw concatenates these as absolute per-cell states, so once any
        # head is drawn every later trail cell would render bold too unless
        # the trail explicitly emits SGR 22, "normal intensity" — the only
        # code that turns bold back off.
        return f"{CSI}1;32m" if level >= _HEAD_LEVEL else f"{CSI}22;32m"
    if mode is ColorMode.COLOR256:
        if level >= _HEAD_LEVEL:
            return f"{CSI}38;5;231m"
        index = min(int(level * len(_C256_RAMP)), len(_C256_RAMP) - 1)
        return f"{CSI}38;5;{_C256_RAMP[index]}m"
    if level >= _HEAD_LEVEL:
        return f"{CSI}38;2;215;255;215m"
    return f"{CSI}38;2;{int(20 * level)};{int(60 + 195 * level)};{int(40 * level)}m"
