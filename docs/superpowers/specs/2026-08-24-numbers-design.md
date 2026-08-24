# Numbers — Design

**Date:** 2026-08-24
**Status:** Approved, ready for an implementation plan
**Issue:** #135
**Register entry:** `docs/PYTHON-PARITY.md`, item 4

## Why

Three holes, one root.

**No decimal type.** Prices, averages, anything with a fraction. A reader's
product search died on its second line:

```
line 2: a float cannot be translated — MatrixLang has no floats; use whole numbers
```

The workaround was storing prices as strings, which works only until you add two
of them.

**No `%`.** Even and odd, cycling, every "every Nth" pattern.

**Division exists and Python cannot reach it.** MatrixLang's `/` truncates
toward zero; Python's `/` is true division and its `//` floors. Neither matches,
so the translator refuses both. The language has an operator no Python program
can use.

This is the last language change in the register, and it spends the last two
glyph slots.

## Four decisions

Each was a live question. Each is recorded here with the reasoning, because the
code will not explain any of them.

### 1. Exact decimals, not binary floats

```
0.1 + 0.2   ->  0.3          not 0.30000000000000004
```

Floats would have given **perfect** Python parity — both sides wrong in the same
way, every differential test passing unchanged. Decimals were chosen anyway,
because this language's whole claim is that a reader can predict what it does,
and `0.30000000000000004` breaks that claim on the first program anyone writes
with money in it.

The price, stated plainly:

- `1 / 3` gives 28 significant digits where Python's float gives 16. **This
  diverges from Python in the most ordinary operation there is.**
- Trailing zeros are significant: `2.50 * 2` is `5.00`, not `5.0`.

### 2. `/` becomes true division

```
7 / 2    ->  3.5     was 3
-7 / 2   ->  -3.5    was -3
```

**This is a breaking change to specified behaviour.** `tests/test_interpreter.py`
pins `7 / 2 == 3` today, with a comment citing the spec. That test, that spec
line, and any program relying on truncation all change.

