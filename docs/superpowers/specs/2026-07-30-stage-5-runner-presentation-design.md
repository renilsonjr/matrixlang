# Stage 5 Design — Runner Presentation

Status: Approved (brainstorm 2026-07-30)
Inputs: parent spec §5-Stage-5, §4.2 R-03, §3 (prior art), §1.1 (in-universe framing).

Stage 5 is the last stage of the series: digital rain on execution. It adds a presentation
layer to a language that already works, and it is deliberately last — the aesthetic is
earned, not a substitute for the machinery underneath.

Parent spec Stage 5 done-when: *"it reads as the film's aesthetic and remains debuggable."*
Both halves are binding. The second is the harder one, and most of this design serves it.

## Decisions made in this brainstorm

| # | Question | Decision |
| --- | --- | --- |
| S5-1 | Where rain sits relative to program output | A curtain **around** execution on the alternate screen buffer. Program output is untouched and byte-identical to Stage 4. |
| S5-2 | What the rain is made of | The full half-width katakana block (U+FF66–FF9D), exported from `glyphs.py` as `RAIN_ALPHABET`. The language's 32 slots are a subset. |
| S5-3 | Default or opt-in | On by default for `matrixlang run` on a TTY; `--no-rain` skips it. Suppressed automatically when stdout is not a TTY. |
| S5-4 | Fidelity | Rich: truecolor gradient, staggered column birth (density waves), and a drain phase that empties the screen before restore. Graceful degradation to 256-color and to basic green. |

## 1. Module boundaries

Three new modules. The split exists so that everything interesting is testable without a
terminal, a clock, or a subprocess.

| Module | Responsibility | Imports |
| --- | --- | --- |
| `src/matrixlang/ansi.py` | Pure escape-sequence construction and colour-capability detection. Every function returns a string. | none |
| `src/matrixlang/rain.py` | The field simulation: pure, deterministic, no time and no ANSI. | `glyphs` |
| `src/matrixlang/curtain.py` | The player: the frame loop, the clock, the writer, terminal restoration. The only impure module. | `ansi`, `rain` |

`glyphs.py` gains `RAIN_ALPHABET` — the full U+FF66–FF9D block — so the
"no katakana literal outside `glyphs.py`" constraint continues to hold, and the glyph set
stays swappable in one place (D-03).

Dependency-graph additions for `tests/test_architecture.py`'s `_ALLOWED`:

```
"ansi": set(),
"rain": {"glyphs"},
"curtain": {"ansi", "rain"},
"cli": {..., "curtain"},     # existing entry gains one member
```

`ansi.py` and `rain.py` import nothing from the toolchain beyond the glyph table, so
neither can drag the interpreter into the presentation layer or vice versa.

## 2. `ansi.py` — escapes and capability

- `ColorMode` enum: `TRUECOLOR`, `COLOR256`, `BASIC`, `NONE`.
- `detect_color_mode(env: Mapping[str, str], isatty: bool) -> ColorMode`, resolved in this
  order: not a TTY → `NONE`; `NO_COLOR` set (any value) → `NONE`; `TERM` unset or `dumb` →
  `NONE`; `COLORTERM` in `{"truecolor", "24bit"}` → `TRUECOLOR`; `TERM` contains
  `256color` → `COLOR256`; otherwise `BASIC`.
  Environment is a parameter, never read from `os.environ` inside the module — that is what
  makes the detection table-testable.
- String builders: `enter_alt_screen()`, `leave_alt_screen()`, `hide_cursor()`,
  `show_cursor()`, `move(row, col)`, `clear()`, `reset()`, and
  `fg(level: float, mode: ColorMode) -> str` mapping a 0.0–1.0 brightness to a colour in
  the given mode.

Honouring `NO_COLOR` is deliberate: it is the standard opt-out, and a presentation layer
that ignores it is a presentation layer that will be complained about.

## 3. `rain.py` — the field

`RainField(width, height, rng)` models a set of falling columns. Each column carries its
x position, a head position that advances by its own speed each tick, a trail length, and
its own glyphs, which occasionally mutate in place.

`advance()` returns the work for one frame:

- **cells to paint** — `(row, col, glyph, level)` where `level` is 0.0–1.0 brightness,
  1.0 at the head and falling toward the tail
- **cells to erase** — the positions that just fell off the end of a trail

Rendering is therefore sparse: a frame is O(active columns), not O(screen area). There is
no full-screen repaint, which is what keeps the effect from flickering and keeps the byte
volume per frame small.

Three phases, driven by a tick counter, over roughly 1.6 seconds at ~24 fps:

1. **Grow** — columns are born staggered, so the field builds in waves instead of
   appearing all at once. This is the "density waves" part of S5-4.
2. **Sustain** — spawning continues at a steady rate.
3. **Drain** — spawning stops; existing columns fall off the bottom and the screen empties.
   The dissolve is this phase, not a separate mechanism.

