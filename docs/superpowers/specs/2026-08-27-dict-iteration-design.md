# Iterating a dictionary — Design

**Date:** 2026-08-27
**Status:** Approved, ready for an implementation plan
**Scope:** Translator only. No language change.

## The defect

`for k in d:` over a dictionary translates today, and the program it
produces is wrong. The `for` desugaring indexes its iterable by an integer
counter — correct for a list and for a string, wrong for a dictionary.

There are two failure modes, and the second is the one that matters.

**String keys — a crash.**

```python
d = {"a": 1, "b": 2}
for k in d:
    print(k)
```

emits `trace d[n]`, which fails at runtime: `no key 0 in this dictionary`.
Python prints `a` then `b`. Loud, and at least unmistakable.

**Integer keys — a wrong answer, silently.**

```python
d = {0: 10, 1: 20}
for k in d:
    print(k)
```

Python prints the **keys**, `0` and `1`. The translation runs cleanly and
prints the **values**, `10` and `20`. Nothing fails; the program simply
means something else.

That second one is the outcome this translator exists to prevent. Its
governing rule is *refuse where the difference would be silent*, and here
it neither refuses nor translates correctly.

The defect predates the comprehension work, but that work widened it:
`[k for k in d]` used to refuse outright and now routes into the same
desugaring.

## What MatrixLang already gives us

`keymaker` takes a dictionary and returns its keys as a list, in insertion
order — exactly the values Python's iteration yields:

```
construct d = {"a": 1, "b": 2}
trace keymaker d          ->  ["a", "b"]
```

It is not a universal answer: `keymaker` on a list is a runtime error
(`'keymaker' takes a dictionary, got list`). So the correct translation
exists, and the whole problem is knowing when to reach for it.

## The constraint that shapes everything

**The translator has no type information.** It tracks which names are
bound (`_bind`, one line) and nothing about what they hold. It can prove a
value is a dictionary only syntactically.

For a function parameter it can never prove it:

```python
def f(d):
    for k in d:      # unknowable
        print(k)
```

and `def f(xs): for x in xs:` — the same shape over a list — is ordinary
teaching code that translates correctly today. So refusing every iterable
we cannot prove is off the table: it would break far more than it fixes.

## The design

Three parts, in order of how much they buy.

### 1. Prove it where we can

A new analysis beside `bound_names`:

```
dict_names(tree: ast.Module) -> set[str]
```

the names whose **every** binding in the program is a dict literal.

"Binding" has to be precise, because the wrong reading admits a name it
should not. A name qualifies only if it is assigned at least once, every
assignment to it has a dict literal on the right, and it appears as no
other kind of binding anywhere — not a function parameter, not a `for`
target, not a `def` or `class` name. Any of those means the name can hold
something we cannot see, and the name is out.

Subscript assignment is deliberately NOT a binding here. `d = {}` followed
by `d["a"] = 1` leaves `d` provable, which matters because building a
dictionary and then walking it is the shape a beginner actually writes.
Verified end to end.

There is no scope sensitivity, on purpose. A module-level `d = {...}` and
an unrelated parameter named `d` in some function disqualify the name
everywhere. That costs a fix we could have made; the alternative costs a
failure we would have introduced.

Conservative deliberately, and the asymmetry is the reason. Guessing
"dictionary" wrongly emits `keymaker` on a list — a runtime error this
change would be *introducing*. Guessing "not a dictionary" wrongly leaves
the behaviour exactly as it is today. One direction adds a new failure;
the other declines to fix an old one. So a name bound to a dict literal in
one place and anything else in another is not a dictionary as far as this
analysis is concerned.

### 2. Emit `keymaker` when it is proven

In `_for`, when the iterable is a dict literal directly or a name in
`dict_names`, wrap the value as `Unary(TokenType.KEYMAKER, value)`.

