# Stage 1 — Lexer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn MatrixLang source text into a token stream, test-first, behind a CLI skeleton that later stages can grow into.

**Architecture:** A single-pass character scanner over the source string, emitting a flat `list[Token]`. Token type definitions live apart from the scanner so the Stage 2 parser can import them without importing the lexer. Errors are a shared exception hierarchy carrying line and column, so the parser and interpreter raise siblings rather than reinventing reporting. A thin `argparse` CLI exposes `lex` now and reserves `run`, `repl`, and `render` for Stages 3–4.

**Tech Stack:** Python ≥3.11, standard library only. `pytest` as the sole dev dependency. `hatchling` as build backend for the editable install.

## Global Constraints

- **Standard library only** in `src/matrixlang/`. `pytest` is a dev dependency and must never be imported by shipped code. (Parent spec, Stage 1: "Pure standard library.")
- **Every error reports line and column.** No exceptions to this, including internal ones.
- **Identifiers are ASCII only:** `[A-Za-z_][A-Za-z0-9_]*`. Never use `str.isalpha()` — it returns `True` for katakana, which would make Stage 4 glyph keywords lex as identifiers. Use explicit ASCII sets.
- **Numbers are ASCII integers only:** `[0-9]+`. Never use `str.isdigit()` — it returns `True` for Unicode digits such as `٣` and `４`. Use explicit ASCII sets.
- **Lines are 1-indexed. Columns are 1-indexed.** A tab advances the column by exactly 1.
- **Tests are written before implementation, in every task.**
- **Commit at the end of every task.**

**Reference:** `docs/superpowers/specs/SPEC-matrixlang-language-surface.md` §3 (lexical structure) and §8 (the nine acceptance cases). Task coverage of those nine cases is mapped in the Self-Review section at the end of this plan.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `pyproject.toml` | Package metadata, `matrixlang` console script, pytest config |
| `.gitignore` | Python ignores |
| `README.md` | Premise from parent spec §1 |
| `src/matrixlang/__init__.py` | Package marker, version |
| `src/matrixlang/tokens.py` | `TokenType`, `Token`, `KEYWORDS`. Pure data — no logic, no imports from siblings |
| `src/matrixlang/errors.py` | `MatrixLangError`, `LexError`. Shared by all future stages |
| `src/matrixlang/lexer.py` | `lex(source) -> list[Token]`. The scanner |
| `src/matrixlang/cli.py` | `main(argv) -> int`. Subcommand dispatch |
| `src/matrixlang/__main__.py` | Enables `python -m matrixlang` |
| `tests/test_package.py` | Package imports and installs correctly |
| `tests/test_lexer.py` | The nine acceptance cases plus regression cover |
| `tests/test_cli.py` | CLI exit codes and output shape |

`tokens.py` is deliberately separate from `lexer.py`. In Stage 2 the parser needs `TokenType` but has no business importing a scanner; keeping them apart now prevents a circular import later.

---

### Task 1: Project scaffolding

**Files:**
- Create: `.gitignore`, `README.md`, `pyproject.toml`, `src/matrixlang/__init__.py`
- Test: `tests/test_package.py`

**Interfaces:**
- Consumes: nothing
- Produces: an installed, importable `matrixlang` package exposing `__version__: str`

- [ ] **Step 1: Create the virtual environment and install pytest**

```bash
cd ~/Documents/GitHub/matrixlang
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet pytest
```

- [ ] **Step 2: Write the failing test**

Create `tests/test_package.py`:

```python
def test_package_is_importable():
    import matrixlang

    assert isinstance(matrixlang.__version__, str)
```

- [ ] **Step 3: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_package.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'matrixlang'`

- [ ] **Step 4: Create the scaffolding**

Create `.gitignore`:

```
.venv/
__pycache__/
*.py[cod]
.pytest_cache/
*.egg-info/
dist/
build/
.superpowers/
```

Create `pyproject.toml`:

```toml
[project]
name = "matrixlang"
version = "0.1.0"
description = "A Matrix-styled esoteric programming language."
requires-python = ">=3.11"
dependencies = []

[project.optional-dependencies]
dev = ["pytest>=8"]

[project.scripts]
matrixlang = "matrixlang.cli:main"

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/matrixlang"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

Create `src/matrixlang/__init__.py`:

```python
"""MatrixLang — a Matrix-styled esoteric programming language."""

__version__ = "0.1.0"
```

