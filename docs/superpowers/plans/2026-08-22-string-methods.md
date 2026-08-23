# String Methods Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give MatrixLang three string operations — `fold` (lower-case), `trim` (strip), `cleave` (split) — and teach the Python translator to reach them.

**Architecture:** Three new keywords, no new AST node types. `fold` and `trim` are `Unary` nodes at the existing `_unary` rung; `cleave` is a `Binary` node at a NEW precedence rung between `_comparison` and `_term`. The lexer needs no change at all — it is table-driven off `tokens.KEYWORDS` and `glyphs.GLYPHS` (`lexer.py:45-51`), so registering the words there makes both faces lex. Everything else is a table entry: `render._OPS`, `render._LEVEL`, `treeview._OPS`, and `treegen`'s two operator lists.

**Tech Stack:** Python 3.11+, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-22-string-methods-design.md`
**Issue:** #132
**Register:** `docs/PYTHON-PARITY.md`, item 1

## Environment

This worktree has **no `.venv` of its own** — the virtualenv lives in the main checkout. Every command in this plan uses the interpreter that is already on PATH:

```bash
PYTHONPATH=src python3 -m pytest -q
```

Baseline at the time of writing: **1784 passed in ~18s.** If your baseline differs before you change anything, stop and say so.

## Global Constraints

- **The three keywords are `fold`, `trim`, `cleave`.** Exactly those spellings.
- **Glyph assignments, fixed:** `fold` → `ﾊ` (U+FF8A), `trim` → `ﾘ` (U+FF98), `cleave` → `ﾛ` (U+FF9B). These three are free today; the other four free slots (`ｰ` U+FF70, `ﾉ` U+FF89, `ﾕ` U+FF95, `ﾝ` U+FF9D) stay free.
- **Glyph budget: 49 → 52 slots used, 7 → 4 free.** `tests/test_glyphs.py` tracks this by hand on purpose. Its ledger comment gains the step `7 - 3 = 4`.
- **Keyword count: 19 → 22.** `tests/test_tokens.py::test_all_nineteen_keywords_are_registered` carries the count in its NAME and must be renamed as well as extended.
- **No new AST node types.** `fold`/`trim` are `Unary`; `cleave` is `Binary`. If a task finds itself adding a node class, it is off-plan — stop and escalate.
- **`fold` is `str.lower()`, never `str.casefold()`.** Verified: `"STRAßE".lower()` is `"straße"`, `"STRAßE".casefold()` is `"strasse"`. The translator maps Python's `.lower()` onto `fold`, so the two must agree. A comment must say so at the implementation site, because the NAME points the other way and a future reader "correcting" it would break agreement with Python silently.
- **`trim` is bare `str.strip()`** — all Unicode whitespace. It must NOT reuse `interpreter._DECODE_SPACE`, which is `string.whitespace` (ASCII-only, deliberately, because `decode` validates a number grammar). The two differ on U+00A0, the non-breaking space: `str.strip()` removes it, `string.whitespace` does not contain it. A comment must say which is which, or the next reader will "unify" them and silently break agreement with Python's `.strip()`.
- **`cleave`'s edges are CPython's**, verified rather than assumed:

  | Expression | Result |
  | --- | --- |
  | `"a,,b" cleave ","` | `["a", "", "b"]` |
  | `"" cleave ","` | `[""]` — one empty string, **not** an empty list |
  | `"abc" cleave ","` | `["abc"]` |
  | `"abc" cleave ""` | **error** — CPython raises `ValueError: empty separator` |

- **Every type failure is a positioned `RuntimeErrorML`** naming the operator and the type it got, in the shape `interpreter.py` already uses: `f"'fold' takes a string, got {type_name(operand)}"`. No Python exception may escape the interpreter — `site/glue.py`'s `run()` promises never to raise, and that promise has been broken five times in this project's history.
- **All three must enter `tests/treegen.py` in the same change that adds them,** and the corpus must be **counted**, not assumed. The 300-seed round-trip property only covers node shapes the generator produces; `decode` and `encode` sat outside it for their entire existence while it stayed green. A zero count means the property is green while proving nothing.
- **`operator/prompt.py` must gain a rule covering all three.** `tests/test_operator_prompt.py::test_every_keyword_is_explained_or_demonstrated` asserts against `_RULES + _EXAMPLE` directly and goes red the moment a keyword is registered without one. This is why the prompt change lives in Task 1 rather than with the docs.
- **The full suite must be green at the end of every task.**
- **The string lexer has only three escapes** — `\\`, `\"`, `\n` (`lexer._ESCAPES`). There is no `\t`. Any test source that wants a tab must not use one.

---

## File Structure

| File | Change | Task |
| --- | --- | --- |
| `src/matrixlang/tokens.py` | 3 `TokenType` members, 3 `KEYWORDS` entries | 1 |
| `src/matrixlang/glyphs.py` | 3 glyph assignments | 1 |
| `src/matrixlang/operator/prompt.py` | one rule in `_RULES` | 1 |
| `tests/test_tokens.py` | rename + extend the keyword-set test | 1 |
| `tests/test_glyphs.py` | 49 → 52, 7 → 4, ledger comment | 1 |
| `tests/test_strings_lex.py` | **new** — both faces lex | 1 |
| `src/matrixlang/parser.py` | `_unary` gains 2; new `_cleave` rung | 2 |
| `tests/test_strings_parse.py` | **new** — precedence | 2 |
| `src/matrixlang/interpreter.py` | 2 `Unary` branches, 1 `Binary` branch | 3 |
| `tests/test_strings_run.py` | **new** — semantics and every refusal | 3 |
| `src/matrixlang/render.py` | `_OPS` +3, `_LEVEL` renumbered, word-unary tuple +2 | 4 |
| `src/matrixlang/treeview.py` | `_OPS` +3 | 4 |
| `tests/treegen.py` | unary list +2, `_BINARY_OPS` +1 | 4 |
| `tests/test_strings_render.py` | **new** — both faces, parens | 4 |
| `tests/test_roundtrip.py` | unary set +2, **counted** cleave corpus | 4 |
| `src/matrixlang/pytrans/translate.py` | `.lower()`, `.strip()`, `.split(sep)`; refuse `.upper()`, bare `.split()` | 5 |
| `tests/test_pytrans_expr.py` | the three mappings | 5 |
| `tests/test_pytrans_refuse.py` | the refusals | 5 |
| `tests/test_pytrans_differential.py` | **the products program**, run against Python | 5 |
| `README.md`, `docs/LEARNING-MATRIXLANG.md`, `docs/TECHNICAL-OVERVIEW.md`, `docs/PYTHON-PARITY.md` | counts, table, a teaching section, register | 6 |

---

### Task 1: Vocabulary — tokens, glyphs, and the Operator prompt

The lexer is table-driven: `lexer.py:45-51` walks `GLYPHS` and looks each slot up in `KEYWORDS`. Registering the words in those two files is the whole of "it lexes in both faces." The new test proves that claim rather than assuming it.

**Files:**
- Modify: `src/matrixlang/tokens.py`
- Modify: `src/matrixlang/glyphs.py`
- Modify: `src/matrixlang/operator/prompt.py` (`_RULES`, around line 60-104)
- Modify: `tests/test_tokens.py:4-29`
- Modify: `tests/test_glyphs.py:7-45`
- Test: `tests/test_strings_lex.py` (create)

**Interfaces:**
- Produces: `TokenType.FOLD`, `TokenType.TRIM`, `TokenType.CLEAVE`; `KEYWORDS["fold"|"trim"|"cleave"]`; `GLYPHS["fold"|"trim"|"cleave"]`. Every later task consumes these names.

