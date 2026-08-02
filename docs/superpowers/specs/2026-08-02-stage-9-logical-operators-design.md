# Stage 9 Design — logical operators, as crew vocabulary

Status: Approved (brainstorm 2026-08-02)
Inputs: GitHub #48 (the f11 umbrella), language-surface spec §9 (deferred features),
D-02 (keyword-delimited constructs), D-03 (the glyph face is a view), D-05 (vocabulary
reads well or it does not ship), §4.3 (the round-trip criterion), Stage 7 design §6.1
(comparison rules go wrong quietly), Stage 8 design §6 (the obvious edit can be the
wrong one).

The language-surface spec §9 defers logical operators as *"reachable, but not needed for
Turing completeness or any demo."* That was true when it was written. Stages 7 and 8
made it false: the natural program to write over a list is a bounded search, and it
cannot be written.

Stage 9 is **`and`, `or` and `not`** under themed names. Nothing else.

## Decisions made in this brainstorm

| # | Question | Decision |
| --- | --- | --- |
| S9-1 | Themed names or plain English | **Themed**, reversing this document's own first recommendation. `true`/`false` stayed English, and the case for these was that logical conjunction has no Matrix concept behind it — see §1, which records the trade honestly rather than pretending the theming is earned. |
| S9-2 | Which words | **`splice` / `fork` / `unplug`.** The one set that behaves as a family: all three are things a crew member does to a connection. |
| S9-3 | Short-circuit | **Yes, and it is forced rather than chosen** — see §2. Without it the motivating program crashes exactly where the guard is meant to save it. |
| S9-4 | Operand types | **Boolean only**, on both sides and on `unplug`. Forced by the existing no-truthiness rule that already makes `redpill 1` an error. |
| S9-5 | Where `unplug` binds | **Looser than comparison**, as Python's `not` does — not at unary level as C's `!` does. §3 shows the C reading makes the common case unwritable. |

## 1. Vocabulary, and an honest note about it

Three new slots, drawn from the 18 free. The table goes 38 → 41, leaving 15.

| Slot | Glyph | Codepoint | Note |
| --- | --- | --- | --- |
| `splice` | `ﾁ` | U+FF81 | adjacent pair, mirroring how `[`/`]` mirror `(`/`)` |
| `fork` | `ﾂ` | U+FF82 | |
| `unplug` | `ｳ` | U+FF73 | mnemonic — "u" |

Verified free, and none of the three words appears anywhere in `src/` or `examples/`
today, so nothing is shadowed.

**The trade, recorded because it is real.** The existing keywords earn their names
because the film concept *is* the programming concept: `dejavu` is literally seeing the
same thing twice, `redpill`/`bluepill` is the choice itself, `jackout` is leaving and
coming back with something, and the crew run traces on calls in the film.

These three do not reach that bar, and the reason is specific: **the films have no
concept of logical conjunction.** `or` comes closest — "the problem is choice" is the
Architect's line and arguably the films' thesis — but a set built around `choice` would
have been three unrelated metaphors, and D-05's concern is a vocabulary that gets tiring
rather than one that reads. `splice` / `fork` / `unplug` are metaphors of connection
rather than film concepts, and they were chosen because they at least fail
*consistently*: one story to learn, not three.

Plain `and` / `or` / `not` was recommended first, on the grounds that `true`/`false`
already take that exception. It was considered and rejected in favour of consistency
with the rest of the keyword set. Recorded so the next reader sees a decision rather
than an accident.

## 2. Short-circuit, and why it is not a preference

The program this stage exists for is a bounded search:

```
construct crew = ["Neo", "Trinity", "Tank"]
construct n = 0
dejavu n < length crew splice crew[n] != "Tank"
  n = n + 1
flatline
```

At the boundary `n == length crew`, the left operand is false and the right operand is
`crew[n]` — an out-of-bounds read. Measured on the current interpreter, with `n` set to
3 against that same three-element list:

```
matrixlang: [line 3, column 11] index 3 is past the end of a list of length 3
```

So a non-short-circuiting `splice` crashes precisely when the guard is meant to prevent
the crash. Short-circuit is what makes the idiom safe, and the idiom is the feature.

`fork` short-circuits symmetrically: a true left operand means the right is never
evaluated.

### The consequence, documented rather than hidden

Short-circuit means the unevaluated operand is never type-checked:

```
false splice 1     ->  false     the right side is never looked at
true  splice 1     ->  error     1 is not a boolean
```

Whether a type error is reported depends on a value, which is unlike every other
operator in this language. Python, Java and C all behave this way and it is the price of
the guard idiom; it belongs in the tutorial as one sentence rather than being discovered.

## 3. Precedence

The ladder gains two rungs at the loose end and one in the middle:

```
expression → fork → splice → unplug → equality → comparison → term → factor → unary → call → primary
```

`fork` binds loosest, then `splice`, matching every language that has both. Both are
left-associative, like every other binary operator here.

### `unplug` reuses the node but not the level

`unplug` is a `Unary` node — the one `-x` and `length` already use — but it does **not**
sit at `_UNARY_LEVEL`. It binds looser than comparison, so:

```
unplug n == 1        parses as    unplug (n == 1)
```

The C reading (`!` at unary level) would give `(unplug n) == 1`, which is an error for
every possible `n`: either `n` is not a boolean and `unplug n` fails, or it is and the
result is a boolean being compared to an integer. **The tight binding makes the common
case unwritable**, which is what decides it. Words bind loosely; punctuation binds
tightly.

