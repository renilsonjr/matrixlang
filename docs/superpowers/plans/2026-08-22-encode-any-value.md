# `encode` Takes Any Value Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let `encode` turn any value into text, so a Python f-string interpolating a string translates and runs instead of dying at a MatrixLang line the reader never wrote.

**Architecture:** Delete a six-line type guard in the interpreter's `ENCODE` branch. `encode` already routes through `values.to_display`, which renders every type — so the happy path needs no new code. The one thing that must be *added* is a `CyclicValue` catch, because widening makes a self-containing value reachable for the first time.

**Tech Stack:** Python 3.11+ stdlib, pytest. No new dependencies.

## Global Constraints

- **No new keyword, token, or AST node.** The glyph budget stays at **7 free of 49 slots** — `tests/test_glyphs.py` tracks it by hand and must not change.
- **`encode` must error on exactly two things afterwards:** a value containing a cycle, and an integer past CPython's digit ceiling.
- **`Interpreter.run()` must not raise a raw Python exception.** `site/glue.py` carries anything that escapes into the browser as an unhandled Pyodide traceback. **This promise has been broken five times in this project**, four by something nobody predicted.
- **Nested quoting is unchanged** — a string at the top level prints bare, a string inside a list or dictionary prints quoted. That is `to_display`'s existing rule and the one `trace` follows.
- **The translator is not modified.** `pytrans` already emits `encode` for `str()` and f-string interpolations.
- Run tests from the repo root: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest -q`. Use `python3`, not `python`.
- Conventional-commit subjects. This branch has no tracking issue of its own; do not invent one.

## File Structure

| Path | Change |
| --- | --- |
| `src/matrixlang/interpreter.py:484-505` | Delete the `is_int` guard; add a `CyclicValue` catch |
| `tests/test_interpreter.py:574-598` | Three refusal tests invert to acceptance tests |
| `tests/test_encode_any.py` | **New.** The widened behaviour and the two surviving errors |
| `tests/test_site_glue.py` | One never-raises test for a cyclic encode |
| `tests/test_pytrans_differential.py` | One case: an f-string interpolating a string |
| `docs/LEARNING-MATRIXLANG.md` §19 | "reverses `decode`" and "turns a number into text" are now false |
| `src/matrixlang/operator/prompt.py:93` | Says `encode` "converts a number to text" |

### Where the tests go

`tests/test_encode_any.py` is new and follows the house convention — a local
`run`/`fails` pair copied from `tests/test_dicts_run.py:1-22`, which
`test_lists_run.py`, `test_logic_run.py` and `test_strings_run.py` all share:

```python
"""encode takes any value -- the widened operator, and what still refuses."""

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
```

`run` returns the **raw captured string including trailing newlines**, not a
list of lines. Every assertion below is written against that.

---

### Task 1: Widen `encode`, and catch the cycle it exposes

**Files:**
- Modify: `src/matrixlang/interpreter.py:484-505`
- Modify: `tests/test_interpreter.py:574-598`
- Create: `tests/test_encode_any.py`

**Interfaces:**
- Consumes: `values.to_display`, `values.CyclicValue`, `values.TooManyDigits` — all already imported in `interpreter.py`.
- Produces: no new names. `encode`'s behaviour changes; its signature does not.

**Why the cycle catch is the point of this task.** Today `encode` cannot receive
a value that contains itself, because the type guard admits only integers.
Delete the guard and `encode xs` where `xs` holds `xs` reaches `to_display`,
which raises `CyclicValue`. Uncaught, that escapes `Interpreter.run()` as a raw
Python exception and reaches the browser as an unhandled traceback.

`Trace` already carries exactly this catch at `interpreter.py:245-260`. Copy its
shape **and its message**: `"cannot display a value that contains a cycle"` —
"a value", not "a list", because a dictionary can hold itself too and naming a
list would be false. That message reaches the browser verbatim in the SSE error
payload.

- [ ] **Step 1: Write the failing acceptance tests**

Create `tests/test_encode_any.py` with the header and helpers from the File
Structure section above, then:

```python
def test_encode_still_renders_a_number():
    assert run("trace encode 2\n") == "2\n"