- [ ] **Step 1: Write the failing lexer test**

Create `tests/test_strings_lex.py`:

```python
"""String methods — lexing fold, trim and cleave in both faces."""

from matrixlang.lexer import lex
from matrixlang.tokens import KEYWORDS, TokenType


def test_the_three_words_are_keywords():
    types = [t.type for t in lex("fold trim cleave\n")]
    assert types[:3] == [TokenType.FOLD, TokenType.TRIM, TokenType.CLEAVE]


def test_the_three_words_lex_in_the_glyph_face():
    # The glyph face must lex to the same tokens as the ASCII face, or
    # D-03's round-trip claim is false for these three keywords.
    types = [t.type for t in lex("ﾊ ﾘ ﾛ\n")]
    assert types[:3] == [TokenType.FOLD, TokenType.TRIM, TokenType.CLEAVE]


def test_a_name_that_merely_starts_with_a_keyword_is_still_a_name():
    # `folder` must not lex as `fold` followed by `er`. The lexer reads a
    # whole word and looks it up, so this holds by construction -- but it
    # is the failure that would turn `construct folder = 1` into a parse
    # error in somebody's existing program, so it is worth pinning.
    types = [t.type for t in lex("folder trimmed cleaver\n")]
    assert types[:3] == [TokenType.IDENT, TokenType.IDENT, TokenType.IDENT]


def test_registration_is_all_the_lexer_needs():
    # lexer.py builds its glyph table by walking GLYPHS and looking each
    # slot up in KEYWORDS, so registering a word in tokens.py and
    # glyphs.py is the whole of adding it to both faces. This asserts the
    # mechanism rather than the outcome: a future refactor that hard-codes
    # a keyword list somewhere else fails here with a reason.
    for word in ("fold", "trim", "cleave"):
        assert word in KEYWORDS
```

- [ ] **Step 2: Run it to make sure it fails**

```bash
PYTHONPATH=src python3 -m pytest tests/test_strings_lex.py -q
```

Expected: FAIL with `AttributeError: FOLD` — the enum member does not exist yet.

- [ ] **Step 3: Register the three token types**

In `src/matrixlang/tokens.py`, in the `# Keywords` block of `class TokenType`, after `ORACLE = auto()`:

```python
    FOLD = auto()
    TRIM = auto()
    CLEAVE = auto()
```

And at the end of the `KEYWORDS` dict, after `"oracle": TokenType.ORACLE,`:

```python
    "fold": TokenType.FOLD,
    "trim": TokenType.TRIM,
    "cleave": TokenType.CLEAVE,
```

- [ ] **Step 4: Assign the three glyphs**

In `src/matrixlang/glyphs.py`, after the `"oracle": "ｵ",` line and before the `# operators` comment:

```python
    # String methods. `trim` takes ﾘ, the "ri" of its own katakana
    # spelling ﾄﾘﾑ -- ﾄ and ﾑ were long gone, so the middle sound is what
    # was left. `fold` and `cleave` take ﾊ and ﾛ arbitrarily: every sound
    # in ﾌｫｰﾙﾄﾞ and ｸﾘｰﾌﾞ was already spent, which is what a 56-slot block
    # looks like by its 52nd entry.
    "fold": "ﾊ",
    "trim": "ﾘ",
    "cleave": "ﾛ",
```

- [ ] **Step 5: Run the lexer test to verify it passes**

```bash
PYTHONPATH=src python3 -m pytest tests/test_strings_lex.py -q
```

Expected: PASS, 4 tests.

- [ ] **Step 6: Update the two hand-tracked ledgers**

In `tests/test_tokens.py`, rename the test and extend its set. The name carries the count, so leaving it at `nineteen` while asserting twenty-two entries is exactly the stale ledger this project hand-tracks to avoid:

```python
def test_all_twenty_two_keywords_are_registered():
    assert set(KEYWORDS) == {
        "construct",
        "trace",
        "redpill",
        "bluepill",
        "dejavu",
        "flatline",
        "true",
        "false",
        # Stage 6
        "agent",
        "jackout",
        # Stage 7
        "length",
        # Stage 9
        "splice",
        "fork",
        "unplug",
        # Input
        "jackin",
        "decode",
        "encode",
        # Dictionaries
        "keymaker",
        "oracle",
        # String methods
        "fold",
        "trim",
        "cleave",
    }
```

In `tests/test_glyphs.py`, rename `test_the_table_covers_exactly_the_49_slots` to `test_the_table_covers_exactly_the_52_slots`, add a line to its comment block immediately before `# Nothing more`:

```python
    # + string methods: fold, trim and cleave.
```

and change the count assertion:

```python
    assert len(expected) == 52
```

In `test_the_glyph_budget_is_tracked_not_discovered`, append to the ledger comment immediately before `# Finite, and worth knowing.`:

```python
    # String methods spend 3 -- fold, trim and cleave -- so 7 - 3 = 4
    # left. Four slots is the language's entire remaining budget.
```

and change the assertion:

```python
    assert free == 4
```

- [ ] **Step 7: Run both ledger tests**

```bash
PYTHONPATH=src python3 -m pytest tests/test_tokens.py tests/test_glyphs.py -q
```

Expected: PASS.

- [ ] **Step 8: Run the whole suite to find what else went red**

```bash
PYTHONPATH=src python3 -m pytest -q
```

Expected: exactly ONE failure — `tests/test_operator_prompt.py::test_every_keyword_is_explained_or_demonstrated`, reporting `never explained or shown: ['cleave', 'fold', 'trim']`. That test asserts against `_RULES + _EXAMPLE` directly rather than against `build()`, precisely so a new keyword cannot slip in unexplained.

If anything ELSE is red, stop and report it — this plan expects that one and only that one.

- [ ] **Step 9: Add the prompt rule**

In `src/matrixlang/operator/prompt.py`, inside `_RULES`, immediately after the bullet beginning `- A string can be indexed too:` and before the dictionary bullet:

```
- Three string operations. `fold s` lower-cases, `trim s` removes
  whitespace from both ends, and the infix `s cleave sep` splits on a
  separator and gives a list — `"a,b" cleave ","` is `["a", "b"]`. All
  three take strings and nothing else. There is no upper-casing
  operator: to compare two strings ignoring case, `fold` both sides. A
  separator with nothing in it is an error, not a character-by-character
  split.
```

- [ ] **Step 10: Run the suite green**

```bash
PYTHONPATH=src python3 -m pytest -q
```

Expected: PASS, no failures.

- [ ] **Step 11: Commit**

```bash
git add src/matrixlang/tokens.py src/matrixlang/glyphs.py src/matrixlang/operator/prompt.py tests/test_tokens.py tests/test_glyphs.py tests/test_strings_lex.py
git commit -m "feat: register fold, trim and cleave — 52 glyph slots, 4 free"
```

---

### Task 2: Parser — where the three operators bind

`fold` and `trim` join `_unary` beside `length`, `decode`, `encode` and `keymaker`: they PRODUCE a value that later operations consume, which is the stated reason those four sit there rather than at `_not`'s level. `cleave` gets a rung of its own between `_comparison` and `_term`, which makes both natural readings come out with no parentheses.

**Files:**
- Modify: `src/matrixlang/parser.py` — the operator tuples around line 96, the ladder at 425-432, `_unary` at 444-472
- Test: `tests/test_strings_parse.py` (create)

