# Loop Control Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give MatrixLang `wake` (break) and `glitch` (continue), and teach the Python translator to reach them — including the counter rewrite that keeps a desugared `for` loop correct.

**Architecture:** Two bare-keyword statements and **two new AST node types**, `Wake` and `Glitch`. Both are exception-shaped signals at runtime, caught by the `While` executor, copying `_Jackout`'s design. The translator maps `ast.Break`/`ast.Continue` onto them and, because it owns the `for` desugaring, inserts the loop counter's increment before every `Glitch` it emits inside one.

**Tech Stack:** Python 3.11+, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-23-loop-control-design.md`
**Issue:** #133
**Register:** `docs/PYTHON-PARITY.md`, item 2
**Branch:** `loop-control`, off `origin/main` at 3e216a8

## Environment

This worktree has **no `.venv` of its own** — the virtualenv lives in the main checkout. Every command uses the interpreter already on PATH:

```bash
PYTHONPATH=src python3 -m pytest -q
```

Baseline: **1880 passed.** If yours differs before you change anything, stop and say so.

## Global Constraints

- **The two keywords are `wake` and `glitch`.** Exactly those spellings.
- **Glyph assignments, fixed:** `wake` → `ﾉ` (U+FF89), `glitch` → `ﾕ` (U+FF95). The two slots left free afterwards are `ｰ` (U+FF70) and `ﾝ` (U+FF9D) — deliberately, because both are non-syllabic marks that read as punctuation rather than as a word, and register item 4 (#135) needs exactly two slots for the punctuation `.` and `%`. Do not use either.
- **Glyph budget: 52 → 54 used, 4 → 2 free.** Hand-tracked on purpose.
- **Keyword count: 22 → 24.**
- **Two new AST node types**, `Wake` and `Glitch`, both `Stmt` subclasses with no fields of their own.
- **Both are statements, not expressions.** `construct x = wake` must be a parse error.
- **Both are bare** — no operand, like bare `jackout` (`parser.py:328`).
- **`wake` leaves only the innermost loop**, as Python's `break` does.
- **Outside any loop, both are a positioned `RuntimeErrorML`** — `'wake' outside a loop` / `'glitch' outside a loop` — mirroring `'jackout' outside an agent` at `interpreter.py:210`.
- **An agent boundary stops both.** `_call` at `interpreter.py:704-711` currently catches only `_Jackout`. A `_Wake` raised inside an agent body called from inside a loop would otherwise escape and break the CALLER's loop. This is the single most important correctness detail in the change.
- **`jackout` beats both** — it unwinds past a loop to the call site. Free, provided the loop catches only `_Wake`/`_Glitch`.
- **The step limit is untouched.** Steps count executed statements (`interpreter.py:228`).
- **`for ... else` and `while ... else` stay refused** (`translate.py:462`, `:248`). Do not add support; Python's loop-else runs only when no `break` fired, and that interaction is exactly what the existing refusals close off.
- **Loops with no `glitch` in them must keep byte-for-byte the output the translator produces today.** The playground shows this code to the reader.
- **The full suite must be green at the end of every task.**

## Traps this project has actually hit — read before starting

These are not hypotheticals. Each one cost real time on the immediately preceding branch:

1. **A file the plan says to "create" may already exist.** An implementer followed that instruction literally and destroyed 29 pre-existing tests before a test-count mismatch caught it. **Check before writing. If it exists, append.**
2. **There are THREE duplicated glyph-count ledgers**, not one: `tests/test_glyphs.py`, `tests/test_lists_lex.py`, and `tests/test_logic_parse.py`. The last two are easy to miss and will go red the moment a glyph is added.
3. **`operator/prompt.py` must gain a rule for any new keyword.** `tests/test_operator_prompt.py::test_every_keyword_is_explained_or_demonstrated` asserts against `_RULES + _EXAMPLE` directly and goes red immediately.
4. **Stale counts hide outside `*.py` and `*.md`.** `site/index.html` carries the keyword count in prose. A sweep that greps only Python and Markdown will miss it, as one did.
5. **Adding to a treegen choice list dilutes every existing entry.** Adding two unary operators last time cut `unplug`'s share from 1/6 to 1/8 and pushed a coverage assertion past its seed range. This change adds **two statement kinds to a six-kind list — a 25% dilution of every statement shape the property covers.** Several coverage tests count statement-derived shapes over fixed seed ranges.
6. **A node type outside treegen is invisible to the property.** It has stayed green while proving nothing three times.

---

## File Structure

| File | Change | Task |
| --- | --- | --- |
| `src/matrixlang/tokens.py` | 2 `TokenType` members, 2 `KEYWORDS` entries | 1 |
| `src/matrixlang/glyphs.py` | 2 glyph assignments | 1 |
| `src/matrixlang/nodes.py` | `Wake`, `Glitch` dataclasses | 1 |
| `src/matrixlang/operator/prompt.py` | one rule in `_RULES` | 1 |
| `tests/test_tokens.py`, `tests/test_glyphs.py`, `tests/test_lists_lex.py`, `tests/test_logic_parse.py` | the four ledgers | 1 |
| `tests/test_loops_lex.py` | **new** — both faces lex | 1 |
| `src/matrixlang/parser.py` | `_statement` dispatch | 2 |
| `tests/test_loops_parse.py` | **new** — bare statements, not expressions | 2 |
| `src/matrixlang/interpreter.py` | `_Wake`/`_Glitch`, the `While` catch, `_call`'s catch, `run`'s catch | 3 |
| `tests/test_loops_run.py` | **new** — semantics, nesting, every error | 3 |
| `src/matrixlang/render.py`, `src/matrixlang/treeview.py` | statement branches | 4 |
| `tests/treegen.py` | two statement kinds | 4 |
| `tests/test_loops_render.py` | **new** — both faces, inside a loop | 4 |
| `tests/test_roundtrip.py` | counted corpus, and the dilution audit | 4 |
| `src/matrixlang/pytrans/translate.py` | mapping + the increment rewrite | 5 |
| `tests/test_pytrans_loops.py`, `tests/test_pytrans_refuse.py`, `tests/test_pytrans_differential.py` | mapping, removed refusals, the four risk cases | 5 |
| `README.md`, `docs/LEARNING-MATRIXLANG.md`, `docs/TECHNICAL-OVERVIEW.md`, `docs/PYTHON-PARITY.md`, `site/index.html` | counts, table, teaching section, register | 6 |

---

### Task 1: Vocabulary and the two node types

**Files:**
- Modify: `src/matrixlang/tokens.py`, `src/matrixlang/glyphs.py`, `src/matrixlang/nodes.py`, `src/matrixlang/operator/prompt.py`
- Modify: `tests/test_tokens.py`, `tests/test_glyphs.py`, `tests/test_lists_lex.py`, `tests/test_logic_parse.py`
- Test: `tests/test_loops_lex.py` (check whether it exists first)

**Interfaces:**
- Produces: `TokenType.WAKE`, `TokenType.GLITCH`; `KEYWORDS["wake"|"glitch"]`; `GLYPHS["wake"|"glitch"]`; `nodes.Wake`, `nodes.Glitch`. Every later task consumes these.

- [ ] **Step 1: Write the failing lexer test**

Create `tests/test_loops_lex.py` (if it already exists, append):

```python
"""Loop control — lexing wake and glitch in both faces."""

