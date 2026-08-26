# The `None` Pattern Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a function returns a value on one path and `None` on another, and its result is later used directly as a condition, replace the translator's two locally-correct-but-jointly-misleading refusals with one that explains the whole rewrite.

**Architecture:** A pure analysis pass over the module AST, run in `translate()` beside the `bound_names(tree)` pass that already exists there, returning the paired refusal and the two positions it stands in for. After the walk, `translate()` swaps those two refusals for the paired one — but only when both actually fired. The walker is never touched.

**Tech Stack:** Python 3.11+ stdlib (`ast`), pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-08-26-none-pattern-design.md`

## Global Constraints

- **This is a better refusal, not a translation.** The program is still refused. Never emit MatrixLang for this shape.
- **No language change.** No null, no truthiness, no option type. The glyph table is closed at 56 used, 0 free.
- **Detection may only fail to fire.** Pattern-matching here exists to EXPLAIN. Worst case is a vaguer message; it must never produce a wrong program.
- **Replace only when both fired.** If only one of the two suppressed positions produced a refusal, change nothing — the reader keeps every accurate message they had.
- **The predicate requires an explicit `return None`.** A bare `return` produces only one refusal today (no `None` constant node exists for `_constant` to refuse), so admitting it would detect a shape the safety property then forbids acting on.
- **Falling off the end of a function is out of scope.** Detecting it means proving no path returns.
- **The walker (`_Translator`) is not modified.** All new behaviour lives in module-level functions and the tail of `translate()`.
- **The full suite must be green at the end of every task.**

## File Structure

| File | Change | Task |
| --- | --- | --- |
| `src/matrixlang/pytrans/translate.py` | five module-level helpers beside `_refuse_function_in_loop` | 1 |
| `tests/test_pytrans_refuse.py` | detection tests (positive + six negatives) | 1 |
| `src/matrixlang/pytrans/translate.py` | `_collapse_none_pattern` + two lines in `translate()` | 2 |
| `tests/test_pytrans_refuse.py` | end-to-end output tests | 2 |

The helpers go in `translate.py` beside `_refuse_function_in_loop`, which is the existing precedent for a module-level analysis helper in this file. They are private (`_`-prefixed) and imported by nothing else.

---

### Task 1: The detection pass

**Files:**
- Modify: `src/matrixlang/pytrans/translate.py` — add five module-level functions immediately after `_refuse_function_in_loop`
- Test: `tests/test_pytrans_refuse.py` (APPEND)

**Interfaces:**
- Consumes: `ast` (stdlib), and `Refusal` from `matrixlang.pytrans.refuse` (already imported in this module).
- Produces: `_none_then_truth_test(tree: ast.Module) -> tuple[Refusal, frozenset[tuple[int, int]]] | None`. Task 2 calls exactly this and nothing else.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pytrans_refuse.py`. Note the import addition at the top of the file — add `import ast` and `from matrixlang.pytrans.translate import _none_then_truth_test` to the existing import block.

