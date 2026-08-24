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
catalogue is what the translator can actually refuse — 49 entries at the time of
writing. This document is a reading of that catalogue plus judgement about
order. If the two ever disagree, the catalogue is right.

---

## What MatrixLang has today

**Types (5)** — integer, string, boolean, list, dictionary — plus agents
(functions) with closures, which the rest of this repo counts separately
from the value types

**Operators** — `+ - * /`, `== != < > <= >=`

**Keywords (24)** — `construct` `trace` `redpill` `bluepill` `dejavu`
`flatline` `true` `false` `agent` `jackout` `length` `splice` `fork` `unplug`
`jackin` `decode` `encode` `keymaker` `oracle` `fold` `trim` `cleave` `wake`
`glitch`

**Glyph budget** — 54 slots used, 2 free.

### One oddity worth knowing

**The language has `/`, and Python cannot reach it.** MatrixLang's `/` truncates
toward zero; Python's `/` is true division and its `//` floors. Neither matches,
so the translator refuses both rather than translate a silent difference.
Division exists in the language and is unreachable from the translator — which
is the strongest single argument for taking on numbers properly.

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

### 3. `in` over a list or string — #134 — *next*

`oracle` asks a *dictionary* for a key. "Is this name in this list?" — one of
the most ordinary things a beginner writes — has no MatrixLang form at all.
Today `2 in xs` translates to `xs oracle 2` and fails at runtime.

Either widen `oracle` or give it a sibling. Small, and it removes a case that
currently fails *after* translation rather than during it.

### 4. Numbers — decimals and `%` — #135

The biggest unlock and the biggest decision.

- **No decimal type.** Prices, averages, anything with a fraction. Blocked the
  products search.
- **No `%`.** Even/odd, cycling, every "every Nth" pattern.
- **Division unreachable**, per the oddity above.

The decision inside it: **binary floats or exact decimals.** Floats bring
`0.1 + 0.2 != 0.3` into a teaching language. Decimals suit money, suit this
project's temperament, and sidestep that entirely — at the cost of being less
familiar to someone arriving from Python. Worth brainstorming rather than
defaulting.

### 5. The `None` pattern — #136

`return None` plus `if result:` — a function that might not find anything, and a
test of whether it did. **This shape has blocked two real programs**, more than
any other single thing here.

Deliberately last, because it is the only item where the right answer may not be
a language change at all. MatrixLang has no null and no truthiness *by design* —
the translator's governing rule ("refuse where the difference would be silent")
leans on truthiness not existing. But the pattern is recognisable, and the
language already has an idiom for it: return an empty list, test with `len`.
A translator-side rewrite of that specific shape would fix the Python unchanged
without touching the language. It might also be too clever. That argument is
worth having after the cheap wins are in.

---

## Tier 2 — real, workaroundable, unscheduled

Slicing · tuples · `a if c else b` · comprehensions · number formatting
(`{x:.2f}`) · chained comparison (`a < b < c`) · multiple assignment · `del` ·
`**`

Each has a working substitute today. They move up if a program you actually
wanted to run gets blocked by one — that is what the register is for.

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

- **The glyph budget is finite** — 2 slots left, hand-tracked in
  `tests/test_glyphs.py` on purpose so that spending one is a decision somebody
  wrote down.

  **Item 2 is spent: `wake` and `glitch` took the two slots budgeted for it.
  Items 3 and 4 divide what remains.** Item 3 widens `oracle` rather than
  adding a sibling, so it takes none; item 4 takes the last two for `.` and
  `%`. Item 5 is translator-side and takes none. There is no margin, and
  that is the point: the table stays inside its 56-slot block, and the ceiling
  keeps the vocabulary small enough to hold in your head, which is the whole
  reason this language is worth reading. If item 4 turns out to need a third
  slot, that is a decision to take deliberately — not a shortfall to route
  around by enlarging the block.
- **D-03**: both textual faces must round-trip, `parse(lex(render_X(t))) == t`,
  and any new node type must enter `tests/treegen.py` in the same change that
  adds it. A diff that adds a node without touching treegen is incomplete —
  that has already gone wrong once here, and the property stayed green while
  proving less than it claimed.