**Interfaces:**
- Consumes: `TokenType.FOLD`, `TokenType.TRIM`, `TokenType.CLEAVE` from Task 1.
- Produces: `Unary(TokenType.FOLD, operand)`, `Unary(TokenType.TRIM, operand)`, `Binary(left, TokenType.CLEAVE, right)`. Tasks 3, 4 and 5 consume exactly these shapes.

- [ ] **Step 1: Write the failing parser test**

Create `tests/test_strings_parse.py`:

```python
"""String methods — where fold, trim and cleave bind."""

from matrixlang.lexer import lex
from matrixlang.nodes import Binary, Unary
from matrixlang.parser import parse, parse_expression
from matrixlang.tokens import TokenType


def expr(source):
    return parse_expression(lex(source))


def test_fold_is_a_unary_operator():
    tree = expr("fold s")
    assert isinstance(tree, Unary)
    assert tree.op is TokenType.FOLD


def test_trim_is_a_unary_operator():
    tree = expr("trim s")
    assert isinstance(tree, Unary)
    assert tree.op is TokenType.TRIM


def test_cleave_is_infix():
    tree = expr('s cleave ","')
    assert isinstance(tree, Binary)
    assert tree.op is TokenType.CLEAVE


def test_fold_binds_tighter_than_plus():
    # `fold a + b` is `(fold a) + b`, the same reading `length`, `decode`,
    # `encode` and `keymaker` already get: these operators PRODUCE a value
    # that the arithmetic then consumes.
    tree = expr("fold a + b")
    assert tree.op is TokenType.PLUS
    assert isinstance(tree.left, Unary)
    assert tree.left.op is TokenType.FOLD


def test_trim_binds_tighter_than_equality():
    # `trim a == b` is `(trim a) == b`. The loose reading would ask trim
    # for a boolean, which is an error for every possible a and b.
    tree = expr("trim a == b")
    assert tree.op is TokenType.EQ
    assert isinstance(tree.left, Unary)
    assert tree.left.op is TokenType.TRIM


def test_fold_over_fold_nests():
    tree = expr("fold fold s")
    assert tree.op is TokenType.FOLD
    assert tree.operand.op is TokenType.FOLD


def test_fold_over_trim_nests():
    tree = expr("fold trim s")
    assert tree.op is TokenType.FOLD
    assert tree.operand.op is TokenType.TRIM


def test_cleave_binds_looser_than_plus():
    # `a + b cleave ","` is `(a + b) cleave ","` -- concatenate, THEN
    # split. This is why cleave's rung sits below _term.
    tree = expr('a + b cleave ","')
    assert tree.op is TokenType.CLEAVE
    assert isinstance(tree.left, Binary)
    assert tree.left.op is TokenType.PLUS


def test_cleave_binds_tighter_than_equality():
    # `s cleave "," == xs` is `(s cleave ",") == xs` -- comparison is
    # looser. This is why cleave's rung sits above _comparison.
    tree = expr('s cleave "," == xs')
    assert tree.op is TokenType.EQ
    assert isinstance(tree.left, Binary)
    assert tree.left.op is TokenType.CLEAVE


def test_cleave_binds_tighter_than_ordering():
    tree = expr('s cleave "," < xs')
    assert tree.op is TokenType.LT
    assert tree.left.op is TokenType.CLEAVE


def test_cleave_binds_tighter_than_oracle():
    # `oracle` shares the comparison rung, so it must land on the same
    # side of cleave as `==` does.
    tree = expr('d oracle s cleave ","')
    assert tree.op is TokenType.ORACLE
    assert tree.right.op is TokenType.CLEAVE


def test_cleave_is_left_associative():
    # Nonsense as a program -- the outer cleave's left operand is a list
    # -- but the SHAPE is what a left-associative rung must produce, and
    # the parser never runs anything.
    tree = expr("a cleave b cleave c")
    assert tree.op is TokenType.CLEAVE
    assert isinstance(tree.left, Binary)
    assert tree.left.op is TokenType.CLEAVE
    assert tree.right.ident == "c"


def test_a_unary_word_over_a_cleave_needs_its_parens():
    # `length keymaker d` already has this shape: a prefix word binds
    # tightest, so reaching a binary result takes parentheses.
    tree = expr('length (s cleave ",")')
    assert tree.op is TokenType.LENGTH
    assert isinstance(tree.operand, Binary)
    assert tree.operand.op is TokenType.CLEAVE


def test_the_operators_work_in_a_whole_program():
    program = parse(lex('trace fold "Mouse"\n'))
    assert program.statements[0].value.op is TokenType.FOLD
```

- [ ] **Step 2: Run it to make sure it fails**

```bash
PYTHONPATH=src python3 -m pytest tests/test_strings_parse.py -q
```

Expected: FAIL with a `ParseError` — `fold` is a keyword now, and no grammar rule accepts it.

- [ ] **Step 3: Add the cleave rung**

In `src/matrixlang/parser.py`, beside the other operator tuples (after `_COMPARISON_OPS`, before `_TERM_OPS`):

```python
# `cleave` gets a rung of its own between comparison and term. Above
# comparison so `s cleave "," == xs` compares the LIST, and below term so
# `a + b cleave ","` concatenates before it splits. Both are the natural
# reading, and this is the only placement that gives both without
# parentheses.
_CLEAVE_OPS = (TokenType.CLEAVE,)
```

Then point `_comparison` at the new rung and add the rung itself:

```python
    def _comparison(self) -> Expr:
        return self._binary_level(_COMPARISON_OPS, self._cleave)

    def _cleave(self) -> Expr:
        return self._binary_level(_CLEAVE_OPS, self._term)
```

`_term` is unchanged — it still calls `self._factor`.

- [ ] **Step 4: Add fold and trim to `_unary`**

In `_unary`, extend the check chain and the explanatory comment. Append to the existing comment block:

```python
        # `fold` and `trim` join on the same argument: each produces a
        # string, so `fold a + b` is `(fold a) + b` and `trim a == b` is
        # `(trim a) == b`. The loose reading of either would hand the
        # operator a value it cannot take, for every possible operand.
```

and extend the condition:

```python
        if (
            self.check(TokenType.MINUS)
            or self.check(TokenType.LENGTH)
            or self.check(TokenType.DECODE)
            or self.check(TokenType.ENCODE)
            or self.check(TokenType.KEYMAKER)
            or self.check(TokenType.FOLD)
            or self.check(TokenType.TRIM)
        ):
```

The body of the branch is unchanged.

- [ ] **Step 5: Run the parser test to verify it passes**

```bash
PYTHONPATH=src python3 -m pytest tests/test_strings_parse.py -q
```

Expected: PASS, 14 tests.

- [ ] **Step 6: Run the whole suite**

```bash
PYTHONPATH=src python3 -m pytest -q
```

Expected: PASS. The renumbering `cleave` forces on `render._LEVEL` is Task 4's job — nothing outside these tests builds a `CLEAVE` node yet, and none of these tests render.

- [ ] **Step 7: Commit**

```bash
git add src/matrixlang/parser.py tests/test_strings_parse.py
git commit -m "feat: parse fold and trim at _unary, cleave on its own rung"
```

---

### Task 3: Interpreter — what the three operators do

**Files:**
- Modify: `src/matrixlang/interpreter.py` — the `Unary` branches at 425-484, and `_binary` at 734-770
- Test: `tests/test_strings_run.py` (create)

**Interfaces:**
- Consumes: `Unary(TokenType.FOLD|TRIM, operand)` and `Binary(left, TokenType.CLEAVE, right)` from Task 2.
- Produces: nothing later tasks import; Task 5's differential test runs these paths end to end.

- [ ] **Step 1: Write the failing interpreter test**

Create `tests/test_strings_run.py`:

```python
"""String methods — running fold, trim and cleave end to end."""

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


def test_fold_lower_cases():
    assert run('trace fold "Mouse"\n') == "mouse\n"


def test_fold_leaves_a_lower_case_string_alone():
    assert run('trace fold "mouse"\n') == "mouse\n"


def test_fold_is_lower_not_casefold():
    # The distinction is real and the NAME points the wrong way:
    # "STRAßE".lower() is "straße" but .casefold() is "strasse". The
    # translator maps Python's .lower() onto fold, so fold must be
    # .lower() or the two disagree on exactly this input.
    assert run('trace fold "STRAßE"\n') == "straße\n"


def test_trim_removes_whitespace_from_both_ends():
    assert run('trace "[" + trim "  hi  " + "]"\n') == "[hi]\n"


def test_trim_removes_newlines_too():
    assert run('trace "[" + trim "\\n hi \\n" + "]"\n') == "[hi]\n"


def test_trim_is_pythons_strip_not_decodes_ascii_only_one():
    # U+00A0 is whitespace to str.strip() but is NOT in string.whitespace,
    # which is what interpreter._DECODE_SPACE is. If trim were built on
    # _DECODE_SPACE the U+00A0s come back still attached, and a
    # translated program disagrees with the Python it came from.
    #
    # Written as an escape, never as a literal: a raw U+00A0 in a source
    # file is invisible, and the next editor to touch the line would
    # silently turn it into a plain space and delete the only thing this
    # test proves.
    nbsp = "\u00a0"
    source = f'trace "[" + trim "{nbsp} hi {nbsp}" + "]"\n'
    assert run(source) == "[hi]\n"


def test_trim_of_a_blank_string_is_empty():
    assert run('trace "[" + trim "   " + "]"\n') == "[]\n"


def test_cleave_splits_on_a_separator():
    assert run('trace "a,b,c" cleave ","\n') == '["a", "b", "c"]\n'


def test_cleave_keeps_empty_pieces():
    assert run('trace "a,,b" cleave ","\n') == '["a", "", "b"]\n'


def test_cleave_of_an_empty_string_is_one_empty_piece():
    # CPython: "".split(",") == [""], NOT []. Verified, not assumed.
    assert run('trace "" cleave ","\n') == '[""]\n'


def test_cleave_with_the_separator_absent_gives_the_whole_string():
    assert run('trace "abc" cleave ","\n') == '["abc"]\n'


def test_cleave_takes_a_multi_character_separator():
    assert run('trace "a::b" cleave "::"\n') == '["a", "b"]\n'


def test_cleave_with_an_empty_separator_is_an_error():
    # CPython raises ValueError("empty separator"). That must arrive as a
    # positioned MatrixLang error, not a Python exception escaping the
    # interpreter -- site/glue.py's run() promises never to raise.
    error = fails('trace "abc" cleave ""\n')
    assert "'cleave'" in error.message
    assert "separator" in error.message


@pytest.mark.parametrize(
    "operand,name",
    [
        ("1", "integer"),
        ("true", "boolean"),
        ('["a"]', "list"),
        ('{"a": 1}', "dictionary"),
    ],
)
def test_fold_refuses_every_non_string(operand, name):
    error = fails(f"trace fold {operand}\n")
    assert error.message == f"'fold' takes a string, got {name}"


@pytest.mark.parametrize(
    "operand,name",
    [
        ("1", "integer"),
        ("true", "boolean"),
        ('["a"]', "list"),
        ('{"a": 1}', "dictionary"),
    ],
)
def test_trim_refuses_every_non_string(operand, name):
    error = fails(f"trace trim {operand}\n")
    assert error.message == f"'trim' takes a string, got {name}"


@pytest.mark.parametrize(
    "left,name", [("1", "integer"), ("true", "boolean"), ('["a"]', "list")]
)
def test_cleave_refuses_a_non_string_on_the_left(left, name):
    error = fails(f'trace {left} cleave ","\n')
    assert error.message == f"'cleave' takes a string, got {name}"


@pytest.mark.parametrize(
    "right,name", [("1", "integer"), ("true", "boolean"), ('["a"]', "list")]
)
def test_cleave_refuses_a_non_string_separator(right, name):
    error = fails(f'trace "a,b" cleave {right}\n')
    assert error.message == f"'cleave' needs a string separator, got {name}"


def test_a_type_error_carries_the_operators_position():
    error = fails("trace 1\ntrace fold 2\n")
    assert error.line == 2


def test_the_three_compose_in_one_program():
    # `fold trim "  Mouse  " cleave "s"` is
    # `(fold (trim "  Mouse  ")) cleave "s"`. CPython:
    # "  Mouse  ".strip().lower().split("s") == ["mou", "e"].
    assert run('trace fold trim "  Mouse  " cleave "s"\n') == '["mou", "e"]\n'


def test_a_case_insensitive_comparison_works():
    source = 'construct a = "Mouse"\nconstruct b = "MOUSE"\ntrace fold a == fold b\n'
    assert run(source) == "true\n"
```

- [ ] **Step 2: Run it to make sure it fails**

```bash
PYTHONPATH=src python3 -m pytest tests/test_strings_run.py -q
```

Expected: FAIL. `fold`/`trim` fall through the `Unary` chain to `self._require_int(...)` and report the unary-minus message; `cleave` falls through `_binary` into `_arithmetic`.

- [ ] **Step 3: Implement fold and trim**

In `src/matrixlang/interpreter.py`, inside the `isinstance(expr, Unary)` branch, immediately after the `TokenType.KEYMAKER` block and before the `TokenType.DECODE` block:

```python
            if expr.op is TokenType.FOLD:
                if not is_str(operand):
                    raise RuntimeErrorML(
                        f"'fold' takes a string, got {type_name(operand)}",
                        expr.line,
                        expr.column,
                    )
                # str.lower(), NOT str.casefold(), despite the name.
                # "STRAßE".lower() is "straße"; .casefold() is "strasse".
                # The Python translator maps `.lower()` onto this
                # operator, so switching to casefold would make a
                # translated program and its original disagree on that
                # input, silently -- which is the one thing the
                # translator's governing rule exists to prevent.
                return operand.lower()
            if expr.op is TokenType.TRIM:
                if not is_str(operand):
                    raise RuntimeErrorML(
                        f"'trim' takes a string, got {type_name(operand)}",
                        expr.line,
                        expr.column,
                    )
                # Bare str.strip() -- all Unicode whitespace.
                # Deliberately NOT _DECODE_SPACE, which is ASCII-only
                # because `decode` is validating a number grammar against
                # text that came from outside. `trim` is trimming text for
                # a reader, and the translator maps Python's `.strip()`
                # onto it, so it has to agree with `.strip()` on U+00A0.
                return operand.strip()
```

- [ ] **Step 4: Implement cleave**

In `_binary`, immediately after the `TokenType.ORACLE` block and before the first `TokenType.PLUS` branch:

```python
        if node.op is TokenType.CLEAVE:
            if not is_str(left):
                raise RuntimeErrorML(
                    f"'cleave' takes a string, got {type_name(left)}",
                    node.line,
                    node.column,
                )
            if not is_str(right):
                raise RuntimeErrorML(
                    f"'cleave' needs a string separator, got "
                    f"{type_name(right)}",
                    node.line,
                    node.column,
                )
            if not right:
                # CPython raises ValueError("empty separator") here.
                # Nothing may escape this interpreter but MatrixLangError
                # -- site/glue.py's run() promises never to raise, and
                # that promise has been broken five times already.
                raise RuntimeErrorML(
                    "'cleave' needs a separator with something in it",
                    node.line,
                    node.column,
                )
            return left.split(right)
```