def test_encode_renders_a_string_unchanged():
    # The case that motivated this: an f-string interpolating a name.
    assert run('trace encode "hi"\n') == "hi\n"


def test_encode_renders_a_boolean_in_the_languages_own_spelling():
    # The deleted guard's comment feared this would give "1". It cannot:
    # values._display checks is_bool before anything else.
    assert run("trace encode true\n") == "true\n"
    assert run("trace encode false\n") == "false\n"


def test_encode_renders_a_list():
    assert run("trace encode [1, 2]\n") == "[1, 2]\n"


def test_encode_renders_a_dictionary():
    assert run('trace encode {"a": 1}\n') == '{"a": 1}\n'


def test_a_string_inside_a_list_keeps_its_quotes():
    # to_display's existing nesting rule, unchanged: bare at the top level,
    # quoted inside a container, so a reader can tell a string from a name.
    assert run('trace encode ["a"]\n') == '["a"]\n'


def test_encode_composes_with_string_concatenation():
    # What the translator emits for f"Name: {name}, ID: {id}".
    source = 'construct name = "clean code"\nconstruct id = 1\n' \
             'trace "Name: " + encode name + ", ID: " + encode id\n'
    assert run(source) == "Name: clean code, ID: 1\n"


def test_encode_refuses_a_value_that_contains_itself():
    # Newly reachable: the type guard used to make this impossible.
    # Uncaught it would escape as a raw Python exception, which
    # site/glue.py carries into the browser as an unhandled traceback.
    error = fails('construct xs = [1]\nxs[0] = xs\ntrace encode xs\n')
    assert "cannot display a value that contains a cycle" in error.message


def test_encode_refuses_a_dictionary_that_contains_itself():
    # "a value", not "a list" -- a dictionary can hold itself too.
    error = fails('construct d = {"a": 1}\nd["a"] = d\ntrace encode d\n')
    assert "cannot display a value that contains a cycle" in error.message


def test_encode_still_refuses_a_number_past_the_digit_ceiling():
    # The one guard that survives, unchanged.
    source = "construct n = 10\nconstruct i = 0\ndejavu i < 14\n" \
             "  n = n * n\n  i = i + 1\nflatline\ntrace encode n\n"
    assert "digits" in fails(source).message
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_encode_any.py -q`
Expected: the string, boolean, list, dictionary, nesting, concatenation and
both cycle tests FAIL with `'encode' takes a number, got …`. The number test
and the digit-ceiling test PASS already.

- [ ] **Step 3: Delete the guard and add the cycle catch**

In `src/matrixlang/interpreter.py`, the `ENCODE` branch currently reads:

```python
            if expr.op is TokenType.ENCODE:
                # Numbers only, and is_int is deliberately narrow: in Python
                # a bool IS an int, so `is_int` (which checks type exactly)
                # is what keeps `encode true` an error rather than "1".
                if not is_int(operand):
                    raise RuntimeErrorML(
                        f"'encode' takes a number, got {type_name(operand)}",
                        expr.line,
                        expr.column,
                    )
```

Replace that whole block — comment and all — with a comment explaining why
there is no longer a type check:

```python
            if expr.op is TokenType.ENCODE:
                # Any value, deliberately. This was numbers-only, guarded by
                # is_int, until a reader's f-string interpolating a string
                # translated cleanly and died on Run naming an operator they
                # never typed. `trace` prints every type through to_display;
                # there was no reason `encode` could not hand back the same
                # text. The old guard's own comment feared `encode true`
                # giving "1" -- to_display gives "true", because _display
                # checks is_bool first, so it was guarding against something
                # values.py already prevented.
