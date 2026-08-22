# Paste Python, Get MatrixLang — Design

**Date:** 2026-08-21
**Status:** Approved, ready for an implementation plan
**Tracking issue:** #122
**Depends on:** #121 (dictionaries), merged as #124

## Why

Running an idea in the playground means writing MatrixLang by hand, or asking
Scribe for one of a fixed set of shapes, or paying for Operator with your own
API key. A reader who already knows Python translates their own program
statement by statement — which is exactly what happened with the students-search
program that motivated dictionaries.

This adds a third route: paste Python, get MatrixLang, run it with the same Run
button.

## What this is not

Not a general Python-to-MatrixLang compiler. MatrixLang has integers, strings,
booleans, lists and dictionaries. No floats, no classes, no imports, no
exceptions, no comprehensions, no `None`, and no truthiness — `redpill` demands
an actual boolean.

So the deliverable is a translator for **a stated subset**, and its most
important behaviour is **refusing clearly**. A translator that silently
mistranslates is worse than one that stops and says which line it cannot do and
what to write instead.

## The governing rule

**Translate syntax; never infer types.**

Where Python's meaning depends on a runtime type that MatrixLang distinguishes,
refuse rather than guess. The corollary sets the boundary precisely:

> **Refuse where the difference would be silent. Allow where MatrixLang will
> fail loudly with a positioned error the reader can act on.**

Truthiness is the case that forces this. `if result:` depends on whether
`result` is a list, a string, a number or a boolean, and each needs a different
MatrixLang expansion. Guessing produces a program that runs and is subtly wrong
— the one outcome this tool must never have. So it refuses:

```
line 18: `if result:` relies on truthiness, which MatrixLang does not
have — a condition must already be a boolean.
  a list or string →  if len(result) > 0:
  a number        →  if result != 0:
```

By contrast, `str(x)` becomes `encode x` even though `encode` takes only a
number. If `x` is a string at runtime, MatrixLang says so with a line and
column. That is a loud failure in a program the reader is about to run, not a
silent one.

## Architecture

**Python AST → MatrixLang AST → `render_ascii()`.** Not Python AST → text.

This is the load-bearing choice. `render.py` already knows every precedence
rule and exactly where parentheses are required. Emitting text directly would
re-derive all of it in a second place — the shape of mistake that produced the
deleted `web/interpreter.js` and the `site/checks/no_semantics.py` gate that
now guards against it (TECHNICAL-OVERVIEW §5.7).

Building real `matrixlang.nodes` objects buys three things:

1. **The output parses by construction.** It was built from the same node
   classes the parser produces, and rendered by the same renderer.
2. **The glyph face comes free**, because `render_glyph` takes the same tree.
3. **Precedence and parenthesisation are not this module's problem.**

Every node the subset needs already exists in `nodes.py`: `Program`, `Declare`,
`Assign`, `IndexAssign`, `Trace`, `If`, `While`, `FunctionDef`, `Return`,
`ExprStmt`, `Call`, `Binary`, `Unary`, `Index`, `ListLiteral`, `DictLiteral`,
`Name`, `NumberLiteral`, `StringLiteral`, `BoolLiteral`, `JackIn`. The
translator adds no node types.

### Module layout

A new package `src/matrixlang/pytrans/`, sibling to `operator/`:

| Module | Responsibility |
| --- | --- |
| `translate.py` | Walks the Python AST, builds MatrixLang nodes |
| `refuse.py` | The `Refusal` type and the message catalogue |
| `names.py` | Counter-name allocation |

### The public interface

Mirrors `scribe()`, including its central promise:

```python
def translate(source: str) -> Translated | Refusals:
    """Translate Python to MatrixLang. Never raises."""
```

```python
@dataclass(frozen=True)
class Translated:
    source: str          # MatrixLang, ASCII face

@dataclass(frozen=True)
class Refusal:
    reason: str          # what cannot be translated
    line: int            # position in the PYTHON source
    column: int
    idiom: str | None    # the MatrixLang way, when one exists

@dataclass(frozen=True)
class Refusals:
    items: list[Refusal]   # in line order, never empty
```

**`ast.parse` raising `SyntaxError` is caught** and returned as a single
`Refusal` carrying its position. Invalid Python is a refusal, not an exception.

**All refusals are collected, not just the first.** A statement that cannot be
translated is recorded and the walk continues to the next statement. Fixing a
thirty-line program should take one pass, not five. When any refusal exists no
program is returned at all — a partial translation is a wrong program.

