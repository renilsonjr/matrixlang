# Web Playground Design — the real interpreter in a stranger's browser

Status: **Approved as a design. Nothing is implemented.**
Inputs: `2026-08-01-operator-design.md` (OP-13, the deferral of public hosting),
`2026-08-03-scribe-design.md` (the keyless generator that makes this reachable by
non-programmers), `TECHNICAL-OVERVIEW.md` §5.7 (presentation may be
re-implemented; semantics may not), commit `1b18491` (why `web/` was deleted),
GitHub #74 (this feature).

Today the shortest path from "I heard about MatrixLang" to "I saw MatrixLang run"
is: install Python, clone a repo, make a virtualenv, run a command. That is a
filter, and it filters out exactly the people the project is most interesting to
— someone reading about it on a phone, someone who has never opened an IDE.

This adds a link. It opens a page that **explains what the project is**, and
further down, runs the real language in the reader's own browser tab. No install,
no account, no server.

## Decisions

| # | Question | Decision |
| --- | --- | --- |
| WP-1 | Where the language runs | **Pyodide.** The actual `src/matrixlang/`, compiled-Python-in-WebAssembly, in the visitor's tab. There is no second implementation. |
| WP-2 | Where it is hosted | **GitHub Pages from this repo** (`renilsonjr.github.io/matrixlang`). Static files only. No server, no backend, no database. |
| WP-3 | What the page leads with | **The explanation.** Narrative first; the playground is proof, further down. A reader who only wants to understand the project loads nothing but HTML. |
| WP-4 | Narrative examples | **Pre-rendered at build time** by the real interpreter, committed, and verified in CI. |
| WP-5 | The editor | **Free-form.** The reader may type or paste any MatrixLang. Scribe is what *fills* it, so nobody faces a blank box. |
| WP-6 | The cascade | **`web-ui/cascade.js`, copied in by the workflow — not forked.** Presentation only, per §5.7. |
| WP-7 | The event shape | **`server/sse.py`'s `payload()`, reused verbatim**, mounted into Pyodide's filesystem. One source of truth for the wire shape. |
| WP-8 | Operator | **Present, opt-in, bring-your-own-key.** In memory only; browser→Anthropic only. Scribe is the default and needs no key. |
| WP-9 | Impact on the package | **None.** `dependencies = []` stays. Nothing in `src/matrixlang/`, `server/`, or `pyproject.toml` changes. |
| WP-10 | Reversibility | One new directory and one workflow. Reverting is deleting `site/` and switching Pages off. |
| WP-11 | Scope creep guard | No accounts, no saved programs, no permalinks, no sharing, no analytics. |

## 1. Why this is allowed, when hosting was deferred

OP-13 deferred public hosting, and listed what it would need: a login, per-user
isolation, rate limiting and cost caps, and "a considered answer to executing
generated code for strangers rather than for the machine's own owner."

**None of those apply here, and not because they have been solved.** They apply to
a server that runs other people's code. This has no server. The visitor's code
runs in the visitor's own browser, inside the sandbox their browser already
enforces for every page they open. The property OP-13 leaned on to permit
clone-and-run —

> Nobody's code runs on anybody else's computer.

— is preserved exactly, and now extends to a stranger on a phone. Static files on
a CDN are not a service; there is nothing to rate-limit, nothing to isolate, and
no account to attach to anything.

**The `web/` failure cannot recur either.** `1b18491` deleted that layer because
`interpreter.js` had become a second complete implementation of the language, one
that every future language change would have to be landed into twice, with no
tests to catch a divergence. Pyodide has nothing to drift from: the semantics
*are* the Python. This is stricter than the deleted layer and stricter than the
current server, which keeps semantics in one place but still needs a protocol
between them.

§5.7's rule holds unchanged and gets easier to obey: **the browser may
re-implement presentation, never semantics.**

## 2. Module boundaries

| Path | Responsibility | Notes |
| --- | --- | --- |
| `site/index.html` | The page: narrative, then playground. | Hand-written. No framework, no build step beyond assembly — same reason the package has no dependencies. |
| `site/style.css` | Presentation. | |
| `site/playground.js` | Lazy Pyodide bootstrap, DOM wiring, the Operator key field. | Deliberately thin. Every decision it could get wrong is one Python already makes. |
| `site/glue.py` | The Python side: request → Scribe → source → run → events. | **Plain Python.** Imported and tested by pytest under normal CPython; only *called* from JS. |
| `site/examples.json` | Pre-rendered narrative examples. | Generated, committed, CI-verified. Never hand-edited. |
| `web-ui/cascade.js` | The canvas cascade. | **Copied in at build time, not duplicated in `site/`.** One file, two consumers. |
| `server/sse.py` | `payload()`, the event → dict shape. | **Mounted into Pyodide, not reimplemented.** |
| `.github/workflows/pages.yml` | Build the wheel, assemble, publish. | |

**Load-bearing assertions:**

- `site/glue.py` imports only from `matrixlang.*` and `server.sse`. It contains no
  language logic of its own — no lexing, no parsing, no glyph table.
- Nothing under `src/matrixlang/` or `server/` imports anything under `site/`.
- `dependencies = []` in `pyproject.toml` is unchanged.

## 3. The playground pipeline