- [ ] **Step 5: Run the interpreter test to verify it passes**

```bash
PYTHONPATH=src python3 -m pytest tests/test_strings_run.py -q
```

Expected: PASS.

If an expected VALUE disagrees, do not change the implementation to match the test — recompute the expectation against CPython and fix the test:

```bash
python3 -c "print('  Mouse  '.strip().lower().split('s'))"
```

- [ ] **Step 6: Run the whole suite**

```bash
PYTHONPATH=src python3 -m pytest -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/matrixlang/interpreter.py tests/test_strings_run.py
git commit -m "feat: fold lower-cases, trim strips, cleave splits"
```

---

### Task 4: Render, treeview, and the round-trip property

This is the task the spec calls the trap. `cleave`'s new rung forces `render._LEVEL` to be renumbered end to end — an off-by-one there changes what a program MEANS, fails loudly nowhere else, and is caught only by the property test, which in turn only catches it if `treegen` produces the shape.

**Files:**
- Modify: `src/matrixlang/render.py` — `_OPS` and `_LEVEL` at 50-105, the word-unary tuple at 250-272
- Modify: `src/matrixlang/treeview.py` — `_OPS` at 35-53
- Modify: `tests/treegen.py` — `_BINARY_OPS` at 74-79, the unary list at ~186-200
- Modify: `tests/test_roundtrip.py` — the unary set at ~359-380, plus a new counted test
- Test: `tests/test_strings_render.py` (create)

**Interfaces:**
- Consumes: the node shapes from Task 2.
- Produces: nothing later tasks import.

- [ ] **Step 1: Write the failing render test**

Create `tests/test_strings_render.py`:

```python
"""String methods — rendering fold, trim and cleave in both faces."""

from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.render import render_ascii, render_glyph


def ascii_face(source):
    return render_ascii(parse(lex(source)))


def glyph_face(source):
    return render_glyph(parse(lex(source)))


def test_fold_renders_with_a_separating_space():
    # `fold s` must never come back as `folds` -- that re-lexes as one
    # identifier, a silent change of meaning. Same rule as `length`,
    # `decode`, `encode` and `keymaker`.
    assert ascii_face("trace fold s\n") == "trace fold s\n"


def test_trim_renders_with_a_separating_space():
    assert ascii_face("trace trim s\n") == "trace trim s\n"


def test_cleave_renders_infix():
    assert ascii_face('trace s cleave ","\n') == 'trace s cleave ","\n'


def test_the_three_render_in_the_glyph_face():
    assert glyph_face("trace fold s\n") == "ﾄ ﾊ s\n"
    assert glyph_face("trace trim s\n") == "ﾄ ﾘ s\n"
    assert glyph_face('trace s cleave "x"\n') == 'ﾄ s ﾛ "x"\n'


def test_a_unary_word_over_a_cleave_keeps_its_parens():
    # cleave binds looser than the unary rung, so these parens are load
    # bearing: `length s cleave ","` would be `(length s) cleave ","`.
    source = 'trace length (s cleave ",")\n'
    assert ascii_face(source) == source


def test_a_cleave_under_a_comparison_needs_no_parens():
    source = 'trace s cleave "," == xs\n'
    assert ascii_face(source) == source


def test_a_plus_under_a_cleave_needs_no_parens():
    source = 'trace a + b cleave ","\n'
    assert ascii_face(source) == source


def test_a_cleave_on_the_right_of_a_cleave_gets_parens():
    # Left-associative: `a cleave (b cleave c)` is NOT what
    # `a cleave b cleave c` parses as, so the render must put them back.
    source = "trace a cleave (b cleave c)\n"
    assert ascii_face(source) == source


def test_a_comparison_under_a_cleave_gets_parens():
    source = 'trace (a == b) cleave ","\n'
    assert ascii_face(source) == source


def test_fold_over_a_plus_gets_parens():
    source = "trace fold (a + b)\n"
    assert ascii_face(source) == source


def test_the_tree_view_names_all_three():
    from matrixlang.treeview import format_tree

    tree = format_tree(parse(lex('trace fold trim s cleave ","\n')))
    assert "fold" in tree and "trim" in tree and "cleave" in tree
```

- [ ] **Step 2: Run it to make sure it fails**

```bash
PYTHONPATH=src python3 -m pytest tests/test_strings_render.py -q
```

Expected: FAIL with `KeyError: <TokenType.FOLD: ...>` out of `render._OPS`.

- [ ] **Step 3: Add the three render entries and renumber `_LEVEL`**

In `src/matrixlang/render.py`, add to `_OPS` after `TokenType.ORACLE: "oracle",`:

```python
    TokenType.FOLD: "fold",
    TokenType.TRIM: "trim",
    TokenType.CLEAVE: "cleave",
```

Then renumber `_LEVEL` **in one move**, exactly as its own comment demands. Replace the table and the three constants below it with:

```python
_LEVEL: dict[TokenType, int] = {
    # The whole table is renumbered in one move rather than shifted
    # twice: this structure is what decides where parentheses go, and an
    # off-by-one here changes what a program means without failing
    # loudly anywhere else.
    TokenType.FORK: 1,
    TokenType.SPLICE: 2,
    TokenType.EQ: 4,
    TokenType.NEQ: 4,
    TokenType.LT: 5,
    TokenType.GT: 5,
    TokenType.LTE: 5,
    TokenType.GTE: 5,
    # `oracle` parses at the comparison level (parser._COMPARISON_OPS), so
    # it shares that level here -- a different number would parenthesise
    # `d oracle "a" == true` differently than the parser groups it.
    TokenType.ORACLE: 5,
    # `cleave` has a rung of its own (parser._CLEAVE_OPS) between
    # comparison and term. It is why every level below this line moved up
    # by one when string methods landed.
    TokenType.CLEAVE: 6,
    TokenType.PLUS: 7,
    TokenType.MINUS: 7,
    TokenType.STAR: 8,
    TokenType.SLASH: 8,
}
# `unplug` is unary, so it is a constant rather than a _LEVEL entry — but
# unlike `-` and `length` it binds LOOSER than every binary operator
# except fork and splice.
_NOT_LEVEL = 3
_UNARY_LEVEL = 9
_ATOM_LEVEL = 10
```

`_CALL_LEVEL = _ATOM_LEVEL` below it is unchanged.

- [ ] **Step 4: Add fold and trim to the word-unary tuple**

Still in `render.py`, in the `isinstance(expr, Unary)` branch:

```python
        if expr.op in (
            TokenType.LENGTH,
            TokenType.DECODE,
            TokenType.ENCODE,
            TokenType.KEYMAKER,
            TokenType.FOLD,
            TokenType.TRIM,
        ):
```

and extend the last sentence of the comment above it to name the two new words:

```python
            # `decode`, `encode`, `keymaker`, `fold` and `trim` are the
            # same shape and share the rule.
```

- [ ] **Step 5: Add the three treeview entries**

In `src/matrixlang/treeview.py`, add to `_OPS` after `TokenType.ORACLE: "oracle",`:

```python
    TokenType.FOLD: "fold",
    TokenType.TRIM: "trim",
    TokenType.CLEAVE: "cleave",
```

- [ ] **Step 6: Run the render test to verify it passes**

```bash
PYTHONPATH=src python3 -m pytest tests/test_strings_render.py -q
```

Expected: PASS, 11 tests.

- [ ] **Step 7: Put all three into the generator**

In `tests/treegen.py`, add `TokenType.CLEAVE` to `_BINARY_OPS`:

```python
_BINARY_OPS = [
    TokenType.EQ, TokenType.NEQ,
    TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE,
    TokenType.PLUS, TokenType.MINUS, TokenType.STAR, TokenType.SLASH,
    TokenType.ORACLE,
    TokenType.CLEAVE,
]
```

and both words to the unary choice list in `gen_expression`:

```python
        return Unary(
            rng.choice(
                [
                    TokenType.MINUS,
                    TokenType.LENGTH,
                    TokenType.UNPLUG,
                    TokenType.DECODE,
                    TokenType.ENCODE,
                    TokenType.KEYMAKER,
                    TokenType.FOLD,
                    TokenType.TRIM,
                ]
            ),
            gen_expression(rng, depth - 1),
        )
```

That branch's comment says "all six". It is now all eight — fix the number, not just the list.

- [ ] **Step 8: Extend the unary-coverage test**

In `tests/test_roundtrip.py::test_the_generator_produces_every_unary_operator`, add the two members to `expected`:

```python
        TokenType.KEYMAKER,
        TokenType.FOLD,
        TokenType.TRIM,
```

- [ ] **Step 9: Add the counted cleave corpus test**

Append to `tests/test_roundtrip.py`. The `walk_stmt` below is copied
verbatim from `test_the_generator_produces_the_dictionary_shapes_too`,
including its `IndexAssign` special case and its exact field names
(`value`/`condition`, `body`/`then_body`/`else_body`). Those names are the
whole correctness of the traversal — a wrong one silently visits nothing
and every count assertion passes on an empty walk. Each coverage test in
this file carries its own copy; do NOT refactor them into a shared helper
as part of this change.

```python
def test_the_generator_produces_the_string_method_shapes_too():
    # The trap, stated in the string-methods spec: the 300-seed property
    # only covers shapes treegen produces, and this has silently failed
    # twice -- `decode` and `encode` sat outside the property for their
    # entire existence while it stayed green, and the same hole reopened
    # one level down when dictionaries landed. So the corpus is COUNTED.
    # A zero here means test_round_trip is green while proving nothing
    # about these three operators.
    #
    # `cleave` matters most: it has a precedence rung of its own, which
    # renumbered render._LEVEL end to end. A wrong level there changes
    # what a program means and fails loudly nowhere else.
    from matrixlang.nodes import IndexAssign
    from matrixlang.tokens import TokenType

    counts = {"cleave": 0, "fold": 0, "trim": 0, "over_term": 0, "under_cmp": 0}

    def walk_expr(expr):
        if isinstance(expr, Unary):
            if expr.op is TokenType.FOLD:
                counts["fold"] += 1
            if expr.op is TokenType.TRIM:
                counts["trim"] += 1
            walk_expr(expr.operand)
        elif isinstance(expr, Binary):
            level = _LEVEL.get(expr.op)
            cleave_level = _LEVEL[TokenType.CLEAVE]
            if expr.op is TokenType.CLEAVE:
                counts["cleave"] += 1
                for side in (expr.left, expr.right):
                    if (
                        isinstance(side, Binary)
                        and _LEVEL.get(side.op, 0) > cleave_level
                    ):
                        counts["over_term"] += 1
            elif level is not None and level < cleave_level:
                for side in (expr.left, expr.right):
                    if isinstance(side, Binary) and side.op is TokenType.CLEAVE:
                        counts["under_cmp"] += 1
            walk_expr(expr.left)
            walk_expr(expr.right)
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
        elif isinstance(expr, DictLiteral):
            for key, value in expr.entries:
                walk_expr(key)
                walk_expr(value)

    def walk_stmt(stmt):
        if isinstance(stmt, IndexAssign):
            walk_expr(stmt.target)
            walk_expr(stmt.index)
            walk_expr(stmt.value)
            return
        for field in ("value", "condition"):
            if getattr(stmt, field, None) is not None:
                walk_expr(getattr(stmt, field))
        for name in ("body", "then_body", "else_body"):
            for child in getattr(stmt, name, None) or []:
                walk_stmt(child)

    for seed in range(300):
        for statement in gen_program(random.Random(seed)).statements:
            walk_stmt(statement)

    print("string-method corpus:", counts)
    assert counts["cleave"], "no `cleave` in 300 seeds — the property proves nothing about it"
    assert counts["fold"], "no `fold` in 300 seeds"
    assert counts["trim"], "no `trim` in 300 seeds"
    assert counts["over_term"], "no `(a + b) cleave c` shape in 300 seeds"
    assert counts["under_cmp"], "no `(a cleave b) == c` shape in 300 seeds"
```

- [ ] **Step 10: Print the counts once, then run the property**

A count assertion that passes on 1 is barely better than no assertion. Print them while developing and confirm they are substantial:

```bash
PYTHONPATH=src python3 -m pytest tests/test_roundtrip.py -q -k string_method -s
```

Then the full file, all 300 seeds:

```bash
PYTHONPATH=src python3 -m pytest tests/test_roundtrip.py -q
```

Expected: PASS.

If `test_round_trip` fails on a seed, the `_LEVEL` renumber is wrong — read the printed source, do not adjust the generator. If a COUNT fails, the generator is not reaching the shape: widen the traversal or raise the seed range to 600 (`test_the_generator_produces_the_stage_9_shapes_too` uses 600 for the same reason). Never delete a count assertion.

- [ ] **Step 11: Run the whole suite**

```bash
PYTHONPATH=src python3 -m pytest -q
```

Expected: PASS.

- [ ] **Step 12: Commit**

```bash
git add src/matrixlang/render.py src/matrixlang/treeview.py tests/treegen.py tests/test_roundtrip.py tests/test_strings_render.py
git commit -m "feat: render fold, trim and cleave in both faces; renumber _LEVEL"
```

---

### Task 5: The translator — `.lower()`, `.strip()`, `.split(sep)`

The governing rule holds: **translate syntax; never infer types. Refuse where the difference would be silent.** `.upper()` and bare `.split()` are refusals with idioms, not omissions.

**Files:**
- Modify: `src/matrixlang/pytrans/translate.py` — `_NAMED_CALL`'s neighbourhood at ~45, and the `ast.Attribute` call branch at 780-787
- Modify: `tests/test_pytrans_expr.py` (helpers `ml()` and `refused()` already exist there)
- Modify: `tests/test_pytrans_refuse.py` (calls `translate()` directly — follow that style)
- Modify: `tests/test_pytrans_differential.py` (helpers `both()` and `agree()` already exist)

**Interfaces:**
- Consumes: `TokenType.FOLD`, `TokenType.TRIM`, `TokenType.CLEAVE`; the node shapes from Tasks 2-4.

**Deliberately unchanged:** the STATEMENT-level attribute path at `translate.py:268-312`, which refuses any method statement that is not `.append()`. `s.lower()` on its own line is a no-op in Python too, so nothing the reader meant is lost there. Say so in the review if asked.

- [ ] **Step 1: Write the failing mapping tests**

In `tests/test_pytrans_expr.py`, add:

```python
def test_lower_becomes_fold():
    assert "fold s" in ml("s = 'A'\nprint(s.lower())\n")


def test_strip_becomes_trim():
    assert "trim s" in ml("s = ' a '\nprint(s.strip())\n")


def test_split_becomes_cleave():
    assert 's cleave ","' in ml("s = 'a,b'\nprint(s.split(','))\n")


def test_a_string_method_on_an_expression_translates():
    # The receiver is an arbitrary expression, not only a name.
    assert "fold xs[0]" in ml("xs = ['A']\nprint(xs[0].lower())\n")


def test_a_case_insensitive_comparison_translates_whole():
    source = "a = 'A'\nb = 'a'\nprint(a.lower() == b.lower())\n"
    assert "fold a == fold b" in ml(source)


def test_a_chained_strip_and_split_translates():
    assert 'trim s cleave ","' in ml("s = ' a,b '\nprint(s.strip().split(','))\n")
```

