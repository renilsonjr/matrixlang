# Input for MatrixLang — `jackin`, `decode`, and the InputSource protocol

Status: **Approved as a design. Nothing is implemented.**
Inputs: `src/matrixlang/events.py` (the symmetric problem, already solved —
this design copies its shape), `TECHNICAL-OVERVIEW.md` §5.7 (the browser may
re-implement presentation, never semantics), `src/matrixlang/glyphs.py` and
D-03 (the 41-slot bijective table both new keywords must join),
`src/matrixlang/operator/validate.py` (the dry-run gate this feature would
otherwise break), GitHub #108 (this feature).

MatrixLang is Turing-complete — recursion and closures both work — but it has
exactly one effect: `trace`. There is no way to read input, no randomness, no
clock, no files. That makes it a *compute-and-print* language, and it means a
whole category of program cannot be written at all.

This adds input. Two keywords, one protocol, and no async refactor.

## Decisions

| # | Question | Decision |
| --- | --- | --- |
| JI-1 | Keyword names | **`jackin`** (read a line) and **`decode`** (text → number). Single words, no underscore: `jackout` set that precedent and every other keyword follows it. |
| JI-2 | What `jackin` yields | **One line of text.** Trailing newline stripped, everything else preserved — Python's `input()` behaviour. Always text; it never auto-detects a number. |
| JI-3 | How numeric input works | Through `decode`, explicitly. **Integers only** — the lexer builds numbers with `int(...)`, so the language has no floats to produce. |
| JI-4 | `decode`'s strictness | Errors on non-numeric text, on a float spelling, and on a value that is already a number. Matches how `splice` refuses a non-boolean rather than coercing. |
| JI-5 | `decode`'s precedence | **Binds tighter than arithmetic**: `decode jackin + 1` is `(decode jackin) + 1`. Deliberately unlike `unplug` — see §3. |
| JI-6 | Where input comes from | An **`InputSource` protocol**, mirroring `EventSink`. Four providers: `StdinSource`, `BufferSource`, `ListSource`, `EmptySource`. |
| JI-7 | The `Interpreter` default | **`EmptySource`**, never stdin. Nothing may block on a terminal by accident — §5 is what happens when it does. |
| JI-8 | Running out of input | A **runtime error** with line and column, like every other diagnostic. |
| JI-9 | The validate gate | `check()` supplies a canned source yielding `"1"` for as long as asked, bounded by the existing step limit. See §5. |
| JI-10 | CLI | Reads `sys.stdin`. No new flag — piping is the answer that already exists. |
| JI-11 | REPL | Shares stdin with the prompt. Documented rather than special-cased. |
| JI-12 | Browser | An input textarea beside the editor; `glue.run(source, stdin=…)` passes it through as a `BufferSource`. |
| JI-13 | Glyphs | Two new slots from the 15 free in U+FF66–FF9D. D-03's bijectivity is preserved, not amended. |
| JI-14 | Scope guard | No Scribe intent, no floats, no `--input` flag, no async/resumable interpreter. |

## 1. Why a protocol, and not a builtin

The browser cannot block. JavaScript is single-threaded, so a blocking read
inside Pyodide freezes the tab — including the cascade that is supposed to be
drawing. The usual fix is to make the interpreter pausable and resumable so it
can yield control while waiting, which means rewriting the tree-walker as a
coroutine or a state machine. That is a large, risky change to the one module
whose correctness everything else rests on.

A pre-supplied buffer avoids all of it, and the codebase already contains the
argument for this shape. `events.py` opens:

> Printing is a decision about *where* output goes, made at the point that
> knows least about it, and it forces every consumer to be a file. A cascade
> window is not a file.

Reading is the same decision in the other direction. The interpreter should
not know whether a line came from a terminal, a textarea, or a list in a test —
only that it asked for one and got one. So input gets a protocol for exactly
the reason output got a sink.

## 2. The two keywords (JI-1 – JI-3)

```
construct name = jackin
trace "Hello, " + name

construct n = decode jackin
trace n + 1
```