from matrixlang.lexer import lex
from matrixlang.tokens import KEYWORDS, TokenType


def test_both_words_are_keywords():
    types = [t.type for t in lex("wake glitch\n")]
    assert types[:2] == [TokenType.WAKE, TokenType.GLITCH]


def test_both_words_lex_in_the_glyph_face():
    # The glyph face must lex to the same tokens as the ASCII face, or
    # D-03's round-trip claim is false for these two keywords.
    types = [t.type for t in lex("ﾉ ﾕ\n")]
    assert types[:2] == [TokenType.WAKE, TokenType.GLITCH]


def test_a_name_that_merely_starts_with_a_keyword_is_still_a_name():
    # `waken` must not lex as `wake` followed by `n`. The lexer reads a
    # whole word and looks it up, so this holds by construction -- but it
    # is what would turn `construct waken = 1` into a parse error in
    # somebody's existing program.
    types = [t.type for t in lex("waken glitches\n")]
    assert types[:2] == [TokenType.IDENT, TokenType.IDENT]


def test_registration_is_all_the_lexer_needs():
    # lexer.py builds its glyph table by walking GLYPHS and looking each
    # slot up in KEYWORDS, so registering a word in tokens.py and
    # glyphs.py is the whole of adding it to both faces.
    for word in ("wake", "glitch"):
        assert word in KEYWORDS
```

- [ ] **Step 2: Run it to make sure it fails**

```bash
PYTHONPATH=src python3 -m pytest tests/test_loops_lex.py -q
```

Expected: FAIL with `AttributeError: WAKE`.

- [ ] **Step 3: Register the token types**

In `src/matrixlang/tokens.py`, after `CLEAVE = auto()` in the `# Keywords` block:

```python
    WAKE = auto()
    GLITCH = auto()
```

and at the end of `KEYWORDS`:

```python
    "wake": TokenType.WAKE,
    "glitch": TokenType.GLITCH,
```

- [ ] **Step 4: Assign the two glyphs**

In `src/matrixlang/glyphs.py`, after the string-methods block and before `# operators`:

```python
    # Loop control. Both arbitrary -- ｳｪｲｸ and ｸﾞﾘｯﾁ have no sound left
    # unspent. The two slots deliberately NOT taken are ｰ (U+FF70) and
    # ﾝ (U+FF9D): neither is a syllable, both read as punctuation, and
    # the next item in the register needs exactly two punctuation slots.
    "wake": "ﾉ",
    "glitch": "ﾕ",
```

- [ ] **Step 5: Add the two node types**

In `src/matrixlang/nodes.py`, after `ExprStmt`:

```python
@dataclass
class Wake(Stmt):
    """`wake`. Leaves the innermost loop, like Python's `break`.

    No fields: the whole statement is the keyword. Both this and Glitch
    are Stmt rather than Expr on purpose -- `construct x = wake` has no
    meaning, and making them expressions would give it one."""


@dataclass
class Glitch(Stmt):
    """`glitch`. Skips to the innermost loop's next iteration.

    Named for the film's own line: a déjà vu IS a glitch in the Matrix.
    The loop keyword is `dejavu`, so this is the word for making the same
    loop happen again."""
```

- [ ] **Step 6: Run the lexer test**

```bash
PYTHONPATH=src python3 -m pytest tests/test_loops_lex.py -q
```

Expected: PASS, 4 tests.

- [ ] **Step 7: Update all FOUR hand-tracked ledgers**

Three carry the glyph count and one the keyword set. Missing any of them turns the suite red.

`tests/test_tokens.py` — rename `test_all_twenty_two_keywords_are_registered` to `test_all_twenty_four_keywords_are_registered` and add to its set:

```python
        # Loop control
        "wake",
        "glitch",
```

`tests/test_glyphs.py` — rename `test_the_table_covers_exactly_the_52_slots` to `..._54_slots`, add a line to its comment block before `# Nothing more`:

```python
    # + loop control: wake and glitch.
```

and change `assert len(expected) == 52` to `== 54`. In `test_the_glyph_budget_is_tracked_not_discovered`, append to the ledger comment before `# Finite, and worth knowing.`:

```python
    # Loop control spends 2 -- wake and glitch -- so 4 - 2 = 2 left. Both
    # survivors are non-syllabic marks, held for the punctuation the
    # numbers item needs.
```

and change `assert free == 4` to `== 2`.

`tests/test_lists_lex.py` — `test_the_table_is_still_bijective`, change `== 52` to `== 54`.

`tests/test_logic_parse.py` — `test_the_table_is_still_bijective_at_52`, rename to `..._at_54` and change `== 52` to `== 54`.

- [ ] **Step 8: Run the suite to see exactly what else went red**

```bash
PYTHONPATH=src python3 -m pytest -q
```

Expected: exactly ONE failure — `tests/test_operator_prompt.py::test_every_keyword_is_explained_or_demonstrated`, reporting `never explained or shown: ['glitch', 'wake']`.

**If anything else is red, stop and report it.** Do not work around it.

- [ ] **Step 9: Add the prompt rule**

