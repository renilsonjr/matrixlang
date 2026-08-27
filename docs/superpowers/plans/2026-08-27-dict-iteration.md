# Dictionary Iteration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `for k in d:` over a dictionary produce a program that means what the Python meant.

**Architecture:** A conservative syntactic analysis proves which names hold dictionaries. Where it can, `_for` wraps the iterable in `keymaker`, which yields the keys as a list — after which the existing integer-counter desugaring is correct unchanged. `.keys()` in the iterable position gives the unprovable case a way out.

**Tech Stack:** Python 3.11+, stdlib `ast` only, pytest.

## Global Constraints

- No language change. No new keyword, no new type, no glyph. The table is closed at 56 used / 0 free.
- `translate()` must NEVER raise, for any input.
- **The analysis must be conservative.** Proving "dictionary" wrongly emits `keymaker` on a list — a runtime error this change would be *introducing*. Proving "not a dictionary" wrongly leaves today's behaviour alone. The two mistakes are not symmetric; when unsure, do not prove.
- Every program iterating a list, a string or a `range` must translate **byte-identically** to what it produces today. The existing suite is the net.
- Tests are pytest, under `tests/`, run with `pytest` from the repo root. The suite is 2192 and takes about 3 minutes.

## What this fixes, measured

| program | today | after |
|---|---|---|
| `d = {"a":1,"b":2}` then `for k in d` | crashes: `no key 0 in this dictionary` | prints `a`, `b` |
| `d = {0:10, 1:20}` then `for k in d` | prints `10`, `20` — **wrong, silently** | prints `0`, `1` |
| `d = {}`, `d["a"]=1`, then `for k in d` | crashes | prints `a` |
| `[k for k in d]` | crashes | correct |

The whole change was prototyped before this plan was written: all 13 cases
below agree with CPython through the real interpreter, and the existing
2192 tests pass unchanged.

## No architecture-table change

Unlike the last two features, this adds no module. `dict_names` goes in
`pytrans/names.py`, which `pytrans/translate.py` may already import.
`tests/test_architecture.py` needs no edit — verified.

## File Structure

| File | Responsibility |
|---|---|
| `src/matrixlang/pytrans/names.py` | **Modify.** Add `dict_names` beside `bound_names` (Task 1). |
| `tests/test_pytrans_names.py` | **Create if absent, else modify.** Unit tests for the analysis (Task 1). Check first. |
| `src/matrixlang/pytrans/translate.py` | **Modify.** `_dict_keys_iterable`, the `_for` branch, `_Translator.__init__`, and the `translate()` wiring (Tasks 2-3). |
| `tests/test_pytrans_differential.py` | **Modify.** `agree()` cases — the only tests that catch "runs but means something else" (Tasks 2-3). |
| `docs/PYTHON-PARITY.md`, `docs/LEARNING-MATRIXLANG.md` | **Modify.** The register and the learner guide (Task 4). |

---

### Task 1: `dict_names`

**Files:**
- Modify: `src/matrixlang/pytrans/names.py`
- Test: `tests/test_pytrans_names.py` — **create it.** Confirmed absent at the time this plan was written; `bound_names` and `free_name` are exercised only indirectly today. Check anyway before writing, and append rather than overwrite if it has appeared.

**Interfaces:**
- Produces: `dict_names(tree: ast.AST) -> set[str]`. Pure analysis; no behaviour changes anywhere yet.

- [ ] **Step 1: Write the failing tests**

