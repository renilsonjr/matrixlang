# Research: Stage 0 of the compact-DSL spike — killed at the spreadsheet

**Addresses #13's Stage 0.** #13 proposes an LLM emitting a compact textual
DSL that a local, deterministic expander turns into working code, for fewer
output tokens than generating the code directly. Its own Stage 0 gate: hand-write
DSL equivalents for ~20 reference tasks, tokenize both, and **stop unless the
DSL is ≥2× denser in tokens** — "no downstream engineering recovers a premise
that fails on a spreadsheet."

**Verdict: it fails the spreadsheet.** The DSL designed and tested here is
**0.911× as dense as plain Python — worse, not better** — on both tokenizer
families measured. Per #13's own kill criterion, the spike stops here. Stage 1
and Stage 2 (which call a live model against a real task corpus, twice, at
real cost) were not started.

This is the same shape of result as #12: something that looks compact to a
human eye (fewer characters) costs *more*, not fewer, tokens once it meets a
BPE tokenizer trained on ordinary source code.

## What was built, and why it's more than a paper design

A DSL that only exists as a density estimate proves nothing about whether it
could ever actually be an expander's input — so before measuring, this
verifies the grammar is real:

- **A grammar and a working deterministic expander** (`(fn NAME (PARAMS) STMT...)`
  → Python), covering function defs, assignment, in-place list element
  assignment, `if`/`else`, `for`/`while`, arithmetic/comparison/boolean
  operators, list literals and indexing, and generic builtin calls.
- **Prefix (S-expression) notation on purpose.** No operator-precedence table
  needed — that removes a whole class of ambiguity a real expander would
  otherwise have to resolve. No significant whitespace or indentation, since
  Python's colon-plus-indent costs real tokens. Plain ASCII throughout,
  specifically *because* of #12's finding: switching to rare symbols for
  visual compactness is what made MatrixLang's own glyph face worse, not
  better, in tokens.
- **20 original small algorithmic tasks** — generic (is_prime, fibonacci,
  gcd, bubble_sort, binary_search, and 15 others), hand-authored rather than
  taken from HumanEval/MBPP verbatim, since Stage 0 only needs representative
  *density*, not a licensed accuracy benchmark.
- **Every one of the 20 was verified, not assumed.** Each DSL example was
  expanded by the real expander and the result was executed against the same
  test cases as its hand-written Python reference. **20/20 passed on every
  test case** — the grammar genuinely expands to correct code, so the density
  numbers below are measuring something that actually works, not a
  representation that only looks plausible on the page.

## Method

Same approach as #12: a scratch venv outside this repo (`pip install
tiktoken`), both `cl100k_base` and `o200k_base`, no API spend — this measures
tokenization only, never calls a model.

```python
# The grammar, illustrated on one task:
dsl_src = "(fn fibonacci (n) (= a 0) (= b 1) " \
          "(for i (rng 0 n) (= c (+ a b)) (= a b) (= b c)) (ret a))"
python_src = expand(dsl_src)
# def fibonacci(n):
#     a = 0
#     b = 1
#     for i in range(0, n):
#         c = a + b
#         a = b
#         b = c
#     return a
```

## Result

| | `cl100k_base` | `o200k_base` |
| --- | --- | --- |
| Mean per-task density (Python tok ÷ DSL tok) | 0.929× | 0.929× |
| Median | 0.944× | 0.944× |
| Best case for the DSL | 1.130× (`reverse_string`) | 1.130× |
| Worst case for the DSL | 0.519× (`is_palindrome`) | 0.519× |
| **Aggregate (sum ÷ sum)** | **0.911×** | **0.911×** |
| Characters (aggregate) | −11% (2511 → 2239) | — |

Both tokenizer families agree almost exactly, which is itself informative —
this isn't a quirk of one BPE vocabulary.

**Characters went the direction the DSL's design intended — 11% fewer.**
Tokens did not follow. The same disconnect #12 found between visual/character
density and token density shows up again, from an unrelated design.

## Why it lost — this is the useful part

The per-task numbers aren't uniform, and the pattern is diagnostic:

- **Best cases were straight-line arithmetic and simple single loops**
  (`reverse_string` 1.13×, `sum_list` 1.12×, `fibonacci` 1.12×, `gcd`,
  `factorial` — all slightly *ahead* of Python). Where the DSL wins, it wins by skipping
  Python's `def foo():` / colon / indentation overhead without paying much
  in parens, because there's little branching to wrap.
- **Worst cases were `is_palindrome` (0.52×) and `count_vowels` (0.59×)** —
  both lost badly, and both lost for the *same* reason: the grammar has no
  string slicing and no membership test, so `s[::-1]` became an explicit
  reversal loop, and `ch in "aeiouAEIOU"` became a four-deep nested `(or (or
  (or (or ...))))` chain. Every missing built-in the DSL has to work around
  costs tokens, and it costs them precisely where Python's stdlib is cheapest.
- **Structurally, prefix notation has a fixed per-operation tax infix doesn't.**
  Python's `a + b` is two tokens (roughly); the DSL's `(+ a b)` is four —
  an open paren, the operator, and (in aggregate) a close paren the whole
  expression tree pays for at every level. `(then ...)`/`(else ...)` wrapper
  forms add two more tokens per conditional branch that Python's bare colon
  does not. None of this is visible by eye — parens read as "shorter" than
  `if`/`:`/indentation — but a BPE tokenizer with `if` and `:` as
  well-merged, extremely common subwords disagrees.

## What this means for #13

**Per #13's own instruction, this stops the spike at Stage 0.** No Stage 1
baseline run, no Stage 2 DSL arm, no API calls, no cost — exactly the point
of gating a live-model experiment behind a free offline measurement first.

This kills *this* DSL design, not necessarily the broader idea in the
abstract — a different design (kept-infix operators, a richer builtin set
covering slicing/membership so common tasks don't need workarounds, or a
vocabulary chosen for known single-token status in a specific tokenizer)
might clear 2×. But the burden is now on any such redesign to clear the same
free, cheap bar before anyone spends API budget on it — which is what Stage 0
existed to enforce, and which it just did.

## Caveats

- One grammar, one designer, one pass. This is a spike-sized effort (~2–3
  hours, matching #12's), not an exhaustive search of the DSL design space.
- `anthropic.count_tokens` was not run, for the same reason as #12: no API
  key was used, staying inside a no-spend scope. Both `tiktoken` families
  measured agree closely with each other, which is some evidence the result
  isn't an artifact of one vocabulary, but Claude's tokenizer is not directly
  measured here.
- 20 tasks, hand-authored. Larger or more varied corpora could shift the
  aggregate, but the internal pattern — the DSL wins on simple straight-line
  code and loses hardest exactly where it has to work around a missing
  built-in — is a structural property of prefix notation plus a small
  grammar, not a sampling artifact likely to reverse with more data.