```python
FIND_BOOK = """def find_book(books, term):
    for book in books:
        if book["name"] == term:
            return book
    return None

result = find_book(library, user_input)
if result:
    print(result["name"])
"""


def _detect(source):
    return _none_then_truth_test(ast.parse(source))


def test_the_none_then_truth_test_shape_is_detected():
    found = _detect(FIND_BOOK)
    assert found is not None
    refusal, positions = found
    # Anchored at the `return None`, naming the condition's line.
    assert refusal.line == 5
    assert "find_book" in refusal.reason
    assert "line 8" in refusal.reason
    # The two positions it stands in for: the None constant and the If test,
    # exactly as _constant and condition() report them.
    assert positions == frozenset({(5, 11), (8, 3)})


def test_the_idiom_shows_both_ends_of_the_rewrite():
    refusal, _ = _detect(FIND_BOOK)
    # The function's contract has to change, and the value has to be
    # unwrapped afterwards. A reader who is told neither hits a fresh
    # error on the next run.
    assert "return []" in refusal.idiom
    assert "len(result) > 0" in refusal.idiom
    assert "result[0]" in refusal.idiom


def test_a_function_whose_every_path_returns_none_is_not_the_shape():
    assert _detect(
        "def f(x):\n"
        "    return None\n"
        "\n"
        "result = f(1)\n"
        "if result:\n"
        "    print(result)\n"
    ) is None


def test_a_function_whose_every_path_returns_a_value_is_not_the_shape():
    assert _detect(
        "def f(x):\n"
        "    return x\n"
        "\n"
        "result = f(1)\n"
        "if result:\n"
        "    print(result)\n"
    ) is None


def test_a_bare_return_is_not_the_shape():
    # Measured, not assumed: a bare `return` produces only ONE refusal
    # today, so admitting it here would detect a shape the safety property
    # in Task 2 then forbids acting on.
    assert _detect(
        "def f(x):\n"
        "    if x:\n"
        "        return x\n"
        "    return\n"
        "\n"
        "result = f(1)\n"
        "if result:\n"
        "    print(result)\n"
    ) is None


def test_a_rebound_name_is_not_the_shape():
    # Without this, the condition gets paired with the wrong function and
    # the refusal explains a shape the reader did not write.
    assert _detect(
        "def f(x):\n"
        "    if x:\n"
        "        return x\n"
        "    return None\n"
        "\n"
        "result = f(1)\n"
        "result = other()\n"
        "if result:\n"
        "    print(result)\n"
    ) is None


def test_a_test_that_is_not_a_bare_name_is_not_the_shape():
    assert _detect(
        "def f(x):\n"
        "    if x:\n"
        "        return x\n"
        "    return None\n"
        "\n"
        "result = f(1)\n"
        "if result.name:\n"
        "    print(result)\n"
    ) is None


def test_a_nested_defs_returns_do_not_count_as_the_outer_functions():
    # The inner def supplies the `return None`; the outer only ever returns
    # a value. Treating the inner's returns as the outer's would invent a
    # mixed shape that is not there.
    assert _detect(
        "def f(x):\n"
        "    def inner():\n"
        "        return None\n"
        "    return inner\n"
        "\n"
        "result = f(1)\n"
        "if result:\n"
        "    print(result)\n"
    ) is None
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `PYTHONPATH=src python3 -m pytest tests/test_pytrans_refuse.py -q -k none_then_truth or shape or idiom`

Expected: every one fails with `ImportError: cannot import name '_none_then_truth_test'`. That is the right failure — the function does not exist yet. If any test fails for a different reason, fix the test before writing implementation.

- [ ] **Step 3: Write the implementation**

Add immediately after `_refuse_function_in_loop` in `src/matrixlang/pytrans/translate.py`:

```python
def _returns_of(func: ast.FunctionDef) -> list[ast.Return]:
    """Every `return` belonging to THIS function.

    Not to a `def` or `lambda` nested inside it, whose returns are its
    own -- counting those would invent a mixed shape where the outer
    function has only one kind of return.
    """
    found: list[ast.Return] = []
    stack: list[ast.AST] = list(func.body)
    while stack:
        node = stack.pop()
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            continue
        if isinstance(node, ast.Return):
            found.append(node)
        stack.extend(ast.iter_child_nodes(node))
    return found


def _mixed_return_none(func: ast.FunctionDef) -> ast.Constant | None:
    """The `None` of an explicit `return None`, when this function also
    returns a value somewhere. None if it is not that shape.

    A bare `return` (`node.value is None`) is deliberately not counted:
    it produces no refusal of its own, so pairing on it would detect a
    shape that can never be acted on.
    """
    returns_value = False
    none_node: ast.Constant | None = None
    for node in _returns_of(func):
        if node.value is None:
            continue
        if isinstance(node.value, ast.Constant) and node.value.value is None:
            if none_node is None:
                none_node = node.value
        else:
            returns_value = True
    return none_node if returns_value else None


