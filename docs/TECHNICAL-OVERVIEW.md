# MatrixLang — Technical Overview

A reference for explaining this project: what it is, how it works, and how to
talk about it in an interview.

Current as of `main`, through Scribe — 4,772 lines in the package across 23
modules, plus a 568-line local server and a 680-line web UI. 8,421 lines of
tests, 1,382 passing, on Python 3.11 through 3.14 in CI. Zero third-party
runtime dependencies; `pytest` for development and the Anthropic SDK as an
optional extra for Operator, which is the only part that needs one.

New to this project? [LEARNING-MATRIXLANG.md](LEARNING-MATRIXLANG.md) teaches
the language itself. This document is about the implementation.

---

## 1. What it is, in one paragraph

MatrixLang is a small, real programming language: dynamically typed,
Turing-complete, with closures, a tree-walking interpreter, a REPL, and a
command-line toolchain. Its distinguishing feature is that a program has **two
faces** — the same source can be written and read either in ASCII
(`construct x = 5`) or in Matrix-style glyphs (`ｱ x ﾅ ｫ`), and the toolchain
converts losslessly between them because both are renderings of a single syntax
tree.

Its second distinguishing feature is that **the cascade is the output device**.
Running a program opens a window in which the program's own source and output
fall as glyphs, looping for as long as the window is open. Nothing random is
ever generated: every glyph on screen came from material the program produced.

On top of that sit two optional layers, both local-only: a stdlib HTTP server
that streams the same execution events over SSE, and **Operator**, an assistive
companion that writes MatrixLang from plain language and is never allowed to
declare its own output valid.

It is written in Python using only the standard library.

## 2. The premise, and why it matters technically

The code shown in *The Matrix* is not a programming language. It has no grammar,
no semantics, and no execution model — the glyphs were mirrored half-width
katakana scanned out of a Japanese cookbook, chosen because they looked good.
Nothing in the film runs.

So the project isn't "recreate the Matrix language." There is nothing to
recreate. It is: **invent the language the film pretended to have.**

That framing produced one genuinely non-obvious engineering constraint. In the
films, the falling green code isn't something characters *write* — it appears on
operator monitors as a readout of system state. Cypher describes no longer seeing
the code at all, only the people it represents. He is reading a *rendering*
fluently, not authoring source.

This is why the glyph face is a **view**, not an encoding. The ASCII face is the
authoring view; the glyph face is the operator view; both project from one AST.
The alternative — a keyword substitution table in the lexer — is one-way, and it
destroys debuggability the moment anything goes wrong. Ergonomics and
in-universe accuracy converge on the same architecture, which is a satisfying
thing to be able to say about a design decision.

## 3. Architecture

```
                      ┌──────────► treeview.py ──► indented tree (parse)
                      │
source ──► lexer ──► tokens ──► parser ──► AST ──► interpreter ──► events
  ▲                                         │                        │
  │                                         ▼                        ▼
  └──────────────── render.py ◄─────────────┘              display ──┴──► text
       (ASCII face or glyph face, from one tree)              │
                                                              └──► cascade ──► window
                                                                          └──► server ──► SSE ──► web-ui
```

The pipeline is the classic front end from Nystrom's *Crafting Interpreters*
Part I, with one addition: `render.py` runs the pipeline **backwards**, turning a
tree back into source text in either face. That reverse edge is what makes the
two-face design work, and it is where most of the interesting problems live.

The two display backends — the Tk window and the browser — sit at the same
place on that diagram and consume the same `events` stream. Neither knows
anything about the language, which is the whole point of the split.

### Module map

| Module | Lines | Responsibility |
| --- | --- | --- |
| `tokens.py` | 113 | Token vocabulary. Pure data |
| `nodes.py` | 213 | AST node definitions. Pure data |
| `errors.py` | 75 | Error hierarchy; every error carries line and column |
| `values.py` | 317 | Runtime value type rules, and `Function` — a runtime value type belongs where the rules describing them live |
| `glyphs.py` | 113 | The 54-slot bijective glyph table. 2 slots left of the block |
| `lexer.py` | 271 | Source text → token list. Handles both faces |
| `parser.py` | 579 | Tokens → AST. Recursive descent |
| `interpreter.py` | 986 | Tree walker. Executes the AST. Owns the environment chain and the step limit |
| `render.py` | 353 | AST → source text, in either face |
| `treeview.py` | 182 | AST → indented text, for teaching |
| `repl.py` | 138 | Interactive session with multi-line block buffering |
| `events.py` | 78 | The execution event vocabulary. Pure data |
| `input.py` | 124 | Where a running program's input comes from. The mirror of `events.py`, and pure like it |
| `translit.py` | 173 | The reversible display table. Pure |
| `display.py` | 96 | The display protocol and backend selection. Pure |
| `cascade.py` | 271 | The content-carrying field simulation. Pure |
| `window.py` | 217 | The Tk backend. The only impure module in the package |
| `ansi.py` | 100 | Terminal escapes and colour capability. **No longer used by the package** — kept for the terminal experiments under `experiments/` |
| `cli.py` | 244 | Command-line entry point |
| `scribe.py` | 632 | Plain language → AST, by pattern. Pure, keyless, and imports no `operator` |
| `operator/prompt.py` | 149 | The system prompt. The language's rules, as text |
| `operator/validate.py` | 96 | Parse and dry-run a candidate program. The gate |
| `operator/client.py` | 96 | The Anthropic call. The SDK is imported inside the function that uses it |
| `operator/loop.py` | 124 | Ask, validate, feed the diagnostic back, retry — at most three times |

