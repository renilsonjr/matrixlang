# `encode` — a number as text, the mirror of `decode`

Status: **Approved as a design. Nothing is implemented.**
Inputs: `2026-08-19-jackin-input-design.md` (the spec that added `decode`, whose
symmetry determines most of this one), `src/matrixlang/values.py` (`to_display`,
which already renders numbers and must agree with this), `src/matrixlang/glyphs.py`
and D-03 (the bijective table `encode` must join), `src/matrixlang/treeview.py`
(the file that shipped broken last time a keyword landed), GitHub #115.

`decode` turns text into a number. Nothing turns a number back into text, so a
program cannot print a number inside a sentence:

```
trace "ID: " + 1
matrixlang: [line 1, column 13] cannot add string and integer
```

That gap surfaced porting a real Python program: it held records as
`{"id": 1, "name": "clean code"}`, matched typed input against either field,
and printed both. The only way through today is to retype every id from `1` to
`"1"` — which works, and silently breaks any program that does arithmetic on
an id.

## Decisions

| # | Question | Decision |
| --- | --- | --- |
| EN-1 | Name | **`encode`**, the mirror of `decode`. Single word, no underscore, like every other keyword. |
| EN-2 | Domain | **Numbers only, strictly.** Booleans, lists, functions, and text that is already text all error. |
| EN-3 | Why not universal | `encode`/`decode` are a conversion *pair* between two of the four types. Rendering lists or booleans would make `encode` an exposure of `to_display` rather than `decode`'s mirror — and widening later is additive, while narrowing later would break programs. |
| EN-4 | Output | Exactly what `trace` prints for that number: `42` → `"42"`, `-3` → `"-3"`, `0` → `"0"`. `encode` must not invent a second way to render an integer. |
| EN-5 | Precedence | The `_unary` level, beside `decode` and `length`. `encode n + 1` is `(encode n) + 1`. |
| EN-6 | Node | Reuses `Unary` with `TokenType.ENCODE`, exactly as `decode`, `length` and `unplug` do. No new node type. |
| EN-7 | Coercion | **None.** `"ID: " + 1` stays an error. The conversion is explicit, which is the point. |
| EN-8 | Glyph | One of the 13 free slots in U+FF66–FF9D. Keywords 16 → 17, slots 43 → 44, free 13 → 12. |
| EN-9 | Scope guard | No implicit coercion, no Scribe intent, no translator. `nodes.py`, `input.py`, `glue.py` and every `site/*.js` untouched. |

## 1. The keyword (EN-1, EN-2, EN-4)

```
construct n = 42
trace "ID: " + encode n          # ID: 42

encode -3                        # "-3"
encode 0                         # "0"

encode true                      # error: 'encode' takes a number, got boolean
encode "already text"            # error: 'encode' takes a number, got text
encode [1, 2]                    # error: 'encode' takes a number, got list
```

Strict on a value that is already text, deliberately. `decode` refuses a value
that is already a number for the same reason: a conversion that silently passed
through would hide the bug where a program converts twice.

**EN-4 is load-bearing.** `values.to_display` already renders `42` as `"42"`
and `-3` as `"-3"`. `encode` must produce that same string rather than
formatting integers its own way, or the language would have two answers to
"how does a number look" and they would drift. The implementation should reach
the same rendering path, and a test should assert `encode n` equals what
`trace n` prints for a spread of integers including negatives and zero.

## 2. Precedence (EN-5)

`encode` joins `_unary`, beside `decode`, `length` and unary minus.

The reasoning is the one `decode` already records: `encode` *produces* a value
that the surrounding operator *consumes*, so it must bind tightly.
`encode n + 1` reaching across the `+` would mean encoding the result of adding
1 to a number — which is not an error, but is never what anyone means, and
would silently produce `"43"` where `"42" + 1` was intended. `unplug` binds
loosely for the opposite reason, and that asymmetry is already documented at
the parser's `_unary` guard.

## 3. The round-trip, and the half that does not hold

```
decode encode n  ==  n      for every integer n
```

That is a real invariant and the natural companion to the properties this
project already keeps for its two textual faces (`parse(lex(render_X(t))) == t`)
and its transliteration table (`untransliterate(transliterate(s)) == s`).

**The reverse does not hold, and the spec says so on purpose:**

```
encode decode "  +7 "  ==  "7"      not "  +7 "
```

`decode` deliberately tolerates surrounding whitespace and a leading sign, so
the text-to-number direction is many-to-one. Anyone writing the symmetric test
will find it fails; this paragraph is why it fails, so the answer is not to
loosen `encode`.

## 4. What it unblocks

The motivating program, with ids left as numbers:

```
construct books = [[1, "clean code"], [2, "refactoring"]]

redpill encode shelf[n][0] == term fork shelf[n][1] == term
  jackout shelf[n]
flatline

trace "Match found! Name: " + hit[1] + ", ID: " + encode hit[0]
```

Both the dual id/name match and the output line become expressible without
changing the data's types. Comparing everything as text also avoids needing a
non-erroring "is this text a number?" test, which the language still lacks and
which this spec does not add.

## 5. Module boundaries

