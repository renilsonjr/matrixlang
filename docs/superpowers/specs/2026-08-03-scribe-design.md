# Scribe Design — a keyless, deterministic companion to Operator

Status: **Approved as a design. Nothing is implemented.**
Inputs: `2026-08-01-operator-design.md` (the purity gradient, validate gate, OP-1…OP-13),
`2026-08-01-stage-6-functions-design.md` (functions, closures, lists), GitHub #59 (this feature).

A person describes a program in plain language and gets MatrixLang — **without an API
key, an SDK, or a network call**. Operator is an LLM that proposes and a parser that
decides. Scribe skips the LLM: a finite set of pattern-matched intents builds the AST
directly. Scribe is the free, offline, deterministic tier; Operator remains the optional
paid upgrade for the long tail. **Scribe never replaces Operator; it is a second option.**

## Decisions

| # | Question | Decision |
| --- | --- | --- |
| SC-1 | Replacement or companion | **Companion.** Operator stays. Scribe is a second engine behind the same chat UX. |
| SC-2 | How generated code becomes trusted | **Same as Operator.** Scribe output goes through `operator/validate.py`'s `parse()` + bounded dry-run — called by the **server**, not by `scribe()`, so the pure module never imports `operator` (SC-5). |
| SC-3 | How ASTs are built | **Directly from `nodes.*`** — no string interpolation, no format-string codegen. Structured by construction. |
| SC-4 | How Scribe is exposed | `engine: "scribe" \| "operator"` on `POST /api/chat` (default `scribe`). Mode toggle in the web UI. |
| SC-5 | Dependencies | **None.** No SDK, no key, no network. `scribe.py` is pure; core modules never import it. |
| SC-6 | Unmatched request | **`ScribeMiss(reason, closest_pattern)`** returned by the pure module; the server turns it into a hint (+ "try Operator" when a key exists). |
| SC-7 | Name handling | **Explicit + auto.** Names come only from phrases like "store as total"/"call it sum"; otherwise auto-named `x`, `y`, `n`. No noun inference. |
| SC-8 | Coverage | **Full current language**, one pass: arithmetic, loops, conditionals, lists, strings, functions, logic. |
| SC-9 | Scope creep guard | Public hosting, cost caps, replacing Operator, noun inference — all out of scope. |

## 1. Why Scribe exists

Operator is gated behind `matrixlang[bot]` (the Anthropic SDK) and a paid `ANTHROPIC_API_KEY`.
That is correct for what Operator is, but it means the *only* path from "describe a program"
to "a working `.rain` file" requires a key. Clone-and-run should not. Scribe gives everyone
the core experience — describe, generate, validate, cascade — at zero cost, with the same
chat surface Operator uses.

The insight that makes it possible: MatrixLang is small. Fourteen keywords, four types,
no stdlib, no I/O. The set of things a beginner asks for is finite and enumerable
(countdowns, sums over lists, if/else, functions that double, …). An LLM generalizes over
that space; a pattern engine can cover it deterministically.

## 2. Module boundaries

The purity gradient the Operator design established extends to Scribe.

| Module | Responsibility | Imports |
| --- | --- | --- |
| `src/matrixlang/scribe.py` | Pattern matching + `nodes.*` AST construction. Pure. | `matrixlang.nodes`, `matrixlang.render` |
| `src/matrixlang/operator/validate.py` | **Reused unchanged.** Scribe output passes the same parse + bounded dry-run gate as Operator's. | existing |
| `server/app.py` | `engine` field on `POST /api/chat`; dispatches scribe vs operator; turns `ScribeMiss` into a hint. | `matrixlang.scribe`, `matrixlang.operator` (lazy, only when selected) |
| `web-ui/` | Mode toggle in the Operator panel: **Scribe (free)** / **Operator (AI)**. | none |

**Load-bearing assertions (tested in `tests/test_architecture.py`, not left as convention):**
- No core module imports `scribe` or `operator`.
- `scribe.py` imports no `operator` module.
- `scribe.py` performs no I/O, no network, no SDK import — it is a pure function
  `request: str → Program | ScribeMiss`.

## 3. The pattern engine

`scribe.py` exposes one pure entry point:

```python
def scribe(request: str) -> ScribeResult  # Valid(program, source) | ScribeMiss(reason, closest)
```

The pipeline:

```
scribe.py (pure)                          server/app.py (impure edge)
─────────────────                         ───────────────────────────
request text
  → normalize phrasing (synonyms: "print"/"show"/"display" → trace)
  → intent patterns, longest match wins
      → matched → build nodes.* AST directly
          → render_ascii(program) → source
          → ScribeProgram(program, source) ──→ validate.py check(source)
                                                  → Valid   → 200 {ok: true, source}
                                                  → Invalid → 200 {ok: false, error}
      → no match → ScribeMiss(reason, closest) ──→ 200 {ok: false, hint, closest}
```

`check()` takes a **string**, not a tree, so `render.render_ascii()` is the required step
before it — the same one Operator's output already goes through. This is why `scribe.py`
imports `render`.

