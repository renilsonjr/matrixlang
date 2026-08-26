# List Comprehensions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Translate `[f(x) for x in xs if c]` by rewriting it into the loop the translator already knows how to emit, before translation begins.

**Architecture:** A Python-AST source-to-source pass, `rewrite_comprehensions`, runs inside `translate()` between `ast.parse` and `_Translator`. It replaces each supported comprehension with a name and emits an accumulator loop immediately before the statement that contained it. `_Translator` is not modified and never learns what a comprehension is. Everything the pass declines to rewrite is left untouched, which means it keeps its existing refusal with no new code.

**Tech Stack:** Python 3.11+, stdlib `ast` only, pytest.

## Global Constraints

- No language change. No new keyword, no new type, no glyph. The table is closed at 56 used / 0 free.
- `src/matrixlang/pytrans/translate.py` is not modified except for the three-line wiring in Task 5.
- The pass is pure Python-in, Python-out. It must not import `nodes`, `render`, or anything from the interpreter.
- `translate()` must never raise. Nothing added here may change that.
- Invented names go through `free_name` from `pytrans.names` and are added to the shared `taken` set, so they collide neither with the reader's names nor with each other.
- Every generated node carries a position via `ast.copy_location` / `ast.fix_missing_locations`.
- Tests are pytest, under `tests/`, run with `pytest` from the repo root.

## Naming decision (deviation from the spec)

The spec illustrated the invented names as `_c0` and `_i0`. This plan uses
the stems **`out`** and **`item`** instead, resolved through the existing
`free_name`. Reason: the emitted MatrixLang is shown to the reader, and

```
construct out = []
dejavu n < length xs
  out = out + [xs[n] * 2]
```

reads as a program a person could have written, where `_c0` reads as
machine output. `free_name` supplies `out1`, `item1`, ... when the reader
already uses those names, so the collision guarantee the spec asked for is
unchanged. Both stems were checked against `tokens.KEYWORDS` and are not
MatrixLang keywords; Task 1 pins that check in a test.

## What is rewritten, and what is left alone

Rewritten: an `ast.ListComp` with **exactly one** generator, whose target is
a plain `ast.Name`, and which is not `async for`. Any number of `if`
clauses.

Left untouched — and therefore still refused by the existing
`_DESCRIBE`/`_IDIOM` path, with no new code:

| Construct | Why it stays refused |
|---|---|
| `[f(x, y) for x in xs for y in ys]` | more than one generator |
| `[f(k) for k, v in items]` | tuple target; the translator refuses tuples |
| set / dict comprehensions, generator expressions | no set type; out of scope |
| `async for` in a comprehension | out of scope |
| a comprehension in a **`while` test** | see below |

**The `while` test is the one position that must be excluded**, and it is
not in the spec. `while` re-evaluates its test every iteration; a hoisted
loop runs once, so `while [x for x in xs]:` would become an infinite loop
or a wrong one. Excluding `While`'s own expression fields costs one
`isinstance` check and leaves the comprehension in place, where it hits the
refusal it already gets today. `While`'s *body* is still processed
normally.

`ast.IfExp` (`a if c else [...]`) needs no special handling: the translator
already refuses conditional expressions, so the statement refuses whatever
the pass does inside it.

## File Structure

| File | Responsibility |
|---|---|
| `src/matrixlang/pytrans/comprehensions.py` | **Create.** The whole pass: block walk, hoister, renamer. Mirrors `names.py` as a small single-purpose sibling. |
| `tests/test_pytrans_comprehensions.py` | **Create.** Source-to-source tests of the pass alone, via `ast.unparse`. |
| `src/matrixlang/pytrans/translate.py` | **Modify.** Three lines in `translate()` (Task 5). |
| `tests/test_architecture.py` | **Modify.** Register the new module in `_ALLOWED` (Task 5). |
| `tests/test_pytrans_expr.py` | **Modify.** End-to-end cases through `translate()` (Task 5). |
| `docs/PYTHON-PARITY.md` | **Modify.** The register; it currently lists comprehensions as unshipped (Task 6). |
| `README.md` | **Modify, conditionally.** Only if its Status list is at feature granularity (Task 6). |

---

### Task 1: The pass, in its simplest complete form

One `for`, no `if`s, with the loop-variable rename that keeps Python's
comprehension scoping.

**Files:**
- Create: `src/matrixlang/pytrans/comprehensions.py`
- Test: `tests/test_pytrans_comprehensions.py`

