# MatrixLang

The code shown in *The Matrix* is not a programming language. It has no grammar, no
semantics, and no execution model. Nothing in the film runs.

This project is not "recreate the Matrix language." There is nothing to recreate. It is:

> **Invent the language the film pretended to have.**

A real, executable, Turing-complete language whose source can be written and read in
Matrix-style glyphs, with a working interpreter, a REPL, and a test suite.

Source files use the `.rain` extension.

## Status

Stage 1 — lexer. See `docs/superpowers/specs/` for the specification and
`docs/superpowers/plans/` for the implementation plan.

## Development

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m pytest
```
