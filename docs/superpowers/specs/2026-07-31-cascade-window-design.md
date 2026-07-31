# Cascade Window Design — the output device

Status: Approved (brainstorm 2026-07-31)
Inputs: parent spec §1.1 (in-universe framing), Stage 5 design (purity gradient, TTY
gating), `experiments/glyph_terminal/README.md` (the spike and its two bugs), GitHub #24
(the f07 umbrella), #21 (functions), #16 (web layer).

Stage 5 gave the language a presentation layer: a curtain of random glyphs played *before*
execution, with no connection to the program. This design replaces the presentation layer
with an **output device** — a native window in which the program's source and its actual
output fall as glyphs, streamed while execution happens.

The in-universe framing and the engineering land on the same answer again. In the films the
falling code is not authored; it appears on operator monitors as a rendering of live system
state, read fluently by people watching a running world. That is a monitoring surface fed by
an event stream, which is what §1 below specifies.

Umbrella done-when: *"the cascade is the output, and the output is readable."* Both halves
bind. The second is the harder one, and §4 serves it.

## Decisions made in this brainstorm

| # | Question | Decision |
| --- | --- | --- |
| CW-1 | Does the window replace text output | **No.** The window is the default display on a TTY; redirected and piped stdout stay byte-identical to today. That property is what keeps programs testable in CI. |
| CW-2 | Toolkit | **`tkinter`** — standard library, verified on Python 3.14.3 / Tk 8.6, so the zero-third-party-dependency property survives a real window. |
| CW-3 | One backend or several | A **display protocol** with backends behind it. Text ships today, Tk is CW-3's work, the browser (#16) becomes a second implementation rather than a competing project. |
| CW-4 | When output is emitted | **During execution**, as an event stream. Collecting per statement is what made the spike's cascade non-incremental. |
| CW-5 | Are diagnostics transliterated | **Never.** Settled empirically by the spike; see §5. |
| CW-6 | Does the window outlive the program | **Yes**, until dismissed. A program finishing in 200 ms would otherwise flash and vanish with its output unread. |
| CW-7 | What the window does once the program has finished | **Output pins, ambient keeps falling.** Added after running it: see §10. |

## 1. Module boundaries

The Stage 5 purity gradient extends across the new work unchanged: everything interesting is
testable without a window, a clock, or a thread.

| Module | Responsibility | Imports |
| --- | --- | --- |
| `src/matrixlang/events.py` | The execution event vocabulary. Pure data. | none |
| `src/matrixlang/translit.py` | The reversible character table, promoted from `experiments/`. Pure. | none |
| `src/matrixlang/cascade.py` | The content-carrying field simulation: which glyph is in which cell at which brightness. Pure, deterministic, seeded. | `glyphs`, `translit` |
| `src/matrixlang/display.py` | The `Display` protocol and backend selection. Pure decision function plus the text backend. | `events`, `ansi` |
| `src/matrixlang/window.py` | The Tk backend. Threading, the canvas, the frame loop. The only module that touches a window. | `cascade`, `display`, `events` |

Dependency-graph additions for `tests/test_architecture.py`'s `_ALLOWED`:

```
"events":    set(),
"translit":  set(),
"cascade":   {"glyphs", "translit"},
"display":   {"events", "ansi"},
"window":    {"cascade", "display", "events"},
"interpreter": {..., "events"},    # existing entry gains one member
"cli":         {..., "display", "window"},
```

The load-bearing assertion: **no core module may import `window`.** The interpreter knows
about events and nothing else, exactly as `repl` must not import `curtain`. A backend that
leaked into the interpreter would make the language unrunnable without a display.

## 2. `events.py` — the execution event stream

`interpreter.py:59` currently does:

```python
print(to_display(self._evaluate(stmt.value)), file=self._out)
```

That becomes an emit into a sink.

| Event | Emitted when | Consumed as |
| --- | --- | --- |
| `Statement(node, line)` | a statement begins executing | source columns |
| `Output(text, line)` | a `trace` produces a value | output columns |
| `Error(diagnostic)` | execution fails | plain text, always |