This means `render.py` has two word-prefix operators at two different levels —
`length` at `_UNARY_LEVEL` and `unplug` below equality — and the `Unary` branch must
dispatch on the operator for the level as well as for the spelling.

### The renumbering

`render._LEVEL` is the §6.4 parenthesisation contract: there is no `Grouping` node, so
this table *is* how parentheses are reconstructed. Two looser levels means every
existing entry shifts:

| Level | Operators |
| --- | --- |
| 1 | `fork` |
| 2 | `splice` |
| 3 | `unplug` (a constant, not a `_LEVEL` entry — it is unary) |
| 4 | `==` `!=` |
| 5 | `<` `>` `<=` `>=` |
| 6 | `+` `-` |
| 7 | `*` `/` |
| 8 | `_UNARY_LEVEL` |
| 9 | `_ATOM_LEVEL` = `_CALL_LEVEL` |

Every number in that table moves. §4.3's property test over 300 generated trees is the
only thing that makes a mistake here loud rather than silent, which is why §6 treats the
generator extension as load-bearing rather than optional.

## 4. What it touches

| File | Change |
| --- | --- |
| `tokens.py` | `SPLICE`, `FORK`, `UNPLUG` and three `KEYWORDS` entries |
| `glyphs.py` | three slots, 38 → 41 |
| `lexer.py` | **nothing.** Words arrive through `KEYWORDS`, and `_GLYPH_TOKENS` builds itself by walking `GLYPHS` |
| `parser.py` | two `_binary_level` rungs and a `_not` level |
| `render.py` | `_LEVEL` renumbered, two `_OPS` entries, a `Unary` branch for `unplug`'s spelling and level |
| `treeview.py` | two `_OPS` entries; the existing `Unary` case reads `_OPS[expr.op]` |
| `interpreter.py` | short-circuit evaluation — see §5 |
| `tests/treegen.py` | generate all three shapes |

No new AST node. `splice` and `fork` are `Binary`; `unplug` is `Unary`. `render._binary`
already emits `f"{left} {op} {right}"` with spaces, so only the prefix `unplug` needs the
separator handling `length` has — without it, `unplug x` renders as `unplugx` and
re-lexes as one identifier.

## 5. The hazard, measured

`_evaluate`'s `Binary` branch reads:

```python
left = self._value_of(expr.left, expr)
right = self._value_of(expr.right, expr)      # both, before dispatch
return self._binary(expr, left, right)
```

`_binary` is where `+`, `==` and the comparisons live. It is the obvious home for two new
binary operators, and **putting them there produces operators that work and do not
short-circuit.**

That failure is quiet. `true splice false` would correctly be `false`; every truth-table
test would pass; and the bounded search from §2 would crash at the boundary with an
out-of-bounds error that looks like a bug in the program rather than in the language.

Short-circuit must therefore be intercepted in `_evaluate` **before** the right operand
is evaluated — the one place an implementer adding a binary operator has no reason to
look.

This is the same shape as Stage 8 §6, where widening `IndexAssign`'s guard the way
`_element`'s was widened let a Python `TypeError` escape. Both stages have exactly one
place where the obvious edit is wrong and looks right, and in both the test that proves
it is a teeth-check rather than a truth table.

## 6. Testing

1. **The teeth-check is the hazard.** Move the operators into `_binary`, confirm the
   bounded-search test fails with an **out-of-bounds error** rather than an assertion
   mismatch, revert. A failure of the wrong kind means the test is not catching what it
   was written for.
2. **Precedence is asserted on the tree, not on a value.** `unplug n == 1` must produce
   `Unary(UNPLUG, Binary(n, EQ, 1))`. Asserting the computed result would pass under both
   readings for some inputs, which is the kind of test that cannot fail.
3. **`a fork b splice c` groups as `a fork (b splice c)`** — again on the tree.
4. **The short-circuit asymmetry is pinned:** `false splice 1` is `false`, `true splice 1`
   is an error. Both, so neither can drift.
5. **`treegen.py` gains all three shapes and the meta-test gains a case.** Every number in
   `_LEVEL` moved; the 300-seed round trip is the only guard on that, and it guards
   nothing if the generator never emits the new operators. This is load-bearing, not
   coverage-padding.
6. **Non-boolean operands are errors** on both sides of both operators and on `unplug`,
   with a message naming the type — consistent with `condition must be a boolean, got
   integer`.
7. The existing suite is the regression proof: **1,167 tests pass before this stage
   begins.**

## 7. Deliberately out of scope

- **`else if`.** Nesting a `redpill` inside a `bluepill` still works and this stage does
  not change it. Chained conditionals are a parser change with its own trade-offs.
- **`xor`, implication, or any other connective.** Two binary operators and one unary
  are what programs need; the rest is arithmetic on booleans that nobody writes.
- **Truthiness.** `splice` and `fork` take booleans, full stop. Allowing `1 splice true`
  would undo the rule that makes `redpill 1` an error, which the language has held since
  Stage 1.
- **Returning an operand rather than a boolean.** Python's `a and b` yields `b`; here
  both operands are booleans, so the result is a boolean either way and the question does
  not arise.
- **`break` and `continue`.** Short-circuit makes the bounded search writable, which is
  most of what `break` was wanted for. Whether the rest justifies a stage is a separate
  question, and a better-informed one after this ships.
