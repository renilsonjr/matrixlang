# `encode` Takes Any Value — Design

**Date:** 2026-08-22
**Status:** Approved, ready for an implementation plan
**Builds on:** #122 (the Python translator), open as #130

## Why

A reader pasted this into the playground's Python box:

```python
print(f"Match found! Name: {result['name']}, ID: {result['id']}")
```

It translated cleanly and then died on Run:

```
'encode' takes a number, got string
```

The translator turns every f-string interpolation into `encode`, and `encode`
accepts only numbers. So an f-string works for a number and fails for a string
— and it fails *after* translation, at a MatrixLang line the reader never wrote,
naming an operator they never typed.

The same hole swallows `str()`. Python's `str(x)` accepts anything;
`encode` does not, so `str(name)` on a string has the identical late failure.

**The root cause is not in the translator.** MatrixLang has `encode` for
number-to-text and nothing for value-to-text, while `trace` prints every type
happily. The operator that was missing is the one `trace` already uses.

## The change

Delete the `is_int` guard in the `ENCODE` branch of
`src/matrixlang/interpreter.py:484-493`. Nothing needs adding for the happy
path: `encode` already routes through `values.to_display`, which renders every
type.

```
encode 2          → "2"          (unchanged)
encode "hi"       → "hi"         (was an error)
encode true       → "true"       (was an error)
encode [1, 2]     → "[1, 2]"     (was an error)
encode {"a": 1}   → "{\"a\": 1}" (was an error)
```

**Nested quoting is unchanged**, because it is `to_display`'s existing rule and
the same one `trace` follows: a string at the top level prints bare, a string
inside a list or dictionary prints quoted. Preserving that consistency is
exactly why `encode` was built on `to_display` rather than `str()` — its own
comment says two renderings of one integer would be two answers to the same
question.

### The guard defends against something that cannot happen

Its comment reads:

> Numbers only, and `is_int` is deliberately narrow: in Python a bool IS an
> int, so `is_int` (which checks type exactly) is what keeps `encode true` an
> error rather than `"1"`.

`to_display(True)` returns `"true"`, not `"1"` — the language's own spelling,
because `_display` checks `is_bool` before anything else. The failure the guard
was written to prevent is already prevented one layer down. Removing the guard
gives `encode true` the right answer rather than a wrong one.

## The one thing that must not be missed

**Add a `CyclicValue` catch**, converting it to a positioned `RuntimeErrorML`.

Today `encode` cannot receive a value that contains itself, because the type
guard admits only integers. Widening makes `encode xs` reachable where
`xs` holds `xs`, and `to_display` raises `CyclicValue` for that. Uncaught, it
escapes `Interpreter.run()` as a raw Python exception — and `site/glue.py`
carries it into the browser as an unhandled Pyodide traceback.

**This promise has been broken five times in this project**, four of them by
something nobody predicted. This is the sixth opportunity, and it is visible in
advance.

`Trace` already does exactly this at `interpreter.py:245-260`. Copy that shape,
including its reasoning: the message says "a value", not "a list", because a
dictionary can hold itself too and naming a list would simply be false —
and that message reaches the browser verbatim in the SSE error payload.

The existing `TooManyDigits` catch at `interpreter.py:498` stays as it is.

After this change `encode` errors on exactly two things: a value containing a
cycle, and an integer past CPython's digit ceiling.

## What comes free

**The translator needs no changes at all.** `pytrans` already emits `encode`
for both `str()` and f-string interpolations, so widening the operator fixes
every such program without touching a line of translator code.

**The glyph budget is untouched** — still 7 free of 49 slots. No new keyword,
no new token, no new node type. Worth stating because that count is
hand-tracked on purpose in `tests/test_glyphs.py`.

## What has to change around it

| Where | What |
| --- | --- |
| `docs/LEARNING-MATRIXLANG.md` §19 | "`encode` reverses `decode`" and "turns a number into text" are both now false |
| `src/matrixlang/operator/prompt.py` | Whatever it tells a model about `encode`'s argument type |
| Tests asserting `'encode' takes a number, got …` | Invert to assert the value now renders |
| `tests/test_pytrans_differential.py` | Gains a case it could not have before |

The `decode`/`encode` pairing survives loosely — `decode` is text-to-number and
still narrow, `encode` is now value-to-text — but the tutorial's "mirror"
framing needs rewording rather than deleting.

## Testing

| Layer | What is covered |
| --- | --- |
| Interpreter | `encode` on an integer, string, boolean, list, dictionary, and a nested string keeping its quotes |
| Interpreter | the two surviving errors: a self-containing list, and an integer past the digit ceiling |
| Never-raises | `site/glue.py`'s `run()` returns an error event rather than raising, for a program that encodes a cyclic value |
| Differential | an f-string interpolating a **string**, translated and compared against Python — the case that motivated this |
| End to end | the books-search program from the report, translated and run |

The differential case is the one that matters. Every other test proves `encode`
returns *something*; only that one proves a reader's Python and its translation
print the same text.

## Explicitly out of scope

- **A separate universal-text keyword.** Considered and rejected: it costs a
  glyph slot, leaves two operators overlapping on numbers, and makes the
  tutorial explain which to reach for. Widening removes code instead of adding
  it.
- **Widening `decode`.** It is text-to-number and narrow for a good reason —
  there is no sensible number for `"hi"`.
- **Truthiness and `None`.** The other two things that blocked the reader's
  original program. Both are refused deliberately by the translator's governing
  rule, and both would need a language-level change far larger than this one.
