# Stage 8 Strings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make strings indexable and orderable, so `name[0]` reads a character and `"Neo" < "Trinity"` sorts — without making strings mutable.

**Architecture:** Four changes, all in `interpreter.py`. Two are widening an `is_list` check to accept strings, one is a new type rule in the ordering branch, and one is a deliberate **refusal** that must not be widened. No parser, no AST node, no glyph slot — indexing syntax already parses and fails at runtime, so this stage is purely semantic.

**Tech Stack:** Python ≥3.11, standard library only. pytest.

**Spec:** `docs/superpowers/specs/2026-08-02-stage-8-strings-design.md` (approved, PR #45). Issue #44.

## Global Constraints

Every task's requirements implicitly include all of these.

- **Python ≥3.11.** No third-party runtime dependencies. `pytest` is the only dev dependency.
- **Value type checks use `type(v) is X`, never `isinstance`** — via the `is_list` / `is_str` / `is_int` predicates in `values.py`. `isinstance` on *AST node* types is correct and used freely; the ban is on runtime value checks.
- **Every error carries a line and a column**, raised as a `RuntimeErrorML`.
- **No Python exception or class name may reach a user-facing diagnostic.** This is a documented project claim (technical overview §6) and Task 3 exists because this stage can break it.
- **`values.py` may import nothing** (`tests/test_architecture.py:23` pins `"values": set()`). This stage adds nothing to it.
- **No syntax changes.** The glyph table stays at **38**. `tests/treegen.py` is untouched. If you find yourself editing `lexer.py`, `parser.py`, `nodes.py`, `render.py`, `treeview.py` or `glyphs.py`, stop — the plan is wrong or you have misread the task.
- **Baseline: 1,138 tests pass on `main`** before this plan begins. No task may reduce that.
- **macOS venv quirk:** if any command reports `ModuleNotFoundError: No module named 'matrixlang'`, run `chflags -R nohidden .venv` and retry. Platform quirk, not a code failure. It can happen at any time.

### Error messages this stage introduces or changes

Named here so a test and its implementation cannot be specified separately and contradict each other — which happened in Stage 7 and survived to the final review.

| Situation | Exact message |
| --- | --- |
| Ordering operands of different or unorderable types | `cannot order {type_name(left)} with {type_name(right)}` |
| Index past the end | `index {index} is past the end of a {type_name(target)} of length {len(target)}` |
| Assigning to a character of a string | `a string cannot be changed — build a new one with +` |

The first two **replace** existing text. The third is new.

---

## File Structure

| File | Change | Responsibility after |
| --- | --- | --- |
| `src/matrixlang/interpreter.py` | Modify | Ordering accepts two strings; `_element`/`_check_index` accept strings; `IndexAssign` refuses them with an explanation |
| `tests/test_strings_run.py` | Create | Every behavioural test for this stage |
| `docs/LEARNING-MATRIXLANG.md` | Modify | Task 4 |
| `README.md` | Modify | Task 4 |
| `docs/TECHNICAL-OVERVIEW.md` | Modify | Task 4 |

One new test file rather than appending to `tests/test_lists_run.py`, matching how Stage 6 and Stage 7 each got their own `test_*_run.py`.

---

## Task 1: Ordering accepts two strings

**Files:**
- Modify: `src/matrixlang/interpreter.py:444-456` (`_comparison`'s ordering branch)
- Test: `tests/test_strings_run.py` (create)

**Interfaces:**
- Consumes: `is_int`, `is_str`, `type_name` from `values.py` — all already imported by `interpreter.py`.
- Produces: nothing other modules call. Tasks 2 and 3 are independent of this one.

**Why this does not touch `_require_int`.** That helper is called from **four** sites: unary minus (`interpreter.py:317`), ordering (`:446`, `:447`), and arithmetic (`:477`, `:478`). Arithmetic and unary minus must keep requiring integers — `1 - "a"` and `-"a"` stay errors. Only the ordering pair changes, so the ordering branch gets its own check and `_require_int` is left exactly as it is.

**A position change you must expect.** The current ordering error is raised by `_require_int` with the *operand's* position (`node.left.line/column`). The new one uses the *operator's* position (`node.line/column`), matching `cannot compare X with Y` at `:466` and `cannot add X and Y` at `:429`. So `trace true < 5` moves from column 7 to column 12. That is deliberate: all three binary-operator failures then report the same place, and the error is about the pair rather than about either operand.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_strings_run.py`:

```python
"""Stage 8 — strings stop being opaque: ordering, then indexing.

Split from test_lists_run.py the way Stage 6 and Stage 7 each got their
own run-tests file. Nothing here needs new syntax: indexing already
parsed before this stage and failed at runtime.
"""

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


# --- Ordering -----------------------------------------------------------


def test_two_strings_can_be_ordered():
    assert run('trace "Neo" < "Trinity"\n') == "true\n"
    assert run('trace "Trinity" < "Neo"\n') == "false\n"


def test_every_ordering_operator_works_on_strings():
    assert run('trace "a" < "b"\n') == "true\n"
    assert run('trace "a" > "b"\n') == "false\n"
    assert run('trace "a" <= "a"\n') == "true\n"
    assert run('trace "a" >= "b"\n') == "false\n"


def test_ordering_is_codepoint_order_not_alphabetical():
    # THE gotcha. Every uppercase letter sorts before every lowercase one,
    # same as Python, Java and C. Pinned rather than only documented,
    # because documentation drifts and a test does not.
    assert run('trace "a" < "B"\n') == "false\n"
    assert run('trace "B" < "a"\n') == "true\n"


def test_integers_still_order():
    assert run("trace 3 < 5\n") == "true\n"
    assert run("trace 5 <= 5\n") == "true\n"


def test_mixed_operands_report_the_pair_exactly():
    # Exact string, not a substring. The old message ("left operand must
    # be an integer, got string") becomes FALSE once strings are
    # orderable, and a substring check like `"string" in message` would
    # pass against both. That exact failure shipped in Stage 7.
    assert fails('trace "a" < 1\n').message == "cannot order string with integer"
    assert fails('trace 1 < "a"\n').message == "cannot order integer with string"


def test_booleans_are_still_unorderable():
    assert fails("trace true < 5\n").message == "cannot order boolean with integer"
    assert fails("trace true < false\n").message == "cannot order boolean with boolean"


def test_lists_are_still_unorderable():
    # Element-wise ordering needs rules for unequal lengths and mixed
    # element types that the spec deliberately does not give (§8).
    assert fails("trace [1] < [2]\n").message == "cannot order list with list"


def test_the_ordering_error_points_at_the_operator():
    # Matches `cannot compare` and `cannot add`, which both report the
    # operator's position rather than an operand's.
    error = fails('trace "a" < 1\n')
    assert (error.line, error.column) == (1, 11)


def test_arithmetic_still_requires_integers():
    # _require_int has four call sites and only the two ordering ones
    # changed. These must not have moved.
    assert 'must be an integer' in fails('trace 1 - "a"\n').message
    assert 'must be an integer' in fails('trace -"a"\n').message
    assert 'must be an integer' in fails('trace "a" * 2\n').message
```

- [ ] **Step 2: Run them to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_strings_run.py -q
```

Expected: FAIL. `test_two_strings_can_be_ordered` fails with `left operand must be an integer, got string`; the exact-message tests fail on the old wording.

`test_integers_still_order` and `test_arithmetic_still_requires_integers` should **pass already** — they are the regression guards.

- [ ] **Step 3: Implement**

In `src/matrixlang/interpreter.py`, replace the two `_require_int` calls at the top of `_comparison`'s ordering branch:

```python
    def _comparison(self, node: Binary, left: object, right: object) -> object:
        if node.op in _ORDERING_OPS:
            # Not _require_int: that helper also serves unary minus and
            # arithmetic, which still require integers. Ordering is now a
            # rule about the PAIR — both integers or both strings — so it
            # gets its own check and reports the operator's position, the
            # way `cannot compare` and `cannot add` already do.
            orderable = (is_int(left) and is_int(right)) or (
                is_str(left) and is_str(right)
            )
            if not orderable:
                raise RuntimeErrorML(
                    f"cannot order {type_name(left)} with {type_name(right)}",
                    node.line,
                    node.column,
                )
            if node.op is TokenType.LT:
                return left < right
            if node.op is TokenType.GT:
                return left > right
            if node.op is TokenType.LTE:
                return left <= right
            if node.op is TokenType.GTE:
                return left >= right
            raise AssertionError(f"unhandled ordering operator: {node.op.name}")
```

The four comparison returns are unchanged — Python's `<` on two `str` is codepoint order, which is what the spec chose.

`is_str` and `is_int` are already imported in this module; confirm before adding anything.

- [ ] **Step 4: Run the new tests**

```bash
.venv/bin/python -m pytest tests/test_strings_run.py -q
```

Expected: PASS.

- [ ] **Step 5: Run the full suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS at ≥1,138 plus your new tests. If a pre-existing test fails, read it before changing it — it may be asserting the old ordering message, in which case update the assertion to the new exact text. Do **not** weaken an assertion to a substring to make it pass.

- [ ] **Step 6: Commit**

```bash
git add src/matrixlang/interpreter.py tests/test_strings_run.py
git commit -m "feat: two strings can be ordered, and the message names the pair"
```

---

## Task 2: Reading a character

**Files:**
- Modify: `src/matrixlang/interpreter.py:337-345` (`_element`), `:347-366` (`_check_index`)
- Test: `tests/test_strings_run.py` (append)

**Interfaces:**
- Consumes: `is_list`, `is_str`, `is_int`, `type_name` — all already imported.
- Produces: `_element` and `_check_index` accept a `list` **or** a `str`. Task 3 relies on `_check_index` accepting a string.

**What you are NOT doing.** `IndexAssign` does not call `_element` — it has its own `is_list` guard at `:227` and calls `_check_index` directly. So generalising `_element` here does **not** make `s[0] = "X"` work. After this task `s[0] = "X"` still reports `cannot index string`, which is now misleading; Task 3 fixes that. Leave it alone in this task.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_strings_run.py`:

```python
# --- Reading a character ------------------------------------------------


def test_a_string_can_be_indexed():
    assert run('trace "Neo"[0]\n') == "N\n"
    assert run('trace "Neo"[2]\n') == "o\n"


def test_a_character_is_a_one_character_string():
    # There is no character type. `s[0]` is a string, so it can be
    # concatenated, compared and measured like any other.
    assert run('trace "Neo"[0] + "eo"\n') == "Neo\n"
    assert run('trace "Neo"[0] == "N"\n') == "true\n"
    assert run('trace length "Neo"[0]\n') == "1\n"


def test_the_regress_terminates_because_you_stop_asking():
    assert run('trace "Neo"[0][0][0]\n') == "N\n"


def test_indexing_a_name_holding_a_string():
    assert run('construct name = "Neo"\ntrace name[1]\n') == "e\n"


def test_walking_a_string_character_by_character():
    # The program this stage exists for.
    source = (
        'construct name = "Neo"\n'
        "construct n = 0\n"
        "dejavu n < length name\n"
        "  trace name[n]\n"
        "  n = n + 1\n"
        "flatline\n"
    )
    assert run(source) == "N\ne\no\n"


def test_a_string_inside_a_list_can_be_indexed():
    assert run('construct xs = ["Neo"]\ntrace xs[0][1]\n') == "e\n"


# --- Read errors, shared with lists -------------------------------------


def test_indexing_past_the_end_of_a_string_says_string():
    error = fails('trace "Neo"[5]\n')
    assert error.message == "index 5 is past the end of a string of length 3"


def test_the_bounds_message_differs_from_the_list_one_only_by_the_noun():
    # They come from the same _check_index. Asserting them together is
    # what stops a future edit from forking one and not the other.
    string_error = fails('trace "Neo"[5]\n').message
    list_error = fails("construct xs = [1, 2, 3]\ntrace xs[5]\n").message
    assert string_error == "index 5 is past the end of a string of length 3"
    assert list_error == "index 5 is past the end of a list of length 3"
    assert string_error.replace("string", "list") == list_error


def test_a_negative_string_index_is_an_error():
    assert (
        fails('trace "Neo"[-1]\n').message
        == "an index cannot be negative — use xs[length xs - 1]"
    )


def test_a_non_integer_string_index_is_an_error():
    assert (
        fails('trace "Neo"["a"]\n').message
        == "an index must be an integer, got string"
    )


def test_indexing_an_empty_string_is_an_error():
    assert (
        fails('trace ""[0]\n').message
        == "index 0 is past the end of a string of length 0"
    )


def test_indexing_a_boolean_is_still_an_error():
    assert fails("trace true[0]\n").message == "cannot index boolean"
```

- [ ] **Step 2: Run them to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_strings_run.py -q -k "character or string_can or walking or bounds or regress"
```

Expected: FAIL with `cannot index string`.

- [ ] **Step 3: Implement**

In `src/matrixlang/interpreter.py`, change `_element`'s guard and `_check_index`'s signature and bounds message:

```python
    def _element(self, target: object, index: object, node) -> object:
        """Bounds-check and read. Shared by Index and IndexAssign so the
        two cannot disagree about what a legal index is.

        Strings read like lists: `s[i]` is a one-character string, because
        the language has no character type. `target[index]` on a Python
        str already returns exactly that, so the read generalises for
        free. WRITING to a string is refused separately — see the
        IndexAssign branch in _execute.
        """
        if not (is_list(target) or is_str(target)):
            raise RuntimeErrorML(
                f"cannot index {type_name(target)}", node.line, node.column
            )
        self._check_index(target, index, node)
        return target[index]

    def _check_index(self, target: list | str, index: object, node) -> None:
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
            # type_name rather than a hardcoded "list": one message serves
            # both, so the two can never drift into disagreeing about the
            # same rule.
            raise RuntimeErrorML(
                f"index {index} is past the end of a {type_name(target)} "
                f"of length {len(target)}",
                node.line,
                node.column,
            )
```

Note the f-string split moved: the length now follows `of length`, so check the assembled string has exactly one space between `{type_name(target)}` and `of`.

- [ ] **Step 4: Run the new tests**

```bash
.venv/bin/python -m pytest tests/test_strings_run.py -q
```

Expected: PASS.

- [ ] **Step 5: Run the full suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS. `tests/test_lists_run.py` asserts the list bounds message; it must still read `index 5 is past the end of a list of length 2` — if it fails, the f-string was reassembled wrongly, not the test.

- [ ] **Step 6: Commit**

```bash
git add src/matrixlang/interpreter.py tests/test_strings_run.py
git commit -m "feat: a string can be read one character at a time"
```

---

## Task 3: Writing to a string is refused, and explained

**Files:**
- Modify: `src/matrixlang/interpreter.py:223-234` (the `IndexAssign` branch of `_execute`)
- Test: `tests/test_strings_run.py` (append)

**Interfaces:**
- Consumes: `_check_index` accepting a string (Task 2) — though this task does not reach it for strings.
- Produces: nothing later depends on.

**This is the hazard task. Read this before you edit anything.**

Tasks 1 and 2 were both "widen a check." This one looks identical and is the opposite. If you widen `IndexAssign`'s `is_list` guard the way `_element`'s was widened, `s[0] = "X"` reaches Python's own item assignment:

```
TypeError: 'str' object does not support item assignment
```

That is an **uncaught Python exception escaping into a `.rain` program** — precisely what technical overview §6 claims cannot happen, and that claim is load-bearing for the project's security posture. The careless version of this stage is a posture regression and it looks like the careful version.

So the guard becomes a **three-way** branch, not a widened two-way one.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_strings_run.py`:

```python
# --- Writing to a string is refused -------------------------------------


def test_assigning_to_a_character_explains_rather_than_refusing_bare():
    # The asymmetry with lists is real (xs[0] = 9 works) so the message
    # has to teach it, not just say no.
    error = fails('construct s = "Neo"\ns[0] = "X"\n')
    assert error.message == "a string cannot be changed — build a new one with +"


def test_assigning_to_a_character_never_raises_a_python_exception():
    # THE test for this task. Widening this guard the way _element's was
    # widened lets s[0] = "X" reach Python's item assignment and raise
    # TypeError: 'str' object does not support item assignment — a Python
    # exception name escaping into a .rain program, which technical
    # overview §6 says cannot happen.
    with pytest.raises(RuntimeErrorML):
        run('construct s = "Neo"\ns[0] = "X"\n')


def test_the_refusal_carries_a_position():
    error = fails('construct s = "Neo"\ns[0] = "X"\n')
    assert error.line == 2
    assert error.column >= 1


def test_assigning_to_a_string_literal_is_refused_at_parse_time():
    # Verified: this never reaches the interpreter. The statement
    # dispatcher requires an IDENT to begin an assignment, so a literal
    # target is rejected by the parser with "expected a statement, found
    # '"Neo"'". Pinned so a future parser change cannot silently route it
    # into the branch this task edits without anyone noticing.
    from matrixlang.errors import ParseError

    with pytest.raises(ParseError) as caught:
        run('"Neo"[0] = "X"\n')
    assert "expected a statement" in caught.value.message


def test_a_nested_string_inside_a_list_is_still_immutable():
    error = fails('construct xs = ["Neo"]\nxs[0][0] = "X"\n')
    assert error.message == "a string cannot be changed — build a new one with +"


def test_assigning_to_a_list_element_still_works():
    # The branch this task edits is the one lists go through. Regression
    # guard: do not break Stage 7 while adding the string case.
    assert run("construct xs = [1, 2]\nxs[0] = 9\ntrace xs[0]\n") == "9\n"


def test_assigning_to_a_non_indexable_still_says_cannot_index():
    assert fails("construct n = 1\nn[0] = 2\n").message == "cannot index integer"
```

Two of these were verified against the real interpreter while writing this plan, so do not be surprised by them:

- `"Neo"[0] = "X"` is a **`ParseError`**, not a runtime error — the statement dispatcher requires an `IDENT` to begin an assignment, so it never reaches the branch you are editing. The test above expects that. Do not change the parser to "fix" it.
- `xs[0][0] = "X"` on a list holding a string **does** reach `IndexAssign`, with `target` bound to the string, and currently reports `cannot index string` at line 2 column 7. That is the case your new branch turns into the immutability message.

- [ ] **Step 2: Run them to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_strings_run.py -q -k "assigning or refusal or immutable"
```

Expected: FAIL — the message is currently `cannot index string`.

- [ ] **Step 3: Implement**

In `src/matrixlang/interpreter.py`, replace the guard in the `IndexAssign` branch of `_execute`:

```python
        elif isinstance(stmt, IndexAssign):
            target = self._value_of(stmt.target, stmt)
            index = self._value_of(stmt.index, stmt)
            value = self._value_of(stmt.value, stmt)
            # Three ways, not two. A string IS indexable — _element reads
            # one happily — so `cannot index string` would now be a lie.
            # And widening this to `is_list or is_str` the way _element
            # was widened would let the assignment reach Python's own item
            # assignment and raise TypeError, putting a Python exception
            # name in front of someone running a .rain file.
            if is_str(target):
                raise RuntimeErrorML(
                    "a string cannot be changed — build a new one with +",
                    stmt.index.line,
                    stmt.index.column,
                )
            if not is_list(target):
                raise RuntimeErrorML(
                    f"cannot index {type_name(target)}",
                    stmt.index.line,
                    stmt.index.column,
                )
            self._check_index(target, index, stmt.index)
            target[index] = value
```

- [ ] **Step 4: Run the new tests**

```bash
.venv/bin/python -m pytest tests/test_strings_run.py -q
```

Expected: PASS.

- [ ] **Step 5: Teeth-check the guard — MANDATORY**

Temporarily replace the two guards above with the naive widening:

```python
            if not (is_list(target) or is_str(target)):
                raise RuntimeErrorML(
                    f"cannot index {type_name(target)}",
                    stmt.index.line,
                    stmt.index.column,
                )
```

Then run:

```bash
.venv/bin/python -m pytest tests/test_strings_run.py -q -k "never_raises_a_python"
```

Expected: **FAIL**, and the failure must be a `TypeError: 'str' object does not support item assignment` rather than an assertion mismatch. Paste the real output into your report — that output is the whole justification for this task.

**Restore with an editor, not `git checkout`** — other files may have uncommitted work and `git checkout` would destroy it. Re-run the tests to confirm you are green again.

- [ ] **Step 6: Run the full suite**

```bash
.venv/bin/python -m pytest -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/matrixlang/interpreter.py tests/test_strings_run.py
git commit -m "fix: writing to a string is refused with a reason, not a Python TypeError"
```

---

## Task 4: The documentation

**Files:**
- Modify: `docs/LEARNING-MATRIXLANG.md`, `README.md`, `docs/TECHNICAL-OVERVIEW.md`
- Test: manual verification of every example

**Interfaces:**
- Consumes: the whole working feature.
- Produces: shipped documentation.

**The standard this project holds documentation to.** Every code example must be **executed and its stated output pasted from the real run**, never remembered or predicted. The existing tutorial was held to this: all 32 of its original examples were run and two quoted error messages were found wrong and fixed. Stage 7's section was held to it again and a reviewer independently re-ran 13 of them byte-for-byte.

- [ ] **Step 1: Verify the feature through the real CLI**

```bash
cat > /tmp/strings-demo.rain <<'RAIN'
construct name = "Neo"

construct n = 0
dejavu n < length name
  trace name[n]
  n = n + 1
flatline

trace "Neo" < "Trinity"
trace "a" < "B"
RAIN
.venv/bin/matrixlang run --no-window /tmp/strings-demo.rain
.venv/bin/matrixlang parse /tmp/strings-demo.rain | head -20
.venv/bin/matrixlang render --face glyph /tmp/strings-demo.rain
```

Expected: `N e o` on three lines, then `true`, then `false`. `parse` prints a tree with no traceback. The glyph render contains no ASCII brackets or commas.

Paste the real output into your report.

- [ ] **Step 2: Extend the tutorial's strings coverage**

`docs/LEARNING-MATRIXLANG.md` has a `## 3. Types` section that currently describes strings as atoms, and a `## 7. Lists` section. Add string indexing and ordering where they read most naturally — most likely a short subsection under §3 for ordering and a subsection near §7 for indexing, since indexing is easiest to explain once `[]` has been introduced for lists. Read the file and decide; the requirement is that it teaches well, not that it goes in a particular slot.

Cover:
- `name[0]` and that a character is a one-character string
- walking a string with `dejavu`, the program from Step 1
- `"Neo" < "Trinity"`
- **the codepoint gotcha** — `"a" < "B"` is `false`, one sentence, with the reason
- **the immutability asymmetry** — `xs[0] = 9` works, `s[0] = "X"` does not, and why: a string handed to an agent stays put, which lists deliberately gave up

Update the file's opening line if it states a type or keyword count that this stage changes. It should not — no keyword was added — but check.

Every example executed.

- [ ] **Step 3: Update the README and technical overview**

`README.md`: strings are indexable and orderable now; update the "Working today" paragraph and the test count.

`docs/TECHNICAL-OVERVIEW.md`:
- Header counts — lines and tests. Recompute with `find`/`wc -l`, do not guess.
- §4 "Semantics worth knowing" — a bullet on strings being indexable but immutable, and why that asymmetry with lists is deliberate.
- §9 (deliberately absent) — remove string indexing; add slicing and string methods in its place, and note that `and`/`or`/`not` is now the largest remaining gap.
- Consider a sentence near §6 (security posture) on the `IndexAssign` trap: this stage's careless version would have let a Python `TypeError` escape into a `.rain` program, and the teeth-check is what proves it does not. It belongs beside the existing §6 material about what a `.rain` program cannot do.

- [ ] **Step 4: Verify every documentation example**

Write a throwaway script in your scratch area that extracts each fenced block from the new documentation, runs it, and asserts the stated output. Report the count checked and the result.

- [ ] **Step 5: Run the full suite and commit**

```bash
.venv/bin/python -m pytest -q
git add -A
git commit -m "docs: teach string indexing and ordering, and the immutability asymmetry"
```

**Do not push and do not open a pull request.** The controller does that after a final whole-branch review.

---

## Self-Review

**Spec coverage.** Every section of the design spec maps to a task:

| Spec | Task |
| --- | --- |
| §1 The surface | 2 (indexing, the walk), 1 (ordering) |
| §2 No syntax changes | Global Constraints — the plan forbids touching the six syntax modules |
| §2 What `s[i]` returns, and the regress | 2 (`test_a_character_is_a_one_character_string`, `test_the_regress_terminates_because_you_stop_asking`) |
| §2 Correction to the Stage 7 spec | Already recorded in the merged spec; Task 4 Step 3 carries it into the overview |
| §3 Immutability and the asymmetry | 3 (the explaining message), 4 (teaching it) |
| §4 Ordering, and the codepoint gotcha | 1 (`test_ordering_is_codepoint_order_not_alphabetical`), 4 (documenting it) |
| §4 The exact reworded message | 1 (`test_mixed_operands_report_the_pair_exactly`) |
| §5 What it touches | 1, 2, 3 — four changes, all in `interpreter.py` |
| §6 The hazard | 3, including the mandatory teeth-check |
| §7 Testing, items 1–8 | 3 (teeth-check), 2 (message parity), 1 (gotcha pinned, exact mixed message, `[1] < [2]`), 2 (compose), Global Constraints (no syntax), 1 (baseline) |
| §8 Out of scope | Task 4 Step 3 documents the exclusions |

**Placeholder scan.** No TBD, no "handle edge cases", no "similar to Task N". Every code step carries the actual code and every insertion point names real lines.

One place deliberately leaves judgement to the implementer, with the reason stated: Task 4 Step 2 leaves the tutorial's section placement to whoever reads the file, because "teaches well" is the requirement and the current structure is not visible from here.

**Every assertion in this plan was run against the real interpreter before the plan was committed.** That check caught one contradiction of exactly the kind Stage 7 shipped: a Task 3 test expected `"Neo"[0] = "X"` to produce the new immutability message, but it is rejected by the *parser* and never reaches the interpreter at all. Fixed in place rather than left for the implementer to discover. Confirmed by running: the operator column for `"a" < 1` is 11; `xs[0][0] = "X"` does reach `IndexAssign` with a string target; the list bounds message is `index 5 is past the end of a list of length 3`; and `"a" * 2`, `""[0]`, `true[0]` and `"Neo"["a"]` all produce the text the tests assert.

**Type consistency.** `_element(target, index, node)`, `_check_index(target: list | str, index, node)`, `is_list`, `is_str`, `is_int`, `type_name` — used identically in every task. The three exact message strings in Global Constraints are the same strings asserted in Tasks 1, 2 and 3.

**One thing this plan does that the last one did not.** The three changed or new error messages are named once, in Global Constraints, and every test asserts against that table. In Stage 7 a message and its test were specified in separate sections, contradicted each other, and a substring assertion that could not fail survived to the final review.