**Interfaces:**
- Consumes: `free_name(bound: set[str], stem: str = "n") -> str` from `matrixlang.pytrans.names`.
- Produces: `rewrite_comprehensions(tree: ast.Module, taken: set[str]) -> ast.Module`. Mutates `tree` and `taken` in place and returns the tree. Later tasks extend this function's internals; the signature is final.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pytrans_comprehensions.py`:

```python
"""The comprehension pass, tested as Python in and Python out.

Nothing here goes through the translator. A failure means the rewrite is
wrong, not that something downstream broke -- which is the whole reason
the pass is source-to-source in the first place.
"""

import ast

from matrixlang.pytrans.comprehensions import rewrite_comprehensions
from matrixlang.pytrans.names import bound_names
from matrixlang import tokens


def rewritten(source):
    """The Python a snippet becomes once comprehensions are loops."""
    tree = ast.parse(source)
    return ast.unparse(rewrite_comprehensions(tree, bound_names(tree)))


def test_a_comprehension_becomes_an_accumulator_loop():
    assert rewritten("print([f(x) for x in xs])\n") == (
        "out = []\n"
        "for item in xs:\n"
        "    out = out + [f(item)]\n"
        "print(out)"
    )


def test_the_loop_variable_does_not_leak():
    # Python 3 gives a comprehension its own scope, so `x` is still 5
    # afterwards. A rewrite that reused `x` as the loop variable would
    # leave it as 3 -- a wrong answer, silently.
    assert rewritten("x = 5\nout = [x for x in ys]\nprint(x)\n") == (
        "x = 5\n"
        "out1 = []\n"
        "for item in ys:\n"
        "    out1 = out1 + [item]\n"
        "out = out1\n"
        "print(x)"
    )


def test_invented_names_avoid_the_readers():
    assert rewritten("out = 1\nitem = 2\nprint([x for x in xs])\n") == (
        "out = 1\n"
        "item = 2\n"
        "out1 = []\n"
        "for item1 in xs:\n"
        "    out1 = out1 + [item1]\n"
        "print(out1)"
    )


def test_two_comprehensions_get_different_names():
    assert rewritten("print([a for a in xs])\nprint([b for b in ys])\n") == (
        "out = []\n"
        "for item in xs:\n"
        "    out = out + [item]\n"
        "print(out)\n"
        "out1 = []\n"
        "for item1 in ys:\n"
        "    out1 = out1 + [item1]\n"
        "print(out1)"
    )


def test_the_invented_stems_are_not_matrixlang_keywords():
    # A later rename of these stems to, say, `fold` would emit MatrixLang
    # that does not parse, and no other test would catch it.
    from matrixlang.pytrans.comprehensions import _ITEM_STEM, _RESULT_STEM

    assert _RESULT_STEM not in tokens.KEYWORDS
    assert _ITEM_STEM not in tokens.KEYWORDS


def test_a_condition_is_declined_until_task_2_supports_it():
    # Scaffolding, and Task 2 deletes it. Its job is to make the one
    # commit between here and there correct: without the guard the filter
    # is silently dropped rather than declined.
    source = "print([x for x in xs if x > 0])\n"
    assert rewritten(source) == ast.unparse(ast.parse(source))


def test_a_program_without_comprehensions_is_untouched():
    source = "x = 1\nfor y in ys:\n    print(y)\n"
    assert rewritten(source) == ast.unparse(ast.parse(source))
```

Note on the second and third tests: `x` and `out` are already bound by the
reader, so `free_name` moves the accumulator to `out1`. That is the
collision guarantee showing up in the expected output, not an accident.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_pytrans_comprehensions.py -v`
Expected: FAIL at import — `ModuleNotFoundError: No module named 'matrixlang.pytrans.comprehensions'`.

- [ ] **Step 3: Write the module**

Create `src/matrixlang/pytrans/comprehensions.py`:

```python
"""List comprehensions, turned into loops before translation begins.

The translator's own `for` desugaring already emits exactly the shape a
comprehension needs -- an empty list, a counter, and `out = out + [v]`.
So there is nothing to teach it. This pass rewrites the comprehension into
that loop in Python, and `_Translator` never learns what a comprehension
is.

Python in, Python out, which is what makes it testable with `ast.unparse`
and no translator involved: a failure here says the rewrite is wrong
rather than that something downstream broke.

Anything this pass declines to rewrite it leaves exactly as it found it,
so the construct keeps the refusal it already had. Declining is the whole
error-handling strategy; there is no failure mode of its own.
"""

import ast

from matrixlang.pytrans.names import free_name

# Names the reader never wrote. Readable rather than mangled, because the
# emitted MatrixLang is something a person reads -- `construct out = []`
# reads as a program, `construct _c0 = []` reads as machine output.
# free_name keeps them off the reader's own names; neither is a MatrixLang
# keyword (pinned in the tests).
_RESULT_STEM = "out"
_ITEM_STEM = "item"