**The property that makes this reviewable:** the default sink is a `TextSink` wrapping
today's `TextIO` and printing exactly what it prints now. Stdout stays byte-identical and
the existing suite proves it. This is a refactor plus a new consumer, not a behaviour
change — and if any existing test moves, the refactor is wrong.

## 3. `display.py` — protocol and selection

`open()`, `emit(event)`, `close()`. Selection reuses the shape of `curtain.should_play`,
which is already table-tested:

| Condition | Result |
| --- | --- |
| stdout is not a TTY (pipe, redirect, CI) | text — no window |
| `--no-window`, or `NO_COLOR` | text |
| no display available, or `tkinter` import fails | text, plus one line on stderr |
| otherwise | window |

```
matrixlang run app.rain                → window opens, glyphs cascade
matrixlang run app.rain > out.txt      → plain text, byte-clean, no window
matrixlang run app.rain --no-window    → plain text in the terminal
```

CW-1 is a property, not a default to be overridden.

## 4. `translit.py` — why the cascade is output and not decoration

The guarantee, already verified in the spike over 4,000 fuzzed strings:

```
untransliterate(transliterate(text)) == text        for ALL text
```

Three decisions make it hold, and the first is the one a first attempt gets wrong:

1. **Uppercase uses a shift glyph.** Case-folding is shorter, but `Neo` and `neo` would
   render identically and no reader could recover which was meant.
2. **Uncovered characters pass through unchanged**, which is still reversible because the
   glyph alphabet is disjoint from ASCII. No escape sequences to get wrong.
3. **Space stays a space** — it destroys nothing and preserves the word boundaries that
   make the result legible as structure.

This table is **not** the language's 32-slot glyph face and must not be merged with it. Its
output is never lexed, so it owes nothing to bijectivity or the round-trip criterion — which
is precisely what lets it cover the Latin alphabet at all. The language's 32 slots cannot:
24 free glyphs, 26 letters needed.

## 5. Diagnostics stay plain

Not a default. A property.

The spike ran the most common error anyone makes — a typo in a name — through a fully
transliterated diagnostic:

```
ｲｦｹｷｮｽｱｦｳｬ: [ｱｮｳｪ ｨ, ｨｴｱｺｲｳ ｨｧ] 'ｳｲｪ' ｮｸ ｳｴｹ ｩｪｨｱｦｷｪｩ — ｺｸｪ 'ｨｴｳｸｹｷｺｨｹ' ｫｮｷｸｹ
```

Line and column, the misspelled name, and the suggested remedy are all gone. Worse, it
breaks D-03: identifiers stay Latin so that *in a wall of green, the only Latin text is the
thing you need to find*. A transliterated diagnostic shows you `ｳｲｪ` while the source shows
you `nme`, and no reader can match them by eye.

Diagnostics render as plain text in a status strip in the window, and on stderr.

Sixty years of prior art agree: every glyph language since APL reports `DOMAIN ERROR`, not a
symbol. Glyphs are a notation for expressions a fluent reader already holds in their head,
and an error is the moment fluency has failed.

## 6. `window.py` — the Tk backend

A canvas of `w × h` cells, one glyph per cell, brightness mapped to colour. Two column
kinds, both prototyped in `experiments/glyph_terminal/live.py`:

| Column | Content | Rendering |
| --- | --- | --- |
| source | a line of the program in its glyph face | green, falls faster |
| output | a value the program actually produced, transliterated | brighter, falls slower so results linger |

**Threading is the risk.** Tk is not thread-safe. The interpreter runs on a worker thread and
pushes events into a `queue.Queue`; the UI thread drains it under `after()`. Build this
first — it is the only part of the design whose failure forces a rethink rather than a fix.

**Failure never propagates.** Any Tk problem falls back to text with one line on stderr, and
exit codes are unchanged. An interpreter error leaves the window open with the diagnostic in
the status strip.