Outside the package, and deliberately not installable:

| Path | Lines | Responsibility |
| --- | --- | --- |
| `server/sse.py` | 99 | Event → wire payload, and the SSE framing. One source of truth for both |
| `server/runs.py` | 147 | A run's lifecycle: worker thread, queue, wall-clock deadline |
| `server/app.py` | 262 | Three endpoints and static file serving. Binds `127.0.0.1` only. Dispatches `/api/chat` to Scribe or Operator |
| `web-ui/cascade.js` | 211 | The cascade again, in a canvas. Mirrors `cascade.py` decision for decision |
| `web-ui/app.js` | 192 | Wiring only: post, read the event stream, hand events to the cascade. Carries the engine toggle |

### The dependency graph is a test, not a convention

`tests/test_architecture.py` parses every module's imports with Python's `ast`
module and asserts them against an explicit allow-table. Two of these encode real
design decisions rather than style preferences:

- **`parser` must not import `lexer`.** The parser consumes any `list[Token]`.
  That's what lets one parser serve both source faces. An unused import would
  break no behavioural test, so it is asserted against the import graph directly.
- **Nothing may import `window`.** A backend leaking into the core would make the
  language unrunnable on a machine without a display. The dependency table lets
  `window` depend on everything below it and nothing depend on `window`, so the
  direction of that edge is a test rather than a convention.

There is also a guard that no module except `glyphs.py` may contain a half-width
katakana literal, which keeps the glyph set genuinely swappable.

## 4. The language

**Keywords (14):** `construct` (declare), `trace` (print), `redpill` / `bluepill`
(if / else), `dejavu` (while), `flatline` (end block), `true` / `false`, from
Stage 6 `agent` (define) / `jackout` (return), from Stage 7 `length` — a
keyword rather than a built-in `length(xs)`, because a built-in name is an
identifier, and identifiers are the one thing D-03 keeps in Latin in the
glyph face — and from Stage 9 `splice` / `fork` / `unplug` (and / or / not),
Matrix-themed rather than borrowed from a host language, same as the rest of
the vocabulary.

An Agent is a callable, reusable program in the films; `jackout` is leaving the
construct and coming back with something. Both had to pass D-05's test — does it
read as vocabulary, or as a joke that gets tiring — which is why `true`/`false`
stayed English.

Blocks are keyword-delimited rather than braced, so every block boundary is a
glyph in the glyph face rather than untranslated Latin punctuation.

```
construct n = 0
construct name = "Neo"

dejavu n < 3
  redpill n == 1
    trace "wake up, " + name
  bluepill
    trace n
  flatline
  n = n + 1
flatline
```

**Semantics worth knowing:**

- **Types:** integer, boolean, string, list. No floats — they buy nothing
  pedagogically and cost `.` disambiguation, a second numeric type, and a
  division-semantics tangent.
- **Lists are the one reference type.** `construct ys = xs` and passing `xs`
  to an agent both share the same underlying list — mutating through one
  name is visible through the other. `+` is the exception: it always builds
  a *new* list and copies, so concatenation cannot itself introduce sharing.
  Element assignment (`xs[i] = v`) is therefore the only route to a
  cycle — nothing else in the language can make a value contain itself.
- **Strings are indexable but immutable, and that asymmetry with lists is
  deliberate, not an oversight.** `s[i]` reads a one-character string —
  there is no separate character type, so `s[i][0]` is `s[i]` — but
  `s[i] = v` is refused (`a string cannot be changed — build a new one
  with +`). Lists gave up "handed to an agent, guaranteed unchanged" in
  exchange for in-place mutation; strings kept the guarantee instead. A
  string can be passed through any number of agent calls and is
  guaranteed to come back exactly as it went in, which is the property
  lists deliberately traded away when `xs[i] = v` was added in Stage 7.
- **Dynamic typing, a chain of environments.** Stage 6 replaced the flat dict:
  `construct` defines in the current scope, assignment and reads walk outward to
  the nearest binding. That walk is the whole of what lexical scoping is, and
  functions are what gave the language a reason to have it.
- **Closures capture where an agent was *defined*,** not where it is called. A
  returned inner agent still sees the scope that made it, after that call has
  finished.
- **`NOTHING` is a sentinel, not a value.** An agent that never jacks out
  produces it; a call in statement position may, and a call in expression
  position that does is a runtime error. The language still has five types, and
  no program can hold or compare a null.
- **`construct` declares; `=` requires a prior declaration.** Re-declaring is an
  error; assigning to an undeclared name is an error. This is what makes
  `construct` carry meaning rather than being decoration.