In `src/matrixlang/operator/prompt.py`, inside `_RULES`, immediately after the bullet describing `dejavu`/blocks or the logical-operator bullet — wherever loops are discussed:

```
- `wake` leaves the innermost `dejavu` immediately; `glitch` skips to that
  loop's next iteration. Both are bare keywords on their own line, like a
  bare `jackout`, and both are an error outside a loop. A `jackout` inside
  a loop still returns from the agent — it is not stopped by the loop.
```

- [ ] **Step 10: Run the suite green**

```bash
PYTHONPATH=src python3 -m pytest -q
```

Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add src/matrixlang/tokens.py src/matrixlang/glyphs.py src/matrixlang/nodes.py src/matrixlang/operator/prompt.py tests/test_tokens.py tests/test_glyphs.py tests/test_lists_lex.py tests/test_logic_parse.py tests/test_loops_lex.py
git commit -m "feat: register wake and glitch — 54 glyph slots, 2 free"
```

---

### Task 2: Parser — two bare statements

**Files:**
- Modify: `src/matrixlang/parser.py` — the `_statement` dispatch at 163-190
- Test: `tests/test_loops_parse.py` (check whether it exists first)

**Interfaces:**
- Consumes: `TokenType.WAKE`, `TokenType.GLITCH`, `nodes.Wake`, `nodes.Glitch` from Task 1.
- Produces: `Wake()` and `Glitch()` nodes with `line`/`column` set from the keyword token. Tasks 3-5 consume these.

- [ ] **Step 1: Write the failing parser test**

Create `tests/test_loops_parse.py`:

```python
"""Loop control — parsing wake and glitch."""

import pytest

from matrixlang.errors import ParseError
from matrixlang.lexer import lex
from matrixlang.nodes import Glitch, Wake, While
from matrixlang.parser import parse


def first(source):
    return parse(lex(source)).statements[0]


def test_wake_is_a_bare_statement():
    assert isinstance(first("wake\n"), Wake)


def test_glitch_is_a_bare_statement():
    assert isinstance(first("glitch\n"), Glitch)


def test_they_carry_the_keywords_position():
    statement = first("trace 1\nwake\n")
    assert isinstance(statement, Wake) is False  # first statement is the trace
    second = parse(lex("trace 1\nwake\n")).statements[1]
    assert second.line == 2
    assert second.column == 1


def test_they_parse_inside_a_loop_body():
    loop = first("dejavu true\n  wake\nflatline\n")
    assert isinstance(loop, While)
    assert isinstance(loop.body[0], Wake)


def test_they_take_no_operand():
    # `wake 1` is not an early exit carrying a value -- there is no such
    # thing. The trailing expression has nowhere to go, so the statement
    # must end at the keyword and the parser must object to what follows.
    with pytest.raises(ParseError):
        parse(lex("wake 1\n"))


def test_they_are_statements_not_expressions():
    # The whole reason they are Stmt rather than Expr. If either reached
    # _primary, `construct x = wake` would build a tree for a program
    # with no meaning.
    with pytest.raises(ParseError):
        parse(lex("construct x = wake\n"))
    with pytest.raises(ParseError):
        parse(lex("trace glitch\n"))


def test_a_trailing_comment_attaches():
    statement = first("wake  # done\n")
    assert statement.trailing_comment == "# done"
```

- [ ] **Step 2: Run it to make sure it fails**

```bash
PYTHONPATH=src python3 -m pytest tests/test_loops_parse.py -q
```

Expected: FAIL — `wake` is a keyword with no grammar rule, so `_statement` falls through.

- [ ] **Step 3: Add the dispatch**

In `src/matrixlang/parser.py`, import `Glitch` and `Wake` from `matrixlang.nodes`, then in `_statement`, after the `JACKOUT` branch:

```python
        if token.type is TokenType.WAKE:
            return self._bare(Wake)
        if token.type is TokenType.GLITCH:
            return self._bare(Glitch)
```

and add the helper beside `_return`:

```python
    def _bare(self, kind: type[Stmt]) -> Stmt:
        """A statement that is nothing but its keyword.

        `wake` and `glitch` take no operand -- unlike `jackout`, which
        may carry a value -- so anything after the keyword on the line is
        an error rather than an expression to attach.
        """
        keyword = self.advance()
        node = kind(line=keyword.line, column=keyword.column)
        self._end_statement(node)
        return node
```

`_end_statement` already requires a NEWLINE, so `wake 1` fails there with "expected end of line after the statement" — which is why Step 1's test asserts only that it raises.

- [ ] **Step 4: Run the parser test**

```bash
PYTHONPATH=src python3 -m pytest tests/test_loops_parse.py -q
```

Expected: PASS, 7 tests.

- [ ] **Step 5: Run the whole suite**

```bash
PYTHONPATH=src python3 -m pytest -q
```

Expected: PASS. Rendering is Task 4 — nothing outside these tests builds a `Wake` yet, and none of them render.

- [ ] **Step 6: Commit**

```bash
git add src/matrixlang/parser.py tests/test_loops_parse.py
git commit -m "feat: parse wake and glitch as bare statements"
```

---

### Task 3: Interpreter — the two signals

**Files:**
- Modify: `src/matrixlang/interpreter.py` — a new signal class beside `_Jackout` at 152, the `While` executor at 355-358, `run`'s catch at 207-215, `_call`'s catch at 704-711
- Test: `tests/test_loops_run.py` (check whether it exists first)

**Interfaces:**
- Consumes: `Wake` and `Glitch` nodes from Task 2.

- [ ] **Step 1: Write the failing interpreter test**

Create `tests/test_loops_run.py`:

```python
"""Loop control — running wake and glitch end to end."""

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


def test_wake_leaves_the_loop():
    source = (
        "construct n = 0\n"
        "dejavu n < 10\n"
        "  redpill n == 3\n"
        "    wake\n"
        "  flatline\n"
        "  trace n\n"
        "  n = n + 1\n"
        "flatline\n"
    )
    assert run(source) == "0\n1\n2\n"


def test_glitch_skips_to_the_next_iteration():
    source = (
        "construct n = 0\n"
        "dejavu n < 5\n"
        "  n = n + 1\n"
        "  redpill n == 3\n"
        "    glitch\n"
        "  flatline\n"
        "  trace n\n"
        "flatline\n"
    )
    assert run(source) == "1\n2\n4\n5\n"