Create `README.md`:

```markdown
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
```

Then install the package in editable mode:

```bash
.venv/bin/pip install --quiet -e ".[dev]"
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_package.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add .gitignore README.md pyproject.toml src tests docs
git commit -m "chore: scaffold matrixlang package with pytest and CLI entry point"
```

---

### Task 2: Token types

**Files:**
- Create: `src/matrixlang/tokens.py`
- Test: `tests/test_tokens.py`

**Interfaces:**
- Consumes: nothing
- Produces:
  - `TokenType` — an `enum.Enum` with members `NUMBER STRING IDENT CONSTRUCT TRACE REDPILL BLUEPILL DEJAVU FLATLINE TRUE FALSE PLUS MINUS STAR SLASH ASSIGN EQ NEQ LT GT LTE GTE LPAREN RPAREN COMMENT NEWLINE EOF`
  - `KEYWORDS: dict[str, TokenType]` — the 8 reserved words
  - `Token` — frozen dataclass with fields `type: TokenType`, `lexeme: str`, `line: int`, `column: int`, `value: int | str | bool | None = None`

- [ ] **Step 1: Write the failing test**

Create `tests/test_tokens.py`:

```python
from matrixlang.tokens import KEYWORDS, Token, TokenType


def test_all_eight_keywords_are_registered():
    assert set(KEYWORDS) == {
        "construct",
        "trace",
        "redpill",
        "bluepill",
        "dejavu",
        "flatline",
        "true",
        "false",
    }


def test_keywords_map_to_distinct_token_types():
    assert len(set(KEYWORDS.values())) == len(KEYWORDS)
    assert KEYWORDS["construct"] is TokenType.CONSTRUCT
    assert KEYWORDS["dejavu"] is TokenType.DEJAVU


def test_token_carries_position_and_defaults_value_to_none():
    token = Token(TokenType.PLUS, "+", line=3, column=7)
    assert token.lexeme == "+"
    assert token.line == 3
    assert token.column == 7
    assert token.value is None


def test_token_is_hashable_and_compares_by_value():
    a = Token(TokenType.NUMBER, "2", 1, 1, 2)
    b = Token(TokenType.NUMBER, "2", 1, 1, 2)
    assert a == b
    assert len({a, b}) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_tokens.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'matrixlang.tokens'`

- [ ] **Step 3: Write the implementation**

Create `src/matrixlang/tokens.py`:

```python
"""Token vocabulary for MatrixLang.

Pure data. This module must not import from any sibling module — the Stage 2
parser depends on it and has no business pulling in the scanner.
"""

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    # Literals and names
    NUMBER = auto()
    STRING = auto()
    IDENT = auto()

    # Keywords
    CONSTRUCT = auto()
    TRACE = auto()
    REDPILL = auto()
    BLUEPILL = auto()
    DEJAVU = auto()
    FLATLINE = auto()
    TRUE = auto()
    FALSE = auto()

    # Operators
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    ASSIGN = auto()
    EQ = auto()
    NEQ = auto()
    LT = auto()
    GT = auto()
    LTE = auto()
    GTE = auto()

    # Punctuation
    LPAREN = auto()
    RPAREN = auto()

    # Structural
    COMMENT = auto()
    NEWLINE = auto()
    EOF = auto()


KEYWORDS: dict[str, TokenType] = {
    "construct": TokenType.CONSTRUCT,
    "trace": TokenType.TRACE,
    "redpill": TokenType.REDPILL,
    "bluepill": TokenType.BLUEPILL,
    "dejavu": TokenType.DEJAVU,
    "flatline": TokenType.FLATLINE,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
}


@dataclass(frozen=True)
class Token:
    """One lexical unit.

    `lexeme` is the exact source text, preserved so Stage 4 can re-render.
    `value` is the decoded Python value for NUMBER, STRING, TRUE and FALSE;
    None for everything else.
    """

    type: TokenType
    lexeme: str
    line: int
    column: int
    value: int | str | bool | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_tokens.py -v`