```python
import ast

from matrixlang.pytrans.names import dict_names


def proven(source):
    """The names this program proves hold dictionaries."""
    return sorted(dict_names(ast.parse(source)))


def test_a_name_bound_to_a_dict_literal_is_proven():
    assert proven('d = {"a": 1}\n') == ["d"]


def test_an_empty_dict_literal_still_proves_it():
    assert proven("d = {}\n") == ["d"]


def test_subscript_assignment_is_not_a_binding():
    # `d = {}` then `d["a"] = 1` is how a reader builds a dictionary. The
    # subscript names `d` in Load context, so it is not a rebinding and
    # must not disqualify it.
    assert proven('d = {}\nd["a"] = 1\n') == ["d"]


def test_a_name_also_bound_to_a_list_is_not_proven():
    assert proven('d = {"a": 1}\nd = [1]\n') == []


def test_a_parameter_of_that_name_disqualifies_it():
    # No scope sensitivity, deliberately: a parameter named `d` anywhere
    # means some `d` can hold anything, and being wrong here emits
    # `keymaker` on a list.
    assert proven('d = {"a": 1}\ndef f(d):\n    return d\n') == []


def test_a_loop_target_of_that_name_disqualifies_it():
    assert proven('d = {"a": 1}\nfor d in xs:\n    print(d)\n') == []


def test_a_tuple_target_never_proves_a_name():
    # The right-hand side must be a dict LITERAL, or this never reaches
    # the `isinstance(target, ast.Name)` guard it exists to pin -- it
    # would fail on the value check instead and the guard could be
    # deleted with every test still green. Unpacking a dict binds its
    # KEYS, so here `d` is the string "a", not a dictionary.
    assert proven('d, e = {"a": 1, "b": 2}\n') == []


def test_a_type_parameter_never_proves_a_name():
    # PEP 695. `def f[d](x)` binds `d` as a TypeVar, and the name lives
    # in a plain string field exactly as MatchAs's does. Skipped below
    # 3.12, where the syntax does not parse.
    import sys

    if sys.version_info < (3, 12):
        return
    assert proven('d = {"a": 1}\ndef f[d](x):\n    return x\n') == []
    assert proven('d = {"a": 1}\ntype d = int\n') == []


def test_the_backstop_denies_what_a_blind_walk_would_prove():
    # The backstop exists for binding forms the walk does not know about
    # -- which, the walk being complete for Python as it stands, cannot
    # be reached through dict_names at all. So it is called directly with
    # a proof the walk would never actually make.
    from matrixlang.pytrans.names import _still_bound_without_their_proofs

    tree = ast.parse('d = {"a": 1}\nmatch xs:\n    case d:\n        pass\n')
    assert _still_bound_without_their_proofs(tree, {"d"}) == {"d"}


def test_a_dict_alone_in_a_block_is_still_proven():
    # Stripping the proof must not empty the block: an empty `class C:`
    # or `def f():` does not unparse, symtable refuses the program, and
    # the failure path denies everything -- including names elsewhere.
    assert proven('class C:\n    d = {"a": 1}\n') == ["d"]
    assert proven('def f():\n    d = {"a": 1}\n') == ["d"]
    assert proven('if c:\n    d = {"a": 1}\n') == ["d"]


def test_one_collapsed_block_does_not_deny_unrelated_names():
    assert proven('class C:\n    d = {"a": 1}\ne = {"b": 2}\n') == ["d", "e"]


def test_a_star_import_proves_nothing():
    # `from m import *` brings in names nobody can enumerate. symtable
    # does not know them either, so it would report every proven name as
    # unbound and wave them all through.
    assert proven('d = {"a": 1}\nfrom m import *\n') == []


def test_an_attribute_assignment_is_not_a_binding():
    # `o.d = 1` names `d` but binds nothing. Guards the Assign-target
    # walk restricting to ast.Name, and would also fail if "attr" were
    # ever added to _NAME_FIELDS. Passes with the backstop disabled --
    # it is not a backstop test.
    assert proven('d = {"a": 1}\no.d = 1\n') == ["d"]


def test_a_dotted_import_denies_the_name_it_actually_binds():
    # `import d.b.c` binds only `d`. The alias node carries the whole
    # dotted path as its name, so denying the raw field value would deny
    # "d.b.c" -- which nobody wrote -- and leave `d` proven.
    assert proven('d = {"a": 1}\nimport d.b.c\n') == []
    assert proven('d = {"a": 1}\nimport x.y as d\n') == []


def test_a_call_keyword_argument_is_not_a_binding():
    # `f(d=1)` names `d` in an ast.keyword, which binds nothing. Denying
    # on the field alone would lose this fix for no safety.
    assert proven('d = {"a": 1}\nf(d=1)\n') == ["d"]


def test_a_match_capture_never_proves_a_name():
    # `case d:` binds `d` through MatchAs, which carries the name as a
    # string and has no ast.Name node to find.
    assert proven(
        'd = {"a": 1}\nmatch xs:\n    case d:\n        print(d)\n'
    ) == []


def test_a_value_from_a_call_is_not_proven():
    assert proven("d = f()\n") == []


def test_several_dictionaries_are_each_proven():
    assert proven('d = {"a": 1}\ne = {"b": 2}\nxs = [1]\n') == ["d", "e"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_pytrans_names.py -v`