```
reader clicks "run it"
  → fetch Pyodide (pinned version, CDN)
  → micropip.install(matrixlang wheel, built by CI from this commit)
  → mount server/sse.py into the Pyodide filesystem
  → import site/glue.py
                                   ── from here, everything is real ──
  → glue.scribe_to_source(request)      Scribe writes MatrixLang, or misses
  → glue.run(source)                    lex → parse → Interpreter
      → each Event → sse.payload(event) → JS
  → cascade.js draws it
```

Two things this deliberately does **not** do. It does not re-render or
re-transliterate anything in JavaScript: every glyph arrives already rendered and
already transliterated, because owning a copy of the translit table is precisely
how the old web layer drifted. And it does not invent a message shape: `payload()`
is the same function `server/runs.py` calls.

### The editor (WP-5)

A plain textarea, free-form, prefilled with a short working program. Scribe sits
above it: type "count from 1 to 10", and the generated MatrixLang lands *in the
editor*, where it can be read, edited, and re-run. A non-programmer never faces a
blank box; a curious one is never boxed in.

A Scribe miss renders its hint inline, the same as the local UI.

## 4. Operator, and the key (WP-8)

Operator stays reachable, because removing it from the hosted page would
misrepresent what the project is. It is gated:

- **Collapsed by default**, behind an explicit opt-in. Scribe is the default
  engine and needs nothing.
- **The key lives in a variable, never in `localStorage`, never in a cookie, never
  in a URL.** Closing or reloading the tab loses it. This is deliberate: a
  persisted key is one XSS away from being someone else's.
- **The request goes from the reader's browser directly to Anthropic.** No host in
  this project is on that path, and there is no host in this project to be on it.
- **The panel says what the risk is, in plain language**, and links to the exact
  source lines that make the call, since the page is open source and a reader
  should be able to check rather than trust.

Direct browser access to the Anthropic API requires an explicit opt-in header.
**To be verified against current API documentation during implementation**, not
assumed; if it is unavailable, Operator degrades to an explanation of how to run
it locally, and Scribe is unaffected.

**Stated plainly, because it is a real cost:** teaching people to paste API keys
into web pages is the habit phishing depends on. The mitigations above are the
best available for a static page, and they are not the same as the risk being
zero. Scribe existing is what makes it acceptable — the key is never the only way
in.

## 5. Testing

| Layer | Approach |
| --- | --- |
| `site/glue.py` | Ordinary pytest, under CPython. Per behaviour: Scribe hit, Scribe miss, a program that runs, a program that fails to parse, a program that hits the step limit. No browser involved. |
| Examples | CI regenerates `examples.json` and fails if the diff is non-empty. The "every example ships executed" rule, enforced instead of promised. |
| The wheel | CI builds it from the same commit the page is published from, so the page can never run a different language than the repo describes. |
| Import graph | `glue.py` imports nothing from `site/` but itself; nothing in the package imports `site/`. |
| Presentation | Unchanged and already covered — `cascade.js` is copied, not modified. |

The deliberate consequence of putting the logic in `glue.py` is that **the
playground is covered by the existing suite**, not by a browser-automation rig the
project would then have to maintain.

## 6. Decomposition

| Child | What | Depends on |
| --- | --- | --- |
| **WP-A** | `site/glue.py` + its tests | nothing |
| **WP-B** | The narrative page: HTML, CSS, generated examples | nothing |
| **WP-C** | `playground.js`: Pyodide bootstrap, editor, Scribe wiring, cascade | WP-A, WP-B |
| **WP-D** | Operator panel and key handling | WP-C |
| **WP-E** | `pages.yml`: wheel build, assembly, publish | WP-A–D |
| **WP-F** | README section, and the example-freshness check in CI | WP-E |

## 7. Deliberately out of scope

- **Accounts, saved programs, permalinks, sharing, analytics** — WP-11.
- **Hosting the Python server** — still deferred, still OP-13. This does not move
  that line; it goes around it.
- **Driving the canvas from `cascade.py`.** Under Pyodide a canvas *can* import it,
  which would remove the last accepted duplication in the project. Whether
  per-frame marshalling across the Python/JS boundary is fast enough is a
  measurement, not a guess. Recorded as a question, not a goal.
- **Replacing `web-ui/`.** The local server keeps working exactly as it does.

## 8. Known risks

- **Weight.** Pyodide is several megabytes. Mitigated by loading it only on first
  playground interaction, and by the narrative being wholly independent of it —
  but a reader on a slow phone who does press the button will wait. **The actual
  figure is to be measured and stated on the page**, not guessed at here.
- **Mobile.** Running a Python runtime in a phone browser is the least-tested path
  in this design. The narrative must remain fully usable if the playground is not.
- **A pinned Pyodide version will age.** Pin it exactly rather than tracking
  latest; a CDN failure or a version that stops loading degrades to the
  pre-rendered examples rather than to a broken page.
- **`site/glue.py` couples the page to `server/sse.py`, which is not packaged.**
  A refactor of `server/` could break the page silently, since the page is not
  imported by anything. The glue tests in CI are the guard, and they are the
  reason the glue is Python rather than JavaScript.
- **Bring-your-own-key**, as set out in §4.
- **Nothing here is implemented.** Verify against the code, not against this file.
