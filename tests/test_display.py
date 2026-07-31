"""C2 — the display protocol and which backend gets chosen.

Backend selection is a pure function of the environment, exactly as
`ansi.detect_color_mode` is, so it is table-testable without a terminal
or a window.

The binding property is the first table row: **when stdout is not a TTY
there is no window and the bytes are unchanged.** That is what keeps
`matrixlang run prog.rain > out.txt` honest and what lets CI assert on a
program's output at all.
"""

import io

import pytest

from matrixlang.display import Backend, TextDisplay, choose_backend
from matrixlang.events import Error, Output, Statement

# --- Selection ----------------------------------------------------------


def choose(**overrides):
    defaults = dict(isatty=True, env={"TERM": "xterm-256color"}, want_window=True, tk_available=True)
    return choose_backend(**{**defaults, **overrides})


def test_a_tty_with_tk_available_gets_a_window():
    assert choose() is Backend.WINDOW


def test_a_redirected_stdout_gets_text_and_no_window():
    # The property everything else defers to.
    assert choose(isatty=False) is Backend.TEXT


def test_no_window_flag_gets_text():
    assert choose(want_window=False) is Backend.TEXT


def test_no_color_gets_text():
    # Presence, not truthiness — NO_COLOR="" still means no.
    assert choose(env={"TERM": "xterm-256color", "NO_COLOR": ""}) is Backend.TEXT


def test_tk_unavailable_gets_text():
    assert choose(tk_available=False) is Backend.TEXT


@pytest.mark.parametrize(
    "isatty,want_window,tk_available,expected",
    [
        (True, True, True, Backend.WINDOW),
        (True, True, False, Backend.TEXT),
        (True, False, True, Backend.TEXT),
        (False, True, True, Backend.TEXT),
        (False, False, False, Backend.TEXT),
    ],
)
def test_selection_table(isatty, want_window, tk_available, expected):
    assert (
        choose(isatty=isatty, want_window=want_window, tk_available=tk_available)
        is expected
    )


def test_a_dumb_terminal_still_gets_a_window():
    # TERM describes a terminal's capabilities. A window is not a terminal,
    # so TERM must not veto it — unlike the curtain, which lived in the
    # terminal and was right to care.
    assert choose(env={"TERM": "dumb"}) is Backend.WINDOW


# --- TextDisplay --------------------------------------------------------


def test_the_text_display_prints_output_events():
    buffer = io.StringIO()
    display = TextDisplay(buffer)
    display.open()
    display.emit(Output(text="wake up, Neo", line=1))
    display.close()
    assert buffer.getvalue() == "wake up, Neo\n"


def test_the_text_display_ignores_statement_events():
    buffer = io.StringIO()
    display = TextDisplay(buffer)
    display.emit(Statement(node=None, line=1))
    assert buffer.getvalue() == ""


def test_the_text_display_keeps_errors_off_stdout():
    buffer = io.StringIO()
    display = TextDisplay(buffer)
    display.emit(Error(message="boom"))
    assert buffer.getvalue() == ""


def test_open_and_close_are_safe_to_call_on_the_text_display():
    # The CLI calls them unconditionally; a backend that cannot take that
    # would push the conditional back up into the caller.
    display = TextDisplay(io.StringIO())
    display.open()
    display.close()
    display.close()