```

Keep the existing `to_display` comment and call. Extend its `try` with a
`CyclicValue` arm **before** the `TooManyDigits` one:

```python
                try:
                    return to_display(operand)
                except CyclicValue:
                    # Newly reachable: the type guard above used to make a
                    # self-containing value impossible here. Same wording as
                    # `trace`'s -- "a value", not "a list", because a
                    # dictionary can hold itself too and the message reaches
                    # the browser verbatim in the SSE error payload.
                    raise RuntimeErrorML(
                        "cannot display a value that contains a cycle",
                        expr.line,
                        expr.column,
                    ) from None
                except TooManyDigits as size:
                    ...
```

Leave the `TooManyDigits` arm and its comment exactly as they are.

`CyclicValue` is already imported at `interpreter.py:49`. **Leave the imports
alone:** `is_int` has 7 uses in this file and `type_name` has 21, so neither
goes unused when this branch stops calling them. Verified.

- [ ] **Step 4: Run the new tests**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_encode_any.py -q`
Expected: all PASS.

- [ ] **Step 5: Invert the three obsolete refusal tests**

`tests/test_interpreter.py` has three tests asserting the old error:
`test_encode_rejects_a_string` (~line 574), `test_encode_rejects_a_boolean`
(~584) and `test_encode_rejects_a_list` (~593).

They now assert behaviour that no longer exists. **Rewrite them as acceptance
tests rather than deleting them**, so the file keeps a record that this
changed:

**`_run` in that file returns a `list[str]` of output lines**
(`tests/test_interpreter.py:502`), *not* the raw string the newer `run` helpers
return. Verified — the assertions below are written against the list:

```python
def test_encode_accepts_a_string():
    # Was test_encode_rejects_a_string. `encode` took numbers only until a
    # translated f-string interpolating a string died on Run; `trace` had
    # always printed every type, and `encode` now hands back the same text.
    assert _run('trace encode "already text"\n') == ["already text"]


def test_encode_accepts_a_boolean():
    # Was test_encode_rejects_a_boolean. The language's own spelling, not
    # Python's: values._display checks is_bool before is_int.
    assert _run("trace encode true\n") == ["true"]


def test_encode_accepts_a_list():
    # Was test_encode_rejects_a_list.
    assert _run("trace encode [1, 2]\n") == ["[1, 2]"]
```

The `from matrixlang.errors import MatrixLangError` import inside each of the
three old tests becomes unused — remove it with them.

- [ ] **Step 6: Run the full suite**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest -q`
Expected: PASS. If anything else fails, it is a place that relied on `encode`
being narrow — report what and where rather than fixing files this task does not
list.

- [ ] **Step 7: Confirm the glyph budget did not move**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_glyphs.py -q`
Expected: PASS, unmodified. This change adds no keyword and no token; if that
file needs touching, something is wrong.

- [ ] **Step 8: Commit**

```bash
git add src/matrixlang/interpreter.py tests/test_encode_any.py tests/test_interpreter.py
git commit -m "feat: encode takes any value, not only a number"
```

---

### Task 2: Prove the browser cannot see a raw exception

**Files:**
- Modify: `tests/test_site_glue.py`

**Interfaces:**
- Consumes: Task 1's widened `encode`.
- Produces: nothing other tasks import.

**Why this is its own task.** `glue.run()` documents that it **never raises**,
because it executes under Pyodide where an escaped exception is an unhandled
browser traceback with no console the reader is looking at. Task 1 makes a new
exception type reachable inside `encode`. A test that only checks the
interpreter's own error does not prove the browser is safe — `glue.run` has its
own `try` and its own promise, and that is the layer this task pins.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_site_glue.py`, following the file's existing style:

```python
def test_encoding_a_cyclic_value_returns_an_error_event_rather_than_raising():
    # `encode` accepts any value now, which makes a self-containing one
    # reachable inside it for the first time. run() promises never to
    # raise; that promise has been broken five times here, so a new
    # reachable exception type gets its own guard at this layer too.
    events = glue.run('construct xs = [1]\nxs[0] = xs\ntrace encode xs\n')
    assert events[-1]["kind"] == "error"
    assert "contains a cycle" in events[-1]["message"]