def test_glitch_re_tests_the_condition():
    # Not "jump to the last statement" -- `glitch` goes back to the top,
    # so a condition that has gone false ends the loop rather than
    # running one more body.
    source = (
        "construct n = 0\n"
        "dejavu n < 3\n"
        "  n = n + 1\n"
        "  glitch\n"
        "flatline\n"
        "trace n\n"
    )
    assert run(source) == "3\n"


def test_wake_leaves_only_the_innermost_loop():
    source = (
        "construct i = 0\n"
        "dejavu i < 2\n"
        "  construct j = 0\n"
        "  dejavu j < 5\n"
        "    redpill j == 1\n"
        "      wake\n"
        "    flatline\n"
        "    trace j\n"
        "    j = j + 1\n"
        "  flatline\n"
        "  trace 9\n"
        "  i = i + 1\n"
        "flatline\n"
    )
    # Inner loop prints 0 then wakes; the OUTER loop keeps going, so the
    # 9 prints twice. If wake broke both, there would be one 9.
    assert run(source) == "0\n9\n0\n9\n"


def test_glitch_belongs_to_the_innermost_loop():
    source = (
        "construct i = 0\n"
        "dejavu i < 2\n"
        "  construct j = 0\n"
        "  dejavu j < 3\n"
        "    j = j + 1\n"
        "    glitch\n"
        "  flatline\n"
        "  trace i\n"
        "  i = i + 1\n"
        "flatline\n"
    )
    assert run(source) == "0\n1\n"


def test_wake_outside_a_loop_is_an_error():
    error = fails("wake\n")
    assert error.message == "'wake' outside a loop"


def test_glitch_outside_a_loop_is_an_error():
    error = fails("glitch\n")
    assert error.message == "'glitch' outside a loop"


def test_an_error_outside_a_loop_carries_its_position():
    error = fails("trace 1\nwake\n")
    assert error.line == 2


def test_wake_inside_an_agent_does_not_reach_the_callers_loop():
    # THE case. An agent called from inside a loop must not be able to
    # break that loop -- the agent's body is not inside a loop, so the
    # wake is an error there, exactly as Python's `break` would be.
    source = (
        "agent f()\n"
        "  wake\n"
        "flatline\n"
        "construct n = 0\n"
        "dejavu n < 3\n"
        "  f()\n"
        "  n = n + 1\n"
        "flatline\n"
    )
    error = fails(source)
    assert error.message == "'wake' outside a loop"


def test_glitch_inside_an_agent_does_not_reach_the_callers_loop():
    source = (
        "agent f()\n"
        "  glitch\n"
        "flatline\n"
        "construct n = 0\n"
        "dejavu n < 3\n"
        "  f()\n"
        "  n = n + 1\n"
        "flatline\n"
    )
    error = fails(source)
    assert error.message == "'glitch' outside a loop"


def test_a_loop_inside_an_agent_still_works():
    # The other half of the agent boundary: a loop INSIDE an agent
    # catches its own wake normally.
    source = (
        "agent f()\n"
        "  construct n = 0\n"
        "  dejavu n < 10\n"
        "    redpill n == 2\n"
        "      wake\n"
        "    flatline\n"
        "    n = n + 1\n"
        "  flatline\n"
        "  jackout n\n"
        "flatline\n"
        "trace f()\n"
    )
    assert run(source) == "2\n"


def test_jackout_beats_a_loop():
    # A jackout inside a loop inside an agent unwinds PAST the loop to
    # the call site. If the loop caught it, this would print nothing or
    # loop forever.
    source = (
        "agent f()\n"
        "  construct n = 0\n"
        "  dejavu n < 10\n"
        "    redpill n == 4\n"
        "      jackout n\n"
        "    flatline\n"
        "    n = n + 1\n"
        "  flatline\n"
        "  jackout 99\n"
        "flatline\n"
        "trace f()\n"
    )
    assert run(source) == "4\n"


def test_wake_still_counts_against_the_step_limit():
    # Steps count executed statements, so neither keyword can be used to
    # loop without being counted. A loop that glitches forever must hit
    # the limit rather than hang.
    source = "dejavu true\n  glitch\nflatline\n"
    out = io.StringIO()
    with pytest.raises(RuntimeErrorML) as caught:
        Interpreter(out=out, max_steps=50).run(parse(lex(source)))
    assert "step limit" in caught.value.message
```

- [ ] **Step 2: Run it to make sure it fails**

```bash
PYTHONPATH=src python3 -m pytest tests/test_loops_run.py -q
```

Expected: FAIL — `_execute` hits its `unhandled statement node` assertion for `Wake`.

- [ ] **Step 3: Add the two signals**

In `src/matrixlang/interpreter.py`, immediately after `_Jackout`:

```python
class _LoopSignal(Exception):
    """A `wake` or a `glitch`, unwinding to the innermost loop.

    Deliberately not a MatrixLangError, for the same reason _Jackout is
    not: these are control flow, not diagnostics, and a stray
    `except MatrixLangError` must never swallow one.

    Carries the position so the "outside a loop" error -- raised where
    the signal escapes rather than where it was written -- can still
    point at the keyword the reader typed.
    """

    __slots__ = ("word", "line", "column")

    def __init__(self, word: str, line: int, column: int) -> None:
        super().__init__()
        self.word = word
        self.line = line
        self.column = column


class _Wake(_LoopSignal):
    pass


class _Glitch(_LoopSignal):
    pass
```

- [ ] **Step 4: Raise them, and catch them in the loop**

In `_execute`, beside the other statement branches:

```python
        elif isinstance(stmt, Wake):
            raise _Wake("wake", stmt.line, stmt.column)
        elif isinstance(stmt, Glitch):
            raise _Glitch("glitch", stmt.line, stmt.column)
```

and replace the `While` branch:

```python
        elif isinstance(stmt, While):
            while self._condition(stmt.condition):
                try:
                    for child in stmt.body:
                        self._execute(child)
                except _Glitch:
                    continue
                except _Wake:
                    break
