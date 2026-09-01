# `oracle` Over Lists and Strings Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Widen `oracle` so it asks a list and a string the same question it already asks a dictionary, closing the register's one case that translates cleanly and then dies on Run.

**Architecture:** One `if` branch in the interpreter, rewritten to dispatch on the left operand's type. Nothing else in the language moves — `oracle` is already a `Binary` node at a settled precedence rung, so the lexer, parser, renderer, tree view and `treegen` are all untouched. The translator's own code is untouched too; its existing `ast.In` mapping simply stops being wrong.

**Tech Stack:** Python 3.11+, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-24-list-membership-design.md`
**Issue:** #134
**Register:** `docs/PYTHON-PARITY.md`, item 3
**Branch:** `list-membership`, off `origin/main` at b109620

## Environment

This worktree has **no `.venv` of its own** — the virtualenv lives in the main checkout. Every command uses the interpreter already on PATH:

```bash
PYTHONPATH=src python3 -m pytest -q
```

Baseline: **1940 passed.** If yours differs before you change anything, stop and say so.

## Global Constraints

- **`oracle` takes a dictionary, a list, or a string on the left.** Anything else is a positioned `RuntimeErrorML` naming all three.
- **Dictionary behaviour is unchanged.** `check_key` still gates the right operand; every existing dictionary test must pass untouched.
- **A list SKIPS what it cannot compare.** `["a"] oracle 1` is `false`, never an error. This is the one place in the language where a type mismatch declines to raise where `==` would, and it is deliberate — `oracle` asks whether a list *contains* something, which has a truthful answer even when `==` on that pair does not.
- **The skip must be order-independent.** `["a", 1] oracle 1` and `[1, "a"] oracle 1` must both be `true`. Order-dependence is precisely the alternative the spec rejected.
- **A string on the left is a SUBSTRING test.** `"matrix" oracle "rix"` is `true`. The right operand must be a string; anything else is a positioned error.
- **`oracle` costs zero glyph slots.** No new keywords, no new AST node types. If you find yourself editing `tokens.py`, `glyphs.py`, `nodes.py`, `parser.py`, `render.py`, `treeview.py` or `tests/treegen.py`, you are off-plan — stop and report.
- **Nothing but `MatrixLangError` may escape the interpreter.** `site/glue.py`'s `run()` promises never to raise, and that promise has been broken **six** times in this project's history — once during the immediately preceding branch.
- **`not in` stays refused.** This change does not add a negated form; only its idiom's wording widens.
- **The full suite must be green at the end of every task.**

## The divergence you must NOT try to fix

`True in [1]` is **`True` in Python** and will be **`false` here.**

Python equates `True` and `1`. MatrixLang deliberately does not — `values._equal` raises `Incomparable` for a boolean against an integer, and its docstring explains at length why (`{true: "a", 1: "b"}` would otherwise collapse into one entry). `oracle` inherits that: the pair is incomparable, so it is skipped, so the answer is `false`.

This is pre-existing and intentional. **Do not write a differential test containing a boolean searched against a list of numbers, or a number searched against a list of booleans** — it will fail, and the correct response would be to delete the test, not to change the interpreter. Every differential case in Task 2 avoids that shape on purpose.

## An existing test asserts the OLD behaviour and must be rewritten

`tests/test_pytrans_expr.py:150` — `test_in_translates_unconditionally_and_a_list_fails_loudly` — currently asserts that `oracle` over a list raises "takes a dictionary". That is the exact failure this change removes.

**Do not delete it.** Half of what it says is still true and still valuable: `in` translates unconditionally because `k in d` and `2 in xs` are the same syntax and deciding between them would be the type inference the governing rule forbids. Task 2 rewrites the second half to assert the program now *runs and prints the right answer*, keeping that reasoning intact.

---

## File Structure

| File | Change | Task |
| --- | --- | --- |
| `src/matrixlang/interpreter.py` | the `ORACLE` branch in `_binary` | 1 |
| `tests/test_membership_run.py` | **new** — every container, every refusal, both decisions | 1 |
| `tests/test_dicts_run.py` | untouched — its passing unchanged is the regression check | 1 |
| `src/matrixlang/pytrans/translate.py` | the `NotIn` idiom's wording only | 2 |
| `tests/test_pytrans_expr.py` | rewrite the obsolete test | 2 |
| `tests/test_pytrans_differential.py` | the four risk cases | 2 |
| `README.md`, `docs/LEARNING-MATRIXLANG.md`, `docs/PYTHON-PARITY.md`, `src/matrixlang/operator/prompt.py` | what `oracle` means now | 3 |

---

### Task 1: The interpreter

**Files:**
- Modify: `src/matrixlang/interpreter.py` — the `TokenType.ORACLE` branch in `_binary`, currently at 824-840
- Test: `tests/test_membership_run.py` (**check whether it exists before writing it** — see the trap note below)

**Interfaces:**
- Consumes: `equal`, `Incomparable`, `is_dict`, `is_list`, `is_str`, `check_key`, `BadKey`, `type_name` — **all eight are already imported** at `interpreter.py:48-65`. You need to add nothing to that import.
- Produces: the widened `oracle` semantics that Tasks 2 and 3 document and test through the translator.

**A trap this repo has hit:** where this plan says to create a test file, check whether it already exists first. On a recent branch an implementer followed that instruction literally for a file that existed and destroyed 29 pre-existing tests before a test-count mismatch caught it. If the file exists, APPEND and say so in your report.

- [ ] **Step 1: Write the failing test**

Create `tests/test_membership_run.py`:

```python
"""`oracle` over a dictionary, a list and a string."""

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


