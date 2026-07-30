# Stage 4 Inputs — carried forward from the Stage 2 and Stage 3 final reviews

Written 2026-07-30, at the merge of Stage 3 (PR #2, 206 tests green). This file exists so
a fresh session can plan Stage 4 without re-deriving anything. It records decisions already
made, spec edits already identified as necessary, and hazards already found. It is an input
to Stage 4's brainstorm and plan — not a plan itself.

Stage 4's goal (parent spec): bidirectional glyph rendering. `render_ascii(tree)` and
`render_glyph(tree)` over one AST, a lexer accepting either face, a view toggle, and the
input pipeline (R-01). The §4.3 acceptance criterion is property-tested round-tripping.

---

## 1. Spec edits required BEFORE writing the Stage 4 plan

Both final reviews concluded these are spec defects that Stage 4 would otherwise discover
mid-implementation. Make the edits first, then plan.

1. **§4.3 quantifies over trees, not source.** It says "for any valid program `t`", but
   `t` is compared against `parse(...)` output, so `t` is an AST. Change the word. (The
   §5-Stage-4 text already writes `render_ascii(tree)`, so this is an internal
   inconsistency, not a redesign.)

2. **Define trivia well-formedness in §6.1.** The §4.3 property test must generate trees,
   and nothing constrains generated trivia strings. Two shapes break the round trip:
   a trailing comment without a leading `#` (renders as code, re-lexes as tokens), and a
   comment string containing a newline (renders as two lines, re-parses as two comments).
   State the invariant: every trivia string starts with `#` and contains no newline.
   Enforce it in the Stage 4 tree generator at minimum; `Stmt.__post_init__` validation is
   optional.

3. **Decide whether whitespace is inside R-02's "loss-free" promise.** Blank lines and
   indentation are currently discarded by the parser (`parse("trace 1\n\n\ntrace 2\n") ==
   parse("trace 1\ntrace 2\n")` is True). §4.3 still passes because it is tree-level, but
   the user-facing toggle demo will visibly reformat files. The two honest options, from
   the Stage 2 review: add `blank_lines_before: int` to `Stmt` alongside the comment
   trivia (cheap now, expensive later — the same argument that justified D-06), or amend
   §6.1/R-02 to say "loss-free" covers semantics and comments while whitespace normalizes.
   Silence is the only unacceptable option.

4. **The renderer's parenthesization duties, stated explicitly.** There is no Grouping
   node (deliberate). Therefore `render_ascii` must parenthesize from precedence AND
   associativity — `Binary(1, +, Binary(2, +, 3))` must emit `1 + (2 + 3)`, not
   `1 + 2 + 3` — and must parenthesize a unary's operand: `Unary(-, Binary(2, *, 3))`
   naively renders `-2 * 3`, which changes the meaning. Both belong in the plan as named
   requirements with tests; the property test only catches them if the generator produces
   those shapes.

5. **Fix the "twelve rules" phrase** if the Stage 3 plan's language is reused: §5 has ten
   bullets that decompose to fourteen testable rows. Neither is twelve.

## 2. Hazards already identified in the code

- **Do NOT reuse `values.to_display` for source rendering.** It is a *runtime value*
  formatter: it drops string quotes and leaves `\n` unescaped, which breaks §4.3.
  `treeview.py` already renders literals correctly (`!r` for strings, lowercased bools) —
  follow its lead, or better, make the source renderer own literal formatting outright.
  (The Stage 3 plan's rationale for `values.py` wrongly invited this reuse; the Stage 3
  final review flagged it.)

- **Property testing under "stdlib only".** Hypothesis is not stdlib. The global
  constraint binds `src/` only, so a dev dependency is arguably allowed — but that is a
  decision for the Stage 4 plan to make explicitly, not discover. The alternative is a
  hand-rolled seeded tree generator honouring the §6.1 trivia invariant.

- **Glyph assets.** Rezmason's project (github.com/Rezmason/matrix) holds the film glyphs
  as WebGL vector/texture data, not a distributable font. Rendering real film glyphs in a
  terminal/editor would require building a font — a sub-project. The working fallback,
  already implied by the spec's own `ｱ x = 5` example: Unicode half-width katakana render
  today in any terminal with zero font work. D-03's fixed bijective table (32 slots:
  8 keywords, 11 operators, 2 parens, 10 digits, `#`) makes the glyph set swappable later —
  ship on Unicode katakana, upgrade the table if a font ever exists. §4.3 doesn't care
  which set is loaded.
  IMPORTANT constraint already enforced by tests: the Stage 1 lexer rejects katakana
  (`test_katakana_is_not_an_identifier`) precisely so glyphs are unclaimed. Stage 4's
  lexer extension claims them as keyword/operator/digit tokens. The disjoint-alphabet
  property (spec §6.3) means one lexer handles both faces with no mode flag, and
  mixed-face source is legal — worth demonstrating.