- [ ] **Step 2: Write the failing refusal tests**

In `tests/test_pytrans_refuse.py`, add — matching that file's own style of calling `translate()` directly:

```python
def test_upper_is_refused_with_an_idiom():
    result = translate("s = 'a'\nprint(s.upper())\n")
    assert isinstance(result, Refusals)
    (refusal,) = result.items
    assert "`.upper()`" in refusal.reason
    assert refusal.idiom is not None
    assert "lower" in refusal.idiom


def test_a_bare_split_is_refused_rather_than_guessed():
    # Python's bare .split() splits on RUNS of whitespace and discards
    # empty strings. `cleave " "` is different behaviour, not a missing
    # argument, so translating one to the other would be silently wrong --
    # which is exactly what the governing rule forbids.
    result = translate("s = 'a b'\nprint(s.split())\n")
    assert isinstance(result, Refusals)
    (refusal,) = result.items
    assert "split" in refusal.reason
    assert refusal.idiom is not None


def test_split_with_two_arguments_is_refused():
    result = translate("s = 'a,b,c'\nprint(s.split(',', 1))\n")
    assert isinstance(result, Refusals)
    assert "split" in result.items[0].reason


def test_strip_with_an_argument_is_refused():
    # `trim` takes no argument; .strip("x") strips a character SET, which
    # is a different operation.
    result = translate("s = 'xax'\nprint(s.strip('x'))\n")
    assert isinstance(result, Refusals)
    assert "strip" in result.items[0].reason


def test_an_untranslatable_method_still_refuses_as_before():
    # Not in this change. The blanket message must still be reachable.
    result = translate("s = 'a'\nprint(s.replace('a', 'b'))\n")
    assert isinstance(result, Refusals)
    assert "`.replace()`" in result.items[0].reason


def test_a_refusal_still_carries_its_python_position():
    result = translate("s = 'a'\nprint(s.upper())\n")
    assert result.items[0].line == 2
```

- [ ] **Step 3: Run both files to make sure they fail**

```bash
PYTHONPATH=src python3 -m pytest tests/test_pytrans_expr.py tests/test_pytrans_refuse.py -q
```

Expected: FAIL — every new case currently hits the blanket "`.<attr>()` cannot be translated as a value" refusal.

- [ ] **Step 4: Add the method table**

In `src/matrixlang/pytrans/translate.py`, beside `_NAMED_CALL`:

```python
# Python string methods that have a MatrixLang operator. Kept separate
# from _NAMED_CALL because these arrive as `receiver.method()` rather than
# `name(argument)` -- MatrixLang has no attribute access at all, which is
# why the translator has to special-case each one it can reach.
_STRING_UNARY = {
    "lower": TokenType.FOLD,
    "strip": TokenType.TRIM,
}
```

- [ ] **Step 5: Handle the three methods in the call path**

Replace the `isinstance(node.func, ast.Attribute)` branch at `translate.py:780-787` with:

```python
        if isinstance(node.func, ast.Attribute):
            method = node.func.attr
            if method in _STRING_UNARY:
                if node.args or node.keywords:
                    raise _Unsupported(
                        self._because(
                            node,
                            f"`.{method}()` can only be translated with no "
                            "arguments",
                            f"MatrixLang's `{_STRING_UNARY[method].name.lower()}` "
                            "is a one-operand operator",
                        )
                    )
                return Unary(
                    _STRING_UNARY[method], self.expression(node.func.value)
                )
            if method == "split":
                if len(node.args) != 1 or node.keywords:
                    # Bare `.split()` is NOT `.split(" ")`. Python splits
                    # on RUNS of whitespace and discards empty strings, so
                    # translating it to `cleave " "` would give a program
                    # that runs and quietly means something else -- which
                    # is exactly what the governing rule forbids.
                    raise _Unsupported(
                        self._because(
                            node,
                            "`.split()` can only be translated with exactly "
                            "one separator",
                            'bare `.split()` splits on runs of whitespace and '
                            'drops empty pieces, which `cleave` does not do — '
                            'name the separator: `.split(" ")`',
                        )
                    )
                return Binary(
                    self.expression(node.func.value),
                    TokenType.CLEAVE,
                    self.expression(node.args[0]),
                )
            if method == "upper":
                raise _Unsupported(
                    self._because(
                        node,
                        "`.upper()` cannot be translated — MatrixLang has "
                        "no upper-casing operator",
                        "to compare ignoring case, use `.lower()` on both "
                        "sides; to display in capitals there is no "
                        "MatrixLang form yet",
                    )
                )
            raise _Unsupported(
                self._because(
                    node,
                    f"`.{node.func.attr}()` cannot be translated as a value",
                    "`.append()` becomes an assignment, so it only works as a "
                    "statement on its own line",
                )
            )
```

`Binary`, `Unary` and `TokenType` are already imported in this file — confirm rather than assume.

- [ ] **Step 6: Run the translator tests to verify they pass**

```bash
PYTHONPATH=src python3 -m pytest tests/test_pytrans_expr.py tests/test_pytrans_refuse.py -q
```

Expected: PASS.

- [ ] **Step 7: Add the differential case — the products program**

This is the case the spec says is the one that matters. Everything else proves the operators return something; only this proves a reader's Python and its translation print the same text.

In `tests/test_pytrans_differential.py`, add:

```python
def test_the_products_search_agrees():
    # The program that put string methods first in the register. Prices
    # are strings because MatrixLang has no decimals yet (register item 4,
    # #135); everything else is the reader's own program, `.lower()`
    # included.
    source = (
        "products = [\n"
        '    {"code": "A1", "name": "Mouse", "price": "49"},\n'
        '    {"code": "B2", "name": "Teclado", "price": "120"},\n'
        "]\n"
        "\n"
        'term = input("Search: ")\n'
        "found = 0\n"
        "for product in products:\n"
        '    if term.lower() == product["code"].lower() or '
        'term.lower() == product["name"].lower():\n'
        '        print(product["name"] + " costs " + product["price"])\n'
        "        found = found + 1\n"
        "if found == 0:\n"
        '    print("Nothing found.")\n'
    )
    agree(source, ["mouse"])
    agree(source, ["B2"])
    agree(source, ["nothing at all"])


def test_trim_and_cleave_agree():
    agree('s = "  a,b,c  "\nfor part in s.strip().split(","):\n    print(part)\n')
```

- [ ] **Step 8: Run the differential tests**

```bash
PYTHONPATH=src python3 -m pytest tests/test_pytrans_differential.py -q
```

Expected: PASS. A failure here means Python and MatrixLang printed different text — read the assertion's `python=` / `matrixlang=` values and fix whichever side is wrong. Never weaken the case to make it pass.

- [ ] **Step 9: Run the whole suite and the browser-half gates**

```bash
PYTHONPATH=src python3 -m pytest -q
```

```bash
python3 site/checks/no_semantics.py
```

```bash
python3 site/checks/key_handling.py
```

Expected: suite PASS, both checks OK. No `site/*.js` file changes in this plan; these prove it.

- [ ] **Step 10: Commit**

```bash
git add src/matrixlang/pytrans/translate.py tests/test_pytrans_expr.py tests/test_pytrans_refuse.py tests/test_pytrans_differential.py
git commit -m "feat(pytrans): .lower(), .strip() and .split(sep) reach fold, trim and cleave"
```

