# String Methods — Design

**Date:** 2026-08-22
**Status:** Approved, ready for an implementation plan
**Register entry:** `docs/PYTHON-PARITY.md`, item 1

## Why

MatrixLang has strings and **no way to change their case, trim them, or split
them.** `.append()` is the only Python method the translator handles, and it is
really list concatenation wearing method clothes.

A reader pasted a product search:

```python
if search_term == str(product["code"]) or search_term.lower() == product["name"].lower():
```

and got

```
line 11: `.lower()` cannot be translated as a value
```

Case-insensitive comparison is one of the most ordinary things a beginner
writes, and there is no MatrixLang form for it at all. This is the gap most
likely to surprise someone who assumes a language with strings can work with
them.

It is first in the register because it is pure addition — no design tension, no
decision buried inside it, unlike numbers.

## The three operations

```
fold s          # "Mouse" -> "mouse"
trim s          # "  hi  " -> "hi"
s cleave sep    # "a,b,c" cleave "," -> ["a", "b", "c"]
```

`fold` and `trim` are **unary**, like `length` and `keymaker`. `cleave` is
**infix binary**, like `oracle` and `splice`.

MatrixLang has no objects, so these are keyword operators rather than methods.
That is not a choice — attribute access does not exist in the language, which is
why the translator already special-cases `.append()`.

All three take strings. Anything else is a positioned `RuntimeErrorML` naming
the operator and the type it got, in the shape every other type error in
`interpreter.py` uses.

### `fold` is `.lower()`, not case-folding

Despite the name. The distinction is real and was checked:

```
"STRAßE".lower()    -> "straße"
"STRAßE".casefold() -> "strasse"
```

The translator maps Python's `.lower()` onto `fold`, so `fold` must be
`str.lower()` for the two to agree. Written down here precisely because the name
suggests otherwise, and a future reader "correcting" it to `casefold` would
break agreement with Python silently.

### `cleave`'s edges, taken from Python

Each verified against CPython rather than assumed:

| Expression | Result |
| --- | --- |
| `"a,,b" cleave ","` | `["a", "", "b"]` — empties kept |
| `"" cleave ","` | `[""]` — one empty string, **not** an empty list |
| `"abc" cleave ","` | `["abc"]` — separator absent, whole string back |
| `"abc" cleave ""` | **error** — CPython raises `ValueError: empty separator` |

The empty-separator case becomes a positioned language error, not a Python
exception escaping.

## Precedence

The existing ladder:

```
_fork → _splice → _not → _equality → _comparison → _term → _factor → _unary
```

**`fold` and `trim` join `_unary`**, beside `length`, `decode`, `encode` and
`keymaker`. They PRODUCE a value that later operations consume, which is the
stated reason those four sit there rather than at `_not`'s level.

**`cleave` gets its own rung between `_comparison` and `_term`.** That placement
makes both natural readings come out right with no parentheses:

| Written | Parses as | Why |
| --- | --- | --- |
| `s cleave "," == xs` | `(s cleave ",") == xs` | comparison is looser |
| `a + b cleave ","` | `(a + b) cleave ","` | `+` is tighter: concatenate, then split |

`length (s cleave ",")` still needs its parentheses, because `length` binds
tightest. That is the same shape `length keymaker d` already has.

## Cost

**Three glyph slots. Seven free before, four after.** `tests/test_glyphs.py`
tracks this by hand on purpose, so its ledger gains the step `7 → 4` and its
slot count goes 49 → 52.

**No new AST node types.** `fold` and `trim` are `Unary`; `cleave` is `Binary` —
exactly as `keymaker` and `oracle` were. The translator adds no node types
either.

## The trap

**All three must enter `tests/treegen.py` in the same change that adds them.**

The 300-seed round-trip property only covers node shapes the generator produces.
This has gone wrong here twice: `decode` and `encode` sat outside the property
for their entire existence while it stayed green, and the same hole reopened one
level down when dictionaries landed. A diff that adds an operator without
touching treegen is incomplete, and a reviewer should treat it as such.

`fold` and `trim` go in the unary-operator list beside `LENGTH` and `KEYMAKER`;
`cleave` goes in `_BINARY_OPS`. Then the corpus must be **counted**, not assumed
— the count is the evidence, and a zero means the property is green while
proving nothing about that operator.

## What the translator gains

| Python | MatrixLang |
| --- | --- |
| `s.lower()` | `fold s` |
| `s.strip()` | `trim s` |
| `s.split(sep)` | `s cleave sep` |

Two things it must still **refuse**, each with an idiom:

- **`.upper()`** — there is no keyword for it. For comparison, `fold` on both
  sides is the answer and the refusal should say so. For display, upper-casing
  is genuinely missing and the refusal should admit that rather than pretend
  `fold` substitutes.
- **bare `.split()`** — Python splits on *runs* of whitespace and discards
  empty strings, which is different behaviour rather than a missing argument.
  Translating it to `cleave " "` would be silently wrong, which is exactly what
  the translator's governing rule forbids.

Other string methods (`.replace()`, `.startswith()`, `.join()`, `.find()`) keep
refusing as they do today. They are not in this change.

## Testing

| Layer | What is covered |
| --- | --- |
| Lexer | the three keywords, in both the ASCII and glyph faces |
| Parser | `fold`/`trim` at `_unary`, `cleave`'s rung against `==` and `+` |
| Interpreter | each operation on a string; each refusing every non-string type; `cleave`'s four edge cases; the empty separator |
| Render | all three in both faces |
| Property | round-trip over 300 seeds **with all three in treegen**, counted |
| Glyph budget | 49 → 52 slots, 7 → 4 free, hand-tracked |
| Translator | `.lower()`, `.strip()`, `.split(sep)` map correctly; `.upper()` and bare `.split()` refuse with idioms |
| **Differential** | **the products program with `.lower()` restored, run against Python** |

The differential case is the one that matters. Everything else proves the
operators return something; only that proves a reader's Python and its
translation print the same text.

`cleave`'s edge cases are checked **against what CPython actually does**, not
against the table above — the table is this document's reading of CPython and
could be wrong.

## Explicitly out of scope

- **`.upper()`** — refused, as above. It costs a fourth glyph slot and nothing
  has been blocked by it. It moves up the register the day a real program needs
  it.
- **`.replace()`, `.join()`, `.startswith()`, `.find()`, indexing by substring.**
  Same reasoning.
- **Splitting on whitespace runs**, Python's bare `.split()`. It is a different
  operation from separator-splitting, not a default for one.
- **Anything about numbers.** Register item 4, with its own decision inside it.