### How it reaches the page

`site/glue.py` gains one function, mirroring `write()`:

```python
def translate_python(source: str) -> dict:
    """Ask the translator for a program. Never raises."""
```

`site/playground.js` calls it and, on success, sets `el("editor").value` exactly
as `writeProgram()` already does. The browser gains no language logic, so
`site/checks/no_semantics.py` keeps passing unmodified.

## The subset

### Translated

| Python | MatrixLang |
| --- | --- |
| `x = v` (first binding in scope) | `construct x = v` |
| `x = v` (later) | `x = v` |
| `x += v` | `x = x + v` |
| `xs[i] = v` | `xs[i] = v` |
| `+ - *`, `== != < > <= >=` | the same operators |
| `and` / `or` / `not` | `splice` / `fork` / `unplug` |
| `if` / `elif` / `else` | `redpill` / nested `redpill` in `bluepill` / `bluepill` |
| `while c:` | `dejavu c` |
| `def f(a, b):` / `return v` / bare `return` | `agent f(a, b)` / `jackout v` / `jackout` |
| `print(x)` | `trace x` |
| `len(x)` | `length x` |
| `str(x)` / `int(x)` | `encode x` / `decode x` |
| `k in d` | `d oracle k` |
| `xs.append(v)` | `xs = xs + [v]` |
| list and dict literals, indexing | the same |
| `True` / `False` | `true` / `false` |
| f-strings | `+` chain with `encode` around each interpolation |

`elif` nests a `redpill` inside the enclosing `bluepill`; verified against the
real interpreter.

**`in` always becomes `oracle`, whatever it is asked about.** MatrixLang's
`oracle` reads a dictionary and nothing else, so `2 in xs` over a list is not a
program this language has. But the translator cannot tell the two apart:
`k in d` and `2 in xs` are the same syntax, and only the runtime value says
which is which — deciding would mean inferring a type, which is the one thing
the governing rule forbids. So the row is unconditional, and `in` over a list or
a string produces `xs oracle 2`, which fails at runtime with a line, a column,
and the words `'oracle' takes a dictionary, got list`. That is the rule's second
half working as intended: loud, positioned, and actionable beats a refusal that
would have to guess to be right. `not in` is a separate matter and genuinely is
refused — MatrixLang has no negated form, and the refusal names
`unplug (d oracle key)`.

### Three rewrites, each with a stated rule

**`for x in xs:` — the index is substituted inline.** No loop variable is
declared; every use of `x` in the body becomes `xs[n]`.

```python
for student in result:
    print(f"-ID: {student['id']}")
```

```
construct n = 0
dejavu n < length result
  trace "-ID: " + encode result[n]["id"]
  n = n + 1
flatline
```

This sidesteps the language quirk below, and invents exactly one name.
`for i in range(n)` uses the same counter shape with the counter itself as the
value, and the bound `n` is read once into a name of its own before the loop —
Python builds the range object at loop entry, so a body that changes `n` still
runs the original number of times. A literal bound stays inline.

Three refusals guard what substitution cannot express:

- **A body that reassigns the loop variable.** There is no name to reassign.
- **A body that reassigns the iterable's own name.** Python's `for` holds the
  list object and never sees the rebinding; indexing the name would follow it
  onto a different list. Hoisting into a holder would fix that and break
  `xs.append(v)` inside `for x in xs`, which never ends in Python and would
  quietly finish — no output is right for both.
- **A loop variable that is already a name in the same scope.** Python leaves
  the variable bound after the loop; the output has no such name, so a read
  after the loop returns whatever the name held *before* it. With a new name
  that read fails loudly; with a reused one it silently returns the old value.

**`input("prompt")` becomes two statements.** `trace "prompt"` then `jackin`.
This is only valid when `input(...)` is the entire right-hand side of an
assignment; anywhere else — nested in a larger expression — it is refused,
because one expression cannot become two statements mid-expression.

**A name first bound inside a loop or an `if` has its `construct` hoisted.**
MatrixLang needs `construct` to declare and bare assignment thereafter, and
**`construct` inside a loop body fails on the second iteration** with `'x' is
already declared`, while **`construct` inside an `if` branch only runs when that
branch is taken** — so the other branch's assignment, and every read after the
`if`, fail with `'x' is not declared`. Both are the same problem: a declaration
sitting somewhere that does not run exactly once. So the declaration is hoisted
above the loop or the `if` and initialised to `0`:

```
construct total = 0       ← hoisted, not written by the reader
construct n = 0
dejavu n < length xs
  total = total + xs[n]
  n = n + 1
flatline
```

`0` is safe as a placeholder: MatrixLang assignment may change a value's type,
verified against the real interpreter. This is the one place output appears
that the reader did not write, so it is documented in the tutorial.

Hoists nest — an `if` inside a `for` hoists first, then the loop hoists what the
`if` left behind — and a placeholder met a second time is **moved**, not
rewritten in place. Left behind as `s = 0` at the top of the loop body it would
reset, on every pass, a name the Python expects to survive from the iteration
that set it.

The hoist has one accepted cost, and it is the same one for both constructs:
where the Python would have raised `NameError` — `if c: s = 1` with `c` false,
then reading `s` — the reader gets the placeholder `0` instead of an error. That
divergence exists only on Python that is already broken, and there is no
MatrixLang value that means "not bound yet" to use instead.

### Counter naming

Collect every name the Python module binds — assignments, parameters, function
names, loop targets, and the targets of refused constructs. Take the first of
`n`, `n1`, `n2`, … not in that set. Nested loops take successive names.
Deterministic, and cannot collide with the reader's own names.

### Refused, each naming a fix where one exists

`class`, `import`, `try`/`except`/`raise`, `lambda`, `yield`, `with`, `global`,
`assert`, `del`, `break`, `continue`, `pass`, comprehensions and generator
expressions, `None`, float literals, tuples, sets, slicing, chained comparison
(`a < b < c`), multiple assignment (`a = b = 0`), tuple unpacking, `print` with
zero or several arguments, f-string conversions and format specs (`{x!r}`,
`{x:>3}`), `is`, **both divisions**, and **truthiness in any condition**.

**Division, refused both ways.** MatrixLang's `/` truncates toward zero, which
is neither of Python's. Python's `/` produces a fraction MatrixLang has no value
for — `7 / 2` is `3.5` there and would be `3` here, and even `4 / 2` differs
(`2.0` against `2`). Python's `//` floors, which agrees with truncation for
non-negative operands and disagrees for negative ones (`-7 // 2` is `-4`;
`-7 / 2` here is `-3`). Which of the two a given `a // b` matches depends on the
signs of values that do not exist at translation time, so translating it would
be the same guess truthiness is refused for. Both refuse and name why.

Two refusals that follow from MatrixLang's own grammar rather than from a
missing feature:

- **`xs.append(v)` only as a statement on its own.** It becomes an assignment,
  so it cannot appear inside a larger expression the way Python allows.
- **A bare expression statement that is not a call.** MatrixLang's parser
  accepts an expression statement only when it is a call — `1 + 1` on its own
  line computes something and discards it, which the grammar treats as a
  mistake. Python permits it, so it is refused here.

Where MatrixLang has an idiom, the refusal names it. `[f(x) for x in xs]` says
to write a `dejavu` loop; `not in` says to write `unplug (d oracle key)`.

## Testing

| Layer | What is covered |
| --- | --- |
| Per construct | One test per row of the Translated table, asserting the rendered MatrixLang |
| Per refusal | One per refused construct, asserting the message names the construct, the line, and the idiom where one exists |
| Names | Counter allocation avoids every bound name; nested loops differ |
| Never raises | Invalid Python, empty input, and a file of only refused constructs all return a value |
| Glue | `translate_python` returns the wire shape and never raises |
| **Differential** | **Translate Python, run the MatrixLang, run the Python, compare output** |

The differential tests are the ones that matter. Everything else checks that
the translator produced *some* MatrixLang; only these check it produced MatrixLang
that **means the same thing**. An output that parses and runs but computes
something different is the failure mode this whole design is arranged against,
and it is the only test shape that catches it.

The students-search program that motivated dictionaries is one of these, with
its `if result:` rewritten to `if len(result) > 0:` as the translator's own
refusal instructs.

## Explicitly out of scope

- **A CLI subcommand.** `matrixlang translate file.py` is natural and cheap, but
  nothing in the motivating flow needs it and the tests call `translate()`
  directly. Worth adding once the subset has settled.
- **Type inference of any kind**, including the narrow local kind that would
  make truthiness work. That is the governing rule, not an omission.
- **Dry-running the output.** `operator/validate.py` exists and could check each
  translation, but the output parses by construction, and a runtime error
  belongs to the reader at the moment they press Run — with a position in the
  MatrixLang they can now see.
- **Scribe integration.** The two produce MatrixLang into the same editor and
  stay independent.