def rewrite_comprehensions(tree: ast.Module, taken: set[str]) -> ast.Module:
    """Replace supported list comprehensions with the loops they mean.

    `taken` is the caller's set of names already in use. It is the pass's
    running record, not a snapshot: every name invented here is added to
    it, so two comprehensions in one program cannot both be `out`, and the
    counters `_Translator` invents afterwards cannot collide with either.
    """
    tree.body = _block(tree.body, taken)
    return tree


def _block(statements: list[ast.stmt], taken: set[str]) -> list[ast.stmt]:
    """Rewrite one suite, emitting each loop just before it is needed."""
    out: list[ast.stmt] = []
    for statement in statements:
        _rewrite_nested_blocks(statement, taken)
        emitted: list[ast.stmt] = []
        _rewrite_own_expressions(statement, taken, emitted)
        out.extend(emitted)
        out.append(statement)
    return out


_BLOCK_FIELDS = ("body", "orelse", "finalbody")


def _rewrite_nested_blocks(statement: ast.stmt, taken: set[str]) -> None:
    """Recurse into the suites a statement contains.

    Doing this before the statement's own expressions is what keeps a
    comprehension inside a loop body inside that loop, rather than hoisted
    above it where it would run once instead of every turn.
    """
    for field in _BLOCK_FIELDS:
        block = getattr(statement, field, None)
        if isinstance(block, list) and all(isinstance(s, ast.stmt) for s in block):
            setattr(statement, field, _block(block, taken))
    for handler in getattr(statement, "handlers", []):
        handler.body = _block(handler.body, taken)


def _rewrite_own_expressions(
    statement: ast.stmt, taken: set[str], emitted: list[ast.stmt]
) -> None:
    """Rewrite the expressions belonging to this statement itself.

    Walking the statement's own expr-typed fields, rather than the whole
    subtree, is what stops the walk at statement boundaries -- the nested
    suites were already handled above, and re-entering them here would
    hoist their comprehensions out to the wrong level.
    """
    hoister = _Hoister(taken, emitted)
    for field, value in ast.iter_fields(statement):
        if isinstance(value, ast.expr):
            setattr(statement, field, hoister.visit(value))
        elif isinstance(value, list) and any(isinstance(v, ast.expr) for v in value):
            setattr(statement, field, [
                hoister.visit(item) if isinstance(item, ast.expr) else item
                for item in value
            ])


class _Hoister(ast.NodeTransformer):
    """Swaps each comprehension for a name, and records the loop it needs.

    `emitted` is where the loops go, and which list it points at is the
    whole scoping mechanism: the top-level instance writes before the
    containing statement, and instances made for a comprehension's element
    or conditions write inside the loop body being built.
    """

    def __init__(self, taken: set[str], emitted: list[ast.stmt]) -> None:
        self.taken = taken
        self.emitted = emitted

    def visit_ListComp(self, node: ast.ListComp) -> ast.expr:
        clause = node.generators[0] if len(node.generators) == 1 else None
        if clause is None or clause.is_async:
            return node
        if not isinstance(clause.target, ast.Name):
            return node
        if clause.ifs:
            # Task 2 adds these. Until it does, a filter has to be
            # DECLINED rather than ignored: ignoring it would rewrite
            # `[x for x in xs if p(x)]` into a loop that keeps every
            # element, which is a wrong answer where declining is merely
            # the refusal the reader already had. Task 2 deletes this
            # guard as it adds real support.
            return node

        result = self._invent(_RESULT_STEM)
        item = self._invent(_ITEM_STEM)
        element = _renamed(node.elt, clause.target.id, item)

        append = ast.Assign(
            targets=[ast.Name(id=result, ctx=ast.Store())],
            value=ast.BinOp(
                left=ast.Name(id=result, ctx=ast.Load()),
                op=ast.Add(),
                right=ast.List(elts=[element], ctx=ast.Load()),
            ),
        )
        loop = ast.For(
            target=ast.Name(id=item, ctx=ast.Store()),
            iter=clause.iter,
            body=[append],
            orelse=[],
        )
        start = ast.Assign(
            targets=[ast.Name(id=result, ctx=ast.Store())],
            value=ast.List(elts=[], ctx=ast.Load()),
        )
        for made in (start, loop):
            self.emitted.append(ast.fix_missing_locations(ast.copy_location(made, node)))
        return ast.copy_location(ast.Name(id=result, ctx=ast.Load()), node)

    def _invent(self, stem: str) -> str:
        name = free_name(self.taken, stem)
        self.taken.add(name)
        return name


