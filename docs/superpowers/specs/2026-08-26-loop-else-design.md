# `for ... else` and `while ... else` — Design

**Date:** 2026-08-26
**Status:** Approved, ready for an implementation plan
**Scope:** Translator only. No language change.

## Why

A book-search program written in ordinary Python was refused, and
`for ... else` was its only blocker. That is the register's own bar for
moving something up: a gap that blocked a program someone actually wanted
to run.

## Reversing a written decision

`docs/superpowers/plans/2026-08-23-loop-control.md:40` says:

> **`for ... else` and `while ... else` stay refused.** Do not add support;
> Python's loop-else runs only when no `break` fired, and that interaction
> is exactly what the existing refusals close off.

That was written while `break` and `continue` were themselves being added,
and deferring an interaction with a feature not yet finished was the right
call at the time. It does not survive contact with the shipped code.

The standard way to express loop-else — a flag set beside the `break` —
**already translates and runs correctly today**, including nested inside
another loop, which is the hardest position:

```python
for r in rows:
    broke = False
    for v in r:
        if v == t:
            broke = True
            break
    if broke == False:
        print(r[0])
```

```
construct n = 0
construct broke = 0
construct xs = 0
construct n1 = 0
dejavu n < length rows
  broke = false
  xs = rows[n]
  n1 = 0
  dejavu n1 < length xs
    redpill xs[n1] == t
      broke = true
      wake
    flatline
    n1 = n1 + 1
  flatline
  redpill broke == false
    trace rows[n]
  flatline
  n = n + 1
flatline
```

Python and MatrixLang print the same thing. `_hoist_declares` lifts the
flag out of the loop body on its own, which is the trap this project has
actually hit before.

So the interaction is not unhandled. It is unwritten. `for ... else` is
sugar over a pattern the translator already carries end to end, and this
work writes the sugar.

## What this is not

**Not a language change.** No new keyword, no new type, no glyph. The
table is closed at 56 used, 0 free, and this needs none of it.

**Not a translator change.** The rewrite happens in Python AST space
before translation, so `_Translator` never learns what a loop-else is.

## Scope

**In:** `for ... else` and `while ... else`. Both get the identical
rewrite; supporting one and refusing the other would be an incoherent
story for no saved work.

**Out:** `try ... else`, which is a different construct on a statement
that is refused wholesale.

## The pass

A new module, `src/matrixlang/pytrans/loop_else.py`, matching how
`comprehensions.py` and `names.py` already sit beside the translator:

```
rewrite_loop_else(tree: ast.Module, taken: set[str]) -> ast.Module
```

Python in, Python out. It runs inside `translate()` **before** the
comprehension pass: control flow desugars first, then expressions desugar
inside the resulting structure. Either order is correct — a comprehension
in an `else` body lands in the right place either way — but this one is
easier to reason about, and it means the comprehension pass only ever sees
loops that have no `else` left on them.

`taken` is the same shared set the other passes and the walker draw from,
so an invented flag cannot collide with the reader's names, with a
comprehension's temporaries, or with the walker's counters. Every flag the
pass invents is added to that set as it goes — it is the pass's running
record, not a snapshot, so two loop-elses in one program get `broke` and
`broke1` rather than both getting `broke`.

## The rewrite

When the loop body contains a `break` belonging to this loop:

```python
for x in xs:
    BODY
else:
    ELSE
```

becomes

```python
broke = False
for x in xs:
    BODY'          # each own break becomes: broke = True; break
if broke == False:
    ELSE
```

`while` is identical; only the loop statement differs.

The flag assignment goes immediately before the loop statement, and the
conditional immediately after it, in the same statement list — never at the
top of the enclosing block. That is the same rule the comprehension pass
follows and for the same reason: a loop-else inside a conditional must keep
its flag inside that branch, and one inside another loop must keep it in
the loop body so it resets each turn. The worked example above is exactly
that case, and it is what `_hoist_declares` then lifts.

### `broke == False`, not `not broke`

This is not style. MatrixLang has no truthiness, and the translator
refuses a bare name as a condition:

```
if not broke:   →  `broke` relies on truthiness, which MatrixLang does not have
if broke:       →  `broke` relies on truthiness, which MatrixLang does not have
if broke == False:  →  redpill broke == false
```

A rewrite emitting `not broke` would produce a program that refuses. The
comparison form is what makes the output translate.

### When there is no `break`, there is no flag

A loop-else whose body cannot `break` always runs its `else`. In that case
the `else` body is emitted directly after the loop, with no flag and no
conditional. The emitted MatrixLang is what a learner reads; a variable
that is written once, never changed, and tested to a foregone conclusion
is noise in the one artifact this project asks people to read.

### Marking "own" breaks is the whole correctness story

A `break` belongs to the nearest enclosing loop. The walk that marks
breaks therefore descends into `if`, `try` and `with` bodies, but **not**
into a nested loop's *body* — those breaks are that loop's.

That single rule is all it needs, and the next section is why. A `break`
can also reach us from inside a nested loop's `else`, which would demand a
second rule — except that by the time we look, no nested `else` exists any
more. Verified against CPython, this is the shape that would otherwise
need it:

```python
for a in [1, 2, 3]:
    for b in []:
        break
    else:
        break        # exits the OUTER loop; outer runs once
```

### Nesting falls out of the ordering, not a special case

Nested statements are rewritten before the enclosing loop looks at its own
breaks — **both the detection of whether a flag is needed and the marking
of the breaks, not just the marking.**

That ordering is what buys the single-rule walk. Rewriting an inner
`for ... else` turns it into `for` + `if broke1 == False: <else body>`,
which removes its `orelse` entirely; a `break` that lived in that `else`
now sits in an `if` at the outer level, where an ordinary walk already
goes. By induction, once the recursion has run, **no nested loop carries
an `else` at all** — so the walk never needs a rule for looking inside one,
and nesting is handled by the ordering rather than by a special case.

Reverse the order and both halves get harder: the walk would need the
second rule, and the flag-needed decision would be made against a body
that has not yet grown the `break` an inner loop-else is about to hand it.

### Positions

Every generated node carries `ast.copy_location` from the loop it came
from, with `ast.fix_missing_locations` for its children, so a refusal
raised inside a rewritten body still points at the reader's line rather
than at invented code.

### `return` needs nothing

Python skips the `else` when the loop is left by `return`. The rewrite
gets this for free: `return` leaves the function, so the trailing
conditional never runs. It is pinned by a test rather than relied on
silently.

## Testing

The rewriter is tested source-to-source with `ast.unparse`, no translator
involved, so a failure says the rewrite is wrong rather than that
something downstream broke. The cases that carry weight:

- the `else` runs on normal completion; the `else` is skipped when a
  `break` fires
- **a `break` in a nested loop must not suppress our `else`**
- **a `break` in an inner loop's `else` must set the OUTER flag**
- `return` inside the loop skips the `else`
- a body with no `break` emits the `else` with no flag at all
- a reader already using `broke` gets a different name
- `while ... else` in both states
- `continue` does not affect the `else`
- nested loop-else, both levels carrying breaks

Then `agree()` cases in `tests/test_pytrans_differential.py`, which runs
both sides and compares output — the only tests that catch a program that
parses, runs, and means something other than the Python did. These must
include **the flag inside an enclosing loop**, the `construct`-in-a-loop-body
trap this project has hit before and which `_hoist_declares` is what saves.

The existing refusal tests are the regression net: every program with no
loop-else in it must translate exactly as it does today.

## Cost

Zero glyph slots. One new module, one call in `translate()`, no change to
`_Translator`, and no change to the language.