`jackin` is a zero-operand **expression**, not a statement. `construct name =
jackin` reads naturally and composes; a statement form (`jackin name`) would
need its own binding rule and could not appear inside a larger expression.
`length` already establishes the keyword-that-is-not-a-function-call precedent
(`length xs`, no parentheses), and `jackin` is the same idea with no operand.

**`jackin` always yields text.** The alternative — inspecting the line and
returning a number when it looks like one — was considered and rejected. It
would make a value's type depend on what a reader typed, so the same program
would take different branches on different runs, and `5 books` and `5` would
produce different types from the same box. This project refuses to guess
elsewhere (Scribe declines rather than approximating, the translit table is
reversible rather than lossy); input is not the place to start.

Which is why `decode` ships in the same change rather than later. Without it,
`jackin` cannot feed arithmetic at all, and "read a number" — the single most
common thing a beginner asks input for — would be impossible. A feature that
cannot express its own most obvious use is not finished.

Keyword count goes 14 → 16.

## 3. `decode`'s rules (JI-4, JI-5)

```
decode "5"      ->  5
decode "-3"     ->  -3
decode "  7 "   ->  7          surrounding whitespace is not an error
decode "5.5"    ->  error — the language has no floats
decode "abc"    ->  error
decode 5        ->  error — already a number
```

Strict on a value that is already a number, deliberately. `splice` refuses an
integer rather than treating it as truthy, and the same reasoning applies: a
`decode` that silently passed numbers through would hide the bug where a
program decodes twice.

**Precedence: `decode` binds tighter than arithmetic.** So `decode jackin + 1`
parses as `(decode jackin) + 1`.

This is the opposite of `unplug`, which binds *looser* than comparison so that
`unplug n == 1` means `unplug (n == 1)`. The inconsistency is intentional and
follows from the operand types. `unplug` consumes a boolean and comparison
*produces* booleans, so reaching across the comparison is what a reader means.
`decode` produces a number and arithmetic *consumes* numbers, so reaching
across the `+` would produce `decode (jackin + 1)` — a decode applied to the
result of adding 1 to a piece of text, which is an error in every case.
Binding tight is the only reading that can ever succeed.

This paragraph exists so the next person to notice the asymmetry finds the
reason instead of "fixing" it.

## 4. The InputSource protocol (JI-6, JI-7, JI-8)

```python
class InputSource(Protocol):
    def next_line(self) -> str | None: ...   # None means exhausted
```

| Provider | Used by | Behaviour |
| --- | --- | --- |
| `EmptySource` | the `Interpreter` default | Always exhausted. |
| `StdinSource` | CLI, REPL | Reads `sys.stdin`. May block — correct at a terminal. |
| `BufferSource` | the browser | Walks pre-supplied text. Never blocks. |
| `ListSource` | tests | A list of lines. Deterministic. |

`Interpreter.__init__` gains `source: InputSource | None = None`, alongside the
existing `out` / `sink` / `max_steps`. It defaults to `EmptySource`, **never**
`StdinSource` — a default that reads a terminal would mean any code path that
forgot to pass a source could hang, and §5 is precisely that path.

Exhaustion is a runtime error carrying position, like every other diagnostic:

```
matrixlang: [line 3, column 17] no input left to read
```

Not an empty string. A `dejavu` loop reading input would spin forever on empty
strings while the real mistake — the program wanted more input than it was
given — stayed invisible. The language's error culture is precise diagnostics
that name the actual problem, and errors are the one thing never transliterated
(design §5) because they are where a reader's fluency has failed.

## 5. The validate gate — the interaction that would otherwise break this

`operator/validate.py`'s `check()` dry-runs every candidate program:

```python
Interpreter(out=io.StringIO(), max_steps=max_steps).run(program)
```

`operator/prompt.py` builds Operator's prompt from `tokens.KEYWORDS` — it reads
the list rather than retyping it, so the prompt cannot drift from the language.
The consequence is immediate: **the moment `jackin` is a keyword, Operator
starts writing programs that use it.** With no input available, every one of
those programs raises "no input left to read" during the dry run and is
rejected as invalid. Operator would become unable to write interactive
programs the language now supports, and the failure would look like a model
problem rather than a plumbing one.

