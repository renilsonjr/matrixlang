# Python Translator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a reader paste Python into the playground and get MatrixLang that runs, or a refusal naming the line and the idiom to use instead.

**Architecture:** Walk the Python AST with `ast`, build real `matrixlang.nodes` objects, and hand them to `render_ascii()`. Never emit text directly — `render.py` already owns precedence and parenthesisation, and re-deriving them is the mistake that produced the deleted `web/interpreter.js`. Building real nodes makes the output parseable by construction.

**Tech Stack:** Python 3.11+ stdlib (`ast`), pytest. No new dependencies.

## Global Constraints

- **`translate(source) -> Translated | Refusals` never raises.** A Python `SyntaxError` is a refusal, not an exception. So is anything else that goes wrong.
- **Translate syntax; never infer types.** Refuse where the difference would be silent; allow where MatrixLang will fail loudly with a position.
- **All refusals are collected**, in line order. When any refusal exists, no program is returned — a partial translation is a wrong program.
- **Every refusal carries the Python line and column**, what is unsupported, and the MatrixLang idiom where one exists.
- **The translator adds no AST node types.** Every node it needs already exists in `src/matrixlang/nodes.py`.
- **The browser gains no language logic.** `site/checks/no_semantics.py` must pass **unmodified**.
- Run tests from the repo root: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest -q`. Use `python3`, not `python`.
- Conventional-commit subjects. **Never write "Closes #122"** in a commit message.

## File Structure

| Path | Responsibility |
| --- | --- |
| `src/matrixlang/pytrans/__init__.py` | Exports `translate`, `Translated`, `Refusal`, `Refusals` |
| `src/matrixlang/pytrans/refuse.py` | `Refusal`, `Refusals`, the `_Unsupported` signal, the message catalogue |
| `src/matrixlang/pytrans/names.py` | Counter and temp-name allocation |
| `src/matrixlang/pytrans/translate.py` | The `_Translator` walker and the public `translate()` |
| `site/glue.py` | `translate_python()`, mirroring `write()` |
| `site/index.html`, `site/style.css`, `site/playground.js` | The collapsed Python box in the editor pane |
| `tests/test_pytrans_*.py` | One file per stage, following the `test_dicts_*.py` convention |

### Where the tests go

Follow the house convention. Feature tests split by stage, one `run`-style helper defined locally per file:

```
tests/test_pytrans_refuse.py     tests/test_pytrans_expr.py
tests/test_pytrans_stmt.py       tests/test_pytrans_loops.py
tests/test_pytrans_differential.py
```

Do **not** append to `test_parser.py` or `test_interpreter.py`.

Most files need this helper, which asserts on rendered MatrixLang:

```python
from matrixlang.pytrans import translate, Translated, Refusals


def ml(python_source):
    """The MatrixLang a Python snippet translates to. Fails loudly on refusal."""
    result = translate(python_source)
    assert isinstance(result, Translated), getattr(result, "items", result)
    return result.source


def refused(python_source):
    """The refusals a Python snippet produces. Fails loudly if it translated."""
    result = translate(python_source)
    assert isinstance(result, Refusals), result
    return result.items
```

---

### Task 1: The skeleton — refusals, and never raising

**Files:**
- Create: `src/matrixlang/pytrans/__init__.py`, `refuse.py`, `translate.py`
- Create: `tests/test_pytrans_refuse.py`

**Interfaces:**
- Produces:
  - `Translated(source: str)` — frozen dataclass
  - `Refusal(reason: str, line: int, column: int, idiom: str | None)` — frozen dataclass
  - `Refusals(items: list[Refusal])` — frozen dataclass, `items` never empty
  - `translate(source: str) -> Translated | Refusals` — never raises
  - `_Unsupported(Exception)` carrying `.refusal`

**Why the signal carries a position, unlike the codebase's other signals.** `values.CyclicValue` and friends are position-less because `values.py` has no source positions to give. Here the Python AST node *does* carry one, so `_Unsupported` carries a fully-formed `Refusal`. It is raised deep in the walk and caught per statement.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pytrans_refuse.py`:

```python
"""The translator's refusal machinery, and its promise never to raise."""

from matrixlang.pytrans import Refusals, Translated, translate


def test_invalid_python_is_a_refusal_not_an_exception():
    result = translate("def (:\n")
    assert isinstance(result, Refusals)
    assert result.items[0].line == 1


def test_an_empty_program_translates_to_an_empty_program():
    result = translate("")
    assert isinstance(result, Translated)
    assert result.source == ""


def test_an_unsupported_statement_is_refused_with_its_line():
    result = translate("import os\n")
    assert isinstance(result, Refusals)
    assert result.items[0].line == 1
    assert "import" in result.items[0].reason


def test_every_refusal_is_collected_not_just_the_first():
    result = translate("import os\nimport sys\nclass A: pass\n")
    assert isinstance(result, Refusals)
    assert [r.line for r in result.items] == [1, 2, 3]


def test_refusals_are_in_line_order():
    result = translate("class A: pass\nimport os\n")
    assert [r.line for r in translate("class A: pass\nimport os\n").items] == [1, 2]


def test_a_refusal_names_an_idiom_when_one_exists():
    refusal = translate("xs = [f(x) for x in ys]\n").items[0]
    assert refusal.idiom is not None
    assert "dejavu" in refusal.idiom
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_pytrans_refuse.py -q`
Expected: FAIL with `ModuleNotFoundError: matrixlang.pytrans`.

- [ ] **Step 3: Write `refuse.py`**

```python
"""What the translator will not do, and how it says so.

A refusal is the point of this package, not its failure mode. MatrixLang is
missing most of Python on purpose, so a translator that tried to cover
everything would have to invent semantics -- and a program that runs and
means something slightly different is the one outcome worth engineering
against. Every refusal therefore carries a position and, where MatrixLang
has an idiom, the thing to write instead.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Refusal:
    reason: str
    line: int
    column: int
    idiom: str | None = None


@dataclass(frozen=True)
class Refusals:
    items: list[Refusal]


@dataclass(frozen=True)
class Translated:
    source: str


class _Unsupported(Exception):
    """One construct the translator will not touch.

    Carries a fully-formed Refusal rather than a bare message. Unlike
    values.CyclicValue and its siblings -- which are position-less because
    values.py has no positions to give -- the Python AST node this comes
    from knows exactly where it is, so there is nothing to reconstruct
    higher up. Raised deep in the walk, caught once per statement so the
    walk can continue and collect the rest.
    """

    def __init__(self, refusal: Refusal) -> None:
        super().__init__(refusal.reason)
        self.refusal = refusal
```

- [ ] **Step 4: Write the skeleton `translate.py`**