# --- the dictionary, which must not have changed ----------------------


def test_a_present_key_is_still_true():
    assert run('trace {"a": 1} oracle "a"\n') == "true\n"


def test_an_absent_key_is_still_false():
    assert run('trace {"a": 1} oracle "b"\n') == "false\n"


def test_a_bad_key_is_still_an_error():
    error = fails('trace {"a": 1} oracle ["x"]\n')
    assert "a dictionary key must be a string or a number" in error.message


def test_an_empty_dictionary_has_no_keys():
    assert run('trace {} oracle "a"\n') == "false\n"


# --- the list ----------------------------------------------------------


def test_a_present_element_is_true():
    assert run('trace ["a", "b"] oracle "a"\n') == "true\n"


def test_an_absent_element_is_false():
    assert run('trace ["a", "b"] oracle "c"\n') == "false\n"


def test_an_empty_list_contains_nothing():
    assert run("trace [] oracle 1\n") == "false\n"


def test_numbers_work_too():
    assert run("trace [1, 2, 3] oracle 2\n") == "true\n"


def test_a_nested_list_compares_by_value():
    # `equal` recurses, so a list element that is itself a list is found
    # by what it holds rather than by identity.
    assert run("trace [[1], [2]] oracle [1]\n") == "true\n"


def test_an_incomparable_element_is_skipped_not_raised():
    # THE decision. `["a"] oracle 1` asks "does this list contain the
    # integer 1?", which has a truthful answer -- no, it holds a string.
    # `1 == "a"` genuinely has no answer and raises; membership is a
    # different question. This is the one place in the language where a
    # type mismatch declines to raise where `==` would.
    assert run('trace ["a"] oracle 1\n') == "false\n"


@pytest.mark.parametrize(
    "literal", ['["a", 1]', '[1, "a"]']
)
def test_the_skip_is_order_independent(literal):
    # The alternative -- raise on the first incomparable element -- would
    # make `["a", 1] oracle 1` an error and `[1, "a"] oracle 1` true: the
    # same list, reordered, deciding whether the program runs. That is
    # why the skip was chosen, so both orders are pinned.
    assert run(f"trace {literal} oracle 1\n") == "true\n"


def test_a_mixed_list_still_answers_for_the_other_type():
    assert run('trace [1, "a"] oracle "a"\n') == "true\n"


# --- the string --------------------------------------------------------


