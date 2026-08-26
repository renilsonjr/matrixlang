# What MatrixLang Has, and What Python Programs Still Need

A working register. The playground translates Python to MatrixLang for a stated
subset; this file records what that subset covers today, what it does not, and
the order we intend to close the gaps.

**The queue on GitHub:** each item below has an issue — #132 through #136 — so
the order is visible without reading this file. The issues carry the same
reasoning; this file carries the ordering and the constraints that bind all of
them.

**How to add to it:** when a program you actually wanted to run gets refused,
find the gap below and note the program beside it. A gap that has blocked three
real programs outranks one that has blocked none, whatever either looks like on
paper.

**Where the truth lives:** `src/matrixlang/pytrans/translate.py`'s `_DESCRIBE`
catalogue is what the translator can actually refuse — 47 entries at the time of
writing. This document is a reading of that catalogue plus judgement about
order. If the two ever disagree, the catalogue is right.

---

## What MatrixLang has today

**Types (5)** — number, string, boolean, list, dictionary — plus agents
(functions) with closures, which the rest of this repo counts separately
from the value types. One number type, exact decimal: `3` and `3.0` are the
same value.

**Operators** — `+ - * / %`, `== != < > <= >=`

**Keywords (24)** — `construct` `trace` `redpill` `bluepill` `dejavu`
`flatline` `true` `false` `agent` `jackout` `length` `splice` `fork` `unplug`
`jackin` `decode` `encode` `keymaker` `oracle` `fold` `trim` `cleave` `wake`
`glitch`

**Glyph budget** — 56 slots used, 0 free. The table is closed.

### One oddity worth knowing

**The language has `/`, and Python can reach it, but not all the way.**
MatrixLang's `/` is true division, translating cleanly from Python's `/`
(#135). `//` is a different story: MatrixLang has no floor operator, and
the glyph table that would carry one is full — 56 used, 0 free — so there
is no slot left to buy one. The translator refuses `//` permanently, not
provisionally; closing this gap the way item 4 closed `/` and `%` is not
on the table without a larger glyph block.

---

## The order

Ordered by value per unit of design risk, not by how often each appears. Cheap
additions with no design argument come before expensive ones that have a real
decision buried inside them.

### 1. String methods — #132 — **done**

`fold` lower-cases, `trim` strips, and the infix `cleave` splits on a
separator. The case-insensitive matching that motivated this item is
solved — `.lower()` now translates. A version of the products search with
string prices translates, runs, and is checked against Python's in
`tests/test_pytrans_differential.py`; the literal program, with decimal
prices, still refuses on its second line — that half is still item 4.

Still refused, each with an idiom: `.upper()` (no operator, and nothing has
been blocked by it yet) and bare `.split()` (splitting on runs of
whitespace is a different operation, not a default separator).

### 2. `break` and `continue` — #133 — **done**

`wake` leaves the loop it sits in; `glitch` skips the rest of the current turn
and goes back to the loop's condition. Both are bare words on a line of their
own, like a bare `jackout`, and both belong to the **innermost** loop they sit
in — a `wake` inside a loop inside another loop leaves only the inner one.

Two rules bound the feature: outside a loop, either one is an error, and that
includes inside an agent called from a loop — the agent's body is not in the
loop, so it cannot reach out and stop the caller's. `jackout` beats both; a
`jackout` inside a loop inside an agent returns from the agent, loop and all.

The translator's Python `for` still desugars to a `dejavu` with a hidden
counter, and `continue` inside it becomes `glitch` — so the counter increment
is inserted before every `glitch` the desugaring emits, not only at the end of
the loop body, or a translated `continue` would loop forever on the same
index.

### 3. `in` over a list or string — #134 — **done**

`oracle` now asks a dictionary for a key, a list for an element and a string
for a substring, so `2 in xs` translates to `xs oracle 2` and runs to the
same answer Python gives.

The design decision was the skip: over a list, an element that cannot be
compared to the one being asked about — `["a"] oracle 1`, say — is skipped
rather than raised. That has to be order-independent, or the answer would
depend on where the incomparable element sits: raising on the first one
found would make `["a", 1] oracle 1` error while `[1, "a"] oracle 1` did
not, the same list in a different order deciding whether the program runs.

It widened `oracle` rather than adding a sibling keyword, so it cost no
glyph slot.

One case still disagrees with Python, silently. `True in [1]` is `true`
in Python, because `True == 1` there; `[1] oracle true` is `false` here,
because MatrixLang's `==` never equates a boolean with a number — the
same rule that keeps `{true: "a", 1: "b"}` as two entries rather than
one. The translator cannot refuse this program, because `True in [1]`
and `"a" in xs` are the same syntax and telling them apart would be the
type inference the translator's governing rule forbids. This is
deliberate and must not be "fixed" by making `oracle` treat `true` and
`1` as the same element — that would collapse dictionary keys instead.

### 4. Numbers — decimals and `%` — #135 — **done**

The biggest unlock and the biggest decision. The integer type is gone; the
language has one number type, `number`, and it is exact decimal, not
binary float. `3` and `3.0` are the same value, and `0.1 + 0.2` is `0.3` —
the decision landed on decimals precisely to avoid the float answer to
that question in a teaching language. Floats translate from Python
through `Decimal(str(value))`, never `Decimal(<float>)`, so the binary
expansion never enters — `Decimal(0.1)` and `Decimal(str(0.1))` are not
the same value, and only the second is what the translator emits.

- **Decimal type, shipped.** Prices, averages, anything with a fraction —
  the products search's decimal prices now translate.
- **`%`, shipped.** Even/odd, cycling, every "every Nth" pattern. Follows
  Python's sign rule, not Decimal's native one: `-7 % 2` is `1` in both
  languages now.
- **`/` reachable.** MatrixLang's `/` is true division, the same operation
  Python's `/` performs, so it translates — the old truncating `/` that
  made division unreachable (per the oddity above) is gone. The *operation*
  matches; the *result* is another instance of the divergence above, and
  deliberately so: `1 / 3` is `0.3333333333333333` in Python and
  `0.3333333333333333333333333333` here, because MatrixLang divides at 28
  exact decimal digits where Python rounds to a binary float.

`.` and `%` took the last two glyph slots: 56 used, 0 free. `//` is not
part of this — see the oddity above — and stays refused permanently, not
provisionally: there is no slot left to give it one.

### 5. The `None` pattern — #136 — **done**

`return None` plus `if result:` — a function that might not find anything, and a
test of whether it did. **This shape has blocked two real programs**, more than
any other single thing here.

Deliberately last, because it turned out to be the one item where the right
answer was not a language change at all. MatrixLang has no null and no
truthiness *by design* — the translator's governing rule ("refuse where the
difference would be silent") leans on both not existing, and neither gained a
glyph: the table stays closed at 56 used, 0 free.

What shipped instead is a better refusal. The shape used to produce two
messages, each locally correct and together misleading: the truthiness one
suggested `len(result) > 0`, which reads fine on its own but on a dict tests
how many keys it has, not whether one was found — a program that runs and
answers a different question. The translator now recognises the paired shape
and reports it as one refusal, anchored at the `return None`, that names both
ends of the rewrite: the function's contract has to change (return a list —
empty for "not found", one element for found) and the caller has to unwrap it
(`len(result) > 0`, then `result[0]`). The program stays refused either way;
only the message changed. Detection only ever *fails* to fire — if the two
halves of the shape are not both independently refused (because translation
never reached one of them), nothing is collapsed and the reader keeps every
accurate message they had.

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