```python
"""Python source in, MatrixLang source out.

Builds real `matrixlang.nodes` objects and renders them with the real
renderer, rather than emitting text. render.py already knows every
precedence rule and where parentheses are needed; a second copy of that
knowledge here is the shape of mistake that produced the deleted
web/interpreter.js. Building nodes also means the output parses by
construction -- it came from the same classes the parser produces.
"""

import ast

from matrixlang.nodes import Program, Stmt
from matrixlang.render import render_ascii

from matrixlang.pytrans.refuse import Refusal, Refusals, Translated, _Unsupported


def translate(source: str) -> Translated | Refusals:
    """Translate Python to MatrixLang. Never raises."""
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return Refusals([
            Refusal(
                f"this is not valid Python: {error.msg}",
                error.lineno or 1,
                (error.offset or 1) - 1,
            )
        ])

    walker = _Translator()
    statements = walker.body(tree.body)
    if walker.refusals:
        return Refusals(sorted(walker.refusals, key=lambda r: (r.line, r.column)))
    return Translated(render_ascii(Program(statements)))


class _Translator:
    def __init__(self) -> None:
        self.refusals: list[Refusal] = []

    def body(self, statements: list[ast.stmt]) -> list[Stmt]:
        """Translate a block, collecting refusals rather than stopping.

        Catching per statement is what makes a thirty-line program take one
        pass to fix instead of five.
        """
        out: list[Stmt] = []
        for node in statements:
            try:
                out.extend(self.statement(node))
            except _Unsupported as stop:
                self.refusals.append(stop.refusal)
        return out

    def statement(self, node: ast.stmt) -> list[Stmt]:
        raise _Unsupported(self._no(node))

    def _no(self, node: ast.AST, idiom: str | None = None) -> Refusal:
        name = type(node).__name__
        return Refusal(
            f"{_DESCRIBE.get(name, name)} cannot be translated",
            getattr(node, "lineno", 1),
            getattr(node, "col_offset", 0),
            idiom if idiom is not None else _IDIOM.get(name),
        )


# What a reader calls each construct, keyed by its ast class name. Without
# this a refusal says "ImportFrom", which is Python's word, not theirs.
_DESCRIBE = {
    "Import": "`import`",
    "ImportFrom": "`import`",
    "ClassDef": "`class`",
    "Try": "`try`",
    "Raise": "`raise`",
    "Lambda": "`lambda`",
    "ListComp": "a list comprehension",
    "SetComp": "a set comprehension",
    "DictComp": "a dict comprehension",
    "GeneratorExp": "a generator expression",
}

_IDIOM = {
    "ListComp": "build the list with a `dejavu` loop and `xs = xs + [v]`",
    "SetComp": "MatrixLang has no sets; use a list",
    "DictComp": "build the dictionary with a `dejavu` loop and `d[k] = v`",
    "GeneratorExp": "build the list with a `dejavu` loop",
}
```

- [ ] **Step 5: Write `__init__.py`**

```python
"""Paste Python, get MatrixLang -- for a stated subset, refusing the rest."""

from matrixlang.pytrans.refuse import Refusal, Refusals, Translated
from matrixlang.pytrans.translate import translate

__all__ = ["Refusal", "Refusals", "Translated", "translate"]
```

- [ ] **Step 6: Run the tests**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_pytrans_refuse.py -q`
Expected: PASS.

- [ ] **Step 7: Run the whole suite**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest -q`
Expected: PASS. A new package can trip `tests/test_architecture.py`, which asserts things about module dependencies — if it does, read what it asserts before changing anything and report it.

- [ ] **Step 8: Commit**

```bash
git add src/matrixlang/pytrans tests/test_pytrans_refuse.py
git commit -m "feat: the translator skeleton, which refuses everything clearly"
```

---

### Task 2: Expressions, and `print`

**Files:**
- Modify: `src/matrixlang/pytrans/translate.py`
- Create: `tests/test_pytrans_expr.py`

**Interfaces:**
- Consumes: `_Unsupported`, `Refusal`, `_Translator` from Task 1.
- Produces: `_Translator.expression(node: ast.expr) -> Expr`, and `print(x)` → `Trace`.

**Why `print` lands here.** An expression needs a statement to hold it before it can be tested end to end, and `trace` is the smallest one.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pytrans_expr.py` with the `ml`/`refused` helpers from the File Structure section above, then:

```python
def test_numbers_strings_and_booleans():
    assert ml("print(1)\n") == "trace 1\n"
    assert ml('print("hi")\n') == 'trace "hi"\n'
    assert ml("print(True)\nprint(False)\n") == "trace true\ntrace false\n"


def test_names():
    assert ml("print(x)\n") == "trace x\n"


def test_arithmetic_and_comparison():
    assert ml("print(1 + 2 * 3)\n") == "trace 1 + 2 * 3\n"
    assert ml("print((1 + 2) * 3)\n") == "trace (1 + 2) * 3\n"
    assert ml("print(a <= b)\n") == "trace a <= b\n"


def test_boolean_operators():
    assert ml("print(a and b)\n") == "trace a splice b\n"
    assert ml("print(a or b)\n") == "trace a fork b\n"
    assert ml("print(not a)\n") == "trace unplug a\n"


def test_unary_minus():
    assert ml("print(-x)\n") == "trace -x\n"


def test_list_and_dict_literals():
    assert ml("print([1, 2])\n") == "trace [1, 2]\n"
    assert ml('print({"a": 1})\n') == 'trace {"a": 1}\n'


def test_indexing():
    assert ml('print(xs[0])\n') == "trace xs[0]\n"
    assert ml('print(d["a"])\n') == 'trace d["a"]\n'


def test_len_str_and_int():
    assert ml("print(len(xs))\n") == "trace length xs\n"
    assert ml("print(str(n))\n") == "trace encode n\n"
    assert ml("print(int(s))\n") == "trace decode s\n"


def test_a_call_to_a_reader_defined_function():
    assert ml("print(f(1, 2))\n") == "trace f(1, 2)\n"


def test_in_over_a_dictionary_is_oracle():
    assert ml('print("a" in d)\n') == 'trace d oracle "a"\n'


def test_precedence_is_rebuilt_not_copied():
    # The renderer decides parentheses, so a tree that needs them gets them
    # and one that does not is left clean. This is the whole reason the
    # translator builds nodes instead of emitting text.
    assert ml("print(a * (b + c))\n") == "trace a * (b + c)\n"
    assert ml("print(a * b + c)\n") == "trace a * b + c\n"


def test_a_float_is_refused():
    refusal = refused("print(1.5)\n")[0]
    assert "float" in refusal.reason


def test_none_is_refused():
    assert "None" in refused("print(None)\n")[0].reason


def test_a_tuple_is_refused():
    assert refused("print((1, 2))\n")[0].idiom is not None


def test_a_chained_comparison_is_refused():
    assert "chain" in refused("print(a < b < c)\n")[0].reason


def test_slicing_is_refused():
    assert refused("print(xs[1:3])\n")[0].idiom is not None


def test_is_is_refused():
    assert "is" in refused("print(a is b)\n")[0].reason


def test_print_with_several_arguments_is_refused():
    refusal = refused('print("a", "b")\n')[0]
    assert refusal.idiom is not None


def test_a_bare_expression_statement_is_refused():
    # MatrixLang's grammar accepts an expression statement only when it is a
    # call: `1 + 1` alone computes and discards, which the parser treats as a
    # mistake. Python allows it, so it is refused here.
    assert refused("1 + 1\n")[0].idiom is not None
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_pytrans_expr.py -q`
Expected: FAIL — every statement currently refuses.

- [ ] **Step 3: Implement expressions**

Add to `_Translator` in `translate.py`. Import the nodes you need at the top:

```python
from matrixlang.nodes import (
    Binary, BoolLiteral, Call, DictLiteral, Expr, Index, ListLiteral,
    Name, NumberLiteral, Program, Stmt, StringLiteral, Trace, Unary,
)
from matrixlang.tokens import TokenType
```

```python
_BINOP = {
    ast.Add: TokenType.PLUS, ast.Sub: TokenType.MINUS,
    ast.Mult: TokenType.STAR, ast.Div: TokenType.SLASH,
}