def test_a_substring_is_found():
    assert run('trace "matrix" oracle "rix"\n') == "true\n"


def test_a_single_character_is_found():
    assert run('trace "matrix" oracle "m"\n') == "true\n"


def test_an_absent_substring_is_false():
    assert run('trace "matrix" oracle "zion"\n') == "false\n"


def test_every_string_contains_the_empty_string():
    # CPython: `"" in "abc"` is True. Verified, not assumed. Note this is
    # NOT inconsistent with `cleave ""` being an error -- CPython itself
    # raises for `"abc".split("")` and returns True here, and each
    # operator follows the language it is matched against.
    assert run('trace "matrix" oracle ""\n') == "true\n"


def test_a_non_string_against_a_string_is_an_error():
    # CPython raises TypeError for `1 in "abc"`. Here it is a positioned
    # MatrixLang error instead -- nothing but MatrixLangError may escape.
    error = fails('trace "matrix" oracle 1\n')
    assert "'oracle'" in error.message
    assert "string" in error.message


# --- everything else ---------------------------------------------------


@pytest.mark.parametrize(
    "left,name",
    [("1", "integer"), ("true", "boolean")],
)
def test_oracle_refuses_a_non_container(left, name):
    error = fails(f"trace {left} oracle 1\n")
    assert error.message == (
        f"'oracle' takes a dictionary, a list or a string, got {name}"
    )


def test_an_agent_is_not_a_container():
    source = "agent f()\n  jackout 1\nflatline\ntrace f oracle 1\n"
    error = fails(source)
    assert "got agent" in error.message


def test_the_error_carries_the_operators_position():
    error = fails("trace 1\ntrace 1 oracle 1\n")
    assert error.line == 2
```

- [ ] **Step 2: Run it to make sure it fails**

```bash
PYTHONPATH=src python3 -m pytest tests/test_membership_run.py -q
```

Expected: the dictionary tests pass; every list and string test fails with `'oracle' takes a dictionary, got list` or `got string`.

- [ ] **Step 3: Widen the branch**

In `src/matrixlang/interpreter.py`, replace the whole `TokenType.ORACLE` branch in `_binary` with:

```python
        if node.op is TokenType.ORACLE:
            # One question -- does this hold that? -- asked of the three
            # things that can hold anything. The dictionary arm is
            # unchanged; the other two are what issue #134 added.
            if is_dict(left):
                try:
                    check_key(right)
                except BadKey as bad:
                    raise RuntimeErrorML(
                        f"a dictionary key must be a string or a number, "
                        f"got {bad.name}",
                        node.line,
                        node.column,
                    ) from None
                return right in left
            if is_list(left):
                for element in left:
                    try:
                        if equal(element, right):
                            return True
                    except Incomparable:
                        # Skipped, not raised, and this is THE decision of
                        # the design. `["a"] oracle 1` asks whether the
                        # list contains the integer 1 -- which has a
                        # truthful answer, no -- while `1 == "a"` asks
                        # something with no answer at all, and rightly
                        # raises. Membership is not equality.
                        #
                        # This is the one place in the language where a
                        # type mismatch declines to raise where `==`
                        # would. The alternative, raising on the first
                        # incomparable element, would make the answer
                        # depend on element ORDER: `["a", 1] oracle 1`
                        # would error while `[1, "a"] oracle 1` would be
                        # true. Same list, reordered, deciding whether
                        # the program runs.
                        continue
                return False
            if is_str(left):
                if not is_str(right):
                    raise RuntimeErrorML(
                        f"'oracle' on a string looks for a string, got "
                        f"{type_name(right)}",
                        node.line,
                        node.column,
                    )
                # A SUBSTRING test, matching Python -- so
                # `"matrix" oracle "rix"` is true even though "rix" is not
                # one of its characters. Everywhere else in the language a
                # string is a sequence of characters (`length` counts
                # them, `[i]` reads one), and this operator is the
                # exception. It is bought deliberately: substring is what
                # `if "@" in email:` means, and the translator cannot tell
                # a string from a list to warn anyone if the two differed.
                return right in left
            raise RuntimeErrorML(
                f"'oracle' takes a dictionary, a list or a string, got "
                f"{type_name(left)}",
                node.line,
                node.column,
            )