Two accepted differences, both from the same mechanism. The first is the
exception that proves the governing rule: hoisting out of an `and`/`or`
operand runs a comprehension Python would have skipped. It is the only
expression position with no statement boundary to emit at.

The second is that hoisting also reorders side effects within a
statement. The loop is emitted immediately before the statement that
contains it, so anything else that statement evaluates — a call before
the comprehension in source order, say — now runs after it instead of
before. `print(g(0) + len([f(x) for x in xs]))` calls `g` then `f` in
Python and `f` then `g` in the translation. Narrowing this would mean
refusing any comprehension sharing a statement with another
side-effecting call, which is most of them, so it is accepted rather
than closed. Both differences are pinned by tests so they stay known
quantities.

---

## Tier 2 — real, workaroundable, unscheduled

Slicing · tuples · `a if c else b` · set and dict comprehensions · number formatting
(`{x:.2f}`) · chained comparison (`a < b < c`) · multiple assignment · `del` ·
`**`

Each has a working substitute today. They move up if a program you actually
wanted to run gets blocked by one — that is what the register is for.

`a if c else b` is not independent of the comprehension pass: `_Hoister`
(comprehensions.py) descends into every sub-expression, including an
`ast.IfExp`'s branches, so a comprehension inside one would be hoisted the
same as anywhere else. Nothing goes wrong today only because the
translator refuses `IfExp` outright before a hoisted comprehension there
could matter. Implementing `a if c else b` means deciding what the
comprehension pass does inside it — hoisting unconditionally would run a
comprehension from a branch that was never taken, a third accepted
difference alongside the two above, unless whoever implements it chooses
to close it instead.

---

## Tier 3 — out of scope, and that is a design

Classes · imports · exceptions · generators · `async` · `lambda` · bitwise
operators · `global`/`nonlocal` · `match` · walrus

**A toy language that stops before classes and exceptions is a decision, not a
shortfall.** Chasing full Python parity would make MatrixLang a worse teaching
language: the whole point is that a reader can hold the entire grammar in their
head. Everything above earns its place by unblocking programs a beginner
actually writes; nothing here does.

---

## How each gap gets closed

Every item follows the same cycle the rest of this project uses: brainstorm to a
spec in `docs/superpowers/specs/`, a plan in `docs/superpowers/plans/`, then
implementation with a review after each task and a whole-branch review before
the pull request.

Two constraints bind every one of them:

- **The glyph budget is full** — 56 used, 0 free, hand-tracked in
  `tests/test_glyphs.py` on purpose so that spending the last slot was a
  decision somebody wrote down.

  **Item 2 spent two: `wake` and `glitch` took the two slots budgeted for
  it. Item 3 spent none: it widened `oracle` rather than adding a
  sibling. Item 4 spent the last two, for `.` and `%`.** There is nothing
  left to spend. Item 5 is translator-side and needs none — the pattern
  it addresses is a rewrite of existing syntax, not a new keyword or
  operator. Every future addition to this register now has exactly three
  routes, not four: **reuse an existing word** the way item 3 widened
  `oracle`, **live entirely in the translator** the way item 5 is
  planned to, or **argue for a larger glyph block** — which is a real
  design decision against D-03, not a formality, since it changes what
  "the table" means everywhere this document and the source both call it
  finite. Nothing in this queue currently needs that argument; `//`
  stays refused rather than being the occasion for it (see the oddity
  above).
- **D-03**: both textual faces must round-trip, `parse(lex(render_X(t))) == t`,
  and any new node type must enter `tests/treegen.py` in the same change that
  adds it. A diff that adds a node without touching treegen is incomplete —
  that has already gone wrong once here, and the property stayed green while
  proving less than it claimed.
