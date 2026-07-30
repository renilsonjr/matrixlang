# MatrixLang

The code shown in *The Matrix* is not a programming language. It has no grammar, no
semantics, and no execution model. Nothing in the film runs.

This project is not "recreate the Matrix language." There is nothing to recreate. It is:

> **Invent the language the film pretended to have.**

A real, executable, Turing-complete language whose source can be written and read in
Matrix-style glyphs, with a working interpreter, a REPL, and a test suite.

Source files use the `.rain` extension.

## Status

Stage 5 — runner presentation. The language runs, and it rains.

## Usage

```bash
.venv/bin/matrixlang lex examples/hello.rain
```

Prints one `line:column<TAB>TOKEN_TYPE<TAB>lexeme` row per token.
`render --face glyph` prints the same
program in half-width katakana; `render --face ascii` converts it back
(and doubles as a formatter — whitespace normalizes to canonical form).

```bash
.venv/bin/matrixlang render --face glyph examples/hello.rain
```

In the REPL, `:glyph` echoes each statement in the operator view as you
type ASCII; `:ascii` turns it back off. Glyph and mixed-face source are
accepted everywhere with no mode flag — glyphs and ASCII identifiers
occupy disjoint alphabets, so one lexer reads both.

```bash
.venv/bin/matrixlang parse examples/hello.rain
```

Prints the syntax tree as indented text — the tree's shape is the precedence lesson.

```bash
.venv/bin/matrixlang run examples/hello.rain
.venv/bin/matrixlang repl
```

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

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
```

If `import matrixlang` fails with `ModuleNotFoundError` after setup, run
`chflags -R nohidden .venv` — some macOS systems intermittently set a hidden
flag on venv files, which Python ≥3.14 silently skips when processing `.pth`
files.