```

Every name used here — `equal`, `Incomparable`, `is_dict`, `is_list`, `is_str`, `check_key`, `BadKey`, `type_name` — is already imported at the top of the file. Confirm rather than assume.

- [ ] **Step 4: Run the new test**

```bash
PYTHONPATH=src python3 -m pytest tests/test_membership_run.py -q
```

Expected: PASS.

If an expected VALUE disagrees, do not change the implementation to match the test. Check what CPython actually does and fix whichever is wrong:

```bash
python3 -c "print('rix' in 'matrix', '' in 'matrix', 1 in ['a'], [1] in [[1],[2]])"
```

- [ ] **Step 5: Run the dictionary suite as the regression check**

```bash
PYTHONPATH=src python3 -m pytest tests/test_dicts_run.py tests/test_dicts_parse.py tests/test_dicts_lex.py tests/test_dicts_render.py -q
```

Expected: PASS, with **no edits to those files**. Their passing unchanged is what proves widening did not alter the original meaning. If you needed to touch one, stop and report — that is a behaviour change the spec did not authorise.

- [ ] **Step 6: Run the whole suite**

```bash
PYTHONPATH=src python3 -m pytest -q
```

Expected: exactly ONE failure — `tests/test_pytrans_expr.py::test_in_translates_unconditionally_and_a_list_fails_loudly`, which asserts the old "takes a dictionary" error. That test is Task 2's job.

**If anything else is red, stop and report it.**

- [ ] **Step 7: Commit**

The one expected failure means the suite is not green yet, and that is why this task's commit lands with it outstanding. Note it in the commit body so the history explains itself.

```bash
git add src/matrixlang/interpreter.py tests/test_membership_run.py
git commit -m "feat: oracle asks a list and a string, not only a dictionary

tests/test_pytrans_expr.py::test_in_translates_unconditionally_and_a_list_fails_loudly
still asserts the old error and is rewritten in the next commit."
```

---

### Task 2: The translator's side

The translator's own mapping does not change — `_compare` already turns `ast.In` into `Binary(right, ORACLE, left)`. What changes is a test that pinned the old failure, an idiom that names only dictionaries, and proof that the mapping now produces programs that agree with Python.

**Files:**
- Modify: `tests/test_pytrans_expr.py:150-175` — rewrite the obsolete test
- Modify: `src/matrixlang/pytrans/translate.py` — the `NotIn` idiom string, around line 1334
- Modify: `tests/test_pytrans_differential.py` — append the risk cases

**Interfaces:**
- Consumes: the widened `oracle` from Task 1.

- [ ] **Step 1: Rewrite the obsolete test**

In `tests/test_pytrans_expr.py`, replace `test_in_translates_unconditionally_and_a_list_fails_loudly` with:

```python
def test_in_translates_unconditionally_over_every_container():
    # `k in d`, `2 in xs` and `"a" in s` are the same syntax, and only the
    # runtime value says which is which -- deciding would be the type
    # inference the governing rule forbids. So `in` always becomes
    # `oracle`, unconditionally.
    #
    # This test used to end by asserting that the list form then FAILED at
    # runtime, with "takes a dictionary". That was honest about a real
    # gap: the translation looked fine and died on Run, naming an operator
    # the reader never typed. Issue #134 closed it by widening `oracle`
    # rather than by teaching the translator to guess, so the second half
    # now asserts the program runs and prints the right answer.
    import io

    from matrixlang.interpreter import Interpreter
    from matrixlang.lexer import lex
    from matrixlang.parser import parse

    assert ml("xs = [1, 2]\nprint(2 in xs)\n") == (
        "construct xs = [1, 2]\ntrace xs oracle 2\n"
    )
    assert ml('print("a" in d)\n') == 'trace d oracle "a"\n'
    assert ml('s = "abc"\nprint("b" in s)\n') == (
        'construct s = "abc"\ntrace s oracle "b"\n'
    )

    out = io.StringIO()
    Interpreter(out=out).run(
        parse(lex("construct xs = [1, 2]\ntrace xs oracle 2\n"))
    )
    assert out.getvalue() == "true\n"