Expected: PASS, 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/tokens.py tests/test_tokens.py
git commit -m "feat(tokens): add TokenType, Token and the keyword table"
```

---

### Task 3: Lexer core — whitespace, single-char operators, newlines, unknown-character errors

**Files:**
- Create: `src/matrixlang/errors.py`, `src/matrixlang/lexer.py`
- Test: `tests/test_lexer.py`

**Interfaces:**
- Consumes: `TokenType`, `Token` from `matrixlang.tokens`
- Produces:
  - `MatrixLangError(Exception)` — base class for the whole toolchain
  - `LexError(MatrixLangError)` with attributes `message: str`, `line: int`, `column: int`
  - `lex(source: str) -> list[Token]`

**Behaviour fixed by this task:**
- Spaces, tabs and carriage returns are skipped; newlines emit `NEWLINE`.
- A source that does not end in a newline gets one **synthesised** before `EOF`. Empty source yields `[EOF]` alone.
- Any character the scanner does not recognise raises `LexError` with line and column.

- [ ] **Step 1: Write the failing test**

Create `tests/test_lexer.py`:

```python
import pytest

from matrixlang.errors import LexError
from matrixlang.lexer import lex
from matrixlang.tokens import TokenType


def kinds(source: str) -> list[TokenType]:
    """Token types only — keeps assertions readable."""
    return [t.type for t in lex(source)]


def pairs(source: str) -> list[tuple[TokenType, str]]:
    """(type, lexeme) pairs."""
    return [(t.type, t.lexeme) for t in lex(source)]