Expected: FAIL — `ImportError: cannot import name 'dict_names'`.

- [ ] **Step 3: Implement**

Append to `src/matrixlang/pytrans/names.py`:

The module's imports become `import ast`, `import copy`, `import symtable`
— all stdlib, so `tests/test_architecture.py`, which tracks matrixlang
siblings, is still unaffected.

```python
# Python 3.12+ only; isinstance against an empty tuple is always False,
# which is what keeps this working on the 3.11 floor.
_TYPE_ALIAS = getattr(ast, "TypeAlias", ())

# Every binding form that carries its name as a plain string rather than
# an ast.Name node puts it in one of these fields.
_NAME_FIELDS = ("name", "rest", "asname", "arg")


def dict_names(tree: ast.AST) -> set[str]:
    """Names every one of whose bindings is a dict literal.

    Deliberately conservative, and the asymmetry is the reason. A name
    that holds a dictionary but is not proven here costs the fix; a name
    wrongly proven costs a `keymaker` on a list, which is a runtime error
    this analysis would be introducing. So anything unclear disqualifies.

    Denial is structural rather than a list of node types, with two
    nodes handled by hand: `ast.keyword`, whose name binds nothing, and
    `ast.alias`, whose name is a dotted path rather than the identifier
    it binds. This is the second design this had. The first enumerated binding forms and missed
    four of them in a row -- `match ... case d`, and PEP 695's `type d =`,
    `def f[d]`, `class C[d]` -- every one a binding that carries its name
    as a plain string field where a walk looking for ast.Name finds
    nothing. Denying on the FIELD rather than the node type closes that
    class instead of adding a fifth special case, and covers forms this
    version of Python does not have yet.

    A subscript target is NOT a binding. `d = {}` followed by
    `d["a"] = 1` leaves `d` proven, which matters because building a
    dictionary and then walking it is the shape a reader actually writes.

    There is no scope sensitivity, on purpose. A module-level `d` and an
    unrelated parameter named `d` disqualify the name everywhere. That
    costs a fix we could have made; the alternative costs a failure we
    would have introduced.
    """
    proven: dict[str, bool] = {}

    def deny(target: ast.AST) -> None:
        for inner in ast.walk(target):
            if isinstance(inner, ast.Name) and isinstance(inner.ctx, ast.Store):
                proven[inner.id] = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                # A tuple target binds no single name to the literal,
                # whatever the right-hand side is: unpacking a dictionary
                # binds its KEYS.
                ok = isinstance(node.value, ast.Dict) and isinstance(target, ast.Name)
                for inner in ast.walk(target):
                    if isinstance(inner, ast.Name) and isinstance(inner.ctx, ast.Store):
                        proven[inner.id] = proven.get(inner.id, True) and ok
            continue

        if isinstance(
            node,
            (ast.AugAssign, ast.AnnAssign, ast.NamedExpr,
             ast.For, ast.AsyncFor, ast.comprehension),
        ):
            deny(node.target)
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            deny(node.optional_vars)
        elif isinstance(node, _TYPE_ALIAS):
            # The one string-named form whose name IS an ast.Name node.
            deny(node.name)

        if isinstance(node, ast.alias):
            # The one field whose value is not the identifier it binds:
            # `import d.b.c` has name="d.b.c" and binds only `d`. Denying
            # the raw string would deny a name nobody wrote and leave the
            # real one proven.
            proven[node.asname or node.name.split(".")[0]] = False
            continue
        if isinstance(node, ast.keyword):
            # A call's keyword argument name binds nothing: `f(d=1)` must
            # leave a dictionary named `d` proven.
            continue
        for field in _NAME_FIELDS:
            value = getattr(node, field, None)
            if isinstance(value, str):
                proven[value] = False

    walked = {name for name, ok in proven.items() if ok}
    return walked - _still_bound_without_their_proofs(tree, walked)


class _WithoutProvingAssigns(ast.NodeTransformer):
    """Replaces the dict-literal assignments the walk credited for a proof.

    `pass` rather than deletion, and that is not a style choice. Removing
    the only statement in a block leaves an empty body, which `ast.unparse`
    renders as invalid source -- `class C:` with nothing under it -- and
    `symtable` then refuses the whole program. The failure path denies
    every proven name, so one `def f(): d = {...}` would cost every fix in
    the file, including names with nothing to do with it.
    """

    def __init__(self, names: set[str]) -> None:
        self.names = names

    def visit_Assign(self, node: ast.Assign):
        if isinstance(node.value, ast.Dict) and all(
            isinstance(t, ast.Name) and t.id in self.names for t in node.targets
        ):
            return ast.copy_location(ast.Pass(), node)
        return node


def _still_bound_without_their_proofs(tree: ast.AST, proven: set[str]) -> set[str]:
    """Of `proven`, the names Python still binds once their proofs are gone.

    The backstop, and the reason it is shaped this way. Asking symtable
    which names are bound cannot catch anything on its own: a name that is
    both assigned a dict literal AND captured by a form the walk missed is
    reported bound either way, so subtracting what the walk saw leaves
    nothing. Removing the assignments the walk is relying on and asking
    again is what makes the missed binding the only one left to report.

    Any name that survives that has a binding the walk did not classify.
    It is denied, and the cost is one lost fix rather than a `keymaker`
    emitted onto a list.
    """
    if not proven:
        return set()
    for node in ast.walk(tree):
        # `from m import *` brings in names nobody can enumerate --
        # symtable does not know them either, so it would report every
        # proven name as unbound and wave them all through. The only
        # honest answer is to prove nothing.
        if isinstance(node, ast.alias) and node.name == "*":
            return set(proven)
    try:
        stripped = _WithoutProvingAssigns(proven).visit(copy.deepcopy(tree))
        ast.fix_missing_locations(stripped)
        table = symtable.symtable(ast.unparse(stripped) or "pass", "<dict_names>", "exec")
    except (SyntaxError, ValueError, RecursionError, AttributeError, TypeError):
        # Unparseable or unanalysable: deny everything, the safe direction.
        return set(proven)

    still: set[str] = set()

    def visit(scope) -> None:
        for symbol in scope.get_symbols():
            name = symbol.get_name()
            if name in proven and (
                symbol.is_assigned() or symbol.is_parameter() or symbol.is_imported()
            ):
                still.add(name)
        for child in scope.get_children():
            visit(child)

    visit(table)
    return still
```