```

If any expected translation string differs from what the translator actually emits, fix the test to match the translator — this task changes no translation behaviour, so today's output is correct by definition.

- [ ] **Step 2: Run it**

```bash
PYTHONPATH=src python3 -m pytest tests/test_pytrans_expr.py -q
```

Expected: PASS.

- [ ] **Step 3: Widen the `not in` idiom**

In `src/matrixlang/pytrans/translate.py`, the `NotIn` entry in the idiom table reads:

```python
    "NotIn": "MatrixLang has no `not in`; write `unplug (d oracle key)`",
```

`oracle` now answers about three containers, so an idiom naming a dictionary is too narrow. Change it to:

```python
    "NotIn": "MatrixLang has no `not in`; write `unplug (xs oracle x)`",
```

Leave the `_DESCRIBE` entry for `"NotIn"` alone — it names the construct, which has not changed.

- [ ] **Step 4: Check the existing `not in` test still passes**

```bash
PYTHONPATH=src python3 -m pytest tests/test_pytrans_expr.py::test_not_in_is_still_refused -q
```

Expected: PASS. It asserts `"unplug" in refusal.idiom`, which the new wording still satisfies. If it asserted the literal old string it would now fail — check, and if so update it to match.

- [ ] **Step 5: Add the differential cases**

These are the tests that matter: they translate a Python program, run BOTH sides, and compare stdout. Append to `tests/test_pytrans_differential.py`, using its existing `agree()` helper:

```python
def test_in_over_a_list_agrees():
    agree(
        'names = ["neo", "trinity", "morpheus"]\n'
        'for name in names:\n'
        '    print(name in names)\n'
        'print("smith" in names)\n'
    )


def test_in_over_a_string_agrees():
    # Substring, not character -- "rix" is not one of "matrix"'s
    # characters, and both sides must still say True.
    agree(
        's = "matrix"\n'
        'print("rix" in s)\n'
        'print("m" in s)\n'
        'print("zion" in s)\n'
        'print("" in s)\n'
    )


def test_in_over_a_mixed_list_agrees_in_both_orders():
    # The skip decision, and the reason it was chosen. Both orders must
    # give the same answers, and both must match Python.
    agree(
        'a = ["a", 1]\n'
        'b = [1, "a"]\n'
        'print(1 in a)\n'
        'print(1 in b)\n'
        'print("a" in a)\n'
        'print("a" in b)\n'
        'print(2 in a)\n'
    )


def test_in_over_a_dictionary_still_agrees():
    agree(
        'd = {"a": 1, "b": 2}\n'
        'print("a" in d)\n'
        'print("z" in d)\n'
    )


def test_a_membership_search_loop_agrees():
    # The shape the register was actually about: a search that stops
    # early, now that both `in` and `wake` exist.
    agree(
        'names = ["neo", "trinity"]\n'
        'wanted = "trinity"\n'
        'found = 0\n'
        'for name in names:\n'
        '    if wanted in name:\n'
        '        found = 1\n'
        '        break\n'
        'print(found)\n'
    )