**The gate lives in the server, not in `scribe()`.** SC-5 forbids `scribe.py` from
importing any `operator` module, and `check()` is `operator/validate.py` — so calling it
from inside the pipeline would break the purity rule the architecture test enforces. The
split is the same one Operator already uses: the pure module proposes, the impure edge
validates. `scribe()` therefore returns a `ScribeProgram` that has not yet been dry-run,
and the server is what decides whether it is trustworthy.

**Longest match, not first registered.** The catalogue is built up over many tasks and its
patterns overlap — `if 5 is greater than 3 trace bigger` matches both the conditional
intent and the bare `trace <value>` intent. Scoring by match width keeps registration order
from becoming load-bearing; a first-match loop would let whichever pattern was added
earliest shadow every longer one added later.

**No string interpolation.** Each intent constructs the actual `nodes.*` tree, and the
source text is rendered from that tree rather than formatted by hand. So the round-trip
`parse(render_ascii(t)) == t` — already established and property-tested in
`tests/test_roundtrip.py` — is what guarantees the program Scribe validates is the program
Scribe built. Scribe inherits that guarantee; it does not need a second one.

### Intent catalogue (full current language)

| Category | Intents |
| --- | --- |
| Arithmetic | `+ - * //` — "add 5 and 3", "double 4", "7 minus 2", "divide 10 by 3" (integer truncation) |
| Comparisons | `< > <= >= ==` — "check if 5 is greater than 3" |
| Output | `trace` — "print/show/display …" |
| Loops | `dejavu … flatline` — "count from 1 to 10", "repeat 5 times", "countdown from N to 1", "loop while x < 5" |
| Conditionals | `redpill … flatline` — "if x is greater than 0", "if/else", "unless x" / "if not x" |
| Logic | `splice`/`fork`/`unplug` — "and", "or", "not" on booleans (short-circuit semantics respected) |
| Lists | literal `[1, 2, 3]`, index `xs[0]`, assign `xs[0] = v`, `+` concat, `length xs` |
| Strings | literal, index `name[0]`, order `name < "Z"` |
| Functions | `agent … flatline`, `jackout` — "define a function that doubles", "adder factory" (closures) |

### Name handling (SC-7)

- Explicit: "store as total" / "call it sum" → variable named `total`/`sum`.
- Otherwise auto: `x`, `y`, `n` chosen from context (loop counter → `i`, accumulator → `total`).
- No noun inference. A request never gets a name it did not earn.

## 4. Server + UI

**Server:** `POST /api/chat` accepts an optional `engine` (`"scribe"` default, `"operator"`).
The scribe path never imports the SDK or touches a key. A `ScribeMiss` becomes a 200 JSON
response with `ok: false`, `error`, `hint` (an example of the closest pattern), and
`closest`. If a key is configured, the server may additionally offer "try Operator".

**UI:** the Operator panel gets a small mode selector — `Scribe (free)` / `Operator (AI)`.
Scribe is the default. Misses render the hint inline; "try Operator" appears only when the
AI path is available.

## 5. Testing

| Layer | Approach |
| --- | --- |
| `tests/test_scribe.py` | Pure. Per intent: happy path, phrasing variants, malformed input, name handling, no-match → `ScribeMiss`. |
| Round-trip | Every generated program `parse()`s to the AST Scribe claims to have built. |
| Validate gate | **Every catalogued intent passes `check()`**, parametrized one case per intent — not just a sample. Round-tripping is a weaker property and passes on programs that cannot run: `trace xs[0]` renders and re-parses perfectly, then fails the dry run because `xs` was never declared. An intent that reads a name must also declare it. Separately: a program that would loop forever is rejected by the dry-run limit, same as Operator. |
| Architecture | No core module imports `scribe`; `scribe` imports no `operator`; `scribe` is pure. |
| Server | `engine` dispatch; miss → hint shape; default is `scribe`. |

## 6. Decomposition

| Child | What | Depends on |
| --- | --- | --- |
| **SC-A** | `scribe.py` core: normalize + matcher + AST builders + `ScribeMiss` | nothing |
| **SC-B** | `tests/test_scribe.py` — the bulk of the work, per-intent | SC-A |
| **SC-C** | `server/app.py` `engine` dispatch | SC-A |
| **SC-D** | `web-ui/` mode toggle + miss hint UI | SC-C |
| **SC-E** | README + architecture tests + spec commit | SC-D |

## 7. Deliberately out of scope

- **Public hosting** — inherited from OP-13.
- **Replacing Operator** — SC-1.
- **Noun-based name inference** — SC-7.
- **Cost caps** — none needed; Scribe is free.

## 8. Known risks

- **"Full current language" is a large surface.** SC-8 is the whole risk: ~30–40 intents,
  each needing tests. Mitigation: patterns are small and orthogonal; the catalogue in §3 is
  the contract, and tests are per-intent.
- **Novel phrasing that is not in the patterns.** The `ScribeMiss` seam is the answer, and
  it is by design — Scribe is deterministic, not omniscient.
- **Nothing here is implemented.** Verify against the code, not against this file.