- **Conditions must be boolean.** No truthy integers or strings.
- **`splice` and `fork` short-circuit, and that creates a real asymmetry.**
  `a splice b` never evaluates `b` once `a` is `false`; `a fork b` never
  evaluates `b` once `a` is `true`. An operand that is never evaluated is
  never type-checked either, so `false splice 1` is `false` while
  `true splice 1` is a type error — the same expression shape, differing
  only in whether the left side decided the right side was worth looking
  at. This is what makes the bounded-search idiom (§5.8) safe rather than
  an accident of the operators happening to short-circuit.
- **Integer division truncates toward zero**, not floor. Python's `//` floors:
  `-7 // 2 == -4`, but the spec requires `-3`.
- **`+` is overloaded** for integer addition and string concatenation; mixed
  operands are an error, with no implicit stringification.

## 5. The eight problems worth talking about

These are the parts where the work was genuinely non-trivial. In an interview,
these are the answers to "tell me about something hard."

### 5.1 Reconstructing parentheses from a tree that doesn't store them

There is no `Grouping` node in the AST. Parentheses are a parse-time instruction:
they tell the parser how to shape the tree and are then discarded. That's the
right design — the tree's *shape* already encodes the grouping.

But it means the renderer must **reconstruct** parentheses from precedence and
associativity, or it silently changes meaning. Three rules, each with a directed
test:

- **Precedence:** a child binding looser than its context gets parens.
  `Binary(Binary(1,+,2), *, 3)` → `(1 + 2) * 3`.
- **Associativity:** the *right* child of a left-associative operator gets parens
  at **equal** precedence. `Binary(1, +, Binary(2,+,3))` → `1 + (2 + 3)`, not
  `1 + 2 + 3`. For `-` and `/` this changes the value: `10 - (3 - 2)` is 9,
  `10 - 3 - 2` is 5.
- **Unary operands:** a binary operand of a unary gets parens.
  `Unary(-, Binary(2,*,3))` naively renders `-2 * 3`, which re-parses as
  `Binary(Unary(-,2), *, 3)` — a different tree.

The implementation is two lines, and the asymmetry *is* the associativity rule:

```python
left  = _expression(expr.left,  level,     face)   # equal is fine
right = _expression(expr.right, level + 1, face)   # equal needs parens
```

### 5.2 The round-trip property

The acceptance criterion for the whole two-face design:

```
parse(render_glyph(t)) == parse(render_ascii(t)) == t
```

Property-tested, not example-tested: a hand-rolled seeded tree generator produces
300 random ASTs, and each is rendered and re-parsed in three faces — ASCII, glyph,
and a **per-seed randomly mixed** face where each of the 54 slots is
independently one or the other. That third case turns "mixed-face source is
legal" from a claim into a tested property, and it costs nothing because the
emitter is already table-parameterized.

Two subtleties that make the equality work:

- **Source positions are excluded from equality** (`compare=False` on the
  dataclass fields). A re-rendered face has different columns; the criterion must
  still hold.
- **Comment trivia is included.** Which leads directly to the next problem.

The generator is hand-rolled rather than using Hypothesis, to keep the repo
dependency-free. The trade-off is no shrinking — but the failing seed reproduces
the tree exactly, and trees stay small by construction.

### 5.3 Comments have to live in the AST

Comments are normally discarded at lex time. Under that design the round-trip
criterion passes *while the view toggle silently deletes every comment in the
file* — the criterion holds and the feature it exists to protect is broken.

So comments are preserved as **trivia** on statement nodes: `leading_comments`,
`trailing_comment`, and per-body trailing lists for block statements. Cheap to do
at Stage 1, expensive to retrofit later.

The related decision: **whitespace is explicitly outside the loss-free promise.**
Blank lines and indentation normalize to canonical form. Preserving them would
mean whitespace trivia on every node, and the honest framing is that the toggle
is also a pretty-printer.

### 5.4 One lexer, two alphabets, no mode flag

Glyphs and ASCII identifiers occupy **disjoint alphabets**. Anything in the glyph
range is a keyword, operator, digit or paren; anything Latin is an identifier or
string content. Two consequences fall out for free:

1. One lexer handles both faces. No mode flag, no separate glyph lexer.
2. **Mixed-face source is valid** — a file can contain glyph keywords and ASCII
   operators in any combination and still lex correctly.

The lexer reads the same 54-entry table the renderer writes through, just
backwards. Digit runs may even mix faces within one number (`1ｦｦ` is 100),
because otherwise `1ｲ` would lex as two adjacent numbers and produce a baffling
parse error two stages from the actual cause.

### 5.5 Python's `bool` is a subclass of `int`

`isinstance(True, int)` is `True`, and `True + 1` is `2`. The language forbids
coercion, so `true + 1` must be a runtime error — and with `isinstance` that
error never fires and the interpreter silently returns `2`.

Every value type check therefore uses `type(v) is int`, centralized in
`values.py` so the rule is auditable in one place rather than scattered across
twenty branches where a reflexive `isinstance` could creep back in. (`isinstance`
on *AST node* types is correct and used freely — the ban is on value checks.)