So `check()` passes a canned source that yields `"1"` for as long as it is
asked. `"1"` is both valid text and decodes cleanly, so it exercises the
`jackin` and `decode jackin` paths alike. A program that loops reading input
forever is already bounded by `DRY_RUN_MAX_STEPS`, so an inexhaustible source
introduces no new way to hang.

This is right rather than merely convenient: a dry run answers *does this parse
and execute without crashing*, not *what does this print*. Immediate EOF would
answer a question nobody asked, and would reject correct programs for lacking
something the gate never had.

## 6. Surfaces (JI-10 – JI-12)

**CLI.** `matrixlang run books.rain` wires a `StdinSource`, so both of these
work with no new flag:

```
echo "Refactoring" | matrixlang run books.rain
matrixlang run books.rain        # type it at the terminal
```

No `--input` option. Piping is the answer the platform already provides, and a
flag would be a second way to do one thing.

**REPL.** The REPL reads stdin for source and now shares it with the running
program, so a `jackin` during execution consumes the next line typed. At a
terminal this is exactly right and needs no machinery. Piping a script into the
REPL gets genuinely confusing — program input and program source interleave in
one stream — so that is documented as a known edge rather than special-cased.
Detecting it would mean the REPL inspecting whether stdin is a TTY and changing
language behaviour accordingly, which is worse than a documented sharp edge.

**Browser.** A textarea beside the editor labelled for input, whose contents
become a `BufferSource`. `glue.run` grows one parameter:

```python
def run(source: str, stdin: str = "", max_steps: int = BROWSER_MAX_STEPS) -> list[dict]:
```

`playground.js` passes the textarea's value. This is what makes the motivating
program — search a list of books for a title someone typed — actually runnable
on the published page. The browser half gains no language logic: it hands over
a string and receives events, exactly as it does now
(`site/checks/no_semantics.py` stays passing, unmodified).

## 7. Glyphs and the two faces (JI-13)

Both keywords need glyph slots — D-03 requires every face to round-trip through
the lexer, `parse(lex(render_X(t))) == t`, and a keyword with no glyph would
break that for any program using it.

The table currently holds 41 entries against a 56-character pool (U+FF66–FF9D),
leaving **15 free**: `ｰｲｵｺﾉﾊﾏﾐﾑﾓﾔﾕﾘﾛﾝ`. Two are taken, bijectivity is preserved.
Assignment stays "loosely mnemonic where a sound offers itself, arbitrary
elsewhere", as `glyphs.py` already states.

**Two glyph tests must be amended by hand, and that is the design.**
`test_the_table_covers_exactly_the_41_slots` asserts `len(expected) == 41`, and
`test_the_glyph_budget_is_tracked_not_discovered` asserts `free == 15` — both
hardcoded. The second says so in its own name, and its comment carries a ledger
of every prior spend (24 free → 21 → 18 → 15). Adding two keywords makes those
43 and 13, and the ledger gains a line for this change.

This is not friction to route around. A budget that recomputed itself would let
a keyword consume a slot with nobody noticing; the whole point is that spending
one requires an edit somebody has to justify in review. The implementation plan
must treat these two edits as deliberate steps, not as test breakage to repair.

`render_ascii` and `render_glyph` both gain the two keywords, and the round-trip
property is what the tests assert — not the specific characters chosen.

## 8. Module boundaries

| Path | Change | Why |
| --- | --- | --- |
| `src/matrixlang/input.py` | **New.** `InputSource` protocol and the four providers. | Its own module for the same reason `events.py` is: pure data and protocol, importing nothing from the interpreter. |
| `src/matrixlang/tokens.py` | Two `TokenType` members, two `KEYWORDS` entries. | Pure data; the prompt and Scribe's `_NAME` pattern both read this, so they update for free. |
| `src/matrixlang/glyphs.py` | Two entries. | D-03. |
| `tests/test_glyphs.py` | The two hardcoded counts: `41 → 43` slots, `15 → 13` free, plus a ledger line. | §7 — the budget is tracked by hand on purpose. |
| `src/matrixlang/nodes.py` | A `JackIn` expression node and a `Decode` unary node. | |
| `src/matrixlang/lexer.py`, `parser.py` | Recognize both; `decode`'s precedence per §3. | |
| `src/matrixlang/interpreter.py` | `source` parameter; evaluate both nodes. | |
| `src/matrixlang/render.py` | Both keywords in both faces. | |
| `src/matrixlang/cli.py`, `repl.py` | Wire a `StdinSource`. | |
| `src/matrixlang/operator/validate.py` | The canned source. | §5 — without this the feature breaks Operator. |
| `site/glue.py` | `run(…, stdin=…)`. | The sanctioned Python-side surface. |
| `site/index.html`, `style.css`, `playground.js` | The input textarea and its wiring. | |
| `docs/LEARNING-MATRIXLANG.md` | Both keywords, with the precedence note. | The language's own documentation. |

