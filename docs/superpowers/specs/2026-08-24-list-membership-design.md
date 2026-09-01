# `oracle` Over Lists and Strings — Design

**Date:** 2026-08-24
**Status:** Approved, ready for an implementation plan
**Issue:** #134
**Register entry:** `docs/PYTHON-PARITY.md`, item 3

## Why

`oracle` asks a **dictionary** for a key. "Is this name in this list?" — one of
the most ordinary things a beginner writes — has no MatrixLang form at all.

That would be an ordinary gap, except for how it fails. `2 in xs` **translates
today**, to `xs oracle 2`, and then dies on Run:

```
'oracle' takes a dictionary, got list
```

The translator cannot refuse it, because `k in d` and `2 in xs` are
syntactically identical and telling them apart needs the type inference its
governing rule forbids. So this is one of the few places where a reader gets a
translation that looks fine and fails at runtime, naming an operator they never
typed.

That makes it worth more than its size suggests.

## What `oracle` becomes

One operator, three containers, one question — *does this hold that?*

| Left | Asks | `right` must be |
| --- | --- | --- |
| dictionary | is this a key? | a string or a number — unchanged, `check_key` |
| list | is this an element? | anything |
| string | is this a substring? | a string |

`oracle` stays infix at the comparison rung (`parser._COMPARISON_OPS`), stays a
`Binary` node, and **costs no glyph slot.** That is what leaves the last two
slots for register item 4's `.` and `%`.

The type error changes from `'oracle' takes a dictionary, got integer` to name
all three containers, because a dictionary is no longer the only right answer.

## The two decisions

Both were live questions with defensible answers on either side. Both are
written down here because the code alone will not explain them.

### A list skips what it cannot compare

```
["a"] oracle 1      -> false, NOT an error
```

MatrixLang's `==` **raises** on mismatched types — `values._equal` throws
`Incomparable` rather than returning false, and that choice is defended at
length where it lives. Python's `in`, by contrast, simply returns `False` for
`1 in ["a"]`.

`oracle` follows Python here, and the justification is that it asks a
**different question from `==`**. "Does this list contain the integer 1?" has a
truthful answer even when "is this string equal to that integer?" does not — the
list contains a string, so no, it does not contain that integer.

**This is the one place in the language where a type mismatch declines to raise
where `==` would.** Said plainly so the next reader does not "correct" it.

The alternative was rejected for a specific reason rather than on taste. A scan
that raises on the first incomparable element makes the answer depend on
element **order**:

```
["a", 1] oracle 1   -> would ERROR   (stops at "a")
[1, "a"] oracle 1   -> would be true (finds 1 first)
```

The same list, reordered, decides whether the program runs. A teaching language
cannot defend that.

### A string is text here, and characters everywhere else

```
"matrix" oracle "rix"   -> true
```

though `"rix"` is not one of its characters, and `length "matrix"` is 6, and
`"matrix"[0]` reads exactly one character. Everywhere else in the language a
string is a sequence of characters. Here it is text.

The inconsistency is real and bought deliberately: substring is what Python
does, so `if "@" in email:` — genuinely common — translates correctly, and the
translator **cannot tell a string from a list** to warn anyone if the two
disagreed.

Edges, taken from CPython rather than assumed:

| Expression | Result |
| --- | --- |
| `"matrix" oracle "rix"` | `true` |
| `"matrix" oracle "m"` | `true` |
| `"matrix" oracle ""` | `true` — every string contains the empty string |
| `"matrix" oracle 1` | **error** — CPython raises `TypeError` |

The empty-string case is worth noting beside `cleave`, which **refuses** an
empty separator. The two are not inconsistent: CPython itself raises for
`"abc".split("")` and returns `True` for `"" in "abc"`, so each operator follows
the language it is being matched against.

## What the translator gains

**The translator's own code does not change.** `translate.py`'s `_compare`
already maps `ast.In` onto `Binary(right, ORACLE, left)`.

What changes is that the mapping stops being wrong for two of the three cases:

| Python | MatrixLang | Today |
| --- | --- | --- |
| `k in d` | `d oracle k` | works |
| `2 in xs` | `xs oracle 2` | translates, then dies on Run |
| `"@" in email` | `email oracle "@"` | translates, then dies on Run |

`not in` **stays refused** — MatrixLang has no negated form and this change does
not add one. Its idiom currently reads `write \`unplug (d oracle key)\``, which
names a dictionary; the wording widens to cover all three containers.

## Cost

**Zero glyph slots. No new AST node types. No new keywords.** The parser,
lexer, renderer, tree view and `treegen` are all untouched — `oracle` is
already a `Binary` at a settled precedence, and this changes only what the
interpreter does when it evaluates one.

That makes this the cheapest item in the register, and the only one that closes
a real failure without spending anything.

## Testing

| Layer | What is covered |
| --- | --- |
| Interpreter | each container type; every refusal; the two decisions above |
| Edges | `""` on both sides; an empty list; an empty dictionary; a one-character string |
| Regression | every existing dictionary `oracle` test still passes unchanged |
| **Differential** | **`in` over a list and over a string, run against Python** |

The differential tests are the ones that matter. They translate a Python
program, run both sides, and compare stdout — the only tests that can catch an
`oracle` that returns a plausible boolean for the wrong reason.

Cases that carry the risk:

| Case | What it catches |
| --- | --- |
| `x in xs` where `xs` holds mixed types | the skip decision, and order-independence |
| `"ab" in s` | substring rather than character |
| `"" in s` | the empty-string edge |
| `k in d` on a dictionary | that widening did not break the original meaning |

Each mixed-type case must be run **in both element orders**, since
order-independence is the whole reason the skip decision was made.

## Explicitly out of scope

- **`not in`.** Still refused, with a widened idiom. Adding a negated form
  would cost a glyph slot the register has already allocated elsewhere.
- **`oracle` on an agent.** An agent is not a container; it stays an error.
- **Anything about numbers.** Register item 4, with its own decision inside it.
- **Making `==` return false on mismatched types.** The opposite of what this
  spec decides, and a much larger change to a rule the language deliberately
  made.
