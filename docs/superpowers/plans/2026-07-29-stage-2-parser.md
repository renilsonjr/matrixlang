# Stage 2 — Parser Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Stage 1 token stream into a syntax tree covering the full grammar — expressions with correct precedence, all five statements, and lossless comment trivia — plus a `matrixlang parse` subcommand that prints the tree.

**Architecture:** Recursive-descent parser, one method per grammar rule, precedence encoded in the call chain (equality → comparison → term → factor → unary → primary). AST nodes live in `nodes.py` as plain dataclasses — pure data, importing only the token vocabulary, so the Stage 3 interpreter and Stage 4 renderers consume the tree without touching the parser. The parser consumes `list[Token]` and never imports the lexer: that separation is what lets one parser serve both source faces in Stage 4. `ParseError` joins the existing error hierarchy. A `treeview.py` module renders the tree as indented text for the CLI and the episode-2 demo.

**Tech Stack:** Python ≥3.11, standard library only. pytest as the sole dev dependency.

## Global Constraints

- **Standard library only** in `src/matrixlang/`. pytest is a dev dependency and must never be imported by shipped code.
- **Every error reports line and column**, both 1-indexed. `ParseError(MatrixLangError)` — never a bare exception.
- **The parser never imports the lexer.** It operates on any `list[Token]`. Dependency direction: `cli → {parser, treeview, lexer, errors}`, `parser → {nodes, tokens, errors}`, `treeview → {nodes, tokens}`, `nodes → {tokens}`.
- **AST equality is structural + trivia, never positional.** Comment trivia participates in `==`; `line`/`column` carry `compare=False`. Both halves are load-bearing for the parent spec §4.3 round-trip criterion: dropping a comment must break equality, while re-rendered positions must not.
- **No semantic checks in the parser.** Assigning to an undeclared name, non-boolean conditions — all parse fine. Semantics are Stage 3's job (language spec §5).
- **`str.isalpha()` and `str.isdigit()` remain banned** package-wide (inherited from Stage 1).
- **Tests are written before implementation, in every task.**
- **Commit at the end of every task.**

**Reference:** `docs/superpowers/specs/SPEC-matrixlang-language-surface.md` §4 (grammar), §6.1 (comment trivia). Parent spec Stage 2 done-when: the tree for `x = 2 + 3 * 4` places multiplication below addition — that is Task 3's headline test.

**Environment note for every task:** run tests with `.venv/bin/python -m pytest`. Never run `pip install`, never create a venv, never add a conftest.py. Known machine fault: if `import matrixlang` fails with ModuleNotFoundError, run `chflags -R nohidden .venv` and continue (note it in your report). Any other import failure: report BLOCKED.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `src/matrixlang/nodes.py` | AST node dataclasses. Pure data; imports only `tokens` |
| `src/matrixlang/parser.py` | `parse(tokens) -> Program`, `parse_expression(tokens) -> Expr` |
| `src/matrixlang/treeview.py` | `format_tree(program) -> str` — indented text view, presentation only |
| `src/matrixlang/errors.py` | Modify: add `ParseError` |
| `src/matrixlang/cli.py` | Modify: `parse` subcommand, shared `_read_source` helper |
| `tests/test_nodes.py` | Equality semantics (structural, trivia, positions) |
| `tests/test_errors.py` | Pins the `[line N, column M]` format contract |
| `tests/test_parser.py` | Grows across Tasks 2–7 |
| `tests/test_treeview.py` | Tree text format |
| `tests/test_cli.py` | Modify: `parse` subcommand tests |

The module is named `nodes.py`, not `ast.py`, to avoid shadowing the stdlib `ast` module in careless imports.

### Comment trivia model (from spec §6.1, made concrete)

- Every statement carries `leading_comments: list[str]` (full-line comments above it) and `trailing_comment: str | None` (comment on its final line — for `If`/`While` that is the `flatline` line).
- `Program` carries `trailing_comments` for comments after the last statement. Each block body has the same problem, so `If` carries `then_trailing`/`else_trailing` and `While` carries `body_trailing`.
- **Normalization rule:** a comment on a block-header line (`redpill x  # why`, `bluepill  # hm`, `dejavu n < 3  # loop`) adopts into that block's body — prepended to the first body statement's `leading_comments`, or to the body's `*_trailing` list if the body is empty. Lossless at AST level: the text survives and re-parses equal; only line placement normalizes on render.
- Comment strings store the raw lexeme including `#`.

---

### Task 1: AST nodes and ParseError

**Files:**
- Create: `src/matrixlang/nodes.py`, `tests/test_nodes.py`, `tests/test_errors.py`
- Modify: `src/matrixlang/errors.py`, `docs/superpowers/specs/SPEC-matrixlang-language-surface.md`

**Interfaces:**
- Consumes: `TokenType` from `matrixlang.tokens`
- Produces:
  - `Node` base (kw-only `line: int = 0`, `column: int = 0`, both `compare=False`)
  - Expressions: `Expr(Node)`; `NumberLiteral(value: int)`, `StringLiteral(value: str)`, `BoolLiteral(value: bool)`, `Name(ident: str)`, `Unary(op: TokenType, operand: Expr)`, `Binary(left: Expr, op: TokenType, right: Expr)`
  - Statements: `Stmt(Node)` with kw-only trivia `leading_comments: list[str]`, `trailing_comment: str | None`; `Declare(name: str, value: Expr)`, `Assign(name: str, value: Expr)`, `Trace(value: Expr)`, `If(condition, then_body: list[Stmt], else_body: list[Stmt] | None = None, *, then_trailing, else_trailing)`, `While(condition, body: list[Stmt], *, body_trailing)`
  - `Program(statements: list[Stmt], *, trailing_comments: list[str])`
  - `ParseError(MatrixLangError)` in errors.py

- [ ] **Step 1: Write the failing tests**

Create `tests/test_nodes.py`:

```python
from matrixlang.nodes import (
    Binary,
    BoolLiteral,
    Declare,
    Name,
    NumberLiteral,
    Trace,
)
from matrixlang.tokens import TokenType


def test_equality_is_structural():
    a = Binary(NumberLiteral(2), TokenType.PLUS, NumberLiteral(3))
    b = Binary(NumberLiteral(2), TokenType.PLUS, NumberLiteral(3))
    assert a == b


def test_positions_do_not_participate_in_equality():
    # Load-bearing for the parent spec §4.3 round-trip: a re-rendered face
    # has different columns, so positional equality would make the
    # criterion unsatisfiable.
    a = NumberLiteral(5, line=1, column=1)
    b = NumberLiteral(5, line=9, column=42)
    assert a == b


def test_comment_trivia_participates_in_equality():
    a = Trace(Name("x"))
    b = Trace(Name("x"))
    b.trailing_comment = "# wake up"
    assert a != b


def test_trivia_defaults_are_empty():
    s = Declare("x", NumberLiteral(0))
    assert s.leading_comments == []
    assert s.trailing_comment is None


def test_trivia_lists_are_not_shared_between_nodes():
    a = Trace(Name("x"))
    b = Trace(Name("y"))
    a.leading_comments.append("# only a")
    assert b.leading_comments == []


def test_distinct_node_types_are_never_equal():
    # Guards the Python quirk that 1 == True.
    assert NumberLiteral(1) != BoolLiteral(True)
```

Create `tests/test_errors.py`:

```python
from matrixlang.errors import LexError, MatrixLangError, ParseError


def test_message_format_pins_line_and_column():
    # This exact format is a contract: the CLI, and every future stage's
    # errors, present positions this way.
    error = MatrixLangError("something broke", 3, 7)
    assert str(error) == "[line 3, column 7] something broke"


def test_attributes_survive():
    error = ParseError("bad tree", 2, 5)
    assert (error.message, error.line, error.column) == ("bad tree", 2, 5)


def test_hierarchy():
    assert issubclass(LexError, MatrixLangError)
    assert issubclass(ParseError, MatrixLangError)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_nodes.py tests/test_errors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'matrixlang.nodes'`, and ImportError for `ParseError`.

- [ ] **Step 3: Write the implementation**

Append to `src/matrixlang/errors.py`:

```python
class ParseError(MatrixLangError):
    """The parser could not build a tree from the tokens."""
```

Create `src/matrixlang/nodes.py`:

```python
"""AST node definitions for MatrixLang.

Pure data. Imports only the token vocabulary — the parser depends on this
module, never the reverse.

Two equality rules matter for the Stage 4 round-trip criterion (parent
spec §4.3): comment trivia PARTICIPATES in equality; source positions DO
NOT. Rendering a tree and re-parsing it yields identical trivia but
different line/column numbers, so positions carry compare=False.
"""

from dataclasses import dataclass, field

from matrixlang.tokens import TokenType


@dataclass
class Node:
    line: int = field(default=0, kw_only=True, compare=False)
    column: int = field(default=0, kw_only=True, compare=False)


# --- Expressions ---------------------------------------------------------


@dataclass
class Expr(Node):
    pass


@dataclass
class NumberLiteral(Expr):
    value: int


@dataclass
class StringLiteral(Expr):
    value: str


@dataclass
class BoolLiteral(Expr):
    value: bool


@dataclass
class Name(Expr):
    ident: str


@dataclass
class Unary(Expr):
    op: TokenType
    operand: Expr


@dataclass
class Binary(Expr):
    left: Expr
    op: TokenType
    right: Expr


# --- Statements ----------------------------------------------------------


@dataclass
class Stmt(Node):
    """Base statement. Trivia fields per language spec §6.1."""

    leading_comments: list[str] = field(default_factory=list, kw_only=True)
    trailing_comment: str | None = field(default=None, kw_only=True)


@dataclass
class Declare(Stmt):
    name: str
    value: Expr


@dataclass
class Assign(Stmt):
    name: str
    value: Expr


@dataclass
class Trace(Stmt):
    value: Expr


@dataclass
class If(Stmt):
    """then_trailing/else_trailing hold comments after each body's last
    statement — the per-body analogue of Program.trailing_comments."""

    condition: Expr
    then_body: list[Stmt]
    else_body: list[Stmt] | None = None
    then_trailing: list[str] = field(default_factory=list, kw_only=True)
    else_trailing: list[str] = field(default_factory=list, kw_only=True)


@dataclass
class While(Stmt):
    condition: Expr
    body: list[Stmt]
    body_trailing: list[str] = field(default_factory=list, kw_only=True)


@dataclass
class Program(Node):
    statements: list[Stmt]
    trailing_comments: list[str] = field(default_factory=list, kw_only=True)
```

- [ ] **Step 4: Amend the language spec**

In `docs/superpowers/specs/SPEC-matrixlang-language-surface.md` §6.1, after the bullet "AST equality in §4.3 includes trivia.", add this bullet:

```markdown
- Source positions (line, column) are carried on nodes for error reporting but are
  **excluded** from AST equality — a re-rendered face has different columns, and the
  §4.3 criterion must still hold.
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_nodes.py tests/test_errors.py -v`
Expected: PASS, 9 passed. Then full suite: 55 passed.

- [ ] **Step 6: Commit**

```bash
git add src/matrixlang/nodes.py src/matrixlang/errors.py tests/test_nodes.py tests/test_errors.py docs/superpowers/specs/SPEC-matrixlang-language-surface.md
git commit -m "feat(nodes): AST dataclasses with trivia-aware, position-blind equality"
```

---

### Task 2: Parser core — primaries, unary, parse_expression

**Files:**
- Create: `src/matrixlang/parser.py`, `tests/test_parser.py`