```

`continue` here re-tests the condition, which is what makes `test_glitch_re_tests_the_condition` pass. Only `_Glitch` and `_Wake` are caught, which is what lets `_Jackout` through.

Import `Glitch` and `Wake` from `matrixlang.nodes` at the top of the file.

- [ ] **Step 5: Close the two escapes**

Both places that currently catch `_Jackout` must also stop a loop signal, or one escapes into a loop it does not belong to.

In `run`, beside the existing `except _Jackout`:

```python
            except _LoopSignal as signal:
                raise RuntimeErrorML(
                    f"'{signal.word}' outside a loop",
                    signal.line,
                    signal.column,
                ) from None
```

In `_call`, after `except _Jackout as jackout:` and before `finally:`:

```python
        except _LoopSignal as signal:
            # THE agent boundary. Without this, `wake` inside an agent
            # called from inside a loop escapes the call and breaks the
            # CALLER's loop -- a program that runs and quietly does
            # something the reader never wrote. The agent's own body is
            # not inside a loop, so this is an error, exactly as Python's
            # `break` in a function body is a SyntaxError.
            raise RuntimeErrorML(
                f"'{signal.word}' outside a loop",
                signal.line,
                signal.column,
            ) from None
```

Note the position comes from the SIGNAL, not from the call site — the reader needs to be pointed at the `wake` they typed.

- [ ] **Step 6: Run the interpreter test**

```bash
PYTHONPATH=src python3 -m pytest tests/test_loops_run.py -q
```

Expected: PASS, 13 tests.

- [ ] **Step 7: Run the whole suite**

```bash
PYTHONPATH=src python3 -m pytest -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/matrixlang/interpreter.py tests/test_loops_run.py
git commit -m "feat: wake leaves a loop, glitch skips to its next turn"
```

---

### Task 4: Render, treeview, and the property

The trap task. Two new node types must enter `tests/treegen.py` in this change, and the corpus must be counted — a statement node that never appears inside a `While` body proves nothing about render nesting.

**This task also carries a dilution audit.** Adding two kinds to a six-kind statement list cuts every existing statement shape's share by 25%. Last time an equivalent change pushed a coverage assertion past its seed range and it was caught only because the suite went red — this time, measure it deliberately.

**Files:**
- Modify: `src/matrixlang/render.py` — the statement branches around 215-224
- Modify: `src/matrixlang/treeview.py` — the statement branches around 120-126
- Modify: `tests/treegen.py` — `gen_statement`
- Modify: `tests/test_roundtrip.py` — a counted corpus test
- Test: `tests/test_loops_render.py` (check whether it exists first)

- [ ] **Step 1: Write the failing render test**

Create `tests/test_loops_render.py`:

```python
"""Loop control — rendering wake and glitch in both faces."""

from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.render import render_ascii, render_glyph


def ascii_face(source):
    return render_ascii(parse(lex(source)))


def glyph_face(source):
    return render_glyph(parse(lex(source)))


def test_wake_renders_bare():
    source = "wake\n"
    assert ascii_face(source) == source


def test_glitch_renders_bare():
    source = "glitch\n"
    assert ascii_face(source) == source


def test_they_render_inside_a_loop_body():
    source = "dejavu true\n  wake\nflatline\n"
    assert ascii_face(source) == source


def test_they_render_in_the_glyph_face():
    assert glyph_face("wake\n") == "ﾉ\n"
    assert glyph_face("glitch\n") == "ﾕ\n"


def test_they_render_indented_inside_a_loop_in_the_glyph_face():
    # Indentation is structural in the rendered output, and a statement
    # with no operand is the shape most likely to lose it.
    source = "dejavu true\n  glitch\nflatline\n"
    assert glyph_face(source) == "ﾃ ｼ\n  ﾕ\nﾗ\n"


def test_a_trailing_comment_survives_the_render():
    source = "wake  # done\n"
    assert ascii_face(source) == source


def test_the_tree_view_names_both():
    from matrixlang.treeview import format_tree

    tree = format_tree(parse(lex("dejavu true\n  wake\n  glitch\nflatline\n")))
    assert "Wake" in tree
    assert "Glitch" in tree
```

- [ ] **Step 2: Run it to make sure it fails**

```bash
PYTHONPATH=src python3 -m pytest tests/test_loops_render.py -q
```

Expected: FAIL with `AssertionError: unhandled statement node: Wake`.

- [ ] **Step 3: Render both**

In `src/matrixlang/render.py`, import `Glitch` and `Wake`, and add before the final `else`:

```python
    elif isinstance(stmt, Wake):
        lines.append(pad + _map(face, "wake") + _trail(stmt, face))
    elif isinstance(stmt, Glitch):
        lines.append(pad + _map(face, "glitch") + _trail(stmt, face))
```

- [ ] **Step 4: Show both in the tree view**

In `src/matrixlang/treeview.py`, import `Glitch` and `Wake`, and add before the final `else`:

```python
    elif isinstance(stmt, Wake):
        lines.append(f"{pad}Wake{tail}")
    elif isinstance(stmt, Glitch):
        lines.append(f"{pad}Glitch{tail}")
```

- [ ] **Step 5: Run the render test**

```bash
PYTHONPATH=src python3 -m pytest tests/test_loops_render.py -q
```

Expected: PASS, 7 tests.

- [ ] **Step 6: Measure the corpus BEFORE touching treegen**

This is the dilution audit's baseline. Write a scratch script (outside the repo) that, for each coverage assertion in `tests/test_roundtrip.py`, counts its shape over that test's own seed range, and record the numbers. The tests to measure are every `test_the_generator_produces_*` in that file.

Record the counts in your report. You will compare against them in Step 9.

- [ ] **Step 7: Put both into the generator**

In `tests/treegen.py`, import `Glitch` and `Wake`, and extend `gen_statement`'s base kinds:

```python
def gen_statement(rng: random.Random, depth: int) -> Stmt:
    kinds = [
        "declare", "assign", "trace", "return", "exprstmt", "indexassign",
        # Loop control. In the BASE list, not gated on depth: these are
        # leaves, and putting them here is what gets them nested inside
        # While, If and agent bodies -- which is the shape that exercises
        # the render's indentation for an operand-less statement.
        "wake", "glitch",
    ]
