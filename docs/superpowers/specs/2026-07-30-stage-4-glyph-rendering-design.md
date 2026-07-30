# Stage 4 Design — Bidirectional Glyph Rendering

Status: Approved (brainstorm 2026-07-30)
Inputs: `docs/superpowers/NOTES-stage-4-inputs.md`, parent spec §4.3/§5-Stage-4,
language-surface spec §6.

Stage 4 delivers the glyph face: `render_ascii(tree)` and `render_glyph(tree)` over the
existing AST, a lexer that accepts either face (or both mixed), a view toggle in the CLI,
and the R-01 input story. Acceptance is the §4.3 round-trip property test.

## Decisions made in this brainstorm

| # | Question | Decision |
| --- | --- | --- |
| S4-1 | Whitespace in R-02's "loss-free" promise | Amend the spec: loss-free covers semantics and comments; whitespace normalizes to canonical form. No `blank_lines_before` trivia. |
| S4-2 | Property testing under "stdlib only" | Hand-rolled seeded tree generator in `tests/`. No Hypothesis, no third-party dependencies anywhere. |
| S4-3 | R-01 scope | ASCII is the input method (the ASCII face *is* the transliteration layer), plus a glyph-echo REPL mode. No curses editor. |
| S4-4 | Carried Stage 3 items | Fold in the four cheap fixes (RecursionError, empty-else pin test, operand-position errors, Name-lookup hint). Skip the cosmetic ones. |
| S4-5 | Renderer architecture | One structure-aware emitter parameterized by a face table; ASCII face is the identity table. |
| S4-6 | Glyph set | Unicode half-width katakana (U+FF66–FF9F), via D-03's swappable bijective table. No font work. |

## 1. Preliminary spec edits (own commit, before the plan)

Apply the five NOTES §1 items to the two spec files before writing the implementation
plan:

1. **§4.3 quantifies over trees.** Change "for any valid program `t`" to quantify over
   ASTs — `t` is compared against `parse(...)` output, so it is a tree.
2. **§6.1 trivia invariant.** Every trivia string starts with `#` and contains no
   newline. Enforced by the Stage 4 tree generator; no `Stmt.__post_init__` validation
   for now.
3. **Whitespace normalizes (S4-1).** Amend §6.1/R-02: round-tripping is loss-free for
   semantics and comments; blank lines and indentation normalize to the canonical form
   defined in §3 below. The toggle is also a pretty-printer, and says so.
4. **Renderer parenthesization duties** stated as named requirements (the two rules in
   §3 below: associativity parens and unary-operand parens).
5. **"Twelve rules" phrase** — do not reuse the Stage 3 plan's wording; §5 decomposes to
   fourteen testable rows, not twelve.

## 2. Glyph table and lexer extension — `glyphs.py`

- `GLYPHS`: a 32-entry dict, ASCII lexeme → one half-width katakana char. Slots per
  language spec §3.1: 8 keywords, 11 operators, 2 parens, 10 digits, `#`. `ｱ` maps to
  `construct`, honoring the parent spec's only code fragment (`ｱ x = 5`).
- `REVERSE`: derived char → slot map, used by the lexer. Bijectivity (32 distinct
  values) is test-asserted.
- **Lexer extension:** a character found in `REVERSE` produces the corresponding
  keyword/operator/paren token (single-glyph lexeme) or contributes a digit. No mode
  flag — the alphabets are disjoint (§6.3), so one lexer handles ASCII, glyph, and
  mixed-face source.
- **Digit runs may mix faces.** A NUMBER accepts any interleaving of ASCII and glyph
  digits, each decoded through the table. Otherwise `1ｲ` would lex as two adjacent
  NUMBERs and produce a baffling parse error.
- **Comment trivia is stored canonically.** A comment opened with the glyph `#` marker
  is normalized to start with ASCII `#` in the trivia string; the renderer re-maps the
  marker on the way out. Without this, `parse(render_glyph(t))` would carry
  glyph-marked trivia and fail equality against `t`. Keywords and digits need no such
  care: the AST stores decoded values, not lexemes.
- The Stage 1 guard `test_katakana_is_not_an_identifier` inverts meaning: glyph chars
  are now claimed as tokens, still never identifiers. Update the test to pin the new
  contract (a glyph keyword lexes as its keyword; katakana outside the 32-slot table
  remains an unknown-character error).

## 3. The renderer — `render.py`

