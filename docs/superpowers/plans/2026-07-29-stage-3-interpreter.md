# Stage 3 — Interpreter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Walk the Stage 2 syntax tree and execute it — variables, arithmetic, conditionals, loops — behind `matrixlang run` and an interactive REPL. At the end of this stage the language exists.

**Architecture:** A tree-walking interpreter. `Interpreter` holds one flat `dict[str, object]` environment and dispatches on node type, mirroring the shape `treeview.py` already established. Output goes through an injected writer so tests capture it without touching stdout. `values.py` owns the type rules — one module, because Python's `bool`-is-an-`int` inheritance makes every type check a trap and centralising them is the only way to be sure. `RuntimeErrorML` joins the existing error hierarchy, sourcing line and column from AST nodes. The REPL buffers input until open blocks close, so a loop can be typed at the prompt.

**Tech Stack:** Python ≥3.11, standard library only. pytest as the sole dev dependency.

## Global Constraints

- **Standard library only** in `src/matrixlang/`. pytest is a dev dependency and must never be imported by shipped code.
- **Every error reports line and column**, both 1-indexed, via the shared `MatrixLangError` hierarchy.
- **NEVER use `isinstance` for MatrixLang value type checks. Use `type(v) is int` / `type(v) is bool` / `type(v) is str`.** In Python `bool` subclasses `int`, so `isinstance(True, int)` is `True` and `True + 1` is `2`. Spec §5 forbids coercion, so `true + 1` must be a runtime error — with `isinstance` that error never fires and the interpreter silently returns `2`. This is the Stage 3 analogue of Stage 1's `str.isdigit()` ban. `isinstance` on **AST node** types is correct and expected; the ban is on value type checks only.
- **Integer division truncates toward zero, not floor.** Python's `//` floors: `-7 // 2 == -4`. The spec requires `-3`. Never use `//` or `math.floor`.
- **The interpreter never imports the lexer, the parser, or the CLI.** It consumes a `Program` node. Dependency direction: `values → errors`, `interpreter → {nodes, tokens, errors, values}`, `repl → {interpreter, lexer, parser, errors}`, `cli → {interpreter, repl, lexer, parser, treeview, errors}`. `tests/test_architecture.py` enforces this — extend its `_ALLOWED` table as you add modules.
- **One flat environment.** A single `dict`. Blocks do not introduce scope (spec §5; functions and closures are deferred).
- **Tests are written before implementation, in every task.**
- **Commit at the end of every task.**

**Reference:** `docs/superpowers/specs/SPEC-matrixlang-language-surface.md` §5 (semantics — twelve rules, all binding). Parent spec Stage 3 done-when: *"a counting loop runs correctly. At this point the language exists."* That is Task 6's headline test.

**Environment note for every task:** run tests with `.venv/bin/python -m pytest`. Never run `pip install`, never create a venv, never add a conftest.py. Known machine fault: if `import matrixlang` fails with ModuleNotFoundError, run `chflags -R nohidden .venv` and continue (note it in your report). Any other import failure: report BLOCKED.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `src/matrixlang/values.py` | Value type rules: naming, strict type predicates, `to_display`. Imports only `errors` |
| `src/matrixlang/interpreter.py` | `Interpreter` class, `run(program, out)`. The tree walker |
| `src/matrixlang/repl.py` | Interactive loop with multi-line block buffering |
| `src/matrixlang/errors.py` | Modify: add `RuntimeErrorML` |
| `src/matrixlang/cli.py` | Modify: `run` and `repl` subcommands graduate out of `_PENDING` |
| `tests/test_values.py` | The bool-is-not-int rules, in isolation |
| `tests/test_interpreter.py` | Grows across Tasks 2–6 |
| `tests/test_repl.py` | Buffering, continuation, error recovery |
| `tests/test_cli.py` | Modify: `run` subcommand |
| `tests/test_architecture.py` | Modify: `_ALLOWED` gains three modules |

**Why `values.py` is its own module.** Every type rule in spec §5 is a place where `bool`-subclasses-`int` can silently defect. Scattering `type(v) is int` across the interpreter's twenty-odd branches means twenty chances to write `isinstance` by reflex. One module, tested in isolation, makes the rule auditable — and gives Stage 4's renderer a single place to ask "how does this value print?".

**Why the error class is `RuntimeErrorML`.** `RuntimeError` is a Python builtin. A module-level class shadowing it inside `errors.py` would make `except RuntimeError` ambiguous for every future reader. The `ML` suffix is ugly on purpose — it is a reminder that the name is taken.

---

### Task 1: Values module and RuntimeErrorML

**Files:**
- Create: `src/matrixlang/values.py`, `tests/test_values.py`
- Modify: `src/matrixlang/errors.py`, `tests/test_architecture.py`

**Interfaces:**
- Consumes: `MatrixLangError` from `matrixlang.errors`
- Produces:
  - `RuntimeErrorML(MatrixLangError)` in errors.py
  - `is_int(value) -> bool`, `is_bool(value) -> bool`, `is_str(value) -> bool` — strict, `type()`-based
  - `type_name(value) -> str` — returns `"integer"`, `"boolean"`, `"string"`, else `type(value).__name__`
  - `to_display(value) -> str` — how `trace` prints a value

- [ ] **Step 1: Write the failing tests**

Create `tests/test_values.py`:

```python
from matrixlang.values import is_bool, is_int, is_str, to_display, type_name


def test_bool_is_not_an_integer():
    # In Python, bool subclasses int: isinstance(True, int) is True and
    # True + 1 is 2. Spec §5 forbids coercion, so the interpreter must be
    # able to tell them apart. This is THE rule this module exists for.
    assert is_int(True) is False
    assert is_int(False) is False
    assert is_bool(True) is True
    assert is_int(7) is True
    assert is_bool(7) is False


def test_string_predicate():
    assert is_str("Neo") is True
    assert is_str(7) is False
    assert is_str(True) is False


def test_type_names_are_the_language_s_words():
    assert type_name(7) == "integer"
    assert type_name(True) == "boolean"
    assert type_name("Neo") == "string"


def test_display_prints_strings_without_quotes():
    assert to_display("wake up") == "wake up"


def test_display_prints_booleans_in_the_language_s_spelling():
    # Python renders these "True"/"False"; MatrixLang spells them lowercase.
    assert to_display(True) == "true"
    assert to_display(False) == "false"


def test_display_prints_integers():
    assert to_display(0) == "0"
    assert to_display(-7) == "-7"
```

Also append to `tests/test_errors.py`:

```python
def test_runtime_error_joins_the_hierarchy():
    from matrixlang.errors import RuntimeErrorML

    error = RuntimeErrorML("boom", 4, 9)
    assert isinstance(error, MatrixLangError)
    assert str(error) == "[line 4, column 9] boom"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_values.py tests/test_errors.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'matrixlang.values'`, and ImportError for `RuntimeErrorML`.

- [ ] **Step 3: Write the implementation**

Append to `src/matrixlang/errors.py`:

```python
class RuntimeErrorML(MatrixLangError):
    """Execution reached something the language forbids.

    Named with the ML suffix because `RuntimeError` is a Python builtin and
    shadowing it here would make `except RuntimeError` ambiguous for every
    future reader.
    """
```

Create `src/matrixlang/values.py`:

```python
"""Runtime value rules for MatrixLang.

Values are plain Python `int`, `bool` and `str` — the environment really is
a dictionary, which is the point of Stage 3.

That choice has one sharp edge, and this module exists to blunt it: in
Python, `bool` is a subclass of `int`. `isinstance(True, int)` is True and
`True + 1` evaluates to 2. Spec §5 forbids coercion, so `true + 1` must be
a runtime error — and with `isinstance` that error would never fire.

Every predicate here uses `type(value) is X`. Never `isinstance`.
"""


def is_int(value: object) -> bool:
    return type(value) is int


def is_bool(value: object) -> bool:
    return type(value) is bool


def is_str(value: object) -> bool:
    return type(value) is str


def type_name(value: object) -> str:
    """The language's own word for a value's type, for error messages."""
    if is_int(value):
        return "integer"
    if is_bool(value):
        return "boolean"
    if is_str(value):
        return "string"
    return type(value).__name__


def to_display(value: object) -> str:
    """How `trace` renders a value.

    Strings print without quotes; booleans print in the language's own
    lowercase spelling, not Python's `True`/`False`.
    """
    if is_bool(value):
        return "true" if value else "false"
    if is_str(value):
        return value
    return str(value)
```

- [ ] **Step 4: Extend the architecture table**

In `tests/test_architecture.py`, add one entry to `_ALLOWED`:

```python
    "values": {"errors"},
```

