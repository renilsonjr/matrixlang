# Interactive input in the browser — re-running a pure program

Status: **Approved as a design. Nothing is implemented.**
Inputs: `2026-08-19-jackin-input-design.md` (which established buffered input
and named a resumable interpreter as out of scope), `site/glue.py` (the
browser's Python half, and the only file whose behaviour changes),
`src/matrixlang/values.py` (`CyclicValue`/`Incomparable`/`TooManyDigits` — the
signal pattern §5 copies), `site/checks/no_semantics.py` (the browser owns no
language logic), GitHub #118.

In the browser, `jackin` reads answers supplied **before** the program runs.
A program cannot ask and wait. Translated faithfully from Python, this prints
its prompt and sails past it:

```
trace "Digite a matricula ou nome: "
construct search = jackin
```

At a terminal the same program is genuinely interactive. Only the page is not.

## Decisions

| # | Question | Decision |
| --- | --- | --- |
| IX-1 | How interaction works | **Re-run the program from the start** with an accumulating list of answers, once per prompt. |
| IX-2 | Why that is sound | MatrixLang is deterministic and its only effect is `trace`, so a re-run reproduces the earlier output exactly. See §2 — this is verified, not assumed. |
| IX-3 | Language changes | **None.** `jackin` is untouched. A program's own `trace` is its prompt, exactly as at a terminal. |
| IX-4 | The existing Input box | **Stays**, front-loading the first answers. When they run out, the page starts asking. Strict superset of today's behaviour. |
| IX-5 | Where the reader reads the question | The answer row carries the program's most recent output line as **readable Latin text**. The cascade is glyphs and is a poor place to read a prompt. |
| IX-6 | How the cascade behaves across re-runs | It is fed **only the new suffix** each round, never replayed. See §3. |
| IX-7 | How exhaustion is detected | A private sentinel exception from a `glue.py`-local `InputSource`, **not** by matching a diagnostic string. See §5. |
| IX-8 | Runaway programs | A cap of **100 rounds** per session, reported the way the step limit is. |
| IX-9 | Scope guard | `site/` and its tests only. `src/matrixlang/`, `server/`, the CLI and the REPL are untouched — they already block on real stdin. |

## 1. Why not the usual approaches

**A resumable interpreter** — generators or `async`, so `jackin` suspends — is
the correct general answer and stays cheap as prompts multiply. It is also a
deep refactor: `interpreter.py` is 742 lines, the walk is recursive, and all
seven `run()` call sites (CLI ×2, REPL, `operator/validate.py`,
`server/runs.py`, `site/glue.py`, and the module-level helper) would need a
driver loop. Every prior spec named this out of scope; this one does too.

**Blocking via `Atomics.wait` on a `SharedArrayBuffer`** in a worker is the
standard Pyodide answer, and it is **unavailable here**. Measured on the
deployed site:

```
crossOriginIsolated: false
SharedArrayBuffer:   undefined
Atomics.wait:        present but useless without a SharedArrayBuffer
```

GitHub Pages cannot send the COOP/COEP headers that unlock it — the same
limitation that already forces `index.html` to declare its CSP in a meta tag.
A service-worker shim can fake cross-origin isolation, but it intercepts every
request on the site and interacts with a deliberately locked-down CSP; too
much fragility for the benefit.

## 2. The property this rests on (IX-2)

Re-running sounds like it should be observable. It is not, because of what
this language happens to be:

- No clock, no randomness, no files, no network. `trace` is the only effect —
  verified by inspection of the interpreter.
- Therefore execution is a pure function of (source, answers).

Two consequences, both measured on a real program through `glue.run` rather
than reasoned about:

- Ten identical runs produce a byte-identical event stream.
- Running with fewer answers produces a strict **prefix** of the output
  produced with more.

So round *n+1* reproduces every event round *n* already showed, in order, and
then continues. The reader cannot tell a re-run from a resumption.

**This is load-bearing.** The day MatrixLang gains `random` or a clock, this
design breaks *silently* — output would differ between rounds and the cascade would
show a history that never happened. §7 requires a test that fails if the
property stops holding, so whoever adds a non-deterministic effect finds out
here rather than from a bug report.

## 3. The cascade must not restart (IX-6)

`runProgram` today clears the cascade and feeds it every event. Re-running
that way would replay the entire falling-glyph animation on every answer —
visually broken, and it would lose the reader's place in their own output.

Because output is prefix-consistent (§2), the page instead remembers how many
events it has already drawn and feeds the cascade **only `events.slice(drawn)`**
each round. The animation is continuous; as far as the cascade knows, the
program never stopped.

`cascade.clear()` therefore happens **once**, when Run is pressed — not once
per round.

## 4. What the reader sees (IX-5)

The cascade shows transliterated glyphs. Reading a prompt there is genuinely
hard, so the answer row carries the last output line as plain Latin text:

```
Digite a matricula ou nome:
> [ ana                    ]  ( Answer )
```

The row is hidden except while waiting. This gives the terminal shape without
adding a transcript pane, and it means the prompt a reader sees is exactly the
text their own program produced.

If the program has traced nothing yet, the row shows a neutral label rather
than an empty space — a program may legitimately read before printing.

## 5. Detecting exhaustion (IX-7)

Not by matching `"no input left to read"`. That message is a *diagnostic*;
making control flow depend on its wording would mean a reworded error silently
changes behaviour.

Instead `glue.py` defines its own source and a private sentinel:

```python
class _NeedsInput(Exception):
    """The program asked for a line the reader has not given yet."""


class _InteractiveSource:
    """Answers so far; asking past the end suspends rather than fails."""

    def __init__(self, answers: list[str]) -> None: ...
    def next_line(self) -> str | None:
        # raises _NeedsInput when exhausted, instead of returning None
```

`run()` catches `_NeedsInput` alongside `MatrixLangError` and returns the
events collected so far plus a terminal `{"kind": "needs_input"}`.

This is the shape `values.py` already uses three times — `CyclicValue`,
`Incomparable` and `TooManyDigits` are non-`MatrixLangError` signals raised
low and caught high. The difference is that this one passes *through* the
interpreter rather than being caught by it, which is safe: the interpreter has
no cleanup, and `recursion_guard` is a context manager that exits correctly on
any exception.

**`run()` still never raises.** That contract has been broken three times by
unguarded integer conversions and is not to be broken a fourth: `_NeedsInput`
is caught in the same `try` that catches `MatrixLangError`.

Non-interactive callers are unaffected. `run(source, stdin="…")` with no
interactive flag keeps today's behaviour exactly — exhaustion is still the
familiar error — so `tests/test_site_glue.py`'s existing expectations and the
tutorial's §17 description both stand.

## 6. The cap (IX-8)

The page counts rounds and stops at **100**, reporting it in the shared
diagnostic slot:

```
this program asked for more than 100 answers — stopped
```

`dejavu true` around a `jackin` then fails loudly rather than prompting
forever while each round re-executes more work than the last. The count lives
in `playground.js` because the loop does; the message is UI text, not language
behaviour, so `no_semantics.py` is unaffected.

## 7. Module boundaries

| Path | Change | Why |
| --- | --- | --- |
| `site/glue.py` | `_NeedsInput`, `_InteractiveSource`, and an interactive mode on `run()`. | The browser's Python half — the only place this logic can live without putting language behaviour in JavaScript. |
| `site/playground.js` | The round loop, suffix-only cascade feeding, the answer row, the cap. | |
| `site/index.html` | The answer row markup. | |
| `site/style.css` | Its styling. | |
| `tests/test_site_glue.py` | Interactive-mode tests, and the determinism property of §2. | |
| `site/tests/dom.mjs`, `playground.test.mjs`, `index-html.test.mjs` | The new ids and the round loop. | |
| `src/matrixlang/`, `server/`, `cli.py`, `repl.py` | **Untouched.** | IX-9. They block on real stdin already. |

**Load-bearing assertions:**

- `site/checks/no_semantics.py` passes unmodified — the JS gains a loop and a
  text field, no language logic.
- `site/checks/key_handling.py` passes unmodified — no persistence sink.
- `glue.run`'s existing signature and behaviour are unchanged for callers that
  do not opt in.

## 8. Testing

| Layer | Approach |
| --- | --- |
| The determinism property | The load-bearing one. Assert that repeated `glue.run` of the same source and answers gives an identical event stream, and that a shorter answer list yields a strict prefix of a longer one's output. **This is the test that must fail if the language ever gains a non-deterministic effect.** |
| Interactive mode | `glue.run` with too few answers returns `needs_input` as its terminal event, with the output so far intact; with enough answers it finishes normally; a genuine runtime error is still an `error` event, not `needs_input`. |
| Non-interactive mode | Unchanged behaviour, pinned — exhaustion is still the familiar error. |
| The round loop and suffix feeding | `site/tests/` against the stub DOM: three rounds feed the cascade 0-to-n, n-to-m, m-to-end and never re-feed a prefix. |
| The cap | Stops at the limit and reports it. |
| The whole thing | A real browser: run the employee program with an empty Input box, answer the prompt, see the result — and confirm the cascade did not restart. |

## 9. Deliberately out of scope

- **A resumable or async interpreter.** §1. Still correct in general; still a
  deep refactor of the module everything rests on. If prompt-heavy programs
  make re-running hurt, this is the upgrade, and the UI built here carries over.
- **A COOP/COEP service-worker shim.** §1.
- **Any language change**, including a prompt argument for `jackin`. IX-3.
- **The CLI and REPL.** IX-9.

## 10. Known risks

- **The determinism property could be broken by a future feature** and the
  breakage would be silent. §2, and §8's first test is the guard.
- **Re-running is O(n²) in prompts.** Fine for a handful; a prompt inside a
  long loop degrades. The cap bounds the damage, and §9 names the upgrade.
- **The step limit applies per round, not per session.** A program near the
  limit could pass early rounds and fail a later one, which reads as
  nondeterminism to someone who does not know why. Worth a comment at the
  call site.
- **Prefix-feeding the cascade assumes the JS count and the event list stay in
  step.** If a round ever returned fewer events than the last, `slice` would
  silently show nothing. §2 makes that impossible, but the code should assert
  it rather than trust it.
- **Nothing here is implemented.** Verify against the page, not against this
  file.
