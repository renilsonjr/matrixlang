# Stage 7 Lists Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give MatrixLang one mutable list type with literals, indexing, element assignment, `+` concatenation, and a `length` keyword — so a program can hold more than one value.

**Architecture:** Three new tokens (`[`, `]`, `length`) and three new AST nodes (`ListLiteral`, `Index`, `IndexAssign`). `length` reuses the existing `Unary` node. Indexing joins the postfix loop in `parser._call()` that already handles `f()()`. The one genuinely new piece of logic is `values.equal()` — a recursive structural comparison that carries the language's own type rules and a cycle seen-set, replacing a delegation to Python's `==` that silently breaks the `bool`-is-not-an-`int` rule at every level below the surface.

**Tech Stack:** Python ≥3.11, standard library only. pytest for tests.

**Spec:** `docs/superpowers/specs/2026-08-01-stage-7-lists-design.md` (approved, PR #41). Issue #40.

## Global Constraints

Every task's requirements implicitly include all of these.

- **Python ≥3.11.** No third-party runtime dependencies. `pytest` is the only dev dependency.
- **Value type checks use `type(v) is X`, never `isinstance`.** `isinstance(True, int)` is `True`, and the whole of Task 8 exists because that trap re-enters through lists. `isinstance` on *AST node* types is correct and used freely — the ban is on value checks only.
- **Every error carries a line and a column.** Raised as a `MatrixLangError` subclass.
- **`values.py` may import nothing.** `tests/test_architecture.py:23` pins `"values": set()`. See the Deviation note below.
- **Only `glyphs.py` may contain a half-width katakana literal.** `tests/test_architecture.py` enforces this. Tests are exempt.
- **The round-trip criterion is non-negotiable:** `parse(render_glyph(t)) == parse(render_ascii(t)) == t`.
- **Baseline: 1,023 tests pass on `main`** before this plan begins. No task may reduce that number.
- **macOS venv quirk:** if any command reports `ModuleNotFoundError: No module named 'matrixlang'`, run `chflags -R nohidden .venv` and retry. This is a platform quirk, not a code failure.

### Deviation from the spec, and why

Spec §6.1 says *"A dedicated `equal(a, b)` in `values.py`, so the rule stays auditable in one place."* That is kept — but the spec did not account for `values.py` being allow-listed to import **nothing**, so `equal` cannot raise a positioned `RuntimeErrorML`.

Resolution: `values.py` defines its own `Incomparable` and `CyclicValue` exceptions locally (a bare `class X(Exception)` needs no import) and the **interpreter** catches them and attaches the line and column. This is principled rather than a workaround — `values.py` has never had access to a source position, so it was never in a position to raise a positioned error. The rule still lives in one auditable place; only the reporting moved to the module that knows where the program is.

### Glyph assignments

| Slot | Glyph | Codepoint |
| --- | --- | --- |
| `[` | `ﾍ` | U+FF8D |
| `]` | `ﾎ` | U+FF8E |
| `length` | `ﾙ` | U+FF99 |

`ﾍ`/`ﾎ` are adjacent, mirroring `(`→`ｸ` (U+FF78) and `)`→`ｹ` (U+FF79). Verified free. Table goes 35 → 38, leaving 18.

---

## File Structure

| File | Change | Responsibility after |
| --- | --- | --- |
| `src/matrixlang/tokens.py` | Modify | Adds `LBRACKET`, `RBRACKET`, `LENGTH` and the `length` keyword entry |
| `src/matrixlang/glyphs.py` | Modify | 38 slots |
| `src/matrixlang/lexer.py` | Modify | Two `_SINGLE` entries. The glyph path builds itself from `GLYPHS` |
| `src/matrixlang/nodes.py` | Modify | Adds `ListLiteral`, `Index`, `IndexAssign` |
| `src/matrixlang/parser.py` | Modify | List literals in `_primary`, indexing in `_call`, `length` in `_unary`, lvalues in `_statement` |
| `src/matrixlang/render.py` | Modify | Three new emit cases and one new statement case |
| `src/matrixlang/treeview.py` | Modify | Three new node cases |
| `src/matrixlang/values.py` | Modify | `is_list`, `type_name`, `to_display`, and the new `equal` + two local exceptions |
| `src/matrixlang/interpreter.py` | Modify | Evaluates the new nodes, `+` on lists, and converts the two `values` exceptions |
| `tests/treegen.py` | Modify | Generates `ListLiteral` and `Index` |
| `tests/test_lists_lex.py` | Create | Task 1 |
| `tests/test_lists_parse.py` | Create | Tasks 2–5 |
| `tests/test_lists_render.py` | Create | Tasks 2–5 |
| `tests/test_lists_run.py` | Create | Tasks 9–10 |
| `tests/test_values.py` | Modify | Tasks 7–8 |
| `tests/test_roundtrip.py` | Modify | Task 6 |
| `tests/test_treeview.py` | Modify | Tasks 2–5 |

Test files are split by **stage of the pipeline**, matching how `test_functions_parse.py` / `test_functions_render.py` / `test_functions_run.py` were split for Stage 6. Follow that precedent rather than inventing a new layout.

---

## Task 1: Vocabulary — tokens, glyphs, lexer

**Files:**
- Modify: `src/matrixlang/tokens.py:42-44` (punctuation block), `:52-63` (KEYWORDS)
- Modify: `src/matrixlang/glyphs.py:40-42` (punctuation block), `:22-26` (keywords)
- Modify: `src/matrixlang/lexer.py:9-20` (`_SINGLE`)
- Test: `tests/test_lists_lex.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `TokenType.LBRACKET`, `TokenType.RBRACKET`, `TokenType.LENGTH`. `GLYPHS["["] == "ﾍ"`, `GLYPHS["]"] == "ﾎ"`, `GLYPHS["length"] == "ﾙ"`. Every later task depends on these names.

- [ ] **Step 1: Write the failing test**

Create `tests/test_lists_lex.py`:

```python
"""Stage 7 — the three new lexical units, in both faces.

The glyph path is not hand-written: lexer._GLYPH_TOKENS builds itself by
walking GLYPHS and looking each slot up in KEYWORDS/_DOUBLE/_SINGLE. So
adding the slots is what makes the glyph face work, and these tests are
what prove that machinery actually covered the new entries.
"""

import pytest

from matrixlang.glyphs import GLYPHS
from matrixlang.lexer import lex
from matrixlang.tokens import TokenType


def types(source):
    return [t.type for t in lex(source) if t.type is not TokenType.NEWLINE]


def test_brackets_lex_in_the_ascii_face():
    assert types("[]") == [
        TokenType.LBRACKET,
        TokenType.RBRACKET,
        TokenType.EOF,
    ]


def test_brackets_lex_in_the_glyph_face():
    assert types(GLYPHS["["] + GLYPHS["]"]) == [
        TokenType.LBRACKET,
        TokenType.RBRACKET,
        TokenType.EOF,
    ]


def test_length_is_a_keyword_not_an_identifier():
    # If `length` were left out of KEYWORDS it would lex as IDENT and the
    # parser would report a baffling error two stages from the cause.
    assert types("length") == [TokenType.LENGTH, TokenType.EOF]


def test_length_lexes_in_the_glyph_face():
    assert types(GLYPHS["length"]) == [TokenType.LENGTH, TokenType.EOF]


def test_a_mixed_face_list_lexes():
    # Mixed-face source is a tested property of this language, not an
    # accident: glyphs and ASCII occupy disjoint alphabets.
    assert types("[1" + GLYPHS["]"]) == [
        TokenType.LBRACKET,
        TokenType.NUMBER,
        TokenType.RBRACKET,
        TokenType.EOF,
    ]


def test_an_identifier_starting_with_length_is_still_an_identifier():
    assert types("lengths") == [TokenType.IDENT, TokenType.EOF]


@pytest.mark.parametrize("slot", ["[", "]", "length"])
def test_each_new_slot_has_a_glyph(slot):
    assert slot in GLYPHS
    assert len(GLYPHS[slot]) == 1


def test_the_table_is_still_bijective():
    assert len(set(GLYPHS.values())) == len(GLYPHS) == 38
```

- [ ] **Step 2: Run the test to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_lists_lex.py -q
```

Expected: FAIL — `AttributeError: LBRACKET` and `KeyError: '['`.

- [ ] **Step 3: Add the token types**

In `src/matrixlang/tokens.py`, in the `# Keywords` block after `JACKOUT = auto()`:

```python
    LENGTH = auto()
```

In the `# Punctuation` block after `COMMA = auto()`:

```python
    LBRACKET = auto()
    RBRACKET = auto()
```

In `KEYWORDS`, after the `"jackout"` entry:

```python
    "length": TokenType.LENGTH,
```

- [ ] **Step 4: Add the glyphs**

In `src/matrixlang/glyphs.py`, after the `"jackout": "ﾖ",` line:

```python
    # Stage 7. A keyword rather than a built-in `length(xs)`: a built-in
    # name is an identifier, so it would be the first piece of the
    # language surface rendered in Latin in the glyph face, and D-03's
    # claim is that the only readable text in a wall of green is the
    # thing you wrote.
    "length": "ﾙ",
```

In the `# punctuation` block, after the `",": "ﾈ",` line:

```python
    # Adjacent, mirroring ( and ) which are adjacent too.
    "[": "ﾍ",
    "]": "ﾎ",
```

Update the module docstring's first line from `"""The 35-slot glyph table` to `"""The 38-slot glyph table`.

- [ ] **Step 5: Add the lexer entries**

In `src/matrixlang/lexer.py`, in `_SINGLE`, after the `",": TokenType.COMMA,` line:

```python
    "[": TokenType.LBRACKET,
    "]": TokenType.RBRACKET,
```

Nothing else in the lexer changes. `_GLYPH_TOKENS` is built by walking `GLYPHS` and looking each slot up in `KEYWORDS`, `_DOUBLE`, then `_SINGLE` — so both new punctuation glyphs and the `length` glyph are picked up automatically.

- [ ] **Step 6: Run the new tests and the full suite**

```bash
.venv/bin/python -m pytest tests/test_lists_lex.py -q
```

Expected: PASS.

```bash
.venv/bin/python -m pytest -q
```

Expected: FAIL in `tests/test_glyphs.py` — `test_the_table_covers_exactly_the_35_slots` pins the count at `tests/test_glyphs.py:7` and `:20`. Rename it to `test_the_table_covers_exactly_the_38_slots`, add `"["`, `"]"` and `"length"` to its `expected` set, and change `assert len(expected) == 35` to `38`. **Do not weaken the assertion to a range** — the exact number is the point of the test.

Re-run until green.

- [ ] **Step 7: Commit**

```bash
git add src/matrixlang/tokens.py src/matrixlang/glyphs.py src/matrixlang/lexer.py tests/
git commit -m "feat: the Stage 7 vocabulary — brackets and 'length', in both faces"
```

---

## Task 2: List literals — parse, render, treeview

**Files:**
- Modify: `src/matrixlang/nodes.py` (after `Call`), `src/matrixlang/parser.py:394-416` (`_primary`), `src/matrixlang/render.py` (`_emit`), `src/matrixlang/treeview.py` (`_expression`)
- Test: `tests/test_lists_parse.py`, `tests/test_lists_render.py` (create), `tests/test_treeview.py` (modify)

**Interfaces:**
- Consumes: `TokenType.LBRACKET`, `TokenType.RBRACKET` from Task 1.
- Produces: `ListLiteral(elements: list[Expr])`. Tasks 3, 5, 6 and 9 all construct this node.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_lists_parse.py`:

```python
"""Stage 7 — parsing lists, indexing, length and element assignment."""

import pytest

from matrixlang.errors import ParseError
from matrixlang.lexer import lex
from matrixlang.nodes import (
    Binary,
    Index,
    ListLiteral,
    Name,
    NumberLiteral,
    StringLiteral,
)
from matrixlang.parser import parse
from matrixlang.tokens import TokenType


def first(source):
    return parse(lex(source)).statements[0]


def test_an_empty_list_parses():
    assert first("construct xs = []\n").value == ListLiteral([])


def test_a_list_of_numbers_parses():
    assert first("construct xs = [1, 2]\n").value == ListLiteral(
        [NumberLiteral(1), NumberLiteral(2)]
    )


def test_a_trailing_element_is_required_after_a_comma():
    with pytest.raises(ParseError) as caught:
        first("construct xs = [1, ]\n")
    assert "expected an expression" in caught.value.message


def test_an_unclosed_list_reports_the_bracket():
    with pytest.raises(ParseError) as caught:
        first("construct xs = [1\n")
    assert "']'" in caught.value.message


def test_elements_may_be_arbitrary_expressions():
    assert first("construct xs = [1 + 2]\n").value == ListLiteral(
        [Binary(NumberLiteral(1), TokenType.PLUS, NumberLiteral(2))]
    )


def test_lists_nest():
    assert first("construct xs = [[1]]\n").value == ListLiteral(
        [ListLiteral([NumberLiteral(1)])]
    )


def test_elements_may_be_mixed_types():
    # Refusing this would need a type system the language does not have.
    parsed = first('construct xs = [1, "a", true]\n').value
    assert len(parsed.elements) == 3
```

Create `tests/test_lists_render.py`:

```python
"""Stage 7 — rendering lists in both faces, and the round trip.

The §4.3 criterion is what these protect: parse(render(t)) == t. A
renderer that drops a bracket or mis-levels a node fails here rather
than silently changing what a program means.
"""

import pytest

from matrixlang.glyphs import GLYPHS
from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.render import render_ascii, render_glyph


def roundtrip(source):
    tree = parse(lex(source))
    assert parse(lex(render_ascii(tree))) == tree, "ascii face"
    assert parse(lex(render_glyph(tree))) == tree, "glyph face"
    return tree


@pytest.mark.parametrize(
    "source",
    [
        "construct xs = []\n",
        "construct xs = [1]\n",
        "construct xs = [1, 2, 3]\n",
        "construct xs = [[1], [2]]\n",
        'construct xs = [1, "a", true]\n',
        "construct xs = [1 + 2, -3]\n",
    ],
)
def test_a_list_literal_round_trips(source):
    roundtrip(source)


def test_the_ascii_face_uses_brackets():
    tree = parse(lex("construct xs = [1, 2]\n"))
    assert render_ascii(tree) == "construct xs = [1, 2]\n"


def test_the_glyph_face_uses_the_bracket_glyphs():
    tree = parse(lex("construct xs = [1]\n"))
    rendered = render_glyph(tree)
    assert GLYPHS["["] in rendered
    assert GLYPHS["]"] in rendered
    assert "[" not in rendered
```

- [ ] **Step 2: Run them to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_lists_parse.py tests/test_lists_render.py -q
```

Expected: FAIL — `ImportError: cannot import name 'ListLiteral'`.

- [ ] **Step 3: Add the node**

In `src/matrixlang/nodes.py`, after the `Call` dataclass:

```python
@dataclass
class ListLiteral(Expr):
    """`[1, 2]`. Elements are their own precedence context, like Call.args."""

    elements: list[Expr]
```

- [ ] **Step 4: Parse it**

In `src/matrixlang/parser.py`, import `ListLiteral` alongside the other node imports. In `_primary`, before the final `raise ParseError`:

```python
        if token.type is TokenType.LBRACKET:
            self.advance()
            elements: list[Expr] = []
            if not self.check(TokenType.RBRACKET):
                while True:
                    elements.append(self.expression())
                    if not self.check(TokenType.COMMA):
                        break
                    self.advance()
            self.expect(TokenType.RBRACKET, "expected ']' to close the list")
            return ListLiteral(elements, line=token.line, column=token.column)
```

This mirrors the argument loop in `_call` exactly, including refusing a trailing comma — `[1, ]` runs the loop again and `expression()` reports `expected an expression`.

- [ ] **Step 5: Render it**

In `src/matrixlang/render.py`, import `ListLiteral`. In `_emit`, before the `Binary` case:

```python
    if isinstance(expr, ListLiteral):
        # Elements render from level 0: the brackets delimit them, so no
        # element ever needs parens for the list's sake. Same reasoning as
        # Call.args. The literal itself is an atom — [1] + [2] must never
        # come back as [1] + [2] with parens, and never as [1 + [2]].
        inner = ", ".join(_expression(e, 0, face) for e in expr.elements)
        return f"{_map(face, '[')}{inner}{_map(face, ']')}", _ATOM_LEVEL
```

- [ ] **Step 6: Add the treeview case**

In `src/matrixlang/treeview.py`, import `ListLiteral`. In `_expression`, before the fallback:

```python
    if isinstance(expr, ListLiteral):
        lines.append(f"{pad}ListLiteral ({len(expr.elements)})")
        for element in expr.elements:
            _expression(element, depth + 1, lines)
        return
```

Add to `tests/test_treeview.py`:

```python
def test_a_list_literal_has_a_treeview_case():
    # treeview.py had no case for the Stage 6 nodes and `matrixlang parse`
    # crashed on an agent while 878 tests passed. One test per new node.
    from matrixlang.lexer import lex
    from matrixlang.parser import parse
    from matrixlang.treeview import format_tree

    out = format_tree(parse(lex("construct xs = [1, 2]\n")))
    assert "ListLiteral (2)" in out
    assert "NumberLiteral 1" in out
```

- [ ] **Step 7: Run the tests**

```bash
.venv/bin/python -m pytest tests/test_lists_parse.py tests/test_lists_render.py tests/test_treeview.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/matrixlang tests/
git commit -m "feat: list literals parse, render in both faces, and round-trip"
```

---

## Task 3: Indexing — parse, render, treeview

**Files:**
- Modify: `src/matrixlang/nodes.py`, `src/matrixlang/parser.py:373-392` (`_call`), `src/matrixlang/render.py`, `src/matrixlang/treeview.py`
- Test: `tests/test_lists_parse.py`, `tests/test_lists_render.py`, `tests/test_treeview.py`

**Interfaces:**
- Consumes: `ListLiteral` (Task 2), `TokenType.LBRACKET`/`RBRACKET` (Task 1).
- Produces: `Index(target: Expr, index: Expr)`. Tasks 5, 6 and 9 use it.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_lists_parse.py`:

```python
def test_indexing_a_name_parses():
    assert first("construct a = xs[0]\n").value == Index(
        Name("xs"), NumberLiteral(0)
    )


def test_indexing_chains():
    # Nested lists are legal, so xs[0][1] must be too.
    assert first("construct a = xs[0][1]\n").value == Index(
        Index(Name("xs"), NumberLiteral(0)), NumberLiteral(1)
    )


def test_a_call_result_can_be_indexed():
    # _call is a postfix loop, so f()[0] falls out for free.
    parsed = first("construct a = f()[0]\n").value
    assert isinstance(parsed, Index)


def test_indexing_a_list_literal_parses():
    assert first("construct a = [1, 2][0]\n").value == Index(
        ListLiteral([NumberLiteral(1), NumberLiteral(2)]), NumberLiteral(0)
    )


def test_an_unclosed_index_reports_the_bracket():
    with pytest.raises(ParseError) as caught:
        first("construct a = xs[0\n")
    assert "']'" in caught.value.message


def test_an_empty_index_is_an_error():
    with pytest.raises(ParseError) as caught:
        first("construct a = xs[]\n")
    assert "expected an expression" in caught.value.message
```

Append to `tests/test_lists_render.py`:

```python
@pytest.mark.parametrize(
    "source",
    [
        "construct a = xs[0]\n",
        "construct a = xs[0][1]\n",
        "construct a = xs[n + 1]\n",
        "construct a = [1, 2][0]\n",
        "construct a = f()[0]\n",
        "construct a = -xs[0]\n",
    ],
)
def test_indexing_round_trips(source):
    roundtrip(source)


def test_indexing_binds_tighter_than_unary_minus():
    # -xs[0] is -(xs[0]), never (-xs)[0]. Rendering it as the latter
    # would be a different tree with a different meaning.
    tree = parse(lex("construct a = -xs[0]\n"))
    assert render_ascii(tree) == "construct a = -xs[0]\n"


def test_an_index_expression_keeps_its_parens_where_needed():
    tree = parse(lex("construct a = xs[n + 1]\n"))
    assert render_ascii(tree) == "construct a = xs[n + 1]\n"
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/python -m pytest tests/test_lists_parse.py -q -k index
```

Expected: FAIL — `cannot import name 'Index'`.

- [ ] **Step 3: Add the node**

In `src/matrixlang/nodes.py`, after `ListLiteral`:

```python
@dataclass
class Index(Expr):
    """`xs[0]`. Postfix, so it binds tighter than every operator — see
    render.py's _CALL_LEVEL, which this shares for exactly that reason."""

    target: Expr
    index: Expr
```

- [ ] **Step 4: Parse it**

In `src/matrixlang/parser.py`, import `Index`. Change the `while` condition in `_call` from `while self.check(TokenType.LPAREN):` to a loop that handles both suffixes:

```python
    def _call(self) -> Expr:
        """Postfix application, so a call or an index binds tighter than
        any operator.

        Loops rather than recurses so `f()()` is a call on a call and
        `xs[0][1]` is an index of an index. Nothing reaches across a
        NEWLINE: the lexer emits one between statements, and `check` sees
        it before it sees a '(' or a '['.
        """
        expr = self._primary()
        while True:
            if self.check(TokenType.LPAREN):
                paren = self.advance()
                args: list[Expr] = []
                if not self.check(TokenType.RPAREN):
                    while True:
                        args.append(self.expression())
                        if not self.check(TokenType.COMMA):
                            break
                        self.advance()
                self.expect(TokenType.RPAREN, "expected ')' to close the arguments")
                expr = Call(expr, args, line=paren.line, column=paren.column)
            elif self.check(TokenType.LBRACKET):
                bracket = self.advance()
                index = self.expression()
                self.expect(TokenType.RBRACKET, "expected ']' to close the index")
                expr = Index(expr, index, line=bracket.line, column=bracket.column)
            else:
                return expr
```

- [ ] **Step 5: Render it**

In `src/matrixlang/render.py`, import `Index`. In `_emit`, after the `Call` case:

```python
    if isinstance(expr, Index):
        # _CALL_LEVEL for the target for the same reason a call uses it:
        # the suffix binds tighter than every operator, so a looser target
        # needs parens. The index itself renders from 0 — the brackets
        # delimit it, exactly like call arguments.
        target = _expression(expr.target, _CALL_LEVEL, face)
        inner = _expression(expr.index, 0, face)
        return (
            f"{target}{_map(face, '[')}{inner}{_map(face, ']')}",
            _CALL_LEVEL,
        )
```

- [ ] **Step 6: Add the treeview case**

In `src/matrixlang/treeview.py`, import `Index`. In `_expression`:

```python
    if isinstance(expr, Index):
        lines.append(f"{pad}Index")
        _expression(expr.target, depth + 1, lines)
        _expression(expr.index, depth + 1, lines)
        return
```

Append to `tests/test_treeview.py`:

```python
def test_an_index_has_a_treeview_case():
    from matrixlang.lexer import lex
    from matrixlang.parser import parse
    from matrixlang.treeview import format_tree

    out = format_tree(parse(lex("construct a = xs[0]\n")))
    assert "Index" in out
    assert "Name 'xs'" in out or "'xs'" in out
```

- [ ] **Step 7: Run the tests**

```bash
.venv/bin/python -m pytest tests/test_lists_parse.py tests/test_lists_render.py tests/test_treeview.py -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/matrixlang tests/
git commit -m "feat: indexing joins the postfix loop that already ran f()()"
```

---

## Task 4: `length` — parse, render, treeview

**Files:**
- Modify: `src/matrixlang/parser.py:366-371` (`_unary`), `src/matrixlang/render.py` (`_emit` Unary case, `_OPS`), `src/matrixlang/treeview.py` (`_OPS`)
- Test: `tests/test_lists_parse.py`, `tests/test_lists_render.py`

**Interfaces:**
- Consumes: `TokenType.LENGTH` (Task 1).
- Produces: nothing new. `length xs` is `Unary(TokenType.LENGTH, Name("xs"))` — **no new AST node**.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_lists_parse.py`:

```python
def test_length_parses_as_a_unary():
    from matrixlang.nodes import Unary
    from matrixlang.tokens import TokenType

    assert first("construct n = length xs\n").value == Unary(
        TokenType.LENGTH, Name("xs")
    )


def test_length_binds_tighter_than_plus():
    # `length xs + 1` must be `(length xs) + 1`, matching `-x + 1`.
    from matrixlang.nodes import Binary, Unary
    from matrixlang.tokens import TokenType

    parsed = first("construct n = length xs + 1\n").value
    assert isinstance(parsed, Binary)
    assert isinstance(parsed.left, Unary)
    assert parsed.left.op is TokenType.LENGTH


def test_length_applies_to_an_index():
    from matrixlang.nodes import Unary

    parsed = first("construct n = length xs[0]\n").value
    assert isinstance(parsed, Unary)
    assert isinstance(parsed.operand, Index)


def test_length_of_a_parenthesised_expression_parses():
    from matrixlang.nodes import Unary

    parsed = first("construct n = length (xs + ys)\n").value
    assert isinstance(parsed, Unary)
```

Append to `tests/test_lists_render.py`:

```python
@pytest.mark.parametrize(
    "source",
    [
        "construct n = length xs\n",
        "construct n = length xs + 1\n",
        "construct n = length [1, 2]\n",
        "construct n = length xs[0]\n",
        'construct n = length "Neo"\n',
        "construct n = -length xs\n",
    ],
)
def test_length_round_trips(source):
    roundtrip(source)


def test_length_renders_with_a_space_and_keeps_precedence():
    # Unary minus renders with no space (-x); length is a WORD and needs
    # one, or `length xs` becomes `lengthxs` and re-lexes as an identifier.
    tree = parse(lex("construct n = length xs + 1\n"))
    assert render_ascii(tree) == "construct n = length xs + 1\n"


def test_length_over_a_binary_gets_parens():
    tree = parse(lex("construct n = length (xs + ys)\n"))
    assert render_ascii(tree) == "construct n = length (xs + ys)\n"
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/python -m pytest tests/test_lists_parse.py -q -k length
```

Expected: FAIL — `expected an expression, found 'length'`.

- [ ] **Step 3: Parse it**

In `src/matrixlang/parser.py`, change `_unary`:

```python
    def _unary(self) -> Expr:
        if self.check(TokenType.MINUS) or self.check(TokenType.LENGTH):
            op = self.advance()
            operand = self._unary()
            return Unary(op.type, operand, line=op.line, column=op.column)
        return self._call()
```

Note the change from the hardcoded `TokenType.MINUS` to `op.type`. Both operators now flow through one path, which is why `length` needs no node of its own.

- [ ] **Step 4: Render it**

In `src/matrixlang/render.py`, add to `_OPS`:

```python
    TokenType.LENGTH: "length",
```

Replace the `Unary` case in `_emit`:

```python
    if isinstance(expr, Unary):
        # R-PAREN-3: any binary operand is looser than _UNARY_LEVEL and
        # therefore parenthesised.
        operand = _expression(expr.operand, _UNARY_LEVEL, face)
        if expr.op is TokenType.LENGTH:
            # A word operator needs a separator or `length xs` renders as
            # `lengthxs` and re-lexes as one identifier — a silent change
            # of meaning, which is exactly what §4.3 exists to catch.
            return _map(face, "length") + " " + operand, _UNARY_LEVEL
        return _map(face, "-") + operand, _UNARY_LEVEL
```

- [ ] **Step 5: Add the treeview entry**

In `src/matrixlang/treeview.py`, add to `_OPS`:

```python
    TokenType.LENGTH: "length",
```

The existing `Unary` case reads `_OPS[expr.op]`, so no other change is needed.

- [ ] **Step 6: Run the tests**

```bash
.venv/bin/python -m pytest tests/test_lists_parse.py tests/test_lists_render.py -q
```

Expected: PASS.

- [ ] **Step 7: Verify the glyph face separator by hand**

```bash
.venv/bin/python -c "
from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.render import render_glyph
print(repr(render_glyph(parse(lex('construct n = length xs\n')))))
"
```

Expected: the `length` glyph, a space, then `xs`. In the glyph face the separator is not strictly required — a glyph and a Latin identifier are already disjoint — but rendering it consistently in both faces keeps one code path.

- [ ] **Step 8: Commit**

```bash
git add src/matrixlang tests/
git commit -m "feat: 'length' as a unary operator, reusing the node -x already uses"
```

---

## Task 5: Element assignment — lvalues in the statement dispatcher

**Files:**
- Modify: `src/matrixlang/nodes.py`, `src/matrixlang/parser.py:143-172` (`_statement`), `src/matrixlang/render.py`, `src/matrixlang/treeview.py`
- Test: `tests/test_lists_parse.py`, `tests/test_lists_render.py`, `tests/test_treeview.py`

**Interfaces:**
- Consumes: `Index` (Task 3).
- Produces: `IndexAssign(target: Expr, index: Expr, value: Expr)` — a `Stmt`. Tasks 6 and 9 use it.

For `xs[0][1] = v`, `target` is `Index(Name("xs"), 0)` and `index` is `1`. The assign target is **a name followed by one or more index suffixes**; `f()[0] = v` is a parse error, because a call result is not a place and the language has nowhere else that assigns to one.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_lists_parse.py`:

```python
def test_element_assignment_parses():
    from matrixlang.nodes import IndexAssign

    stmt = first("xs[0] = 9\n")
    assert stmt == IndexAssign(Name("xs"), NumberLiteral(0), NumberLiteral(9))


def test_nested_element_assignment_parses():
    from matrixlang.nodes import IndexAssign

    stmt = first("xs[0][1] = 9\n")
    assert isinstance(stmt, IndexAssign)
    assert stmt.target == Index(Name("xs"), NumberLiteral(0))
    assert stmt.index == NumberLiteral(1)


def test_assigning_to_a_call_result_is_a_parse_error():
    with pytest.raises(ParseError) as caught:
        first("f()[0] = 9\n")
    assert "cannot assign" in caught.value.message


def test_a_bare_index_is_not_a_statement():
    # Same rule as a bare name: it computes something and throws it away,
    # which is a mistake rather than a statement.
    with pytest.raises(ParseError):
        first("xs[0]\n")


def test_plain_assignment_still_reports_the_equals_sign():
    # Regression: the IDENT dispatch must not swallow this case.
    with pytest.raises(ParseError) as caught:
        first("x + 1\n")
    assert "'='" in caught.value.message
```

Append to `tests/test_lists_render.py`:

```python
@pytest.mark.parametrize(
    "source",
    [
        "xs[0] = 9\n",
        "xs[0][1] = 9\n",
        "xs[n + 1] = a + b\n",
    ],
)
def test_element_assignment_round_trips(source):
    roundtrip(source)


def test_element_assignment_renders_in_ascii():
    tree = parse(lex("xs[0] = 9\n"))
    assert render_ascii(tree) == "xs[0] = 9\n"
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/python -m pytest tests/test_lists_parse.py -q -k assign
```

Expected: FAIL — `cannot import name 'IndexAssign'`.

- [ ] **Step 3: Add the node**

In `src/matrixlang/nodes.py`, after `Assign`:

```python
@dataclass
class IndexAssign(Stmt):
    """`xs[0] = 9`. The first statement in the language that mutates a
    VALUE rather than rebinding a NAME — which is what makes cyclic
    lists reachable. See the Stage 7 design §3."""

    target: Expr
    index: Expr
    value: Expr
```

- [ ] **Step 4: Dispatch on it**

In `src/matrixlang/parser.py`, import `IndexAssign`. Replace the `IDENT` branch of `_statement`:

```python
        if token.type is TokenType.IDENT:
            # One token of lookahead decides, and it is the suffix rather
            # than the '='. Dispatching on the paren means `x + 1` still
            # reaches _assign and still reports "expected '='", which is
            # the more useful message for what that mistake usually is.
            nxt = self._tokens[self._pos + 1].type
            if nxt is TokenType.LPAREN:
                return self._expression_statement()
            if nxt is TokenType.LBRACKET:
                return self._index_assign()
            return self._assign()
```

**Delete the duplicated unreachable `raise ParseError` block** immediately after the first one at the end of `_statement` — dead code, currently seven lines.

Add the method, next to `_assign`:

```python
    def _index_assign(self) -> IndexAssign:
        """`xs[0] = 9`, and `xs[0][1] = 9`.

        The target is a name followed by one or more index suffixes.
        Parsing it as a full postfix chain and then rejecting a Call is
        what produces a message about the real problem — a call result is
        not a place — instead of a confusing one about the '['.
        """
        start = self.peek()
        chain = self._call()
        if not isinstance(chain, Index):
            raise ParseError(
                "cannot assign to this — only a name or an element of one",
                start.line,
                start.column,
            )
        if isinstance(chain.target, Call):
            raise ParseError(
                "cannot assign to the result of a call",
                start.line,
                start.column,
            )
        self.expect(TokenType.ASSIGN, "expected '=' after the element")
        value = self.expression()
        node = IndexAssign(
            chain.target,
            chain.index,
            value,
            line=start.line,
            column=start.column,
        )
        self._end_statement(node)
        return node
```

- [ ] **Step 5: Render it**

In `src/matrixlang/render.py`, import `IndexAssign`. In `_statement`, after the `Assign` case:

```python
    elif isinstance(stmt, IndexAssign):
        target = _expression(stmt.target, _CALL_LEVEL, face)
        index = _expression(stmt.index, 0, face)
        head = (
            f"{target}{_map(face, '[')}{index}{_map(face, ']')} "
            f"{_map(face, '=')} {_expression(stmt.value, 0, face)}"
        )
        lines.append(pad + head + _trail(stmt, face))
```

- [ ] **Step 6: Add the treeview case**

In `src/matrixlang/treeview.py`, import `IndexAssign`. In `_statement`, after the `Assign` case:

```python
    elif isinstance(stmt, IndexAssign):
        lines.append(f"{pad}IndexAssign{tail}")
        _expression(stmt.target, depth + 1, lines)
        _expression(stmt.index, depth + 1, lines)
        _expression(stmt.value, depth + 1, lines)
```

Append to `tests/test_treeview.py`:

```python
def test_index_assignment_has_a_treeview_case():
    from matrixlang.lexer import lex
    from matrixlang.parser import parse
    from matrixlang.treeview import format_tree

    out = format_tree(parse(lex("xs[0] = 9\n")))
    assert "IndexAssign" in out
```

- [ ] **Step 7: Run the tests and the full suite**

```bash
.venv/bin/python -m pytest tests/ -q
```

Expected: PASS. The dead-code deletion changes no behaviour.

- [ ] **Step 8: Commit**

```bash
git add src/matrixlang tests/
git commit -m "feat: element assignment, and the lvalue dispatch it needs"
```

---

## Task 6: The generator, and the property test that must keep having teeth

**Files:**
- Modify: `tests/treegen.py:130-153` (`gen_expression`), `:164-175` (`gen_atom`), `:76-80` (`gen_statement`)
- Modify: `tests/test_roundtrip.py` (add a Stage 7 coverage meta-test)

**Interfaces:**
- Consumes: `ListLiteral`, `Index`, `IndexAssign` from Tasks 2, 3, 5.
- Produces: nothing new. The deliverable is coverage.

**Why this task is not optional.** Without it the §4.3 property test keeps passing while covering none of the new syntax. `test_the_generator_produces_the_shapes_the_parens_rules_need` exists precisely because *"a generator that stops producing the hard shapes would quietly gut the property."*

- [ ] **Step 1: Write the failing meta-test**

Append to `tests/test_roundtrip.py`:

```python
def test_the_generator_produces_the_stage_7_shapes_too():
    # Same reasoning as the two tests above, extended to lists. A
    # generator that never emits an index over a list literal would let
    # a precedence bug in [1,2][0] through while looking green.
    from matrixlang.nodes import Index, IndexAssign, ListLiteral, Unary
    from matrixlang.tokens import TokenType

    empty_list = False
    populated_list = False
    nested_list = False
    index_of_index = False
    index_of_literal = False
    length_over_binary = False
    index_assignment = False

    def walk_expr(expr):
        nonlocal empty_list, populated_list, nested_list
        nonlocal index_of_index, index_of_literal, length_over_binary
        if isinstance(expr, ListLiteral):
            if expr.elements:
                populated_list = True
            else:
                empty_list = True
            if any(isinstance(e, ListLiteral) for e in expr.elements):
                nested_list = True
            for element in expr.elements:
                walk_expr(element)
        elif isinstance(expr, Index):
            if isinstance(expr.target, Index):
                index_of_index = True
            if isinstance(expr.target, ListLiteral):
                index_of_literal = True
            walk_expr(expr.target)
            walk_expr(expr.index)
        elif isinstance(expr, Unary):
            if expr.op is TokenType.LENGTH and isinstance(expr.operand, Binary):
                length_over_binary = True
            walk_expr(expr.operand)
        elif isinstance(expr, Binary):
            walk_expr(expr.left)
            walk_expr(expr.right)
        elif isinstance(expr, Call):
            walk_expr(expr.callee)
            for arg in expr.args:
                walk_expr(arg)

    def walk_stmt(stmt):
        nonlocal index_assignment
        if isinstance(stmt, IndexAssign):
            index_assignment = True
            walk_expr(stmt.target)
            walk_expr(stmt.index)
            walk_expr(stmt.value)
            return
        for field in ("value", "condition"):
            if hasattr(stmt, field) and getattr(stmt, field) is not None:
                walk_expr(getattr(stmt, field))
        for child in getattr(stmt, "body", []):
            walk_stmt(child)
        for child in getattr(stmt, "then_body", []):
            walk_stmt(child)
        for child in getattr(stmt, "else_body", None) or []:
            walk_stmt(child)

    for seed in range(300):
        for statement in gen_program(random.Random(seed)).statements:
            walk_stmt(statement)

    assert empty_list, "no [] in 300 seeds"
    assert populated_list, "no populated list in 300 seeds"
    assert nested_list, "no nested list in 300 seeds"
    assert index_of_index, "no xs[0][1] shape in 300 seeds"
    assert index_of_literal, "no [1,2][0] shape in 300 seeds"
    assert length_over_binary, "no `length (a + b)` shape in 300 seeds"
    assert index_assignment, "no IndexAssign in 300 seeds"
```

Add `from matrixlang.nodes import Call` to the imports at the top of `test_roundtrip.py` if it is not already there.

- [ ] **Step 2: Run it to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_roundtrip.py -q -k stage_7
```

Expected: FAIL with `no [] in 300 seeds`.

- [ ] **Step 3: Teach the generator to emit lists**

In `tests/treegen.py`, add the imports (`Index`, `IndexAssign`, `ListLiteral`). In `gen_expression`, change the tail so lists and indexes occur constantly rather than by luck:

```python
def gen_expression(rng: random.Random, depth: int) -> Expr:
    if depth == 0:
        return gen_atom(rng)
    roll = rng.random()
    if roll < 0.34:
        # Both children draw from the full depth-1 space, so equal-
        # precedence right children (R-PAREN-2) and nested chains occur
        # constantly rather than by luck.
        return Binary(
            gen_expression(rng, depth - 1),
            rng.choice(_BINARY_OPS),
            gen_expression(rng, depth - 1),
        )
    if roll < 0.46:
        # Unary over a full subexpression: the R-PAREN-3 shape. Both
        # unary operators, so `length (a + b)` is generated too — the
        # shape that would render as `length a + b` if the emitter reused
        # the enclosing level, which is a different tree.
        return Unary(
            rng.choice([TokenType.MINUS, TokenType.LENGTH]),
            gen_expression(rng, depth - 1),
        )
    if roll < 0.58:
        # Calls, with arguments drawn from the full space so f(a + b)
        # occurs constantly rather than by luck. That shape is the one an
        # emitter that reuses the enclosing precedence renders as
        # f(a) + b -- a different tree with a different meaning.
        return gen_call(rng, depth - 1)
    if roll < 0.70:
        return gen_list(rng, depth - 1)
    if roll < 0.80:
        return gen_index(rng, depth - 1)
    return gen_atom(rng)


def gen_list(rng: random.Random, depth: int) -> ListLiteral:
    """A list literal, empty a fifth of the time so [] is covered."""
    if rng.random() < 0.2:
        return ListLiteral([])
    return ListLiteral(
        [gen_expression(rng, max(0, depth)) for _ in range(rng.randint(1, 3))]
    )


def gen_index(rng: random.Random, depth: int) -> Index:
    """An index whose target may be a name, a list literal or another
    index, so xs[0][1] and [1,2][0] both occur."""
    roll = rng.random()
    target: Expr
    if roll < 0.5 or depth <= 0:
        target = Name(rng.choice(_IDENTS))
    elif roll < 0.75:
        target = gen_list(rng, depth - 1)
    else:
        target = gen_index(rng, depth - 1)
    return Index(target, gen_expression(rng, max(0, depth - 1)))
```

In `gen_statement`, add `"indexassign"` to the base `kinds` list and the branch:

```python
    elif kind == "indexassign":
        stmt = IndexAssign(
            gen_index(rng, 2).target if rng.random() < 0.3 else Name(rng.choice(_IDENTS)),
            gen_expression(rng, 2),
            gen_expression(rng, 3),
        )
```

Update the `treegen.py` module docstring's coverage paragraph to name the Stage 7 shapes alongside the others.

- [ ] **Step 4: Run the meta-test and the property test**

```bash
.venv/bin/python -m pytest tests/test_roundtrip.py -q
```

Expected: PASS, including the pre-existing 300-seed round trip now exercising list syntax.

- [ ] **Step 5: Teeth-check the generator**

Temporarily change `gen_list` to always return `ListLiteral([])`, then:

```bash
.venv/bin/python -m pytest tests/test_roundtrip.py -q -k stage_7
```

Expected: FAIL with `no populated list in 300 seeds`. **Revert the change with an editor, not `git checkout`** — uncommitted work in other files would be lost.

- [ ] **Step 6: Commit**

```bash
git add tests/
git commit -m "test: the round-trip generator produces the Stage 7 shapes"
```

---

## Task 7: Runtime values — `is_list`, `type_name`, `to_display`

**Files:**
- Modify: `src/matrixlang/values.py`
- Test: `tests/test_values.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `is_list(value) -> bool`, `type_name` returning `"list"`, `to_display` rendering `[1, 2]`, and a module-local `CyclicValue(Exception)`. Task 9 catches `CyclicValue`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_values.py`:

```python
def test_a_list_is_recognised_by_identity_of_type_not_isinstance():
    from matrixlang.values import is_list

    assert is_list([]) is True
    assert is_list([1, 2]) is True
    assert is_list("no") is False
    assert is_list(1) is False


def test_a_list_names_itself_list():
    from matrixlang.values import type_name

    assert type_name([1]) == "list"


def test_a_list_displays_with_brackets():
    from matrixlang.values import to_display

    assert to_display([]) == "[]"
    assert to_display([1, 2]) == "[1, 2]"
    assert to_display([True, False]) == "[true, false]"


def test_strings_are_quoted_inside_a_list_but_not_outside_one():
    # Bare `trace "hi"` prints hi. Inside a list, without quotes there is
    # no way to tell a string from a name and a list of strings becomes
    # unreadable, so the inconsistency is deliberate.
    from matrixlang.values import to_display

    assert to_display("hi") == "hi"
    assert to_display(["hi"]) == '["hi"]'
    assert to_display(["a", 1]) == '["a", 1]'


def test_a_quote_inside_a_displayed_string_is_escaped():
    from matrixlang.values import to_display

    assert to_display(['say "hi"']) == '["say \\"hi\\""]'


def test_nested_lists_display():
    from matrixlang.values import to_display

    assert to_display([[1], [2, 3]]) == "[[1], [2, 3]]"


def test_an_agent_inside_a_list_displays_by_name():
    from matrixlang.values import Function, to_display

    agent = Function("fib", ["n"], None, None)
    assert to_display([agent]) == "[<agent fib>]"


def test_displaying_a_cyclic_list_raises_a_named_error_not_a_recursion_error():
    # Measured before the design was written: the naive recursive
    # to_display raises RecursionError, which the interpreter converts to
    # "expression is nested too deeply" — a false statement about a
    # one-element list. A named exception is what lets the interpreter
    # report the truth.
    from matrixlang.values import CyclicValue, to_display

    xs = [1]
    xs[0] = xs
    with pytest.raises(CyclicValue):
        to_display(xs)
```

Add `import pytest` at the top of `tests/test_values.py` if it is not already there.

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/python -m pytest tests/test_values.py -q
```

Expected: FAIL — `cannot import name 'is_list'`.

- [ ] **Step 3: Implement**

In `src/matrixlang/values.py`, after the `NOTHING` definition:

```python
class CyclicValue(Exception):
    """A list that contains itself, directly or through other lists.

    Raised rather than recursing forever. It is NOT a MatrixLangError,
    because this module may import nothing (tests/test_architecture.py)
    and has never had access to a line or column — every MatrixLangError
    carries one. The interpreter catches this and attaches the position,
    which is the module that actually knows it.
    """
```

Add the predicate next to the others:

```python
def is_list(value: object) -> bool:
    return type(value) is list
```

Extend `type_name`, before the fallback:

```python
    if is_list(value):
        return "list"
```

Replace `to_display`:

```python
def to_display(value: object) -> str:
    """How `trace` renders a value.

    Strings print without quotes at the top level; booleans print in the
    language's own lowercase spelling, not Python's True/False.

    Inside a list, strings ARE quoted. The inconsistency is deliberate:
    without quotes `[hi, 1]` gives a reader no way to tell a string from
    a name. The top level keeps its old behaviour because changing it
    would alter the output of every program written so far.
    """
    return _display(value, nested=False, seen=frozenset())


def _display(value: object, nested: bool, seen: frozenset) -> str:
    if is_bool(value):
        return "true" if value else "false"
    if is_str(value):
        if not nested:
            return value
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if is_function(value):
        # Never str(value): that would put a Python class name and a
        # memory address into output a program produced, which is a hole
        # in the claim that a .rain program has no route into Python.
        return f"<agent {value.name}>"
    if is_list(value):
        if id(value) in seen:
            raise CyclicValue
        seen = seen | {id(value)}
        return "[" + ", ".join(_display(v, True, seen) for v in value) + "]"
    return str(value)
```

- [ ] **Step 4: Run the tests**

```bash
.venv/bin/python -m pytest tests/test_values.py -q
```

Expected: PASS.

- [ ] **Step 5: Confirm `values.py` still imports nothing**

```bash
.venv/bin/python -m pytest tests/test_architecture.py -q
```

Expected: PASS. If this fails, an import crept into `values.py` — remove it rather than editing the allow-table.

- [ ] **Step 6: Commit**

```bash
git add src/matrixlang/values.py tests/test_values.py
git commit -m "feat: lists are a runtime value type, and a cycle says so by name"
```

---

## Task 8: `values.equal` — the load-bearing one

**Files:**
- Modify: `src/matrixlang/values.py`
- Test: `tests/test_values.py`

**Interfaces:**
- Consumes: `type_name`, `is_list` (Task 7).
- Produces: `equal(a, b) -> bool` and `Incomparable(Exception)` with `.left` and `.right` type-name strings. Task 9 calls `equal` and converts `Incomparable`.

**Why this is the load-bearing task.** Measured against the real code path before the design was written:

```
1 == true          (top level, existing guard)  -> error: cannot compare   ✓
[1] == [true]      (one level down)             -> True                    ✗
[[1]] == [[true]]  (two levels down)            -> True                    ✗
```

`interpreter.py:368` guards operand types with `type_name` and then delegates to Python's `==`. The guard is top-level only, so the language's rule that a bool never equals an integer — technical overview §5.5 — holds at the surface and breaks everywhere beneath it.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_values.py`:

```python
# --- The rule the top-level guard could not reach ------------------------


def test_a_bool_never_equals_an_int_at_any_depth():
    # THE test for this task. The old code guarded operand types with
    # type_name and then handed off to Python's ==, where 1 == True. The
    # guard held exactly at the surface: [1] == [true] returned True.
    from matrixlang.values import Incomparable, equal

    for left, right in [
        (1, True),
        ([1], [True]),
        ([0], [False]),
        ([[1]], [[True]]),
        ([1, [2]], [1, [True]]),
    ]:
        with pytest.raises(Incomparable):
            equal(left, right)


def test_incomparable_carries_both_type_names():
    from matrixlang.values import Incomparable, equal

    with pytest.raises(Incomparable) as caught:
        equal([1], [True])
    assert caught.value.left == "integer"
    assert caught.value.right == "boolean"


def test_lists_compare_structurally():
    from matrixlang.values import equal

    assert equal([1, 2], [1, 2]) is True
    assert equal([], []) is True
    assert equal([[1], [2]], [[1], [2]]) is True


def test_lists_of_different_contents_or_length_are_not_equal():
    from matrixlang.values import equal

    assert equal([1, 2], [1, 3]) is False
    assert equal([1], [1, 2]) is False
    assert equal([1, 2], [1]) is False


def test_scalars_still_compare_by_value():
    from matrixlang.values import equal

    assert equal(1, 1) is True
    assert equal("a", "a") is True
    assert equal(True, True) is True
    assert equal(1, 2) is False


def test_comparing_across_types_is_incomparable():
    from matrixlang.values import Incomparable, equal

    with pytest.raises(Incomparable):
        equal("3", 3)
    with pytest.raises(Incomparable):
        equal([1], 1)


def test_agents_compare_by_identity_inside_a_list():
    from matrixlang.values import Function, equal

    a = Function("f", [], None, None)
    b = Function("f", [], None, None)
    assert equal([a], [a]) is True
    assert equal([a], [b]) is False


# --- Cycles --------------------------------------------------------------


def test_cyclic_lists_compare_without_blowing_the_stack():
    # Measured: Python's per-element identity shortcut saves `a == a` but
    # NOT two mutually referential lists, which raise RecursionError.
    from matrixlang.values import equal

    b = [None]
    c = [None]
    b[0] = c
    c[0] = b

    d = [None]
    e = [None]
    d[0] = d
    e[0] = e

    a = [1]
    a[0] = a

    assert equal(b, c) is True
    assert equal(d, e) is True
    assert equal(a, a) is True


def test_a_cycle_does_not_make_unequal_lists_equal():
    # The seen-set assumes equality on re-entry, which is the standard
    # coinductive treatment. It must not leak into siblings.
    from matrixlang.values import equal

    a = [None, 1]
    a[0] = a
    b = [None, 2]
    b[0] = b
    assert equal(a, b) is False
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/python -m pytest tests/test_values.py -q -k "depth or cyclic or structurally"
```

Expected: FAIL — `cannot import name 'equal'`.

> **Correction recorded 2026-08-02 (Task 11).** Step 3 below, as written,
> is superseded. This plan is a historical record, so the original text is
> left intact beneath this note rather than silently rewritten — read the
> `finally: seen.discard(pair)` block that follows knowing it did not ship.
>
> The plan mandated discarding the `(id, id)` pair from `seen` on the way
> back up the recursion, with a comment claiming the discard prevented "a
> cycle assumption leaking into a sibling comparison." During Task 8's
> implementation, code review found that invariant does not exist:
> fuzzing 20,000 random object graphs (sharing, self-loops, mutual cycles)
> found zero divergence between the discard and no-discard forms, because
> within one `equal()` call a `False` result and an `Incomparable`
> exception both propagate straight to the top without leaving a stale
> entry behind — so any pair that ever finishes recursing does so `True`,
> and a memoized `True` is never wrong to reuse.
>
> What the discard *did* do was make `seen` path-scoped rather than a true
> memo, forcing shared (not just cyclic) list structure to be re-walked
> once per path to it — exponential in the number of shared paths.
> Measured on `node = [node, node]` repeated to depth 20, compared against
> a `copy.deepcopy` of itself: **1,195 ms with the discard** versus
> **0.017 ms without it**. This is reachable from an ordinary `.rain`
> program, not a contrived one — `[n, n]` evaluates `n` once into one
> shared object, which is exactly what Task 9's list-literal evaluation
> does.
>
> The human ruled the plan text superseded rather than binding: the
> shipped code (commit `0947c9a`, "fix: drop discard in values.equal,
> memoize proven-equal pairs instead") deletes the `try`/`finally` and
> lets `seen` accumulate as a genuine memo for the lifetime of one
> `equal()` call. See `docs/TECHNICAL-OVERVIEW.md` §5.5 for the write-up
> alongside the `bool`/`int` finding it sits next to.

- [ ] **Step 3: Implement**

In `src/matrixlang/values.py`, after `CyclicValue`:

```python
class Incomparable(Exception):
    """Two values the language refuses to compare.

    Carries both type names so the interpreter can build the message. Not
    a MatrixLangError for the same reason as CyclicValue: this module may
    import nothing, and has no line or column to report.
    """

    def __init__(self, left: str, right: str) -> None:
        self.left = left
        self.right = right
        super().__init__(f"cannot compare {left} with {right}")
```

At the end of the module:

```python
def equal(left: object, right: object) -> bool:
    """The language's `==`, at every depth.

    **Never delegates to Python's `==` for a list.** Python compares list
    elements with its own `==`, where `1 == True` — so `[1] == [true]`
    returned True while the top-level guard correctly rejected
    `1 == true`. The rule held at the surface and broke at every level
    beneath it. Recursing here with `type_name` is what makes it total.

    Cycles are handled with a seen-set of id-pairs rather than left to
    RecursionError: two mutually referential lists blow the stack under
    Python's own comparison, and mutation is what makes such lists
    reachable at all (Stage 7 design §3).
    """
    return _equal(left, right, set())


def _equal(left: object, right: object, seen: set) -> bool:
    if type_name(left) != type_name(right):
        raise Incomparable(type_name(left), type_name(right))
    if not is_list(left):
        # Agents are identity-compared by Function.__eq__; scalars are
        # value-compared. Both are correct here because the type check
        # above has already ruled out the bool/int confusion.
        return left == right
    if len(left) != len(right):
        return False
    pair = (id(left), id(right))
    if pair in seen:
        # Already comparing this pair further up the stack. Assuming
        # equality is the standard treatment and is what terminates.
        return True
    seen.add(pair)
    try:
        for a, b in zip(left, right):
            if not _equal(a, b, seen):
                return False
        return True
    finally:
        # Discarded so a cycle assumption cannot leak into a sibling
        # comparison and make two unequal lists compare equal.
        seen.discard(pair)
```

- [ ] **Step 4: Run the tests**

```bash
.venv/bin/python -m pytest tests/test_values.py -q
```

Expected: PASS, all of them.

- [ ] **Step 5: Teeth-check**

Temporarily replace the body of `_equal` with the naive version:

```python
def _equal(left, right, seen):
    if type_name(left) != type_name(right):
        raise Incomparable(type_name(left), type_name(right))
    return left == right
```

```bash
.venv/bin/python -m pytest tests/test_values.py -q -k "depth or cyclic"
```

Expected: FAIL — `test_a_bool_never_equals_an_int_at_any_depth` (DID NOT RAISE) and the cyclic tests with `RecursionError`. **Restore with an editor, not `git checkout`.**

- [ ] **Step 6: Commit**

```bash
git add src/matrixlang/values.py tests/test_values.py
git commit -m "feat: equality recurses with the language's own type rules"
```

---

## Task 9: The interpreter — evaluate, concatenate, and report

**Files:**
- Modify: `src/matrixlang/interpreter.py` — `_execute` (new `IndexAssign` case), `_evaluate` (three new cases), `_binary` (`+` on lists, and `equal`), `_unary` (`length`)
- Test: `tests/test_lists_run.py` (create)

**Interfaces:**
- Consumes: `ListLiteral`, `Index`, `IndexAssign` (Tasks 2, 3, 5); `equal`, `Incomparable`, `CyclicValue`, `is_list`, `to_display`, `type_name` (Tasks 7, 8).
- Produces: working list programs.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_lists_run.py`:

```python
"""Stage 7 — running list programs end to end."""

import io

import pytest

from matrixlang.errors import RuntimeErrorML
from matrixlang.interpreter import Interpreter
from matrixlang.lexer import lex
from matrixlang.parser import parse


def run(source):
    out = io.StringIO()
    Interpreter(out=out).run(parse(lex(source)))
    return out.getvalue()


def fails(source):
    with pytest.raises(RuntimeErrorML) as caught:
        run(source)
    return caught.value


def test_a_list_traces():
    assert run("trace [1, 2, 3]\n") == "[1, 2, 3]\n"


def test_an_empty_list_traces():
    assert run("trace []\n") == "[]\n"


def test_indexing_reads_an_element():
    assert run('construct xs = ["a", "b"]\ntrace xs[1]\n') == "b\n"


def test_element_assignment_writes():
    assert run("construct xs = [1, 2]\nxs[0] = 9\ntrace xs[0]\n") == "9\n"


def test_element_assignment_is_visible_through_an_alias():
    # Reference semantics: this is the observable consequence of S7-1.
    source = (
        "construct xs = [1]\n"
        "construct ys = xs\n"
        "xs[0] = 9\n"
        "trace ys[0]\n"
    )
    assert run(source) == "9\n"


def test_an_agent_mutates_the_caller_s_list():
    source = (
        "agent bump(zs)\n"
        "  zs[0] = zs[0] + 1\n"
        "flatline\n"
        "construct xs = [1]\n"
        "bump(xs)\n"
        "trace xs[0]\n"
    )
    assert run(source) == "2\n"


def test_length_of_a_list():
    assert run("trace length [1, 2, 3]\n") == "3\n"


def test_length_of_a_string():
    assert run('trace length "Neo"\n') == "3\n"


def test_length_of_an_empty_list_and_string():
    assert run('trace length []\ntrace length ""\n') == "0\n0\n"


def test_concatenation_produces_a_new_list():
    assert run("trace [1] + [2]\n") == "[1, 2]\n"


def test_concatenation_does_not_mutate_either_operand():
    source = (
        "construct xs = [1]\n"
        "construct ys = xs + [2]\n"
        "trace length xs\n"
        "trace length ys\n"
    )
    assert run(source) == "1\n2\n"


def test_lists_compare_structurally_at_runtime():
    assert run("trace [1, 2] == [1, 2]\n") == "true\n"
    assert run("trace [1] != [2]\n") == "true\n"


def test_a_bool_never_equals_an_int_inside_a_list_at_runtime():
    # The end-to-end form of Task 8's central case.
    error = fails("trace [1] == [true]\n")
    assert "cannot compare integer with boolean" in error.message
    assert error.line == 1


def test_walking_a_list_with_dejavu():
    source = (
        'construct crew = ["Neo", "Trinity"]\n'
        "construct n = 0\n"
        "dejavu n < length crew\n"
        "  trace crew[n]\n"
        "  n = n + 1\n"
        "flatline\n"
    )
    assert run(source) == "Neo\nTrinity\n"


def test_tracing_a_cyclic_list_says_what_is_wrong():
    # NOT "expression is nested too deeply", which is what the naive
    # implementation reports and which is false — nothing is nested.
    error = fails("construct xs = [1]\nxs[0] = xs\ntrace xs\n")
    assert "cycle" in error.message.lower()
    assert "nested too deeply" not in error.message
    assert error.line == 3
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/python -m pytest tests/test_lists_run.py -q
```

Expected: FAIL on every test.

- [ ] **Step 3: Evaluate the new expression nodes**

In `src/matrixlang/interpreter.py`, import `Index`, `IndexAssign`, `ListLiteral` from `nodes`, and `CyclicValue`, `Incomparable`, `equal`, `is_list` from `values`. In `_evaluate` — the `if isinstance(expr, ...)` chain that begins around line 274 — add before the fallback:

```python
        if isinstance(expr, ListLiteral):
            # _value_of, not _evaluate: `[f()]` where f jacks out no value
            # must be an error, not a list holding NOTHING. Routing every
            # position through _value_of is what keeps NOTHING from being
            # stored, compared, printed or added to anything.
            return [self._value_of(element, expr) for element in expr.elements]
        if isinstance(expr, Index):
            target = self._value_of(expr.target, expr)
            index = self._value_of(expr.index, expr)
            return self._element(target, index, expr)
```

Note the parameter is named `expr` in this method, not `node` — match the surrounding branches.

Add the shared accessor, which Task 10 will lean on:

```python
    def _element(self, target: object, index: object, node) -> object:
        """Bounds-check and read. Shared by Index and IndexAssign so the
        two cannot disagree about what a legal index is."""
        if not is_list(target):
            raise RuntimeErrorML(
                f"cannot index {type_name(target)}", node.line, node.column
            )
        self._check_index(target, index, node)
        return target[index]

    def _check_index(self, target: list, index: object, node) -> None:
        if not is_int(index):
            raise RuntimeErrorML(
                f"an index must be an integer, got {type_name(index)}",
                node.line,
                node.column,
            )
        if index < 0:
            raise RuntimeErrorML(
                "an index cannot be negative — use xs[length xs - 1]",
                node.line,
                node.column,
            )
        if index >= len(target):
            raise RuntimeErrorML(
                f"index {index} is past the end of a list of length "
                f"{len(target)}",
                node.line,
                node.column,
            )
```

Import `is_int` from `values` alongside the others.

- [ ] **Step 4: Execute element assignment**

In `_execute`, add a branch to the `elif` chain immediately after the `Assign` case (around line 200):

```python
        elif isinstance(stmt, IndexAssign):
            target = self._value_of(stmt.target, stmt)
            index = self._value_of(stmt.index, stmt)
            value = self._value_of(stmt.value, stmt)
            if not is_list(target):
                raise RuntimeErrorML(
                    f"cannot index {type_name(target)}", stmt.line, stmt.column
                )
            self._check_index(target, index, stmt)
            target[index] = value
```

**Do not add an event-emission call.** `self._sink.emit(Statement(...))` already runs at `interpreter.py:186`, before the dispatch chain, for *every* statement including block children. Emitting again here would make an element assignment fall through the cascade twice.

It is an `elif`, not an `if` — the chain is a single dispatch, and starting a new `if` would let a statement match two branches.

- [ ] **Step 5: Extend `+` and wire in `equal`**

`_binary` currently reads (interpreter.py:339-349): equality/ordering first, then two `PLUS` branches for strings — one concatenating, one raising `cannot add X and Y` when exactly one side is a string — then arithmetic. Add the list pair immediately after the string pair, in the same shape:

```python
        if node.op is TokenType.PLUS and is_list(left) and is_list(right):
            # A NEW list. Concatenation copies, which is why `+` alone
            # cannot build a cycle — element assignment is the only door.
            return left + right
        if node.op is TokenType.PLUS and is_list(left) != is_list(right):
            raise RuntimeErrorML(
                f"cannot add {type_name(left)} and {type_name(right)}",
                node.line,
                node.column,
            )
```

The second branch matters for the message. Without it, `[1] + 2` falls through to `_arithmetic` and reports `left operand must be an integer, got list` — technically true and much worse than `cannot add list and integer`, which is the family the string case already uses.

In `_comparison` (interpreter.py:352), replace everything from the `# Equality: same type only` comment to the end of the method:

```python
        # Equality routes through values.equal, which applies type_name at
        # EVERY depth. The old code checked the operands here and then
        # handed off to Python's ==, where 1 == True — so `1 == true` was
        # correctly an error while `[1] == [true]` returned True.
        try:
            same = equal(left, right)
        except Incomparable as mismatch:
            raise RuntimeErrorML(
                f"cannot compare {mismatch.left} with {mismatch.right}",
                node.line,
                node.column,
            ) from None
        if node.op is TokenType.EQ:
            return same
        if node.op is TokenType.NEQ:
            return not same
        raise AssertionError(f"unhandled equality operator: {node.op.name}")
```

Delete the old `if type_name(left) != type_name(right)` guard and the two `left == right` / `left != right` returns it protected. `equal` performs that check itself, recursively, which is the entire point of Task 8.

The ordering-operator block above it is unchanged: `<`, `>`, `<=`, `>=` still require integers, so lists are not orderable.

- [ ] **Step 6: Implement `length`**

There is **no `_unary` method** — `Unary` is handled inline in `_evaluate` at interpreter.py:274, and it currently assumes the operator is always `-`:

```python
        if isinstance(expr, Unary):
            operand = self._evaluate(expr.operand)
            self._require_int(operand, expr.operand, "operand of unary '-'")
            return -operand
```

Replace that block with a dispatch on the operator:

```python
        if isinstance(expr, Unary):
            operand = self._value_of(expr.operand, expr)
            if expr.op is TokenType.LENGTH:
                if not (is_list(operand) or is_str(operand)):
                    raise RuntimeErrorML(
                        f"'length' takes a list or a string, got "
                        f"{type_name(operand)}",
                        expr.line,
                        expr.column,
                    )
                return len(operand)
            self._require_int(operand, expr.operand, "operand of unary '-'")
            return -operand
```

`is_str` is already imported in this module; add `is_list` to the same import block.

The switch from `_evaluate` to `_value_of` here also fixes a latent gap: `-f()` where `f` jacks out no value previously reached `_require_int` with `NOTHING` and reported a type error naming a sentinel that is not a language value.

- [ ] **Step 7: Convert `CyclicValue` where a value is displayed**

The only call site is the `Trace` branch at interpreter.py:188-192, where `to_display` is nested inside the `emit` call:

```python
        if isinstance(stmt, Trace):
            self._sink.emit(
                Output(
                    text=to_display(self._value_of(stmt.value, stmt)), line=stmt.line
                )
            )
```

Unnest it so the conversion has somewhere to live:

```python
        if isinstance(stmt, Trace):
            value = self._value_of(stmt.value, stmt)
            try:
                text = to_display(value)
            except CyclicValue:
                # NOT "expression is nested too deeply", which is what the
                # RecursionError path reports and which is false: a list
                # that contains itself may be one element long.
                raise RuntimeErrorML(
                    "cannot display a list that contains itself",
                    stmt.line,
                    stmt.column,
                ) from None
            self._sink.emit(Output(text=text, line=stmt.line))
```

- [ ] **Step 8: Run the tests**

```bash
.venv/bin/python -m pytest tests/test_lists_run.py -q
```

Expected: PASS.

- [ ] **Step 9: Run the full suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS, with a total above the 1,023 baseline. If any pre-existing test fails, the equality rewrite is the first place to look — it changed a code path every comparison in the language goes through.

- [ ] **Step 10: Commit**

```bash
git add src/matrixlang/interpreter.py tests/test_lists_run.py
git commit -m "feat: lists run — index, assign, concatenate, compare, measure"
```

---

## Task 10: The error surface

**Files:**
- Test: `tests/test_lists_run.py`
- Modify: `src/matrixlang/interpreter.py` only if a case below is missing

**Interfaces:**
- Consumes: everything from Task 9.
- Produces: nothing new. This task proves the error surface is complete and each message is useful.

- [ ] **Step 1: Write the tests**

Append to `tests/test_lists_run.py`:

```python
# --- Errors --------------------------------------------------------------


def test_indexing_past_the_end_reports_both_numbers():
    error = fails("construct xs = [1, 2]\ntrace xs[5]\n")
    assert "5" in error.message and "2" in error.message
    assert error.line == 2


def test_a_negative_index_suggests_the_idiom():
    error = fails("construct xs = [1]\ntrace xs[-1]\n")
    assert "length xs - 1" in error.message


def test_a_non_integer_index_is_an_error():
    error = fails('construct xs = [1]\ntrace xs["a"]\n')
    assert "must be an integer" in error.message


def test_indexing_a_non_list_is_an_error():
    error = fails("construct n = 1\ntrace n[0]\n")
    assert "cannot index integer" in error.message


def test_indexing_an_empty_list_is_an_error():
    error = fails("construct xs = []\ntrace xs[0]\n")
    assert "length 0" in error.message


def test_adding_a_list_to_an_integer_is_an_error():
    error = fails("trace [1] + 2\n")
    assert "list" in error.message and "integer" in error.message


def test_length_of_an_integer_is_an_error():
    error = fails("trace length 5\n")
    assert "'length' takes a list or a string" in error.message


def test_length_of_a_boolean_is_an_error():
    error = fails("trace length true\n")
    assert "boolean" in error.message


def test_assigning_past_the_end_is_an_error():
    error = fails("construct xs = [1]\nxs[3] = 9\n")
    assert "past the end" in error.message
    assert error.line == 2


def test_every_list_error_carries_a_line_and_a_column():
    for source in [
        "construct xs = []\ntrace xs[0]\n",
        "trace length 5\n",
        "trace [1] + 2\n",
        "construct xs = [1]\nxs[9] = 1\n",
    ]:
        error = fails(source)
        assert error.line >= 1
        assert error.column >= 1
```

- [ ] **Step 2: Run them**

```bash
.venv/bin/python -m pytest tests/test_lists_run.py -q
```

Expected: PASS. `test_adding_a_list_to_an_integer_is_an_error` depends on the second `PLUS` branch from Task 9 Step 5 being present — without it the message is `left operand must be an integer, got list`, which contains both words by accident and would let a worse message ship. If that test passes but the message is the arithmetic one, the branch was skipped; go back and add it.

- [ ] **Step 3: Commit**

```bash
git add tests/test_lists_run.py src/matrixlang/interpreter.py
git commit -m "test: the Stage 7 error surface, with positions"
```

---

## Task 11: The CLI, the cascade, and the documentation

**Files:**
- Modify: `docs/LEARNING-MATRIXLANG.md`, `README.md`, `docs/TECHNICAL-OVERVIEW.md`
- Test: manual verification steps, plus one CLI test

**Interfaces:**
- Consumes: the whole working feature.
- Produces: shipped documentation.

- [ ] **Step 1: Run the CLI against a real list program**

`treeview.py` had no case for the Stage 6 nodes and `matrixlang parse` crashed while 878 tests passed. Unit tests are not enough here.

```bash
cat > /tmp/list-demo.rain <<'RAIN'
construct crew = ["Neo", "Trinity", "Morpheus"]

crew[1] = "Tank"
construct all = crew + ["Cypher"]

construct n = 0
dejavu n < length all
  trace all[n]
  n = n + 1
flatline
RAIN
.venv/bin/matrixlang parse /tmp/list-demo.rain
.venv/bin/matrixlang lex /tmp/list-demo.rain | head -5
.venv/bin/matrixlang render --face glyph /tmp/list-demo.rain
.venv/bin/matrixlang render --face glyph /tmp/list-demo.rain > /tmp/list-demo-glyph.rain
.venv/bin/matrixlang render --face ascii /tmp/list-demo-glyph.rain
.venv/bin/matrixlang run --no-window /tmp/list-demo.rain
```

Expected: `parse` prints a tree containing `ListLiteral`, `Index` and `IndexAssign` with no traceback; the glyph render contains no `[` or `]`; the ascii render of the glyph file is byte-identical to the original; `run` prints `Neo`, `Tank`, `Morpheus`, `Cypher`.

- [ ] **Step 2: Add a CLI regression test**

Append to `tests/test_cli.py`:

```python
def test_parse_does_not_crash_on_a_list_program(tmp_path, capsys):
    # treeview.py had no case for the Stage 6 nodes and this command
    # crashed while 878 tests passed. One test per stage, forever.
    path = tmp_path / "lists.rain"
    path.write_text("construct xs = [1, 2]\nxs[0] = length xs\n", encoding="utf-8")
    assert main(["parse", str(path)]) == 0
    out = capsys.readouterr().out
    assert "ListLiteral" in out
    assert "IndexAssign" in out
```

```bash
.venv/bin/python -m pytest tests/test_cli.py -q
```

Expected: PASS.

- [ ] **Step 3: Watch a list program in the cascade**

```bash
.venv/bin/matrixlang run /tmp/list-demo.rain
```

A list literal is a longer source line, and a line falls **vertically**, so its length is its height on screen. Look at whether `construct crew = ["Neo", "Trinity", "Morpheus"]` still reads as rain or as a wall. This is a human judgement, deliberately not a test — the cascade's visual quality has never been caught by a test and has been wrong twice. **If it reads badly, stop and report rather than adjusting the cascade**; that is a separate decision, not part of this plan.

- [ ] **Step 4: Add the tutorial section**

In `docs/LEARNING-MATRIXLANG.md`, insert a new `## 7. Lists` between the current §6 (Agents) and §7 (Scope), renumbering the sections after it and updating the two forward references in §9 and §10. Cover, in this order: literals; `xs[0]`; `xs[0] = v`; `length`; `+`; walking one with `dejavu`; that lists are shared when passed to an agent; and the four errors from Task 10. Every code block must be executed and its output pasted, not remembered — that is the standard the rest of the file was held to.

Update the counts in the file's opening paragraph: **eleven keywords**, and four types.

Update the glyph table in §9 to 38 slots, adding `[`, `]` and `length`.

Add to the "What the language does not have" list: string indexing (`"Neo"[0]`), dictionaries, sets, and `for`.

- [ ] **Step 5: Update the README and technical overview**

`README.md`: add lists to the "Working today" paragraph, and update the test count.

`docs/TECHNICAL-OVERVIEW.md`:
- Header counts — lines, modules, tests.
- §3 module map — new line counts for the nine changed modules.
- §4 — "Keywords (10)" becomes eleven; add a bullet on lists to "Semantics worth knowing", including that `+` copies and element assignment is the only route to a cycle.
- §5.5 — extend with the Stage 7 finding: the guard was top-level only and lists reintroduced the trap beneath it. This is the strongest addition in the whole stage and belongs in the interview material.
- §9 — remove "Collections of any kind" from what is deliberately absent; add string indexing, dictionaries and sets in its place.

- [ ] **Step 6: Verify every documentation example**

Write a throwaway script in the scratchpad that extracts each fenced block from the new tutorial section, runs it, and asserts the stated output — the same check the tutorial was originally held to.

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS.

- [ ] **Step 7: Commit and open the pull request**

```bash
git add -A
git commit -m "docs: teach lists, and record what Stage 7 found about equality"
git push -u origin feat/stage-7-lists
```

Open a PR against `main` referencing #40. The body must state: the measured before/after for `[1] == [true]`, the cycle diagnostic change, the final test count, and the result of the human cascade check from Step 3.

---

## Self-Review

**Spec coverage.** Every section of the design spec maps to a task:

| Spec | Task |
| --- | --- |
| §1 Vocabulary and glyph budget | 1 |
| §2 The surface | 2, 3, 4, 5 |
| §3 Mutability and its cost | 5, 9 (`test_element_assignment_is_visible_through_an_alias`) |
| §4 What a list is at runtime | 7 |
| §5 Errors | 10 |
| §6.1 The `bool`/`int` trap | 8 |
| §6.2 Cycles | 7 (display), 8 (equality) |
| §7 The two faces | 2, 3, 4, 5 (render), 6 (generator) |
| §8 The cascade | 11 Step 3 |
| §9 Testing | throughout; the four commitments are Tasks 8, 6, 11 Step 1–2, 11 Step 3 |
| §10 Out of scope | Task 11 Step 4 documents the exclusions |

**Placeholder scan.** No TBD, no "handle edge cases", no "similar to Task N". Every code step carries the actual code, and every insertion point names a real line.

**Five corrections made by reading the code rather than assuming it.** The first draft of this plan would have produced wrong code in each of these places:

1. **`_emit_statement` does not exist.** `self._sink.emit(Statement(...))` runs at `interpreter.py:186`, *before* the dispatch chain, for every statement. The draft told the implementer to call it again inside the `IndexAssign` branch, which would have made every element assignment fall through the cascade twice.
2. **`_unary` does not exist either.** `Unary` is handled inline in `_evaluate` at line 274, and it hardcodes `_require_int(..., "operand of unary '-'")`. The draft described editing a method that is not there.
3. **`_evaluate` is the wrong call for element values.** Statement and operand positions route through `_value_of`, which refuses `NOTHING`. Using `_evaluate` would have let `[f()]` build a list holding the sentinel — the one thing §4 of the spec says must never be stored.
4. **`+` needed a second branch, not one.** The string case has a matching "exactly one side is a string" branch that produces `cannot add X and Y`. Without the list equivalent, `[1] + 2` falls through to arithmetic and reports `left operand must be an integer, got list`.
5. **`tests/test_glyphs.py:7` and `:20` pin the table at 35** by name and by assertion. Task 1 now says exactly what to rename and what to change.

**Type consistency.** `ListLiteral.elements`, `Index.target`, `Index.index`, `IndexAssign.target/index/value`, `equal(a, b) -> bool`, `Incomparable.left/.right`, `CyclicValue`, `is_list`, `_element`, `_check_index` — each name is used identically in every task that references it. `length` is `Unary(TokenType.LENGTH, operand)` in Tasks 4, 6 and 9 alike. Parameter names match the methods being edited: `expr` inside `_evaluate`, `node` inside `_binary` and `_comparison`, `stmt` inside `_execute`.

**One spec gap found and closed.** §6.1 called for `equal()` in `values.py` without accounting for that module being allow-listed to import nothing, so it cannot raise a positioned `MatrixLangError`. Resolved with module-local `Incomparable` and `CyclicValue` exceptions converted by the interpreter — recorded in Global Constraints above rather than applied silently.
