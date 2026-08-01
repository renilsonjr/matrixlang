# Spike: is a glyph-only terminal usable?

Answers [#22](https://github.com/renilsonjr/matrixlang/issues/22) by building the
thing and looking at it, rather than reasoning about it.

**Not part of the shipped package.** Nothing under `src/matrixlang/` imports it,
it adds no dependency, and it changes no behaviour. Delete the directory and the
project is unaffected.

```bash
.venv/bin/python experiments/glyph_terminal/demo.py
```

It renders the same two programs three ways: plain, operator view (source in
glyphs, diagnostics plain — today's REPL `:glyph` mode), and full glyph
(everything transliterated, which is what #22 proposes).

---

## Result: the proposal splits cleanly in two, and only half survives

### Full-glyph **output** works, and looks the part

```
source:
  ｱ name ﾅ "Neo"
  ｱ n ﾅ ｦ
  ﾃ n ｻ ｩ
    ﾄ "wake up, " ﾀ name
    n ﾅ n ﾀ ｧ
  ﾗ
output:
  ｼｦｰｪ ｺｵ, ｳｪｴ
  ｼｦｰｪ ｺｵ, ｳｪｴ
  ｼｦｰｪ ｺｵ, ｳｪｴ
```

`ｼｦｰｪ ｺｵ, ｳｪｴ` is `wake up, Neo`. Word boundaries survive, the shape of the
output is legible as *structure* even when the characters are not, and it is
unmistakably the aesthetic the project is after. **This is worth shipping as a
toggle.**

### Full-glyph **diagnostics** are unusable, and worse than expected

The test is the most common error anyone makes — a typo in a name:

```
construct name = "Neo"
trace "wake up, " + nme
```

| Mode | Error |
| --- | --- |
| plain | `matrixlang: [line 2, column 21] 'nme' is not declared — use 'construct' first` |
| operator view | `matrixlang: [line 2, column 21] 'nme' is not declared — use 'construct' first` |
| **full glyph** | `ｲｦｹｷｮｽｱｦｳｬ: [ｱｮｳｪ ｨ, ｨｴｱｺｲｳ ｨｧ] 'ｳｲｪ' ｮｸ ｳｴｹ ｩｪｨｱｦｷｪｩ — ｺｸｪ 'ｨｴｳｸｹｷｺｨｹ' ｫｮｷｸｹ` |

You cannot fix your own typo. The line and column numbers are glyphs, the
misspelled name is glyphs, and the suggested remedy is glyphs. Every affordance
the error message exists to provide is gone.

### The finding the research did not predict

Look at mode 3's source and error together:

```
source:  ﾄ "wake up, " ﾀ nme        ← the typo is ASCII, per D-03
error:   … 'ｳｲｪ' ｮｸ ｳｴｹ …          ← the same typo is glyphs
```

**A full-glyph mode is internally inconsistent with the language's own design.**
D-03 deliberately keeps identifiers in ASCII — *"in a wall of green, the only
Latin text is the thing you need to find."* So the source shows you `nme`, the
diagnostic shows you `ｳｲｪ`, and you cannot match one to the other by eye.

Transliterating diagnostics does not merely make them hard to read. It breaks the
one property D-03 was written to guarantee.

---

## What this confirms, and what it changes

**Confirms the prior-art finding empirically.** Every glyph language since APL
keeps diagnostics in natural language — Dyalog reports `DOMAIN ERROR`, not a
symbol. The reason turns out to be visible in ten lines of output: glyphs are a
notation for expressions a fluent reader already holds in their head, and an
error is the moment fluency has failed.

**Changes the recommendation from "probably don't" to "here is exactly where the
line goes."** It is not that glyphs are unreadable — the working program's output
above is fine, and arguably better than plain text for this project's purposes.
It is that *diagnostics specifically* are the one category of text whose entire
job is to work when the reader is lost.

## Suggested resolution for #22

1. **Ship full-glyph output as a toggle.** It works, it looks right, and the
   transliteration is ~40 lines. `translit.py` here is a working starting point.
2. **Keep diagnostics in plain text, always.** Not a default to override — a
   property. Sixty years of prior art, and now this.
3. If a total-immersion mode is still wanted, make it explicit and self-limiting:
   glyph everything *including* errors, with a documented single keystroke back
   to plain. Sold as an aesthetic mode, not as a working environment.

---

## `live.py` — the cascade *is* the program

The static demo above answered "can you read glyph text." It did not test the
actual proposal, which is a cascade that **carries the software** rather than
decorating it.

```bash
python experiments/glyph_terminal/live.py                        # built-in demo
python experiments/glyph_terminal/live.py examples/hello.rain    # your own file
python experiments/glyph_terminal/live.py --frames 30            # frames as text
```

Every falling column carries real material from the program. Nothing is random:

| Column | Content | Rendering |
| --- | --- | --- |
| **source** | a line of the program in its glyph face | green, falls faster |
| **output** | a value the program actually produced, transliterated | brighter, falls slower so results linger |

A frame, mid-run:

```
                     ｱ                                   "        ｼ
                        ﾃ                                w        ｦ
                     n                          ｩ        a        ｰ
                     a  n                                k        ｪ
                     m                                   e
                     e  ｻ                                         ｺ
                                                         u        ｵ
ﾌ                    ﾅ  ｪ              n                 p        ,
```

Read the columns downward: `ｱ name ﾅ` is `construct name =`. Next to it,
`ﾄ "wake up,` is the `trace` statement. On the right, `ｼｦｰｪ ｺｵ,` is the
program's actual output — `wake up,` — transliterated and falling brighter.

**This is the readout of state from parent spec §1.1**: Cypher watching the
Matrix and seeing what it means rather than what it says. It is a categorically
different thing from the Stage 5 curtain, which is random glyphs played *before*
execution with no connection to your code.

### Two bugs worth recording, because both were invisible in the decorative rain

1. **Column reuse.** The first version returned a column's x to the free pool as
   soon as it spawned, so two streams could share a column and overwrite each
   other. This is the exact defect the Stage 5 review found in `rain.py`. In the
   decorative rain it was nearly unnoticeable — random glyphs all look alike. Here
   it silently corrupts a line of your program. Now verified: 0 overlapping cells
   across 30 seeds × 80 frames.
2. **Reversed lines.** The obvious layout — first character at the head — renders
   every line *backwards*. Harmless when nobody reads the glyphs; fatal when the
   columns *are* the program. Lines now read top-to-bottom in natural order.

Both make the same point: **content-carrying rain has correctness requirements
that decorative rain does not.** Anything built from this needs its own tests,
not the existing rain's.

---

## `shell.py` — an interactive terminal, and a decodable dictionary

```bash
python experiments/glyph_terminal/shell.py                 # the terminal
python experiments/glyph_terminal/shell.py --table         # the dictionary
python experiments/glyph_terminal/shell.py --script 'a;b'  # headless
```

Inside it, `:load path/to/file.rain` pulls a file into the session. The file is
fed line by line through the same session as typed input, so it behaves exactly
as if you had typed it — blocks buffer, state persists, and a diagnostic stops
the load and lands in the status line rather than the cascade.

Type MatrixLang at the prompt. Every statement and every value it produces
joins the falling cascade in glyphs. The screen is not a log with an animation
behind it — the animation is the session.

```
┌────────────────────────────────────┐
│   your statements and their output │  glyphs, falling
│   falling as glyphs                │
├────────────────────────────────────┤
│ matrixlang: [line 1, column 7] …   │  errors, plain text
│ > construct x = 5                  │  what you are typing, ASCII
└────────────────────────────────────┘
```

Two things stay readable, for different reasons. **The input line is ASCII**
because you cannot touch-type an alphabet you are still learning — that is
D-03's authoring view, not a compromise. **Diagnostics are plain** because the
static spike proved transliterated ones are unusable.

### The dictionary is reversible, which is the point

`translit.py` is now a complete text-to-glyph map with a guarantee:

```
untransliterate(transliterate(text)) == text        for ALL text
```

Verified over 4,000 fuzzed strings including uppercase, digits, punctuation and
non-ASCII — zero failures. So the glyph output is **decodable**: a person, a
program or a model holding the table can read the screen exactly.

```
$ trace "wake up, " + name
  source  ﾄ "wake up, " ﾀ name
  output  ﾁ｡ｵ･ ｿｺﾆ ﾙｸ･ｹ      (decodes to 'wake up, Neo')
```

Three decisions make reversibility hold, and the first is the one a first
attempt gets wrong:

1. **Uppercase uses a shift glyph** (`ﾙ`). Case-folding is shorter and is what
   you reach for first, but `Neo` and `neo` would render identically and no
   reader could recover which was meant.
2. **Uncovered characters pass through unchanged, and that is still reversible** —
   the glyph alphabet is disjoint from ASCII, so a decoder always knows which is
   which. No escape sequences to get wrong.
3. **Space stays a space.** Encoding it gains nothing and destroys the word
   boundaries that make the result legible as structure.

`--table` prints the dictionary for exactly this purpose: hand it to a model with
a line of glyphs and it can recover the text with no other context.

### A bug worth recording: blocks are not lines

The first version rendered each entered line separately. A `dejavu` body line is
not a parseable program on its own, so the loop body never reached the cascade at
all and `flatline` spilled out as raw ASCII. Statements are now buffered and
rendered **as a complete block**:

```
$ dejavu n < 3 / trace "wake up" / n = n + 1 / flatline
  source ﾃ n ｻ ｩ
  source ﾄ "wake up"
  source n ﾅ n ﾀ ｧ
  source ﾗ
```

### What it still does not do

- **Not incremental.** Output is collected per statement, not streamed as it is
  produced. Watching a long-running loop emit results into the rain *as it runs*
  would need the interpreter to yield events during execution.
- **No external commands.** This is a MatrixLang REPL, not a shell — no process
  spawning, pipes, redirection or job control. #22 covers why every shipping
  programmable shell kept an escape hatch to ordinary commands, and why that is
  the expensive half of the idea.

## Files

| File | What it is |
| --- | --- |
| `translit.py` | Display-only character map. Deliberately **not** the language's glyph face — its output is never lexed, so it owes nothing to bijectivity or the round trip, which is what lets it cover the Latin alphabet at all (the language's face cannot: 35 of the block's 56 glyphs are taken, leaving 21 where 26 letters are needed) |
| `demo.py` | Static: the two programs in all three modes |
| `live.py` | Animated: the cascade carrying a program that has run |
| `shell.py` | Interactive: type MatrixLang, watch the session cascade |
