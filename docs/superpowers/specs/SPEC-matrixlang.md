# SPEC — MatrixLang

**A Matrix-styled esoteric programming language, built as a teaching series.**

Status: Draft v1
Last updated: 2026-07-29

---

## 1. Premise

The code shown in *The Matrix* is not a programming language. It has no grammar, no
semantics, and no execution model — the glyphs were assembled from mirrored half-width
katakana scanned out of a Japanese cookbook, chosen because they looked good on screen.
Nothing in the film runs.

This project therefore is **not** "recreate the Matrix language." There is nothing to
recreate. It is:

> **Invent the language the film pretended to have.**

Deliverable: a real, executable, Turing-complete language whose source can be written and
read in Matrix-style glyphs, with a working interpreter, a REPL, and a test suite.

### 1.1 In-universe framing (design-relevant)

Within the films, the falling green code is not something characters *write*. It appears on
operator monitors as a live readout of simulation state — Cypher describes no longer seeing
the code at all, only the people it represents. He is reading a rendering fluently, not
authoring source.

This is not trivia; it directly motivates R-02 below. The glyph face is an **operator
view**. The ASCII face is an **authoring view**. Ergonomics and in-universe accuracy
converge on the same architecture.

## 2. Rationale — series, not product

A new language cannot win on syntax. Languages win on ecosystem: Python is valued for its
libraries and package manager, not its grammar. This language starts with zero libraries
and will never compete on utility.

Framed as a teaching series, every weakness inverts:

| Weakness as a product | Strength as a series |
| --- | --- |
| Hard to build | That is the subject matter |
| Nothing runs in the film | That is the hook |
| No users | None required — the audience is learning, not adopting |
| Incomplete | Each stage is a complete lesson |

**Governing rule:** each stage ships as a self-contained explanation. Completion of the
language is not a prerequisite for value.

### 2.1 Framing sources

- Cinematic computers historically **mirror** real technology trends rather than invent
  novel interfaces (Larson, 2008). This project inverts that: take the reflection, build
  the real thing.
- *The Matrix* marks the point where code became an everyday cultural metaphor
  (Newman, 2024).
- The film's "humans as power source" premise is its most-criticized element; reporting
  indicates an earlier script treated humans as **processing power** instead. Machine
  resource constraints are therefore the weakest seam in canon — the natural place for
  invented lore to sit without contradiction, and a place where real infrastructure facts
  (datacenter cooling, water consumption, thermal limits) can be introduced honestly.

**Lore discipline:** lore *answers* design questions; it never *generates* them. Write the
justification after the engineering decision exists. Reversing this turns storytelling into
an uncapped scope generator.

## 3. Prior art

**Digital rain — solved, borrowable.**
`github.com/Rezmason/matrix` reverse-engineered the actual film glyphs from an archived
promotional asset — not Unicode katakana, the real mirrored vectors, plus characters from
Susan Kare's Chicago typeface, and the expanded 135-glyph set from *Resurrections*. Dozens
of other implementations exist (TMatrix, green_rain, RGB-digital-rain); a terminal version
is achievable in under 20 lines of ANSI escape sequences. **Do not rebuild this.**

**A language using these glyphs as syntax — not found.**

### 3.1 Novelty check

Search-term warning: "matrix" is the wrong query — on esolang wikis it returns
matrix-*mathematics* languages. The film aesthetic is called **digital rain**, **green
rain**, or **falling code**. Correct entry points: `esolangs.org/wiki/Category:CJK`,
`Category:Themed`, GitHub topics `esolang`, `matrix-digital-rain`, `matrix-rain`.

| Component | Novel? | Prior art |
| --- | --- | --- |
| CJK/katakana as syntax | **No** | 124 languages in Category:CJK — Kana, KanjiCode, ModanShogi, Sakana, Iwashi, Atamagaokashii, 日本語, かわいい |
| Pop-culture-themed esolang | **No — established genre** | ArnoldC, Chef, LOLCODE, Rockstar, Shakespeare |
| Matrix digital rain | **No — solved repeatedly** | Rezmason, TMatrix, green_rain, + 3 GitHub topics |
| **All three combined** | **Unclaimed** | none found |

Accurate claim: the *combination* is unclaimed, and no existing implementation is built as
a teaching artifact. Avoid claiming component novelty — it is false and trivially
falsifiable.

**Academic literature:** no peer-reviewed work exists on this. Note that this is weak
evidence — esolangs are essentially never published, so an academic corpus is the wrong
place to check.

