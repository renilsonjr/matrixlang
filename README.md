# MatrixLang

The code shown in *The Matrix* is not a programming language. It has no grammar, no
semantics, and no execution model. Nothing in the film runs.

This project is not "recreate the Matrix language." There is nothing to recreate. It is:

> **Invent the language the film pretended to have.**

A real, executable, Turing-complete language whose source can be written and read in
Matrix-style glyphs, with a working interpreter, a REPL, and a test suite.

Source files use the `.rain` extension.

## Status

Stage 3 — interpreter. The language runs.

## Usage

```bash
.venv/bin/matrixlang lex examples/hello.rain
```

Prints one `line:column<TAB>TOKEN_TYPE<TAB>lexeme` row per token. `render` is
reserved for Stage 4 and currently exits 2.

```bash
.venv/bin/matrixlang parse examples/hello.rain
```

Prints the syntax tree as indented text — the tree's shape is the precedence lesson.

```bash
.venv/bin/matrixlang run examples/hello.rain
.venv/bin/matrixlang repl
```

`run` executes a program. `repl` starts an interactive session — blocks span
multiple lines, so a `dejavu` loop can be typed at the prompt.

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