`False` is absorbing: once a name is denied, `proven.get(name, True) and ok`
keeps it denied whatever order `ast.walk` visits things in. That is what
makes the analysis order-independent.

**Why the backstop is shaped the way it is, and not the obvious way.** The
obvious backstop — ask `symtable` which names are bound and deny any the
walk did not see a site for — **catches nothing**, and this was measured
rather than reasoned about. A name that is both assigned a dict literal
and captured by a form the walk missed is reported bound either way, so
subtracting what the walk saw leaves an empty set. Removing the
assignments the walk is *relying on* and asking again is what makes the
missed binding the only one left to report.

Verified against nine simulated misses — every historical one plus
parameters, `except ... as`, `with ... as`, and loop targets — all caught;
and against five names that must stay proven, all kept.

Cost: nothing when no name is proven (an early return, measured at 0.02ms
on a 1900-line file), and one deepcopy, unparse and `symtable` build when
one is — 44ms on that same file, and playground programs are a fraction of
its size.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_pytrans_names.py -v`
Expected: 18 passed.

- [ ] **Step 5: Run the whole suite**

Run: `pytest`
Expected: 2192 + 18. Nothing calls `dict_names` yet, so no
existing behaviour can have changed.

- [ ] **Step 6: Commit**

```bash
git add src/matrixlang/pytrans/names.py tests/test_pytrans_names.py
git commit -m "feat(pytrans): prove which names hold dictionaries"
```

---

### Task 2: Iterate a proven dictionary by its keys

**Files:**
- Modify: `src/matrixlang/pytrans/translate.py`
- Test: `tests/test_pytrans_differential.py`

**Interfaces:**
- Consumes: `dict_names(tree) -> set[str]` from Task 1.
- Produces: `_dict_keys_iterable(node: ast.expr, dicts: set[str]) -> ast.expr | None`, extended in Task 3.

**This is where behaviour changes.** Everything before was inert.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pytrans_differential.py`, following the form of the
tests already there. **These run both sides and compare output — the only
tests here that can catch a program which parses, runs, and means
something other than the Python did, which is exactly this defect.**