## 4. Architecture

**Decision: tree-walking interpreter in Python. ASCII authoring form first. Glyph form as a
second lossless rendering of the same AST.**

### 4.1 Rejected alternatives

- **Bytecode compiler + stack VM.** Reachable and well documented (Nystrom Part II), but
  starting here means debugging an unfamiliar execution model, an unfamiliar parser, and an
  unfamiliar glyph pipeline simultaneously. Revisit after Stage 3.
- **Native compilation via LLVM.** The hard problems become calling conventions and memory
  models — orthogonal to the point of the project.
- **Pure transpiler to a host language.** Tempting: inherits an entire ecosystem for free.
  Rejected because it destroys error reporting — a runtime failure surfaces as a traceback
  into generated code the author never wrote. The fix is source maps, which are the hardest
  component of any transpiler. If this route is ever taken, source maps are day one.
- **Visual programming language (VPL) approaches.** Not applicable. VPL research concerns
  *graphical* syntax where spatial arrangement carries meaning; that field had to construct
  two-dimensional computation models and prove them Turing-equivalent precisely because
  conventional models assume one-dimensional text. This language **is** one-dimensional
  text. `ｱ x = 5` is a character string in exactly the same sense `print x = 5` is. Glyphs
  are a font and rendering concern, not a syntax-model concern, and Turing completeness
  follows from semantics — variables, conditionals, loops, unbounded storage — not from
  character appearance. Brainfuck is Turing-complete using eight punctuation marks.

### 4.2 Constraints

- **R-01 — Input latency.** If a glyph cannot be entered in roughly the time it takes to
  type a word, no one will write in the language, including its author. Requires a
  transliteration layer or live-substitution editor. **This is the hardest ergonomics
  problem in the project and is routinely underestimated.**
- **R-02 — Bidirectional rendering, not one-way substitution.** Glyph form and ASCII form
  are two lossless renderings of a single AST. Authoring in either form is valid; a toggle
  switches views; round-tripping is loss-free. **Loss-free covers semantics and comments;
  whitespace is not preserved** — blank lines and indentation normalize to the canonical
  rendering (language-surface addendum §6.1), so the toggle is also a pretty-printer.
  Design precedent: hybrid visual/textual
  languages preserve pure-text editability so visual constructs remain proper language
  extensions rather than a separate dialect (Andersen). This supersedes any "keyword lookup
  table in the lexer" approach — substitution is one-way and degrades debuggability.
  Identifiers default to ASCII.
- **R-03 — Rain in the runner, not the editor.** Motion and legibility are adversaries. The
  film's code reads well because no one must parse it; this code must be parsed. Empirical
  support: developers prefer to *supplement* text with visual syntax rather than displace it
  (Andersen).

Together these preserve the visual identity while keeping the language debuggable.

### 4.3 Acceptance criterion for glyph support

For any well-formed AST `t` (the criterion quantifies over trees, not source text —
`t` is compared against `parse(...)` output):

```
parse(render_glyph(t)) == parse(render_ascii(t)) == t
```

AST equality includes comment trivia. Comments are preserved as trivia attached to
AST nodes (see the language-surface addendum §6.1); a round-trip that drops comments
fails this criterion even though the executable code survives.

Property-tested, not example-tested.

## 5. Build stages

Each stage is a self-contained unit of work and a self-contained lesson. Depth is achieved
across the series, never within a single stage.

### Stage 1 — Lexer

**Goal:** convert source text into a token stream.

**Task:** `lex("x = 2 + 3")` → `[NAME(x), EQUALS, NUMBER(2), PLUS, NUMBER(3)]`. Pure
standard library. Tests from the first commit.

**Done when:** tests pass for numbers, identifiers, operators, and whitespace, plus at
least one malformed input reporting line and column.

**Teaching points:** a computer does not "read" code; the first act of any language is
segmentation. What a token is. Live demonstration: text in, structured list out. Open
question for the next stage: tokens carry no meaning yet.

### Stage 2 — Parser

**Goal:** convert the token stream into an abstract syntax tree.

**Task:** expression parsing with correct precedence — `2 + 3 * 4` must evaluate to 14, not
20. Assignment statements.

**Done when:** the tree for `x = 2 + 3 * 4` places multiplication below addition.

**Teaching points:** precedence is not innate to the machine; it is encoded in tree shape.
Draw the tree before showing code. Parallel to natural-language grammar.

### Stage 3 — Interpreter

**Goal:** execute the tree.