---

### Task 6: The documentation and the register

Four documents carry counts or vocabulary that are now wrong. `operator/prompt.py` was already handled in Task 1, because a test forced it.

**Files:**
- Modify: `README.md` — the vocabulary paragraph at 45-60, and `nineteen keywords` at 132
- Modify: `docs/LEARNING-MATRIXLANG.md` — a new teaching section after `### length and keymaker` (~line 622), and the glyph table (~line 1180)
- Modify: `docs/TECHNICAL-OVERVIEW.md` — the 49-slot claims at 93, 264, 305
- Modify: `docs/PYTHON-PARITY.md` — the register itself

- [ ] **Step 1: Update the README**

In the vocabulary paragraph, after the dictionaries clause and before `— and **Operator**`, insert:

```
— **string methods** — `fold` lower-cases, `trim` removes whitespace from
both ends, and the infix `cleave` splits on a separator, so `"a,b" cleave
","` is `["a", "b"]`, which makes a case-insensitive comparison `fold a ==
fold b` —
```

At line 132, change `nineteen keywords` to `twenty-two keywords`.

- [ ] **Step 2: Update the learning guide's glyph table**

Change the prose above the table:

```
Twenty-two keywords, eleven operators, parentheses, a comma, two brackets,
a pair of braces, a colon, ten digits, and the comment marker — 52 slots
in all.
```

and fill the last row's three empty cells:

```
| `keymaker` `ﾔ` | `{` `ﾐ` | `}` `ﾑ` | `:` `ﾓ` | `fold` `ﾊ` | `trim` `ﾘ` | `cleave` `ﾛ` |
```

- [ ] **Step 3: Add a teaching section to the learning guide**

Immediately after the `### length and keymaker` section ends, add:

````
### `fold`, `trim` and `cleave`

Three things you will want to do to a string.

```
construct name = "  Mouse  "
trace trim name
trace fold "MOUSE"
trace "a,b,c" cleave ","
```

```
Mouse
mouse
["a", "b", "c"]
```

`fold` lower-cases and `trim` takes the whitespace off both ends. Both are
prefix keywords like `length`, so they bind tightly: `fold a + b` is
`(fold a) + b`.

`cleave` is infix, like `oracle`. It splits a string on a separator and
gives back a list. It binds looser than `+` and tighter than `==`, which
is what makes both of these read the way they look:

```
trace a + b cleave ","       # concatenate, THEN split
trace s cleave "," == parts  # split, THEN compare the lists
```

Reaching for `length` on the result needs parentheses, the same way
`length keymaker d` does — a prefix keyword binds tightest of all:

```
trace length (s cleave ",")
```

Three rules worth knowing:

- All three take strings. `fold 1` is an error, not a `1`.
- An empty separator is an error. `"abc" cleave ""` does not give you the
  letters; there is no operation in MatrixLang that does.
- Empty pieces are kept: `"a,,b" cleave ","` is `["a", "", "b"]`, and
  `"" cleave ","` is a list holding one empty string, not an empty list.

There is no upper-casing operator. To compare two strings ignoring case,
`fold` both sides:

```
construct typed = "MOUSE"
construct stored = "Mouse"
redpill fold typed == fold stored
  trace "match"
flatline
```
````

- [ ] **Step 4: Update the technical overview's counts**

Find them rather than trusting the line numbers:

```bash
grep -n "49" docs/TECHNICAL-OVERVIEW.md
```

Line 93: `The 49-slot bijective glyph table. 7 slots left of the block` → `The 52-slot bijective glyph table. 4 slots left of the block`.
Line 264: `each of the 49 slots` → `each of the 52 slots`.
Line 305: `the same 49-entry table` → `the same 52-entry table`.

`glyphs.py`'s own module docstring opens with `"""The 49-slot glyph table` — fix that too, and check whether the line count beside it in the overview's table still holds after Task 1's edit.

- [ ] **Step 5: Update the register**

In `docs/PYTHON-PARITY.md`:

- `**Keywords (19)**` → `**Keywords (22)**`, with `fold` `trim` `cleave` added to the list.
- `**Glyph budget** — 49 slots used, 7 free.` → `**Glyph budget** — 52 slots used, 4 free.`
- Item 1's heading `### 1. String methods — #132 — *next*` → `### 1. String methods — #132 — **done**`, and replace its body with a record of what shipped rather than what is missing:

```
`fold` lower-cases, `trim` strips, and the infix `cleave` splits on a
separator. The products search that motivated this item now translates and
runs, and its output is checked against Python's in
`tests/test_pytrans_differential.py`.

Still refused, each with an idiom: `.upper()` (no operator, and nothing has
been blocked by it yet) and bare `.split()` (splitting on runs of
whitespace is a different operation, not a default separator).
```

- Item 2's heading gains `— *next*`.
- In the closing constraints section, `7 slots left` → `4 slots left`.
- Check the `_DESCRIBE` count in the "Where the truth lives" paragraph rather than assuming it moved:

```bash
PYTHONPATH=src python3 -c "from matrixlang.pytrans.translate import _DESCRIBE; print(len(_DESCRIBE))"
```

- [ ] **Step 6: Verify every example in the new guide section actually runs**

The learning guide's standing claim is that every example in it was executed before it shipped. Honour it. Write the first block to a scratch file and run it:

```bash
printf 'construct name = "  Mouse  "\ntrace trim name\ntrace fold "MOUSE"\ntrace "a,b,c" cleave ","\n' > /tmp/ml-doc-check.rain
```

```bash
PYTHONPATH=src python3 -m matrixlang run /tmp/ml-doc-check.rain
```

Expected output, exactly:

```
Mouse
mouse
["a", "b", "c"]
```

Do the same for the `redpill fold typed == fold stored` block, which is written to be runnable as it stands and should print `match`.

- [ ] **Step 7: Run the whole suite one more time**

```bash
PYTHONPATH=src python3 -m pytest -q
```

Expected: PASS. `tests/test_site_examples.py` and `tests/test_package.py` both read repository files, so a documentation edit can genuinely turn a test red here.

- [ ] **Step 8: Commit**

```bash
git add README.md docs/LEARNING-MATRIXLANG.md docs/TECHNICAL-OVERVIEW.md docs/PYTHON-PARITY.md src/matrixlang/glyphs.py
git commit -m "docs: fold, trim and cleave — 22 keywords, 52 slots, 4 free"
```

---

## Verification gates

Run all of these on the branch tip before opening the pull request:

```bash
PYTHONPATH=src python3 -m pytest -q
```

```bash
python3 site/checks/no_semantics.py
```

```bash
python3 site/checks/key_handling.py
```

```bash
git diff --stat origin/main -- site/
```

The last one should be empty: this change is entirely in the Python half, and the browser half calls through `site/glue.py` unchanged.

## Self-review notes

Three places this change can be wrong while looking right — a reviewer should go straight to them:

1. **The `render._LEVEL` renumbering.** Every level from `PLUS` down moved. A missed entry produces parentheses in the wrong place — a program that means something different — and only `test_round_trip` catches it, and only if `treegen` generates the shape.
2. **The counted corpus in Task 4, Step 9.** If the counts are asserted but the walker never reaches the nodes (wrong attribute names on the statement classes), the assertions pass on garbage. Step 10 exists to make that visible; do not skip it.
3. **`fold` is `.lower()`.** The name says otherwise. `tests/test_strings_run.py::test_fold_is_lower_not_casefold` is the guard, and `test_trim_is_pythons_strip_not_decodes_ascii_only_one` is its sibling for `trim`. Both must stay.