**Stage 7 reintroduced the same trap one level down.** The interpreter's
equality guard checked `type_name(left) != type_name(right)` before ever
touching the values, so `true + 1` and `1 == true` both raised correctly.
But comparing lists meant comparing their elements, and the first
implementation did that by delegating to Python's own list `==` — which
uses `isinstance` internally, where `1 == True` is `True`. Net effect:
`1 == true` correctly raised `cannot compare integer with boolean`, while
`[1] == [true]` silently returned `True`. The type-name guard was real and
it was in the wrong place; auditing `values.py` for a stray `isinstance`
proves nothing about a comparison that recurses through `list.__eq__`
instead. The fix, `values.equal`, reapplies `type_name` at every depth
rather than handing elements to Python once the containers' types match.

**A second "the obvious implementation is subtly wrong" story sits right
next to it.** The Stage 7 plan's `values._equal` discarded a cycle's
`(id, id)` pair from its seen-set in a `finally` block on the way back up
the recursion, on the theory that leaving it in place would let "a cycle
assumption leak into a sibling comparison." Fuzzing 20,000 random object
graphs found zero behavioural difference with or without the discard:
within one `equal()` call, a `False` result and an `Incomparable`
exception both propagate straight to the outermost call without leaving a
stale entry, so every pair that ever finishes recursing does so `True` —
a memoized `True` is never wrong to reuse. What the discard *did* cost was
speed: it made the seen-set path-scoped instead of a genuine memo, so
shared (not merely cyclic) list structure was re-walked once per path to
it. Comparing `node = [node, node]` repeated to depth 20 against a
`copy.deepcopy` of itself took **1,195 ms with the discard** versus
**0.017 ms without it** — and this is reachable from an ordinary `.rain`
program, since `[n, n]` evaluates `n` once into one shared object. The
shipped code drops the `finally`/`discard` and lets `seen` accumulate as a
real memo for the life of one `equal()` call; the plan itself carries a
dated correction note at Task 8 rather than being silently rewritten.

### 5.6 Testing an animation, and why content-carrying rain is harder

The cascade is the kind of feature that normally ships untested. It's testable
because the code is split on a **purity gradient**:

- `events.py` — pure data. The interpreter emits `Statement` / `Output` / `Error`
  rather than printing, so what the program did is separable from where it goes.
- `cascade.py` — the field simulation. Deterministic given a seed, with no time,
  no toolkit and no colour. `CascadeField(w, h, Random(7))` advanced N times
  produces identical cells on any machine.
- `display.py` — backend selection as a pure function of `(isatty, env, flags,
  tk_available)`, which is what makes it table-testable without a terminal.
- `window.py` — the only impure module. Tk, the clock, and the thread boundary.

**The lesson that only appeared once the rain carried the program.** The Stage 5
rain was random glyphs, and random glyphs all look alike — so two bugs hid in it
completely:

1. **Column reuse.** A column was returned to the free pool at spawn time, so two
   streams could share it and overwrite each other. Invisible in noise; in the
   cascade it silently corrupts a line of your program.
2. **Reversed lines.** Putting the first character at the head renders every line
   backwards. Harmless when nobody reads the glyphs; fatal when the columns *are*
   the program.

Both now have regression tests, and both were **teeth-checked by re-injecting
them**: the reversed-line bug fails 3 tests, column reuse fails all 30 seeds.
The general point is that *content-carrying rain has correctness requirements
decorative rain does not*, and inheriting the old field's tests would not have
been enough.

**What is still not tested: pixels.** No test opens a window or asserts what it
looks like. The frame stream, the routing and the degradation path are verified;
the appearance is a human judgment, which is the same admission the curtain
carried before it.

And the gate survives unchanged: **piped or redirected output is byte-identical
to what it was before any of this existed** — verified as bytes, not just as
strings.

### 5.7 The same animation, twice, without a second source of truth

The browser needs the cascade too, and a canvas cannot import `cascade.py`. So
there are two implementations of one simulation, which is exactly the shape that
produced the project's worst prior defect: a hand-written `web/interpreter.js`
that drifted from the real interpreter until the two disagreed about the
language. That file was deleted rather than fixed.

The rule that came out of it: **the browser may re-implement presentation, never
semantics.** `cascade.js` mirrors `cascade.py` — one reserved column per stream,
character 0 highest, source faster than output — and nothing else. Every glyph
it draws arrives over the wire already rendered and already transliterated,
because owning a copy of the translit table is how the old web layer drifted.

Two things went wrong anyway, and both are worth stating:

- **The wire payload was built in two places** — once for the queue the Tk
  window drains, once for the HTTP response — and they disagreed about whether
  output was sent as text or as glyphs, so the browser drew Latin with the glyph
  wall selected. Collapsed into `sse.payload`, which both paths now call.
- **The browser ran the simulation at the monitor's refresh rate.** Stepping
  once per `requestAnimationFrame` meant 60 rows/second on a 60Hz panel and 108
  on a 120Hz one, against the Tk window's 27. Accumulating real time and
  stepping at a fixed 33ms makes speed a property of the design rather than of
  the hardware.

Both were found by running it, not by a test — which is the recurring lesson of
§5.6 restated at a layer boundary.

### 5.8 The obvious home for `splice`/`fork` is the wrong one

`_evaluate`'s `Binary` branch reads:

```python
if isinstance(expr, Binary):
    left = self._value_of(expr.left, expr)
    right = self._value_of(expr.right, expr)      # both, before dispatch
    return self._binary(expr, left, right)
```

`_binary` is where `+`, `==`, the comparisons and the concatenations already
live. It is the obvious home for two new binary operators, `splice` and
`fork` — and putting them there produces operators that **work and do not
short-circuit.** The failure is quiet in exactly the way that makes it
dangerous: `true splice false` still correctly evaluates to `false`, and
every truth-table test in the suite still passes, because none of them
depend on which operand gets evaluated. What breaks is the idiom the whole
stage exists for — `n < length xs splice xs[n] != target` — which now reads
`xs[n]` at the boundary `n == length xs` and dies with an out-of-bounds
error that looks like a bug in the caller's program rather than in the
language.

The fix is to intercept `splice`/`fork` **in `_evaluate`, before** the
`Binary` branch evaluates both operands, so the right side is reached only
when the left side has not already decided the answer. The guard that
proves the interception is load-bearing rather than decorative is a
teeth-check: route `splice`/`fork` back through `_binary` and
`test_splice_does_not_evaluate_the_right_side_when_the_left_is_false` (an
observable side effect on the right operand, not an inference) fails
immediately, along with the bounded-search test itself.

This is the third stage in a row with a "the obvious edit is wrong and
looks right" story at its center — Stage 7's list-equality delegating to
Python's own `==` (§5.5) and Stage 8's string assignment falling through to
a Python `TypeError` (§7) are the other two. In all three, the dangerous
version passes its own truth-table tests. What differs is how each was
actually caught: Stage 7's leaked through a *return value* (`[1] ==
[true]` silently returning `True`), and Stage 8's through a *Python
exception class name* reaching the user. Only Stage 9's is silent on both
channels — the return value is correct and nothing raises — so it alone
needed a test built around an *observable side effect* on the unevaluated
operand, rather than either of those, to be caught.

## 6. Two generators, one gate, and the local web layer

Two things turn plain language into MatrixLang. **Operator** asks a model.
**Scribe** asks a regex table. They share the property that matters: neither is
trusted, and both answer to the same validator.

### Operator

Operator writes MatrixLang from plain language. The interesting decision is not
that it calls a model; it is what it is **not** allowed to do.

**Operator never declares its own output valid.** A candidate program is parsed
and dry-run against a reduced step limit before the user ever sees it. If either
fails, the diagnostic — the real one, with its line and column — is fed back and
the model tries again, at most three times. There is no path by which unvalidated
source reaches the editor.

```
request ──► prompt ──► model ──► candidate ──► validate ──► ok? ──► editor
                         ▲                         │
                         └──── the real diagnostic ─┘   (≤ 3 attempts)
