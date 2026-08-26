# List comprehensions — Design

**Date:** 2026-08-26
**Status:** Approved, ready for an implementation plan
**Scope:** Translator only. No language change.

## Why

`[f(x) for x in xs]` is among the most common things in ordinary Python, and
the translator refuses it. Nothing about it is hard to express in
MatrixLang — the language already has everything needed, and the
translator's own `for` desugaring already emits the exact shape a
comprehension needs.

Verified before designing anything, `out = out + [x * 2]` inside a `for`
already produces:

```
construct out = []
construct n = 0
dejavu n < length xs
  redpill xs[n] > 2
    out = out + [xs[n] * 2]
  flatline
  n = n + 1
flatline
```

That is a list comprehension, written the long way. The work is turning one
into the other.

## What this is not

**Not a language change.** No new keyword, no new type, no glyph. The table
is closed at 56 used, 0 free, and this needs none of it.

**Not a new translator path.** The rewrite happens in Python AST space
before translation, so `_Translator` never learns what a comprehension is.

## Scope

**In:** one `for` clause, zero or more `if` clauses, in any expression
position, including nested inside another comprehension.

**Out:** multiple `for` clauses in one comprehension
(`[f(x, y) for x in xs for y in ys]`), set comprehensions (there is no set
type), dict comprehensions, and generator expressions. All keep their
present refusals.

## The pass

A new module, `src/matrixlang/pytrans/comprehensions.py`, matching how
`names.py` already holds `bound_names`:

```
rewrite_comprehensions(tree: ast.Module, taken: set[str]) -> ast.Module
```

Python in, Python out. It runs in `translate()` after `ast.parse` and
before `_Translator` is constructed, so the walker only ever sees
constructs it already handles.

`taken` is the existing `bound_names(tree)`, so invented temporaries cannot
collide with the reader's names. Each name the pass invents is added to
that set as it goes, so two comprehensions in one program get `_c0` and
`_c1` rather than both getting `_c0` — the set is the pass's running
record, not a fixed snapshot.

Being source-to-source makes it testable with no translator involved:
parse, rewrite, `ast.unparse`, compare. A failure says "the rewrite is
wrong" rather than "something downstream broke".

## The rewrite

For each statement containing a comprehension, the loop is emitted
immediately before that statement and the expression is replaced by a name:

```python
print([f(x) for x in xs if c])
```

becomes

```python
_c0 = []
for _i0 in xs:
    if c:
        _c0 = _c0 + [f(_i0)]
print(_c0)
```

Emitting immediately before the containing statement — rather than at the
top of the enclosing block — is load-bearing, and does more than it looks.

Inside a loop body it keeps the comprehension in the loop, so it re-runs
each turn. Inside a conditional body it keeps it in the branch, so

```python
if c:
    out = [f(x) for x in xs]
```

does not call `f` when `c` is false. That is the same hazard class as the
short-circuit difference accepted below — and it is closed for free by
emitting in place rather than at the top of the block. The accepted hole
is genuinely only `and`/`or` operands, where the two sides are one
expression and there is no statement boundary to emit between.

### The loop variable must be renamed

This is not cosmetic. In Python 3 a comprehension has its own scope and its
variable does not leak. A naive rewrite to a `for` loop leaks it:

```python
x = 5
out = [x for x in [1, 2, 3]]
print(x)        # Python: 5.  Naive rewrite: 3.
```

So the rewrite substitutes a fresh `_i0` for the comprehension's variable
throughout the element and condition expressions. Unlike the difference
accepted below, this one buys nothing and is simply a bug.

### Multiple `if` clauses nest

`[f(x) for x in xs if c1 if c2]` becomes `if c1:` containing `if c2:`,
rather than `if c1 and c2:`. One less expression to build, and it does not
evaluate `c2` when `c1` is false.

### Nested comprehensions recurse

`[[y for y in row] for row in rows]` is two comprehensions, each with one
`for`. The inner one is rewritten inside the generated loop body,
innermost-first.

### Positions

Every generated node carries `ast.copy_location` from the node it came
from, so a refusal raised inside a comprehension still points at the
reader's line rather than at invented code.

## The accepted difference

Hoisting is allowed in every expression position, **including operands of
`and` and `or`**. That is a deliberate exception to the translator's
governing rule — refuse where the difference would be silent — taken with
the cost understood:

```python
c and [f(x) for x in xs]
```

Python skips the comprehension entirely when `c` is false. The hoisted
rewrite runs it first, so `f` is called either way. If `f` has side
effects, the translated program does something the original did not.

It is a narrow hole. `and`/`or` with a list operand is unusual Python, and
MatrixLang's `splice` requires boolean operands, so such a program would
likely fail at runtime regardless.

**It is pinned by a test** — not one asserting the behaviour is correct,
but one asserting it is *this*, so the difference stays a known quantity
rather than something a later reader mistakes for a bug and "fixes" into an
inconsistency.

## Testing

The rewriter is tested as a source-to-source function. The cases that carry
weight:

- the basic form; with one `if`; with two `if`s, nesting rather than combining
- **the loop variable does not leak** — the trap above
- **invented names avoid the reader's** — a program already using `_c0` or
  `_i0` gets different temporaries
- a comprehension as a call argument, in a return, and inside a loop body
- **nested comprehensions**, innermost-first
- the accepted short-circuit difference, pinned as described

Then a smaller end-to-end set through `translate()`, confirming the emitted
MatrixLang actually runs and produces the right answer — this project's
standard being that examples ship executed rather than asserted.

The existing refusal tests are the regression net: every program containing
no comprehension must translate exactly as it does today.

## Cost

Zero glyph slots. One new module, one call in `translate()`, no change to
`_Translator` and no change to the language.