def test_single_character_operators():
    assert kinds("+ - * / ( )") == [
        TokenType.PLUS,
        TokenType.MINUS,
        TokenType.STAR,
        TokenType.SLASH,
        TokenType.LPAREN,
        TokenType.RPAREN,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_whitespace_is_skipped_but_newlines_are_not():
    assert kinds("+\t+\r+") == [
        TokenType.PLUS,
        TokenType.PLUS,
        TokenType.PLUS,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_trailing_newline_is_synthesised_exactly_once():
    with_newline = kinds("+\n")
    without_newline = kinds("+")
    assert with_newline == without_newline
    assert with_newline == [TokenType.PLUS, TokenType.NEWLINE, TokenType.EOF]


def test_empty_source_yields_only_eof():
    assert kinds("") == [TokenType.EOF]


def test_blank_lines_produce_newlines_and_nothing_else():
    # Acceptance case 7.
    assert kinds("\n\n\n+") == [
        TokenType.NEWLINE,
        TokenType.NEWLINE,
        TokenType.NEWLINE,
        TokenType.PLUS,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_line_and_column_are_one_indexed_and_track_newlines():
    tokens = lex("+\n  +")
    assert (tokens[0].line, tokens[0].column) == (1, 1)
    assert (tokens[2].line, tokens[2].column) == (2, 3)


def test_unknown_character_reports_line_and_column():
    # Acceptance case 9.
    with pytest.raises(LexError) as excinfo:
        lex("+ +\n+ @")
    error = excinfo.value
    assert error.line == 2
    assert error.column == 3
    assert "@" in str(error)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_lexer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'matrixlang.errors'`

- [ ] **Step 3: Write the implementation**

Create `src/matrixlang/errors.py`:

```python
"""Error hierarchy for the MatrixLang toolchain.

Every error carries a line and column. Stage 2 and Stage 3 add siblings to
LexError rather than inventing their own reporting.
"""


class MatrixLangError(Exception):
    """Base class for every error raised by MatrixLang."""

    def __init__(self, message: str, line: int, column: int) -> None:
        self.message = message
        self.line = line
        self.column = column
        super().__init__(f"[line {line}, column {column}] {message}")


class LexError(MatrixLangError):
    """The scanner could not turn the source into tokens."""
```

Create `src/matrixlang/lexer.py`:

```python
"""The MatrixLang scanner: source text in, token list out."""

import string

from matrixlang.errors import LexError
from matrixlang.tokens import Token, TokenType

_SINGLE: dict[str, TokenType] = {
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "*": TokenType.STAR,
    "/": TokenType.SLASH,
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "=": TokenType.ASSIGN,
    "<": TokenType.LT,
    ">": TokenType.GT,
}

# Explicit ASCII sets. str.isdigit() and str.isalpha() accept Unicode, which
# would let Stage 4 glyphs lex as identifiers. See Global Constraints.
_DIGITS = frozenset(string.digits)
_ID_START = frozenset(string.ascii_letters + "_")
_ID_CONTINUE = frozenset(string.ascii_letters + string.digits + "_")


def lex(source: str) -> list[Token]:
    """Scan `source` into a flat token list terminated by NEWLINE, EOF."""
    tokens: list[Token] = []
    index = 0
    line = 1
    column = 1
    length = len(source)

    while index < length:
        char = source[index]

        if char == "\n":
            tokens.append(Token(TokenType.NEWLINE, "\n", line, column))
            index += 1
            line += 1
            column = 1
            continue

        if char in " \t\r":
            index += 1
            column += 1
            continue

        if char in _SINGLE:
            tokens.append(Token(_SINGLE[char], char, line, column))
            index += 1
            column += 1
            continue

        raise LexError(f"unexpected character {char!r}", line, column)

    if tokens and tokens[-1].type is not TokenType.NEWLINE:
        tokens.append(Token(TokenType.NEWLINE, "", line, column))
    tokens.append(Token(TokenType.EOF, "", line, column))
    return tokens
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_lexer.py -v`
Expected: PASS, 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/errors.py src/matrixlang/lexer.py tests/test_lexer.py
git commit -m "feat(lexer): scan whitespace, single-char operators and newlines"
```

---

### Task 4: Two-character operators (longest match)

**Files:**
- Modify: `src/matrixlang/lexer.py`
- Test: `tests/test_lexer.py` (append)

**Interfaces:**
- Consumes: `lex` from Task 3
- Produces: no new names. `lex` now emits `EQ NEQ LTE GTE`.

**Behaviour fixed by this task:** two-character operators are matched **before** single-character ones, so `<=` is one token and never `LT` followed by `ASSIGN`. A bare `!` is an error — MatrixLang v1 has no logical operators.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_lexer.py`:

```python
def test_two_character_operators_win_over_single():
    # Acceptance case 4.
    assert kinds("<= >= == !=") == [
        TokenType.LTE,
        TokenType.GTE,
        TokenType.EQ,
        TokenType.NEQ,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_single_character_comparisons_still_work():
    assert kinds("< > =") == [
        TokenType.LT,
        TokenType.GT,
        TokenType.ASSIGN,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_two_character_operator_advances_column_by_two():
    tokens = lex("<= <=")
    assert tokens[0].column == 1
    assert tokens[1].column == 4


def test_bare_bang_is_an_error():
    with pytest.raises(LexError) as excinfo:
        lex("! ")
    assert excinfo.value.column == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_lexer.py -v`
Expected: FAIL — `test_two_character_operators_win_over_single` produces `LT, ASSIGN, ...` instead of `LTE, ...`

- [ ] **Step 3: Write the implementation**

In `src/matrixlang/lexer.py`, add the table below `_SINGLE`:

```python
_DOUBLE: dict[str, TokenType] = {
    "==": TokenType.EQ,
    "!=": TokenType.NEQ,
    "<=": TokenType.LTE,
    ">=": TokenType.GTE,
}
```

Then in `lex`, insert this block **immediately before** the `if char in _SINGLE:` block:

```python
        two = source[index : index + 2]
        if two in _DOUBLE:
            tokens.append(Token(_DOUBLE[two], two, line, column))
            index += 2
            column += 2
            continue
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_lexer.py -v`
Expected: PASS, 11 passed

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/lexer.py tests/test_lexer.py
git commit -m "feat(lexer): match two-character operators before single-character ones"
```

---

### Task 5: Integer literals

**Files:**
- Modify: `src/matrixlang/lexer.py`
- Test: `tests/test_lexer.py` (append)

**Interfaces:**
- Consumes: `lex` from Task 4
- Produces: no new names. `NUMBER` tokens carry `value: int`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_lexer.py`:

```python
def test_multi_digit_number_is_one_token_with_int_value():
    tokens = lex("1024")
    assert tokens[0].type is TokenType.NUMBER
    assert tokens[0].lexeme == "1024"
    assert tokens[0].value == 1024


def test_numbers_and_operators_interleave():
    assert pairs("2+3") == [
        (TokenType.NUMBER, "2"),
        (TokenType.PLUS, "+"),
        (TokenType.NUMBER, "3"),
        (TokenType.NEWLINE, ""),
        (TokenType.EOF, ""),
    ]


def test_number_column_points_at_first_digit():
    tokens = lex("  42")
    assert tokens[0].column == 3


def test_non_ascii_digits_are_rejected():
    # str.isdigit() would accept these. See Global Constraints.
    with pytest.raises(LexError):
        lex("４")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_lexer.py -v`
Expected: FAIL — `lex("1024")` raises `LexError: unexpected character '1'`

- [ ] **Step 3: Write the implementation**

In `lex`, insert this block **immediately after** the whitespace block and **before** the `_DOUBLE` block:

```python
        if char in _DIGITS:
            start = index
            start_column = column
            while index < length and source[index] in _DIGITS:
                index += 1
                column += 1
            lexeme = source[start:index]
            tokens.append(
                Token(TokenType.NUMBER, lexeme, line, start_column, int(lexeme))
            )
            continue
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_lexer.py -v`
Expected: PASS, 15 passed

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/lexer.py tests/test_lexer.py
git commit -m "feat(lexer): scan ASCII integer literals"
```

---

### Task 6: Identifiers and keywords

**Files:**
- Modify: `src/matrixlang/lexer.py`
- Test: `tests/test_lexer.py` (append)

**Interfaces:**
- Consumes: `lex` from Task 5, `KEYWORDS` from `matrixlang.tokens`
- Produces: no new names. `TRUE`/`FALSE` tokens carry `value: bool`.

**Behaviour fixed by this task:** a word is scanned to its full length and *then* looked up in `KEYWORDS`, so keyword matching can never fire on a prefix.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_lexer.py`:

```python
def test_identifier_is_scanned():
    tokens = lex("counter")
    assert tokens[0].type is TokenType.IDENT
    assert tokens[0].lexeme == "counter"
    assert tokens[0].value is None


def test_keyword_is_recognised():
    # Acceptance case 2.
    assert kinds("construct") == [
        TokenType.CONSTRUCT,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_keyword_matching_does_not_fire_on_a_prefix():
    # Acceptance case 3. 'constructor' starts with 'construct'.
    tokens = lex("constructor = 1")
    assert tokens[0].type is TokenType.IDENT
    assert tokens[0].lexeme == "constructor"


def test_booleans_carry_python_bool_values():
    tokens = lex("true false")
    assert (tokens[0].type, tokens[0].value) == (TokenType.TRUE, True)
    assert (tokens[1].type, tokens[1].value) == (TokenType.FALSE, False)


def test_identifiers_may_contain_digits_and_underscores():
    tokens = lex("_x1 count_2")
    assert [t.lexeme for t in tokens[:2]] == ["_x1", "count_2"]


def test_identifiers_may_not_start_with_a_digit():
    assert kinds("1x") == [
        TokenType.NUMBER,
        TokenType.IDENT,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_katakana_is_not_an_identifier():
    # str.isalpha() would accept this. Stage 4 needs glyphs to stay unclaimed.
    with pytest.raises(LexError):
        lex("ｱ")


def test_assignment_statement_lexes_as_specified():
    # Acceptance case 1 — the parent spec's opening commit.
    assert kinds("x = 2 + 3") == [
        TokenType.IDENT,
        TokenType.ASSIGN,
        TokenType.NUMBER,
        TokenType.PLUS,
        TokenType.NUMBER,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_lexer.py -v`
Expected: FAIL — `lex("counter")` raises `LexError: unexpected character 'c'`

- [ ] **Step 3: Write the implementation**

Add `KEYWORDS` to the import at the top of `src/matrixlang/lexer.py`:

```python
from matrixlang.tokens import KEYWORDS, Token, TokenType
```

In `lex`, insert this block **immediately after** the number block:

```python
        if char in _ID_START:
            start = index
            start_column = column
            while index < length and source[index] in _ID_CONTINUE:
                index += 1
                column += 1
            lexeme = source[start:index]
            token_type = KEYWORDS.get(lexeme, TokenType.IDENT)
            value: bool | None = None
            if token_type is TokenType.TRUE:
                value = True
            elif token_type is TokenType.FALSE:
                value = False
            tokens.append(Token(token_type, lexeme, line, start_column, value))
            continue
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_lexer.py -v`
Expected: PASS, 23 passed

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/lexer.py tests/test_lexer.py
git commit -m "feat(lexer): scan identifiers and resolve keywords by full-word lookup"
```

---

### Task 7: String literals

**Files:**
- Modify: `src/matrixlang/lexer.py`
- Test: `tests/test_lexer.py` (append)

**Interfaces:**
- Consumes: `lex` from Task 6
- Produces: private helper `_scan_string(source, index, line, column) -> tuple[Token, int, int]` returning the token and the updated `(index, column)`. `STRING` tokens carry the **raw** source text including quotes in `lexeme` and the **decoded** text in `value`.

**Behaviour fixed by this task:** escapes are `\"`, `\\`, `\n`. Any other escape is an error. A newline inside a string, or end-of-input before the closing quote, is an unterminated-string error reported at the **opening** quote.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_lexer.py`:

```python
def test_string_keeps_raw_lexeme_and_decoded_value():
    # Acceptance case 5.
    tokens = lex('"wake up, "')
    assert tokens[0].type is TokenType.STRING
    assert tokens[0].lexeme == '"wake up, "'
    assert tokens[0].value == "wake up, "


def test_string_escapes_are_decoded():
    tokens = lex(r'"a\"b\\c\nd"')
    assert tokens[0].value == 'a"b\\c\nd'


def test_string_concatenation_expression_lexes():
    assert kinds('"wake up, " + name') == [
        TokenType.STRING,
        TokenType.PLUS,
        TokenType.IDENT,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_unterminated_string_reports_the_opening_quote():
    # Acceptance case 8.
    with pytest.raises(LexError) as excinfo:
        lex('trace "unterminated')
    error = excinfo.value
    assert error.line == 1
    assert error.column == 7
    assert "unterminated" in str(error)


def test_newline_inside_string_is_unterminated():
    with pytest.raises(LexError) as excinfo:
        lex('"broken\n"')
    assert excinfo.value.line == 1


def test_unknown_escape_is_an_error():
    with pytest.raises(LexError) as excinfo:
        lex(r'"\q"')
    assert "\\q" in str(excinfo.value)


def test_empty_string_is_valid():
    tokens = lex('""')
    assert tokens[0].value == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_lexer.py -v`
Expected: FAIL — `lex('"wake up, "')` raises `LexError: unexpected character '"'`

- [ ] **Step 3: Write the implementation**

Add the escape table below `_ID_CONTINUE` in `src/matrixlang/lexer.py`:

```python
_ESCAPES: dict[str, str] = {'"': '"', "\\": "\\", "n": "\n"}
```

Add the helper below `lex` (module level, after the function):

```python
def _scan_string(
    source: str, index: int, line: int, column: int
) -> tuple[Token, int, int]:
    """Scan a double-quoted string starting at `index`.

    Returns the token plus the updated index and column. Errors are reported
    at the opening quote, which is the position a reader needs to find.
    """
    length = len(source)
    start = index
    start_column = column
    index += 1
    column += 1
    decoded: list[str] = []

    while True:
        if index >= length or source[index] == "\n":
            raise LexError("unterminated string", line, start_column)

        char = source[index]

        if char == '"':
            index += 1
            column += 1
            return (
                Token(
                    TokenType.STRING,
                    source[start:index],
                    line,
                    start_column,
                    "".join(decoded),
                ),
                index,
                column,
            )

        if char == "\\":
            if index + 1 >= length or source[index + 1] == "\n":
                raise LexError("unterminated string", line, start_column)
            escape = source[index + 1]
            if escape not in _ESCAPES:
                raise LexError(
                    f"unknown escape sequence '\\{escape}'", line, column
                )
            decoded.append(_ESCAPES[escape])
            index += 2
            column += 2
            continue

        decoded.append(char)
        index += 1
        column += 1
```

In `lex`, insert this block **immediately after** the whitespace block and **before** the number block:

```python
        if char == '"':
            token, index, column = _scan_string(source, index, line, column)
            tokens.append(token)
            continue
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_lexer.py -v`
Expected: PASS, 30 passed

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/lexer.py tests/test_lexer.py
git commit -m "feat(lexer): scan string literals with escapes and unterminated detection"
```

---

### Task 8: Comments as tokens

**Files:**
- Modify: `src/matrixlang/lexer.py`
- Test: `tests/test_lexer.py` (append)

**Interfaces:**
- Consumes: `lex` from Task 7
- Produces: no new names. `COMMENT` tokens carry the raw text **including** the `#` in `lexeme`.

**Behaviour fixed by this task:** comments are emitted, never discarded. This is what makes the parent spec §4.3 round-trip honest — see language-surface spec §6.1. The lexer does not attach comments to anything; Stage 2 turns `COMMENT` tokens into AST trivia.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_lexer.py`:

```python
def test_comment_is_emitted_not_discarded():
    # Acceptance case 6.
    tokens = lex("trace x  # wake up")
    assert [t.type for t in tokens] == [
        TokenType.TRACE,
        TokenType.IDENT,
        TokenType.COMMENT,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]
    assert tokens[2].lexeme == "# wake up"


def test_comment_stops_at_the_newline():
    assert kinds("# one\n# two\n") == [
        TokenType.COMMENT,
        TokenType.NEWLINE,
        TokenType.COMMENT,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_hash_inside_a_string_is_not_a_comment():
    tokens = lex('"# not a comment"')
    assert tokens[0].type is TokenType.STRING
    assert tokens[0].value == "# not a comment"


def test_comment_column_points_at_the_hash():
    tokens = lex("x # here")
    assert tokens[1].column == 3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_lexer.py -v`
Expected: FAIL — `lex("trace x  # wake up")` raises `LexError: unexpected character '#'`

- [ ] **Step 3: Write the implementation**

In `lex`, insert this block **immediately after** the whitespace block and **before** the string block:

```python
        if char == "#":
            start = index
            start_column = column
            while index < length and source[index] != "\n":
                index += 1
                column += 1
            tokens.append(
                Token(TokenType.COMMENT, source[start:index], line, start_column)
            )
            continue
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_lexer.py -v`
Expected: PASS, 34 passed

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/lexer.py tests/test_lexer.py
git commit -m "feat(lexer): emit comments as tokens so Stage 4 can round-trip them"
```

---

### Task 9: CLI skeleton

**Files:**
- Create: `src/matrixlang/cli.py`, `src/matrixlang/__main__.py`, `examples/hello.rain`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `lex` from Task 8, `MatrixLangError` from `matrixlang.errors`
- Produces: `main(argv: list[str] | None = None) -> int`. Exit codes: `0` success, `1` source error, `2` usage or I/O error.

**Behaviour fixed by this task:** `lex` works. `run`, `repl` and `render` parse but exit `2` with a message naming the stage that will implement them — honest scaffolding, not dead code.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli.py`:

```python
import pytest

from matrixlang.cli import main


@pytest.fixture
def source_file(tmp_path):
    def write(text: str):
        path = tmp_path / "program.rain"
        path.write_text(text, encoding="utf-8")
        return str(path)

    return write


def test_lex_prints_tokens_and_exits_zero(source_file, capsys):
    exit_code = main(["lex", source_file("x = 1\n")])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "IDENT" in output
    assert "ASSIGN" in output
    assert "NUMBER" in output
    assert "EOF" in output


def test_lex_reports_source_errors_on_stderr_and_exits_one(source_file, capsys):
    exit_code = main(["lex", source_file('trace "unterminated\n')])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "line 1" in captured.err
    assert "column 7" in captured.err


def test_missing_file_exits_two(capsys, tmp_path):
    exit_code = main(["lex", str(tmp_path / "nope.rain")])
    assert exit_code == 2
    assert "nope.rain" in capsys.readouterr().err


def test_non_utf8_file_exits_two_without_traceback(capsys, tmp_path):
    path = tmp_path / "binary.rain"
    path.write_bytes(b"\xff\xfe invalid utf-8")
    exit_code = main(["lex", str(path)])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "matrixlang:" in captured.err


def test_unimplemented_subcommands_exit_two_naming_the_stage(capsys):
    for command in ("run", "repl", "render"):
        assert main([command]) == 2
    assert "Stage" in capsys.readouterr().err


def test_no_subcommand_is_a_usage_error():
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'matrixlang.cli'`

- [ ] **Step 3: Write the implementation**

Create `src/matrixlang/cli.py`:

```python
"""Command-line entry point for the MatrixLang toolchain."""

import argparse
import sys
from pathlib import Path

from matrixlang.errors import MatrixLangError
from matrixlang.lexer import lex

_PENDING: dict[str, str] = {
    "run": "Stage 3",
    "repl": "Stage 3",
    "render": "Stage 4",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="matrixlang", description="The MatrixLang toolchain."
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    lex_parser = subcommands.add_parser(
        "lex", help="Print the token stream for a source file."
    )
    lex_parser.add_argument("path", help="Path to a .rain source file.")

    subcommands.add_parser("run", help="Execute a source file. (Stage 3)")
    subcommands.add_parser("repl", help="Start an interactive session. (Stage 3)")
    subcommands.add_parser(
        "render", help="Convert between the ASCII and glyph faces. (Stage 4)"
    )

    args = parser.parse_args(argv)

    if args.command == "lex":
        return _command_lex(args.path)

    stage = _PENDING[args.command]
    print(
        f"matrixlang: '{args.command}' arrives in {stage}", file=sys.stderr
    )
    return 2


def _command_lex(path: str) -> int:
    try:
        source = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"matrixlang: {error}", file=sys.stderr)
        return 2

    try:
        tokens = lex(source)
    except MatrixLangError as error:
        print(f"matrixlang: {error}", file=sys.stderr)
        return 1

    for token in tokens:
        print(f"{token.line}:{token.column}\t{token.type.name}\t{token.lexeme!r}")
    return 0
```

Create `src/matrixlang/__main__.py`:

```python
"""Enables `python -m matrixlang`."""

import sys

from matrixlang.cli import main

if __name__ == "__main__":
    sys.exit(main())
```

Create `examples/hello.rain`:

```
# The Stage 3 demo. Lexes today; runs once the interpreter lands.
construct n = 0
construct name = "Neo"

dejavu n < 3
  redpill n == 1
    trace "wake up, " + name
  bluepill
    trace n
  flatline
  n = n + 1
flatline
```

Note that `tokens` is built **before** any printing in `_command_lex`, so a source error produces no partial output on stdout. The test asserts this.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: PASS, 5 passed

- [ ] **Step 5: Verify the whole suite and the real entry point**

```bash
.venv/bin/python -m pytest -v
.venv/bin/matrixlang lex examples/hello.rain
```

Expected: all tests pass, and the example file prints a token stream ending in `EOF` with exit code 0.

- [ ] **Step 6: Commit**

```bash
git add src/matrixlang/cli.py src/matrixlang/__main__.py tests/test_cli.py examples/hello.rain
git commit -m "feat(cli): add matrixlang entry point with working lex subcommand"
```

---

## Self-Review

**Spec coverage — the nine acceptance cases from language-surface spec §8:**

| Case | Input | Task | Test |
| --- | --- | --- | --- |
| 1 | `x = 2 + 3` | 6 | `test_assignment_statement_lexes_as_specified` |
| 2 | `construct n = 0` | 6 | `test_keyword_is_recognised` |
| 3 | `constructor = 1` | 6 | `test_keyword_matching_does_not_fire_on_a_prefix` |
| 4 | `n <= 10` | 4 | `test_two_character_operators_win_over_single` |
| 5 | `"wake up, " + name` | 7 | `test_string_keeps_raw_lexeme_and_decoded_value` |
| 6 | `trace x  # comment` | 8 | `test_comment_is_emitted_not_discarded` |
| 7 | `\n\n\nx = 1` | 3 | `test_blank_lines_produce_newlines_and_nothing_else` |
| 8 | `trace "unterminated` | 7 | `test_unterminated_string_reports_the_opening_quote` |
| 9 | `construct x = 5 @ 3` | 3 | `test_unknown_character_reports_line_and_column` |

All nine covered.

**Other spec §3.2 rules:**

| Rule | Task |
| --- | --- |
| Integers only, `[0-9]+` | 5 |
| Identifiers `[A-Za-z_][A-Za-z0-9_]*`, ASCII only | 6 |
| String escapes `\"` `\\` `\n` | 7 |
| Newline inside a string is an error | 7 |
| Comments `#` to end of line, not discarded | 8 |
| NEWLINE is a token | 3 |
| Indentation cosmetic, no INDENT/DEDENT | 3 |
| Longest-match on operators | 4 |

**Scanner dispatch order** — the branches in `lex` must end up in exactly this order, since several are prefix-ambiguous:

1. newline
2. whitespace
3. comment (`#`)
4. string (`"`)
5. number (`_DIGITS`)
6. identifier/keyword (`_ID_START`)
7. two-character operator (`_DOUBLE`)
8. single-character operator (`_SINGLE`)
9. error

Only 7-before-8 is strictly load-bearing. The rest are unambiguous by first character, but this order is what the tasks build and what the tests assume.

**Out of scope for Stage 1** — deliberately not here: parsing, the AST, comment-to-trivia attachment, glyph rendering, and the `run`/`repl`/`render` implementations. Stages 2–4.
