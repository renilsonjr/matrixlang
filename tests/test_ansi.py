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