- **Pin the `None`-vs-`[]` else_body contract where it is observable.** In
  `treeview.py`, an `If` with `else_body=[]` emits an `else:` header; under a truthiness
  check it would vanish. `tests/test_treeview.py` never tests the empty-else case. One
  test there pins the AST contract behaviourally — the interpreter cannot (the two forms
  are indistinguishable in `_execute`, which is why a comment lives there instead).

## 3. Smaller carried items (fold in opportunistically, none blocking)

- `RecursionError` on ~900-deep expression chains and CPython's 4300-digit int→str limit
  both escape as raw tracebacks and kill a REPL session (`feed` catches only
  `MatrixLangError`). A small `except RecursionError` in `Interpreter.run` mapping to
  `RuntimeErrorML` turns the likeliest crash into a lesson.
- `_execute` (if/elif/else) and `_evaluate` (if/return chain) have different dispatch
  shapes; `treeview.py` uses if/elif in both. Cosmetic; unify if touched.
- Binary type errors report the operator's position, not the offending operand's
  (`_require_int` receives the Binary node). Operand nodes carry positions; passing them
  is strictly better.
- The `Name`-lookup error omits the "use 'construct' first" hint the `Assign` error has.
- REPL: `_buffer.clear()` double-clears on the error path; buffered source is lexed twice
  per closing line; the lone-`flatline` and lex-error-mid-buffer edge cases are verified
  correct but untested.
- CLI: `_PENDING` holds only `render`. The retirement pattern (subparser + dispatch
  branch) is demonstrated twice in `cli.py`.

## 4. Process lessons that paid for themselves (keep using)

- **State the mutation a subtle test must catch, next to the test.** Three Stage 2 rounds
  were lost to tests that could not fail; every Stage 3 guard that mattered was proven by
  injecting the bug and watching the test fail (`//` for truncation, lexer-import
  spellings, BLUEPILL-as-closer). A test that has never failed proves nothing.
- **Implementers type briefs verbatim and report contradictions rather than patching
  around them.** This caught two genuine plan defects (Task 2's impossible test; the
  hello.rain comment edit colliding with the parser test — which was D-06 working).
- **Machine fault:** UF_HIDDEN on `.venv` recurs constantly; `chflags -R nohidden .venv`
  fixes it. Every dispatch prompt should carry the authorisation. (Also in the README.)
- Per-task briefs via `scripts/task-brief`, review packages via `scripts/review-package`,
  a ledger in `.superpowers/sdd/<plan>/progress.md`, cheap models for verbatim
  transcription, one fix wave after the final review, teeth-checks on every guard.

## 5. Current state, for orientation

- main @ Stage 3 merge: 206 tests, `matrixlang lex|parse|run|repl` all working, v0.3.0.
- Specs: `docs/superpowers/specs/SPEC-matrixlang.md` (build path) and
  `SPEC-matrixlang-language-surface.md` (the language; §6 already specifies the glyph
  face: D-03 coverage, §6.2 bijective mapping policy, §6.3 disjoint-alphabet lexing).
- Plans for Stages 1–3 in `docs/superpowers/plans/` show the task-shape that worked
  (8–9 tasks, exact code in every task, tests-first, ~2 fix rounds per stage).
- Stage 5 (the rain runner) remains after Stage 4, and is deliberately last.
