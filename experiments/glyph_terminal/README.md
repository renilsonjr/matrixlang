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

## Files

| File | What it is |
| --- | --- |
| `translit.py` | Display-only character map. Deliberately **not** the language's glyph face — its output is never lexed, so it owes nothing to bijectivity or the round trip, which is what lets it cover the Latin alphabet at all (the language's 32 slots cannot: 24 free glyphs, 26 letters needed) |
| `demo.py` | Renders the two programs in all three modes |