```python
def test_iterating_a_dictionary_yields_its_keys_agrees():
    agree('d = {"a": 1, "b": 2}\nfor k in d:\n    print(k)\n')


def test_iterating_a_dictionary_with_integer_keys_agrees():
    # The case that used to run cleanly and print the VALUES where Python
    # prints the keys. A crash is at least visible; this one was not.
    agree("d = {0: 10, 1: 20}\nfor k in d:\n    print(k)\n")


def test_iterating_an_empty_dictionary_agrees():
    agree("d = {}\nfor k in d:\n    print(k)\nprint(9)\n")


def test_looking_up_values_while_iterating_a_dictionary_agrees():
    agree('d = {"a": 1, "b": 2}\nfor k in d:\n    print(d[k])\n')


def test_iterating_a_dictionary_built_by_subscript_agrees():
    agree('d = {}\nd["a"] = 1\nd["b"] = 2\nfor k in d:\n    print(k)\n')


def test_iterating_a_dict_literal_inline_agrees():
    agree('for k in {"a": 1, "b": 2}:\n    print(k)\n')


def test_a_comprehension_over_a_dictionary_agrees():
    agree('d = {"a": 1, "b": 2}\nprint(len([k for k in d]))\n')


def test_adding_a_key_during_iteration_completes_where_python_raises():
    # The one accepted difference, pinned so it stays a known quantity.
    # Python raises `RuntimeError: dictionary changed size during
    # iteration`; the translation walks the keys as they were at loop
    # entry and finishes. There is no MatrixLang output that reproduces a
    # Python runtime error, and the reader's program was already an error
    # -- so this is recorded rather than closed. Not an `agree()` case,
    # because the two deliberately do not agree.
    # io, Interpreter, ListSource, lex, parse, translate and Translated
    # are all already imported at the top of this file -- do not add them.
    source = 'd = {"a": 1}\nfor k in d:\n    d[k + "x"] = 2\n    print(k)\n'
    result = translate(source)
    assert isinstance(result, Translated), result
    out = io.StringIO()
    Interpreter(out=out, source=ListSource([])).run(parse(lex(result.source)))
    assert out.getvalue() == "a\n"


def test_rebinding_a_dictionary_inside_its_own_loop_agrees():
    # The list path REFUSES this shape, because the output indexes the
    # name and would follow the rebinding. A dictionary is hoisted into a
    # keys list instead, so rebinding cannot reach it -- which is also
    # what Python does, its `for` holding the object it was given.
    agree('d = {"a": 1, "b": 2}\nfor k in d:\n    d = {"z": 9}\n    print(k)\n')
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_pytrans_differential.py -k dictionar -v`
Expected: FAIL. The string-keyed cases fail with a MatrixLang runtime
error (`no key 0 in this dictionary`); the integer-keyed one fails as a
**mismatch** — `python='0\n1'` against `matrixlang='10\n20'`. Confirm you
see both failure shapes; they are the two defects being fixed.

- [ ] **Step 3: Implement**

Three edits.

First, the helper. Add it immediately above `_is_input_call`:

```python
def _dict_keys_iterable(node: ast.expr, dicts: set[str]) -> ast.expr | None:
    """The expression whose KEYS this iterable stands for, or None.

    Read off the raw ast, BEFORE expression() -- that call is what raises
    the existing `.keys()` refusal, so a branch placed after it never
    runs. Task 3 adds the `.keys()` case here.
    """
    if isinstance(node, ast.Dict):
        return node
    if isinstance(node, ast.Name) and node.id in dicts:
        return node
    return None