_COMPARE = {
    ast.Eq: TokenType.EQ, ast.NotEq: TokenType.NEQ,
    ast.Lt: TokenType.LT, ast.Gt: TokenType.GT,
    ast.LtE: TokenType.LTE, ast.GtE: TokenType.GTE,
}

_NAMED_CALL = {
    "len": TokenType.LENGTH,
    "str": TokenType.ENCODE,
    "int": TokenType.DECODE,
}
```

```python
    def expression(self, node: ast.expr) -> Expr:
        if isinstance(node, ast.Constant):
            return self._constant(node)
        if isinstance(node, ast.Name):
            return Name(node.id)
        if isinstance(node, ast.BinOp):
            op = _BINOP.get(type(node.op))
            if op is None:
                raise _Unsupported(self._no(node.op))
            return Binary(self.expression(node.left), op, self.expression(node.right))
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.USub):
                return Unary(TokenType.MINUS, self.expression(node.operand))
            if isinstance(node.op, ast.Not):
                return Unary(TokenType.UNPLUG, self.expression(node.operand))
            raise _Unsupported(self._no(node.op))
        if isinstance(node, ast.BoolOp):
            op = TokenType.SPLICE if isinstance(node.op, ast.And) else TokenType.FORK
            result = self.expression(node.values[0])
            for value in node.values[1:]:
                result = Binary(result, op, self.expression(value))
            return result
        if isinstance(node, ast.Compare):
            return self._compare(node)
        if isinstance(node, ast.List):
            return ListLiteral([self.expression(e) for e in node.elts])
        if isinstance(node, ast.Dict):
            return self._dict(node)
        if isinstance(node, ast.Subscript):
            if not isinstance(node.slice, ast.expr) or isinstance(node.slice, ast.Slice):
                raise _Unsupported(
                    self._no(node, "MatrixLang has no slicing; copy with a `dejavu` loop")
                )
            return Index(self.expression(node.value), self.expression(node.slice))
        if isinstance(node, ast.Call):
            return self._call(node)
        raise _Unsupported(self._no(node))
```

```python
    def _constant(self, node: ast.Constant) -> Expr:
        value = node.value
        if value is True or value is False:
            return BoolLiteral(value)
        if value is None:
            raise _Unsupported(
                self._no(node, "MatrixLang has no null; use a value your program can test")
            )
        if isinstance(value, float):
            raise _Unsupported(
                self._no(node, "MatrixLang has no floats; use whole numbers")
            )
        if isinstance(value, int):
            return NumberLiteral(value)
        if isinstance(value, str):
            return StringLiteral(value)
        raise _Unsupported(self._no(node))

    def _compare(self, node: ast.Compare) -> Expr:
        if len(node.ops) != 1:
            raise _Unsupported(
                self._no(node, "split the chain with `and`")
            )
        op, right = node.ops[0], node.comparators[0]
        if isinstance(op, ast.In):
            # Only a dictionary. `in` over a list or a string has no
            # MatrixLang form -- oracle asks a dictionary for a key.
            return Binary(
                self.expression(right), TokenType.ORACLE, self.expression(node.left)
            )
        mapped = _COMPARE.get(type(op))
        if mapped is None:
            raise _Unsupported(self._no(op))
        return Binary(self.expression(node.left), mapped, self.expression(right))

    def _dict(self, node: ast.Dict) -> Expr:
        entries = []
        for key, value in zip(node.keys, node.values):
            if key is None:
                raise _Unsupported(self._no(node))
            entries.append((self.expression(key), self.expression(value)))
        return DictLiteral(entries)

    def _call(self, node: ast.Call) -> Expr:
        if node.keywords:
            raise _Unsupported(
                self._no(node, "MatrixLang agents take positional arguments only")
            )
        if isinstance(node.func, ast.Name) and node.func.id in _NAMED_CALL:
            if len(node.args) != 1:
                raise _Unsupported(self._no(node))
            return Unary(_NAMED_CALL[node.func.id], self.expression(node.args[0]))
        if not isinstance(node.func, ast.Name):
            raise _Unsupported(self._no(node))
        return Call(Name(node.func.id), [self.expression(a) for a in node.args])
```

**`in` reverses its operands.** Python writes `key in d`, MatrixLang writes `d oracle key`. The `Compare` node's `left` is the key and its comparator is the dictionary.

**A refusal for `is`, tuples and `Slice`** falls out of the final `raise _Unsupported(self._no(node))` in `expression`, which names the ast class. Add entries to `_DESCRIBE` and `_IDIOM` for `Tuple`, `Set`, `Slice`, `Is`, `IsNot`, `In`, `NotIn` so the messages read in the reader's words rather than Python's.

- [ ] **Step 4: Implement `print` and the expression-statement rule**

Replace `_Translator.statement`'s body:

```python
    def statement(self, node: ast.stmt) -> list[Stmt]:
        if isinstance(node, ast.Expr):
            return self._expression_statement(node)
        raise _Unsupported(self._no(node))

    def _expression_statement(self, node: ast.Expr) -> list[Stmt]:
        call = node.value
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
            if call.func.id == "print":
                if len(call.args) != 1 or call.keywords:
                    raise _Unsupported(
                        self._no(
                            node,
                            'print one value at a time: `print(a)` then `print(b)`, '
                            'or join them with `+`',
                        )
                    )
                return [Trace(self.expression(call.args[0]))]
            return [ExprStmt(self.expression(call))]
        raise _Unsupported(
            self._no(
                node,
                "MatrixLang runs a statement only when it is a call — "
                "assign the value to a name if you meant to keep it",
            )
        )
```

Import `ExprStmt` alongside the other nodes.

- [ ] **Step 5: Run the tests**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_pytrans_expr.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/matrixlang/pytrans/translate.py tests/test_pytrans_expr.py
git commit -m "feat: translate Python expressions and print"
```

---

### Task 3: Binding — `construct` versus assignment

**Files:**
- Modify: `src/matrixlang/pytrans/translate.py`
- Create: `tests/test_pytrans_stmt.py`

**Interfaces:**
- Consumes: `_Translator.expression` from Task 2.
- Produces: a scope stack on `_Translator`; assignment, `+=`, `xs[i] = v`, `xs.append(v)`.

**The distinction Python does not make.** MatrixLang declares with `construct x = v` and assigns with `x = v`, and re-declaring an existing name is an error. Python's `x = v` is both. So the translator tracks which names a scope has already bound and emits `construct` only the first time.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_pytrans_stmt.py` with the `ml`/`refused` helpers, then:

```python
def test_a_first_binding_uses_construct():
    assert ml("x = 1\n") == "construct x = 1\n"


def test_a_later_binding_is_a_plain_assignment():
    assert ml("x = 1\nx = 2\n") == "construct x = 1\nx = 2\n"


def test_augmented_assignment_expands():
    assert ml("x = 1\nx += 2\n") == "construct x = 1\nx = x + 2\n"


def test_augmented_assignment_before_any_binding_is_refused():
    assert "before changing it" in refused("x += 1\n")[0].idiom


def test_index_assignment():
    assert ml("xs = [1]\nxs[0] = 9\n") == "construct xs = [1]\nxs[0] = 9\n"


def test_dictionary_key_assignment():
    assert ml('d = {}\nd["a"] = 1\n') == 'construct d = {}\nd["a"] = 1\n'


def test_append_becomes_concatenation():
    assert ml("xs = []\nxs.append(1)\n") == "construct xs = []\nxs = xs + [1]\n"


def test_append_inside_an_expression_is_refused():
    assert refused("xs = []\ny = xs.append(1)\n")[0].reason != ""


def test_an_unknown_method_call_is_refused():
    refusal = refused("xs = []\nxs.sort()\n")[0]
    assert "sort" in refusal.reason or "method" in refusal.reason


def test_multiple_assignment_is_refused():
    assert refused("a = b = 0\n")[0].idiom is not None


def test_tuple_unpacking_is_refused():
    assert refused("a, b = 1, 2\n")[0].idiom is not None
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_pytrans_stmt.py -q`
Expected: FAIL — assignment is not handled.

- [ ] **Step 3: Add the scope stack**

In `_Translator.__init__`:

```python
        # One set of bound names per MatrixLang scope. An agent body is its
        # own scope, so a name declared inside one does not collide with the
        # same name outside it. `construct` is emitted the first time a name
        # is bound in the current scope and never again -- re-declaring is an
        # error in MatrixLang and Python draws no such distinction.
        self.scopes: list[set[str]] = [set()]

    def _bind(self, name: str) -> bool:
        """Record a binding. True if this is the first one in this scope."""
        first = name not in self.scopes[-1]
        self.scopes[-1].add(name)
        return first
```

- [ ] **Step 4: Implement the statements**

Add to `statement`'s dispatch, before its final `raise`:

```python
        if isinstance(node, ast.Assign):
            return self._assign(node)
        if isinstance(node, ast.AugAssign):
            return self._aug_assign(node)
```

```python
    def _assign(self, node: ast.Assign) -> list[Stmt]:
        if len(node.targets) != 1:
            raise _Unsupported(
                self._no(node, "assign one name at a time: `a = 0` then `b = 0`")
            )
        target = node.targets[0]
        value = self.expression(node.value)
        if isinstance(target, ast.Name):
            if self._bind(target.id):
                return [Declare(target.id, value)]
            return [Assign(target.id, value)]
        if isinstance(target, ast.Subscript):
            if isinstance(target.slice, ast.Slice):
                raise _Unsupported(self._no(target))
            return [
                IndexAssign(
                    self.expression(target.value),
                    self.expression(target.slice),
                    value,
                )
            ]
        raise _Unsupported(
            self._no(target, "assign to one name or one element at a time")
        )

    def _aug_assign(self, node: ast.AugAssign) -> list[Stmt]:
        op = _BINOP.get(type(node.op))
        if op is None or not isinstance(node.target, ast.Name):
            raise _Unsupported(self._no(node))
        if node.target.id not in self.scopes[-1]:
            raise _Unsupported(
                self._no(
                    node,
                    f"give `{node.target.id}` a value before changing it",
                )
            )
        return [
            Assign(
                node.target.id,
                Binary(Name(node.target.id), op, self.expression(node.value)),
            )
        ]
```

Import `Assign`, `Declare` and `IndexAssign`.

- [ ] **Step 5: Implement `.append`**

In `_expression_statement`, before the `isinstance(call.func, ast.Name)` branch:

```python
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute):
            if call.func.attr != "append" or len(call.args) != 1:
                raise _Unsupported(
                    self._no(
                        node,
                        f"MatrixLang has no `.{call.func.attr}()`; "
                        "the only list method it can translate is `.append()`",
                    )
                )
            if not isinstance(call.func.value, ast.Name):
                raise _Unsupported(self._no(node))
            # Concatenation, not mutation: `+` copies, which is what makes
            # this an assignment rather than a call.
            target = call.func.value.id
            return [
                Assign(
                    target,
                    Binary(
                        Name(target), TokenType.PLUS,
                        ListLiteral([self.expression(call.args[0])]),
                    ),
                )
            ]
```

An `.append()` used as a value rather than a statement falls through `expression`'s `_call`, which refuses any non-`Name` callee.

- [ ] **Step 6: Run the tests**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_pytrans_stmt.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/matrixlang/pytrans/translate.py tests/test_pytrans_stmt.py
git commit -m "feat: translate binding, and tell construct from assignment"
```

---

### Task 4: Control flow and functions

**Files:**
- Modify: `src/matrixlang/pytrans/translate.py`
- Modify: `tests/test_pytrans_stmt.py`

**Interfaces:**
- Consumes: the scope stack and `expression` from Tasks 2 and 3.
- Produces: `if`/`elif`/`else`, `while`, `def`/`return`, and the truthiness refusal.

**`elif` nests.** MatrixLang has no `elif`; the else-branch holds another `redpill`. Verified against the real interpreter.

**The truthiness refusal is the spec's governing case.** A condition that is not already a comparison, a boolean operator, or a boolean literal is refused with the exact rewrites named.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pytrans_stmt.py`:

```python
def test_if_becomes_redpill():
    assert ml("if a == 1:\n    print(a)\n") == "redpill a == 1\n  trace a\nflatline\n"


def test_if_else_becomes_redpill_bluepill():
    source = "if a == 1:\n    print(1)\nelse:\n    print(2)\n"
    assert ml(source) == (
        "redpill a == 1\n  trace 1\nbluepill\n  trace 2\nflatline\n"
    )


def test_elif_nests_inside_the_else():
    source = "if a == 1:\n    print(1)\nelif a == 2:\n    print(2)\n"
    assert ml(source) == (
        "redpill a == 1\n"
        "  trace 1\n"
        "bluepill\n"
        "  redpill a == 2\n"
        "    trace 2\n"
        "  flatline\n"
        "flatline\n"
    )


def test_while_becomes_dejavu():
    source = "n = 0\nwhile n < 3:\n    n += 1\n"
    assert ml(source) == "construct n = 0\ndejavu n < 3\n  n = n + 1\nflatline\n"


def test_a_function_becomes_an_agent():
    source = "def double(x):\n    return x * 2\n"
    assert ml(source) == "agent double(x)\n  jackout x * 2\nflatline\n"


def test_a_bare_return_becomes_a_bare_jackout():
    source = "def f(x):\n    return\n"
    assert ml(source) == "agent f(x)\n  jackout\nflatline\n"


def test_a_function_body_is_its_own_scope():
    # `x` is declared in the agent and again outside it, because MatrixLang
    # gives an agent body its own frame.
    source = "def f():\n    x = 1\n    return x\nx = 2\n"
    assert ml(source) == (
        "agent f()\n  construct x = 1\n  jackout x\nflatline\nconstruct x = 2\n"
    )


def test_truthiness_is_refused_with_both_rewrites():
    refusal = refused("result = f()\nif result:\n    print(1)\n")[0]
    assert "truthiness" in refusal.reason
    assert "len(result) > 0" in refusal.idiom
    assert "result != 0" in refusal.idiom


def test_a_comparison_condition_is_not_refused():
    assert ml("if a == 1:\n    print(1)\n").startswith("redpill a == 1")


def test_a_boolean_operator_condition_is_not_refused():
    assert ml("if a == 1 and b == 2:\n    print(1)\n").startswith("redpill")


def test_a_not_condition_is_not_refused():
    assert ml("if not a == 1:\n    print(1)\n").startswith("redpill unplug")


def test_a_while_with_a_truthy_condition_is_refused():
    assert "truthiness" in refused("while xs:\n    print(1)\n")[0].reason


def test_default_arguments_are_refused():
    assert "positional" in refused("def f(a=1):\n    return a\n")[0].idiom
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_pytrans_stmt.py -q -k "redpill or dejavu or agent or truthiness or elif or scope or default"`
Expected: FAIL.