## 7. Testing

| Layer | Approach |
| --- | --- |
| Event stream | Pure. Assert the event sequence for a given program |
| Cascade field | Pure and seeded, as `rain.py` is. **Regression tests for both spike bugs: zero overlapping cells across seeds × frames, and lines reading top-to-bottom** |
| Backend selection | Table test over (isatty, display present, flags), as `detect_color_mode` is tested |
| Tk backend | Frame stream asserted; pixels are not |
| Architecture | No core module imports `window` |

The two spike bugs are named because both were invisible in decorative rain and both
silently corrupt a program in content-carrying rain. **Content-carrying rain has correctness
requirements decorative rain does not**, and inheriting `rain.py`'s tests is not sufficient.

Every load-bearing guard here gets a teeth-check: inject the bug, watch the test fail, revert.

## 8. Deliberately out of scope

- **Functions, collections and I/O** — #21. A window is a display; it does not make the
  language general-purpose, and this design must not be read as claiming otherwise.
- **The browser backend** — #16, a second implementation of §3's protocol.
- **The film's actual glyphs.** Rezmason's reverse-engineered TTFs now exist, which
  invalidates the README's "not a font" note, but a font swap is `glyphs.py`'s problem and
  independent of this work.

## 9. Known risks

- **macOS Tk rendering half-width katakana** is the most likely thing to look wrong. Probe
  the font on day one, not at the end.
- **Performance is unproven.** Mitigation is redrawing only changed cells, which the field
  already computes. If an 80×40 grid cannot hold a usable frame rate, the answer is #16, not
  more Tk tuning.
- **Pixel quality stays unverified by tests**, consistent with the existing admission that
  the curtain's visual quality is a human judgment never formally captured.
- **Tk is a 1990s toolkit**, chosen because it is the only route to a real window that keeps
  the zero-dependency property. That is a genuine constraint of this project rather than a
  preference, and it belongs in the record rather than in a review comment.

---

## 10. CW-7, and two corrections the design earned by being run

Everything above was written before the thing existed. Running it produced
one design decision the spec had no way to anticipate, and it went through two
wrong answers first.

**Wrong answer one: the cascade drained.** CW-6 said the window outlives the
program. It did — and the *output* did not. `hello.rain` emits 15 events, the
field emptied after ~109 frames (3.6s), and the window then sat black forever.
Every acceptance criterion in §7 passed while the feature did not do its job,
because none of them asked what is on screen after execution ends.

**Wrong answer two: the output settled and everything stopped.** Pinning the
transcript fixed the black screen and replaced it with a still image. A screen
that stops moving is not a cascade; that trade bought readability by giving up
the entire point.

**CW-7, the answer that is both.** The transcript pins, bright, and an
**ambient layer keeps falling behind it** — filler glyphs from the katakana
block, capped at `AMBIENT_LEVEL = 0.3` so they can never be mistaken for the
head of a stream carrying real material. Output stays readable; the window
never stops.

Three consequences worth recording:

- **`AMBIENT_ALPHABET` returns to `glyphs.py`.** It was deleted a commit
  earlier as dead code, on the reasoning that nothing samples random glyphs
  once the cascade carries the program. That reasoning was right about the
  program layer and wrong about there being only one layer. It now has a real
  consumer.
- **Ambient clears whole rows, not cells.** A filler glyph landing immediately
  after your last character makes it impossible to see where the output ends,
  and colour alone does not fix that. The transcript gets a clear band.
- **The same column-reuse bug reappeared in the new code.** Ambient columns
  were sampled independently and two could land on the same x. Third time this
  defect has appeared in this project; it is now fixed by construction
  (`rng.sample`) rather than by vigilance.

The general lesson, and the reason this section exists: **the spec's testing
strategy was sound and its acceptance criteria were not.** Criteria that
describe what the code does can all pass while the feature fails. The two
defects here were both found by a human opening the window and looking at it,
which no part of §5 or §7 required anyone to do.