That makes it a non-`Name` expression, which means **the existing holder
logic hoists it with no new code** — the same path that already exists so
a call in the iterable position is evaluated once rather than per
iteration. The rest of the desugaring is untouched:

```
construct ks = keymaker d
construct n = 0
dejavu n < length ks
  trace ks[n]
  n = n + 1
flatline
```

`length` works on either kind, so only the element access had to change.

The holder wants its own stem. The existing path names it with
`_fresh("xs")`, so a dictionary's keys would land in `construct xs =
keymaker d` — read aloud, that says the keys of a dictionary are a list
called `xs`, which is exactly the confusion this fix exists to remove. Use
`ks` when the value was wrapped.

### 3. Give the unprovable case a way out

`for k in d.keys():` translates as `keymaker d`.

**This must be intercepted before `self.expression(node.iter)` is
called, not after.** That call is what raises the existing `.keys()`
refusal, so a branch placed after it never runs — the prototype for this
design put it after, and `.keys()` kept refusing. The check belongs at the
top of the iterable handling, on the raw `ast` node.

**In the `for` iterable position only.** It does not join the existing
method table beside `"lower": TokenType.FOLD` and `"strip":
TokenType.TRIM`, because Python prints `d.keys()` as `dict_keys(['a'])`
where a MatrixLang list prints `["a"]`. Supporting it as a general value
would trade one silent difference for another. Everywhere else `.keys()`
keeps the refusal it has now.

This is what makes the residual honest: a reader whose dictionary arrives
through a parameter has something to write.

## One refusal stops applying, and one difference appears

The list path refuses `for x in xs` when the body rebinds `xs`, because
the output indexes the name and would follow the rebinding onto a
different list. A wrapped dictionary is hoisted into a holder instead, so
that refusal neither fires nor needs to: rebinding `d` inside the body
cannot affect a keys list already computed, which is also what Python
does — its `for` holds the object it was given.

The difference that comes with hoisting is worth naming. Adding a key
during iteration raises `RuntimeError: dictionary changed size during
iteration` in Python; the translation completes, walking the keys as they
were at loop entry. This is accepted rather than closed: the reader's
program was already an error in Python, and there is no MatrixLang output
that reproduces a Python runtime error faithfully. It is recorded here so
it is a known quantity rather than a surprise.

## Comprehensions come free

The comprehension pass rewrites `[k for k in d]` into `for item in d`,
preserving the iterable expression. Fixing `_for` therefore fixes the
comprehension form with no extra work. Verified rather than assumed.

## What stays wrong

A dictionary reaching the loop through a function parameter or a call
result is still iterated as a list. `.keys()` is the way out, and the
register says so plainly rather than implying the gap is closed.

This is a real residual, not a rounding error, and it is worth stating why
it is accepted: the alternative is refusing every iterable the translator
cannot prove, which would refuse `def f(xs): for x in xs:` — a correct
program today, and one of the most ordinary shapes a beginner writes.

## Testing

The cases that carry weight are differential — `agree()` in
`tests/test_pytrans_differential.py`, which runs both sides and compares
output. These are the only tests here that can catch a program which
parses, runs, and means something other than the Python did, and this
defect is exactly that:

- a string-keyed dictionary — today a crash
- **an integer-keyed dictionary — today a silent wrong answer**
- an empty dictionary
- the `.keys()` form
- a dict literal inline in the `for`
- a comprehension over a dictionary

Then the conservatism itself, which is where a careless implementation
would introduce the new failure:

- a name bound to a dict literal in one place and a list in another must
  **not** get `keymaker`
- a name whose only binding is a list must not get it either
- a name rebound from dict to list between two loops

And `.keys()` outside the `for` iterable must still refuse.

The existing suite is the regression net: every program iterating a list,
a string or a `range` must translate byte-identically to what it produces
today.

## Cost

One new analysis function, one branch in `_for`, one special case in its
iterable handling. No new keyword, no new type, no glyph, and no change to
the language.