def _call_binding(
    stmt: ast.stmt, functions: dict[str, ast.FunctionDef]
) -> tuple[str, ast.FunctionDef] | None:
    """`name = f(...)` where `f` is a def in this module -> (name, def)."""
    if not isinstance(stmt, ast.Assign) or len(stmt.targets) != 1:
        return None
    target = stmt.targets[0]
    if not isinstance(target, ast.Name):
        return None
    call = stmt.value
    if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
        return None
    func = functions.get(call.func.id)
    return None if func is None else (target.id, func)


def _rebinds(stmt: ast.stmt, name: str) -> bool:
    """Does this statement bind `name` again?"""
    for node in ast.walk(stmt):
        if (
            isinstance(node, ast.Name)
            and isinstance(node.ctx, ast.Store)
            and node.id == name
        ):
            return True
        if (
            isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and node.name == name
        ):
            return True
    return False


def _bare_name_test_after(rest: list[ast.stmt], name: str) -> ast.Name | None:
    """The first `if <name>:` in `rest`, before anything rebinds `name`.

    The `if` is checked before the rebinding check on the same statement:
    a condition is evaluated before its own body runs.
    """
    for stmt in rest:
        if (
            isinstance(stmt, ast.If)
            and isinstance(stmt.test, ast.Name)
            and stmt.test.id == name
        ):
            return stmt.test
        if _rebinds(stmt, name):
            return None
    return None
```

- [ ] **Step 4: Write the pass itself and its message**

Append, still in `translate.py`:

```python
def _scope_bodies(tree: ast.Module) -> list[list[ast.stmt]]:
    """Every statement list that is a scope body: the module's, and each
    function's. The binding and its test must share one of these."""
    bodies = [tree.body]
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            bodies.append(node.body)
    return bodies


def _none_then_truth_test(
    tree: ast.Module,
) -> tuple[Refusal, frozenset[tuple[int, int]]] | None:
    """The `return None` + `if result:` shape, recognised to EXPLAIN it.

    Never to translate it. MatrixLang has neither null nor truthiness,
    both by design, and this shape stays refused -- what changes is that
    one message describes the whole rewrite instead of two describing
    half of it each.

    Returns the paired refusal and the two positions it stands in for,
    or None. The positions are the ones the existing raise sites report:
    `_constant` reports the `None` constant node, `condition` reports the
    `If` test node.
    """
    functions = {
        stmt.name: stmt for stmt in tree.body if isinstance(stmt, ast.FunctionDef)
    }
    if not functions:
        return None
    for body in _scope_bodies(tree):
        for index, stmt in enumerate(body):
            binding = _call_binding(stmt, functions)
            if binding is None:
                continue
            name, func = binding
            none_node = _mixed_return_none(func)
            if none_node is None:
                continue
            test = _bare_name_test_after(body[index + 1 :], name)
            if test is None:
                continue
            return (
                _none_pattern_refusal(func, name, none_node, test),
                frozenset(
                    {
                        (none_node.lineno, none_node.col_offset),
                        (test.lineno, test.col_offset),
                    }
                ),
            )
    return None


def _none_pattern_refusal(
    func: ast.FunctionDef, name: str, none_node: ast.Constant, test: ast.Name
) -> Refusal:
    """One message for both halves, anchored at the line that must change.

    Names both ends of the rewrite deliberately: the function's contract
    has to change for either half to make sense, and the value has to be
    unwrapped afterwards. A reader told only one hits a fresh error on
    the next run.
    """
    return Refusal(
        f"`{func.name}` returns None on one path and its result is used as "
        f"a condition on line {test.lineno}. MatrixLang has neither null "
        f"nor truthiness.",
        none_node.lineno,
        none_node.col_offset,
        'Return a list instead — empty for "not found", one element for '
        "found:\n"
        "\n"
        "    return [value]        instead of   return value\n"
        "    return []             instead of   return None\n"
        "\n"
        "then test its length, and read the value out of it:\n"
        "\n"
        f"    if len({name}) > 0:  instead of   if {name}:\n"
        f"        {name}[0]                     {name}",
    )
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `PYTHONPATH=src python3 -m pytest tests/test_pytrans_refuse.py -q`
Expected: PASS, including every pre-existing test in the file unchanged.