- [ ] **Step 3: Implement the condition guard**

```python
    def condition(self, node: ast.expr) -> Expr:
        """A condition, refusing anything that leans on truthiness.

        MatrixLang's `redpill` takes a boolean and nothing else -- an empty
        list is not false, and 0 is not false. Python's `if xs:` means four
        different things depending on a runtime type, and choosing between
        them would mean inferring that type and sometimes guessing wrong.
        A program that runs and means something slightly different is the
        one outcome worth engineering against, so this refuses instead.
        """
        if isinstance(node, (ast.Compare, ast.BoolOp)):
            return self.expression(node)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return self.expression(node)
        if isinstance(node, ast.Constant) and node.value in (True, False):
            return self.expression(node)
        shown = ast.unparse(node)
        raise _Unsupported(
            Refusal(
                f"`{shown}` relies on truthiness, which MatrixLang does not "
                "have — a condition must already be a boolean",
                node.lineno,
                node.col_offset,
                f"a list or string →  len({shown}) > 0\n"
                f"a number        →  {shown} != 0",
            )
        )
```

- [ ] **Step 4: Implement the statements**

Add to `statement`'s dispatch:

```python
        if isinstance(node, ast.If):
            return [
                If(
                    self.condition(node.test),
                    self.body(node.body),
                    self.body(node.orelse) if node.orelse else None,
                )
            ]
        if isinstance(node, ast.While):
            if node.orelse:
                raise _Unsupported(self._no(node, "MatrixLang has no `while ... else`"))
            return [While(self.condition(node.test), self.body(node.body))]
        if isinstance(node, ast.FunctionDef):
            return self._function(node)
        if isinstance(node, ast.Return):
            return [Return(self.expression(node.value) if node.value else None)]
```

`elif` needs no special case: Python already represents it as an `If` inside `orelse`, which is exactly the nesting MatrixLang wants.

```python
    def _function(self, node: ast.FunctionDef) -> list[Stmt]:
        args = node.args
        if (
            args.defaults or args.kw_defaults or args.vararg or args.kwarg
            or args.posonlyargs or args.kwonlyargs
        ):
            raise _Unsupported(
                self._no(node, "MatrixLang agents take plain positional parameters")
            )
        if node.decorator_list:
            raise _Unsupported(self._no(node, "MatrixLang has no decorators"))
        names = [a.arg for a in args.args]
        # An agent body is its own frame, so it gets its own scope, seeded
        # with the parameters -- they are bound on entry and must not be
        # re-declared inside.
        self.scopes.append(set(names))
        body = self.body(node.body)
        self.scopes.pop()
        self._bind(node.name)
        return [FunctionDef(node.name, names, body)]
```

Import `FunctionDef`, `If`, `Return`, `While`.

`FunctionDef`'s fields are `name: str`, `params: list[str]`, `body: list[Stmt]`
(`src/matrixlang/nodes.py:167`), verified — the positional call above matches.
`Return`'s single field is `value: Expr | None = None`, so a bare `Return()` is
`jackout` with no value.

- [ ] **Step 5: Run the tests**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_pytrans_stmt.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/matrixlang/pytrans/translate.py tests/test_pytrans_stmt.py
git commit -m "feat: translate control flow and agents, refusing truthiness"
```

---

### Task 5: The `for` loop

**Files:**
- Create: `src/matrixlang/pytrans/names.py`
- Modify: `src/matrixlang/pytrans/translate.py`
- Create: `tests/test_pytrans_loops.py`

**Interfaces:**
- Consumes: everything above.
- Produces: `free_name(bound: set[str], stem: str) -> str`; `for` translation; hoisting.

**Three rules, and one of them is a correctness hazard.**

**(a) The iterable is evaluated once.** `for s in find_students(a, b):` substituted inline would call `find_students` on **every iteration** — a different program from the one written. So when the iterable is not already a plain name, it is hoisted into a generated name before the loop and the substitution uses that.

**(b) The loop variable is substituted, not declared.** Every use of `s` in the body becomes `xs[n]`. Declaring it inside the body would hit the language quirk in (c); declaring it outside would need a placeholder the reader never wrote. A body that **reassigns** the loop variable is refused, because substitution cannot express that.

**(c) A name first bound inside a loop has its `construct` hoisted above the loop, initialised to `0`.** `construct` inside a loop body fails on the second iteration with `'x' is already declared`. `0` is safe: MatrixLang assignment may change a value's type, verified against the real interpreter.

- [ ] **Step 1: Write `names.py` and its test**

```python
"""Names the translator has to invent, and how they avoid the reader's.

A `for` loop needs a counter, and an iterable that is not already a name
needs somewhere to live. Both are names the reader never wrote, so both
must be guaranteed not to collide with one they did.
"""

import ast


