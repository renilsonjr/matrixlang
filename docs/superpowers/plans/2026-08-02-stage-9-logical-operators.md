# Stage 9 Logical Operators Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `splice`, `fork` and `unplug` — `and`, `or` and `not` under themed names — with short-circuit evaluation, so a bounded search over a list can be written.

**Architecture:** Three keywords, three glyph slots, **no new AST node** — `splice`/`fork` are `Binary`, `unplug` is the `Unary` node `-x` and `length` already use. The parser's ladder gains two rungs at the loose end and one in the middle. The one genuinely dangerous piece is short-circuit evaluation, which cannot live where every other binary operator lives.

**Tech Stack:** Python ≥3.11, standard library only. pytest.

**Spec:** `docs/superpowers/specs/2026-08-02-stage-9-logical-operators-design.md` (approved, PR #49). Issue #48.

## Global Constraints

Every task's requirements implicitly include all of these.

- **Python ≥3.11.** No third-party runtime dependencies. `pytest` is the only dev dependency.
- **Value type checks use `type(v) is X`, never `isinstance`** — via `is_bool` / `is_int` / `is_str` / `is_list` from `values.py`. `isinstance` on *AST node* types is correct and used freely; the ban is on runtime value checks.
- **Every error carries a line and a column**, raised as a `RuntimeErrorML`.
- **No Python exception or class name may reach a user-facing diagnostic** (technical overview §7).
- **`values.py` may import nothing** and this stage adds nothing to it.
- **Only `glyphs.py` may contain a half-width katakana literal** in `src/`. Tests and docs are exempt.
- **The round-trip criterion is non-negotiable:** `parse(render_glyph(t)) == parse(render_ascii(t)) == t`. This stage renumbers the entire precedence table, so that property is the primary guard.
- **Baseline: 1,167 tests pass on `main`** before this plan begins. No task may reduce that.
- **macOS venv quirk:** if any command reports `ModuleNotFoundError: No module named 'matrixlang'`, run `chflags -R nohidden .venv` and retry. Platform quirk, not a code failure. It can happen at any time.

### Glyph assignments

| Slot | Glyph | Codepoint |
| --- | --- | --- |
| `splice` | `ﾁ` | U+FF81 |
| `fork` | `ﾂ` | U+FF82 |
| `unplug` | `ｳ` | U+FF73 |

`ﾁ`/`ﾂ` are adjacent, mirroring how `[`/`]` mirror `(`/`)`. `ｳ` is mnemonic ("u"). All three verified free; the table goes 38 → 41, leaving 15.

### The three error messages this stage introduces

Named once here so a test and its implementation cannot be written separately and contradict each other — which happened in Stage 7 and survived to the final review.

| Situation | Exact message |
| --- | --- |
| A non-boolean operand of `splice` or `fork` | `'splice' takes booleans, got integer` (with the operator's own spelling and the real type name) |
| A non-boolean operand of `unplug` | `'unplug' takes a boolean, got integer` |

Both follow the shape of the existing `'length' takes a list or a string, got integer`, so the three word-operator failures read as one family.

### The final precedence table

Task 2 installs this whole table at once, including the two rows Task 3 fills in. **Renumbering once is deliberate** — shifting the table twice would double the chance of an off-by-one in the one structure that decides where parentheses go.

| Level | Operators |
| --- | --- |
| 1 | `fork` — added in Task 3 |
| 2 | `splice` — added in Task 3 |
| 3 | `_NOT_LEVEL` (a constant; `unplug` is unary, so it is not a `_LEVEL` entry) |
| 4 | `==` `!=` |
| 5 | `<` `>` `<=` `>=` |
| 6 | `+` `-` |
| 7 | `*` `/` |
| 8 | `_UNARY_LEVEL` — `-x`, `length` |
| 9 | `_ATOM_LEVEL` = `_CALL_LEVEL` |

---

## File Structure

| File | Change | Responsibility after |
| --- | --- | --- |
| `src/matrixlang/tokens.py` | Modify | Adds `SPLICE`, `FORK`, `UNPLUG` and three `KEYWORDS` entries |
| `src/matrixlang/glyphs.py` | Modify | 41 slots |
| `src/matrixlang/lexer.py` | **unchanged** | Words arrive through `KEYWORDS`; `_GLYPH_TOKENS` builds itself by walking `GLYPHS` |
| `src/matrixlang/parser.py` | Modify | Two new `_binary_level` rungs and a `_not` level |
| `src/matrixlang/render.py` | Modify | `_LEVEL` renumbered, three `_OPS` entries, a `Unary` branch that dispatches on operator for level as well as spelling |
| `src/matrixlang/treeview.py` | Modify | Three `_OPS` entries |
| `src/matrixlang/interpreter.py` | Modify | `unplug` evaluation, and short-circuit interception |
| `tests/treegen.py` | Modify | Generates all three shapes |
| `tests/test_logic_run.py` | Create | Behavioural tests for this stage |
| `tests/test_logic_parse.py` | Create | Tree-shape tests — precedence asserted on structure, not values |
| `tests/test_roundtrip.py` | Modify | A Stage 9 coverage meta-test |
| `docs/*`, `README.md` | Modify | Task 6 |

Two new test files rather than one, split the way Stages 6–8 split theirs: precedence is a *parse* property and must be asserted on the tree, so it does not belong in a file whose helper runs programs.

---

## Task 1: Vocabulary — tokens and glyphs

**Files:**
- Modify: `src/matrixlang/tokens.py` (the `TokenType` keyword block and `KEYWORDS`), `src/matrixlang/glyphs.py`
- Test: `tests/test_glyphs.py`, `tests/test_tokens.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `TokenType.SPLICE`, `TokenType.FORK`, `TokenType.UNPLUG`; `GLYPHS["splice"] == "ﾁ"`, `GLYPHS["fork"] == "ﾂ"`, `GLYPHS["unplug"] == "ｳ"`. Every later task depends on these names.

**`lexer.py` is not touched.** `_GLYPH_TOKENS` is built by walking `GLYPHS` and looking each slot up in `KEYWORDS`, `_DOUBLE`, then `_SINGLE`, so adding the keyword entries is what makes the glyph face work. Verify this by running the glyph-face test below rather than by editing the lexer.

- [ ] **Step 1: Write the failing test**

Create `tests/test_logic_parse.py`:

```python
"""Stage 9 — the shape of a logical expression.

Precedence is a parse property, so it is asserted on the TREE here. A
test that checks a computed value can pass under two different groupings
for the inputs it happens to use, which is the kind of test that cannot
fail.
"""

import pytest

from matrixlang.glyphs import GLYPHS
from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.tokens import TokenType


def types(source):
    return [t.type for t in lex(source) if t.type is not TokenType.NEWLINE]


# --- Vocabulary ---------------------------------------------------------


def test_the_three_words_lex_as_keywords():
    assert types("splice") == [TokenType.SPLICE, TokenType.EOF]
    assert types("fork") == [TokenType.FORK, TokenType.EOF]
    assert types("unplug") == [TokenType.UNPLUG, TokenType.EOF]


def test_the_three_words_lex_in_the_glyph_face():
    # _GLYPH_TOKENS builds itself from GLYPHS, so this is what proves the
    # table entries were picked up rather than a hand-written branch.
    assert types(GLYPHS["splice"]) == [TokenType.SPLICE, TokenType.EOF]
    assert types(GLYPHS["fork"]) == [TokenType.FORK, TokenType.EOF]
    assert types(GLYPHS["unplug"]) == [TokenType.UNPLUG, TokenType.EOF]


def test_identifiers_that_start_with_a_keyword_are_still_identifiers():
    assert types("splicer") == [TokenType.IDENT, TokenType.EOF]
    assert types("forked") == [TokenType.IDENT, TokenType.EOF]
    assert types("unplugged") == [TokenType.IDENT, TokenType.EOF]


@pytest.mark.parametrize("slot", ["splice", "fork", "unplug"])
def test_each_new_slot_has_a_single_glyph(slot):
    assert slot in GLYPHS
    assert len(GLYPHS[slot]) == 1


def test_the_table_is_still_bijective_at_41():
    assert len(set(GLYPHS.values())) == len(GLYPHS) == 41
```

- [ ] **Step 2: Run it to verify it fails**

```bash
.venv/bin/python -m pytest tests/test_logic_parse.py -q
```

Expected: FAIL — `AttributeError: SPLICE` and `KeyError: 'splice'`.

- [ ] **Step 3: Add the token types**

In `src/matrixlang/tokens.py`, in the `# Keywords` block after `LENGTH = auto()`:

```python
    SPLICE = auto()
    FORK = auto()
    UNPLUG = auto()
```

In `KEYWORDS`, after the `"length"` entry:

```python
    "splice": TokenType.SPLICE,
    "fork": TokenType.FORK,
    "unplug": TokenType.UNPLUG,
```

- [ ] **Step 4: Add the glyphs**

In `src/matrixlang/glyphs.py`, after the `"length": "ﾙ",` line:

```python
    # Stage 9. `and`, `or` and `not` as crew vocabulary: splice joins two
    # signals, fork is a branch in the path, unplug cuts it. The films
    # have no concept of logical conjunction, so these are metaphors of
    # connection rather than film concepts — recorded in the Stage 9
    # design §1 rather than pretended otherwise.
    "splice": "ﾁ",
    "fork": "ﾂ",
    "unplug": "ｳ",
```

Update the module docstring's first line from `"""The 38-slot glyph table` to `"""The 41-slot glyph table`.

- [ ] **Step 5: Run the new tests, then the full suite**

```bash
.venv/bin/python -m pytest tests/test_logic_parse.py -q
```

Expected: PASS.

```bash
.venv/bin/python -m pytest -q
```

Expected: two failures to fix, both counts that are pinned deliberately and must be **updated, not weakened**:

- `tests/test_glyphs.py` — a test named for the slot count (`test_the_table_covers_exactly_the_38_slots` or similar) asserts the exact number and lists the expected slots. Rename it to 41, add `"splice"`, `"fork"`, `"unplug"` to its expected set, and change the count assertion. Do **not** relax it to a range.
- `tests/test_tokens.py` — `test_all_eleven_keywords_are_registered` does a full-set equality against `KEYWORDS`. Rename it for fourteen and add the three entries.

Re-run until green.

- [ ] **Step 6: Commit**

```bash
git add src/matrixlang/tokens.py src/matrixlang/glyphs.py tests/
git commit -m "feat: the Stage 9 vocabulary — splice, fork and unplug, in both faces"
```

---

## Task 2: `unplug`, end to end

**Files:**
- Modify: `src/matrixlang/parser.py` (`expression` at :383, the ladder comment, a new `_not` method), `src/matrixlang/render.py` (`_OPS` at :49, `_LEVEL` at :66, the constants at :78-84, the `Unary` branch at :224), `src/matrixlang/treeview.py` (`_OPS`), `src/matrixlang/interpreter.py` (the `Unary` branch at :318)
- Test: `tests/test_logic_parse.py`, `tests/test_logic_run.py` (create)

**Interfaces:**
- Consumes: `TokenType.UNPLUG` (Task 1).
- Produces: `unplug x` parses as `Unary(TokenType.UNPLUG, x)` — **no new node**. `render._NOT_LEVEL == 3`, and the rest of `_LEVEL` renumbered to its final values. Task 3 fills in levels 1 and 2.

**Why the whole table is renumbered here.** Levels 1 and 2 stay empty until Task 3. Doing it in one move means the 300-seed round-trip property validates the new numbering immediately, rather than validating two intermediate tables neither of which is the target.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_logic_parse.py`:

```python
# --- unplug's shape -----------------------------------------------------


def first(source):
    return parse(lex(source)).statements[0]


def test_unplug_is_a_unary_over_the_whole_comparison():
    # THE precedence test for unplug. `unplug n == 1` must be
    # unplug (n == 1). The C reading, (unplug n) == 1, is an error for
    # every possible n — either n is not boolean and unplug fails, or it
    # is and a boolean is compared to an integer.
    from matrixlang.nodes import Binary, Unary

    parsed = first("construct b = unplug n == 1\n").value
    assert isinstance(parsed, Unary)
    assert parsed.op is TokenType.UNPLUG
    assert isinstance(parsed.operand, Binary)
    assert parsed.operand.op is TokenType.EQ


def test_unplug_nests():
    from matrixlang.nodes import Unary

    parsed = first("construct b = unplug unplug flag\n").value
    assert isinstance(parsed, Unary)
    assert isinstance(parsed.operand, Unary)


def test_unplug_over_a_parenthesised_expression():
    from matrixlang.nodes import Binary, Unary

    parsed = first("construct b = unplug (a == b)\n").value
    assert isinstance(parsed, Unary)
    assert isinstance(parsed.operand, Binary)
```

Create `tests/test_logic_run.py`:

```python
"""Stage 9 — running logical expressions."""

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


# --- unplug -------------------------------------------------------------


def test_unplug_negates():
    assert run("trace unplug true\n") == "false\n"
    assert run("trace unplug false\n") == "true\n"


def test_unplug_over_a_comparison():
    assert run("trace unplug 1 == 2\n") == "true\n"
    assert run("trace unplug 1 == 1\n") == "false\n"


def test_unplug_nests_at_runtime():
    assert run("trace unplug unplug true\n") == "true\n"


def test_unplug_in_a_condition():
    source = 'redpill unplug false\n  trace "yes"\nflatline\n'
    assert run(source) == "yes\n"


def test_unplug_requires_a_boolean():
    assert fails("trace unplug 1\n").message == "'unplug' takes a boolean, got integer"
    assert (
        fails('trace unplug "a"\n').message == "'unplug' takes a boolean, got string"
    )


def test_unplug_carries_a_position():
    error = fails("trace unplug 1\n")
    assert error.line == 1
    assert error.column >= 1
```

Also append to `tests/test_logic_parse.py` a render round-trip block:

```python
# --- unplug round-trips -------------------------------------------------


def roundtrip(source):
    from matrixlang.render import render_ascii, render_glyph

    tree = parse(lex(source))
    assert parse(lex(render_ascii(tree))) == tree, "ascii face"
    assert parse(lex(render_glyph(tree))) == tree, "glyph face"
    return tree


@pytest.mark.parametrize(
    "source",
    [
        "construct b = unplug flag\n",
        "construct b = unplug n == 1\n",
        "construct b = unplug unplug flag\n",
        "construct b = unplug (a == b)\n",
    ],
)
def test_unplug_round_trips(source):
    roundtrip(source)


def test_unplug_renders_with_a_separator_and_no_parens_over_a_comparison():
    # A word operator needs the space or `unplug flag` becomes
    # `unplugflag` and re-lexes as one identifier. And because unplug
    # binds LOOSER than comparison, no parens are needed here — adding
    # them would be harmless but adding them in the wrong place would not.
    from matrixlang.render import render_ascii

    tree = parse(lex("construct b = unplug n == 1\n"))
    assert render_ascii(tree) == "construct b = unplug n == 1\n"
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/python -m pytest tests/test_logic_parse.py tests/test_logic_run.py -q
```

Expected: FAIL — `expected an expression, found 'unplug'`.

- [ ] **Step 3: Parse it**

In `src/matrixlang/parser.py`, change `expression` and add the `_not` rung. Replace:

```python
    def expression(self) -> Expr:
        return self._equality()
```

with:

```python
    def expression(self) -> Expr:
        return self._not()
```

and add `_not` immediately above `_equality`:

```python
    def _not(self) -> Expr:
        """`unplug`, binding looser than comparison.

        Recurses into itself so `unplug unplug flag` works. Placed above
        _equality rather than at the unary level because `unplug n == 1`
        must mean `unplug (n == 1)`: the tight reading, `(unplug n) == 1`,
        is an error for every possible n.
        """
        if self.check(TokenType.UNPLUG):
            op = self.advance()
            operand = self._not()
            return Unary(op.type, operand, line=op.line, column=op.column)
        return self._equality()
```

Update the ladder comment above `_equality` so it mentions the new rung rather than describing a ladder that no longer starts where it says.

- [ ] **Step 4: Renumber the precedence table and render it**

In `src/matrixlang/render.py`, add to `_OPS`:

```python
    TokenType.UNPLUG: "unplug",
```

Replace `_LEVEL` and the constants beneath it with the final table:

```python
_LEVEL: dict[TokenType, int] = {
    # Levels 1 and 2 belong to `fork` and `splice`, added in Stage 9's
    # next step. The whole table is renumbered in one move rather than
    # shifted twice: this structure is what decides where parentheses go,
    # and an off-by-one here changes what a program means without failing
    # loudly anywhere else.
    TokenType.EQ: 4,
    TokenType.NEQ: 4,
    TokenType.LT: 5,
    TokenType.GT: 5,
    TokenType.LTE: 5,
    TokenType.GTE: 5,
    TokenType.PLUS: 6,
    TokenType.MINUS: 6,
    TokenType.STAR: 7,
    TokenType.SLASH: 7,
}
# `unplug` is unary, so it is a constant rather than a _LEVEL entry — but
# unlike `-` and `length` it binds LOOSER than every binary operator
# except fork and splice.
_NOT_LEVEL = 3
_UNARY_LEVEL = 8
_ATOM_LEVEL = 9
# A call is postfix and binds tighter than every operator, including unary
# minus: -f(1) is -(f(1)), never (-f)(1). That makes it an atom for
# parenthesisation purposes, and saying so is better than the two constants
# happening to be equal.
_CALL_LEVEL = _ATOM_LEVEL
```

Replace the `Unary` branch at `render.py:224` so it dispatches on the operator for the **level** as well as the spelling:

```python
    if isinstance(expr, Unary):
        if expr.op is TokenType.UNPLUG:
            # Looser than every binary operator except fork and splice, so
            # `unplug n == 1` needs no parens while `unplug (a fork b)`
            # does. Rendering the operand at _UNARY_LEVEL instead would
            # parenthesise the common case unnecessarily.
            operand = _expression(expr.operand, _NOT_LEVEL, face)
            return _map(face, "unplug") + " " + operand, _NOT_LEVEL
        # R-PAREN-3: any binary operand is looser than _UNARY_LEVEL and
        # gets parens; atoms and nested unaries do not.
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
    TokenType.UNPLUG: "unplug",
```

The existing `Unary` case reads `_OPS[expr.op]`, so nothing else changes.

- [ ] **Step 6: Evaluate it**

In `src/matrixlang/interpreter.py`, in the `Unary` branch (around :318), add the `UNPLUG` case before the `LENGTH` case:

```python
        if isinstance(expr, Unary):
            operand = self._value_of(expr.operand, expr)
            if expr.op is TokenType.UNPLUG:
                if not is_bool(operand):
                    raise RuntimeErrorML(
                        f"'unplug' takes a boolean, got {type_name(operand)}",
                        expr.line,
                        expr.column,
                    )
                return not operand
            if expr.op is TokenType.LENGTH:
                ...
```

`is_bool` is already imported in this module — confirm before adding anything.

- [ ] **Step 7: Run the tests, then the full suite**

```bash
.venv/bin/python -m pytest tests/test_logic_parse.py tests/test_logic_run.py -q
```

Expected: PASS.

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS. **`tests/test_roundtrip.py` is the one that matters here** — it exercises 300 generated trees against the renumbered table. If it fails, the renumbering is wrong, not the test.

- [ ] **Step 8: Commit**

```bash
git add src/matrixlang tests/
git commit -m "feat: unplug, a word operator that binds looser than comparison"
```

---

## Task 3: `splice` and `fork` — parse and render

**Files:**
- Modify: `src/matrixlang/parser.py` (the op tuples at :90-93, `expression`, two new rungs), `src/matrixlang/render.py` (`_OPS`, `_LEVEL`), `src/matrixlang/treeview.py` (`_OPS`)
- Test: `tests/test_logic_parse.py`

**Interfaces:**
- Consumes: `TokenType.SPLICE`, `TokenType.FORK` (Task 1); `_NOT_LEVEL` and the renumbered `_LEVEL` (Task 2).
- Produces: `a splice b` parses as `Binary(a, TokenType.SPLICE, b)`. Task 4 evaluates it.

**Expect a confusing intermediate state, and do not fix it here.** After this task `true splice false` parses and renders correctly but evaluates through `_binary`, which has no case for `SPLICE`, so it falls through to `_arithmetic` and reports `left operand must be an integer, got boolean`. **That is expected.** Task 4 owns evaluation. Do not add `SPLICE`/`FORK` to `_binary` — doing so is the specific mistake the whole stage is shaped around.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_logic_parse.py`:

```python
# --- splice and fork: shape and precedence ------------------------------


def test_splice_and_fork_parse_as_binary():
    from matrixlang.nodes import Binary

    for source, op in [
        ("construct b = a splice c\n", TokenType.SPLICE),
        ("construct b = a fork c\n", TokenType.FORK),
    ]:
        parsed = first(source).value
        assert isinstance(parsed, Binary)
        assert parsed.op is op


def test_fork_binds_looser_than_splice():
    # `a fork b splice c` is `a fork (b splice c)`, as in every language
    # that has both. Asserted on the tree: a value test would agree with
    # the wrong grouping for many inputs.
    from matrixlang.nodes import Binary

    parsed = first("construct b = a fork b splice c\n").value
    assert parsed.op is TokenType.FORK
    assert isinstance(parsed.right, Binary)
    assert parsed.right.op is TokenType.SPLICE


def test_splice_binds_looser_than_comparison():
    from matrixlang.nodes import Binary

    parsed = first("construct b = n < 3 splice m > 1\n").value
    assert parsed.op is TokenType.SPLICE
    assert isinstance(parsed.left, Binary) and parsed.left.op is TokenType.LT
    assert isinstance(parsed.right, Binary) and parsed.right.op is TokenType.GT


def test_unplug_binds_tighter_than_splice():
    from matrixlang.nodes import Binary, Unary

    parsed = first("construct b = unplug a splice c\n").value
    assert isinstance(parsed, Binary)
    assert parsed.op is TokenType.SPLICE
    assert isinstance(parsed.left, Unary)


def test_both_are_left_associative():
    from matrixlang.nodes import Binary

    parsed = first("construct b = a splice c splice d\n").value
    assert parsed.op is TokenType.SPLICE
    assert isinstance(parsed.left, Binary)
    assert parsed.left.op is TokenType.SPLICE


@pytest.mark.parametrize(
    "source",
    [
        "construct b = a splice c\n",
        "construct b = a fork c\n",
        "construct b = a fork b splice c\n",
        "construct b = (a fork b) splice c\n",
        "construct b = unplug a splice c\n",
        "construct b = unplug (a fork c)\n",
        "construct b = n < 3 splice m > 1\n",
    ],
)
def test_logical_expressions_round_trip(source):
    roundtrip(source)


def test_grouping_parens_survive_a_render():
    # (a fork b) splice c is a DIFFERENT tree from a fork b splice c.
    # The renderer must put those parens back from the level table alone.
    from matrixlang.render import render_ascii

    tree = parse(lex("construct b = (a fork b) splice c\n"))
    assert render_ascii(tree) == "construct b = (a fork b) splice c\n"


def test_the_glyph_face_uses_the_new_glyphs():
    from matrixlang.render import render_glyph

    rendered = render_glyph(parse(lex("construct b = a splice c fork d\n")))
    assert GLYPHS["splice"] in rendered
    assert GLYPHS["fork"] in rendered
    assert "splice" not in rendered
    assert "fork" not in rendered
```

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/python -m pytest tests/test_logic_parse.py -q -k "splice or fork"
```

Expected: FAIL — `expected end of line after the statement, found 'splice'`.

- [ ] **Step 3: Parse them**

In `src/matrixlang/parser.py`, add the op tuples next to the existing ones at :90-93:

```python
_FORK_OPS = (TokenType.FORK,)
_SPLICE_OPS = (TokenType.SPLICE,)
```

Change `expression` to enter at the loosest rung:

```python
    def expression(self) -> Expr:
        return self._fork()
```

Add the two rungs immediately above `_not`:

```python
    def _fork(self) -> Expr:
        return self._binary_level(_FORK_OPS, self._splice)

    def _splice(self) -> Expr:
        return self._binary_level(_SPLICE_OPS, self._not)
```

`_binary_level` already folds a left-associative chain, so both are one-liners like every other rung.

- [ ] **Step 4: Render them**

In `src/matrixlang/render.py`, add to `_OPS`:

```python
    TokenType.SPLICE: "splice",
    TokenType.FORK: "fork",
```

Add to `_LEVEL`, at the top where the comment reserves them:

```python
    TokenType.FORK: 1,
    TokenType.SPLICE: 2,
```

and delete the "belong to fork and splice, added in Stage 9's next step" sentence from that comment, since they are now there. Keep the rest of it — the point about renumbering once is still worth saying.

No change to `_binary`'s emitter: it already produces `f"{left} {op} {right}"` with spaces, so these word operators need no separator handling.

- [ ] **Step 5: Add the treeview entries**

In `src/matrixlang/treeview.py`, add to `_OPS`:

```python
    TokenType.SPLICE: "splice",
    TokenType.FORK: "fork",
```

- [ ] **Step 6: Run the tests and the full suite**

```bash
.venv/bin/python -m pytest tests/test_logic_parse.py -q
.venv/bin/python -m pytest -q
```

Expected: PASS. `tests/test_logic_run.py` should still pass — it has no `splice`/`fork` cases yet.

- [ ] **Step 7: Commit**

```bash
git add src/matrixlang tests/
git commit -m "feat: splice and fork join the ladder at its loose end"
```

---

## Task 4: Short-circuit evaluation — the hazard

**Files:**
- Modify: `src/matrixlang/interpreter.py` (`_evaluate`'s `Binary` branch at :331-334, plus a new helper)
- Test: `tests/test_logic_run.py`

**Interfaces:**
- Consumes: `Binary` nodes carrying `TokenType.SPLICE` / `TokenType.FORK` (Task 3).
- Produces: working logical operators.

**Read this before editing anything.**

`_evaluate`'s `Binary` branch reads:

```python
        if isinstance(expr, Binary):
            left = self._value_of(expr.left, expr)
            right = self._value_of(expr.right, expr)      # both, before dispatch
            return self._binary(expr, left, right)
```

`_binary` is where `+`, `==`, the comparisons and the concatenations live. It is the obvious home for two new binary operators, and **putting them there produces operators that work and do not short-circuit.**

That failure is quiet. `true splice false` would correctly be `false`. Every truth-table test would pass. And the program this stage exists for would crash:

```
dejavu n < length crew splice crew[n] != "Tank"
```
```
index 3 is past the end of a list of length 3
```

— an error that looks like a bug in the program rather than in the language.

So the interception goes in `_evaluate`, **before** the right operand is evaluated.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_logic_run.py`:

```python
# --- splice and fork ----------------------------------------------------


def test_splice_is_and():
    assert run("trace true splice true\n") == "true\n"
    assert run("trace true splice false\n") == "false\n"
    assert run("trace false splice true\n") == "false\n"
    assert run("trace false splice false\n") == "false\n"


def test_fork_is_or():
    assert run("trace true fork true\n") == "true\n"
    assert run("trace true fork false\n") == "true\n"
    assert run("trace false fork true\n") == "true\n"
    assert run("trace false fork false\n") == "false\n"


def test_they_compose_with_comparisons():
    assert run("trace 1 < 2 splice 3 > 2\n") == "true\n"
    assert run("trace 1 > 2 fork 3 > 2\n") == "true\n"


def test_unplug_composes_with_them():
    assert run("trace unplug true splice true\n") == "false\n"
    assert run("trace unplug (true splice true)\n") == "false\n"


# --- Short-circuit: the reason this stage exists ------------------------


def test_the_bounded_search_does_not_run_off_the_end():
    # THE test for this task. Without short-circuit, crew[n] is evaluated
    # at the boundary where n == length crew and the program dies with
    # "index 3 is past the end of a list of length 3" — an error that
    # looks like a bug in the program rather than in the language.
    source = (
        'construct crew = ["Neo", "Trinity", "Tank"]\n'
        "construct n = 0\n"
        'dejavu n < length crew splice crew[n] != "Tank"\n'
        "  n = n + 1\n"
        "flatline\n"
        "trace n\n"
    )
    assert run(source) == "2\n"


def test_a_search_that_finds_nothing_still_terminates():
    source = (
        'construct crew = ["Neo", "Trinity"]\n'
        "construct n = 0\n"
        'dejavu n < length crew splice crew[n] != "Cypher"\n'
        "  n = n + 1\n"
        "flatline\n"
        "trace n == length crew\n"
    )
    assert run(source) == "true\n"


def test_splice_does_not_evaluate_the_right_side_when_the_left_is_false():
    # An observable side effect on the right proves the short circuit
    # rather than inferring it.
    source = (
        "agent shout()\n"
        '  trace "evaluated"\n'
        "  jackout true\n"
        "flatline\n"
        "trace false splice shout()\n"
    )
    assert run(source) == "false\n"


def test_fork_does_not_evaluate_the_right_side_when_the_left_is_true():
    source = (
        "agent shout()\n"
        '  trace "evaluated"\n'
        "  jackout false\n"
        "flatline\n"
        "trace true fork shout()\n"
    )
    assert run(source) == "true\n"


def test_the_right_side_does_run_when_it_is_needed():
    source = (
        "agent shout()\n"
        '  trace "evaluated"\n'
        "  jackout true\n"
        "flatline\n"
        "trace true splice shout()\n"
    )
    assert run(source) == "evaluated\ntrue\n"


# --- The asymmetry short-circuit creates --------------------------------


def test_an_unevaluated_operand_is_never_type_checked():
    # Whether a type error appears depends on a VALUE, which is unlike
    # every other operator here. Python, Java and C all behave this way;
    # it is the price of the guard idiom above. Both directions are
    # pinned so neither can drift.
    assert run("trace false splice 1\n") == "false\n"
    assert fails("trace true splice 1\n").message == "'splice' takes booleans, got integer"

    assert run("trace true fork 1\n") == "true\n"
    assert fails("trace false fork 1\n").message == "'fork' takes booleans, got integer"


def test_a_non_boolean_left_operand_is_always_an_error():
    assert fails("trace 1 splice true\n").message == "'splice' takes booleans, got integer"
    assert fails('trace "a" fork true\n').message == "'fork' takes booleans, got string"


def test_the_error_carries_a_position():
    error = fails("trace 1 splice true\n")
    assert error.line == 1
    assert error.column >= 1
```

> **Plan correction, recorded during Task 4 (superseded — kept for the
> record, not rewritten as though it had always been right).** The
> `test_the_bounded_search_does_not_run_off_the_end` specified above
> searches for `"Tank"`, which is the **last** element of `crew`. The
> loop therefore exits at `n == 2`, reading `crew[2]` — a perfectly
> legal index — and never reaches the boundary `n == length crew` at
> all. The test's own comment claims it "dies with `index 3 is past the
> end of a list of length 3`" without short-circuit, but that is false:
> a non-short-circuiting interpreter evaluates `crew[2] != "Tank"`,
> gets `false`, and the loop exits at `n == 2` exactly as a
> short-circuiting one does. The test passed under both, so it could
> not fail for the behaviour it was named after and existed to pin.
> The fix, made during Task 4, was a one-word data change to an absent
> target — searching for `"Cypher"`, which is not in `crew`, so the
> loop genuinely runs to the boundary and only short-circuit prevents
> `crew[3]` from being read. Short-circuit itself was never
> unverified: `test_splice_does_not_evaluate_the_right_side_when_the_left_is_false`,
> `test_fork_does_not_evaluate_the_right_side_when_the_left_is_true`,
> `test_the_right_side_does_run_when_it_is_needed`, and
> `test_an_unevaluated_operand_is_never_type_checked` — all four
> already in this task's plan — pin it directly through an observable
> side effect. Only the one test named after the bounded search failed
> to test the bounded search's boundary.

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/python -m pytest tests/test_logic_run.py -q -k "splice or fork or bounded or search"
```

Expected: FAIL with `left operand must be an integer, got boolean` — the fall-through to `_arithmetic` described in Task 3.

- [ ] **Step 3: Implement the interception**

In `src/matrixlang/interpreter.py`, add a module-level tuple next to `_EQUALITY_OPS` and `_ORDERING_OPS`:

```python
_LOGICAL_OPS = (TokenType.SPLICE, TokenType.FORK)
```

In `_evaluate`, insert a branch **before** the existing `Binary` branch:

```python
        if isinstance(expr, Binary) and expr.op in _LOGICAL_OPS:
            # Intercepted HERE, not in _binary, and that is the whole
            # point: the Binary branch below evaluates both operands
            # before dispatching, so routing these through _binary would
            # give operators that work and do not short-circuit. Every
            # truth-table test would still pass, and the bounded search
            # `n < length xs splice xs[n] != target` would die at the
            # boundary with an out-of-bounds error.
            return self._logical(expr)
        if isinstance(expr, Binary):
            left = self._value_of(expr.left, expr)
            right = self._value_of(expr.right, expr)
            return self._binary(expr, left, right)
```

Add the helper next to `_binary`:

```python
    def _logical(self, expr: Binary) -> bool:
        """`splice` and `fork`, short-circuiting.

        The right operand is evaluated only when the left does not already
        decide the answer. That is what makes a bounded search safe:
        `n < length xs splice xs[n] != target` must not read xs[n] at the
        boundary.

        The cost, which is documented rather than hidden: an operand that
        is never evaluated is never type-checked, so `false splice 1` is
        false while `true splice 1` is an error.
        """
        left = self._value_of(expr.left, expr)
        self._require_bool(left, expr.left, expr.op)
        if expr.op is TokenType.SPLICE and not left:
            return False
        if expr.op is TokenType.FORK and left:
            return True
        right = self._value_of(expr.right, expr)
        self._require_bool(right, expr.right, expr.op)
        return right

    def _require_bool(self, value: object, node: Expr, op: TokenType) -> None:
        if not is_bool(value):
            raise RuntimeErrorML(
                f"'{_OP_WORDS[op]}' takes booleans, got {type_name(value)}",
                node.line,
                node.column,
            )
```

and the spelling table next to `_LOGICAL_OPS`:

```python
# The operator's own word, for its diagnostic. Not render._OPS: importing
# render into the interpreter would put a presentation module underneath
# execution, which tests/test_architecture.py forbids.
_OP_WORDS = {TokenType.SPLICE: "splice", TokenType.FORK: "fork"}
```

- [ ] **Step 4: Run the tests**

```bash
.venv/bin/python -m pytest tests/test_logic_run.py -q
```

Expected: PASS.

- [ ] **Step 5: Teeth-check the interception — MANDATORY**

Temporarily delete the `_LOGICAL_OPS` branch from `_evaluate` and instead add the operators to `_binary`, so they evaluate without short-circuiting:

```python
        if node.op is TokenType.SPLICE:
            return bool(left) and bool(right)
        if node.op is TokenType.FORK:
            return bool(left) or bool(right)
```

Then run:

```bash
.venv/bin/python -m pytest tests/test_logic_run.py -q -k "bounded_search"
```

Expected: **FAIL**, and the failure must be `index 3 is past the end of a list of length 3` — an out-of-bounds error, **not** an assertion mismatch. Note that `test_splice_is_and` and `test_fork_is_or` will still **pass** under this broken version; that is the point of the check, and worth stating in your report.

Paste the real output. **Restore with an editor, not `git checkout`** — other files may have uncommitted work.

- [ ] **Step 6: Run the full suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/matrixlang/interpreter.py tests/test_logic_run.py
git commit -m "feat: splice and fork short-circuit, which is what makes the guard idiom safe"
```

---

## Task 5: The generator, and the property that guards the renumbering

**Files:**
- Modify: `tests/treegen.py`, `tests/test_roundtrip.py`
- Test: the meta-test is the deliverable

**Interfaces:**
- Consumes: all three operators (Tasks 1–3).
- Produces: coverage.

**Why this is load-bearing rather than coverage-padding.** Task 2 renumbered every entry in `render._LEVEL`. There is no `Grouping` node, so that table alone decides where parentheses are reconstructed, and the only thing that makes a mistake in it loud is the 300-seed round trip — which guards nothing for these operators if the generator never emits them.

- [ ] **Step 1: Write the failing meta-test**

Append to `tests/test_roundtrip.py`:

```python
def test_the_generator_produces_the_stage_9_shapes_too():
    # Same reasoning as the earlier coverage meta-tests. Stage 9
    # renumbered every level in render._LEVEL; the round trip is the only
    # guard on that, and it guards nothing if these operators never
    # appear in a generated tree.
    from matrixlang.nodes import Binary, Unary
    from matrixlang.tokens import TokenType

    splice = False
    fork = False
    unplug = False
    unplug_over_binary = False
    fork_over_splice = False
    logical_over_comparison = False

    def walk_expr(expr):
        nonlocal splice, fork, unplug
        nonlocal unplug_over_binary, fork_over_splice, logical_over_comparison
        if isinstance(expr, Binary):
            if expr.op is TokenType.SPLICE:
                splice = True
            if expr.op is TokenType.FORK:
                fork = True
                if isinstance(expr.right, Binary) and expr.right.op is TokenType.SPLICE:
                    fork_over_splice = True
            if expr.op in (TokenType.SPLICE, TokenType.FORK):
                for side in (expr.left, expr.right):
                    if isinstance(side, Binary) and side.op in (
                        TokenType.EQ,
                        TokenType.NEQ,
                        TokenType.LT,
                        TokenType.GT,
                        TokenType.LTE,
                        TokenType.GTE,
                    ):
                        logical_over_comparison = True
            walk_expr(expr.left)
            walk_expr(expr.right)
        elif isinstance(expr, Unary):
            if expr.op is TokenType.UNPLUG:
                unplug = True
                if isinstance(expr.operand, Binary):
                    unplug_over_binary = True
            walk_expr(expr.operand)
        elif isinstance(expr, ListLiteral):
            for element in expr.elements:
                walk_expr(element)
        elif isinstance(expr, Index):
            walk_expr(expr.target)
            walk_expr(expr.index)
        elif isinstance(expr, Call):
            walk_expr(expr.callee)
            for arg in expr.args:
                walk_expr(arg)

    def walk_stmt(stmt):
        for field in ("value", "condition", "target", "index"):
            if hasattr(stmt, field) and getattr(stmt, field) is not None:
                walk_expr(getattr(stmt, field))
        for name in ("body", "then_body"):
            for child in getattr(stmt, name, []) or []:
                walk_stmt(child)
        for child in getattr(stmt, "else_body", None) or []:
            walk_stmt(child)

    for seed in range(300):
        for statement in gen_program(random.Random(seed)).statements:
            walk_stmt(statement)

    assert splice, "no splice in 300 seeds"
    assert fork, "no fork in 300 seeds"
    assert unplug, "no unplug in 300 seeds"
    assert unplug_over_binary, "no `unplug (a == b)` shape in 300 seeds"
    assert fork_over_splice, "no `a fork (b splice c)` shape in 300 seeds"
    assert logical_over_comparison, "no logical-over-comparison shape in 300 seeds"
```

`tests/test_roundtrip.py:17` currently reads `from matrixlang.nodes import Binary, Call, If, Unary` — verified. Add `Index` and `ListLiteral` to it; `Binary`, `Call` and `Unary` are already there.

- [ ] **Step 2: Run to verify failure**

```bash
.venv/bin/python -m pytest tests/test_roundtrip.py -q -k stage_9
```

Expected: FAIL with `no splice in 300 seeds`.

- [ ] **Step 3: Teach the generator**

`tests/treegen.py` already imports `TokenType` (line 46) and already has `gen_call`, `gen_list`, `gen_index` and `gen_atom` from Stages 7 and 8 — verified, so no new helper is needed. Only `gen_expression`'s thresholds change. Replace its body with:

```python
def gen_expression(rng: random.Random, depth: int) -> Expr:
    if depth == 0:
        return gen_atom(rng)
    roll = rng.random()
    if roll < 0.28:
        # Both children draw from the full depth-1 space, so equal-
        # precedence right children (R-PAREN-2) and nested chains occur
        # constantly rather than by luck.
        return Binary(
            gen_expression(rng, depth - 1),
            rng.choice(_BINARY_OPS),
            gen_expression(rng, depth - 1),
        )
    if roll < 0.40:
        # splice and fork, drawing both children from the full space so
        # `a fork (b splice c)` and logical-over-comparison shapes occur.
        # These are the shapes that catch a wrong level in render._LEVEL,
        # which Stage 9 renumbered end to end.
        return Binary(
            gen_expression(rng, depth - 1),
            rng.choice([TokenType.SPLICE, TokenType.FORK]),
            gen_expression(rng, depth - 1),
        )
    if roll < 0.50:
        # All three unary operators. unplug over a binary is the shape
        # that would render as `unplug a == b` re-parsing differently if
        # its level were wrong.
        return Unary(
            rng.choice([TokenType.MINUS, TokenType.LENGTH, TokenType.UNPLUG]),
            gen_expression(rng, depth - 1),
        )
    if roll < 0.60:
        # Calls, with arguments drawn from the full space so f(a + b)
        # occurs constantly rather than by luck.
        return gen_call(rng, depth - 1)
    if roll < 0.72:
        return gen_list(rng, depth - 1)
    if roll < 0.82:
        return gen_index(rng, depth - 1)
    return gen_atom(rng)
```

Update the module docstring's coverage paragraph to name the Stage 9 shapes alongside the others.

- [ ] **Step 4: Run the meta-test and the property test**

```bash
.venv/bin/python -m pytest tests/test_roundtrip.py -q
```

Expected: PASS — including the pre-existing 300-seed round trip, now exercising the renumbered table with logical operators in it, and the three earlier coverage meta-tests, which must not have been starved by the rebalance.

- [ ] **Step 5: Teeth-check the generator**

Temporarily change the `splice`/`fork` branch to always produce `TokenType.SPLICE`, then:

```bash
.venv/bin/python -m pytest tests/test_roundtrip.py -q -k stage_9
```

Expected: FAIL with `no fork in 300 seeds`. **Restore with an editor, not `git checkout`.**

- [ ] **Step 6: Run the full suite and commit**

```bash
.venv/bin/python -m pytest -q
git add tests/
git commit -m "test: the round-trip generator produces the Stage 9 shapes"
```

---

## Task 6: The documentation

**Files:**
- Modify: `docs/LEARNING-MATRIXLANG.md`, `README.md`, `docs/TECHNICAL-OVERVIEW.md`, `src/matrixlang/operator/prompt.py`
- Test: `tests/test_operator_prompt.py` (the existing guard should catch omissions), manual verification of every example

**Interfaces:**
- Consumes: the whole working feature.
- Produces: shipped documentation.

**`operator/prompt.py` is in this task's file list on purpose.** It was forgotten in the Stage 7 plan and again in the Stage 8 plan; Stage 8 added a guard test asserting the prompt mentions every keyword and type name. That guard should fail the moment Task 1 adds three keywords — if it does not, say so in your report, because it means the guard is weaker than intended.

**The documentation standard.** Every code example must be **executed and its stated output pasted from the real run**, never predicted. The tutorial was held to this originally, and reviewers have independently re-run its examples byte-for-byte in each of the last two stages.

- [ ] **Step 1: Verify through the real CLI**

```bash
cat > /tmp/logic-demo.rain <<'RAIN'
construct crew = ["Neo", "Trinity", "Tank"]
construct n = 0
dejavu n < length crew splice crew[n] != "Tank"
  n = n + 1
flatline

redpill unplug (n == length crew)
  trace "found at"
  trace n
bluepill
  trace "not found"
flatline
RAIN
.venv/bin/matrixlang run --no-window /tmp/logic-demo.rain
.venv/bin/matrixlang parse /tmp/logic-demo.rain
.venv/bin/matrixlang render --face glyph /tmp/logic-demo.rain
.venv/bin/matrixlang render --face glyph /tmp/logic-demo.rain > /tmp/logic-glyph.rain
.venv/bin/matrixlang render --face ascii /tmp/logic-glyph.rain
```

Expected: `found at` then `2`; a tree with no traceback; a glyph render containing none of the words `splice`, `fork` or `unplug`; and an ascii render of the glyph file byte-identical to the original. Paste the real output into your report.

- [ ] **Step 2: Update the Operator prompt**

In `src/matrixlang/operator/prompt.py`, read the whole file and match its voice. Add a rule covering `splice`, `fork` and `unplug`: what they mean, that operands must be booleans, that they short-circuit, and that `unplug` binds looser than comparison so `unplug n == 1` is `unplug (n == 1)`. Consider whether `_EXAMPLE` should show the bounded search, which is the idiom the stage exists for.

Run `tests/test_operator_prompt.py` before and after, and report whether the guard test caught the omission on its own.

- [ ] **Step 3: Extend the tutorial**

Read `docs/LEARNING-MATRIXLANG.md` fully and decide placement — the requirement is that it teaches well. Cover:

- the three operators and their truth tables
- **the bounded search**, which is why they exist; show the version that works
- `unplug` binding looser than comparison, with `unplug n == 1` spelled out
- **short-circuit**, and the asymmetry it creates: `false splice 1` is `false` while `true splice 1` is an error

Update the file's opening line: the keyword count goes from eleven to **fourteen**. Types are unchanged at four.

Add the three glyphs to the §9 table and update its slot count to 41.

Amend the "What the language does not have" list — `no and, or, or not` is now false.

Every example executed.

- [ ] **Step 4: Update the README and technical overview**

`README.md`: add the operators to the "Working today" paragraph and update the test count.

`docs/TECHNICAL-OVERVIEW.md`:
- Header counts — lines, modules, tests. Recompute with `find`/`wc -l`, do not guess.
- §4 — the keyword count, and a bullet on short-circuit and the type-check asymmetry it creates.
- §9 (deliberately absent) — logical operators must come off the list. `else if`, `break`/`continue`, `xor`, and slicing are what remain; note which is now the largest gap.
- Consider a paragraph beside the existing §5 material on the interception point: the obvious home for two new binary operators produces operators that work and do not short-circuit, and the teeth-check is what proves the interception is load-bearing. It is the third stage in a row with a "the obvious edit is wrong and looks right" story, which is worth saying explicitly.

- [ ] **Step 5: Verify every documentation example**

Write a throwaway script in your scratch area that extracts each fenced block from the new documentation, runs it, and asserts the stated output. Report the count checked and the result.

- [ ] **Step 6: Run the full suite and commit**

```bash
.venv/bin/python -m pytest -q
git add -A
git commit -m "docs: teach splice, fork and unplug, and the short-circuit asymmetry"
```

**Do not push and do not open a pull request.** The controller does that after a final whole-branch review.

---

## Self-Review

**Spec coverage.** Every section of the design spec maps to a task:

| Spec | Task |
| --- | --- |
| §1 Vocabulary and the naming trade | 1 (the glyphs and the comment recording it) |
| §2 Short-circuit is forced | 4 |
| §2 The asymmetry it creates | 4 (`test_an_unevaluated_operand_is_never_type_checked`), 6 (documenting it) |
| §3 Precedence ladder | 2 (`unplug`), 3 (`fork`/`splice`) |
| §3 `unplug` reuses the node but not the level | 2 |
| §3 The renumbering | 2 — done once, in full |
| §4 What it touches | 1, 2, 3, 4 |
| §5 The hazard | 4, including the mandatory teeth-check |
| §6 Testing, items 1–7 | 4 (teeth-check), 2 and 3 (tree-shape precedence), 4 (asymmetry), 5 (generator), 2 and 4 (non-boolean errors), Global Constraints (baseline) |
| §7 Out of scope | 6 documents the exclusions |

**Placeholder scan.** No TBD, no "handle edge cases", no "similar to Task N". Every code step carries the actual code and every insertion point names a real line.

Two places deliberately leave judgement to the implementer, each with the reason stated: Task 6 Step 3 leaves the tutorial's placement to whoever reads the file, because "teaches well" is the requirement; Task 6 Step 2 asks whether `_EXAMPLE` should gain the bounded search, because that is a judgement about prompt length versus signal.

**Type consistency.** `_LOGICAL_OPS`, `_OP_WORDS`, `_logical(expr)`, `_require_bool(value, node, op)`, `_NOT_LEVEL`, `_FORK_OPS`, `_SPLICE_OPS`, `_fork()`, `_splice()`, `_not()` — each name is used identically everywhere it appears. `unplug` is `Unary(TokenType.UNPLUG, operand)` in Tasks 2, 5 and 6 alike; `splice`/`fork` are `Binary` throughout.

**Every assumption in this plan was checked against the code before it was committed**, which is how the last two plans' self-contradictions were caught. Confirmed: `interpreter.py` already imports `is_bool` (line 47); `tests/test_architecture.py:44` pins `"interpreter": {"errors", "events", "nodes", "tokens", "values"}`, so importing `render` for the operator spellings would fail the architecture test — hence the local `_OP_WORDS` table; `treegen.py` already imports `TokenType` and already has `gen_call`/`gen_list`/`gen_index`/`gen_atom`; and `test_roundtrip.py:17` imports `Binary, Call, If, Unary`, so exactly `Index` and `ListLiteral` need adding.

**Three things this plan does that earlier ones learned the hard way.**

1. **The error messages are named once**, in Global Constraints, and every test asserts against that table by exact string. Stage 7 specified a message and its test separately, they contradicted each other, and a substring assertion that could not fail survived to the final review.
2. **`operator/prompt.py` is in Task 6's file list.** It was missing from both the Stage 7 and Stage 8 plans and had to be fixed in each final review. Stage 8 added a guard test; this plan also asks the implementer to report whether that guard fired on its own, which is the only way to learn whether it works.
3. **The precedence table is renumbered once, not twice.** Task 2 installs the final numbering including two rows it does not use yet, so the 300-seed property validates the target table immediately rather than validating two intermediate ones.
