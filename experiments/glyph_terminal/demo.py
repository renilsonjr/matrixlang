"""Does a glyph-only terminal work? Run this and judge for yourself.

EXPERIMENT for issue #22. Renders the same session three ways so the
question can be answered by looking rather than by arguing:

  1. plain            what the toolchain does today
  2. operator view    source in glyphs, output and errors plain (today's
                      REPL `:glyph` mode)
  3. full glyph       everything transliterated, including diagnostics --
                      the mode the issue proposes

Usage:  python experiments/glyph_terminal/demo.py
"""

import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from matrixlang.errors import MatrixLangError  # noqa: E402
from matrixlang.interpreter import Interpreter  # noqa: E402
from matrixlang.lexer import lex  # noqa: E402
from matrixlang.parser import parse  # noqa: E402
from matrixlang.render import render_glyph  # noqa: E402

from matrixlang.translit import transliterate  # noqa: E402

WORKING = """\
construct name = "Neo"
construct n = 0
dejavu n < 3
  trace "wake up, " + name
  n = n + 1
flatline
"""

# The case that decides the design. A typo in a name -- the single most
# common error anyone makes -- and the question is whether you can still
# fix it when the diagnostic is rendered in the glyph alphabet.
BROKEN = """\
construct name = "Neo"
trace "wake up, " + nme
"""


def run(source: str) -> tuple[str, str]:
    """Execute a program, returning (stdout, diagnostic)."""
    out = io.StringIO()
    try:
        Interpreter(out=out).run(parse(lex(source)))
    except MatrixLangError as error:
        return out.getvalue(), f"matrixlang: {error}"
    return out.getvalue(), ""


def show(label: str, source: str, glyph_source: bool, glyph_text: bool) -> None:
    face = render_glyph(parse(lex(source))) if glyph_source else source
    stdout, diagnostic = run(source)
    if glyph_text:
        stdout = transliterate(stdout)
        diagnostic = transliterate(diagnostic)

    print(f"\n{'─' * 68}\n{label}\n{'─' * 68}")
    print("source:")
    for line in face.rstrip("\n").split("\n"):
        print(f"  {line}")
    if stdout:
        print("output:")
        for line in stdout.rstrip("\n").split("\n"):
            print(f"  {line}")
    if diagnostic:
        print("error:")
        print(f"  {diagnostic}")


def main() -> None:
    for title, source in (("A WORKING PROGRAM", WORKING), ("A TYPO", BROKEN)):
        print(f"\n\n╔{'═' * 66}╗")
        print(f"║ {title:<64} ║")
        print(f"╚{'═' * 66}╝")
        show("1. plain — the toolchain today", source, False, False)
        show("2. operator view — source in glyphs, diagnostics plain (today's REPL)",
             source, True, False)
        show("3. full glyph — everything transliterated (what #22 proposes)",
             source, True, True)


if __name__ == "__main__":
    main()
