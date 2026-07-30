"""The player. Every impure thing is injected, so these run headless.

Two of these carry teeth-checks, because both guard failures are silent:
a stranded terminal looks fine until you type, and escape bytes in a pipe
look fine until something downstream parses them.
"""

import io
import re
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
    # reset() leads, so a bold/coloured SGR state left by the shell can't
    # bleed into the field (minor fix 8).
    assert output.startswith(ansi.reset() + ansi.enter_alt_screen())
    assert output.endswith(ansi.leave_alt_screen())
    assert ansi.hide_cursor() in output
    assert ansi.show_cursor() in output


def test_the_curtain_actually_draws_something():
    writer = FakeTty()
    play(writer, (40, 12), ColorMode.TRUECOLOR, nap, Random(2))
    assert "\x1b[38;2;" in writer.getvalue()


def test_the_curtain_terminates():
    # A player that never returns hangs the run it was decorating. Guards
    # that the loop actually drew frames, not just that the unconditional
    # enter_alt_screen write produced output — deleting the entire frame
    # loop would still satisfy `len(output) > 0`. A cursor-move escape
    # (ansi.move) is written only from inside the loop's _draw call, so
    # its presence is evidence the loop ran.
    writer = FakeTty()
    play(writer, (40, 12), ColorMode.BASIC, nap, Random(3))
    output = writer.getvalue()
    assert re.search(r"\x1b\[\d+;\d+H", output), "no cursor-move escape: loop never drew"


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


def test_a_failing_restore_does_not_mask_the_original_error():
    # If the writer breaks mid-loop (a broken pipe, an unencodable glyph)
    # and the finally's own restore write breaks for the same reason, the
    # restore's exception must not replace the original — that would leave
    # the terminal on the alternate screen with a hidden cursor AND report
    # the wrong error.
    class BrokenWriter(FakeTty):
        def write(self, text: str) -> int:
            if ansi.leave_alt_screen() in text or "\x1b[38" in text or "\x1b[3" in text:
                raise OSError("terminal went away")
            return super().write(text)

    with pytest.raises(OSError, match="terminal went away"):
        play(BrokenWriter(), (40, 12), ColorMode.BASIC, nap, Random(1))


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