(Place it after the `"nodes"` entry. `values.py` imports nothing from siblings today; the entry states its ceiling.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest -q`
Expected: 146 passed (138 + 6 values + 1 errors + 1 new parametrized architecture case).

- [ ] **Step 6: Commit**

```bash
git add src/matrixlang/values.py src/matrixlang/errors.py tests/test_values.py tests/test_errors.py tests/test_architecture.py
git commit -m "feat(values): strict type rules that keep bool from posing as int"
```

---

### Task 2: Interpreter core — literals, trace, output injection

**Files:**
- Create: `src/matrixlang/interpreter.py`, `tests/test_interpreter.py`
- Modify: `tests/test_architecture.py`

**Interfaces:**
- Consumes: nodes from `matrixlang.nodes`; `RuntimeErrorML`; `values` helpers
- Produces:
  - `Interpreter` class: `__init__(self, out: TextIO | None = None)`, `.environment: dict[str, object]`, `.run(program: Program) -> None`
  - `run(program: Program, out: TextIO | None = None) -> None` — module-level convenience
  - Internal: `_execute(stmt)`, `_evaluate(expr) -> object`, both isinstance-dispatched with terminal `else: raise AssertionError(...)`

**Note on `out`:** defaults to `sys.stdout` when `None`. Tests pass an `io.StringIO` so they assert on captured text rather than on process stdout. Do not print directly.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_interpreter.py`:

```python
import io

import pytest

from matrixlang.errors import RuntimeErrorML
from matrixlang.interpreter import Interpreter, run
from matrixlang.lexer import lex
from matrixlang.parser import parse


def output(source: str) -> str:
    """Run a program and return everything it printed."""
    buffer = io.StringIO()
    run(parse(lex(source)), out=buffer)
    return buffer.getvalue()


def env(source: str) -> dict:
    """Run a program and return its final environment."""
    interpreter = Interpreter(out=io.StringIO())
    interpreter.run(parse(lex(source)))
    return interpreter.environment


def test_trace_prints_an_integer_with_a_newline():
    assert output("trace 7\n") == "7\n"


def test_trace_prints_a_string_without_quotes():
    assert output('trace "wake up, Neo"\n') == "wake up, Neo\n"


def test_trace_prints_booleans_in_the_language_s_spelling():
    assert output("trace true\ntrace false\n") == "true\nfalse\n"


def test_several_traces_appear_in_order():
    assert output("trace 1\ntrace 2\ntrace 3\n") == "1\n2\n3\n"


def test_an_empty_program_prints_nothing():
    assert output("") == ""


def test_comments_do_not_execute():
    assert output("# just a comment\ntrace 1  # and another\n") == "1\n"


def test_a_fresh_interpreter_starts_with_an_empty_environment():
    # `construct` does not exist until Task 3, so this task can only assert
    # the empty case. Task 3's test_environment_holds_every_declared_name
    # covers a populated environment.
    assert env("trace 1\n") == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_interpreter.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'matrixlang.interpreter'`

- [ ] **Step 3: Write the implementation**

Create `src/matrixlang/interpreter.py`:

```python
"""The MatrixLang tree-walking interpreter: syntax tree in, effects out.

The environment is a dictionary. That is not a simplification for teaching
purposes — with no functions and no closures yet (spec §5), a flat dict is
the whole of what scope means in this language.

This module consumes a Program node and nothing else. It never imports the
lexer, the parser or the CLI, so Stage 4 can hand it a tree that came from
either source face.
"""

import sys
from typing import TextIO

from matrixlang.errors import RuntimeErrorML
from matrixlang.nodes import (
    BoolLiteral,
    Expr,
    NumberLiteral,
    Program,
    Stmt,
    StringLiteral,
    Trace,
)
from matrixlang.values import to_display


class Interpreter:
    def __init__(self, out: TextIO | None = None) -> None:
        self.environment: dict[str, object] = {}
        self._out = sys.stdout if out is None else out

    def run(self, program: Program) -> None:
        for statement in program.statements:
            self._execute(statement)

    # --- statements -------------------------------------------------------

    def _execute(self, stmt: Stmt) -> None:
        if isinstance(stmt, Trace):
            print(to_display(self._evaluate(stmt.value)), file=self._out)
        else:
            raise AssertionError(f"unhandled statement node: {type(stmt).__name__}")

    # --- expressions ------------------------------------------------------

    def _evaluate(self, expr: Expr) -> object:
        if isinstance(expr, NumberLiteral):
            return expr.value
        if isinstance(expr, StringLiteral):
            return expr.value
        if isinstance(expr, BoolLiteral):
            return expr.value
        raise AssertionError(f"unhandled expression node: {type(expr).__name__}")


def run(program: Program, out: TextIO | None = None) -> None:
    """Execute a program. Convenience wrapper over Interpreter."""
    Interpreter(out=out).run(program)
```

- [ ] **Step 4: Extend the architecture table**

In `tests/test_architecture.py`, add to `_ALLOWED`:

```python
    "interpreter": {"errors", "nodes", "tokens", "values"},
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest -q`
Expected: 154 passed (146 + 7 interpreter + 1 architecture case).

- [ ] **Step 6: Commit**

```bash
git add src/matrixlang/interpreter.py tests/test_interpreter.py tests/test_architecture.py
git commit -m "feat(interpreter): literals and trace with injectable output"
```

---

### Task 3: Variables — construct, assignment, name lookup

**Files:**
- Modify: `src/matrixlang/interpreter.py`, `tests/test_interpreter.py`

**Interfaces:**
- Consumes: `Interpreter` from Task 2
- Produces: no new public names. `_execute` handles `Declare` and `Assign`; `_evaluate` handles `Name`.

**Behaviour fixed by this task (spec §5):** `construct` declares a name; re-declaring an existing name is an error. `=` requires a prior declaration; assigning to an unknown name is an error. That asymmetry is what makes `construct` mean something.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_interpreter.py` (add `Declare` is not needed — these go through source):

```python
def test_construct_declares_and_name_reads_back():
    assert output("construct x = 5\ntrace x\n") == "5\n"


def test_assignment_updates_an_existing_name():
    assert output("construct x = 1\nx = 2\ntrace x\n") == "2\n"


def test_environment_holds_every_declared_name():
    assert env('construct a = 1\nconstruct b = "two"\nconstruct c = true\n') == {
        "a": 1,
        "b": "two",
        "c": True,
    }


def test_redeclaring_a_name_is_an_error():
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("construct x = 1\nconstruct x = 2\n")
    assert "already declared" in str(excinfo.value)
    assert excinfo.value.line == 2


def test_assigning_to_an_undeclared_name_is_an_error():
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("x = 1\n")
    assert "not declared" in str(excinfo.value)
    assert excinfo.value.line == 1


def test_reading_an_undeclared_name_is_an_error():
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("trace nope\n")
    assert "not declared" in str(excinfo.value)
    assert excinfo.value.column == 7


def test_a_name_may_hold_a_different_type_after_assignment():
    # Dynamic typing, spec §5: no declared types, so this is legal.
    assert output('construct x = 1\nx = "now a string"\ntrace x\n') == "now a string\n"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_interpreter.py -v`
Expected: FAIL — `AssertionError: unhandled statement node: Declare`

- [ ] **Step 3: Write the implementation**

Add `Assign, Declare, Name` to the nodes import in `interpreter.py`. Add these branches to `_execute`, before the terminal `else`:

```python
        elif isinstance(stmt, Declare):
            if stmt.name in self.environment:
                raise RuntimeErrorML(
                    f"'{stmt.name}' is already declared", stmt.line, stmt.column
                )
            self.environment[stmt.name] = self._evaluate(stmt.value)
        elif isinstance(stmt, Assign):
            if stmt.name not in self.environment:
                raise RuntimeErrorML(
                    f"'{stmt.name}' is not declared — use 'construct' first",
                    stmt.line,
                    stmt.column,
                )
            self.environment[stmt.name] = self._evaluate(stmt.value)
```

Add this branch to `_evaluate`, before the terminal `raise`:

```python
        if isinstance(expr, Name):
            if expr.ident not in self.environment:
                raise RuntimeErrorML(
                    f"'{expr.ident}' is not declared", expr.line, expr.column
                )
            return self.environment[expr.ident]
```

Note the `Trace` branch in `_execute` is now the first of an if/elif chain — convert its `if` to stay first and make the new ones `elif`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest -q`
Expected: 161 passed.

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/interpreter.py tests/test_interpreter.py
git commit -m "feat(interpreter): construct, assignment and name resolution"
```

---

### Task 4: Arithmetic, concatenation, and the type rules

**Files:**
- Modify: `src/matrixlang/interpreter.py`, `tests/test_interpreter.py`

**Interfaces:**
- Consumes: `Interpreter` from Task 3; `is_int`, `is_str`, `type_name` from `values`
- Produces: no new public names. `_evaluate` handles `Unary` and the arithmetic half of `Binary`. Internal helpers `_arithmetic(op, left, right, node)` and `_require_int(value, node, role)`.

**Behaviour fixed by this task (spec §5):** integer-only arithmetic; `/` truncates toward zero; division by zero is a runtime error; `+` also concatenates two strings; mixed `int + str` is an error; unary `-` is integers only. **`true + 1` must be an error** — that is the whole reason `values.py` exists.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_interpreter.py`:

```python
def test_integer_arithmetic():
    assert output("trace 2 + 3 * 4\n") == "14\n"
    assert output("trace (2 + 3) * 4\n") == "20\n"
    assert output("trace 10 - 3 - 2\n") == "5\n"


def test_division_truncates_toward_zero_not_floor():
    # Python's // floors: -7 // 2 == -4. Spec §5 requires -3.
    # All four sign combinations. (-,-) matters most: it is the case that
    # still looks right if someone "simplifies" the sign logic back to //,
    # because -7 // -2 == 3 agrees with truncation. Assert it anyway, so the
    # test pins the rule rather than two-thirds of it.
    assert output("trace 7 / 2\n") == "3\n"
    assert output("trace -7 / 2\n") == "-3\n"
    assert output("trace 7 / -2\n") == "-3\n"
    assert output("trace -7 / -2\n") == "3\n"


def test_division_by_zero_is_a_runtime_error():
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("trace 1 / 0\n")
    assert "divide by zero" in str(excinfo.value)


def test_unary_minus():
    assert output("trace -5\n") == "-5\n"
    assert output("construct x = 3\ntrace -x\n") == "-3\n"


def test_string_concatenation():
    assert output('trace "wake up, " + "Neo"\n') == "wake up, Neo\n"


def test_mixing_a_string_and_an_integer_is_an_error():
    with pytest.raises(RuntimeErrorML) as excinfo:
        output('trace "count: " + 1\n')
    assert "string" in str(excinfo.value)
    assert "integer" in str(excinfo.value)


def test_booleans_are_not_integers_in_arithmetic():
    # THE bool-is-an-int trap. Python would evaluate True + 1 to 2.
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("trace true + 1\n")
    assert "boolean" in str(excinfo.value)


def test_booleans_are_not_integers_under_unary_minus():
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("trace -true\n")
    assert "boolean" in str(excinfo.value)


def test_arithmetic_errors_report_the_operator_position():
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("trace 1 + true\n")
    assert excinfo.value.line == 1
    assert excinfo.value.column == 9
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_interpreter.py -v`
Expected: FAIL — `AssertionError: unhandled expression node: Binary`

- [ ] **Step 3: Write the implementation**

Add `Binary, Unary` to the nodes import, `TokenType` from `matrixlang.tokens`, and `is_int, is_str, type_name` from `matrixlang.values`.

Add these branches to `_evaluate`, before the terminal `raise`:

```python
        if isinstance(expr, Unary):
            operand = self._evaluate(expr.operand)
            self._require_int(operand, expr, "operand of unary '-'")
            return -operand
        if isinstance(expr, Binary):
            left = self._evaluate(expr.left)
            right = self._evaluate(expr.right)
            return self._binary(expr, left, right)
```

Add these methods to the class:

```python
    def _binary(self, node: Binary, left: object, right: object) -> object:
        if node.op is TokenType.PLUS and is_str(left) and is_str(right):
            return left + right
        return self._arithmetic(node, left, right)

    def _arithmetic(self, node: Binary, left: object, right: object) -> object:
        self._require_int(left, node, "left operand")
        self._require_int(right, node, "right operand")
        if node.op is TokenType.PLUS:
            return left + right
        if node.op is TokenType.MINUS:
            return left - right
        if node.op is TokenType.STAR:
            return left * right
        if node.op is TokenType.SLASH:
            if right == 0:
                raise RuntimeErrorML("cannot divide by zero", node.line, node.column)
            # Truncate toward zero. Python's // floors, which differs for
            # negatives: -7 // 2 is -4, but the spec requires -3.
            quotient = abs(left) // abs(right)
            return -quotient if (left < 0) != (right < 0) else quotient
        raise AssertionError(f"unhandled binary operator: {node.op.name}")

    def _require_int(self, value: object, node: Expr, role: str) -> None:
        if not is_int(value):
            raise RuntimeErrorML(
                f"{role} must be an integer, got {type_name(value)}",
                node.line,
                node.column,
            )
```

Note `_binary` handles the string-concatenation case first, then falls through to `_arithmetic`, which rejects anything non-integer. A `"a" + 1` therefore reports "left operand must be an integer, got string" — the message names both types the test asserts on.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest -q`
Expected: 170 passed.

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/interpreter.py tests/test_interpreter.py
git commit -m "feat(interpreter): arithmetic, concatenation, and strict integer rules"
```

---

### Task 5: Comparisons and equality

**Files:**
- Modify: `src/matrixlang/interpreter.py`, `tests/test_interpreter.py`

**Interfaces:**
- Consumes: `_binary` from Task 4
- Produces: no new public names. `_binary` gains equality and ordering, via `_comparison(node, left, right)`.

**Behaviour fixed by this task (spec §5):** `==` and `!=` work on any two values **of the same type**; comparing across types is an error. Ordering (`< > <= >=`) is integers only. `true == 1` must be an error, not `True` — the bool/int trap again, in its second disguise.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_interpreter.py`:

```python
def test_integer_equality_and_ordering():
    assert output("trace 1 == 1\ntrace 1 != 1\n") == "true\nfalse\n"
    assert output("trace 1 < 2\ntrace 2 <= 2\ntrace 3 > 4\ntrace 4 >= 4\n") == (
        "true\ntrue\nfalse\ntrue\n"
    )


def test_string_and_boolean_equality():
    assert output('trace "a" == "a"\ntrace "a" != "b"\n') == "true\ntrue\n"
    assert output("trace true == true\ntrace true != false\n") == "true\ntrue\n"


def test_comparing_across_types_is_an_error():
    with pytest.raises(RuntimeErrorML) as excinfo:
        output('trace 1 == "1"\n')
    assert "integer" in str(excinfo.value)
    assert "string" in str(excinfo.value)


def test_true_does_not_equal_one():
    # Python says True == 1. MatrixLang says these are different types.
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("trace true == 1\n")
    assert "boolean" in str(excinfo.value)


def test_ordering_strings_is_an_error():
    with pytest.raises(RuntimeErrorML) as excinfo:
        output('trace "a" < "b"\n')
    assert "must be an integer" in str(excinfo.value)


def test_ordering_booleans_is_an_error():
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("trace true < false\n")
    assert "must be an integer" in str(excinfo.value)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_interpreter.py -v`
Expected: FAIL with `AssertionError: unhandled binary operator: EQ`. Trace why: `_binary` routes everything except string concatenation to `_arithmetic`, whose `_require_int` calls both pass for `1 == 1`, so it falls through its PLUS/MINUS/STAR/SLASH chain to the terminal assertion. The ordering tests fail the same way with `LT`, `GT`, `LTE`, `GTE`.

- [ ] **Step 3: Write the implementation**

`type_name` is already imported from Task 4. Add these module-level tuples below the imports in `interpreter.py`:

```python
_EQUALITY_OPS = (TokenType.EQ, TokenType.NEQ)
_ORDERING_OPS = (TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE)
```

Rewrite `_binary` to route before reaching arithmetic:

```python
    def _binary(self, node: Binary, left: object, right: object) -> object:
        if node.op in _EQUALITY_OPS or node.op in _ORDERING_OPS:
            return self._comparison(node, left, right)
        if node.op is TokenType.PLUS and is_str(left) and is_str(right):
            return left + right
        return self._arithmetic(node, left, right)
```

Add:

```python
    def _comparison(self, node: Binary, left: object, right: object) -> object:
        if node.op in _ORDERING_OPS:
            self._require_int(left, node, "left operand")
            self._require_int(right, node, "right operand")
            if node.op is TokenType.LT:
                return left < right
            if node.op is TokenType.GT:
                return left > right
            if node.op is TokenType.LTE:
                return left <= right
            return left >= right

        # Equality: same type only. type_name is the arbiter, so a bool can
        # never equal an int even though Python says True == 1.
        if type_name(left) != type_name(right):
            raise RuntimeErrorML(
                f"cannot compare {type_name(left)} with {type_name(right)}",
                node.line,
                node.column,
            )
        return left == right if node.op is TokenType.EQ else left != right
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest -q`
Expected: 176 passed.

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/interpreter.py tests/test_interpreter.py
git commit -m "feat(interpreter): equality and ordering with strict type matching"
```

---

### Task 6: Conditionals and loops — the language runs

**Files:**
- Modify: `src/matrixlang/interpreter.py`, `tests/test_interpreter.py`

**Interfaces:**
- Consumes: `Interpreter` from Task 5
- Produces: no new public names. `_execute` handles `If` and `While`; internal `_condition(expr) -> bool`.

**Behaviour fixed by this task (spec §5):** conditions must be boolean. No truthy integers, no truthy strings — `redpill 1` is an error, not a taken branch.

**This task contains the parent spec's Stage 3 done-when criterion:** a counting loop runs correctly. At this point the language exists.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_interpreter.py`:

```python
def test_redpill_takes_the_then_branch():
    assert output("redpill true\n  trace 1\nflatline\n") == "1\n"


def test_redpill_skips_an_untaken_branch_with_no_else():
    assert output("redpill false\n  trace 1\nflatline\n") == ""


def test_bluepill_takes_the_else_branch():
    source = "redpill false\n  trace 1\nbluepill\n  trace 2\nflatline\n"
    assert output(source) == "2\n"


def test_nested_conditionals():
    source = (
        "construct x = 2\n"
        "redpill x > 1\n"
        "  redpill x > 5\n"
        "    trace 100\n"
        "  bluepill\n"
        "    trace 50\n"
        "  flatline\n"
        "flatline\n"
    )
    assert output(source) == "50\n"


def test_a_non_boolean_condition_is_an_error():
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("redpill 1\n  trace 1\nflatline\n")
    assert "must be a boolean" in str(excinfo.value)
    assert "integer" in str(excinfo.value)


def test_a_string_condition_is_an_error():
    with pytest.raises(RuntimeErrorML) as excinfo:
        output('dejavu "yes"\n  trace 1\nflatline\n')
    assert "must be a boolean" in str(excinfo.value)


def test_a_loop_that_never_runs():
    assert output("dejavu false\n  trace 1\nflatline\n") == ""


def test_counting_loop_runs():
    # THE parent spec's Stage 3 done-when criterion. At this point the
    # language exists.
    source = (
        "construct n = 1\n"
        "dejavu n <= 10\n"
        "  trace n\n"
        "  n = n + 1\n"
        "flatline\n"
    )
    assert output(source) == "".join(f"{i}\n" for i in range(1, 11))


def test_the_stage_3_demo_program_runs():
    source = (
        "construct n = 0\n"
        'construct name = "Neo"\n'
        "\n"
        "dejavu n < 3\n"
        "  redpill n == 1\n"
        '    trace "wake up, " + name\n'
        "  bluepill\n"
        "    trace n\n"
        "  flatline\n"
        "  n = n + 1\n"
        "flatline\n"
    )
    assert output(source) == "0\nwake up, Neo\n2\n"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_interpreter.py -v`
Expected: FAIL — `AssertionError: unhandled statement node: If`

- [ ] **Step 3: Write the implementation**

Add `If, While` to the nodes import and `is_bool` to the values import. Add these branches to `_execute`, before the terminal `else`:

```python
        elif isinstance(stmt, If):
            if self._condition(stmt.condition):
                for child in stmt.then_body:
                    self._execute(child)
            elif stmt.else_body is not None:
                for child in stmt.else_body:
                    self._execute(child)
        elif isinstance(stmt, While):
            while self._condition(stmt.condition):
                for child in stmt.body:
                    self._execute(child)
```

Add:

```python
    def _condition(self, expr: Expr) -> bool:
        """Evaluate a condition, requiring a boolean.

        Spec §5: no truthy integers, no truthy strings. `redpill 1` is an
        error, not a taken branch.
        """
        value = self._evaluate(expr)
        if not is_bool(value):
            raise RuntimeErrorML(
                f"condition must be a boolean, got {type_name(value)}",
                expr.line,
                expr.column,
            )
        return value
```

Note `stmt.else_body is not None` — never truthiness. An empty `bluepill` body is `[]`, which is falsy but still means the branch exists.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest -q`
Expected: 185 passed.

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/interpreter.py tests/test_interpreter.py
git commit -m "feat(interpreter): conditionals and loops — the language runs"
```

---

### Task 7: The REPL

**Files:**
- Create: `src/matrixlang/repl.py`, `tests/test_repl.py`
- Modify: `tests/test_architecture.py`

**Interfaces:**
- Consumes: `Interpreter`; `lex`; `parse`; `MatrixLangError`
- Produces:
  - `Repl` class: `__init__(self, out: TextIO)`, `.feed(line: str) -> bool`, `.interpreter: Interpreter`
  - `repl(in_: TextIO | None = None, out: TextIO | None = None) -> int` — the interactive loop
  - `PROMPT = "> "`, `CONTINUATION = "... "`

**How buffering works.** `feed(line)` returns `True` when it is waiting for more input (an open block), `False` when it executed. It tracks depth by counting block openers (`redpill`, `dejavu`) against closers (`flatline`) in the token stream of the buffered text — not by string matching, so a `#` comment or a string containing the word `flatline` cannot confuse it.

**Error recovery.** Any `MatrixLangError` is printed and the buffer is cleared; the session continues. A REPL that dies on a typo is not a REPL.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_repl.py`:

```python
import io

from matrixlang.repl import Repl, repl


def feed_all(lines: list[str]) -> str:
    """Feed lines to a Repl and return everything it printed."""
    buffer = io.StringIO()
    session = Repl(out=buffer)
    for line in lines:
        session.feed(line)
    return buffer.getvalue()


def test_a_single_statement_executes_immediately():
    assert feed_all(["trace 1"]) == "1\n"


def test_state_persists_between_lines():
    assert feed_all(["construct x = 5", "trace x"]) == "5\n"


def test_a_block_waits_for_flatline():
    buffer = io.StringIO()
    session = Repl(out=buffer)
    assert session.feed("dejavu false") is True
    assert session.feed("  trace 1") is True
    assert session.feed("flatline") is False
    assert buffer.getvalue() == ""


def test_a_loop_typed_at_the_prompt_runs():
    printed = feed_all(
        ["construct n = 1", "dejavu n <= 3", "  trace n", "  n = n + 1", "flatline"]
    )
    assert printed == "1\n2\n3\n"


def test_nested_blocks_need_both_flatlines():
    buffer = io.StringIO()
    session = Repl(out=buffer)
    session.feed("redpill true")
    session.feed("  redpill true")
    session.feed("    trace 9")
    assert session.feed("  flatline") is True
    assert session.feed("flatline") is False
    assert buffer.getvalue() == "9\n"


def test_a_syntax_error_is_reported_and_the_session_continues():
    printed = feed_all(["construct = 5", "trace 1"])
    assert "line 1" in printed
    assert printed.endswith("1\n")


def test_a_runtime_error_is_reported_and_the_session_continues():
    printed = feed_all(["trace nope", "trace 2"])
    assert "not declared" in printed
    assert printed.endswith("2\n")


def test_an_error_inside_a_block_clears_the_buffer():
    # After a failed block the next line must be treated as fresh input,
    # not appended to the wreckage.
    printed = feed_all(["redpill 1", "  trace 1", "flatline", "trace 7"])
    assert "must be a boolean" in printed
    assert printed.endswith("7\n")


def test_blank_lines_and_comments_are_harmless():
    assert feed_all(["", "# nothing", "trace 1"]) == "1\n"


def test_a_bare_expression_is_a_syntax_error_not_a_crash():
    # The grammar has no expression statement; the REPL must report that
    # cleanly rather than raise.
    printed = feed_all(["1 + 1", "trace 2"])
    assert "line 1" in printed
    assert printed.endswith("2\n")


def test_repl_reads_until_eof_and_returns_zero():
    source = io.StringIO("construct x = 2\ntrace x\n")
    out = io.StringIO()
    assert repl(in_=source, out=out) == 0
    assert "2\n" in out.getvalue()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_repl.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'matrixlang.repl'`

- [ ] **Step 3: Write the implementation**

Create `src/matrixlang/repl.py`:

```python
"""Interactive MatrixLang session.

Buffers input while a block is open, so a `dejavu` loop can be typed at the
prompt and watched running — which is the point of Stage 3.

Depth is counted over the TOKEN stream, not over raw text: a `#` comment or
a string containing the word "flatline" must not close a block.
"""

import sys
from typing import TextIO

from matrixlang.errors import MatrixLangError
from matrixlang.interpreter import Interpreter
from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.tokens import TokenType

PROMPT = "> "
CONTINUATION = "... "

_OPENERS = (TokenType.REDPILL, TokenType.DEJAVU)


class Repl:
    def __init__(self, out: TextIO | None = None) -> None:
        self._out = sys.stdout if out is None else out
        self.interpreter = Interpreter(out=self._out)
        self._buffer: list[str] = []

    def feed(self, line: str) -> bool:
        """Take one line. Return True if more input is needed."""
        self._buffer.append(line)
        source = "\n".join(self._buffer) + "\n"

        try:
            depth = _open_blocks(source)
        except MatrixLangError as error:
            self._fail(error)
            return False

        if depth > 0:
            return True

        try:
            self.interpreter.run(parse(lex(source)))
        except MatrixLangError as error:
            self._fail(error)
        self._buffer.clear()
        return False

    def _fail(self, error: MatrixLangError) -> None:
        print(f"matrixlang: {error}", file=self._out)
        self._buffer.clear()


def _open_blocks(source: str) -> int:
    """How many blocks are still open, counted over tokens."""
    depth = 0
    for token in lex(source):
        if token.type in _OPENERS:
            depth += 1
        elif token.type is TokenType.FLATLINE:
            depth -= 1
    return max(depth, 0)


def repl(in_: TextIO | None = None, out: TextIO | None = None) -> int:
    """Run an interactive session until end of input."""
    source = sys.stdin if in_ is None else in_
    sink = sys.stdout if out is None else out
    session = Repl(out=sink)
    needs_more = False

    while True:
        print(CONTINUATION if needs_more else PROMPT, end="", file=sink)
        sink.flush()
        line = source.readline()
        if not line:
            print(file=sink)
            return 0
        needs_more = session.feed(line.rstrip("\n"))
```

- [ ] **Step 4: Extend the architecture table**

In `tests/test_architecture.py`, add to `_ALLOWED`:

```python
    "repl": {"errors", "interpreter", "lexer", "parser", "tokens"},
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest -q`
Expected: 197 passed (185 + 11 repl + 1 architecture case).

- [ ] **Step 6: Commit**

```bash
git add src/matrixlang/repl.py tests/test_repl.py tests/test_architecture.py
git commit -m "feat(repl): interactive session with multi-line block buffering"
```

---

### Task 8: CLI wiring, README, version

**Files:**
- Modify: `src/matrixlang/cli.py`, `tests/test_cli.py`, `tests/test_architecture.py`, `README.md`, `src/matrixlang/__init__.py`, `pyproject.toml`

**Interfaces:**
- Consumes: `run` from `interpreter`; `repl` from `repl`
- Produces: `matrixlang run <file>` and `matrixlang repl`. `_PENDING` shrinks to `{"render": "Stage 4"}`. Version bumps to 0.3.0.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_cli.py`:

```python
def test_run_executes_a_program(source_file, capsys):
    exit_code = main(["run", source_file("construct x = 2\ntrace x + 3\n")])
    assert exit_code == 0
    assert capsys.readouterr().out == "5\n"


def test_run_reports_a_runtime_error_and_exits_one(source_file, capsys):
    exit_code = main(["run", source_file("trace 1 / 0\n")])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "divide by zero" in captured.err
    assert "line 1" in captured.err


def test_run_reports_a_parse_error_and_exits_one(source_file, capsys):
    exit_code = main(["run", source_file("construct = 5\n")])
    assert exit_code == 1
    assert "line 1" in capsys.readouterr().err


def test_run_emits_output_produced_before_a_runtime_error(source_file, capsys):
    # Unlike lex and parse, run has side effects as it goes. Output already
    # printed is real and must not be swallowed.
    exit_code = main(["run", source_file("trace 1\ntrace 2 / 0\n")])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == "1\n"
    assert "divide by zero" in captured.err


def test_run_missing_file_exits_two(capsys, tmp_path):
    assert main(["run", str(tmp_path / "nope.rain")]) == 2


def test_only_render_remains_unimplemented(capsys):
    assert main(["render"]) == 2
    assert "Stage 4" in capsys.readouterr().err
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: FAIL — `main(["run", ...])` returns 2 with "arrives in Stage 3" rather than executing.

- [ ] **Step 3: Write the implementation**

In `src/matrixlang/cli.py`:

1. Add imports:

```python
from matrixlang.interpreter import run as run_program
from matrixlang.repl import repl as run_repl
```

2. Shrink `_PENDING` to:

```python
_PENDING: dict[str, str] = {"render": "Stage 4"}
```

3. Give `run` a path argument. Replace the existing bare `subcommands.add_parser("run", ...)` with:

```python
    run_parser = subcommands.add_parser("run", help="Execute a source file.")
    run_parser.add_argument("path", help="Path to a .rain source file.")
```

Leave the `repl` and `render` subparsers as they are.

4. In `main`'s dispatch, add after the `parse` case:

```python
    if args.command == "run":
        return _command_run(args.path)
    if args.command == "repl":
        return run_repl()
```

5. Add:

```python
def _command_run(path: str) -> int:
    source = _read_source(path)
    if source is None:
        return 2

    try:
        tree = parse(lex(source))
    except MatrixLangError as error:
        print(f"matrixlang: {error}", file=sys.stderr)
        return 1

    # Execution is deliberately outside the parse try-block: a program that
    # fails partway has already printed real output, and that output stays.
    try:
        run_program(tree)
    except MatrixLangError as error:
        print(f"matrixlang: {error}", file=sys.stderr)
        return 1
    return 0
```

6. Version: `__version__ = "0.3.0"` in `src/matrixlang/__init__.py`, `version = "0.3.0"` in `pyproject.toml`.

7. `tests/test_architecture.py` — update the `cli` entry:

```python
    "cli": {"errors", "interpreter", "lexer", "parser", "repl", "treeview"},
```

8. `README.md` — change the Status line to:

```markdown
Stage 3 — interpreter. The language runs.
```

and add to the Usage section, below the `parse` block:

```markdown
```bash
.venv/bin/matrixlang run examples/hello.rain
.venv/bin/matrixlang repl
```

`run` executes a program. `repl` starts an interactive session — blocks span
multiple lines, so a `dejavu` loop can be typed at the prompt.
```

- [ ] **Step 4: Run tests and the real CLI**

```bash
.venv/bin/python -m pytest -v
.venv/bin/matrixlang run examples/hello.rain
printf 'construct n = 1\ndejavu n <= 3\n  trace n\n  n = n + 1\nflatline\n' | .venv/bin/matrixlang repl
```

Expected: 203 passed. `run` prints `0`, `wake up, Neo`, `2` and exits 0. The piped REPL session prints `1`, `2`, `3`.

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/cli.py src/matrixlang/__init__.py pyproject.toml README.md tests/test_cli.py tests/test_architecture.py
git commit -m "feat(cli): matrixlang run and repl; version 0.3.0"
```

---

## Self-Review

**Spec §5 coverage — all twelve rules:**

| Rule | Task | Test |
| --- | --- | --- |
| Dynamic typing, int/bool/str | 1, 3 | `test_a_name_may_hold_a_different_type_after_assignment` |
| One flat environment | 2 | `test_interpreter_exposes_its_environment` |
| `construct` declares; re-declaration errors | 3 | `test_redeclaring_a_name_is_an_error` |
| `=` requires prior declaration | 3 | `test_assigning_to_an_undeclared_name_is_an_error` |
| Conditions must be boolean | 6 | `test_a_non_boolean_condition_is_an_error` |
| Integer-only arithmetic | 4 | `test_booleans_are_not_integers_in_arithmetic` |
| `/` truncates toward zero | 4 | `test_division_truncates_toward_zero_not_floor` |
| Division by zero errors | 4 | `test_division_by_zero_is_a_runtime_error` |
| `+` concatenates strings; mixed errors | 4 | `test_mixing_a_string_and_an_integer_is_an_error` |
| `==`/`!=` same type only | 5 | `test_true_does_not_equal_one` |
| Ordering integers only | 5 | `test_ordering_strings_is_an_error` |
| Unary `-` integers only | 4 | `test_booleans_are_not_integers_under_unary_minus` |
| `trace` formatting | 1, 2 | `test_display_prints_booleans_in_the_language_s_spelling` |
| All errors report line and column | 3–6 | `test_arithmetic_errors_report_the_operator_position` |

**Parent spec Stage 3 done-when:** `test_counting_loop_runs`, Task 6.

**The `bool`-is-an-`int` trap has three faces, all tested:** arithmetic (`true + 1`, Task 4), unary minus (`-true`, Task 4), and equality (`true == 1`, Task 5). A single `isinstance` slip breaks one of the three without breaking the others, which is why each has its own test.

**Type consistency spot-checks:** `RuntimeErrorML` used identically in Tasks 1, 3–6. `Interpreter(out=...)` signature matches across Tasks 2 and 7. `_require_int(value, node, role)` defined in Task 4, reused in Task 5. `stmt.else_body is not None` in Task 6 matches the `None`-vs-`[]` distinction Stage 2 established. `type_name` is the equality arbiter in Task 5 and the message source in Tasks 4 and 6.

**Known intentional choices (do not "fix" during implementation):** no truthiness anywhere; no step or iteration limit on loops (an infinite `dejavu true` is the user's to interrupt); the REPL discards a failed buffer rather than attempting recovery; `_open_blocks` counts tokens rather than text; execution sits outside the parse try-block in `_command_run` so partial output survives.

**Deliberately out of scope:** functions, closures, lexical scope, collections, `else if` chains, logical operators (all deferred by spec §9); glyph rendering and the rain runner (Stages 4–5).