```

Second, `_Translator` has to carry the proven set:

```python
    def __init__(self, taken: set[str] | None = None,
                 dicts: set[str] | None = None) -> None:
        self.dicts: set[str] = dicts or set()
```

keeping the rest of `__init__` as it is, and in `translate()`:

```python
    walker = _Translator(taken, dict_names(tree))
```

with `dict_names` added to the existing `from matrixlang.pytrans.names import ...`.

Third, the branch in `_for`. Replace this:

```python
            value = self.expression(node.iter)
            if isinstance(value, Name):
```

with:

```python
            keys_of = _dict_keys_iterable(node.iter, self.dicts)
            if keys_of is not None:
                # A dictionary iterates its KEYS, and the desugaring below
                # indexes by an integer counter -- right for a list or a
                # string, wrong for a dictionary. `keymaker` turns it into
                # the list of keys the loop should walk. Hoisted like any
                # other non-name iterable, which is also what makes
                # rebinding the dictionary inside the body harmless, the
                # way Python's `for` holding the object it was given is.
                value = Unary(TokenType.KEYMAKER, self.expression(keys_of))
                holder = self._fresh("ks")
                before.append(Declare(holder, value))
            else:
                value = self.expression(node.iter)
                if isinstance(value, Name):
```

and **indent the rest of that original branch by one level** so it sits
inside the new `else` — the `holder = value.ident` line, the `_rebinds`
refusal it guards, and the `else:` clause that hoists a non-name iterable.
The lines after it (`self.substitutions[...]`, the counter `Declare`, the
`condition`) stay where they are: both paths set `holder`, and everything
downstream is shared.

The stem is `ks`, not the `xs` the other path uses. The emitted MatrixLang
is read by people, and `construct xs = keymaker d` says a dictionary's
keys are a list called `xs` — the exact confusion this change removes.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_pytrans_differential.py -v`
Expected: all pass.

Then check the emitted shape by hand:

```bash
python3 -c "
import sys; sys.path.insert(0,'src')
from matrixlang.pytrans import translate
print(translate('d = {\"a\": 1, \"b\": 2}\nfor k in d:\n    print(d[k])\n').source)
"
```

Expected, exactly:

```
construct d = {"a": 1, "b": 2}
construct ks = keymaker d
construct n = 0
dejavu n < length ks
  trace d[ks[n]]
  n = n + 1
flatline
```

- [ ] **Step 5: Run the whole suite**

Run: `pytest`
Expected: all pass. **This is the step that matters.** Every existing test
iterating a list, a string or a `range` is the regression net for "nothing
that worked changed". The prototype for this plan passed all 2192
unchanged; if yours does not, the conservatism is wrong somewhere and a
program that used to work now emits `keymaker` on a list.

- [ ] **Step 6: Commit**

```bash
git add src/matrixlang/pytrans/translate.py tests/test_pytrans_differential.py
git commit -m "fix(pytrans): iterate a dictionary by its keys, not by index"
```

---

### Task 3: `.keys()` as the way out

**Files:**
- Modify: `src/matrixlang/pytrans/translate.py`
- Test: `tests/test_pytrans_differential.py`, `tests/test_pytrans_refuse.py`

**Interfaces:** Consumes `_dict_keys_iterable` from Task 2. No signature change.

A dictionary arriving through a parameter cannot be proven. `.keys()` is
what a reader can write instead.

- [ ] **Step 1: Write the failing tests**

To `tests/test_pytrans_differential.py`:

```python
def test_iterating_dict_keys_explicitly_agrees():
    agree('d = {"a": 1, "b": 2}\nfor k in d.keys():\n    print(k)\n')


def test_iterating_dict_keys_of_a_parameter_agrees():
    # The case the analysis can never prove: the dictionary arrives as an
    # argument. `.keys()` is what makes it expressible.
    agree(
        'def f(d):\n    for k in d.keys():\n        print(k)\n'
        'f({"a": 1, "b": 2})\n'
    )
```

