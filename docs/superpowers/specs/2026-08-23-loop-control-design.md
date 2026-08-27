# Loop Control — Design

**Date:** 2026-08-23
**Status:** Approved, ready for an implementation plan
**Issue:** #133
**Register entry:** `docs/PYTHON-PARITY.md`, item 2

## Why

MatrixLang has **no loop control at all.** Every search loop must run to the
end even after it has found what it wanted.

```python
for book in books:
    if book["id"] == wanted:
        found = book
        break          # refused
```

Today the refusal says a `dejavu` leaves only by its own condition, which is
honest but is not what the reader's Python said. The workaround — restructuring
around a sentinel in the loop condition — is a rewrite of their logic, not a
translation of it. `continue`'s current idiom is to wrap the rest of the body in
a `redpill`, which nests the code one level deeper every time.

## The two statements

```
wake       # leave the innermost loop entirely
glitch     # skip to the innermost loop's next iteration
```

`wake` because waking up is how you leave the Matrix, and the two obvious
alternatives — `unplug` and `jackout` — are both already taken by other
meanings.

`glitch` because the film says a déjà vu **is** a glitch in the Matrix. The loop
keyword is `dejavu`, so the word for "make the same loop happen again" was
already sitting in the vocabulary. The pairing is the rare case where the
metaphor does the teaching.

Both are **bare keywords taking no operand** — the shape bare `jackout` already
has (`parser.py:328`). Both are **statements**, not expressions, so neither can
appear inside a condition or on the right of an `=`.

## Cost

**Two glyph slots. 52 → 54 used, 4 → 2 free.**

That leaves exactly the two slots register item 4 needs for `.` and `%`, with
nothing spare. This is deliberate: the budget ruling for the remaining queue is
to keep the 56-slot block and spend carefully — item 3 widens `oracle` rather
than taking a slot, and item 4 takes the last two.

**Two new AST node types**, `Wake` and `Glitch`, both `Stmt`. This is the first
change since dictionaries to add node types rather than reuse `Unary`/`Binary`.

## The trap

**Both node types must enter `tests/treegen.py` in the same change that adds
them, and the corpus must be counted.**

The 300-seed round-trip property only covers node shapes the generator produces.
This has gone wrong three times now: `decode` and `encode` sat outside the
property for their entire existence while it stayed green; the hole reopened one
level down when dictionaries landed; and the string-methods branch shipped a
`_ATOM_LEVEL` that could be set wrong with all 1873 tests still passing, because
treegen never builds a unary callee.

A statement node is a shape treegen must generate inside a `While` body
specifically — a `Wake` at the top level of a program is not the interesting
case and would not exercise the render nesting.

## Mechanism

Exception-shaped signals caught by the `While` executor, copying `_Jackout`'s
design at `interpreter.py:152` — including its rationale for deliberately not
being a `MatrixLangError`, so a stray `except MatrixLangError` can never swallow
one.

```python
while self._condition(stmt.condition):
    try:
        for child in stmt.body:
            self._execute(child)
    except _Glitch:
        continue
    except _Wake:
        break
```

### What follows from that shape

- **`wake` leaves only the innermost loop**, as Python's `break` does. Nesting
  falls out of the `try` sitting inside the loop rather than around it.
- **Outside any loop, both are a positioned `RuntimeErrorML`** —
  `'wake' outside a loop` — mirroring `'jackout' outside an agent` at
  `interpreter.py:210`.
- **`jackout` beats both.** A `jackout` inside a loop inside an agent unwinds
  past the loop to the call site. Free, because only `_Glitch` and `_Wake` are
  caught here.
- **An agent boundary stops both.** A `wake` in an agent called from inside a
  loop must not break the caller's loop. It is outside a loop in its own body,
  so it errors — which is what Python does too.
- **The step limit is untouched.** Steps count executed statements
  (`interpreter.py:228`), so neither keyword can loop without being counted.

## The translator

