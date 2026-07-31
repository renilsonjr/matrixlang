"""An interactive MatrixLang terminal where the cascade IS the session.

EXPERIMENT for issue #22. Not part of the shipped package.

Type MatrixLang at the prompt. Every statement you enter and every value it
produces joins the falling cascade, in glyphs. The screen is not a log with
an animation behind it -- the animation is the session.

    ┌────────────────────────────────────┐
    │                                    │
    │   cascade: your statements and     │  glyphs, falling
    │   their output, falling as glyphs  │
    │                                    │
    ├────────────────────────────────────┤
    │ status: errors, in plain text      │  never transliterated
    │ > construct x = 5                  │  what you are typing, in ASCII
    └────────────────────────────────────┘

Two things deliberately stay readable, and the reasons are different:

  THE INPUT LINE is ASCII because you cannot touch-type an alphabet you are
  still learning. This is not a compromise -- it is D-03's authoring view.

  DIAGNOSTICS are plain because the static spike proved transliterated ones
  are unusable: you cannot fix a typo when the line number, the misspelled
  name and the suggested remedy are all glyphs.

Everything else -- your statements, your results -- is glyph-only and, by
construction, decodable: translit.untransliterate() recovers the text
exactly, so a person or a model holding the table can read the screen.

    python experiments/glyph_terminal/shell.py
    python experiments/glyph_terminal/shell.py --table       print the dictionary
    python experiments/glyph_terminal/shell.py --script '...'  headless, dumps frames
"""

import argparse
import io
import os
import random
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from matrixlang import ansi  # noqa: E402
from matrixlang.ansi import ColorMode  # noqa: E402
from matrixlang.repl import Repl  # noqa: E402

from live import OUTPUT, SOURCE, FRAME_SECONDS, LiveField, paint  # noqa: E402
from matrixlang.translit import table_for_readers, transliterate, untransliterate  # noqa: E402

PROMPT = "> "
CONTINUATION = "... "
_ERROR_PREFIX = "matrixlang:"


class Session:
    """A MatrixLang REPL whose results become cascade material.

    Wraps the shipped Repl rather than reimplementing block buffering, so
    multi-line `dejavu` and `redpill` blocks behave exactly as they do in
    `matrixlang repl`.
    """

    def __init__(self) -> None:
        self._buffer = io.StringIO()
        self._repl = Repl(out=self._buffer)
        self._read = 0
        self._pending: list[str] = []
        self.needs_more = False

    def feed(self, line: str) -> tuple[list[tuple[str, str]], str]:
        """Run one line. Returns (cascade items, plain diagnostic)."""
        self._pending.append(line)
        self.needs_more = self._repl.feed(line)

        produced = self._buffer.getvalue()[self._read:]
        self._read = len(self._buffer.getvalue())

        items: list[tuple[str, str]] = []
        diagnostic = ""
        for out_line in produced.splitlines():
            if out_line.startswith(_ERROR_PREFIX):
                diagnostic = out_line          # stays plain, never cascades
            else:
                items.append((OUTPUT, transliterate(out_line)))

        if self.needs_more:
            return items, diagnostic           # block still open, nothing to show

        # The statement joins the cascade in the LANGUAGE's glyph face, not the
        # display dictionary -- it is code, so it uses the code face.
        #
        # Rendered as a whole block, not line by line: an individual line of a
        # `dejavu` body is not a parseable program, so rendering per line drops
        # the body entirely and spills `flatline` out as raw ASCII.
        block, self._pending = "\n".join(self._pending), []
        if block.strip() and not diagnostic:
            for rendered in _glyph_source_lines(block):
                items.insert(0, (SOURCE, rendered))
        return items, diagnostic


def _glyph_source_lines(block: str) -> list[str]:
    """A complete statement or block in the language's glyph face.

    Falls back to the raw text if it will not parse -- the cascade should
    show something rather than nothing when input is malformed.
    """
    from matrixlang.errors import MatrixLangError
    from matrixlang.lexer import lex
    from matrixlang.parser import parse
    from matrixlang.render import render_glyph

    try:
        rendered = render_glyph(parse(lex(block + "\n")))
    except MatrixLangError:
        return [line for line in block.splitlines() if line.strip()]
    return [line.strip() for line in rendered.splitlines() if line.strip()]


class Screen:
    """Composes one frame: cascade above, status and prompt pinned below."""

    def __init__(self, width: int, height: int, rng: random.Random) -> None:
        self.width = width
        self.height = height
        self.cascade_rows = max(1, height - 2)
        self.field = LiveField(width, self.cascade_rows, [], rng)
        self.status = ""

    def add(self, items) -> None:
        self.field._items.extend(items)
        self.field._queue.extend(items)

    def frame(self, mode: ColorMode, prompt: str, typed: str) -> str:
        parts = [ansi.clear(), paint(self.field.advance(), mode)]

        parts.append(ansi.move(self.height - 2, 0) + ansi.reset())
        if self.status:
            parts.append(self.status[: self.width - 1])

        parts.append(ansi.move(self.height - 1, 0) + ansi.reset())
        parts.append((prompt + typed)[: self.width - 1])
        return "".join(parts)