The field is a pure function of its seed: `RainField(w, h, Random(7))` advanced N times
produces the same cells every run, on every machine. That is the whole testing strategy.

## 4. `curtain.py` — the player

```python
def play(
    writer: TextIO,
    size: tuple[int, int],
    mode: ColorMode,
    sleep: Callable[[float], None],
    rng: Random,
) -> None
```

Everything impure is a parameter: the writer, the clock, the terminal size, the colour
mode, and the RNG. The tests pass a `StringIO`, a no-op sleep, and a seeded `Random`, so
they are instant and headless.

`play` enters the alternate screen buffer and hides the cursor, runs the frame loop inside
`try/finally`, and the `finally` **always** writes show-cursor and leave-alternate-screen.
The alternate screen is what guarantees zero scrollback residue: when the curtain ends, the
user's real screen is exactly as it was, and the program's output is the only thing that
lands on it.

A separate predicate decides whether the curtain runs at all:

```python
def should_play(mode: ColorMode, size: tuple[int, int]) -> bool
```

Rain plays only when the colour mode is not `NONE` and the terminal is at least 20 columns
by 8 rows. The TTY test is not repeated here: `detect_color_mode` already returns `NONE`
for a non-TTY, for `NO_COLOR`, and for `TERM=dumb`, so `NONE` is the single answer to
"should there be no rain." Any failure means the curtain is skipped silently — a
presentation layer must never be the reason a run fails.

Erasing is writing a space at the position: the field reports the cell, and the player
emits a cursor move plus `" "`. Nothing else clears the screen mid-curtain.

`KeyboardInterrupt` during the curtain restores the terminal and aborts the command with
exit code 130, the conventional contract. `--no-rain` is the answer to impatience; Ctrl-C
keeps meaning "stop".

Terminal size is captured once at the start and clamped against for the duration. A resize
mid-curtain is not handled: the curtain lasts 1.6 seconds, and the alternate screen
confines any consequence to a buffer that is about to be discarded.

## 5. CLI integration

`matrixlang run FILE` plays the curtain by default. `run` gains one flag:

```
--no-rain    Skip the digital rain and execute immediately.
```

No other subcommand changes. Rain plays **after a successful parse and before execution**:
a program with a syntax error reports it immediately instead of making the author sit
through an animation first.

Per R-03 — *"rain in the runner, not the editor"* — the REPL gets no rain. It is the
editing surface, and motion and legibility are adversaries there.

**The debuggability guarantee, stated so it can be tested:** when stdout is not a TTY,
`matrixlang run` writes not one escape byte. `matrixlang run p.rain > out.txt` produces
exactly the bytes Stage 4 produced.

## 6. Testing

`ansi.py` and `rain.py` are deterministic and get ordinary unit tests:

- Capability detection, table-driven over environment dictionaries, including the
  `NO_COLOR` and `TERM=dumb` opt-outs and the non-TTY case.
- Colour output per mode: truecolor emits `38;2;r;g;b`, 256 emits `38;5;n`, basic emits a
  plain green SGR, and brightness ordering is monotonic.
- Field invariants under a fixed seed: every painted cell is inside the bounds; every glyph
  comes from `RAIN_ALPHABET`; the head is the brightest cell of its column; columns are
  born staggered rather than all at tick zero; and the field fully drains — after the drain
  phase there are no cells left to paint.

`curtain.py` gets injected fakes, and two of its tests carry teeth-checks:

- **The terminal is restored even when the frame loop raises.** Inject an exception
  mid-loop, assert the show-cursor and leave-alt-screen bytes were still written. Teeth:
  delete the `finally` and watch the test fail.
- **A non-TTY writes nothing.** Assert the writer received the empty string. Teeth: bypass
  the `should_play` guard and watch the test fail.

`cli` tests: `run` on a non-TTY emits no escape bytes and produces the Stage 4 output
exactly; `--no-rain` suppresses the curtain; the existing `run` tests continue to pass
unmodified, which is itself the regression guard.

## 7. Attribution and close-out

README gains an attribution section. It credits Rezmason's project for reverse-engineering
the actual film glyphs from an archived promotional asset, and states plainly that this
project uses Unicode half-width katakana because those glyphs are WebGL vector and texture
data, not a distributable font — building one is a separate project, not a stage of this
one. Other terminal implementations (TMatrix, green_rain, RGB-digital-rain) are noted per
§3's "do not rebuild this."

Status line moves to Stage 5. Version bumps to 0.5.0.

## 8. Explicitly out of scope

- Rain in the REPL (R-03).
- Rain during execution, interleaved with output (S5-1 chose the curtain).
- A standalone `matrixlang rain` subcommand — `run` covers the demo.
- Resize handling mid-curtain (§4).
- A configurable curtain duration. The constant is tuned once; a flag is a knob nobody
  needs.
- Any attempt to build or ship a film-glyph font (§7).