It is also the only thing that closes this item's stated goal. `Decimal(-7) /
Decimal(2)` is exactly `-3.5`, matching Python's `/` on every input including
negatives, so the oddity the register has carried since division existed
disappears.

**Integer division leaves the language.** There is no floor operator and no slot
to buy one — `.` and `%` take both remaining. A reader computing
`length xs / 2` for a midpoint index gets `1.5` and an error from indexing
rather than a silent truncation, which is the honest outcome but is a real loss
for anyone writing a binary search.

### 3. One number type

Every number is a `decimal.Decimal`. `3` and `3.0` are the same value.

The alternative — integers and decimals as separate types — is a much smaller
diff, but it adds rules a reader must learn rather than removing them: what
`1 + 1.5` promotes to, whether `1.5` may be a dictionary key, and whether
`1 == 1.0` is true. That last one is decisive: `values._equal` raises
`Incomparable` on mismatched type names, so `1 == 1.0` would be an **error**
where Python says `True` — the exact class of trap the previous branch spent its
entire review budget on.

With one type, `Decimal(1) == Decimal("1.0")` is `True` and they hash equal,
matching Python, and `{1: "a", 1.0: "b"}` collapses to one entry exactly as it
does in Python.

**Whole numbers still print as whole numbers.** `str(Decimal(3))` is `"3"`, so
no existing program's output changes.

### 4. `%` follows Python's rule, not Decimal's

```
-7 % 2   ->  1      Python's answer
```

Decimal's native `%` follows the **dividend's** sign and gives `-1`; Python's
follows the **divisor's** and gives `1`. The translator maps `a % b` straight
through and cannot see signs, so Decimal's rule would be a silent disagreement
with Python on every negative operand — precisely what the governing rule
forbids.

The implementation is `a - floor(a / b) * b`, verified against Python on every
sign combination and on non-whole operands:

| Expression | Python | Decimal's native `%` | Ours |
| --- | --- | --- | --- |
| `-7 % 2` | `1` | `-1` | `1` |
| `7 % -2` | `-1` | `1` | `-1` |
| `7 % 2` | `1` | `1` | `1` |
| `-7 % -2` | `-1` | `-1` | `-1` |
| `7.5 % 2` | `1.5` | — | `1.5` |
| `-7.5 % 2` | `0.5` | — | `0.5` |

## The type name

**`number`.** One type, one word, everywhere.

`integer` becomes false the moment `1.5` exists. `decimal` is accurate but reads
as jargon in a teaching language — `'fold' takes a string, got decimal` is worse
than `got number`.

Reporting `integer` for whole values and `decimal` otherwise was considered and
rejected: it makes `type_name` answer "what does this look like?" instead of
"what is this?", which misleads exactly when someone is debugging a number that
is not the shape they expected.

**57 test assertions across 8 files name `"integer"`** and move with it.

## Cost

**Both remaining glyph slots. 54 → 56 used, 2 → 0 free.**

- `.` takes **`ｰ`** (U+FF70). The string-methods branch recorded that this slot
  was passed over because "a prolonged-sound mark reads as punctuation rather
  than a word" — which is exactly what a decimal point is.
- `%` takes **`ﾝ`** (U+FF9D).

**After this the 56-slot block is full and the vocabulary is closed.** Every
later addition must either reuse an existing word, live in the translator, or
argue for a larger block.

## The literal form

**Digits are required on both sides of the point.** `0.5` is a number; `.5` and
`1.` are lex errors.

Python accepts both of the refused forms, so this is a deliberate divergence —
but it only affects MatrixLang a reader types by hand. Translated Python is
unaffected, because the translator renders the *value* it got from `ast`, so
Python's `.5` arrives as `0.5` and works.

The reason to require both sides is `xs[0].5`, which is unreadable and which a
lexer scanning greedily would have to resolve by rule rather than by shape. One
digit on each side removes the question.

`1.2.3` is a lex error for the same reason: the scan takes at most one point.

## Two things the implementation must guard

**Scientific notation must never reach a reader.** `str(Decimal("1e3"))` is
`"1E+3"`. Display goes through a formatter that never emits an exponent, not
through `str()`.

**Digits render per-digit through the glyph table** — `10` is `ｧｦ` — so `.` joins
that path rather than being special-cased.

## The translator

Three refusals disappear: `float`, `Div` (`/`) and `Mod` (`%`).

**`FloorDiv` (`//`) stays refused.** MatrixLang has no floor operator now that
`/` is true division, so translating `//` would be a silent difference on
exactly the negative operands `%` was just made careful about.

## Testing

| Layer | What is covered |
| --- | --- |
| Lexer | decimal literals in both faces; `1.` and `.5` and `1.2.3` refused |
| Values | one type name; equality across `3` and `3.0`; hashing as a key |
| Interpreter | arithmetic, ordering, `/`, `%` on every sign combination |
| Whole-number rules | indexing, `length`, `decode`, `encode` |
| Display | no exponent form ever, at any magnitude |
| Render | decimal literals in both faces |
| Property | round-trip over 300 seeds **with decimal literals in treegen**, counted |
| Glyph budget | 54 → 56 slots, 2 → 0 free, hand-tracked |
| **Differential** | **`/`, `%` and decimal arithmetic, run against Python** |

The differential tests carry the most weight here, because `/` and `%` now agree
with Python exactly and any divergence is a bug rather than a design choice.

**Cases that must avoid Python comparison**, because they diverge by design:
`1 / 3` and anything else with no exact decimal form.

## Explicitly out of scope

- **`//`.** Refused, as above.
- **A floor or round operator.** No slot remains, and nothing has been blocked
  by its absence.
- **Number formatting** (`{x:.2f}`). Tier 2 in the register.
- **`**`.** Tier 2.
- **Enlarging the glyph block.** A separate argument, to be had if and when
  something is actually blocked by a full table.