_LOAD = ":load"


def _run_line(screen: Screen, session: Session, line: str) -> None:
    if line.strip().startswith(_LOAD):
        _load_file(screen, session, line.strip()[len(_LOAD):].strip())
        return
    items, diagnostic = session.feed(line)
    screen.add(items)
    screen.status = diagnostic


def _load_file(screen: Screen, session: Session, path: str) -> None:
    """`:load FILE` — pull a .rain file into the session and cascade it.

    Fed line by line through the same Session as typed input, so a file
    behaves exactly as if you had typed it: blocks buffer, state persists,
    and diagnostics land in the status line rather than the cascade.
    """
    if not path:
        screen.status = f"usage: {_LOAD} path/to/file.rain"
        return
    try:
        source = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        screen.status = f"matrixlang: {error}"
        return

    loaded = 0
    for line in source.splitlines():
        items, diagnostic = session.feed(line)
        screen.add(items)
        loaded += len(items)
        if diagnostic:                     # stop at the first failure
            screen.status = diagnostic
            return
    screen.status = f"loaded {path} — {loaded} items cascading"


def interactive(seconds: float | None) -> int:
    """Raw-mode loop: animate continuously, read keys without blocking."""
    import select
    import termios
    import tty

    if not sys.stdin.isatty() or not sys.stdout.isatty():
        print("shell.py needs a terminal. Try --script for a headless run.")
        return 2

    mode = ansi.detect_color_mode(os.environ, True)
    if mode is ColorMode.NONE:
        print("No colour available (NO_COLOR / TERM=dumb).")
        return 2

    width, height = shutil.get_terminal_size()
    screen = Screen(width, height, random.Random())
    session = Session()
    typed = ""

    fd = sys.stdin.fileno()
    saved = termios.tcgetattr(fd)
    sys.stdout.write(ansi.enter_alt_screen() + ansi.hide_cursor())
    try:
        tty.setraw(fd)
        while True:
            prompt = CONTINUATION if session.needs_more else PROMPT
            sys.stdout.write(screen.frame(mode, prompt, typed))
            sys.stdout.flush()

            ready, _, _ = select.select([sys.stdin], [], [], FRAME_SECONDS)
            if not ready:
                continue
            key = sys.stdin.read(1)

            if key in ("\x03", "\x04"):            # Ctrl-C, Ctrl-D
                return 0
            if key in ("\r", "\n"):
                _run_line(screen, session, typed)
                typed = ""
            elif key in ("\x7f", "\b"):
                typed = typed[:-1]
            elif key.isprintable():
                typed += key
    finally:
        # Unconditional, exactly as curtain.play does it. A presentation
        # layer that can strand a terminal is worse than none.
        termios.tcsetattr(fd, termios.TCSADRAIN, saved)
        sys.stdout.write(ansi.reset() + ansi.show_cursor() + ansi.leave_alt_screen())
        sys.stdout.flush()


def scripted(lines: list[str], frames: int) -> int:
    """Headless: feed lines, then dump frames as plain text.

    Exists so the session logic is verifiable without a terminal -- the
    animation cannot be asserted on, but the content can.
    """
    width, height = 74, 16
    screen = Screen(width, height, random.Random(11))
    session = Session()

    # Animate the EMPTY field first. shell.py spends its whole startup here,
    # before a single statement is entered, and an earlier version crashed on
    # exactly this: every scripted run fed lines before drawing a frame, so
    # the state the real terminal opens in was never once exercised.
    for _ in range(40):
        screen.field.advance()
    print("empty-field warmup: 40 frames, no crash\n")

    for line in lines:
        _run_line(screen, session, line)
        state = "needs more input" if session.needs_more else "ran"
        print(f"$ {line}\n    -> {state}"
              + (f" | {screen.status}" if screen.status else ""))

    print(f"\ncascade now carries {len(screen.field._items)} items:")
    for kind, text in screen.field._items:
        decoded = untransliterate(text) if kind is OUTPUT else ""
        print(f"  {kind:6} {text}" + (f"   (decodes to {decoded!r})" if decoded else ""))

    for number in range(1, frames + 1):
        grid = [[" "] * width for _ in range(screen.cascade_rows)]
        for row, col, char, _ in screen.field.advance():
            grid[row][col] = char
        print(f"\n--- frame {number} " + "-" * (width - 14))
        for row in grid:
            print("".join(row).rstrip())
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--table", action="store_true", help="print the glyph dictionary")
    ap.add_argument("--script", help="semicolon-separated lines, headless")
    ap.add_argument("--frames", type=int, default=3, help="frames to dump in --script")
    args = ap.parse_args()

    if args.table:
        print("MatrixLang display dictionary (reversible)\n")
        print(table_for_readers())
        return 0
    if args.script:
        return scripted(args.script.split(";"), args.frames)
    return interactive(None)


if __name__ == "__main__":
    raise SystemExit(main())