def _renamed(node: ast.expr, old: str, new: str) -> ast.expr:
    """`node` with the comprehension's variable renamed to ours."""
    return _Rename(old, new).visit(node)


class _Rename(ast.NodeTransformer):
    def __init__(self, old: str, new: str) -> None:
        self.old = old
        self.new = new

    def visit_Name(self, node: ast.Name) -> ast.Name:
        if node.id != self.old:
            return node
        return ast.copy_location(ast.Name(id=self.new, ctx=node.ctx), node)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_pytrans_comprehensions.py -v`
Expected: 7 passed.

- [ ] **Step 5: Run the whole suite**

Run: `pytest`
Expected: all pass. The module is not wired into `translate()` yet, so no
existing behaviour can have changed. A failure here means the new file
broke an import or an architecture rule — deal with it now rather than
letting Task 5 inherit it.

- [ ] **Step 6: Commit**

```bash
git add src/matrixlang/pytrans/comprehensions.py tests/test_pytrans_comprehensions.py
git commit -m "feat(pytrans): rewrite simple list comprehensions into loops"
```

---

### Task 2: `if` clauses

**Files:**
- Modify: `src/matrixlang/pytrans/comprehensions.py`
- Test: `tests/test_pytrans_comprehensions.py`

**Interfaces:**
- Consumes: `_Hoister.visit_ListComp` from Task 1.
- Produces: no signature change.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pytrans_comprehensions.py`:

```python
def test_one_condition_becomes_a_guard():
    assert rewritten("print([f(x) for x in xs if x > 2])\n") == (
        "out = []\n"
        "for item in xs:\n"
        "    if item > 2:\n"
        "        out = out + [f(item)]\n"
        "print(out)"
    )


def test_conditions_nest_rather_than_combine():
    # `if c1 if c2` nests instead of becoming `c1 and c2`: one less
    # expression to build, and c2 is not evaluated when c1 is false.
    assert rewritten("print([x for x in xs if c1 if c2])\n") == (
        "out = []\n"
        "for item in xs:\n"
        "    if c1:\n"
        "        if c2:\n"
        "            out = out + [item]\n"
        "print(out)"
    )


def test_the_rename_reaches_the_conditions():
    assert rewritten("print([1 for x in xs if x])\n") == (
        "out = []\n"
        "for item in xs:\n"
        "    if item:\n"
        "        out = out + [1]\n"
        "print(out)"
    )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_pytrans_comprehensions.py -k condition -v`
Expected: FAIL — the comprehension is left exactly as written, because
Task 1's guard declines any comprehension carrying an `if`. Confirm the
failure output still contains `[f(x) for x in xs if x > 2]` unrewritten; a
failure for any other reason means the test is wrong, not the code.

- [ ] **Step 3: Implement**

First delete the two things Task 1 put in as scaffolding, which this task
replaces: the `if clause.ifs: return node` guard in `visit_ListComp`, and
`test_a_condition_is_declined_until_task_2_supports_it` in the test file.
Both were there to keep Task 1's commit correct, and both become false the
moment conditions are supported.

Then, in `visit_ListComp`, after the `element` line, add the conditions,
and replace the `body=[append]` argument to `ast.For`:

```python
        element = _renamed(node.elt, clause.target.id, item)
        conditions = [
            _renamed(test, clause.target.id, item) for test in clause.ifs
        ]
```

```python
        body: list[ast.stmt] = [append]
        for test in reversed(conditions):
            body = [ast.If(test=test, body=body, orelse=[])]
        loop = ast.For(
            target=ast.Name(id=item, ctx=ast.Store()),
            iter=clause.iter,
            body=body,
            orelse=[],
        )
```

Building the guards from the inside out is why `reversed` is there: the
first `if` written must end up outermost.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_pytrans_comprehensions.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/pytrans/comprehensions.py tests/test_pytrans_comprehensions.py
git commit -m "feat(pytrans): support if clauses in comprehensions"
```

---

### Task 3: Where the loop is emitted

The statement-position rules: in place rather than at the top of a block,
and the `while` test excluded.

**Files:**
- Modify: `src/matrixlang/pytrans/comprehensions.py`
- Test: `tests/test_pytrans_comprehensions.py`

**Interfaces:**
- Consumes: `_block`, `_rewrite_own_expressions` from Task 1.
- Produces: no signature change.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pytrans_comprehensions.py`:

```python
def test_inside_a_loop_body_the_rewrite_stays_in_the_loop():
    assert rewritten("for y in ys:\n    print([f(x) for x in y])\n") == (
        "for y in ys:\n"
        "    out = []\n"
        "    for item in y:\n"
        "        out = out + [f(item)]\n"
        "    print(out)"
    )


def test_inside_a_conditional_the_rewrite_stays_in_the_branch():
    # Hoisting above the `if` would call f() when c is false -- the same
    # silent difference accepted for `and`/`or`, but here there is a
    # statement boundary to emit at, so it costs nothing to be correct.
    assert rewritten("if c:\n    print([f(x) for x in xs])\n") == (
        "if c:\n"
        "    out = []\n"
        "    for item in xs:\n"
        "        out = out + [f(item)]\n"
        "    print(out)"
    )


def test_in_an_else_branch():
    assert rewritten("if c:\n    pass\nelse:\n    print([x for x in xs])\n") == (
        "if c:\n"
        "    pass\n"
        "else:\n"
        "    out = []\n"
        "    for item in xs:\n"
        "        out = out + [item]\n"
        "    print(out)"
    )


def test_a_while_test_is_left_alone():
    # `while` re-evaluates its test every turn; a hoisted loop runs once.
    # Left in place, the comprehension keeps the refusal it already has.
    source = "while [x for x in xs]:\n    print(1)\n"
    assert rewritten(source) == ast.unparse(ast.parse(source))


def test_a_comprehension_in_a_while_body_is_still_rewritten():
    assert rewritten("while c:\n    print([x for x in xs])\n") == (
        "while c:\n"
        "    out = []\n"
        "    for item in xs:\n"
        "        out = out + [item]\n"
        "    print(out)"
    )


def test_as_a_call_argument_and_in_a_return():
    assert rewritten("def f():\n    return [x for x in xs]\n") == (
        "def f():\n"
        "    out = []\n"
        "    for item in xs:\n"
        "        out = out + [item]\n"
        "    return out"
    )


def test_a_tuple_target_is_left_alone():
    source = "print([k for k, v in items])\n"
    assert rewritten(source) == ast.unparse(ast.parse(source))


def test_more_than_one_for_is_left_alone():
    source = "print([f(x, y) for x in xs for y in ys])\n"
    assert rewritten(source) == ast.unparse(ast.parse(source))


def test_other_comprehension_kinds_are_left_alone():
    for source in (
        "print({x for x in xs})\n",
        "print({k: v for k in xs})\n",
        "print(sum(x for x in xs))\n",
    ):
        assert rewritten(source) == ast.unparse(ast.parse(source))
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_pytrans_comprehensions.py -v`
Expected: `test_a_while_test_is_left_alone` FAILS — the pass currently
rewrites it, producing a loop before the `while`. The other tests in this
group are expected to PASS already: `_block` recursion and the
leave-alone guards were built in Task 1, and these pin behaviour that must
not regress. **Only the `while` test is a RED here.** If any other test in
this group fails, stop and find out why before implementing — it means
Task 1 does not do what Task 1's tests claimed.

- [ ] **Step 3: Implement**

In `_block`, skip the statement's own expressions for `While`:

```python
        emitted: list[ast.stmt] = []
        # A `while` test is re-evaluated every turn, and a hoisted loop
        # runs once. Left in place, the comprehension keeps the refusal it
        # already has -- which is the right answer and costs no code. The
        # body was already handled above.
        if not isinstance(statement, ast.While):
            _rewrite_own_expressions(statement, taken, emitted)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_pytrans_comprehensions.py -v`
Expected: 18 passed.

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/pytrans/comprehensions.py tests/test_pytrans_comprehensions.py
git commit -m "feat(pytrans): emit comprehension loops in place, not at block top"
```

---

### Task 4: Nested comprehensions

**Files:**
- Modify: `src/matrixlang/pytrans/comprehensions.py`
- Test: `tests/test_pytrans_comprehensions.py`

**Interfaces:**
- Consumes: `_Hoister.visit_ListComp`, `_Rename` from Tasks 1–2.
- Produces: no signature change.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pytrans_comprehensions.py`:

```python
def test_a_nested_comprehension_is_rewritten_inside_the_outer_loop():
    assert rewritten("print([[y for y in row] for row in rows])\n") == (
        "out = []\n"
        "for item in rows:\n"
        "    out1 = []\n"
        "    for item1 in item:\n"
        "        out1 = out1 + [item1]\n"
        "    out = out + [out1]\n"
        "print(out)"
    )


def test_a_declined_inner_comprehension_is_not_renamed_into():
    # The case that actually falsifies a missing scope guard: the inner
    # comprehension has two `for` clauses, so the pass DECLINES it -- and
    # a declined comprehension has to come back byte-identical, or it
    # stops matching the refusal it is supposed to keep. Renaming into it
    # corrupts its own bound variable.
    source = "print([[x for x in a for z in b] for x in rows])\n"
    assert "[x for x in a for z in b]" in rewritten(source)


def test_a_declined_tuple_target_comprehension_is_not_renamed_into():
    # The same hole reached through the tuple-target path rather than the
    # multi-generator one. This is why `binds` walks the target instead of
    # testing it for `ast.Name`.
    source = "print([[y for a, x in pairs] for x in rows])\n"
    assert "[y for a, x in pairs]" in rewritten(source)


def test_a_comprehension_in_the_iterable_hoists_beside_the_outer_loop():
    # `xs` in `for x in [...]` is evaluated once, in the ENCLOSING scope --
    # so its loop belongs before the outer loop, not inside it.
    assert rewritten("print([f(x) for x in [g(y) for y in ys]])\n") == (
        "out = []\n"
        "for item in ys:\n"
        "    out = out + [g(item)]\n"
        "out1 = []\n"
        "for item1 in out:\n"
        "    out1 = out1 + [f(item1)]\n"
        "print(out1)"
    )


def test_a_comprehension_in_a_condition_runs_inside_the_loop():
    assert rewritten("print([x for x in xs if [y for y in x]])\n") == (
        "out = []\n"
        "for item in xs:\n"
        "    out1 = []\n"
        "    for item1 in item:\n"
        "        out1 = out1 + [item1]\n"
        "    if out1:\n"
        "        out = out + [item]\n"
        "print(out)"
    )


def test_an_inner_comprehension_rebinding_the_name_keeps_its_own():
    # Pins the nesting output shape only. It does NOT exercise the scope
    # guard: the inner comprehension here is single-generator, so it gets
    # re-hoisted with its own fresh names either way and the output is the
    # same with or without `_Rename.visit_ListComp`. The two tests below
    # are the ones that falsify a missing guard.
    assert rewritten("print([[x for x in row] for x in rows])\n") == (
        "out = []\n"
        "for item in rows:\n"
        "    out1 = []\n"
        "    for item1 in row:\n"
        "        out1 = out1 + [item1]\n"
        "    out = out + [out1]\n"
        "print(out)"
    )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_pytrans_comprehensions.py -k nested -v` then the whole file.
Expected: FAIL — the inner comprehension is left as a literal `ListComp`
in the unparsed output (visible as `[y for y in row]` still present),
because nothing currently visits the element or the conditions.

- [ ] **Step 3: Implement**

Two changes.

First, in `_Hoister.visit_ListComp`, visit the iterable at the current
level, and visit the element and each condition into their own collectors.
Replace the block from `result = self._invent(...)` through the `loop = `
assignment with:

```python
        # The iterable is evaluated once, out here -- so a comprehension
        # inside it hoists beside this loop, not into it.
        iterable = self.visit(clause.iter)

        result = self._invent(_RESULT_STEM)
        item = self._invent(_ITEM_STEM)

        # Everything below is evaluated per iteration, so each piece
        # collects into the part of the loop body where it belongs: a
        # comprehension in the element must not run when a guard rejects
        # the item, and one in a condition must not run when an earlier
        # condition already failed.
        element_hoists: list[ast.stmt] = []
        element = _Hoister(self.taken, element_hoists).visit(
            _renamed(node.elt, clause.target.id, item)
        )
        conditions: list[tuple[ast.expr, list[ast.stmt]]] = []
        for test in clause.ifs:
            hoists: list[ast.stmt] = []
            rewritten_test = _Hoister(self.taken, hoists).visit(
                _renamed(test, clause.target.id, item)
            )
            conditions.append((rewritten_test, hoists))
```

then, after `append` is built:

```python
        body: list[ast.stmt] = element_hoists + [append]
        for test, hoists in reversed(conditions):
            body = hoists + [ast.If(test=test, body=body, orelse=[])]
        loop = ast.For(
            target=ast.Name(id=item, ctx=ast.Store()),
            iter=iterable,
            body=body,
            orelse=[],
        )
```

Second, teach `_Rename` about comprehension scope. Add to `_Rename`:

```python
    def visit_ListComp(self, node: ast.ListComp) -> ast.ListComp:
        # A nested comprehension that binds the same name has its own
        # scope: its element and conditions see ITS variable, not ours, so
        # the rename must not reach them. Its first iterable is evaluated
        # out here, so that one must.
        binds = any(
            isinstance(name, ast.Name) and name.id == self.old
            for clause in node.generators
            for name in ast.walk(clause.target)
        )
        if not binds:
            return self.generic_visit(node)
        # Only the first iterable: the later ones in a multi-generator
        # comprehension see earlier targets, and such a comprehension is
        # left un-rewritten and refuses anyway.
        node.generators[0].iter = self.visit(node.generators[0].iter)
        return node
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_pytrans_comprehensions.py -v`
Expected: 24 passed.