```

Three consequences that make it work:

- **The retry loop is shown, not hidden.** The UI prints each rejected attempt
  and why. Concealing it would waste the most important property of the design.
- **A client error ends the loop immediately.** Retrying a missing SDK three
  times was a real bug: only *validation* failures are worth another attempt.
- **The SDK is imported inside the function that calls it.** `pip install
  matrixlang` stays dependency-free and `import matrixlang.operator` works
  without the extra installed.

### Scribe, and the invariant that shaped it

Operator costs money and needs a key, which made the only path from "describe a
program" to a working `.rain` file a paid one. Scribe is the keyless answer: a
finite catalogue of ~20 intent patterns that build `nodes.*` trees directly and
render them with `render_ascii`. No model, no network, no SDK — the same request
always produces the same program.

Three decisions carry the weight:

- **It builds trees, never strings.** Each intent constructs the actual AST, so
  the round-trip property (§5.2) is what guarantees the source Scribe validates
  is the program Scribe built. There is no format-string codegen to drift.
- **Longest match wins, not first registered.** The patterns overlap — "if 5 is
  greater than 3 trace bigger" matches both the conditional intent and the bare
  `trace <value>` one, because `.search()` finds that tail. Scoring by match
  width is what stops registration order from becoming load-bearing as the
  catalogue grows.
- **Scribe may not import `operator`.** `check()` lives in `operator/validate.py`,
  so calling it from inside `scribe()` would breach the purity rule the import
  graph enforces. The gate therefore runs in `server/app.py`: the pure module
  proposes, the impure edge validates. Same split Operator already had.

The invariant that turned out to be load-bearing: **every request Scribe accepts
must produce a program that survives the dry run.** It is easy to state and easy
to breach, because a program can be perfectly well-formed and still fail at
runtime. Three ways it broke, all found by running the thing rather than reading
it:

- `trace xs[0]` — renders, parses, round-trips, then dies with "'xs' is not
  declared". An intent that *reads* a name must also declare it.
- `construct trace = 5`, from "store 5 as trace" — a reserved word is a valid
  identifier to a regex and a parse error to the parser. The name patterns are
  built from `tokens.KEYWORDS` so a new keyword cannot leave them stale.
- "count from 1 to 10000" — the one intent whose cost is unbounded in the
  request, against a dry run deliberately capped well below the CLI's limit.

Each is now a refusal with a hint instead of a program, and the invariant is
fuzzed over the catalogue's own vocabulary rather than asserted case by case.
The lesson is the one §8 keeps repeating: **round-tripping is a weaker property
than running,** and a test that only checks the former goes green on a feature
that cannot work.

### The web layer

The server is `http.server` and Server-Sent Events rather than a framework, for
the same reason the package has no dependencies. Three endpoints — run, chat,
events — and static files. It **binds `127.0.0.1` only**, resolves static paths
and checks containment before serving, and gives every run a wall-clock deadline
in addition to the interpreter's step limit, because a program can be slow
without executing many statements.

One contract is worth naming because it was wrong first: **the event stream
always ends with `done`.** The queue originally treated `error` as terminal
while HTTP appended `done` after it, so a client could not write one handler
that worked against both.

`server/` is deliberately not packaged. A top-level `server` module on PyPI
would collide with half the ecosystem; it runs from the repo root with
`python -m server`, which is the clone-and-run model the design chose.

## 7. Security posture

A whole-repository security review was run against v0.5.0. Worth being able to
state precisely:

**What a `.rain` program cannot do.** There is no `eval`, `exec`, `compile`,
`pickle`, `marshal`, `subprocess`, `os.system`, `__import__`, socket, or XML/YAML
use anywhere in the package — confirmed by grep, not by assumption. The
interpreter is a closed `isinstance` dispatch over a fixed AST node set, so a
program has no route into Python. There are no file *writes* at all; the only
read is the path the operator typed.

**A Python exception name is also something a `.rain` program cannot
surface, and Stage 8 had a near miss.** `s[0] = "X"` on a string reaches
`IndexAssign`, and Python strings are themselves immutable — the careless
implementation would let `s[i] = v` fall through to Python's own item
assignment and raise `TypeError: 'str' object does not support item
assignment` straight into the user's terminal, a Python-internal name
leaking through a language boundary that is supposed to be closed. The
shipped guard checks the target's type before assignment and raises the
language's own diagnostic (`a string cannot be changed — build a new one
with +`) instead. A teeth-check proves the guard is load-bearing rather
than decorative: widening it the way an unrelated check was once
loosened lets the Python `TypeError` through, and the regression test
that would catch that (`test_assigning_to_a_character_never_raises_a_python_exception`
in `tests/test_strings_run.py`) fails the moment it does.

**The one finding, and why the obvious fix was wrong.** The lexer preserved raw
source bytes verbatim — correct for round-tripping — so an ESC byte in a string
or comment reached the terminal unescaped through `trace`, `parse`, `render` and
the REPL echo. `parse` and `render` mattered most: they are the *inspection*
commands, the safe thing a cautious person reaches for before running an unknown
file.

The obvious fix — escape control characters at the output sites — **breaks the
round-trip criterion**, because `render` must reproduce source exactly and an
escaped byte re-lexes as the escape text rather than the byte. Comments have no
escape syntax at all, so nothing could decode them back.

The fix was to refuse the byte **at the lexer**, in strings and comments alike.
Such trees can no longer be built from source, so every output path closes at
once and three downstream modules need no knowledge of the rule. It also
generalizes a rule the lexer already enforced (*a raw newline inside a string is
an error*) rather than inventing a new one.

This is a good story precisely because the first instinct was wrong and the
constraint that revealed it was a property test.

**What the web layer adds, and what it does not.** The server binds `127.0.0.1`
and is not intended to face a network. Static paths are resolved and checked for
containment before anything is served. Everything the model produces is escaped
before it reaches `innerHTML`, and a run carries a wall-clock deadline as well as
a step limit. What is deliberately *absent* is authentication, rate limiting, and
any notion of a user — those belong to a hosted product, and hosting was
explicitly deferred. Exposing this server publicly is not a supported
configuration.

## 8. Testing philosophy

1,382 tests, ~1.8× more test code than source code, run against Python 3.11
through 3.14 on every pull request. Three practices are worth describing:

**Teeth-checks.** Every load-bearing guard is proven by injecting the bug and
watching the test fail, then reverting. A test that has never failed proves
nothing. This caught a real defect: a test asserting "the head is the brightest
cell" used `max()` over a list whose insertion order already guaranteed the
property — with every level tied at 1.0 it still passed. It was replaced with a
strict-ordering assertion that ties cannot satisfy.

**Architecture tests.** The import graph is asserted, so design decisions that
would otherwise rot into stale comments fail loudly instead.

**Property tests over examples** where a property exists. The round-trip
criterion is the obvious one; the cascade field's invariants (every painted cell
in bounds, no two cells sharing a position across 30 seeds, a line reading top to
bottom, the field empty once every stream has fallen off) are the less obvious
ones.

The most instructive failure in the project: three tests with "drain" and
"clears" in their names asserted only that a *list* had emptied, not that the
*screen* had. You could delete the erase mechanism entirely and all three stayed
green — while a third of an 80×24 terminal was still lit when the animation
ended. The lesson is that a test's name is not its assertion.

Stage 9 produced a smaller instance of the same lesson. The plan's
`test_the_bounded_search_does_not_run_off_the_end` searched a three-element
list for `"Tank"` — its own **last** element — so the loop exited at
`n == 2` reading a perfectly legal index, and never reached the boundary
`n == length crew` its name and comment claimed to pin. It passed under a
deliberately non-short-circuiting interpreter for the same reason the drain
tests passed with the erase mechanism deleted: the assertion did not require
the behaviour the name promised. The fix was a one-word data change —
searching for an absent target instead of a present one — after which the
test genuinely could not pass without short-circuit. Short-circuit itself
was never actually unverified: four other tests in the same task pinned it
directly through an observable side effect. Only the one test named after
the bounded search failed to test the bounded search's boundary.

**And the standing limit of all of it: units pass while the wiring fails.** Four
of the project's worst defects were invisible to a green suite — the cascade
draining to a black window, the retry loop retrying an unfixable client error,
the browser drawing Latin with the glyph wall selected, and `matrixlang parse`
crashing on an agent while 878 tests passed. Every one was found by running the
thing. Each has a test now, but the pattern is the honest caveat on a suite this
size, and it is why every example in
[LEARNING-MATRIXLANG.md](LEARNING-MATRIXLANG.md) was executed before it shipped.

## 9. What is deliberately absent

Scope discipline is part of the design, and being able to say *why* something
isn't there is usually more convincing than a feature list:

- **Dictionaries and sets.** Stage 7 gave the language one collection
  type — a list — deliberately, not as a first installment; Stage 8 gave
  strings single-character indexing and ordering, but a key/value or
  unique-membership type would still need its own hashing and equality
  story on top of the one lists already required.
- **Slicing (`name[0:2]`) and string methods** (`upper`, `split`,
  `find`, and the like). Stage 8 went as far as one character at a time
  — `name[0]` — and stopped; a range or a method table is more surface
  than the pedagogical goal needed. With Stage 9's logical operators
  shipped, slicing is the largest remaining gap in the language: `else
  if` is a nesting exercise, `break`/`continue` are two keywords and a
  control-flow exception in the shape `jackout` already established, and
  `xor` is one more entry in the same table `splice`/`fork` already
  populate — none of those is a new kind of feature. Slicing is: it
  needs new syntax (a colon inside `[`), a new AST node, and bounds
  semantics for both strings and lists that the existing single-index
  rules do not give away for free.
- **Floats** — see §4.
- **`else if` chaining** — nest a `redpill` inside a `bluepill`.
- **`break` and `continue`.** A counter and a condition are how loops are
  written instead (§4).
- **`xor`.** `splice`, `fork` and `unplug` shipped in Stage 9; a fourth
  logical operator was reachable but not needed for Turing completeness
  or any demo, the same reasoning Stage 8 applied to slicing.
- **Hosting, accounts, and anything a product needs.** The web layer runs on
  `127.0.0.1` for whoever cloned the repo. Deploying it would mean designing
  auth, quotas and abuse handling first, which is a separate project.
- **A bytecode VM.** Explicitly deferred: starting there would mean debugging an
  unfamiliar execution model, an unfamiliar parser, and an unfamiliar glyph
  pipeline simultaneously.
- **A transpiler to a host language.** Tempting — it inherits an entire ecosystem
  free — but it destroys error reporting: a runtime failure surfaces as a
  traceback into generated code the author never wrote. The fix is source maps,
  which are the hardest part of any transpiler.

---

# Explaining this in an interview

## The 30-second version

> I built a small programming language in Python — lexer, parser, tree-walking
> interpreter with closures, REPL, and a CLI. Two things make it interesting.
> First, it has two interchangeable syntaxes: the same program can be written in
> ASCII or in Japanese katakana glyphs, and the toolchain converts between them
> losslessly because both are just renderings of one syntax tree — enforced by a
> property test that renders any tree either way, re-parses, and gets an
> identical tree back, comments included. Second, its output device is the
> Matrix cascade: running a program opens a window where its own source and
> output fall as glyphs, and the transliteration is reversible, so what falls
> can be read back rather than merely watched. It also writes itself from
> plain English two ways — an LLM, or a keyless pattern engine — and neither
> is allowed to declare its own output valid; the parser decides. About 4,800
> lines of source, 1,382 tests, no third-party runtime dependencies.

## The two-minute version

Lead with the pipeline (§3), then pick **one** deep problem rather than listing
all eight. The best single choice for most interviews is §5.1 — reconstructing
parentheses — because it is:

- easy to state in one sentence ("the tree doesn't store parentheses, so the
  renderer has to figure out where they go"),
- obviously wrong if done naively, in a way the listener can verify mentally
  (`1 + (2 + 3)`),
- and it has a two-line implementation, so you can show the whole solution.

Then close with how you knew it was right: the property test, and the fact that
you injected the bug deliberately to confirm the test could catch it.

## Questions you should expect, with the shape of the answer

**"Why not just use a substitution table for the glyphs?"**
Because substitution is one-way and it corrupts the wrong things. `x2` contains a
digit; `trace "trace"` contains a keyword inside a string. A structure-aware
emitter can't corrupt them because it never sees identifiers or string contents
as candidates for mapping — the correctness comes from *where* the substitution
happens, not from how careful the regex is.

**"How do you know the two faces are really equivalent?"**
Property test over 300 generated trees in three faces, including a randomly mixed
one. Not example-based. And a meta-test asserts the generator actually produces
the hard shapes — otherwise the property could quietly degrade into testing
nothing.

**"What was the hardest bug?"**
The animation drain. The field erased one row per frame while a column's head
moved several rows per frame, so about a third of the screen was still lit when
the curtain lifted. Three tests named "drain" and "clears" passed throughout,
because they asserted a *list* had emptied rather than the *screen*. It was found
by replaying the frame stream into a virtual screen and asserting what a viewer
would actually see.

**"What would you do differently?"**
Two honest answers. First, several test bodies were written stronger than the
truth — one asserted a value that is legitimately false once a column falls off
the screen, and an implementer changed working code to satisfy it. Tests encode
assumptions, and an over-strict assertion is a bug that costs you correct code.
Second, CI arrived late: a source change once rode in on a documentation PR and
broke `main` because no gate existed. There is one now — the suite runs on
3.11 through 3.14 on every pull request — but it was a reaction rather than a
starting condition.

**"How do you keep an LLM from writing broken code?"**
You do not. You make it impossible for broken code to reach the user. Operator's
output is parsed and dry-run before anyone sees it, and the real diagnostic goes
back to the model on failure — at most three times, because a model that cannot
satisfy a request will not start to on the fourth try. Operator is never the
authority on whether its own output is valid; the parser is. The UI shows the
rejected attempts rather than hiding them, since that gate is the design.

**"Why Python, and why no dependencies?"**
Python because the reference material (*Crafting Interpreters*) lines up and the
subject is the language, not the host. No dependencies because the project is
meant to be read line by line — every import is something a reader has to learn
before they can follow along. The one place it cost something was property
testing, where Hypothesis would have given shrinking; a hand-rolled seeded
generator was ~130 lines and reproduces failures by seed instead.

**"Is it actually Turing-complete?"**
Yes — variables, conditionals, and unbounded loops with unbounded integer
storage. Turing completeness follows from semantics, not from how the characters
look. Brainfuck manages it with eight punctuation marks.

## Which parts to emphasize, by role

- **Backend / general software:** the pipeline, the architecture tests as
  executable design decisions, and the `bool`-is-an-`int` trap as an example of
  language-level gotchas being contained in one auditable place.
- **Developer tooling / DX:** the two-face design, the round-trip guarantee, and
  the fact that `render --face ascii` doubles as a formatter for free because the
  renderer is canonical.
- **Testing / quality:** teeth-checks, the property test and its meta-test, the
  "tests that could not fail" failures and what they cost.
- **Security-adjacent:** §7 — particularly that the obvious fix was wrong, and
  that a property test is what proved it.
- **AI-adjacent:** §6 — validation as a gate rather than a suggestion, and the
  deleted `web/interpreter.js` as the case for one implementation of anything.

## Things to be honest about

Volunteering these lands better than being caught by them:

- It is a **teaching artifact that anyone can clone and run**, not a product.
  No users, no ecosystem, no hosting, and languages win on ecosystem rather than
  syntax.
- The glyph set is Unicode katakana, **not** the film's actual glyphs. Those
  were reverse-engineered by Rezmason/matrix and now ship as real fonts, so
  swapping them in is a change to `glyphs.py` and nothing else — the katakana
  are a convenience, not a limitation, and an earlier version of this document
  claimed otherwise.
- The novelty is in the **combination**. CJK-as-syntax has 124 prior examples on
  the esolang wiki; pop-culture-themed esolangs are an established genre; digital
  rain has been implemented dozens of times. Claiming component novelty would be
  false and trivially checkable.
- **CI came after the incident that needed it**, as above.
- The animation's *visual quality* has never been verified by an automated test —
  only its byte stream and frame math. Whether it looks right is a human
  judgment that hasn't been formally captured, and it has been wrong twice in
  ways every test missed: a window that went black after 3.6 seconds, and a
  field with exactly two speeds in it that read as a block of text sliding down
  rather than as rain.
- **Operator costs money to use** and needs an API key. Everything else in the
  repository runs on the standard library alone.

---

## Appendix: commands to demo it live

```bash
matrixlang run examples/hello.rain          # runs; opens the cascade window
matrixlang run --no-window examples/hello.rain   # ...or prints as text
matrixlang lex examples/hello.rain          # token stream
matrixlang parse examples/hello.rain        # the tree; shape is the lesson
matrixlang render --face glyph examples/hello.rain   # the operator view
matrixlang render --face ascii glyph.rain   # ...and back; also a formatter
matrixlang repl                             # :glyph toggles live echo

python -m server                            # the browser version, on 127.0.0.1

# Scribe, with no key and no network — plain English in, MatrixLang out
python -c "from matrixlang.scribe import scribe; print(scribe('count from 1 to 5').source)"
```

The strongest 20-second live demo is the round trip: render a file to glyphs,
save it, render it back, and diff against the original.

If the audience wants the plain-language angle instead, run the Scribe line
above and then ask for something it does not know ("sort a list") — the refusal,
with its nearest-pattern hint, makes the point that a deterministic generator
says no rather than guessing.
