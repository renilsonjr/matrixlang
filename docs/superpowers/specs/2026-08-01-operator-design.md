# Operator Design — an assistive coding companion for MatrixLang

Status: **Approved as a design. Nothing is implemented.**
Inputs: `2026-07-31-cascade-window-design.md` (module boundaries, purity gradient,
the threading precedent in `window.py`), `2026-08-01-stage-6-functions-design.md`
(approved, unimplemented), GitHub #30 (the f08 umbrella, decisions OP-1…OP-13),
#21 (general-purpose language), #28 (the web layer's removal).

A person describes a program in plain language, watches **Operator** write it in
MatrixLang, and watches it run in the cascade — without knowing the syntax. An LLM
proposes; the real lexer and parser decide. **Operator never gets to declare its own
output valid.**

## Decisions

| # | Question | Decision |
| --- | --- | --- |
| OP-1 | Local app or public website | **Local.** A small backend on the user's own machine, browser UI. Reuses the real Python interpreter; nothing duplicated, nothing hosted, no untrusted generated code run for strangers. |
| OP-2 | Fate of `web/interpreter.js` | **Already gone (#28)**, for reasons independent of this. `web-ui/` is greenfield, not a migration. |
| OP-3 | How generated code becomes trusted | **Generate → validate → retry.** Output is fed to the real parser before it is ever run. |
| OP-4 | Retry ceiling | **3 attempts.** On the third failure, surface the last diagnostic in chat rather than looping. |
| OP-5 | Where the LLM dependency lives | **Optional extra** `matrixlang[bot]`, imported lazily inside the calling function — the same pattern `window.py` uses for `tkinter`. |
| OP-6 | What stops a generated infinite loop | **A step counter in `interpreter.py`**, not a wall-clock timeout. See §3. |
| OP-7 | Relationship to #21 | **Not blocked on it, but capped by it.** Without functions or input, Operator can only write toy programs. |
| OP-8 | Layout | **D** — program top-left, Operator bottom-left, cascade **full height** on the right. See §5. |
| OP-9 | Server | **stdlib `http.server` + Server-Sent Events. Not FastAPI.** See §4. |
| OP-10 | What the cascade carries | **Source and output.** Output is pure glyphs, brighter, slower — already shipped in f07. |
| OP-11 | Are generated programs files | **Files you keep**, not a session transcript. |
| OP-12 | Source in the cascade | **Transliterated too — a pure glyph wall.** Shipped in #31. |
| OP-13 | Does the project accept becoming a product | **Yes, but local-first.** Anyone can clone it and run it on their own machine. **Public hosting is explicitly deferred** — it needs its own design, authentication, and protection of the software, and none of that is in scope here. |

## 1. What OP-13 changes, and what it does not

The README says:

> It is a **teaching artifact**, not a product. No users, no ecosystem.

That is now only half true, and the half that changes is smaller than it sounds.
**Clone-and-run is not hosting.** A person who clones this repo already runs the
real interpreter on their own machine with their own files; Operator gives them a
nicer way in. Nobody's code runs on anybody else's computer.

What would genuinely change the category — and is **deferred** — is putting this on
the internet. That needs, at minimum:

- a login and per-user isolation,
- rate limiting and per-session cost caps on the LLM API,
- a considered answer to executing generated code for strangers rather than for the
  machine's own owner,
- and a design pass that this document has not done.

Recording that as deferred is the point. The failure mode is drifting into hosting
one convenience at a time.

## 2. Module boundaries

The existing purity gradient extends the same way it did for the cascade window: the
interesting logic stays testable without a network call.

| Module | Responsibility | Imports |
| --- | --- | --- |
| `src/matrixlang/operator/prompt.py` | Builds the LLM context from the spec, grammar and examples. Pure. | none |
| `src/matrixlang/operator/validate.py` | Feeds candidate source to the real `lexer`/`parser`. Returns a result or a diagnostic. Pure. | `lexer`, `parser` |
| `src/matrixlang/operator/client.py` | The LLM call. Impure, isolated, lazily imports the SDK. | none at module scope |
| `src/matrixlang/operator/loop.py` | generate → validate → retry, capped at OP-4. Thin. | `prompt`, `validate`, `client` |
| `server/` | Local stdlib HTTP + SSE. Imports `matrixlang` as an ordinary dependency. | `matrixlang`, `matrixlang.operator` |
| `web-ui/` | Chat, editor and cascade panes. Talks only to `server/`. | none (browser) |

**The load-bearing assertion, the same shape as the window's: no core module may
import `operator`.** The interpreter and parser stay runnable with no SDK installed,
no key configured and no network reachable — asserted in `tests/test_architecture.py`,
not left as a convention.

## 3. The step limit

`Interpreter._execute` is the single place every statement passes through, including
every iteration of a loop body — verified at `interpreter.py` lines 60, 98, 107 and
111. That makes it the correct and only necessary place to count.

```python
def __init__(self, ..., max_steps: int | None = 200_000): ...

def _execute(self, stmt):
    if self._max_steps is not None:
        self._steps += 1
        if self._steps > self._max_steps:
            raise RuntimeErrorML("program exceeded the step limit — likely an "
                                 "infinite loop", stmt.line, stmt.column)
```

**Why a step count and not a wall-clock timeout.** A timeout needs a clock and usually
a thread, which is exactly what Stage 5 committed not to require of anything testable.
A step count is deterministic: a test asserts it raises at `max_steps + 1` and not at
`max_steps`, with no `sleep()` and no CI flake. It costs one integer compare on a path
that already emits an event per statement.

`max_steps=None` preserves today's behaviour exactly. `operator/loop.py` should pass a
visibly lower ceiling than the CLI default before handing generated output to the
interpreter.

**200,000 is a guess, not a measurement.** It needs tuning against real programs and
will want raising once Stage 6 makes loops over real data possible.

**Breadth, not depth.** Stage 6 §6 declines a recursion-depth limit on the grounds
that it and Python's stack limit would be two numbers to keep in agreement. That is
about how far a call stack goes. This counts statements executed regardless of stack
shape: a `while true` with no calls never grows the stack and would never trip a depth
limit. Function bodies execute through the same `_execute`, so calls accumulate against
this counter for free once Stage 6 lands.

**This should ship first, on its own.** It has no dependency on Operator, a server or
an LLM; it protects a human's accidental infinite loop today; and it protects the
cascade window from an unbounded event stream. It is the one piece whose design is
fully settled.

## 4. Why stdlib rather than FastAPI

Two flows, and only one is unusual:

1. Browser → server: a chat message. An ordinary `POST`.
2. Server → browser: execution events while the program runs. **One-directional.**

Server-Sent Events is the boring HTTP answer to (2): the server holds a response open
and writes `data:` lines; the browser reads them with `new EventSource(url)` and
reconnects on its own. No handshake, no protocol upgrade, no library on either side.

WebSockets solve a harder problem — both sides pushing at any time — which this app
does not have. FastAPI's main draw here is a feature that is not needed.

| | stdlib `http.server` + SSE | FastAPI + uvicorn |
| --- | --- | --- |
| Install | nothing | ~10 packages, incl. a compiled extension |
| Code for this app | ~150 lines | ~60 lines |
| Async | not needed — one user | yes |
| Versions to track | none | a framework, a server, a validator |

The threading pattern already exists: `window.py` runs the interpreter on a worker
thread pushing into a `queue.Queue` while the UI drains it. An SSE endpoint is the
same shape — drain the queue, write `data:` lines. A port, not a new design.

**The honest counter:** FastAPI could also live behind an optional extra, so
`pip install matrixlang` stays dependency-free either way. The real cost of stdlib is
~90 more lines that must be owned, including MIME types and shutdown. The judgement is
that those lines are simple and permanent, where a framework is maintained forever for
features never used.

**If this is ever hosted publicly, revisit immediately.** At that point auth, rate
limiting and real concurrency are needed, and hand-rolling those is the wrong call.

## 5. Layout D

```
┌──────────────────────┬──────────────────────┐
│ PROGRAM.RAIN         │                      │
│ line numbers, save   │                      │
│ ascii ⇄ glyph        │      CASCADE         │
├──────────────────────┤      full height     │
│ OPERATOR             │                      │
│ chat, attempts       │                      │
│ > describe a program │                      │
└──────────────────────┴──────────────────────┘
```

The cascade gets full height because it is what this project is about; in earlier
layouts it was half of one column and read as an output panel. The program sits above
the conversation because the program is the artefact and the conversation is how you
got there — and a composer belongs at the bottom of its pane.

Two consequences, both deliberate:

- **The retry loop is visible.** `attempt 1 rejected — [line 2, column 9] condition
  must be a boolean` appears in the chat. OP-3 is the most important decision in this
  design and hiding it would waste it.
- **The program pane implies OP-11.** Line numbers and a save control say *this is a
  file you keep*, which makes the editor genuinely editable and makes the round-trip
  guarantee matter in the browser: a file could be toggled to the glyph face and saved
  that way.

A **latin ⇄ glyph wall** toggle sits on the cascade; it flips `glyph_source`, which
#31 already implemented on both `CascadeField` and `CascadeWindow`.

## 6. Testing

| Layer | Approach |
| --- | --- |
| Step limit | Pure. No raise at `max_steps`, raise at `max_steps + 1` |
| `validate.py` | Pure. Known-bad syntax, assert the real parser's diagnostic surfaces unchanged |
| `operator/loop.py` | A stub client — **never a real API call in tests**. Assert the retry cap and that the last diagnostic reaches the caller |
| Architecture | No core module imports `operator` |

## 7. Once Stage 6 lands, `validate` must stop meaning "parses"

Today a program that parses essentially runs; the language is too small for the two to
diverge. Stage 6 changes that on its own terms: `NOTHING` is legal in statement
position and a runtime error in expression position, and arity mismatches and calls to
non-functions are runtime errors, not parse errors. A program can be syntactically
perfect and still fail.

So `validate.check()` becomes parse **and a bounded dry-run** — and that dry-run is
untrusted execution of generated output, so it goes through §3's step limit rather than
a separate unguarded path.

## 8. Decomposition

| Child | What | Depends on |
| --- | --- | --- |
| **OP-A** | The step limit | nothing — **ship first** |
| **OP-B** | `prompt.py` + `validate.py`, pure | OP-A |
| **OP-C** | `client.py` + `loop.py` | OP-B |
| **OP-D** | `server/` — stdlib HTTP + SSE | OP-C |
| **OP-E** | `web-ui/` — layout D | OP-D |
| **OP-F** | `validate` becomes parse + dry-run | Stage 6 (#21) |

## 9. Deliberately out of scope

- **Public hosting** — OP-13, and everything §1 lists as its price.
- **Stage 6 itself** — #21.
- **Collections, stdlib, modules, I/O** — each its own stage.
- **Cost caps on the LLM API.** Every retry is a paid call; a bad prompt could burn
  budget quietly across a session. Log attempts from day one even before any cap
  exists.

## 10. Known risks

- **200,000 is unmeasured.** §3.
- **Nothing here is implemented.** This document is a design, and the project's own
  history in this area is that acceptance criteria can all pass while a feature does
  not work — see the cascade window design's §10. Verify against the code, not against
  this file.