```

**Do not add a case searching a boolean against a list of numbers, or the reverse.** `True in [1]` is `True` in Python and `false` here, because MatrixLang deliberately never equates booleans and integers. That divergence is pre-existing and intentional; a differential test would fail and the correct response would be to delete the test, not to change the interpreter.

- [ ] **Step 6: Run the differential tests**

```bash
PYTHONPATH=src python3 -m pytest tests/test_pytrans_differential.py -q
```

Expected: PASS. A failure means Python and MatrixLang printed different text — read the assertion's `python=` / `matrixlang=` values and fix whichever side is actually wrong. **Never weaken a case to make it pass.**

- [ ] **Step 7: Run the whole suite and the browser-half gates**

```bash
PYTHONPATH=src python3 -m pytest -q
```

```bash
python3 site/checks/no_semantics.py
```

```bash
python3 site/checks/key_handling.py
```

Expected: suite PASS with no failures at all now, both checks OK.

- [ ] **Step 8: Commit**

```bash
git add tests/test_pytrans_expr.py tests/test_pytrans_differential.py src/matrixlang/pytrans/translate.py
git commit -m "feat(pytrans): in over a list and a string now runs, not just translates"
```

---

### Task 3: Documentation and the register

`oracle` means something wider than it did, and four places describe it.

**Files:**
- Modify: `src/matrixlang/operator/prompt.py` — the `oracle` rule in `_RULES`
- Modify: `README.md`, `docs/LEARNING-MATRIXLANG.md`, `docs/PYTHON-PARITY.md`

- [ ] **Step 1: Sweep for descriptions of `oracle`**

```bash
grep -rn "oracle" --include='*' . | grep -v '.git/' | grep -v 'docs/superpowers/' | grep -v '^tests/'
```

Read every hit. `docs/superpowers/specs/` and `docs/superpowers/plans/` are historical records and must NOT be rewritten. Report what you found and what you decided about each, including hits you deliberately left alone.

**Sweep every extension, not just `*.py` and `*.md`.** On a recent branch a sweep restricted to those two shipped a false claim to the live landing page in `site/index.html`. Check whether `oracle` is described there.

- [ ] **Step 2: Update the Operator prompt**

In `src/matrixlang/operator/prompt.py`, the dictionary bullet currently says `oracle` checks a dictionary. Widen it — this is the text a model is given to write MatrixLang from, so a narrow description produces programs that use a workaround for something the language now does:

```
- `oracle` is infix and gives a boolean: it asks whether a container holds
  something. `d oracle "a"` asks a dictionary for a key, `xs oracle 3` asks
  a list whether it holds that element, and `s oracle "ab"` asks a string
  whether that text appears in it. An element a list cannot compare is
  simply not a match, so `["a"] oracle 1` is false rather than an error.