def bound_names(tree: ast.AST) -> set[str]:
    """Every name the Python program binds, anywhere.

    Deliberately over-inclusive: it counts targets inside constructs that
    will be refused anyway. A name that turns out not to exist costs one
    counter suffix; a name that is missed collides with the reader's.
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.arg):
            found.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found.add(node.name)
    return found


def free_name(bound: set[str], stem: str = "n") -> str:
    """The first of `n`, `n1`, `n2`, ... that nothing else uses.

    The caller adds the result to `bound` before asking again, so nested
    loops get different counters.
    """
    if stem not in bound:
        return stem
    index = 1
    while f"{stem}{index}" in bound:
        index += 1
    return f"{stem}{index}"
```

Create `tests/test_pytrans_loops.py` with the `ml`/`refused` helpers plus:

```python
import ast

from matrixlang.pytrans.names import bound_names, free_name


def test_free_name_avoids_a_taken_stem():
    assert free_name({"n"}) == "n1"
    assert free_name({"n", "n1", "n2"}) == "n3"
    assert free_name(set()) == "n"


def test_bound_names_sees_parameters_and_function_names():
    tree = ast.parse("def f(a, b):\n    c = 1\n")
    assert {"f", "a", "b", "c"} <= bound_names(tree)
```

- [ ] **Step 2: Write the failing loop tests**

Append to `tests/test_pytrans_loops.py`:

```python
def test_a_for_loop_substitutes_the_index_inline():
    source = "xs = [1]\nfor x in xs:\n    print(x)\n"
    assert ml(source) == (
        "construct xs = [1]\n"
        "construct n = 0\n"
        "dejavu n < length xs\n"
        "  trace xs[n]\n"
        "  n = n + 1\n"
        "flatline\n"
    )


def test_the_counter_avoids_a_name_the_reader_used():
    source = "n = 5\nxs = [1]\nfor x in xs:\n    print(x)\n"
    assert "construct n1 = 0" in ml(source)
    assert "dejavu n1 < length xs" in ml(source)


def test_nested_loops_get_different_counters():
    source = "xs = [1]\nfor a in xs:\n    for b in xs:\n        print(b)\n"
    out = ml(source)
    assert "construct n = 0" in out and "construct n1 = 0" in out


def test_a_non_name_iterable_is_evaluated_once():
    # Substituting `f(1)[n]` inline would call f on every iteration -- a
    # different program from the one written.
    source = "for x in f(1):\n    print(x)\n"
    out = ml(source)
    assert "construct xs = f(1)\n" in out
    assert "f(1)[" not in out


def test_range_uses_the_counter_itself():
    source = "for i in range(3):\n    print(i)\n"
    assert ml(source) == (
        "construct n = 0\ndejavu n < 3\n  trace n\n  n = n + 1\nflatline\n"
    )


def test_range_with_a_start():
    source = "for i in range(2, 5):\n    print(i)\n"
    assert ml(source) == (
        "construct n = 2\ndejavu n < 5\n  trace n\n  n = n + 1\nflatline\n"
    )


def test_range_with_a_step_is_refused():
    assert "step" in refused("for i in range(0, 10, 2):\n    print(i)\n")[0].idiom


def test_reassigning_the_loop_variable_is_refused():
    source = "xs = [1]\nfor x in xs:\n    x = 2\n"
    assert "reassigns `x`" in refused(source)[0].reason


def test_a_name_first_bound_inside_a_loop_is_hoisted():
    # `construct` inside a loop body fails on iteration 2, so the
    # declaration moves above the loop with a placeholder.
    source = "xs = [1]\nfor x in xs:\n    total = x\n"
    out = ml(source)
    assert out.index("construct total = 0") < out.index("dejavu")
    assert "  total = xs[n]" in out


def test_for_else_is_refused():
    source = "xs = [1]\nfor x in xs:\n    print(x)\nelse:\n    print(2)\n"
    assert "for ... else" in refused(source)[0].idiom
```

- [ ] **Step 3: Run them to verify they fail**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_pytrans_loops.py -q`
Expected: FAIL — `for` is not handled.

- [ ] **Step 4: Wire the name allocator in**

In `translate()`, after parsing, seed the walker:

```python
    walker = _Translator(bound_names(tree))
```

In `__init__`:

```python
    def __init__(self, taken: set[str] | None = None) -> None:
        self.refusals: list[Refusal] = []
        self.scopes: list[set[str]] = [set()]
        self.taken: set[str] = set(taken or ())
        self.substitutions: dict[str, Expr] = {}

    def _fresh(self, stem: str = "n") -> str:
        name = free_name(self.taken, stem)
        self.taken.add(name)
        return name
```

In `expression`, the `ast.Name` branch consults substitutions first:

```python
        if isinstance(node, ast.Name):
            replacement = self.substitutions.get(node.id)
            if replacement is not None:
                # Shared, not copied: rendering never mutates a node, and
                # line/column do not take part in equality.
                return replacement
            return Name(node.id)
```

- [ ] **Step 5: Implement the loop**

```python
    def _for(self, node: ast.For) -> list[Stmt]:
        if node.orelse:
            raise _Unsupported(self._no(node, "MatrixLang has no `for ... else`"))
        if not isinstance(node.target, ast.Name):
            raise _Unsupported(
                self._no(node.target, "loop over one name at a time")
            )
        if _rebinds(node.body, node.target.id):
            raise _Unsupported(
                self._no(
                    node,
                    f"the loop reassigns `{node.target.id}`; copy it to another "
                    "name first",
                )
            )

        before: list[Stmt] = []
        counter = self._fresh()

        start, stop = self._range_bounds(node.iter)
        if stop is not None:
            # `for i in range(...)`: the counter IS the value.
            self.substitutions[node.target.id] = Name(counter)
            before.append(Declare(counter, start))
            condition = Binary(Name(counter), TokenType.LT, stop)
        else:
            source = node.iter
            if isinstance(source, ast.Name):
                holder = source.id
            else:
                # Evaluated once. Substituting a call inline would run it
                # on every iteration -- a different program.
                holder = self._fresh("xs")
                before.append(Declare(holder, self.expression(source)))
            self.substitutions[node.target.id] = Index(Name(holder), Name(counter))
            before.append(Declare(counter, NumberLiteral(0)))
            condition = Binary(
                Name(counter), TokenType.LT, Unary(TokenType.LENGTH, Name(holder))
            )

        outer = set(self.scopes[-1])
        body = self.body(node.body)
        # Anything the body declared for the first time must be declared
        # ABOVE the loop instead: `construct` inside a loop body fails on
        # the second iteration. 0 is a safe placeholder because assignment
        # may change a value's type.
        hoisted = sorted(self.scopes[-1] - outer)
        body = [_as_assignment(s) for s in body]
        before.extend(Declare(name, NumberLiteral(0)) for name in hoisted)

        del self.substitutions[node.target.id]
        body.append(
            Assign(counter, Binary(Name(counter), TokenType.PLUS, NumberLiteral(1)))
        )
        return before + [While(condition, body)]

    def _range_bounds(self, node: ast.expr) -> tuple[Expr, Expr | None]:
        """(start, stop) for a `range(...)` iterable, or (0, None) otherwise."""
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "range"
        ):
            return NumberLiteral(0), None
        if len(node.args) == 1:
            return NumberLiteral(0), self.expression(node.args[0])
        if len(node.args) == 2:
            return self.expression(node.args[0]), self.expression(node.args[1])
        raise _Unsupported(
            self._no(node, "count with a `dejavu` loop and your own step")
        )
```

Two module-level helpers:

```python
def _rebinds(body: list[ast.stmt], name: str) -> bool:
    """Does this block assign to `name`? Substitution cannot express that."""
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            if node.id == name:
                return True
        if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            if node.target.id == name:
                return True
    return False


def _as_assignment(statement: Stmt) -> Stmt:
    """A Declare becomes an Assign; everything else is unchanged.

    Paired with hoisting the Declare above the loop -- together they turn
    a first binding inside a loop body into a declaration outside it and a
    plain assignment inside, which is the only shape MatrixLang accepts.
    """
    if isinstance(statement, Declare):
        return Assign(statement.name, statement.value)
    return statement
```

Add `if isinstance(node, ast.For): return self._for(node)` to `statement`'s dispatch, and import `bound_names`, `free_name` from `matrixlang.pytrans.names`.

`Declare` and `Assign` both carry exactly `name: str` and `value: Expr`
(`src/matrixlang/nodes.py:118-128`), verified — which is what makes
`_as_assignment` a one-line rewrite rather than a reconstruction.

- [ ] **Step 6: Run the tests**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_pytrans_loops.py -q`
Expected: PASS.

- [ ] **Step 7: Run the whole suite and commit**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest -q`

```bash
git add src/matrixlang/pytrans tests/test_pytrans_loops.py
git commit -m "feat: translate for loops, evaluating the iterable once"
```

---

### Task 6: `input()` and f-strings

**Files:**
- Modify: `src/matrixlang/pytrans/translate.py`
- Modify: `tests/test_pytrans_stmt.py`

**Interfaces:**
- Consumes: everything above.

**`input("prompt")` becomes two statements** — `trace "prompt"` then a binding to `jackin` — and only when it is the entire right-hand side of an assignment. Nested inside a larger expression it is refused, because one expression cannot become two statements mid-expression.

**An f-string becomes a `+` chain with `encode` around every interpolation.** `encode` takes a number, so interpolating a string will fail loudly at runtime with a position — which the governing rule permits, unlike a silent difference. Conversions and format specs are refused.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_pytrans_stmt.py`:

```python
def test_input_with_a_prompt_becomes_two_statements():
    source = 'name = input("Name: ")\n'
    assert ml(source) == 'trace "Name: "\nconstruct name = jackin\n'


def test_input_without_a_prompt_is_one_statement():
    assert ml("name = input()\n") == "construct name = jackin\n"


def test_input_nested_in_an_expression_is_refused():
    refusal = refused('n = int(input("n: "))\n')[0]
    assert refusal.idiom is not None


def test_an_fstring_becomes_a_concatenation():
    assert ml('print(f"id: {n}")\n') == 'trace "id: " + encode n\n'


def test_an_fstring_with_text_on_both_sides():
    assert ml('print(f"a{n}b")\n') == 'trace "a" + encode n + "b"\n'


def test_an_fstring_with_no_interpolation_is_just_a_string():
    assert ml('print(f"plain")\n') == 'trace "plain"\n'


def test_an_fstring_conversion_is_refused():
    assert "formatting" in refused('print(f"{n!r}")\n')[0].idiom


def test_an_fstring_format_spec_is_refused():
    assert "formatting" in refused('print(f"{n:>3}")\n')[0].idiom
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_pytrans_stmt.py -q -k "input or fstring"`
Expected: FAIL.

- [ ] **Step 3: Implement `input()`**

In `_assign`, before computing `value`:

```python
        prelude: list[Stmt] = []
        source = node.value
        if _is_input_call(source):
            if source.args:
                if len(source.args) != 1:
                    raise _Unsupported(self._no(source))
                prelude.append(Trace(self.expression(source.args[0])))
            value: Expr = JackIn()
        else:
            value = self.expression(source)
```

and return `prelude + [...]` from each branch. A module-level helper:

```python
def _is_input_call(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "input"
    )
```

In `expression`'s `_call`, refuse `input` wherever it appears, since reaching there means it was not a whole right-hand side:

```python
        if isinstance(node.func, ast.Name) and node.func.id == "input":
            raise _Unsupported(
                self._no(
                    node,
                    "read the line into its own name first: "
                    "`answer = input(...)`, then use `answer`",
                )
            )
```

Import `JackIn`.

- [ ] **Step 4: Implement f-strings**

In `expression`, before the final raise:

```python
        if isinstance(node, ast.JoinedStr):
            return self._fstring(node)
```

```python
    def _fstring(self, node: ast.JoinedStr) -> Expr:
        """An f-string as a `+` chain, with `encode` around each hole.

        `encode` takes a number, so interpolating a string fails loudly at
        runtime with a line and column. That is allowed where a silent
        difference would not be: the reader sees the error and fixes it,
        rather than getting a program that quietly means something else.
        """
        parts: list[Expr] = []
        for piece in node.values:
            if isinstance(piece, ast.Constant):
                if piece.value:
                    parts.append(StringLiteral(piece.value))
            elif isinstance(piece, ast.FormattedValue):
                if piece.conversion != -1 or piece.format_spec is not None:
                    raise _Unsupported(
                        self._no(
                            piece,
                            "MatrixLang has no formatting; build the text with `+`",
                        )
                    )
                parts.append(Unary(TokenType.ENCODE, self.expression(piece.value)))
            else:
                raise _Unsupported(self._no(node))
        if not parts:
            return StringLiteral("")
        result = parts[0]
        for part in parts[1:]:
            result = Binary(result, TokenType.PLUS, part)
        return result
```

- [ ] **Step 5: Run the tests and commit**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest -q`

```bash
git add src/matrixlang/pytrans/translate.py tests/test_pytrans_stmt.py
git commit -m "feat: translate input and f-strings"
```

---

### Task 7: The glue and the page

**Files:**
- Modify: `site/glue.py`
- Modify: `site/index.html:126-140`, `site/style.css`, `site/playground.js`
- Modify: `site/tests/dom.mjs`, `site/tests/playground.test.mjs`, `tests/test_site_glue.py`

**Interfaces:**
- Produces: `glue.translate_python(source: str) -> dict`.

**The browser gains no language logic.** JS calls Python and sets `editor.value`, exactly as `writeProgram()` already does. `site/checks/no_semantics.py` must pass **unmodified**.

- [ ] **Step 1: Write the failing glue test**

Append to `tests/test_site_glue.py`:

```python
def test_translate_python_returns_a_program():
    result = glue.translate_python("print(1)\n")
    assert result == {"ok": True, "source": "trace 1\n"}


def test_translate_python_returns_refusals_with_positions():
    result = glue.translate_python("import os\n")
    assert result["ok"] is False
    assert result["refusals"][0]["line"] == 1


def test_translate_python_never_raises_on_invalid_python():
    result = glue.translate_python("def (:\n")
    assert result["ok"] is False
```

- [ ] **Step 2: Implement it**

In `site/glue.py`, after `write()`:

```python
def translate_python(source: str) -> dict:
    """Ask the translator for a program. Never raises.

    The wire shape mirrors `write()`: a flag plus either source or the
    reasons it could not be produced. Refusals come back as a list because
    the translator collects every one -- a reader fixing a long program
    should see all of it at once.
    """
    result = translate(source)
    if isinstance(result, Translated):
        return {"ok": True, "source": result.source}
    return {
        "ok": False,
        "refusals": [
            {
                "reason": r.reason,
                "line": r.line,
                "column": r.column,
                "idiom": r.idiom or "",
            }
            for r in result.items
        ],
    }
```

Import `translate`, `Translated` from `matrixlang.pytrans` at the top of `glue.py`.

- [ ] **Step 3: Add the markup**

In `site/index.html`, after the `#miss` paragraph and before the `MatrixLang` label:

```html
          <details id="python-panel">
            <summary>Or paste Python</summary>
            <textarea id="python-source" rows="10" spellcheck="false"
                      placeholder="for x in xs:&#10;    print(x)"></textarea>
            <button id="translate">Translate it</button>
          </details>
```

Collapsed by default, so the pane looks unchanged until opened.

Add `"python-source"` and `"translate"` to `GATED_CONTROL_IDS` in `playground.js`, and to whatever id list `site/tests/dom.mjs` maintains.

- [ ] **Step 4: Add the JS**

```javascript
function translatePython() {
  const result = glue
    .translate_python(el("python-source").value)
    .toJs({ dict_converter: Object.fromEntries });
  const miss = el("miss");
  if (result.ok) {
    el("editor").value = result.source;
    withdrawEditorFace();
    miss.hidden = true;
    return;
  }
  // Every refusal at once. A reader fixing a long program should not have
  // to discover its problems one press at a time.
  miss.textContent = result.refusals
    .map((r) => `line ${r.line}: ${r.reason}${r.idiom ? ` — ${r.idiom}` : ""}`)
    .join("\n");
  miss.hidden = false;
}
```

Wire it: `el("translate").addEventListener("click", translatePython);`

- [ ] **Step 5: Add the CSS**

In `site/style.css`, beside the other editor-pane rules:

```css
/* Collapsed by default: the pane already carries Scribe, an editor and an
   input box, and a reader who does not write Python should not pay for it
   in vertical space. */
#python-panel summary { cursor: pointer; }
#python-source { width: 100%; }
```

- [ ] **Step 6: Add a JS test**

In `site/tests/playground.test.mjs`, following the file's existing stub-`glue` pattern, assert that a successful translation sets `editor.value` and that refusals are all rendered into `#miss`.

- [ ] **Step 7: Verify and commit**

```
PYTHONPATH="$PWD/src:$PWD" python3 -m pytest -q
node --test site/tests/*.test.mjs
python3 site/checks/no_semantics.py
python3 site/checks/key_handling.py
```

All must pass, and `site/checks/` must be unmodified.

```bash
git add site tests/test_site_glue.py
git commit -m "feat: a Python box in the editor pane"
```

---

### Task 8: Differential tests and the tutorial

**Files:**
- Create: `tests/test_pytrans_differential.py`
- Modify: `docs/LEARNING-MATRIXLANG.md`

**Why this task carries the weight.** Every other test proves the translator produced *some* MatrixLang. These prove it produced MatrixLang that **means the same thing** — by running both and comparing. An output that parses and runs but computes something different is the failure this whole design is arranged against, and this is the only test shape that catches it.

- [ ] **Step 1: Write the harness**

Create `tests/test_pytrans_differential.py`:

```python
"""Translate, run both, compare.