Then confirm the two `declined` tests are real: rename `_Rename.visit_ListComp`
so it stops being dispatched, re-run them, and see both FAIL. Restore the
file. A scope guard whose absence no test notices is not a guard.

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/pytrans/comprehensions.py tests/test_pytrans_comprehensions.py
git commit -m "feat(pytrans): rewrite nested comprehensions, innermost first"
```

---

### Task 5: Wire it into `translate()`

**Files:**
- Modify: `src/matrixlang/pytrans/translate.py` (imports, and `translate()` around line 101)
- Modify: `tests/test_architecture.py:69-80` (the `_ALLOWED` table)
- Test: `tests/test_pytrans_expr.py`

**Interfaces:**
- Consumes: `rewrite_comprehensions(tree: ast.Module, taken: set[str]) -> ast.Module` from Task 1.
- Produces: the user-visible feature. Nothing consumes this.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pytrans_expr.py`:

```python
def test_a_list_comprehension_translates():
    assert ml("print([x * 2 for x in xs])\n") == (
        "construct out = []\n"
        "construct n = 0\n"
        "dejavu n < length xs\n"
        "  out = out + [xs[n] * 2]\n"
        "  n = n + 1\n"
        "flatline\n"
        "trace out\n"
    )


def test_a_filtered_list_comprehension_translates():
    assert ml("print([x for x in xs if x > 2])\n") == (
        "construct out = []\n"
        "construct n = 0\n"
        "dejavu n < length xs\n"
        "  redpill xs[n] > 2\n"
        "    out = out + [xs[n]]\n"
        "  flatline\n"
        "  n = n + 1\n"
        "flatline\n"
        "trace out\n"
    )


def test_the_translators_own_counter_avoids_the_invented_names():
    # `out` and `item` go into the same `taken` set the counter draws
    # from, so nothing here can collide.
    source = ml("out = 1\nprint([x for x in xs])\n")
    assert "construct out1 = []" in source
    assert "construct out = 1" in source


def test_a_comprehension_in_a_boolean_operand_is_hoisted():
    # The one accepted silent difference: Python skips the comprehension
    # when `c` is false, the translation runs it either way. Pinned so it
    # stays a known quantity rather than being "fixed" into an
    # inconsistency later. An `and` operand is the only position with no
    # statement boundary to emit at.
    source = ml("print(c and [x for x in xs])\n")
    assert source.startswith("construct out = []\n")
    assert source.endswith("trace c splice out\n")


def test_a_refusal_inside_a_comprehension_keeps_the_readers_position():
    # The spec requires generated nodes carry positions, so a refusal
    # raised inside a comprehension points at the reader's line rather
    # than at invented code. `//` is refused permanently, which makes it
    # a stable thing to aim at.
    refusal = refused("a = 1\nb = 2\nprint([x // 2 for x in xs])\n")[0]
    assert (refusal.line, refusal.column) == (3, 7)


def test_the_unsupported_comprehensions_still_refuse():
    assert "a set comprehension" in refused("print({x for x in xs})\n")[0].reason
    assert "a dict comprehension" in refused("print({k: 1 for k in xs})\n")[0].reason
    assert "a generator expression" in refused("print(sum(x for x in xs))\n")[0].reason
    assert "a list comprehension" in refused(
        "print([f(x, y) for x in xs for y in ys])\n"
    )[0].reason
    # Not "a list comprehension": left in place, the comprehension reaches
    # the condition check first, and MatrixLang has no truthiness. The
    # reader gets the better of the two messages.
    assert "truthiness" in refused("while [x for x in xs]:\n    print(1)\n")[0].reason
```

The expected MatrixLang in the first two tests is the shape the existing
`for` desugaring already produces — it was measured, not guessed. If it
comes out differently, the desugaring is what to read, not these strings.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_pytrans_expr.py -k comprehension -v`
Expected: FAIL — `translate()` still refuses with "a list comprehension
cannot be translated", so `ml()` raises its assertion. The
`test_the_unsupported_comprehensions_still_refuse` case is expected to
PASS already; it is the regression net, not a RED.

- [ ] **Step 3: Implement**

In `src/matrixlang/pytrans/translate.py`, add the import beside the
existing `pytrans.names` one:

```python
from matrixlang.pytrans.comprehensions import rewrite_comprehensions
```