```

and add the branches:

```python
    elif kind == "wake":
        stmt = Wake()
    elif kind == "glitch":
        stmt = Glitch()
```

Also extend the module docstring — it enumerates what the property covers, and it is the file whose docstring exists to say a node type outside it is invisible.

- [ ] **Step 8: Add the counted corpus test**

Append to `tests/test_roundtrip.py`. Copy the `walk_stmt` shape from `test_the_generator_produces_the_dictionary_shapes_too` — its `IndexAssign` special case and its exact field names (`value`/`condition`, `body`/`then_body`/`else_body`) are the whole correctness of the traversal, and a wrong name silently visits nothing:

```python
def test_the_generator_produces_the_loop_control_shapes_too():
    # Two new STATEMENT node types, and the property only covers shapes
    # treegen produces. A `wake` at a program's top level would round
    # trip trivially; the shape that matters is one INSIDE a loop body,
    # because that is where the render's indentation for an
    # operand-less statement is exercised. So both are counted, and
    # counted separately for the nested case.
    from matrixlang.nodes import Glitch, IndexAssign, Wake

    counts = {"wake": 0, "glitch": 0, "in_loop": 0}

    def walk_stmt(stmt, in_loop):
        if isinstance(stmt, Wake):
            counts["wake"] += 1
            if in_loop:
                counts["in_loop"] += 1
            return
        if isinstance(stmt, Glitch):
            counts["glitch"] += 1
            if in_loop:
                counts["in_loop"] += 1
            return
        if isinstance(stmt, IndexAssign):
            return
        for name in ("body", "then_body", "else_body"):
            for child in getattr(stmt, name, None) or []:
                walk_stmt(child, in_loop or isinstance(stmt, While))

    for seed in range(300):
        for statement in gen_program(random.Random(seed)).statements:
            walk_stmt(statement, False)

    assert counts["wake"], "no `wake` in 300 seeds — the property proves nothing about it"
    assert counts["glitch"], "no `glitch` in 300 seeds"
    assert counts["in_loop"], "no loop-control statement INSIDE a loop body in 300 seeds"
```

`While` is already imported at the top of that file.

- [ ] **Step 9: Re-measure, and compare**

Re-run the Step 6 script against the new generator. Put both sets of numbers in your report, side by side.

```bash
PYTHONPATH=src python3 -m pytest tests/test_roundtrip.py -q
```

Expected: PASS, including all 300 seeds.

**If a coverage assertion fails**, the dilution pushed its shape past its seed range. Raise that test's range — the file already has precedent at 300, 600 and 1000 — and write an HONEST comment saying the share genuinely fell and by how much. Do not write "no change to the shape's real generation probability"; that claim was inherited twice and was false both times.

**If `test_round_trip` fails on a seed**, the render is wrong. Read the printed source; do not adjust the generator.

- [ ] **Step 10: Run the whole suite**

```bash
PYTHONPATH=src python3 -m pytest -q
```

Expected: PASS.

- [ ] **Step 11: Commit**

```bash
git add src/matrixlang/render.py src/matrixlang/treeview.py tests/treegen.py tests/test_roundtrip.py tests/test_loops_render.py
git commit -m "feat: render wake and glitch in both faces; put both in treegen"
```

---

### Task 5: The translator — mapping, and the counter rewrite

**Files:**
- Modify: `src/matrixlang/pytrans/translate.py` — the statement dispatch, `_for` at 461-587, and the refusal catalogue at ~1194 and ~1252
- Modify: `tests/test_pytrans_loops.py`, `tests/test_pytrans_refuse.py`, `tests/test_pytrans_differential.py` (all three exist — append)

**Interfaces:**
- Consumes: `Wake`, `Glitch` nodes; the semantics from Task 3.

- [ ] **Step 1: Write the failing mapping tests**

Append to `tests/test_pytrans_loops.py`. That file already defines `ml(python_source)` — "the MatrixLang a Python snippet translates to, failing loudly on refusal" — so use it rather than redefining one:

```python
def test_break_becomes_wake():
    source = "for x in xs:\n    if x == 1:\n        break\n"
    assert "wake" in ml(source)


def test_continue_becomes_glitch():
    source = "for x in xs:\n    if x == 1:\n        continue\n"
    assert "glitch" in ml(source)


def test_a_glitch_in_a_for_gets_the_increment_before_it():
    # The whole point. A `glitch` jumps to the condition, so without the
    # increment the counter never advances and a correct Python loop
    # translates into one that spins until the step limit.
    source = "for x in xs:\n    if x == 1:\n        continue\n    print(x)\n"
    out = ml(source)
    glitch_line = [i for i, line in enumerate(out.splitlines()) if "glitch" in line][0]
    assert "n = n + 1" in out.splitlines()[glitch_line - 1]


def test_a_wake_in_a_for_gets_no_increment():
    # `wake` leaves the loop, so a skipped increment is exactly right.
    source = "for x in xs:\n    if x == 1:\n        break\n    print(x)\n"
    out = ml(source)
    wake_line = [i for i, line in enumerate(out.splitlines()) if "wake" in line][0]
    assert "n = n + 1" not in out.splitlines()[wake_line - 1]


def test_a_glitch_in_a_plain_while_gets_no_increment():
    # A Python `while` has no counter to advance.
    source = "n = 0\nwhile n < 3:\n    n = n + 1\n    continue\n"
    out = ml(source)
    glitch_line = [i for i, line in enumerate(out.splitlines()) if "glitch" in line][0]
    before = out.splitlines()[glitch_line - 1]
    assert before.strip() == "n = n + 1"  # the reader's own line, not an inserted one


def test_a_loop_with_no_glitch_is_unchanged():
    # Loops without loop control must keep byte-for-byte the output the
    # translator produced before this change, because the playground
    # shows this code to the reader.
    source = "for x in xs:\n    print(x)\n"
    assert ml(source) == (
        "construct n = 0\n"
        "dejavu n < length xs\n"
        "  trace xs[n]\n"
        "  n = n + 1\n"
        "flatline\n"
    )