```

- [ ] **Step 2: Run it**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_site_glue.py -q -k cyclic`
Expected: PASS, because Task 1's catch converts `CyclicValue` into a
`MatrixLangError` that `glue.run` already handles.

**If it FAILS by raising**, Task 1's catch is missing or misplaced — fix that
rather than adding a second catch in `glue.py`. The interpreter is where the
position is known.

- [ ] **Step 3: Verify by mutation**

A passing test proves nothing unless it would fail without the fix. Temporarily
remove the `CyclicValue` arm you added in Task 1, re-run this test, and confirm
it fails with a raw `CyclicValue` escaping. Restore the arm and confirm
`git diff src/matrixlang/interpreter.py` prints nothing.

Put the observed failure in your report.

- [ ] **Step 4: Commit**

```bash
git add tests/test_site_glue.py
git commit -m "test: pin that a cyclic encode reaches the browser as an event"
```

---

### Task 3: The differential case that motivated this

**Files:**
- Modify: `tests/test_pytrans_differential.py`

**Interfaces:**
- Consumes: Task 1's widened `encode`.

**Why this is the test that matters.** Every other test here proves `encode`
returns *something*. This one runs the reader's Python, runs its translation,
and compares the output — the only shape that proves they mean the same thing.
Before this change it could not have existed: the translation died on Run.

The file's `agree()` harness already does the comparison; read its docstring
before adding, because it documents two deliberate accommodations (the
`input()` prompt newline, and Python's `True` versus MatrixLang's `true`).

- [ ] **Step 1: Write the test**

Append to `tests/test_pytrans_differential.py`:

```python
def test_an_fstring_interpolating_a_string_agrees():
    # The case that prompted widening `encode`. The translator emits
    # `encode` for every interpolation; while that took numbers only, this
    # program translated cleanly and then died on Run.
    agree(
        'name = "clean code"\n'
        'book_id = 1\n'
        'print(f"Match found! Name: {name}, ID: {book_id}")\n'
    )


def test_an_fstring_interpolating_a_dictionary_field_agrees():
    agree(
        'book = {"id": 2, "name": "refactoring"}\n'
        'print(f"Name: {book[\'name\']}, ID: {book[\'id\']}")\n'
    )
```

- [ ] **Step 2: Run them**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_pytrans_differential.py -q`
Expected: PASS.

**A failure here is a real defect, not a test problem.** Read the reported
`python=… matrixlang=…` and find the cause. Do not adjust an expected value to
make it pass.

- [ ] **Step 3: Run the books program end to end**

The program that prompted all of this. Write it to a scratch file and translate
it, then run the result through the interpreter with `matrixlang.input.ListSource`
supplying `"refactoring"`:

```python
library_books = [
    {"id": 1, "name": "clean code"},
    {"id": 2, "name": "refactoring"},
    {"id": 3, "name": "design patterns"},
    {"id": 4, "name": "the pragmatic programmer"}
    ]
user_input = input("Enter book name or id: ")

def find_book(books_data, search_term):
    found = []
    for book in books_data:
        if search_term == str(book["id"]) or search_term == book["name"]:
            found = found + [book]
    return found

result = find_book(library_books, user_input)
if len(result) > 0:
    print(f"Match found! Name: {result[0]['name']}, ID: {result[0]['id']}")
else:
    print("No book found matching that Name or ID.")