A grep for consumers of `TokenType`, `KEYWORDS` and `GLYPHS` finds 13 Python
files; 7 more carry hand-tracked counts. This table is that grep, resolved.

| Path | Change | Why |
| --- | --- | --- |
| `src/matrixlang/tokens.py` | `TokenType.ENCODE`, `KEYWORDS["encode"]`. | Pure data. Lexing both faces follows automatically — see below. |
| `src/matrixlang/glyphs.py` | One entry, from the 13 free. Docstring count 43 → 44. | D-03. |
| `src/matrixlang/parser.py` | `ENCODE` in `_unary`, beside `DECODE`. | EN-5. |
| `src/matrixlang/interpreter.py` | Evaluate `Unary(ENCODE, …)`. | EN-2, EN-4. |
| `src/matrixlang/render.py` | `_OPS` entry; the word-separator rule already covers it once registered. | Both faces must round-trip. |
| **`src/matrixlang/treeview.py`** | **`_OPS` entry.** | **The file that shipped broken last time.** See §6. |
| `src/matrixlang/operator/prompt.py` | The hand-written prose bullet naming `jackin`/`decode`. | Its keyword *list* is derived and needs nothing; the prose is not. |
| `README.md`, `docs/LEARNING-MATRIXLANG.md`, `docs/TECHNICAL-OVERVIEW.md`, `site/index.html`, `src/matrixlang/cascade.py`, `src/matrixlang/translit.py` | Keyword and slot counts: sixteen → seventeen, 43 → 44, free 13 → 12. | Stale counts have bitten this project repeatedly. |
| `tests/test_glyphs.py`, `test_tokens.py`, `test_lists_lex.py`, `test_logic_parse.py` | The hardcoded counts, plus a ledger line in the budget test. | Tracked by hand on purpose — that test says so in its own name. |
| `src/matrixlang/lexer.py` | **Untouched.** | It builds its glyph-token map from `GLYPHS` ∩ `KEYWORDS`, so both faces lex the new keyword with no edit. |
| `src/matrixlang/nodes.py` | **Untouched.** | EN-6 — reuses `Unary`. |
| `src/matrixlang/scribe.py` | **Untouched.** | Derives its reserved-word pattern from `KEYWORDS`. |
| `src/matrixlang/input.py`, `site/glue.py`, every `site/*.js` | **Untouched.** | Nothing here is input or presentation. |

**Load-bearing assertions:**

- `site/checks/no_semantics.py` and `key_handling.py` pass unmodified — no
  JavaScript changes at all.
- `tests/test_architecture.py` needs nothing: no new module, and no new
  import edge between existing ones.

## 6. `treeview.py`, named explicitly

When `jackin` and `decode` landed, `matrixlang parse` crashed on every program
using them — `KeyError` on `_OPS`, `AssertionError` on the unhandled node —
while 1455 tests passed. It was the **second** occurrence; `tests/test_cli.py`
already carried a note from the first: *"One test per stage, forever."*

That work added an exhaustiveness guard walking every concrete node class, so a
missing *node* branch now fails a test. `encode` adds no node (EN-6), so the
guard will not catch a missing `_OPS` *operator* entry — that is still a plain
dict lookup and still a `KeyError` waiting to happen.

So this spec names `treeview.py` in the boundaries table, and requires a
`matrixlang parse` test covering `encode` specifically. The implementation plan
must not treat `parse` as incidental.

## 7. Testing

| Layer | Approach |
| --- | --- |
| Accepts | `encode 42`, `encode -3`, `encode 0` — and each asserted equal to what `trace` prints for the same value, per EN-4. |
| Rejects | Boolean, list, function, and already-text, each asserting the specific message rather than merely that something raised. |
| Round-trip | `decode encode n == n` across a spread of integers including negatives and zero. |
| Both faces | `parse(lex(render_X(t))) == t` for a program using `encode`, both faces. |
| `parse` | A CLI test rendering a program containing `encode`, per §6. |
| Precedence | A parser test asserting `encode n + 1` builds `(encode n) + 1`, since this is the decision most likely to be "corrected" later. |
| Budget | The two hand-tracked counts updated with a ledger line. |

## 8. Deliberately out of scope

- **Rendering booleans or lists.** EN-3.
- **Implicit coercion in `+`.** EN-7 — `"ID: " + 1` stays an error.
- **A non-erroring "is this text a number?" test.** Genuinely missing and
  genuinely useful, but a separate keyword with its own design.
- **A Scribe intent for `encode`.** Scribe's catalogue is its own concern.
- **The Python-to-MatrixLang translator this unblocks.** Separate work, and
  the reason this spec exists first.

## 9. Known risks

- **`encode` drifting from `to_display`.** EN-4. If the implementation formats
  integers itself rather than reaching the existing path, the language grows a
  second answer to "how does a number look". The equality test against `trace`
  is the guard.
- **`treeview.py` missed a third time.** §6. The exhaustiveness guard does not
  cover operator-table entries, so this rests on the named task and its test.
- **The reverse round-trip looks broken.** §3 — it is not; `decode` is
  many-to-one by design.
- **Nothing here is implemented.** Verify against the code, not against this
  file.