```

If the last test's expected text does not match what the translator produces today, **fix the test to match today's output, not the translator** — the whole point of that test is that today's output is preserved. Get today's text by running the translator on that source before you change anything.

- [ ] **Step 2: Write the failing refusal-removal test**

Append to `tests/test_pytrans_refuse.py`:

```python
def test_break_and_continue_are_no_longer_refused():
    result = translate("for x in xs:\n    break\n")
    assert isinstance(result, Translated)
    result = translate("for x in xs:\n    continue\n")
    assert isinstance(result, Translated)


def test_loop_else_is_still_refused():
    # Python's loop-else runs only when no `break` fired. Adding `break`
    # without keeping this refusal would let a `for ... else` translate
    # into something that quietly means the wrong thing.
    result = translate("for x in xs:\n    break\nelse:\n    print(1)\n")
    assert isinstance(result, Refusals)
    assert "for ... else" in result.items[0].reason
```

- [ ] **Step 3: Run both to make sure they fail**

```bash
PYTHONPATH=src python3 -m pytest tests/test_pytrans_loops.py tests/test_pytrans_refuse.py -q
```

Expected: FAIL — `break` and `continue` are still refused.

- [ ] **Step 4: Map the two statements**

In `src/matrixlang/pytrans/translate.py`, in the statement dispatch beside the other `isinstance(node, ast.…)` branches:

```python
        if isinstance(node, ast.Break):
            return [Wake()]
        if isinstance(node, ast.Continue):
            return [Glitch()]
```

Import `Glitch` and `Wake` from `matrixlang.nodes`.

Then remove `"Break"` and `"Continue"` from BOTH the `_DESCRIBE` catalogue (~line 1194) and the idiom table (~line 1252). Removing them from only one leaves a dangling half.

- [ ] **Step 5: Add the increment rewrite**

Still in `translate.py`, add a module-level helper beside `_hoist_declares`:

```python
def _increment_before_glitches(body: list[Stmt], counter: str) -> list[Stmt]:
    """Put the loop counter's increment before every `glitch` in `body`.

    A `glitch` jumps to the loop's condition, so it skips the increment
    the desugaring appends at the END of the body -- and a correct Python
    loop becomes one that spins until the step limit.

    Walks the ALREADY-TRANSLATED statements rather than the Python ast,
    which is what makes the boundary rule fall out for free:

      - A nested Python loop is already a While node here, so its own
        `glitch` sits behind the stop and keeps the increment its own
        translation inserted.
      - A Python `while` has no counter, and stopping at While gives that
        too.
      - A nested `for` in a `for` gets the INNER counter incremented by
        the inner translation, and this walk leaves it alone.

    `wake` needs nothing: it leaves the loop, so a skipped increment is
    exactly right.
    """
    out: list[Stmt] = []
    for statement in body:
        if isinstance(statement, Glitch):
            out.append(
                Assign(counter, Binary(Name(counter), TokenType.PLUS, NumberLiteral(1)))
            )
            out.append(statement)
        elif isinstance(statement, If):
            statement.then_body = _increment_before_glitches(
                statement.then_body, counter
            )
            if statement.else_body is not None:
                statement.else_body = _increment_before_glitches(
                    statement.else_body, counter
                )
            out.append(statement)
        else:
            # While and FunctionDef fall here deliberately -- a `glitch`
            # inside either belongs to that loop, not this one.
            out.append(statement)
    return out
```

Then call it in `_for`, immediately before the existing trailing-increment append at `translate.py:583`:

```python
        body = _increment_before_glitches(body, counter)
        body.append(
            Assign(counter, Binary(Name(counter), TokenType.PLUS, NumberLiteral(1)))
        )
```

`Assign`, `Binary`, `If`, `Name`, `NumberLiteral` and `TokenType` are all already imported in this file (`translate.py:14-20`) — the only names you need to add to that import are `Glitch` and `Wake`.

- [ ] **Step 6: Run the translator tests**

```bash
PYTHONPATH=src python3 -m pytest tests/test_pytrans_loops.py tests/test_pytrans_refuse.py -q
```

Expected: PASS.

- [ ] **Step 7: Add the four differential cases**

These are the ones that matter. A wrong counter produces a plausible loop that skips or repeats an element — no structural assertion on the output text would catch it. Append to `tests/test_pytrans_differential.py`, using its existing `agree()` helper:

```python
def test_a_continue_nested_two_ifs_deep_agrees():
    # Catches the walk not descending far enough.
    agree(
        "xs = [1, 2, 3, 4]\n"
        "for x in xs:\n"
        "    if x > 1:\n"
        "        if x < 4:\n"
        "            continue\n"
        "    print(x)\n"
    )


def test_a_continue_in_a_while_nested_in_a_for_agrees():
    # Catches the walk descending too far and double-incrementing the
    # OUTER counter for a `glitch` that belongs to the inner while.
    agree(
        "xs = [1, 2]\n"
        "for x in xs:\n"
        "    n = 0\n"
        "    while n < 3:\n"
        "        n = n + 1\n"
        "        if n == 2:\n"
        "            continue\n"
        "        print(n)\n"
        "    print(x)\n"
    )


def test_a_continue_in_a_nested_for_agrees():
    # Catches the wrong counter being incremented.
    agree(
        "rows = [[1, 2], [3, 4]]\n"
        "for row in rows:\n"
        "    for cell in row:\n"
        "        if cell == 2:\n"
        "            continue\n"
        "        print(cell)\n"
    )


def test_a_break_in_a_for_agrees():
    agree(
        "xs = [1, 2, 3, 4]\n"
        "for x in xs:\n"
        "    if x == 3:\n"
        "        break\n"
        "    print(x)\n"
    )


def test_break_and_continue_together_agree():
    agree(
        "xs = [1, 2, 3, 4, 5]\n"
        "for x in xs:\n"
        "    if x == 2:\n"
        "        continue\n"
        "    if x == 4:\n"
        "        break\n"
        "    print(x)\n"
    )