One emitter walks the AST producing canonical source through a face table.
`render_ascii(tree)` and `render_glyph(tree)` are wrappers passing the identity table
and `GLYPHS` respectively.

**Canonical form:** 2-space indent per block depth; one statement per line; single
spaces around binary operators and `=`; no blank lines; leading comments on their own
lines at the statement's indent; trailing comments after two spaces.

**The emitter owns literal formatting outright** — never `values.to_display`, which is a
runtime-value formatter that drops quotes and leaves `\n` raw. Strings are re-quoted
with `\"`, `\\`, `\n` re-escaped; numbers are emitted digit-by-digit through the face
table; booleans render via their keyword slots. Identifiers, string contents, and
comment text bypass the table by construction — the structure-aware emitter cannot
corrupt `x2` or `trace "trace"` the way naive string substitution would.

**Parenthesization — named requirements, each with a directed test and a teeth-check
(inject the naive renderer, watch the test fail):**

- **R-PAREN-1 (precedence):** parens when a child's precedence is lower than its
  context requires.
- **R-PAREN-2 (associativity):** parens when the right child of a left-associative
  binary has *equal* precedence — `Binary(1, +, Binary(2, +, 3))` → `1 + (2 + 3)`;
  same for `-` and `/`.
- **R-PAREN-3 (unary operand):** parens around any binary operand of a unary —
  `Unary(-, Binary(2, *, 3))` → `-(2 * 3)`.

The renderer is total over well-formed trees; an unhandled node type raises
`AssertionError`, matching `treeview.py`'s convention (programmer error, not a
`MatrixLangError`).

## 4. CLI and REPL surface

- **CLI:** the pending `render` subcommand retires (third demonstration of the
  retirement pattern in `cli.py`). `matrixlang render --face {ascii,glyph} FILE` parses
  the file and prints the canonical rendering to stdout. Toggling is rendering to the
  other face; `render --face ascii` doubles as a formatter. Lex/parse errors report
  exactly as the `parse` subcommand does.
- **REPL:** gains a face-toggle meta-command, matching the REPL's existing command
  style. In glyph mode, each successfully parsed statement is echoed in its glyph
  rendering before execution output. This is the R-01 demo: you type ASCII at full
  speed and the machine shows you the operator view. Glyph *input* already works via
  the shared lexer — worth a test, not new code.

## 5. The §4.3 property test

- `tests/treegen.py`: `gen_program(rng)` — a seeded generator using `random.Random`,
  bounded depth and statement count, covering every node type, both `else_body=None`
  and `else_body=[]`, trivia honoring the §6.1 invariant, identifiers avoiding
  keywords, strings exercising all three escapes, and expression shapes deliberately
  stressing R-PAREN-1..3 (equal-precedence right children, unary over binary).
- The test runs a few hundred seeds asserting
  `parse(render_ascii(t)) == t` and `parse(render_glyph(t)) == t`, printing the
  failing seed and rendered source on failure.
- **Mixed-face property:** a third assertion renders through a per-seed mixed table
  (each slot randomly ASCII or glyph) and asserts the same equality — §6.3's
  mixed-face claim becomes property-tested for free, since the emitter is already
  table-parameterized.

## 6. Carried fixes (Stage 3, NOTES §3)

1. `except RecursionError` in `Interpreter.run`, mapped to `RuntimeErrorML` — a deep
   expression chain becomes a language error instead of killing the REPL.
2. Empty-else pin test in `test_treeview`: `If` with `else_body=[]` emits an `else:`
   header; `else_body=None` does not. Load-bearing for Stage 4 — the renderer must
   make the same distinction.
3. Binary type errors report the offending operand's position, not the operator's.
4. The `Name`-lookup error gains the "use 'construct' first" hint the `Assign` error
   already has.

## 7. Testing summary

New: `test_glyphs` (bijectivity, all 32 slots covered), `test_render` (canonical form,
literal formatting, each R-PAREN rule with teeth-checks), `test_roundtrip` (the §5
property), `tests/treegen.py`. Extended: `test_lexer` (glyph tokens, mixed faces,
mixed-digit runs, glyph-comment normalization, updated katakana guard), `test_cli`
(render subcommand, error paths), `test_repl` (face toggle, glyph echo, glyph input),
`test_treeview` (empty-else pin), `test_interpreter`/`test_errors` (carried fixes).

Version bumps to v0.4.0. Stage 5 (the rain runner) remains after this and is
deliberately last.