The only tests here that can catch an output which parses, runs, and
means something other than the Python did.
"""

import io
from contextlib import redirect_stdout

from matrixlang.interpreter import Interpreter
from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.pytrans import Translated, translate


def both(python_source, stdin_lines=()):
    """(what Python printed, what the MatrixLang printed)."""
    from matrixlang.input import ListSource

    python_out = io.StringIO()
    supply = iter(stdin_lines)
    namespace = {"input": lambda *a: next(supply)}
    with redirect_stdout(python_out):
        exec(compile(python_source, "<differential>", "exec"), namespace)

    result = translate(python_source)
    assert isinstance(result, Translated), result.items
    ml_out = io.StringIO()
    Interpreter(out=ml_out, source=ListSource(list(stdin_lines))).run(
        parse(lex(result.source))
    )
    return python_out.getvalue(), ml_out.getvalue()


def agree(python_source, stdin_lines=()):
    left, right = both(python_source, stdin_lines)
    assert left == right, f"python={left!r} matrixlang={right!r}"
```

**Note on the `input` shim:** Python's `input()` echoes nothing but consumes a line; MatrixLang's `jackin` does the same. The prompt is printed by a separate `trace` in the translation, and by `input`'s own argument in Python — which `print`s to stdout only in interactive use, not under `redirect_stdout`. So the shim must **not** print the prompt; the translated `trace` supplies it, and the Python side needs the same text. Handle this by having the shim print its prompt argument: `lambda p="": (print(p, end=""), next(supply))[1]`. Verify the two agree on a program with a prompt before trusting the rest.

- [ ] **Step 2: Write the cases**

```python
def test_arithmetic_and_printing_agree():
    agree("x = 2\nprint(x * 3 + 1)\n")


def test_a_while_loop_agrees():
    agree("n = 0\nwhile n < 3:\n    print(n)\n    n += 1\n")


def test_a_for_loop_over_a_list_agrees():
    agree("xs = [1, 2, 3]\nfor x in xs:\n    print(x)\n")


def test_a_for_loop_over_range_agrees():
    agree("for i in range(3):\n    print(i)\n")


def test_an_agent_agrees():
    agree("def double(x):\n    return x * 2\n\nprint(double(21))\n")


def test_if_elif_else_agrees():
    agree(
        "g = 'B'\n"
        "if g == 'A':\n    print('top')\n"
        "elif g == 'B':\n    print('middle')\n"
        "else:\n    print('other')\n"
    )


def test_a_dictionary_agrees():
    agree('d = {"a": 1, "b": 2}\nprint(d["a"])\nprint(len(d))\n')


def test_building_a_list_in_a_loop_agrees():
    agree(
        "out = []\n"
        "for i in range(4):\n"
        "    out = out + [i * 2]\n"
        "print(len(out))\n"
        "for v in out:\n    print(v)\n"
    )


def test_the_students_search_program_agrees():
    # The program that motivated dictionaries, with the one line the
    # translator's own truthiness refusal instructs the reader to change.
    agree(
        'students_data = [\n'
        '    {"id": 1, "grade": "A"},\n'
        '    {"id": 2, "grade": "B"},\n'
        '    {"id": 3, "grade": "A"},\n'
        ']\n'
        'user_search = input("Digite a nota(A, B, C): ")\n'
        '\n'
        'def find_students(students_data, search_student):\n'
        '    found = []\n'
        '    for students in students_data:\n'
        '        if search_student == str(students["id"]) '
        'or search_student == students["grade"]:\n'
        '            found = found + [students]\n'
        '    return found\n'
        '\n'
        'result = find_students(students_data, user_search)\n'
        'if len(result) > 0:\n'
        '    print("Encontrado esses ID que dao match:")\n'
        '    for student in result:\n'
        '        print("-ID: " + str(student["id"]))\n'
        'else:\n'
        '    print("match nao valido")\n',
        stdin_lines=["A"],
    )
```

- [ ] **Step 3: Run them**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_pytrans_differential.py -q`
Expected: PASS. **A failure here is a real translation bug**, not a test problem — read the reported `python=... matrixlang=...` and fix the translator, not the test.

- [ ] **Step 4: Write the tutorial section**

Add a section to `docs/LEARNING-MATRIXLANG.md` after the dictionaries section, in the file's existing register. Cover: what the translator does, the subset it accepts, the governing rule (syntax not types), why truthiness is refused, and the three rewrites — with the hoisted `construct` called out, because it is the one thing in the output the reader did not write.

**Run every snippet through the interpreter and paste the observed output.** Tutorial snippets are prose, not tests, and rot silently — this has already bitten this project once.

- [ ] **Step 5: Run everything and commit**

```
PYTHONPATH="$PWD/src:$PWD" python3 -m pytest -q
node --test site/tests/*.test.mjs
python3 site/checks/no_semantics.py && python3 site/checks/key_handling.py
```

```bash
git add tests/test_pytrans_differential.py docs/LEARNING-MATRIXLANG.md
git commit -m "test: prove the translation means what the Python meant"
```

---

## Self-review notes

**Spec coverage.** Never-raises and collected refusals (T1); the Translated table's expressions and `print` (T2); binding, `+=`, index assign, `append` (T3); control flow, functions, the truthiness refusal (T4); the three rewrites — `for` with one-time iterable evaluation, hoisting, counter naming (T5); `input()` and f-strings (T6); glue and the page (T7); differential tests and the tutorial (T8). Every "Refused" item in the spec has a test in T2–T6.

**Out of scope, per the spec** and absent from every task: a CLI subcommand, type inference of any kind, dry-running the output, Scribe integration.

**Naming consistency.** `Translated.source`, `Refusal.reason/line/column/idiom`, `Refusals.items`, `_Translator.expression/condition/statement/body`, `free_name`, `bound_names` are used identically wherever they appear.

**Node field names were verified against `nodes.py`, not guessed:** `Declare` and
`Assign` are `(name: str, value: Expr)`, `FunctionDef` is
`(name, params, body)`, `Return.value` defaults to `None`. Confident-but-wrong
details of exactly this kind have cost this project fix rounds before, so they
were checked rather than written from memory.

**One thing the plan cannot settle in advance,** flagged in T8 Step 1: the
differential harness's `input` shim has to print its prompt so the Python side
emits the same text the translated `trace` does. The note says to verify that on
a prompted program before trusting the rest of the file. If the two disagree,
the harness is wrong — fix the shim, not the translator.