```

- [ ] **Step 8: Run the differential tests**

```bash
PYTHONPATH=src python3 -m pytest tests/test_pytrans_differential.py -q
```

Expected: PASS. A failure means Python and MatrixLang printed different text — read the assertion's `python=` / `matrixlang=` values and fix whichever side is wrong. **Never weaken a case to make it pass.**

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

Expected: suite PASS, both checks OK.

- [ ] **Step 10: Commit**

```bash
git add src/matrixlang/pytrans/translate.py tests/test_pytrans_loops.py tests/test_pytrans_refuse.py tests/test_pytrans_differential.py
git commit -m "feat(pytrans): break and continue reach wake and glitch"
```

---

### Task 6: Documentation and the register

**Files:**
- Modify: `README.md`, `docs/LEARNING-MATRIXLANG.md`, `docs/TECHNICAL-OVERVIEW.md`, `docs/PYTHON-PARITY.md`, `site/index.html`, `src/matrixlang/glyphs.py` (docstring), and any other file your sweep finds

The facts that changed: keywords **22 → 24**; glyph slots **52 → 54 used, 4 → 2 free**; `wake` → `ﾉ`, `glitch` → `ﾕ`.

- [ ] **Step 1: Sweep for stale counts across EVERY extension**

```bash
grep -rn "twenty-two\|52 slot\|52-slot\|52-entry\|4 slots\|4 free" --include='*' . | grep -v '.git/' | grep -v 'docs/superpowers/'
```

Read every hit and judge it. `docs/superpowers/specs/` and `docs/superpowers/plans/` are historical records of past decisions and must NOT be rewritten. Unrelated numbers stay. Only current-fact claims that are now false get fixed.

**`site/index.html` carries the keyword count in prose.** A sweep restricted to `*.py` and `*.md` missed it last time and shipped a false claim to the live landing page.

- [ ] **Step 2: Update the counts you found**

Including at minimum: `README.md`'s "twenty-two keywords", `docs/LEARNING-MATRIXLANG.md`'s opening count and its glyph-table prose, `docs/TECHNICAL-OVERVIEW.md`'s slot claims, `site/index.html`, and `src/matrixlang/glyphs.py`'s module docstring.

Add the two new cells to the learning guide's glyph table:

```
| `wake` `ﾉ` | `glitch` `ﾕ` | | | | | |
```

- [ ] **Step 3: Check the module map's line counts**

`docs/TECHNICAL-OVERVIEW.md` has a hand-maintained table of module line counts. This change touches `tokens.py`, `nodes.py`, `parser.py`, `interpreter.py`, `render.py`, `treeview.py` and `glyphs.py`. Verify each with `wc -l` and correct the rows that are wrong.

- [ ] **Step 4: Add a teaching section to the learning guide**

After the loops section, add:

````
### `wake` and `glitch`

A `dejavu` normally runs until its condition goes false. Two keywords let
you leave early.

```
construct n = 0
dejavu n < 10
  n = n + 1
  redpill n == 3
    glitch
  flatline
  redpill n == 6
    wake
  flatline
  trace n
flatline
```

```
1
2
4
5
```

`wake` leaves the loop entirely — you wake up, and the loop is over.
`glitch` skips the rest of this turn and goes back to the condition. The
name is the film's own: a déjà vu *is* a glitch in the Matrix, and the
loop keyword is `dejavu`.

Both are bare words on a line of their own, like a bare `jackout`. Both
belong to the **innermost** loop they sit in, so a `wake` inside a loop
inside another loop leaves only the inner one.

Two rules worth knowing:

- Outside a loop, either one is an error. That includes inside an agent
  called from a loop — the agent's body is not in a loop, so it cannot
  reach out and stop the caller's.
- `jackout` beats both. A `jackout` inside a loop inside an agent returns
  from the agent, loop and all.
````

- [ ] **Step 5: Run every example in the new section**

The learning guide claims every example in it was executed before it shipped. Honour that. Write the block to a scratch file outside the repo and run it:

```bash
PYTHONPATH=src python3 -m matrixlang run /tmp/ml-loop-check.rain
```

Paste the real output into your report. **If it differs from what the section claims, the documentation is wrong** — fix the documentation, and say so.

- [ ] **Step 6: Update the register**

In `docs/PYTHON-PARITY.md`:

- `**Keywords (22)**` → `**Keywords (24)**`, list gains `wake` `glitch`.
- `**Glyph budget** — 52 slots used, 4 free.` → `54 slots used, 2 free.`
- Item 2's heading gains `— **done**`, and its body becomes a record of what shipped: `wake` and `glitch`, the innermost-loop rule, the agent boundary, and that the translator inserts the counter increment before each `glitch` inside a desugared `for`.
- Item 3's heading gains `— *next*`.
- In the constraints section, `4 slots left` → `2 slots left`, and update the allocation paragraph: item 2 is spent, items 3 and 4 remain.

- [ ] **Step 7: Run the whole suite**

```bash
PYTHONPATH=src python3 -m pytest -q
```

Expected: PASS. `tests/test_site_examples.py` and `tests/test_package.py` read repository files, so a documentation edit can genuinely turn a test red.

- [ ] **Step 8: Commit**

```bash
git add README.md docs/LEARNING-MATRIXLANG.md docs/TECHNICAL-OVERVIEW.md docs/PYTHON-PARITY.md site/index.html src/matrixlang/glyphs.py
git commit -m "docs: wake and glitch — 24 keywords, 54 slots, 2 free"
```

---

## Verification gates

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

The last one is expected to show `site/index.html` and nothing else — prose only. `no_semantics.py`, which inspects `site/*.js`, is the real guard on the browser half.

## Self-review notes

Four places this change can be wrong while looking right:

1. **`_call`'s loop-signal catch (Task 3, Step 5).** Without it, `wake` inside an agent called from inside a loop breaks the CALLER's loop — a program that runs and quietly does something the reader never wrote. `tests/test_loops_run.py::test_wake_inside_an_agent_does_not_reach_the_callers_loop` is the guard.
2. **`_increment_before_glitches`'s boundary (Task 5, Step 5).** Descending into a nested `While` double-increments the outer counter; not descending into an `If` misses the common case. Both failure modes are caught only by the differential tests, because both produce output that parses and runs.
3. **The treegen dilution (Task 4, Steps 6 and 9).** Two new statement kinds cut every existing kind's share by 25%. Measure it; do not infer it from a green suite.
4. **`test_a_loop_with_no_glitch_is_unchanged` (Task 5, Step 1).** It is the only thing standing between this change and a quiet regression in every translated loop's readability.
