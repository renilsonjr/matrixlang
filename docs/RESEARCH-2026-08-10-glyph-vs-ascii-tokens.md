# Research: the token cost of MatrixLang's ASCII vs glyph face

**Closes #12.** Measures the claim #11 inferred from byte counts but flagged as
unmeasured: that the glyph face, despite being visually denser and having fewer
*characters*, costs more LLM *tokens* than the ASCII face.

**Verdict: the hypothesis is confirmed, and by a wider margin than the
inference predicted.** The glyph face costs **70–80% more tokens on average**,
on two different tokenizer families, and was never once cheaper across 30
sampled programs.

## Method

Exactly the method #12 specified, run in a scratch venv outside this repo
(`pip install tiktoken`; this repo stays dependency-free) with `src/` on
`PYTHONPATH`:

1. `examples/hello.rain`, the reference program #11 hand-counted.
2. 30 programs from `tests/treegen.gen_program`, seed `20260810`, for size
   variety — 14 to 694 ASCII characters. One degenerate empty program was
   skipped; 29 generated programs plus `hello.rain` = 30 measured.
3. Both faces rendered with the real `render_ascii`/`render_glyph`, tokenized
   with `tiktoken`'s `cl100k_base` (GPT-3.5/4 family) and `o200k_base` (GPT-4o
   family).
4. `anthropic.count_tokens` was **not** run — it needs a live API key, and this
   spike was scoped to no API spend, per the issue.

```python
import tiktoken
from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.render import render_ascii, render_glyph

enc = tiktoken.get_encoding("o200k_base")
tree = parse(lex(open("examples/hello.rain").read()))
for name, text in (("ascii", render_ascii(tree)), ("glyph", render_glyph(tree))):
    print(name, len(enc.encode(text)), "tokens")
```

## Result

| | `cl100k_base` | `o200k_base` |
| --- | --- | --- |
| Mean per-program ratio (glyph ÷ ASCII) | **1.775×** | **1.699×** |
| Median | 1.797× | 1.718× |
| Min (best case for glyph) | 1.125× | 1.125× |
| Max (worst case for glyph) | 2.576× | 2.333× |
| Aggregate (sum tokens / sum tokens) | 3044 → 5517 = **1.812×** | 3029 → 5257 = **1.736×** |

**The glyph face was more expensive on every single one of 30 programs, on
both tokenizers.** The minimum ratio observed was 1.125× — there was no
program, however small or large, where glyph broke even with ASCII, let alone
beat it.

For the reference example specifically:

| Face | Characters | UTF-8 bytes | `cl100k_base` tokens | `o200k_base` tokens |
| --- | --- | --- | --- | --- |
| ASCII | 222 | 222 | 81 | 80 |
| Glyph | 165 (**−26%**) | 207 (−7%) | 108 (**+33%**) | 103 (**+29%**) |

The character-count reduction (26%) matches #11's hand count exactly, which is
the cross-check that these are the same renderings #11 reasoned about. The
byte count (207, +7% over ASCII) also matches. Tokens invert the character
story: **26% fewer characters, but 29–33% more tokens** on this one example —
and the 30-program sample shows the single example undersold the effect;
larger and more varied programs average closer to +70–80%.

## Interpretation

This confirms #11's inference and sharpens it. The byte-count argument
predicted the glyph face would be "likely worse" in tokens; the measured
effect is not marginal — it is close to **double** the token cost on average.
The mechanism #11 named holds up: `construct`, `trace`, `flatline` and
friends are common strings with rich learned BPE merges, and half-width
katakana (U+FF66–FF9D) are rare in code corpora and tokenize closer to the
byte level, so each 3-byte glyph frequently costs more than one token where a
whole keyword costs one.

**Visual density is not token density**, demonstrated on a system this
project built and controls, not inferred from an external benchmark.

## What this means downstream

- **#11's conclusion stands, now with a measured number instead of an
  inference.** The glyph face should never be assumed cheaper for LLM I/O —
  if anything, prefer ASCII when token cost matters (e.g. what Operator sends
  and receives).
- **#13's kill criterion is unaffected** — #13 is about a *different*,
  purpose-built compact DSL, not MatrixLang's glyph face, and remains blocked
  on its own Stage 0 measurement.
- The playground's cascade shows the glyph face because it is a *display*
  choice (the wall is the point, per `docs/adr/0001`), not because it is
  cheaper to generate or transmit. This research does not change that — the
  cascade never sends glyphs to an LLM, and this measurement doesn't bear on
  the wire-naming question in ADR-0001.

## Caveats

- `anthropic.count_tokens` was not measured (no API key used for this spike).
  The two `tiktoken` families measured here are BPE tokenizers with similar
  design to Claude's; there is no specific reason to expect Claude's tokenizer
  to invert the direction of this result, but that is an inference, not a
  measurement — flagged the same way #11 flagged its own byte-based inference.
- 30 programs is a spike-sized sample (~2 hours of effort, per the issue's own
  estimate), not an exhaustive one. Every program in the sample agreed on
  direction and rough magnitude, which is what a spike needs to decide a kill
  criterion; a larger corpus would tighten the confidence interval, not
  change the conclusion.