Then in `translate()`, replace this line:

```python
    walker = _Translator(bound_names(tree))
```

with:

```python
    # Comprehensions become the loops they mean before the walk starts, so
    # _Translator only ever sees constructs it already handles. `taken` is
    # shared rather than recomputed: the rewrite adds the names it invents
    # to it, so the counters the walker invents cannot collide with them.
    taken = bound_names(tree)
    tree = rewrite_comprehensions(tree, taken)
    walker = _Translator(taken)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_pytrans_expr.py -v`
Expected: all pass, including the position test — `ast.copy_location` and
`ast.fix_missing_locations` in the pass are what make it hold.

- [ ] **Step 5: Register the module in the architecture test**

In `tests/test_architecture.py`, add to `_ALLOWED` beside `"pytrans.names"`:

```python
    "pytrans.comprehensions": {"pytrans.names"},
```

and add `"pytrans.comprehensions"` to the set on the `"pytrans.translate"` entry.

- [ ] **Step 6: Run the whole suite**

Run: `pytest`
Expected: all pass. This is the run that matters — every existing refusal
test is the regression net for "a program with no comprehension in it
translates exactly as it did before".

- [ ] **Step 7: Check the motivating program end to end**

The program that started this work is a book search whose only remaining
blocker was `for ... else`. Confirm a comprehension-bearing program not
only translates but runs:

```bash
python3 -c "
import sys; sys.path.insert(0,'src')
from matrixlang.pytrans import translate
src = '''titles = [\"Dune\", \"Neuromancer\", \"Snow Crash\"]
found = [t for t in titles if \"a\" in t]
print(found)
'''
out = translate(src)
print(out.source)
"
```

Then run that MatrixLang through the interpreter and confirm the answer
matches Python's (`['Neuromancer', 'Snow Crash']`). This project ships
examples executed rather than asserted; if the output differs, the
translation is wrong regardless of what the unit tests say.

- [ ] **Step 8: Commit**

```bash
git add src/matrixlang/pytrans/translate.py tests/test_architecture.py tests/test_pytrans_expr.py
git commit -m "feat(pytrans): translate list comprehensions"
```

---

### Task 6: Update the register

`docs/PYTHON-PARITY.md` is the working register of what the translator
covers. It currently lists "comprehensions" wholesale under Tier 2, which
stops being true the moment Task 5 lands.

**Files:**
- Modify: `docs/PYTHON-PARITY.md` (the "The order" section, and the Tier 2 line near line 173)
- Modify: `README.md` — only per Step 3 below.

**Interfaces:** none. Documentation only.

- [ ] **Step 1: Add the entry to "The order"**

Items 1–5 are all marked `**done**`. Add a sixth after item 5, in the same
voice — what shipped, and what deliberately did not:

```markdown
### 6. List comprehensions — **done**

`[f(x) for x in xs if c]` translates. Not by teaching the translator a new
construct: a pass rewrites the comprehension into the accumulator loop the
`for` desugaring already emits, before translation starts, so the walker
never sees a comprehension at all.

Unlike items 1–5 this one came from a blocked program rather than from the
queue above, which is the register working as intended.

Still refused, and each for a reason rather than for lack of time: more
than one `for` clause, a tuple target (the translator has no tuples), set
and dict comprehensions and generator expressions (no set type, and the
rest is scope), and a comprehension in a `while` test — that one because
`while` re-evaluates its test every turn and a hoisted loop runs once, so
rewriting it would produce a program that silently loops wrong.

One accepted difference, which is the exception that proves the governing
rule: hoisting out of an `and`/`or` operand runs a comprehension Python
would have skipped. It is the only expression position with no statement
boundary to emit at, and a test pins the behaviour so it stays a known
quantity.
```

- [ ] **Step 2: Correct the Tier 2 line**

Tier 2 currently reads:

```
Slicing · tuples · `a if c else b` · comprehensions · number formatting
```

Replace the bare `comprehensions` with `set and dict comprehensions`, so
the line no longer claims list comprehensions are unshipped. Leave the rest
of the line alone.

- [ ] **Step 3: Check the README, and only then edit it**

Run:

```bash
grep -n "comprehension\|Status" README.md
```

The Status list enumerates shipped translator features. Add a line for list
comprehensions **only if** the surrounding entries are at that granularity —
item-per-feature. If the list is coarser than that, leave it: a line the
list's grain does not call for is worse than no line. Say which you did.

- [ ] **Step 4: Commit**

```bash
git add docs/PYTHON-PARITY.md README.md
git commit -m "docs: register list comprehensions as shipped"
```