- [ ] **Step 6: Run the full suite**

Run: `PYTHONPATH=src python3 -m pytest -q`
Expected: PASS. Nothing calls the new functions yet, so the count rises only by the eight tests added.

- [ ] **Step 7: Commit**

```bash
git add src/matrixlang/pytrans/translate.py tests/test_pytrans_refuse.py
git commit -m "feat(pytrans): recognise the return-None-then-truth-test shape"
```

---

### Task 2: Swap the two refusals for the paired one

**Files:**
- Modify: `src/matrixlang/pytrans/translate.py` — add `_collapse_none_pattern`, and two lines in `translate()`
- Test: `tests/test_pytrans_refuse.py` (APPEND)

**Interfaces:**
- Consumes: `_none_then_truth_test(tree)` from Task 1, returning `tuple[Refusal, frozenset[tuple[int, int]]] | None`.
- Produces: nothing further tasks depend on. This is the last task.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pytrans_refuse.py`:

```python
def test_the_none_pattern_is_one_refusal_not_two():
    result = translate(FIND_BOOK)
    assert isinstance(result, Refusals)
    assert len(result.items) == 1
    only = result.items[0]
    assert only.line == 5
    assert "find_book" in only.reason
    assert "line 8" in only.reason


def test_the_paired_refusal_replaces_the_misleading_len_advice():
    # Today's truthiness idiom suggests `len(result) > 0` -- on a dict,
    # that tests how many keys it has. A reader following it gets a
    # program that runs and answers a different question, which is what
    # the truthiness refusal exists to prevent.
    result = translate(FIND_BOOK)
    (only,) = result.items
    assert "a list or string" not in (only.idiom or "")
    assert "return []" in only.idiom


def test_a_program_without_the_shape_still_gets_both_refusals():
    # The regression net: everything that does not match must behave
    # exactly as it did before.
    result = translate(
        "def f(x):\n"
        "    if x:\n"
        "        return x\n"
        "    return None\n"
        "\n"
        "print(f(1))\n"
        "if other:\n"
        "    print(1)\n"
    )
    assert isinstance(result, Refusals)
    reasons = " ".join(item.reason for item in result.items)
    assert "None cannot be translated" in reasons
    assert "truthiness" in reasons


def test_nothing_is_replaced_when_only_one_of_the_two_fired():
    # The safety property, tested directly. `import os` refuses the whole
    # statement first, so the truthiness position never produces a
    # refusal -- and the None refusal must survive untouched rather than
    # being swapped for a claim about a shape the reader never reached.
    source = (
        "def find(xs, t):\n"
        "    for x in xs:\n"
        "        if x == t:\n"
        "            return x\n"
        "    return None\n"
        "\n"
        "result = find(a, b)\n"
        "import os\n"
        "if result:\n"
        "    print(result)\n"
    )
    result = translate(source)
    assert isinstance(result, Refusals)
    reasons = " ".join(item.reason for item in result.items)
    assert "None cannot be translated" in reasons