```

Place it beside the existing dictionary rule rather than replacing that rule's other content — `keymaker` and the reading-a-missing-key sentence stay.

- [ ] **Step 3: Update the README's vocabulary paragraph**

`README.md:56-57` currently reads:

```
for the keys in insertion order, and the infix `oracle` to ask whether a
key is there before reading it, since reading a missing one is an error
```

Replace those two lines with:

```
for the keys in insertion order, and the infix `oracle` to ask any
container whether it holds something — a dictionary for a key, a list for
an element, a string for text inside it
```

The "since reading a missing one is an error" clause goes: it explained why you would ask a dictionary before indexing it, which is still true but is now only one of three reasons to reach for `oracle`, and the sentence cannot carry all three.

- [ ] **Step 4: Widen the two narrow claims in the learning guide**

Two places describe `oracle` as dictionary-only, and one of them says so in as many words.

`docs/LEARNING-MATRIXLANG.md:740` — the section heading:

```
### `oracle` — is a key there?
```

becomes:

```
### `oracle` — is it in there?
```

`docs/LEARNING-MATRIXLANG.md:900-901` — in the translator section:

```
**`in` always becomes `oracle`.** MatrixLang's `oracle` asks a
*dictionary* for a key (§8), and nothing else:
```

becomes:

```
**`in` always becomes `oracle`.** MatrixLang's `oracle` asks any
container whether it holds something (§8) — which is why the translator
can map `in` onto it without knowing which container it has:
```

That passage's point was originally that the mapping was unconditional *and* narrow, which is what made it fail at runtime. The mapping is still unconditional; it is no longer narrow. Read the surrounding paragraphs and make sure the rewritten claim still fits what they go on to say — if they build on the old narrowness, they need adjusting too. Report what you found there.

- [ ] **Step 5: Add a teaching passage to the learning guide**

Extend the `oracle` section (the one whose heading you just widened) with:

````
`oracle` is not only for dictionaries. It asks any container the same
question — *do you hold this?*

```
trace ["neo", "trinity"] oracle "neo"
trace "matrix" oracle "rix"
trace {"a": 1} oracle "a"
```

```
true
true
true
```

A list is asked about its elements, a dictionary about its keys, and a
string about the text inside it — so `"matrix" oracle "rix"` is true even
though `"rix"` is not one of its characters.

One rule worth knowing: an element a list cannot compare is simply not a
match. `["a"] oracle 1` is `false`, not an error, even though `"a" == 1`
*is* an error. Asking whether a list contains the number 1 has a truthful
answer — it does not, it holds a string — while asking whether a string
equals a number does not.
````

- [ ] **Step 6: Run every example in the new passage**

The guide claims every example in it was executed before it shipped. Honour that:

```bash
printf 'trace ["neo", "trinity"] oracle "neo"\ntrace "matrix" oracle "rix"\ntrace {"a": 1} oracle "a"\n' > /tmp/ml-oracle-check.rain
```

```bash
PYTHONPATH=src python3 -m matrixlang run /tmp/ml-oracle-check.rain
```

Expected output, exactly:

```
true
true
true
```

Paste the real output into your report. If it differs, the documentation is wrong — fix the documentation and say so.

- [ ] **Step 7: Update the register**

In `docs/PYTHON-PARITY.md`:

- Item 3's heading gains `— **done**`, and its body becomes a record of what shipped: `oracle` now asks a dictionary for a key, a list for an element and a string for a substring; the skip decision and why it is order-independent; and that it cost no glyph slot.
- Item 4's heading gains `— *next*`.
- The glyph budget line and the allocation paragraph both say item 3 takes none — check they now read correctly with item 3 done rather than pending. **The budget numbers do not change**: still 54 used, 2 free.
- Check the `_DESCRIBE` count claim, which moved on the last branch:

```bash
PYTHONPATH=src python3 -c "from matrixlang.pytrans.translate import _DESCRIBE; print(len(_DESCRIBE))"
```

- [ ] **Step 8: Run the whole suite**

```bash
PYTHONPATH=src python3 -m pytest -q
```

Expected: PASS. `tests/test_operator_prompt.py` asserts every keyword is explained, and `tests/test_site_examples.py` and `tests/test_package.py` read repository files — a documentation edit really can turn a test red.

- [ ] **Step 9: Commit**

```bash
git add README.md docs/LEARNING-MATRIXLANG.md docs/PYTHON-PARITY.md src/matrixlang/operator/prompt.py
git commit -m "docs: oracle asks a dictionary, a list or a string"
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
git diff --stat origin/main -- src/matrixlang/tokens.py src/matrixlang/glyphs.py src/matrixlang/nodes.py src/matrixlang/parser.py src/matrixlang/render.py src/matrixlang/treeview.py tests/treegen.py
```

The last one must be **empty**. This change spends no glyph slot and adds no node type, so every one of those files should be untouched — that command is the proof rather than the claim.

## Self-review notes

Four places this change can be wrong while looking right:

1. **The skip's order-independence.** A loop that raises instead of continuing passes every single-type test and fails only on a mixed list in one particular order. `test_the_skip_is_order_independent` is parametrized over both orders for exactly that reason.
2. **The dictionary arm.** Widening restructured the branch around it. The regression check is that `tests/test_dicts_*.py` pass **with no edits** — if any needed changing, the original meaning moved.
3. **What escapes.** `equal` raises `Incomparable`, which the list arm catches. Satisfy yourself that nothing else it can raise gets out — a cyclic list is the case to think about, since `equal` handles cycles internally with a seen-set rather than by recursing to a `RecursionError`.
4. **The boolean divergence.** `True in [1]` differs between Python and MatrixLang, deliberately and pre-existingly. Any differential test that trips over it should be deleted, not fixed by changing the interpreter.