**Load-bearing assertions:**

- `site/checks/no_semantics.py` still passes, unmodified — the browser gains no
  language logic, only a string it hands to `glue.py`.
- `site/checks/key_handling.py` still passes, unmodified — the input textarea
  is not a persistence sink and `playground.js` gains none.
- `tests/test_site_examples.py` still passes — no committed example uses
  `jackin`, so the generated `examples.json` is unaffected.

## 9. Testing

| Layer | Approach |
| --- | --- |
| The providers | Direct unit tests. `ListSource` is the one the rest of the suite uses, so its exhaustion behaviour is exercised everywhere. |
| `jackin` / `decode` semantics | Interpreter tests with a `ListSource`: reading, exhaustion, `decode` on each of its accept and reject cases. |
| Both faces | Extend the existing round-trip property — `parse(lex(render_glyph(t))) == t` and the ASCII equivalent — to programs containing both keywords. Bijectivity and single-character tests cover the new entries unchanged; the two counting tests are amended by hand, per §7. |
| `decode` precedence | A parser test asserting `decode jackin + 1` builds `(decode jackin) + 1`, since this is the decision most likely to be "corrected" later. |
| The validate gate | A test that `check()` accepts a program using `jackin` — the regression that would otherwise appear as "Operator got worse". |
| CLI and REPL | Existing CLI test patterns with piped stdin. |
| Browser wiring | `glue.run(source, stdin=…)` under CPython, as the suite already covers `glue`. The textarea itself is presentation, verified by looking at the page. |

## 10. Deliberately out of scope

- **A Scribe intent for input.** Scribe's catalogue is a separate concern with
  its own matching rules, and #107 is currently changing how it refuses.
- **Floats.** The language has integers; `decode "5.5"` is an error, and adding
  a numeric tower is its own project.
- **An `--input` flag.** JI-10 — piping already works.
- **An async or resumable interpreter.** The buffer design exists precisely to
  avoid this. Anything requiring real interactive input inside the browser —
  a program that prompts, waits, then prompts again based on the answer — is
  out of reach by construction, and that is the accepted cost.
- **Other effects.** Randomness and a clock were considered and declined:
  the site's examples are generated by running the real interpreter and
  CI-checked for staleness, and a non-deterministic program would make that
  gate meaningless. Input from a supplied buffer stays deterministic.

## 11. Known risks

- **The validate gate is the one that breaks quietly.** §5. If the canned
  source is dropped or the default becomes `StdinSource`, Operator stops being
  able to write interactive programs, or worse, `check()` blocks on a terminal
  inside a server request. The test named in §9 is the guard.
- **A default that reads stdin would hang somewhere.** JI-7 exists for this.
  Any new call site constructing an `Interpreter` without a source must get
  `EmptySource`, not a terminal.
- **`decode`'s precedence will look like a bug.** §3 explains why it differs
  from `unplug`. The parser test is what stops a well-meaning correction.
- **The REPL's shared stdin is a genuine sharp edge** when a script is piped
  in rather than typed. §6 accepts it deliberately; the alternative is
  branching language behaviour on whether stdin is a TTY.
- **Two keywords at once is more surface than usual.** They ship together
  because `jackin` without `decode` cannot read a number, which is most of the
  point. If the implementation gets unwieldy, `decode` is the half that can
  land second — `jackin` alone is still useful for text, as the motivating
  book-search program shows.
- **Nothing here is implemented.** Verify against the code, not against this
  file.