```

- [ ] **Step 2: Run them to make sure they fail**

Run: `PYTHONPATH=src python3 -m pytest tests/test_pytrans_refuse.py -q -k none_pattern or misleading or without_the_shape or only_one`

Expected: the first two fail with `assert 2 == 1` — the two refusals are still both present, which is exactly the behaviour being changed. The last two should already pass: they assert behaviour that must not change. If either of those fails now, stop and re-read the test before touching implementation.

- [ ] **Step 3: Write the collapse**

Add immediately after `_none_pattern_refusal` in `translate.py`:

```python
def _collapse_none_pattern(
    refusals: list[Refusal],
    paired: tuple[Refusal, frozenset[tuple[int, int]]] | None,
) -> list[Refusal]:
    """Swap the two component refusals for the paired one.

    Only when BOTH actually fired. If one did not -- because translation
    refused something earlier in the program and never reached it -- the
    reader keeps every accurate message they had, rather than trading one
    away for a claim about a shape they never got to.
    """
    if paired is None:
        return refusals
    refusal, positions = paired
    matched = [r for r in refusals if (r.line, r.column) in positions]
    if len(matched) != len(positions):
        return refusals
    kept = [r for r in refusals if (r.line, r.column) not in positions]
    return kept + [refusal]
```

- [ ] **Step 4: Wire it into `translate()`**

In `translate()`, immediately after `tree = ast.parse(source)` succeeds and before `walker = _Translator(...)`, add:

```python
    paired = _none_then_truth_test(tree)
```

Then change the refusal return from:

```python
    if walker.refusals:
        return Refusals(sorted(walker.refusals, key=lambda r: (r.line, r.column)))
```

to:

```python
    if walker.refusals:
        collapsed = _collapse_none_pattern(walker.refusals, paired)
        return Refusals(sorted(collapsed, key=lambda r: (r.line, r.column)))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `PYTHONPATH=src python3 -m pytest tests/test_pytrans_refuse.py -q`
Expected: PASS, every pre-existing test included.

- [ ] **Step 6: Run the full suite**

Run: `PYTHONPATH=src python3 -m pytest -q`
Expected: PASS. Pay attention to `tests/test_pytrans_differential.py` and any test asserting a refusal count — if one changed, decide whether the program matches the shape (correct) or whether detection is too broad (a defect).

- [ ] **Step 7: Update the register**

`docs/PYTHON-PARITY.md` item 5 is marked `*next*`. Mark it done in the format items 1-4 use, and say what shipped: a refusal that explains the rewrite, not a language change. Read a sibling item first and match it rather than inventing a format.

- [ ] **Step 8: Run the full suite once more, then commit**

```bash
PYTHONPATH=src python3 -m pytest -q
git add src/matrixlang/pytrans/translate.py tests/test_pytrans_refuse.py docs/PYTHON-PARITY.md
git commit -m "feat(pytrans): one refusal for the None pattern, naming the whole rewrite"
```

---

## Self-Review

**Spec coverage.** The pass and its plug-in point: Task 1 Steps 3-4, Task 2 Step 4. The four-part predicate: Task 1 Step 3 (`_call_binding`, `_mixed_return_none`, `_bare_name_test_after`) and Step 4 (`_scope_bodies` for requirement 4's shared scope). Both deliberate exclusions: `_mixed_return_none`'s bare-return skip, and fall-off-the-end never being examined. The message: Task 1 Step 4. The safety property: Task 2 Step 3. Every negative case in the spec's testing section maps to a test in Task 1 Step 1, plus the bare-return case the spec added. The register: Task 2 Step 7.

**One spec item deliberately not implemented as written.** The spec says the positions are "line 5, column 11" and "line 8, column 3" for the example. Those are illustrative, and the code reads them off the nodes rather than hard-coding them — the test asserts them, which is where the literal values belong.

**Type consistency.** `_none_then_truth_test` returns `tuple[Refusal, frozenset[tuple[int, int]]] | None` in Task 1 and is consumed with exactly that shape in Task 2's `_collapse_none_pattern`. `_mixed_return_none` returns `ast.Constant | None`, consumed as the `none_node` argument to `_none_pattern_refusal`. `_bare_name_test_after` returns `ast.Name | None`, consumed as `test`.

**Placeholder scan.** No TBD, no "add error handling", every code step carries the code.