```

Expected output: `Match found! Name: refactoring, ID: 2`.

Note this uses an **f-string**, unlike the hand-rewritten version that was
needed before — that is the point of the change. Paste what you observed into
your report.

- [ ] **Step 4: Commit**

```bash
git add tests/test_pytrans_differential.py
git commit -m "test: an f-string interpolating a string agrees with Python"
```

---

### Task 4: The claims that are now false

**Files:**
- Modify: `docs/LEARNING-MATRIXLANG.md` §19
- Modify: `src/matrixlang/operator/prompt.py:93`

**Interfaces:**
- Consumes: Task 1's widened `encode`.

**Why this is not optional tidying.** `operator/prompt.py` is what a model reads
when it writes MatrixLang; a false claim there produces wrong programs. And
`tests/test_operator_prompt.py` asserts every keyword is genuinely *explained* in
`_RULES` — a guard that exists because an earlier version was satisfiable by
construction and stayed green while three keywords went unexplained.

- [ ] **Step 1: Fix the Operator prompt**

`src/matrixlang/operator/prompt.py:93` currently says `encode` "converts a
number to text". Reword it to say `encode` gives the text form of any value —
the same text `trace` would print — and that it is `decode`'s counterpart rather
than its exact mirror.

- [ ] **Step 2: Run the prompt guard**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_operator_prompt.py -q`
Expected: PASS.

- [ ] **Step 3: Fix the tutorial**

`docs/LEARNING-MATRIXLANG.md` §19 contains a subsection headed
**"`encode` reverses `decode`"** saying "`encode` turns a number into text — the
mirror of `decode`", and a worked example whose output block is:

```
matrixlang: [line 1, column 7] 'encode' takes a number, got string
```

That error no longer happens. Rewrite the subsection so it says what `encode`
does now: gives the text form of any value, the same text `trace` would print.
Keep `decode` described as narrow — there is no sensible number for `"hi"` — and
reword the "mirror" framing rather than deleting the relationship.

Replace the refusal example with one that shows the widened behaviour. **Run
whatever you write and paste the output you observed** — tutorial snippets are
prose, not tests, and rot silently; this has already bitten this project once.

The precedence paragraph that follows (`encode n + 1` means `(encode n) + 1`)
is still true and should stay.

- [ ] **Step 4: Sweep for other stale claims**

Grep the repository for `takes a number`, `encode` beside `mirror`, and
`number into text`. Report every hit you leave and why. Hits inside
`docs/superpowers/plans/` and `docs/superpowers/specs/` are historical records
of what each stage did and should be **left alone** — say so explicitly rather
than skipping them silently.

- [ ] **Step 5: Run everything**

```
PYTHONPATH="$PWD/src:$PWD" python3 -m pytest -q
node --test site/tests/*.test.mjs
python3 site/checks/no_semantics.py && python3 site/checks/key_handling.py
```

Expected: all green, `site/checks/` unmodified.

- [ ] **Step 6: Commit**

```bash
git add docs/LEARNING-MATRIXLANG.md src/matrixlang/operator/prompt.py
git commit -m "docs: encode gives the text form of any value"
```

---

## Self-review notes

**Spec coverage.** Guard deletion and the `CyclicValue` catch (T1); the two
surviving errors (T1); nested quoting unchanged (T1); the never-raises promise
at the glue layer (T2); the differential f-string case and the books program
(T3); the tutorial and Operator prompt (T4); the glyph budget confirmed
unmoved (T1 Step 7). Every row of the spec's testing table maps to a task.

**Out of scope, per the spec** and absent from every task: a separate
universal-text keyword, widening `decode`, and anything about truthiness or
`None`.

**Naming consistency.** `to_display`, `CyclicValue`, `TooManyDigits`,
`RuntimeErrorML` are used identically throughout and all already exist in
`interpreter.py`'s imports.

**Both facts the plan could have guessed at were checked instead.** `_run` in
`tests/test_interpreter.py:502` returns a `list[str]`, not the raw string the
newer `run` helpers return — the inverted assertions in T1 Step 5 are written
against the list, and would have been wrong the other way. `is_int` (7 uses)
and `type_name` (21) both stay in use after the guard goes, so T1 Step 3 says
leave the imports rather than inviting a judgement call. Confident-but-wrong
details of exactly this kind have cost this project fix rounds before.

**One thing this plan cannot settle in advance.** Task 1 Step 6 may surface a
test elsewhere that relied on `encode` being narrow. The instruction is to
report it rather than fix it, because where such a test lives determines
whether it is an obsolete assertion or a real dependency on the old contract.