**Interfaces:**
- Consumes: `Token`, `TokenType`; `ParseError`; expression nodes from Task 1
- Produces: `parse_expression(tokens: list[Token]) -> Expr` (the Stage 3 REPL's entry point); internal `_Parser` class with `peek/advance/check/expect` and the `expression()` entry that Task 3 rewires

- [ ] **Step 1: Write the failing tests**

Create `tests/test_parser.py`:

```python
import pytest

from matrixlang.errors import ParseError
from matrixlang.lexer import lex
from matrixlang.nodes import (
    BoolLiteral,
    Name,
    NumberLiteral,
    StringLiteral,
    Unary,
)
from matrixlang.parser import parse_expression
from matrixlang.tokens import TokenType


def expr(source):
    return parse_expression(lex(source))


def test_number_literal():
    assert expr("42") == NumberLiteral(42)


def test_string_literal():
    assert expr('"Neo"') == StringLiteral("Neo")


def test_bool_literals():
    assert expr("true") == BoolLiteral(True)
    assert expr("false") == BoolLiteral(False)


def test_name():
    assert expr("counter") == Name("counter")


def test_parens_group_without_a_wrapper_node():
    # No Grouping node: parens live in tree shape. The Stage 4 renderer
    # re-derives them from precedence, which is lossless at AST level.
    assert expr("(42)") == NumberLiteral(42)


def test_unary_minus_nests():
    assert expr("--3") == Unary(
        TokenType.MINUS, Unary(TokenType.MINUS, NumberLiteral(3))
    )


def test_positions_are_captured_but_not_compared():
    node = expr("  42")
    assert (node.line, node.column) == (1, 3)
    assert node == NumberLiteral(42)


def test_unclosed_paren_reports_position():
    with pytest.raises(ParseError) as excinfo:
        expr("(1 + 2")
    assert excinfo.value.column == 4


def test_missing_expression_is_an_error():
    with pytest.raises(ParseError) as excinfo:
        expr("+")
    assert "expected an expression" in str(excinfo.value)


def test_trailing_input_is_an_error():
    with pytest.raises(ParseError):
        expr("1 2")


def test_trailing_comment_is_tolerated_and_discarded():
    # REPL convenience. The §4.3 round-trip criterion applies to whole
    # programs via parse(), where trivia is preserved.
    assert expr("1  # note") == NumberLiteral(1)
```

Note on `test_unclosed_paren_reports_position`: at this task `expression()` is just unary→primary, so `(1 + 2` parses `1`, then `expect(RPAREN)` fails at the `+` (column 4). The test stays valid after Task 3 wires binary operators — then the inner expression consumes `1 + 2` and the failure moves to end-of-line… which the lexer synthesises a NEWLINE for, at column 7. **Because of that, Task 3 will update this test's expected column to 7 — that update is explicitly planned there, not a regression.**

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_parser.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'matrixlang.parser'`

- [ ] **Step 3: Write the implementation**

Create `src/matrixlang/parser.py`:

```python
"""The MatrixLang parser: token list in, syntax tree out.

Recursive descent. One method per grammar rule; precedence is encoded in
the call chain, tightest binding deepest. The parser never imports the
lexer — it consumes any list[Token], which is what lets one parser serve
both source faces in Stage 4.
"""

from matrixlang.errors import ParseError
from matrixlang.nodes import (
    BoolLiteral,
    Expr,
    Name,
    NumberLiteral,
    StringLiteral,
    Unary,
)
from matrixlang.tokens import Token, TokenType


def parse_expression(tokens: list[Token]) -> Expr:
    """Parse a single expression — the Stage 3 REPL's entry point.

    A trailing comment is accepted and discarded: expression parsing is a
    REPL convenience; the round-trip criterion applies to whole programs
    via parse(), where trivia is preserved.
    """
    parser = _Parser(tokens)
    expr = parser.expression()
    if parser.check(TokenType.COMMENT):
        parser.advance()
    if parser.check(TokenType.NEWLINE):
        parser.advance()
    end = parser.peek()
    if end.type is not TokenType.EOF:
        raise ParseError(
            f"unexpected input after expression: {_describe(end)}",
            end.line,
            end.column,
        )
    return expr


def _describe(token: Token) -> str:
    if token.type is TokenType.EOF:
        return "end of input"
    if token.type is TokenType.NEWLINE:
        return "end of line"
    return f"'{token.lexeme}'"


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    # --- cursor -----------------------------------------------------------

    def peek(self) -> Token:
        return self._tokens[self._pos]

    def advance(self) -> Token:
        token = self._tokens[self._pos]
        self._pos += 1
        return token

    def check(self, type_: TokenType) -> bool:
        return self.peek().type is type_

    def expect(self, type_: TokenType, message: str) -> Token:
        token = self.peek()
        if token.type is not type_:
            raise ParseError(
                f"{message}, found {_describe(token)}", token.line, token.column
            )
        return self.advance()

    # --- expressions ------------------------------------------------------

    def expression(self) -> Expr:
        return self._unary()

    def _unary(self) -> Expr:
        if self.check(TokenType.MINUS):
            op = self.advance()
            operand = self._unary()
            return Unary(TokenType.MINUS, operand, line=op.line, column=op.column)
        return self._primary()

    def _primary(self) -> Expr:
        token = self.peek()
        if token.type is TokenType.NUMBER:
            self.advance()
            return NumberLiteral(token.value, line=token.line, column=token.column)
        if token.type is TokenType.STRING:
            self.advance()
            return StringLiteral(token.value, line=token.line, column=token.column)
        if token.type in (TokenType.TRUE, TokenType.FALSE):
            self.advance()
            return BoolLiteral(token.value, line=token.line, column=token.column)
        if token.type is TokenType.IDENT:
            self.advance()
            return Name(token.lexeme, line=token.line, column=token.column)
        if token.type is TokenType.LPAREN:
            self.advance()
            inner = self.expression()
            self.expect(TokenType.RPAREN, "expected ')' to close '('")
            return inner
        raise ParseError(
            f"expected an expression, found {_describe(token)}",
            token.line,
            token.column,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_parser.py -v`
Expected: PASS, 11 passed. Full suite: 66 passed.

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/parser.py tests/test_parser.py
git commit -m "feat(parser): cursor, primaries, unary minus and parse_expression"
```

---

### Task 3: The precedence ladder

**Files:**
- Modify: `src/matrixlang/parser.py`, `tests/test_parser.py`

**Interfaces:**
- Consumes: `_Parser` from Task 2; `Binary` from nodes
- Produces: no new public names. `expression()` now runs the full ladder equality → comparison → term → factor → unary.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_parser.py` (and add `Binary` to the nodes import):

```python
def test_multiplication_binds_tighter_than_addition():
    # THE Stage 2 done-when from the parent spec: * sits BELOW + in the tree.
    assert expr("2 + 3 * 4") == Binary(
        NumberLiteral(2),
        TokenType.PLUS,
        Binary(NumberLiteral(3), TokenType.STAR, NumberLiteral(4)),
    )


def test_same_level_operators_associate_left():
    assert expr("10 - 3 - 2") == Binary(
        Binary(NumberLiteral(10), TokenType.MINUS, NumberLiteral(3)),
        TokenType.MINUS,
        NumberLiteral(2),
    )


def test_parens_override_precedence():
    assert expr("(2 + 3) * 4") == Binary(
        Binary(NumberLiteral(2), TokenType.PLUS, NumberLiteral(3)),
        TokenType.STAR,
        NumberLiteral(4),
    )


def test_comparison_sits_below_arithmetic():
    assert expr("1 + 2 < 4") == Binary(
        Binary(NumberLiteral(1), TokenType.PLUS, NumberLiteral(2)),
        TokenType.LT,
        NumberLiteral(4),
    )


def test_equality_sits_below_comparison():
    assert expr("1 < 2 == 3 < 4") == Binary(
        Binary(NumberLiteral(1), TokenType.LT, NumberLiteral(2)),
        TokenType.EQ,
        Binary(NumberLiteral(3), TokenType.LT, NumberLiteral(4)),
    )


def test_unary_binds_tighter_than_multiplication():
    assert expr("-2 * 3") == Binary(
        Unary(TokenType.MINUS, NumberLiteral(2)), TokenType.STAR, NumberLiteral(3)
    )
```

Also apply the planned update from Task 2's note: in `test_unclosed_paren_reports_position`, change `assert excinfo.value.column == 4` to `assert excinfo.value.column == 7` — with binary operators wired, the inner expression now consumes `1 + 2` and `expect(RPAREN)` fails at the synthesised end-of-line (column 7).

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_parser.py -v`
Expected: the six new tests FAIL (`expression()` stops at unary, so `2 + 3 * 4` leaves trailing input); the amended paren test FAILS with column 4 ≠ 7.

- [ ] **Step 3: Write the implementation**

In `src/matrixlang/parser.py`, add `Binary` to the nodes import. Add these operator tables at module level, below `_describe`:

```python
_EQUALITY_OPS = (TokenType.EQ, TokenType.NEQ)
_COMPARISON_OPS = (TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE)
_TERM_OPS = (TokenType.PLUS, TokenType.MINUS)
_FACTOR_OPS = (TokenType.STAR, TokenType.SLASH)
```

Replace the `expression` method and insert the ladder above `_unary`:

```python
    def expression(self) -> Expr:
        return self._equality()

    # The ladder: each level parses the next-tighter level, then folds a
    # left-associative chain of its own operators. Named levels keep the
    # grammar visible; the shared loop lives once in _binary_level.

    def _equality(self) -> Expr:
        return self._binary_level(_EQUALITY_OPS, self._comparison)

    def _comparison(self) -> Expr:
        return self._binary_level(_COMPARISON_OPS, self._term)

    def _term(self) -> Expr:
        return self._binary_level(_TERM_OPS, self._factor)

    def _factor(self) -> Expr:
        return self._binary_level(_FACTOR_OPS, self._unary)

    def _binary_level(self, operators, next_level) -> Expr:
        expr = next_level()
        while self.peek().type in operators:
            op = self.advance()
            right = next_level()
            expr = Binary(expr, op.type, right, line=op.line, column=op.column)
        return expr
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_parser.py -v`
Expected: PASS, 17 passed. Full suite: 72 passed.

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/parser.py tests/test_parser.py
git commit -m "feat(parser): binary precedence ladder — * sits below + in the tree"
```

---

### Task 4: Simple statements and Program

**Files:**
- Modify: `src/matrixlang/parser.py`, `tests/test_parser.py`

**Interfaces:**
- Consumes: statement nodes from Task 1
- Produces: `parse(tokens: list[Token]) -> Program`. Internal: `parse_program`, `_statement` dispatch, `_declare`/`_assign`/`_trace`, `_skip_blank_lines` (Task 5 replaces it), `_end_statement` (Task 5 teaches it about comments).

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_parser.py` (add `parse` to the parser import; add `Assign, Declare, Program, Trace` to the nodes import):

```python
def program(source):
    return parse(lex(source))


def test_declare_statement():
    assert program("construct x = 5\n") == Program([Declare("x", NumberLiteral(5))])


def test_assign_and_trace():
    tree = program("x = x + 1\ntrace x\n")
    assert tree.statements == [
        Assign("x", Binary(Name("x"), TokenType.PLUS, NumberLiteral(1))),
        Trace(Name("x")),
    ]


def test_blank_lines_are_skipped():
    assert program("\n\ntrace 1\n\n") == Program([Trace(NumberLiteral(1))])


def test_empty_source_is_an_empty_program():
    assert program("") == Program([])


def test_statement_positions_point_at_the_keyword():
    statement = program("  trace 1\n").statements[0]
    assert (statement.line, statement.column) == (1, 3)


def test_declare_without_name_is_an_error():
    with pytest.raises(ParseError) as excinfo:
        program("construct = 5\n")
    assert "expected a name" in str(excinfo.value)


def test_bare_expression_is_not_a_statement():
    with pytest.raises(ParseError) as excinfo:
        program("x + 1\n")
    assert "expected '='" in str(excinfo.value)


def test_two_statements_on_one_line_is_an_error():
    with pytest.raises(ParseError) as excinfo:
        program("trace 1 trace 2\n")
    assert "expected end of line" in str(excinfo.value)


def test_flatline_without_a_block_is_an_error():
    with pytest.raises(ParseError) as excinfo:
        program("flatline\n")
    assert "expected a statement" in str(excinfo.value)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_parser.py -v`
Expected: FAIL — ImportError: cannot import name `parse`.

- [ ] **Step 3: Write the implementation**

In `src/matrixlang/parser.py`, extend the nodes import with `Assign, Declare, Program, Stmt, Trace`. Add above `parse_expression`:

```python
def parse(tokens: list[Token]) -> Program:
    """Parse a complete program."""
    return _Parser(tokens).parse_program()
```

Add to `_Parser`, above the expressions section:

```python
    # --- statements -------------------------------------------------------

    def parse_program(self) -> Program:
        statements: list[Stmt] = []
        while True:
            self._skip_blank_lines()
            if self.check(TokenType.EOF):
                return Program(statements)
            statements.append(self._statement())

    def _skip_blank_lines(self) -> None:
        while self.check(TokenType.NEWLINE):
            self.advance()

    def _statement(self) -> Stmt:
        token = self.peek()
        if token.type is TokenType.CONSTRUCT:
            return self._declare()
        if token.type is TokenType.TRACE:
            return self._trace()
        if token.type is TokenType.IDENT:
            return self._assign()
        raise ParseError(
            f"expected a statement, found {_describe(token)}",
            token.line,
            token.column,
        )

    def _declare(self) -> Declare:
        keyword = self.advance()
        name = self.expect(TokenType.IDENT, "expected a name after 'construct'")
        self.expect(TokenType.ASSIGN, "expected '=' after the name")
        value = self.expression()
        node = Declare(name.lexeme, value, line=keyword.line, column=keyword.column)
        self._end_statement(node)
        return node

    def _assign(self) -> Assign:
        name = self.advance()
        self.expect(TokenType.ASSIGN, "expected '=' after the name")
        value = self.expression()
        node = Assign(name.lexeme, value, line=name.line, column=name.column)
        self._end_statement(node)
        return node

    def _trace(self) -> Trace:
        keyword = self.advance()
        value = self.expression()
        node = Trace(value, line=keyword.line, column=keyword.column)
        self._end_statement(node)
        return node

    def _end_statement(self, node: Stmt) -> None:
        """Consume the statement's line ending. Task 5 teaches it about
        trailing comments."""
        self.expect(TokenType.NEWLINE, "expected end of line after the statement")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_parser.py -v`
Expected: PASS, 26 passed. Full suite: 81 passed.

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/parser.py tests/test_parser.py
git commit -m "feat(parser): construct, assignment and trace statements under parse()"
```

---

### Task 5: Comment trivia

**Files:**
- Modify: `src/matrixlang/parser.py`, `tests/test_parser.py`

**Interfaces:**
- Consumes: Task 4's statement machinery
- Produces: no new public names. `_skip_blank_lines` is **replaced** by `_collect_leading() -> list[str]`; `_end_statement` now captures a trailing comment; `parse_program` attaches leading comments and Program trailing comments. D-06 becomes real here.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_parser.py`:

```python
def test_leading_comments_attach_to_the_next_statement():
    tree = program("# a\n# b\ntrace 1\n")
    assert tree.statements[0].leading_comments == ["# a", "# b"]


def test_trailing_comment_attaches_to_its_statement():
    tree = program("trace 1  # loud\n")
    assert tree.statements[0].trailing_comment == "# loud"


def test_comments_after_the_last_statement_belong_to_the_program():
    tree = program("trace 1\n# end\n")
    assert tree.trailing_comments == ["# end"]


def test_comment_only_source():
    assert program("# ghost\n") == Program([], trailing_comments=["# ghost"])


def test_blank_lines_between_comments_and_statement_do_not_detach_them():
    tree = program("# a\n\ntrace 1\n")
    assert tree.statements[0].leading_comments == ["# a"]


def test_trivia_changes_equality():
    # The whole point of D-06: dropping a comment must break AST equality.
    assert program("trace 1\n") != program("trace 1  # hi\n")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_parser.py -v`
Expected: the six new tests FAIL — a COMMENT at statement position raises "expected a statement".

- [ ] **Step 3: Write the implementation**

In `_Parser`, replace `parse_program` and `_skip_blank_lines` (delete the latter) with:

```python
    def parse_program(self) -> Program:
        statements: list[Stmt] = []
        while True:
            leading = self._collect_leading()
            if self.check(TokenType.EOF):
                return Program(statements, trailing_comments=leading)
            statement = self._statement()
            statement.leading_comments = leading
            statements.append(statement)

    def _collect_leading(self) -> list[str]:
        """Blank lines and full-line comments before a statement position."""
        comments: list[str] = []
        while True:
            if self.check(TokenType.NEWLINE):
                self.advance()
                continue
            if self.check(TokenType.COMMENT):
                comments.append(self.advance().lexeme)
                self.expect(TokenType.NEWLINE, "expected end of line after comment")
                continue
            return comments
```

Replace `_end_statement` with:

```python
    def _end_statement(self, node: Stmt) -> None:
        if self.check(TokenType.COMMENT):
            node.trailing_comment = self.advance().lexeme
        self.expect(TokenType.NEWLINE, "expected end of line after the statement")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_parser.py -v`
Expected: PASS, 32 passed. Full suite: 87 passed.

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/parser.py tests/test_parser.py
git commit -m "feat(parser): preserve comments as AST trivia (D-06)"
```

---

### Task 6: redpill / bluepill / flatline

**Files:**
- Modify: `src/matrixlang/parser.py`, `tests/test_parser.py`

**Interfaces:**
- Consumes: `If` node; `_collect_leading`, `_end_statement` from Task 5
- Produces: `_if()`, plus shared block machinery Task 7 reuses: `_body(*closers) -> tuple[list[Stmt], list[str]]`, `_end_header() -> str | None`, module-level `_adopt_header_comment(comment, body, trailing)`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_parser.py` (add `If` to the nodes import):

```python
def test_if_without_else():
    tree = program("redpill x == 1\n  trace x\nflatline\n")
    assert tree.statements == [
        If(
            Binary(Name("x"), TokenType.EQ, NumberLiteral(1)),
            [Trace(Name("x"))],
            None,
        )
    ]


def test_if_with_else():
    branch = program(
        "redpill x\n  trace 1\nbluepill\n  trace 2\nflatline\n"
    ).statements[0]
    assert branch.then_body == [Trace(NumberLiteral(1))]
    assert branch.else_body == [Trace(NumberLiteral(2))]


def test_nested_ifs():
    source = "redpill x\n  redpill y\n    trace 1\n  flatline\nflatline\n"
    outer = program(source).statements[0]
    inner = outer.then_body[0]
    assert isinstance(inner, If)
    assert inner.then_body == [Trace(NumberLiteral(1))]


def test_empty_bodies_are_legal():
    branch = program("redpill x\nbluepill\nflatline\n").statements[0]
    assert branch.then_body == []
    assert branch.else_body == []


def test_missing_flatline_reports_end_of_input():
    with pytest.raises(ParseError) as excinfo:
        program("redpill x\n  trace 1\n")
    assert "flatline" in str(excinfo.value)


def test_header_comment_normalizes_into_the_body():
    branch = program("redpill x  # why\n  trace 1\nflatline\n").statements[0]
    assert branch.then_body[0].leading_comments == ["# why"]


def test_comment_on_the_flatline_line_trails_the_whole_if():
    branch = program("redpill x\n  trace 1\nflatline  # done\n").statements[0]
    assert branch.trailing_comment == "# done"


def test_dangling_comments_before_flatline_are_kept():
    branch = program("redpill x\n  trace 1\n  # tail\nflatline\n").statements[0]
    assert branch.then_trailing == ["# tail"]


def test_bluepill_outside_redpill_is_an_error():
    with pytest.raises(ParseError):
        program("bluepill\n")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_parser.py -v`
Expected: the new tests FAIL — `redpill` raises "expected a statement".

- [ ] **Step 3: Write the implementation**

Add `If` to the parser's nodes import. Add a module-level helper below `_describe`:

```python
def _adopt_header_comment(
    comment: str | None, body: list, trailing: list[str]
) -> None:
    """A comment on a block-header line normalizes into the block's body.

    Lossless at AST level: the text survives in the tree and re-parses
    equal; only its line placement is normalized by a render.
    """
    if comment is None:
        return
    if body:
        body[0].leading_comments.insert(0, comment)
    else:
        trailing.insert(0, comment)
```

In `_statement`, add the dispatch line before the IDENT case:

```python
        if token.type is TokenType.REDPILL:
            return self._if()
```

Add to `_Parser`, after `_trace`:

```python
    def _if(self) -> If:
        keyword = self.advance()
        condition = self.expression()
        header_comment = self._end_header()
        then_body, then_trailing = self._body(
            TokenType.BLUEPILL, TokenType.FLATLINE
        )
        _adopt_header_comment(header_comment, then_body, then_trailing)
        else_body: list[Stmt] | None = None
        else_trailing: list[str] = []
        if self.check(TokenType.BLUEPILL):
            self.advance()
            else_header = self._end_header()
            else_body, else_trailing = self._body(TokenType.FLATLINE)
            _adopt_header_comment(else_header, else_body, else_trailing)
        self.expect(TokenType.FLATLINE, "expected 'flatline' to close 'redpill'")
        node = If(
            condition,
            then_body,
            else_body,
            line=keyword.line,
            column=keyword.column,
            then_trailing=then_trailing,
            else_trailing=else_trailing,
        )
        self._end_statement(node)
        return node

    def _end_header(self) -> str | None:
        """Line ending after a block header; returns its trailing comment."""
        comment = None
        if self.check(TokenType.COMMENT):
            comment = self.advance().lexeme
        self.expect(TokenType.NEWLINE, "expected end of line")
        return comment

    def _body(self, *closers: TokenType) -> tuple[list[Stmt], list[str]]:
        """Statements until a closer keyword. Returns (statements, dangling
        comments collected after the last statement)."""
        statements: list[Stmt] = []
        while True:
            leading = self._collect_leading()
            if self.peek().type in closers or self.check(TokenType.EOF):
                return statements, leading
            statement = self._statement()
            statement.leading_comments = leading
            statements.append(statement)
```

(When a body runs into EOF, the caller's `expect(FLATLINE, ...)` raises with "found end of input" at the EOF position — that is `test_missing_flatline_reports_end_of_input`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_parser.py -v`
Expected: PASS, 41 passed. Full suite: 96 passed.

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/parser.py tests/test_parser.py
git commit -m "feat(parser): redpill/bluepill/flatline blocks with comment adoption"
```

---

### Task 7: dejavu, and the whole language end to end

**Files:**
- Modify: `src/matrixlang/parser.py`, `tests/test_parser.py`

**Interfaces:**
- Consumes: `While` node; `_body`, `_end_header`, `_adopt_header_comment` from Task 6
- Produces: `_while()`. After this task the parser covers the full §4 grammar.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_parser.py` (add `While` to the nodes import, and `from pathlib import Path` at the top):

```python
def test_while_loop():
    loop = program("dejavu n < 3\n  n = n + 1\nflatline\n").statements[0]
    assert loop == While(
        Binary(Name("n"), TokenType.LT, NumberLiteral(3)),
        [Assign("n", Binary(Name("n"), TokenType.PLUS, NumberLiteral(1)))],
    )


def test_while_missing_flatline_names_dejavu():
    with pytest.raises(ParseError) as excinfo:
        program("dejavu true\n  trace 1\n")
    assert "dejavu" in str(excinfo.value)


def test_bluepill_inside_while_is_an_error():
    with pytest.raises(ParseError):
        program("dejavu true\nbluepill\nflatline\n")


def test_if_nested_in_while():
    loop = program(
        "dejavu x < 3\n"
        "  redpill x == 1\n"
        "    trace x\n"
        "  flatline\n"
        "  x = x + 1\n"
        "flatline\n"
    ).statements[0]
    assert [type(s).__name__ for s in loop.body] == ["If", "Assign"]


def test_hello_rain_parses_end_to_end():
    source = (Path(__file__).parent.parent / "examples" / "hello.rain").read_text(
        encoding="utf-8"
    )
    tree = program(source)
    assert [type(s).__name__ for s in tree.statements] == [
        "Declare",
        "Declare",
        "While",
    ]
    assert tree.statements[0].leading_comments == [
        "# The Stage 3 demo. Lexes today; runs once the interpreter lands."
    ]
    loop = tree.statements[2]
    assert [type(s).__name__ for s in loop.body] == ["If", "Assign"]
    branch = loop.body[0]
    assert branch.else_body is not None
    concat = branch.then_body[0].value
    assert isinstance(concat, Binary)
    assert concat.op is TokenType.PLUS
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_parser.py -v`
Expected: the new tests FAIL — `dejavu` raises "expected a statement".

- [ ] **Step 3: Write the implementation**

Add `While` to the parser's nodes import. In `_statement`, add before the IDENT case:

```python
        if token.type is TokenType.DEJAVU:
            return self._while()
```

Add to `_Parser`, after `_if`:

```python
    def _while(self) -> While:
        keyword = self.advance()
        condition = self.expression()
        header_comment = self._end_header()
        body, body_trailing = self._body(TokenType.FLATLINE)
        _adopt_header_comment(header_comment, body, body_trailing)
        self.expect(TokenType.FLATLINE, "expected 'flatline' to close 'dejavu'")
        node = While(
            condition,
            body,
            line=keyword.line,
            column=keyword.column,
            body_trailing=body_trailing,
        )
        self._end_statement(node)
        return node
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_parser.py -v`
Expected: PASS, 46 passed. Full suite: 101 passed.

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/parser.py tests/test_parser.py
git commit -m "feat(parser): dejavu loops — the full grammar now parses"
```

---

### Task 8: Tree view, CLI parse subcommand, docs

**Files:**
- Create: `src/matrixlang/treeview.py`, `tests/test_treeview.py`
- Modify: `src/matrixlang/cli.py`, `tests/test_cli.py`, `README.md`, `src/matrixlang/__init__.py`, `pyproject.toml`

**Interfaces:**
- Consumes: `parse`, nodes, `format_tree`
- Produces: `format_tree(program: Program) -> str`; CLI `matrixlang parse <file>`; shared `_read_source(path) -> str | None` used by both file subcommands. Version bumps to 0.2.0.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_treeview.py`:

```python
from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.treeview import format_tree


def test_if_else_and_comments_render():
    source = (
        "# intro\n"
        "redpill true\n"
        "  trace 1  # then side\n"
        "bluepill\n"
        "  trace 2\n"
        "flatline\n"
    )
    assert format_tree(parse(lex(source))) == (
        "Program\n"
        "  # intro\n"
        "  If\n"
        "    condition:\n"
        "      BoolLiteral true\n"
        "    then:\n"
        "      Trace  # then side\n"
        "        NumberLiteral 1\n"
        "    else:\n"
        "      Trace\n"
        "        NumberLiteral 2\n"
    )
```

Append to `tests/test_cli.py`:

```python
def test_parse_prints_the_tree(source_file, capsys):
    exit_code = main(["parse", source_file("x = 2 + 3 * 4\n")])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == (
        "Program\n"
        "  Assign 'x'\n"
        "    Binary +\n"
        "      NumberLiteral 2\n"
        "      Binary *\n"
        "        NumberLiteral 3\n"
        "        NumberLiteral 4\n"
    )


def test_parse_reports_errors_and_exits_one(source_file, capsys):
    exit_code = main(["parse", source_file("construct = 5\n")])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "line 1" in captured.err


def test_parse_missing_file_exits_two(capsys, tmp_path):
    assert main(["parse", str(tmp_path / "nope.rain")]) == 2


def test_lex_still_works_after_the_read_refactor(source_file, capsys):
    assert main(["lex", source_file("x = 1\n")]) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_treeview.py tests/test_cli.py -v`
Expected: FAIL — no module `matrixlang.treeview`; `parse` is not a known subcommand (argparse SystemExit 2).

- [ ] **Step 3: Write the implementation**

Create `src/matrixlang/treeview.py`:

```python
"""Indented text view of a MatrixLang syntax tree.

Presentation only: nothing here participates in parsing or in the Stage 4
round-trip. This output is the Stage 2 teaching artifact — the shape of
the tree IS the precedence lesson.
"""

from matrixlang.nodes import (
    Assign,
    Binary,
    BoolLiteral,
    Declare,
    Expr,
    If,
    Name,
    NumberLiteral,
    Program,
    Stmt,
    StringLiteral,
    Trace,
    Unary,
    While,
)
from matrixlang.tokens import TokenType

_OPS: dict[TokenType, str] = {
    TokenType.PLUS: "+",
    TokenType.MINUS: "-",
    TokenType.STAR: "*",
    TokenType.SLASH: "/",
    TokenType.EQ: "==",
    TokenType.NEQ: "!=",
    TokenType.LT: "<",
    TokenType.GT: ">",
    TokenType.LTE: "<=",
    TokenType.GTE: ">=",
}


def format_tree(program: Program) -> str:
    lines: list[str] = ["Program"]
    for statement in program.statements:
        _statement(statement, 1, lines)
    for comment in program.trailing_comments:
        lines.append("  " + comment)
    return "\n".join(lines) + "\n"


def _statement(stmt: Stmt, depth: int, lines: list[str]) -> None:
    pad = "  " * depth
    for comment in stmt.leading_comments:
        lines.append(pad + comment)
    tail = f"  {stmt.trailing_comment}" if stmt.trailing_comment else ""
    if isinstance(stmt, Declare):
        lines.append(f"{pad}Declare '{stmt.name}'{tail}")
        _expression(stmt.value, depth + 1, lines)
    elif isinstance(stmt, Assign):
        lines.append(f"{pad}Assign '{stmt.name}'{tail}")
        _expression(stmt.value, depth + 1, lines)
    elif isinstance(stmt, Trace):
        lines.append(f"{pad}Trace{tail}")
        _expression(stmt.value, depth + 1, lines)
    elif isinstance(stmt, If):
        lines.append(f"{pad}If{tail}")
        lines.append(f"{pad}  condition:")
        _expression(stmt.condition, depth + 2, lines)
        lines.append(f"{pad}  then:")
        for child in stmt.then_body:
            _statement(child, depth + 2, lines)
        for comment in stmt.then_trailing:
            lines.append(f"{pad}    {comment}")
        if stmt.else_body is not None:
            lines.append(f"{pad}  else:")
            for child in stmt.else_body:
                _statement(child, depth + 2, lines)
            for comment in stmt.else_trailing:
                lines.append(f"{pad}    {comment}")
    elif isinstance(stmt, While):
        lines.append(f"{pad}While{tail}")
        lines.append(f"{pad}  condition:")
        _expression(stmt.condition, depth + 2, lines)
        lines.append(f"{pad}  body:")
        for child in stmt.body:
            _statement(child, depth + 2, lines)
        for comment in stmt.body_trailing:
            lines.append(f"{pad}    {comment}")


def _expression(expr: Expr, depth: int, lines: list[str]) -> None:
    pad = "  " * depth
    if isinstance(expr, NumberLiteral):
        lines.append(f"{pad}NumberLiteral {expr.value}")
    elif isinstance(expr, StringLiteral):
        lines.append(f"{pad}StringLiteral {expr.value!r}")
    elif isinstance(expr, BoolLiteral):
        lines.append(f"{pad}BoolLiteral {str(expr.value).lower()}")
    elif isinstance(expr, Name):
        lines.append(f"{pad}Name '{expr.ident}'")
    elif isinstance(expr, Unary):
        lines.append(f"{pad}Unary {_OPS[expr.op]}")
        _expression(expr.operand, depth + 1, lines)
    elif isinstance(expr, Binary):
        lines.append(f"{pad}Binary {_OPS[expr.op]}")
        _expression(expr.left, depth + 1, lines)
        _expression(expr.right, depth + 1, lines)
```

In `src/matrixlang/cli.py`:

1. Add imports: `from matrixlang.parser import parse` and `from matrixlang.treeview import format_tree`.
2. Add the subparser after the `lex` one:

```python
    parse_parser = subcommands.add_parser(
        "parse", help="Print the syntax tree for a source file."
    )
    parse_parser.add_argument("path", help="Path to a .rain source file.")
```

3. In `main`'s dispatch, add after the `lex` case:

```python
    if args.command == "parse":
        return _command_parse(args.path)
```

4. Add the shared reader and the command, and refactor `_command_lex` to use it (its behaviour is already pinned by tests):

```python
def _read_source(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"matrixlang: {error}", file=sys.stderr)
        return None


def _command_parse(path: str) -> int:
    source = _read_source(path)
    if source is None:
        return 2
    try:
        tree = parse(lex(source))
    except MatrixLangError as error:
        print(f"matrixlang: {error}", file=sys.stderr)
        return 1
    print(format_tree(tree), end="")
    return 0
```

`_command_lex` becomes:

```python
def _command_lex(path: str) -> int:
    source = _read_source(path)
    if source is None:
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

`_PENDING` keeps only `run`, `repl`, `render`.

5. Version bump: `__version__ = "0.2.0"` in `src/matrixlang/__init__.py` and `version = "0.2.0"` in `pyproject.toml`.

6. `README.md` updates (the Stage 1 final review's lesson — keep Task-1-era files true):
   - Status section: change to `Stage 2 — parser. The full grammar parses to a syntax tree.`
   - Usage section: add below the lex line:

```markdown
```bash
.venv/bin/matrixlang parse examples/hello.rain
```

Prints the syntax tree as indented text — the tree's shape is the precedence lesson.
```

   - Development section: add at the end:

```markdown
If `import matrixlang` fails with `ModuleNotFoundError` after setup, run
`chflags -R nohidden .venv` — some macOS systems intermittently set a hidden
flag on venv files, which Python ≥3.14 silently skips when processing `.pth`
files.
```

- [ ] **Step 4: Run tests and the real CLI**

```bash
.venv/bin/python -m pytest -v
.venv/bin/matrixlang parse examples/hello.rain
```

Expected: 106 passed. The parse command prints the hello.rain tree and exits 0.

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/treeview.py src/matrixlang/cli.py src/matrixlang/__init__.py pyproject.toml README.md tests/test_treeview.py tests/test_cli.py
git commit -m "feat(cli): matrixlang parse prints the syntax tree; version 0.2.0"
```

---

## Self-Review

**Grammar coverage (language spec §4):** program → T4/T5; declare/assign/trace → T4; if → T6; while → T7; equality/comparison/term/factor → T3; unary/primary → T2. Every production has a task.

**D-06 / §6.1 coverage:** leading → T5; trailing → T5; Program.trailing_comments → T5; per-body dangling and header adoption → T6. The §6.1 spec amendment (positions excluded from equality) → T1 Step 4.

**Parent-spec Stage 2 done-when:** `test_multiplication_binds_tighter_than_addition`, T3.

**Type consistency spot-checks:** `Name.ident` (not `.name`) everywhere including treeview; `If(condition, then_body, else_body=None, *, then_trailing, else_trailing)` construction order matches T1's dataclass in T6's `_if`; `parse`/`parse_expression` signatures consistent across T2/T4/T8 imports.

**Known intentional choices (do not "fix" during implementation):** no Grouping node; parser performs no semantic checks; `parse_expression` discards a trailing comment; `_binary_level` is shared while the ladder's levels stay named; treeview is isinstance-dispatch, not a visitor — Stage 3 can introduce a visitor if the interpreter wants one, YAGNI today.

**Deliberately out of scope:** evaluation (Stage 3), rendering back to source (Stage 4), `else if` chains (spec §9 defers them), logical operators (spec §9).