and to `tests/test_pytrans_refuse.py`, following that file's existing
style (it has no `refused()` helper — use `translate()` and
`isinstance(..., Refusals)` as the neighbouring tests do):

```python
def test_keys_outside_a_for_iterable_still_refuses():
    # `.keys()` is supported ONLY as the thing a `for` walks. Python
    # prints `d.keys()` as `dict_keys(['a'])` where a MatrixLang list
    # prints `["a"]`, so supporting it as a value would trade one silent
    # difference for another.
    result = translate('d = {"a": 1}\nprint(d.keys())\n')
    assert isinstance(result, Refusals), result
    assert "`.keys()`" in result.items[0].reason
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_pytrans_differential.py -k keys -v`
Expected: FAIL — `agree()` asserts the result is `Translated`, and
`.keys()` currently refuses with ``.keys()` cannot be translated as a
value`. The refusal test in `test_pytrans_refuse.py` is expected to PASS
already; it is a regression pin, not a RED.

- [ ] **Step 3: Implement**

Add the third case to `_dict_keys_iterable`, before its `return None`:

```python
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "keys"
        and not node.args
        and not node.keywords
    ):
        return node.func.value
```

and delete the "Task 3 adds the `.keys()` case here" line from its
docstring. Note the receiver is **not** required to be a proven
dictionary: `.keys()` exists precisely for the case that cannot be proven.
`xs.keys()` on a list fails in both languages — `AttributeError` in
Python, `'keymaker' takes a dictionary` in MatrixLang.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_pytrans_differential.py -v` and
`pytest tests/test_pytrans_refuse.py -v`
Expected: all pass.

- [ ] **Step 5: Run the whole suite**

Run: `pytest`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/matrixlang/pytrans/translate.py tests/test_pytrans_differential.py tests/test_pytrans_refuse.py
git commit -m "feat(pytrans): support .keys() as a for iterable"
```

---

### Task 4: The register and the learner guide

**Files:**
- Modify: `docs/PYTHON-PARITY.md`
- Modify: `docs/LEARNING-MATRIXLANG.md` — only per Step 2.

- [ ] **Step 1: Add the entry to "The order"**

Items 1-7 are marked `**done**`. Add an eighth in the same voice. Unlike
the others this one is a **defect fixed**, not a gap closed, and the entry
should say so — the translator accepted a program and produced one that
meant something else, which is what the governing rule exists to prevent.

It must record:

- both failure modes: a crash with string keys, and a **silent wrong
  answer** with integer keys, where the translation printed the values
  Python prints the keys;
- that `keymaker` was already the right answer and the work was knowing
  when to reach for it;
- that the analysis is conservative on purpose, because proving
  "dictionary" wrongly would introduce a runtime error while proving "not
  a dictionary" wrongly leaves today's behaviour alone;
- **the residual, plainly**: a dictionary arriving through a parameter or
  a call result is still iterated as a list, and `.keys()` is what a
  reader writes instead. Do not imply the gap is closed;
- **one accepted difference**: adding a key during iteration raises
  `RuntimeError` in Python and completes in the translation, because the
  keys are taken once at loop entry. The reader's program was already an
  error in Python, and no MatrixLang output reproduces a Python runtime
  error. It is pinned by a test.

- [ ] **Step 2: Check the learner guide, then edit only what is false**

Run:

```bash
grep -n -i "keymaker\|dictionar" docs/LEARNING-MATRIXLANG.md
```

If it describes iterating a dictionary from Python, or lists `.keys()`
among things that are refused, correct it. If it says nothing that is now
false, leave the file alone and say so in your report. Do not add a
section the guide's structure does not call for.

- [ ] **Step 3: Verify**

Run: `pytest`
Expected: all pass. Documentation should not affect it, but this repo has
tests that read documentation files — confirm rather than assume.

- [ ] **Step 4: Commit**

```bash
git add docs/PYTHON-PARITY.md docs/LEARNING-MATRIXLANG.md
git commit -m "docs: register dictionary iteration as fixed"
```