**Task:** evaluate the AST. Environment as a dictionary. `print`, then conditionals, then
loops. Add a REPL.

**Done when:** a counting loop runs correctly. **At this point the language exists.**

**Teaching points:** an environment is a dictionary — demystify it. Turing completeness
follows from variables + conditionals + unbounded loops. Tree-walking interpreters are not
a toy category; major production languages shipped this way for years.

### Stage 4 — Bidirectional glyph rendering

**Goal:** the Matrix visual identity, without losing readability.

**Task:** `render_ascii(tree)` and `render_glyph(tree)` over one AST; a lexer accepting
either input form; a view toggle. Then the input pipeline (R-01) — **the renderers are
small; input is the real work of this stage.**

**Done when:** the §4.3 property test passes and a program can be authored in glyphs
without ergonomic pain.

**Teaching points:** same language, different face. Honest disclosure that rendering is the
small part. Why round-tripping matters. Origin of the glyphs. The input problem.

### Stage 5 — Runner presentation

**Goal:** digital rain on execution.

**Task:** ANSI escape sequences in the terminal runner; glyphs sourced from existing
open work with attribution. Rain plays on execute, never during editing (R-03).

**Done when:** it reads as the film's aesthetic and remains debuggable.

**Teaching points:** presentation layer, earned last. Attribution and the reverse-
engineering story. Series synthesis: from "text is meaningless" to "a language that runs."

## 6. Deferred

Explicitly out of scope for v1:

- Bytecode compiler and stack VM
- Functions, closures, collections, standard library
- Editor tooling beyond a minimal REPL
- Package management, module system
- **LLM authoring support.** Approach when reached: in-context learning — supply the
  specification plus roughly a dozen worked examples in the prompt. This works well for
  small languages. Fine-tuning requires authoring a corpus of thousands of examples, a
  larger undertaking than the language itself. Because semantics stay close to a
  conventional imperative model, a model already understands the *meaning* and needs only
  the mapping; genuinely novel semantics would mean fighting both no-ecosystem and
  no-training-data simultaneously.

## 7. Risks

| ID | Risk | Mitigation |
| --- | --- | --- |
| RSK-1 | Unbounded research. "How computers understand code" has no floor, and neither does film lore — several in-universe questions have no canonical answer at all, so research feels convergent while never converging. | Time-box research passes. One layer of depth per stage. Ship, then deepen. |
| RSK-2 | Perfectionism — nothing ships until the language is complete | Stage 1 is a lexer and is a complete lesson on its own |
| RSK-3 | Glyph work begun before an interpreter exists | Stages 4–5 are last by design. Do not reorder. |
| RSK-4 | Scope creep into visual editors / VPL territory | Ruled out in §4.1. This language is one-dimensional text. |
| RSK-5 | Overstated novelty claims | §3.1 governs public phrasing. The combination is unclaimed; the components are not. |
| RSK-6 | Lore-driven feature growth | §2 discipline: lore answers design questions, never generates them |
| RSK-7 | Transpiler shortcut adopted mid-project without source maps | §4.1. If adopted, source maps are day one, not an afterthought. |

## 8. First action

```
mkdir matrixlang && cd matrixlang
git init
# README with the §1 premise
# pytest
# tests/test_lexer.py  ← written first
# src/lexer.py         ← written to pass it
```

Make `lex("x = 2 + 3")` produce the expected token list. Commit.

The expected token list, from the language-surface addendum §7.2:

```python
lex("x = 2 + 3")
# [IDENT(x), ASSIGN, NUMBER(2), PLUS, NUMBER(3), NEWLINE, EOF]
```

That is Stage 1, and at that point the project exists.

## 9. References

**Implementation**
- Nystrom, *Crafting Interpreters* — free online. Part I covers Stages 1–3; Part II covers
  the deferred bytecode VM.

**Design precedent**
- Andersen et al., hybrid visual/textual syntax as language extension — basis for R-02 and
  supporting evidence for R-03

**Assets**
- `github.com/Rezmason/matrix` — reverse-engineered film glyphs, including the
  *Resurrections* set

**Framing**
- Larson (2008) — cinematic computers mirror rather than invent
- Newman (2024) — code as everyday cultural metaphor post-1999

**Novelty check**
- `esolangs.org/wiki/Category:CJK`
- GitHub topics: `esolang`, `matrix-digital-rain`, `matrix-rain`
- Genre comparables: ArnoldC, Chef, LOLCODE, Rockstar, Shakespeare