`ast.Break` → `Wake`, `ast.Continue` → `Glitch`, and both lose their entries
from the refusal catalogue.

Python's own parser rejects `break` outside a loop with a `SyntaxError`, so
`ast.parse` never hands the translator that case.

`for ... else` and `while ... else` are **already refused** (`translate.py:462`
and `:248`). This closes the one interaction where adding `break` would
otherwise silently change meaning, since Python's loop-else runs only when no
`break` fired.

> **Reversed 2026-08-26.** Once `break` existed, this interaction was already
> handled rather than unhandled, and support for `for ... else` / `while ...
> else` shipped. See `docs/superpowers/specs/2026-08-26-loop-else-design.md`.

### The `for` collision, and the rewrite

MatrixLang has no `for`. The translator desugars Python's into a counter plus
`dejavu`, appending the increment to the **end** of the body
(`translate.py:583`). A `glitch` jumps to the condition, so it would skip that
increment and spin until the step limit — on a loop the reader wrote correctly.

The fix belongs to the translator, which owns the desugaring:

> Walk this loop's **already-translated MatrixLang** statements. Descend into
> `If.then_body` and `If.else_body`. **Stop at `While` and `FunctionDef`.**
> Insert `Assign(counter, counter + 1)` immediately before every `Glitch` found.

Walking the translated output rather than the Python AST is what makes the
boundary rule fall out for free:

- A **nested Python loop** is already a `While` node when the outer walk reaches
  it, so its `glitch` sits behind the stop and keeps the increment its own
  translation inserted.
- A **Python `while`** needs no increment at all, and stopping at `While` gives
  that too.
- A **nested `for` in a `for`** gets the inner counter incremented by the inner
  translation and the outer one left alone.

One rule, three cases.

`wake` needs no rewrite: it leaves the loop, so a skipped increment is exactly
right.

Emitted shape:

```
dejavu n < length xs
  redpill xs[n] == ""
    n = n + 1
    glitch
  flatline
  trace xs[n]
  n = n + 1
flatline
```

Loops with no `glitch` in them keep byte-for-byte the output they produce today.
That matters because the playground shows this code to the reader.

## Testing

| Layer | What is covered |
| --- | --- |
| Lexer | both keywords, in the ASCII and glyph faces |
| Parser | both as bare statements; both refused where an expression is required |
| Interpreter | each in a `dejavu`; nesting; outside a loop; `jackout` unwinding past a loop; an agent boundary stopping both |
| Render | both in both faces, inside a loop body |
| Property | round trip over 300 seeds **with both in treegen, inside `While` bodies**, counted |
| Glyph budget | 52 → 54 slots, 4 → 2 free, hand-tracked |
| Translator | `break` → `wake`, `continue` → `glitch`; both refusal-catalogue entries removed |
| **Differential** | **the four cases below** |

### The four cases that carry the risk

Each is a differential test — run the Python, run the translation, compare
stdout. A wrong counter produces a plausible loop that skips or repeats an
element, which no structural assertion on the output text would catch.

| Case | What it catches |
| --- | --- |
| `glitch` in a `for` body, nested two `if`s deep | the walk not descending far enough |
| `glitch` in a Python `while` nested inside a `for` | the walk descending too far and double-incrementing |
| nested `for` in `for`, `glitch` in the inner | the wrong counter being incremented |
| `wake` in an agent called from inside a loop | the caller's loop breaking when it must not |

## Explicitly out of scope

- **Labelled break**, or breaking more than one level. Python has neither.
- **`for ... else` / `while ... else`.** Already refused, and this change does
  not alter that.
  (**Reversed 2026-08-26** — see `docs/superpowers/specs/2026-08-26-loop-else-design.md`;
  a later change added support.)
- **`wake`/`glitch` as expressions.** They are statements. `construct x = wake`
  is a parse error.
- **Anything about `in` over a list, or numbers.** Register items 3 and 4, each
  with its own issue.
