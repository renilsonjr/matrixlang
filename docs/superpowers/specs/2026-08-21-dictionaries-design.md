# Dictionaries — Design

**Date:** 2026-08-21
**Status:** Approved, ready for an implementation plan
**Tracking issue:** #121

## Why

MatrixLang has integers, strings, booleans and lists. It has no way to say
"this value belongs to that name inside one record." Every program that
handles a row of data has to keep parallel lists that line up by position:

```
construct ids = [1, 2, 3, 4, 5]
construct grades = ["A", "B", "A", "A", "B"]
```

`ids[n]` and `grades[n]` are one student only because a human keeps them the
same length. Nothing in the language enforces it, nothing catches a mistake,
and the shape a reader actually wrote in Python —

```python
students_data = [{"id": 1, "grade": "A"}, ...]
```

— cannot be expressed at all. That is the gap this closes. It is also the
blocker on the Python-to-MatrixLang translator (#122): a translator that
refuses a dictionary literal refuses most real Python, including the program
that prompted this work.

## Syntax

Literals use braces and colons, and lookup reuses the bracket already used for
lists:

```
construct aluno = {"id": 1, "grade": "A"}

trace aluno["grade"]            # A
aluno["grade"] = "B"            # update
aluno["turma"] = "3B"           # insert
trace length aluno              # 3
trace keymaker aluno            # ["id", "grade", "turma"]

redpill aluno oracle "turma"
  trace aluno["turma"]
flatline

construct vazio = {}
```

Nesting falls out of the existing postfix index chain:

```
construct alunos = [{"id": 1, "grade": "A"}, {"id": 2, "grade": "B"}]
trace alunos[0]["grade"]        # A
```

**One line, no trailing comma** — the same rule list literals already follow,
verified against the current parser rather than assumed:

```
construct xs = [
  1,
]
# [line 1, column 17] expected an expression, found end of line

construct xs = [1, 2,]
# [line 1, column 22] expected an expression, found ']'
```

Dictionary literals inherit that rule exactly. Allowing newlines inside
brackets is a change to how the lexer treats NEWLINE inside every bracketed
form, it would apply to lists and call arguments too, and it is worth doing on
its own terms rather than smuggled in here — see Out of scope.

**Braces cost nothing in ambiguity.** MatrixLang closes blocks with `flatline`,
not `}`, so `{` and `}` are unclaimed and `{}` is unambiguously an empty
dictionary rather than an empty block.

### `keymaker` — the key list

Prefix, one operand, at the `_unary` rung beside `length`, `decode` and
`encode` — identical to `length` in every syntactic respect. It PRODUCES a
value that later operations consume, which is the stated reason those three sit
there rather than at `_not`'s level. So `length keymaker aluno` is the entry
count of the key list, and `keymaker alunos[0]` binds its operand tightly:
`keymaker (alunos[0])`.

### `oracle` — the membership test

**Infix binary**, exactly like `splice` and `fork`:

```
trace aluno oracle "grade"      # true
redpill unplug aluno oracle "idade"
  trace "sem idade"
flatline
```

Infix rather than prefix-with-two-operands deliberately. Every keyword in the
language today is either prefix-with-one or infix-binary; a prefix keyword
taking two operands would be a new parsing shape, and every future two-operand
keyword would inherit the precedent.

**Precedence: `oracle` joins the `_comparison` rung**, beside `<`, `>`, `<=`
and `>=`. The existing ladder is

```
_fork → _splice → _not → _equality → _comparison → _term → _factor → _unary
```

and that placement is what makes the three expressions a reader will actually
write parse the way they read, with no parentheses:

| Written | Parses as | Why the rung gives this |
| --- | --- | --- |
| `unplug aluno oracle "idade"` | `unplug (aluno oracle "idade")` | `_not` sits above `_comparison` |
| `a oracle "k" splice b oracle "j"` | `(a oracle "k") splice (b oracle "j")` | `_splice` sits above `_comparison` |
| `aluno oracle "gr" + "ade"` | `aluno oracle ("gr" + "ade")` | `_comparison` takes `_term` operands |

This mirrors Python, where `in` is a comparison operator. It also means
`aluno oracle "k" == true` parses as `(aluno oracle "k") == true`, since
equality is the looser of the two rungs.

## Semantics

**Type name:** `dictionary`, joining integer, string, boolean, list in
`type_name` and therefore in every error message.

**Keys are strings or integers. Nothing else.** Booleans, lists and
dictionaries are rejected with a positioned error.

Booleans are rejected for a concrete reason, not tidiness. In Python
`True == 1` and `hash(True) == hash(1)`, so a dictionary stored the obvious way
would silently collapse `{true: "a", 1: "b"}` into a single entry — two keys a
reader wrote, one entry they get, no diagnostic. Rejecting boolean keys removes
the trap rather than papering over it. Lists and dictionaries are rejected
because they are mutable: a key that can change after insertion is a lookup
that stops working for reasons invisible at the call site.

Values have no restriction. Any MatrixLang value may be a value, including
another dictionary or a list.

**Insertion order is guaranteed.** `keymaker` returns keys in the order they
were first assigned; re-assigning an existing key does not move it. Python
dictionaries already behave this way, so this costs nothing to implement — but
it is pinned by a test rather than inherited silently, because it is
load-bearing well beyond aesthetics:

> The playground runs a program, and when it needs input it **re-runs the
> program from the start** and draws only the new suffix. That is honest only
> because MatrixLang is deterministic. A `keymaker` whose order varied between
> runs would make the second run diverge from the first, and the reader would
> watch their own output change underneath them. `tests/test_site_glue.py`'s
> determinism tests would catch it, but the failure would read as a playground
> bug rather than what it was.

**A missing key is an error**, positioned, worded like a list index out of
range:

```
no key "idade" in this dictionary
```

Not a null. The language has no null: `NOTHING` exists internally but
`interpreter.py`'s `_value_of` routes every user-visible position through a
guard specifically to keep it from leaking. Returning it for a missing key
would puncture that on purpose, and every lookup downstream would inherit a
value with no operations defined on it.

**Assignment inserts or updates.** `aluno["turma"] = "3B"` on an absent key
inserts at the end; on a present key it replaces the value and leaves the key
where it was.

**Equality is order-independent.** `{"a": 1, "b": 2} == {"b": 2, "a": 1}` is
true, matching Python and matching what a reader means by "the same record."
Note the deliberate asymmetry: those two dictionaries are equal while their
`keymaker` lists are not. That is correct — order is a property of how a
dictionary was built, not of what it contains.

**`length`** returns the entry count.

**Cycles reuse the existing machinery.** A dictionary can contain itself, the
same way a list can. `values.py` already raises `CyclicValue` for that during
display and comparison; dictionaries route through the same guard rather than
growing a second one.

## Glyph budget

Five slots: `{`, `}`, `:`, `keymaker`, `oracle`. Twelve free before, seven
after.

`tests/test_glyphs.py` tracks this by hand on purpose — the count is asserted,
not discovered, so that spending budget is a decision someone writes down
rather than a number that drifts. Its ledger comment gains the new step:

```
24 → 21 → 18 → 15 → 13 → 12 → 7
```

## Two things that would silently rot

**D-03 round-tripping.** Both textual faces must satisfy
`parse(lex(render_X(t))) == t`. `render.py` needs dictionary literals in ASCII
and glyph form, and the translit table needs the three new punctuation slots
and two new keywords.

**The `treegen` trap.** The 300-seed round-trip property only covers node
shapes `tests/treegen.py` actually generates. This has already bitten once: on
the `encode` branch, treegen was found generating three of the five unary
operators, so `decode` and `encode` had been silently excluded from the
property for as long as they had existed. Dictionary literals, `keymaker` and
`oracle` must be added to treegen **in the same change that adds them to the
language**, or they inherit the identical invisible hole. A reviewer should
treat a diff that adds a node type without touching treegen as incomplete.

## Testing

| Layer | What is covered |
| --- | --- |
| Lexer | `{`, `}`, `:` tokens; `keymaker` and `oracle` as keywords |
| Parser | literals, empty literal, nesting, a trailing comma **rejected** the way lists reject it, a newline inside braces rejected likewise, `keymaker` prefix, and each row of the `oracle` precedence table above |
| Interpreter | lookup, insert, update, `length`, `keymaker` order, `oracle` both ways, missing-key error, rejected key types, order-independent equality, self-containing dictionary |
| Render | ASCII and glyph faces for every new node |
| Translit | the five new slots, bijection, budget ledger |
| Property | round-trip over 300 seeds **with dictionaries in treegen** |
| End to end | the students program that motivated this |

The insertion-order test is written as a determinism guard, in the register of
`tests/test_site_glue.py`'s: it should say in its comment what breaks if it
fails, so the next reader knows it is not a style preference.

## Explicitly out of scope

- **Deletion.** No way to remove a key in this version. It is a real gap and a
  cheap follow-up, but nothing in the motivating program needs it and it costs
  another glyph slot.
- **Multi-line bracketed literals.** A record type makes the one-line rule bite
  harder than it did for lists — a five-field dictionary is a long line, and a
  list of them is longer. Worth fixing, but as its own change: it means altering
  how the lexer treats NEWLINE inside every bracketed form, it changes lists and
  call arguments as much as dictionaries, and D-03 round-tripping has to keep
  working across the new formatting. Folding that into this feature would put
  two unrelated risks in one diff.
- **Iterating values directly.** `keymaker` plus lookup covers it.
- **Scribe support.** Scribe writes programs from English descriptions; teaching
  it dictionaries is its own piece of work, separate from the language gaining
  them.
- **The Python translator.** Tracked as #122. It depends on this landing but is
  designed and built separately.
