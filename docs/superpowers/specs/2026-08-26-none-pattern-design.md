# The `None` pattern — Design

**Date:** 2026-08-26
**Status:** Approved, ready for an implementation plan
**Issue:** #136
**Register entry:** `docs/PYTHON-PARITY.md`, item 5

## Why

A function that might not find anything, and a test of whether it did:

```python
def find_book(books, term):
    for book in books:
        if book["name"] == term:
            return book
    return None            # <- refused

result = find_book(library, user_input)
if result:                 # <- refused
    print(result["name"])
```

This shape has blocked two real programs — a book search and a product
search — more than any other single thing in the register.

Both halves are refused **by design**, not by omission. MatrixLang has no
null: `NOTHING` exists internally, and `_value_of` guards every
user-visible position specifically to keep it from leaking. And MatrixLang
has no truthiness: `redpill` takes a boolean and nothing else, because
`if xs:` means four different things depending on a runtime type, and
guessing between them produces a program that runs and quietly gives the
wrong answer.

Adding either undoes a decision the rest of the design rests on.

## What this is not

**Not a language change.** No null, no truthiness, no option type. The
glyph table is closed at 56 used, 0 free, so a new keyword would have to
reuse a slot or argue for a larger block — and neither is warranted for a
shape the language can already express.

**Not a translator rewrite into working code.** Recognising this pattern
and silently emitting a list-based translation is how a translator starts
guessing, and guessing is what the whole design is arranged against.

**This is a better refusal.** The translator still refuses. What changes
is that it recognises this specific shape and explains the whole rewrite
once, instead of leaving the reader two locally-correct messages that do
not add up.

## The problem with today's output

The reader already gets both refusals, each with an idiom:

```
line 5: None cannot be translated
        -> MatrixLang has no null; use a value your program can test
line 8: `result` relies on truthiness, which MatrixLang does not have
        -> a list or string ->  len(result) > 0
           a number         ->  result != 0
```

Each is locally correct. Together they mislead.

`result` here is a book — a dict — or `None`. `len(result) > 0` on a dict
tests how many keys it has. A reader who follows that advice gets a
program that runs and answers a different question, which is precisely the
outcome the truthiness refusal exists to prevent.

The real rewrite is not at line 8 at all. It changes the *function's
contract*: return `[]` and `[book]`, then test length and unwrap. Neither
message says so, and neither can, because each sees only its own statement.

## The pass

A module-level function beside `_refuse_function_in_loop`:

```
_none_then_truth_test(tree) -> (Refusal, frozenset[(line, column)]) | None
```

It runs in `translate()` after `ast.parse`, returning either nothing or
the paired refusal and the two positions it stands in for.

Those two positions are the ones the existing raise sites report, not the
statements containing them: `_constant` reports the `None` constant node
(line 5, column 11 in the example above) and `condition` reports the `If`
test node (line 8, column 3). The filter matches on those exact pairs, so
it must read them from the same nodes the raise sites use.

This is the pattern the file already uses. `translate()` opens with
`_Translator(bound_names(tree))` — a pre-pass over the tree whose result
is handed to the walker — so a second analysis pass is not new machinery.

**The walker is untouched.** After the walk, `translate()` filters
`walker.refusals`: if *both* suppressed positions actually produced a
refusal, they are dropped and the paired one appended.

That condition is the safety property. Replacement happens only when it
can trade two real messages for one. If only one fired — because
translation stopped earlier for an unrelated reason — nothing is replaced
and the reader keeps every accurate message they had.

## What counts

All four must hold, within one module:

1. A `FunctionDef` containing **both** a `return <expr>` where `expr` is
   not `None`, **and** an explicit `return None` or a bare `return`.
2. An `Assign` with a single plain `Name` target whose value is a `Call`
   to that function by name.
3. An `If` whose test is exactly that `Name` — not a call on it, not an
   attribute, not a comparison.
4. The `Assign` and the `If` share a scope, and nothing rebinds the name
   between them.

Anything else falls through to today's two messages.

### Two deliberate exclusions

**Falling off the end of a function.** Python returns `None` that way too,
but detecting it means proving no path returns — the inference that gets
this wrong. The shape is also invisible in the source rather than written
down, so a reader cannot see what the translator claims to have seen.

**Rebinding between the assign and the test** is why requirement 4 exists.
Without it, `result = find(x)` … `result = other()` … `if result:` pairs
the condition with the wrong function and explains a shape the reader did
not write. It costs a small scope walk.

## What it says

Anchored at the `return None` — the line that must actually change — with
the condition's line named in the text.

```
reason:
  `find_book` returns None on one path and its result is used as a
  condition on line 8. MatrixLang has neither null nor truthiness.

idiom:
  Return a list instead — empty for "not found", one element for found:

      return [book]        instead of   return book
      return []            instead of   return None

  then test its length, and read the value out of it:

      if len(result) > 0:  instead of   if result:
          result[0]["name"]             result["name"]
```

Three things this does that the pair cannot:

- It names **both** ends of the rewrite. The function's contract has to
  change for either half to make sense, and no single-statement message
  can say that.
- It includes `result[0]`. Without it, a reader who follows the advice
  hits a fresh error on the next run.
- It stops advising `len()` on a dict, which is the actively-wrong part
  of today's output.

## Testing

Test-first throughout.

**The positive case** is the program above: one refusal rather than two,
naming both lines and carrying the rewrite.

**The negative cases matter more**, because a false positive now costs the
reader two accurate messages. Each must fall through to today's behaviour:

- every path returns `None`, or every path returns a value
- `result` rebound between the assign and the `if`
- the test is `if result.name:` or `if find(x):` rather than a bare `Name`
- the `None` arrives by falling off the end
- two such functions in one module, with their results crossed

**The safety property** is tested directly: when only one of the two
positions produces a refusal, nothing is replaced.

**The existing refusal tests are the regression net.** Every program that
does not match the shape must behave exactly as it does today, so those
tests pass unchanged.

## Cost

Zero glyph slots. One analysis pass, one filter in `translate()`, no
change to the walker, and no change to the language.
