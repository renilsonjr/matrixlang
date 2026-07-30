# Stage 4 — Bidirectional Glyph Rendering Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `render_ascii(tree)` and `render_glyph(tree)` over the existing AST, a lexer that accepts either face (or both mixed), a `matrixlang render` view toggle, a glyph-echo REPL mode, and the §4.3 round-trip property test — plus four small carried Stage 3 fixes.

**Architecture:** One structure-aware emitter (`render.py`) walks the AST producing canonical source through a *face table* mapping the 32 glyph slots; the ASCII face is the empty table, so `render_ascii` and `render_glyph` are wrappers over the same walk. `glyphs.py` owns the bijective slot table (design S4-6: Unicode half-width katakana, swappable later); the lexer reads the same table backwards, so one lexer serves both faces with no mode flag (spec §6.3 — the alphabets are disjoint). The §4.3 property test uses a hand-rolled seeded tree generator (design S4-2), no Hypothesis.

**Tech Stack:** Python ≥3.11, standard library only. pytest as the sole dev dependency.

**Reference:** `docs/superpowers/specs/2026-07-30-stage-4-glyph-rendering-design.md` (the stage design, decisions S4-1…S4-6), `SPEC-matrixlang-language-surface.md` §6 (glyph face, §6.4 parenthesization duties, §6.1 trivia invariant), parent spec §4.3 (acceptance criterion).

## Global Constraints

- **Standard library only** in `src/matrixlang/`. pytest is a dev dependency and must never be imported by shipped code. No Hypothesis — the property test generator is hand-rolled (design S4-2).
- **Glyph assignments live ONLY in `src/matrixlang/glyphs.py`.** Shipped code goes through `GLYPHS` / `REVERSE`; no other src module may contain a katakana literal. (D-03 makes the glyph set swappable; a hardcoded glyph elsewhere breaks that.) Tests MAY pin specific glyphs — that is what makes the table's contract testable.
- **The renderer NEVER imports `values.py`.** `to_display` is a runtime-value formatter: it drops string quotes and leaves `\n` unescaped, which breaks §4.3. The renderer owns literal formatting outright. The architecture test enforces this (render's allowed imports are `{glyphs, nodes, tokens}`).
- **Trivia invariant (spec §6.1):** every trivia string starts with `#` and contains no newline. The tree generator must honour it; the lexer normalizes glyph-marked comments into it.
- **Whitespace is outside the loss-free promise (design S4-1):** rendering normalizes blank lines and indentation to canonical form. Do not add whitespace trivia to the AST.
- **NEVER use `isinstance` for MatrixLang value type checks. Use `type(v) is int` / `type(v) is bool` / `type(v) is str`.** `isinstance` on **AST node** types is correct and expected; the ban is on value type checks only.
- **Integer division truncates toward zero, not floor.** Never use `//` or `math.floor` in the interpreter.
- **Every error reports line and column**, both 1-indexed, via the shared `MatrixLangError` hierarchy.
- **Dependency direction** (architecture test `_ALLOWED` table): `glyphs → {}` (pure data), `render → {glyphs, nodes, tokens}`, `lexer → {errors, glyphs, tokens}`, `repl` gains `render`, `cli` gains `render`. Extend `tests/test_architecture.py::_ALLOWED` in the same task that adds or re-wires each module.
- **Tests are written before implementation, in every task.**
- **Commit at the end of every task.**

**Environment note for every task:** run tests with `.venv/bin/python -m pytest`. Never run `pip install`, never create a venv, never add a conftest.py. Known machine fault: if `import matrixlang` fails with ModuleNotFoundError, run `chflags -R nohidden .venv` and continue (note it in your report). Any other import failure: report BLOCKED.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `src/matrixlang/glyphs.py` | Create: the 32-slot bijective table `GLYPHS` and its inverse `REVERSE`. Pure data, imports nothing |
| `src/matrixlang/render.py` | Create: canonical source rendering. `render(program, face)`, `render_ascii`, `render_glyph`, `ASCII_FACE`, `GLYPH_FACE` |
| `src/matrixlang/lexer.py` | Modify: accept glyph keywords/operators/parens/digits/comment-marker via `REVERSE` |
| `src/matrixlang/interpreter.py` | Modify: RecursionError guard, operand-position errors, Name-lookup hint |
| `src/matrixlang/repl.py` | Modify: `:ascii` / `:glyph` face commands, glyph echo |
| `src/matrixlang/cli.py` | Modify: `render` subcommand graduates out of `_PENDING`; `_PENDING` retires entirely |
| `tests/treegen.py` | Create: seeded random tree generator for the property test |
| `tests/test_glyphs.py` | Create: bijectivity, slot coverage |
| `tests/test_render.py` | Create: canonical form, literal formatting, R-PAREN-1..3 |
| `tests/test_roundtrip.py` | Create: the §4.3 property over ascii/glyph/mixed faces |
| `tests/test_lexer.py` | Modify: glyph tokens, mixed faces, comment normalization, katakana guard inverts |
| `tests/test_interpreter.py` | Modify: carried-fix tests; two existing assertions move |
| `tests/test_treeview.py` | Modify: empty-else pin test |
| `tests/test_repl.py` | Modify: face commands, glyph echo, glyph input |
| `tests/test_cli.py` | Modify: render subcommand; the pending-subcommand test retires |
| `tests/test_architecture.py` | Modify: `_ALLOWED` gains `glyphs` and `render`; three entries change |

**Why `glyphs.py` is keyed by ASCII lexeme, not TokenType.** The table's keys are the 32 slot spellings (`"construct"`, `"=="`, `"7"`, `"#"`). The lexer already owns lexeme→TokenType tables (`KEYWORDS`, `_SINGLE`, `_DOUBLE`); keying glyphs the same way means the glyph branch translates a glyph to its ASCII spelling and reuses those tables, and `glyphs.py` imports nothing at all. The renderer maps the other direction with a one-line `face.get(slot, slot)`.

**Why the emitter takes a face table instead of having two renderers.** The two faces differ by exactly 32 string substitutions. A naive *textual* substitution is broken (`x2` contains a digit; `"trace"` contains a keyword) — the emitter substitutes at emission time, per slot, so identifiers, string contents, and comment text bypass the table *by construction*. That argument is the stage's teaching beat; the code should visibly embody it.

---

### Task 1: Carried Stage 3 fixes

Four small items from the Stage 2/3 final reviews (design §6). No new modules.

**Files:**
- Modify: `src/matrixlang/interpreter.py`
- Test: `tests/test_interpreter.py`, `tests/test_treeview.py`

**Interfaces:**
- Consumes: existing `Interpreter`, `run`, `RuntimeErrorML`, AST nodes.
- Produces: no signature changes. Behaviour changes only: `Interpreter.run` converts `RecursionError` to `RuntimeErrorML`; `_require_int` call sites pass the *operand* node; the undeclared-`Name` message gains the `construct` hint.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_interpreter.py` (it already imports `io`, `pytest`, `RuntimeErrorML`, `Interpreter`, `run`, `lex`, `parse`):

```python
def test_a_very_deep_expression_is_a_language_error_not_a_crash():
    # A ~900-deep chain kills the process with a raw RecursionError today,
    # which in the REPL ends the session (feed catches MatrixLangError only).
    # Built programmatically: lex/parse would hit their own recursion first.
    from matrixlang.nodes import NumberLiteral, Program, Trace, Unary
    from matrixlang.tokens import TokenType

    expr = NumberLiteral(1)
    for _ in range(50_000):
        expr = Unary(TokenType.MINUS, expr)
    program = Program([Trace(expr, line=3, column=7)])
    with pytest.raises(RuntimeErrorML) as excinfo:
        run(program, out=io.StringIO())
    assert "nested too deeply" in str(excinfo.value)
    assert excinfo.value.line == 3
    assert excinfo.value.column == 7


def test_type_errors_point_at_the_offending_operand():
    # 'trace 1 + true': the operator is at column 9, 'true' at column 11.
    # The operand is what the reader must fix, so that is the position.
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("trace 1 + true\n")
    assert excinfo.value.line == 1
    assert excinfo.value.column == 11


def test_unary_type_errors_point_at_the_operand():
    # 'trace -true': '-' at column 7, 'true' at column 8.
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("trace -true\n")
    assert excinfo.value.column == 8


def test_reading_an_undeclared_name_suggests_construct():
    # The Assign error already carries this hint; the Name error did not.
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("trace nope\n")
    assert "use 'construct' first" in str(excinfo.value)
```

Replace the existing `test_arithmetic_errors_report_the_operator_position` (which pins `column == 9`, the operator — the exact behaviour this task removes) with:

```python
def test_ordering_type_errors_point_at_the_offending_operand():
    # 'trace true < 1': 'true' is the left operand, at column 7.
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("trace true < 1\n")
    assert excinfo.value.line == 1
    assert excinfo.value.column == 7
```

Append to `tests/test_treeview.py` (match its existing import style):

```python
def test_an_empty_bluepill_block_still_prints_an_else_header():
    # else_body=[] (a bluepill with no statements) and else_body=None (no
    # bluepill at all) are DIFFERENT trees, and treeview's `is not None`
    # check is what keeps them distinguishable. Under a truthiness check
    # the empty else would vanish. Stage 4's renderer relies on the same
    # distinction, so this pins the AST contract behaviourally.
    from matrixlang.lexer import lex
    from matrixlang.parser import parse

    with_empty_else = format_tree(parse(lex("redpill true\nbluepill\nflatline\n")))
    assert "else:" in with_empty_else

    without_else = format_tree(parse(lex("redpill true\nflatline\n")))
    assert "else:" not in without_else
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_interpreter.py tests/test_treeview.py -v`
Expected: the four new interpreter tests FAIL (RecursionError propagates; columns are 9 and 7; no hint). `test_ordering_type_errors_point_at_the_offending_operand` FAILS (column is the operator's). The treeview test may already PASS (the code is correct; the test was missing) — that is fine, it is a pin, and Step 3 will not touch treeview.

- [ ] **Step 3: Implement the three interpreter changes**

In `src/matrixlang/interpreter.py`:

1. `run` gains the RecursionError guard:

```python
    def run(self, program: Program) -> None:
        for statement in program.statements:
            try:
                self._execute(statement)
            except RecursionError:
                raise RuntimeErrorML(
                    "expression is nested too deeply",
                    statement.line,
                    statement.column,
                ) from None
```

2. `_require_int` call sites pass the operand *node* (the operand values are unchanged). In `_evaluate` (Unary branch):

```python
        if isinstance(expr, Unary):
            operand = self._evaluate(expr.operand)
            self._require_int(operand, expr.operand, "operand of unary '-'")
            return -operand
```

In `_comparison` (ordering branch):

```python
        if node.op in _ORDERING_OPS:
            self._require_int(left, node.left, "left operand")
            self._require_int(right, node.right, "right operand")
```

In `_arithmetic`:

```python
        self._require_int(left, node.left, "left operand")
        self._require_int(right, node.right, "right operand")
```

(`_require_int` itself is unchanged — operand nodes carry their own positions.)

3. The `Name` branch of `_evaluate` gains the hint:

```python
        if isinstance(expr, Name):
            if expr.ident not in self.environment:
                raise RuntimeErrorML(
                    f"'{expr.ident}' is not declared — use 'construct' first",
                    expr.line,
                    expr.column,
                )
            return self.environment[expr.ident]
```

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: all PASS. If any other test pinned the old operator-column or the hint-less message, fix that *test* — the new behaviour is the spec'd one (design §6, items 1/3/4).

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/interpreter.py tests/test_interpreter.py tests/test_treeview.py
git commit -m "fix: carried Stage 3 items — recursion guard, operand positions, construct hint, empty-else pin"
```

---

### Task 2: The glyph table — `glyphs.py`

**Files:**
- Create: `src/matrixlang/glyphs.py`, `tests/test_glyphs.py`
- Modify: `tests/test_architecture.py`

**Interfaces:**
- Consumes: nothing (pure data).
- Produces:
  - `GLYPHS: dict[str, str]` — ASCII slot spelling → one glyph char. Keys are exactly the 32 slots of language spec §3.1: the 8 keywords, the 11 operator spellings, `(`, `)`, `0`–`9`, `#`.
  - `REVERSE: dict[str, str]` — glyph char → ASCII slot spelling.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_glyphs.py`:

```python
import string

from matrixlang.glyphs import GLYPHS, REVERSE
from matrixlang.tokens import KEYWORDS


def test_the_table_covers_exactly_the_32_slots():
    # Language spec §3.1: 8 keywords + 11 operators + 2 parens + 10 digits
    # + the '#' comment marker. Nothing more (identifiers and string
    # contents stay ASCII, per D-03), nothing less.
    expected = (
        set(KEYWORDS)
        | {"+", "-", "*", "/", "=", "==", "!=", "<", ">", "<=", ">="}
        | {"(", ")"}
        | set(string.digits)
        | {"#"}
    )
    assert set(GLYPHS) == expected
    assert len(expected) == 32


def test_the_mapping_is_bijective():
    # §6.2 requires a bijection: two slots sharing a glyph would make the
    # glyph face ambiguous to lex.
    assert len(set(GLYPHS.values())) == len(GLYPHS)


def test_reverse_is_the_exact_inverse():
    assert REVERSE == {glyph: slot for slot, glyph in GLYPHS.items()}


def test_every_glyph_is_one_halfwidth_katakana_char():
    # Single chars from the halfwidth block (U+FF66–FF9D): they render in
    # any terminal today with zero font work, and single-char glyphs keep
    # column arithmetic trivial.
    for glyph in GLYPHS.values():
        assert len(glyph) == 1
        assert 0xFF66 <= ord(glyph) <= 0xFF9D


def test_construct_is_the_spec_s_own_fragment():
    # The parent spec's only code example is 'ｱ x = 5'. Honour it.
    assert GLYPHS["construct"] == "ｱ"


def test_glyphs_are_disjoint_from_every_ascii_alphabet():
    # §6.3's disjoint-alphabet property is what lets one lexer serve both
    # faces without a mode flag. If a glyph ever collided with ASCII, the
    # whole architecture would silently break.
    for glyph in GLYPHS.values():
        assert not glyph.isascii()
```

In `tests/test_architecture.py`, add to `_ALLOWED`:

```python
    "glyphs": set(),
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_glyphs.py tests/test_architecture.py -v`
Expected: test_glyphs FAILS with `ModuleNotFoundError: matrixlang.glyphs`; `test_every_module_has_an_entry_in_the_allow_table` PASSES only after the module exists — order is fine either way.

- [ ] **Step 3: Write the table**

Create `src/matrixlang/glyphs.py`:

```python
"""The 32-slot glyph table — D-03's fixed bijective mapping.

Pure data; imports nothing. Keys are the ASCII slot spellings from the
language spec §3.1; values are single half-width katakana (U+FF66–FF9D),
which render in any terminal with zero font work. The set is swappable:
if a real film-glyph font ever exists, only this table changes (§6.2).

Assignments are loosely mnemonic where a sound offered itself (ﾄ "to" for
trace, ﾚ "re" for redpill, ﾃ "te" for dejavu) and arbitrary elsewhere;
the tests pin bijectivity and coverage, not the choices.
"""

GLYPHS: dict[str, str] = {
    # keywords
    "construct": "ｱ",  # the spec's own fragment: ｱ x = 5
    "trace": "ﾄ",
    "redpill": "ﾚ",
    "bluepill": "ﾌ",
    "dejavu": "ﾃ",
    "flatline": "ﾗ",
    "true": "ｼ",
    "false": "ｷ",
    # operators
    "+": "ﾀ",
    "-": "ﾋ",
    "*": "ｶ",
    "/": "ﾜ",
    "=": "ﾅ",
    "==": "ﾆ",
    "!=": "ﾇ",
    "<": "ｻ",
    ">": "ｿ",
    "<=": "ｾ",
    ">=": "ｽ",
    # punctuation
    "(": "ｸ",
    ")": "ｹ",
    # digits, per-digit (§6.2: 10 renders as two glyphs)
    "0": "ｦ",
    "1": "ｧ",
    "2": "ｨ",
    "3": "ｩ",
    "4": "ｪ",
    "5": "ｫ",
    "6": "ｬ",
    "7": "ｭ",
    "8": "ｮ",
    "9": "ｯ",
    # comment marker
    "#": "ﾒ",
}

REVERSE: dict[str, str] = {glyph: slot for slot, glyph in GLYPHS.items()}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_glyphs.py tests/test_architecture.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/glyphs.py tests/test_glyphs.py tests/test_architecture.py
git commit -m "feat: the 32-slot bijective glyph table"
```

---

### Task 3: The lexer accepts the glyph face

**Files:**
- Modify: `src/matrixlang/lexer.py`, `tests/test_lexer.py`, `tests/test_architecture.py`

**Interfaces:**
- Consumes: `GLYPHS`, `REVERSE` from `matrixlang.glyphs`; existing `KEYWORDS`, `_SINGLE`, `_DOUBLE` tables.
- Produces: `lex(source)` unchanged in signature. New behaviour: glyph chars produce the same TokenTypes as their ASCII spellings; NUMBER accepts mixed-face digit runs; COMMENT lexemes are normalized to start with ASCII `#`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_lexer.py` (it already imports `pytest`, `LexError`, `lex`, and `TokenType`; add `from matrixlang.glyphs import GLYPHS` at the top with the other imports):

```python
def test_glyph_keywords_lex_as_keywords():
    # ｱ x ﾅ ｫ  ==  construct x = 5. One lexer, no mode flag (§6.3).
    tokens = lex("ｱ x ﾅ ｫ\n")
    assert [t.type for t in tokens] == [
        TokenType.CONSTRUCT,
        TokenType.IDENT,
        TokenType.ASSIGN,
        TokenType.NUMBER,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]
    assert tokens[3].value == 5


def test_the_spec_s_own_fragment_means_what_the_spec_says():
    # Parent spec §1's only code example, mixed-face: glyph keyword, ASCII
    # everything else. Mixed-face source is legal — D-03's free win.
    assert [t.type for t in lex("ｱ x = 5\n")] == [
        t.type for t in lex("construct x = 5\n")
    ]


def test_glyph_operators_lex_as_operators():
    # ｧ ﾆ ｧ  ==  1 == 1. A glyph operator is ONE char even when its ASCII
    # spelling is two.
    tokens = lex("ｧ ﾆ ｧ\n")
    assert [t.type for t in tokens[:3]] == [
        TokenType.NUMBER,
        TokenType.EQ,
        TokenType.NUMBER,
    ]


def test_glyph_booleans_carry_their_values():
    # The parser reads token.value for BoolLiteral; a glyph ｼ that lexes
    # as TRUE with value=None would build BoolLiteral(None).
    tokens = lex("ｼ ｷ\n")
    assert tokens[0].type is TokenType.TRUE
    assert tokens[0].value is True
    assert tokens[1].type is TokenType.FALSE
    assert tokens[1].value is False


def test_glyph_digit_runs_decode_positionally():
    # §6.2: digits map per-digit. ｧｦ is 10, not two tokens.
    tokens = lex("ﾄ ｧｦ\n")
    assert tokens[1].type is TokenType.NUMBER
    assert tokens[1].value == 10


def test_a_number_may_mix_faces_within_one_run():
    # 1ｦｦ is 100. Without this, adjacent NUMBER NUMBER tokens would parse
    # into a baffling error two stages away from the actual cause.
    tokens = lex("ﾄ 1ｦｦ\n")
    assert tokens[1].type is TokenType.NUMBER
    assert tokens[1].value == 100


def test_glyph_comments_normalize_to_canonical_trivia():
    # §6.1 invariant: trivia starts with ASCII '#'. A glyph-marked comment
    # must store '#…' or parse(render_glyph(t)) carries different trivia
    # than t and the §4.3 equality fails.
    tokens = lex("ﾄ x ﾒ note\n")
    comment = tokens[2]
    assert comment.type is TokenType.COMMENT
    assert comment.lexeme == "# note"


def test_katakana_outside_the_table_is_still_an_error():
    # Replaces test_katakana_is_not_an_identifier: the 32 mapped glyphs
    # are now claimed as tokens, but unmapped katakana (ﾝ, U+FF9D) stays
    # an unknown-character error — glyphs never become identifiers.
    with pytest.raises(LexError) as excinfo:
        lex("construct ﾝ = 1\n")
    assert excinfo.value.column == 11


def test_every_slot_lexes_to_the_same_type_as_its_ascii_spelling():
    # The whole-table property, so a future glyph-set swap stays honest.
    # '#' is excluded: a lone '#' opens a comment, checked above.
    for slot, glyph in GLYPHS.items():
        if slot == "#":
            continue
        assert lex(glyph + "\n")[0].type is lex(slot + "\n")[0].type, slot
```

Delete `test_katakana_is_not_an_identifier` (its premise inverts this stage; the unknown-katakana case moves to `test_katakana_outside_the_table_is_still_an_error`).

In `tests/test_architecture.py`, change the lexer's `_ALLOWED` entry:

```python
    "lexer": {"errors", "glyphs", "tokens"},
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_lexer.py -v`
Expected: every new test FAILS with `LexError: unexpected character` on the glyph char. The deleted test is gone.

- [ ] **Step 3: Extend the lexer**

In `src/matrixlang/lexer.py`:

1. Import the table (after the existing imports):

```python
from matrixlang.glyphs import GLYPHS, REVERSE
```

2. Update the module-level sets (replace the existing `_DIGITS` line and the comment above it; keep `_ID_START` / `_ID_CONTINUE` as they are):

```python
# Explicit ASCII sets. str.isdigit() and str.isalpha() accept Unicode, which
# would let glyphs lex as identifiers. Glyphs enter through REVERSE only.
_DIGITS = frozenset(string.digits)
_GLYPH_DIGITS = frozenset(GLYPHS[digit] for digit in string.digits)
_ANY_DIGIT = _DIGITS | _GLYPH_DIGITS
_COMMENT_MARKERS = frozenset({"#", GLYPHS["#"]})

# Glyph char -> TokenType for the single-glyph tokens (keywords, operators,
# parens). Digits and the comment marker are handled by their own branches.
_GLYPH_TOKENS: dict[str, TokenType] = {}
for _slot, _glyph in GLYPHS.items():
    if _slot in KEYWORDS:
        _GLYPH_TOKENS[_glyph] = KEYWORDS[_slot]
    elif _slot in _DOUBLE:
        _GLYPH_TOKENS[_glyph] = _DOUBLE[_slot]
    elif _slot in _SINGLE:
        _GLYPH_TOKENS[_glyph] = _SINGLE[_slot]
```

(`_GLYPH_TOKENS` must be defined *after* `_SINGLE` and `_DOUBLE`.)

3. In `lex`, change the comment branch's guard and normalize the lexeme:

```python
        if char in _COMMENT_MARKERS:
            start = index
            start_column = column
            while index < length and source[index] != "\n":
                index += 1
                column += 1
            # Canonical trivia (§6.1): a glyph marker is stored as '#', so
            # the same comment re-lexed from either face compares equal.
            lexeme = "#" + source[start + 1 : index]
            tokens.append(Token(TokenType.COMMENT, lexeme, line, start_column))
            continue
```

4. Change the number branch to scan mixed-face digit runs:

```python
        if char in _ANY_DIGIT:
            start = index
            start_column = column
            while index < length and source[index] in _ANY_DIGIT:
                index += 1
                column += 1
            lexeme = source[start:index]
            value = int("".join(REVERSE.get(c, c) for c in lexeme))
            tokens.append(
                Token(TokenType.NUMBER, lexeme, line, start_column, value)
            )
            continue
```

5. Add the glyph branch, directly after the identifier branch and before the two-char operator lookup:

```python
        if char in _GLYPH_TOKENS:
            token_type = _GLYPH_TOKENS[char]
            value = None
            if token_type is TokenType.TRUE:
                value = True
            elif token_type is TokenType.FALSE:
                value = False
            tokens.append(Token(token_type, char, line, column, value))
            index += 1
            column += 1
            continue
```

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: all PASS — including every pre-existing lexer test: ASCII behaviour is untouched (`#` comments produce identical lexemes through the new normalization line, since `"#" + rest` is the old `source[start:index]` when the marker is ASCII).

- [ ] **Step 5: Teeth-check the comment normalization**

Temporarily change the normalization line back to `lexeme = source[start:index]`, run `.venv/bin/python -m pytest tests/test_lexer.py::test_glyph_comments_normalize_to_canonical_trivia`, confirm it FAILS, then restore. A guard that has never failed proves nothing.

- [ ] **Step 6: Commit**

```bash
git add src/matrixlang/lexer.py tests/test_lexer.py tests/test_architecture.py
git commit -m "feat: the lexer accepts the glyph face — same tokens, no mode flag"
```

---

### Task 4: The renderer — `render.py`

The heart of the stage. One emitter, face tables, canonical form, and the three parenthesization requirements from spec §6.4.

**Files:**
- Create: `src/matrixlang/render.py`, `tests/test_render.py`
- Modify: `tests/test_architecture.py`

**Interfaces:**
- Consumes: AST nodes from `matrixlang.nodes`, `TokenType` from `matrixlang.tokens`, `GLYPHS` from `matrixlang.glyphs`.
- Produces:
  - `Face = dict[str, str]` (type alias), `ASCII_FACE: Face` (empty dict), `GLYPH_FACE: Face` (is `GLYPHS`)
  - `render(program: Program, face: Face) -> str`
  - `render_ascii(program: Program) -> str`
  - `render_glyph(program: Program) -> str`
  - Output always ends with `\n` (or is `""` for an empty program with no trailing comments).

- [ ] **Step 1: Write the failing tests**

Create `tests/test_render.py`:

```python
"""Canonical-form and face-table tests for the renderer.

The parenthesization tests are the load-bearing ones: there is no
Grouping node, so a renderer that ignores associativity (R-PAREN-2) or
unary operands (R-PAREN-3) emits source that parses to a DIFFERENT tree
— silently changed meaning, the worst failure this stage can have.
"""

from matrixlang.lexer import lex
from matrixlang.nodes import (
    Binary,
    BoolLiteral,
    If,
    Name,
    NumberLiteral,
    Program,
    StringLiteral,
    Trace,
    Unary,
)
from matrixlang.parser import parse
from matrixlang.render import render, render_ascii, render_glyph
from matrixlang.tokens import TokenType


def prog(*statements) -> Program:
    return Program(list(statements))


# --- literals -------------------------------------------------------------


def test_numbers_render_in_decimal():
    assert render_ascii(prog(Trace(NumberLiteral(42)))) == "trace 42\n"


def test_strings_render_quoted_with_escapes_reapplied():
    # NEVER values.to_display: that drops the quotes and leaves \n raw,
    # which renders a newline INSIDE a string literal — a lex error on
    # re-parse, §4.3 dead on arrival.
    value = 'say "no"\\' + "\n" + "end"
    expected = 'trace "say \\"no\\"\\\\\\nend"\n'
    assert render_ascii(prog(Trace(StringLiteral(value)))) == expected


def test_booleans_render_in_the_language_s_spelling():
    assert render_ascii(prog(Trace(BoolLiteral(True)))) == "trace true\n"
    assert render_ascii(prog(Trace(BoolLiteral(False)))) == "trace false\n"


# --- parenthesization (spec §6.4) ----------------------------------------


def test_r_paren_1_lower_precedence_children_get_parens():
    tree = prog(
        Trace(Binary(Binary(NumberLiteral(1), TokenType.PLUS, NumberLiteral(2)),
                     TokenType.STAR, NumberLiteral(3)))
    )
    assert render_ascii(tree) == "trace (1 + 2) * 3\n"


def test_r_paren_1_flat_left_chains_need_no_parens():
    tree = prog(
        Trace(Binary(Binary(NumberLiteral(1), TokenType.PLUS, NumberLiteral(2)),
                     TokenType.PLUS, NumberLiteral(3)))
    )
    assert render_ascii(tree) == "trace 1 + 2 + 3\n"


def test_r_paren_2_equal_precedence_right_children_get_parens():
    # Binary(1, +, Binary(2, +, 3)) is NOT the tree '1 + 2 + 3' parses to.
    # Rendering it without parens changes the tree; for '-' and '/' it
    # changes the VALUE: 10 - (3 - 2) is 9, 10 - 3 - 2 is 5.
    plus = prog(Trace(Binary(NumberLiteral(1), TokenType.PLUS,
                             Binary(NumberLiteral(2), TokenType.PLUS,
                                    NumberLiteral(3)))))
    assert render_ascii(plus) == "trace 1 + (2 + 3)\n"

    minus = prog(Trace(Binary(NumberLiteral(10), TokenType.MINUS,
                              Binary(NumberLiteral(3), TokenType.MINUS,
                                     NumberLiteral(2)))))
    assert render_ascii(minus) == "trace 10 - (3 - 2)\n"

    slash = prog(Trace(Binary(NumberLiteral(8), TokenType.SLASH,
                              Binary(NumberLiteral(4), TokenType.SLASH,
                                     NumberLiteral(2)))))
    assert render_ascii(slash) == "trace 8 / (4 / 2)\n"


def test_r_paren_3_binary_operands_of_unary_get_parens():
    # Unary(-, Binary(2, *, 3)) naively renders '-2 * 3', which re-parses
    # as Binary(Unary(-,2), *, 3): same value here, different tree — and
    # for '+' a different VALUE: -(2 + 3) is -5, -2 + 3 is 1.
    tree = prog(Trace(Unary(TokenType.MINUS,
                            Binary(NumberLiteral(2), TokenType.STAR,
                                   NumberLiteral(3)))))
    assert render_ascii(tree) == "trace -(2 * 3)\n"


def test_unary_needs_no_parens_for_atoms_or_nested_unary():
    assert render_ascii(prog(Trace(Unary(TokenType.MINUS, NumberLiteral(5))))) == (
        "trace -5\n"
    )
    tree = prog(Trace(Unary(TokenType.MINUS, Unary(TokenType.MINUS, Name("x")))))
    assert render_ascii(tree) == "trace --x\n"


def test_comparison_inside_equality_needs_no_parens_on_the_left():
    # 'a < b == c' parses as Binary(EQ, Binary(LT, a, b), c) — the same
    # tree — so no parens. The other nesting direction does need them.
    same = prog(Trace(Binary(Binary(Name("a"), TokenType.LT, Name("b")),
                             TokenType.EQ, Name("c"))))
    assert render_ascii(same) == "trace a < b == c\n"

    other = prog(Trace(Binary(Binary(Name("a"), TokenType.EQ, Name("b")),
                              TokenType.LT, Name("c"))))
    assert render_ascii(other) == "trace (a == b) < c\n"


# --- statements, blocks, comments ----------------------------------------


def test_the_stage_3_demo_renders_canonically():
    # The spec §7.1 program: same statements, blank line dropped (design
    # S4-1 — whitespace normalizes), 2-space indent per depth.
    source = (
        'construct n = 0\n'
        'construct name = "Neo"\n'
        '\n'
        'dejavu n < 3\n'
        '  redpill n == 1\n'
        '    trace "wake up, " + name\n'
        '  bluepill\n'
        '    trace n\n'
        '  flatline\n'
        '  n = n + 1\n'
        'flatline\n'
    )
    expected = (
        'construct n = 0\n'
        'construct name = "Neo"\n'
        'dejavu n < 3\n'
        '  redpill n == 1\n'
        '    trace "wake up, " + name\n'
        '  bluepill\n'
        '    trace n\n'
        '  flatline\n'
        '  n = n + 1\n'
        'flatline\n'
    )
    assert render_ascii(parse(lex(source))) == expected


def test_comments_survive_in_place():
    source = "# lead\ntrace 1  # tail\n# after everything\n"
    assert render_ascii(parse(lex(source))) == source


def test_body_trailing_comments_render_inside_the_block():
    source = "dejavu true\n  trace 1\n  # last words\nflatline\n"
    assert render_ascii(parse(lex(source))) == source


def test_an_empty_else_renders_its_bluepill_and_none_does_not():
    # else_body=[] and else_body=None are different trees (the Task 1
    # treeview pin); the renderer must keep them distinguishable in
    # SOURCE too, or the §4.3 round trip conflates them.
    with_empty = prog(If(BoolLiteral(True), [], []))
    assert render_ascii(with_empty) == "redpill true\nbluepill\nflatline\n"

    without = prog(If(BoolLiteral(True), [], None))
    assert render_ascii(without) == "redpill true\nflatline\n"


def test_an_empty_program_renders_empty():
    assert render_ascii(prog()) == ""


# --- faces ----------------------------------------------------------------


def test_the_glyph_face_maps_structure_and_only_structure():
    # ﾄ=trace ﾀ=+ ｧ=1 ｨ=2. Identifiers stay ASCII (D-03: in a wall of
    # green, the Latin text is the thing you need to find).
    tree = prog(Trace(Binary(NumberLiteral(1), TokenType.PLUS, NumberLiteral(2))))
    assert render_glyph(tree) == "ﾄ ｧ ﾀ ｨ\n"


def test_glyph_digits_map_per_digit():
    assert render_glyph(prog(Trace(NumberLiteral(42)))) == "ﾄ ｪｨ\n"


def test_identifiers_strings_and_comment_text_bypass_the_table():
    # 'x2' contains a digit; the string contains a keyword spelling and a
    # digit. Naive textual substitution corrupts both; the structure-aware
    # emitter cannot touch them. THE design argument, as a test.
    tree = parse(lex('construct x2 = "trace 42"  # note 42\n'))
    assert render_glyph(tree) == 'ｱ x2 ﾅ "trace 42"  ﾒ note 42\n'


def test_a_partial_face_renders_mixed_source():
    # Any subset of the table is a legal face — §6.3's mixed-face claim.
    tree = prog(Trace(Binary(NumberLiteral(1), TokenType.PLUS, NumberLiteral(2))))
    assert render(tree, {"trace": "ﾄ"}) == "ﾄ 1 + 2\n"


def test_glyph_blocks_keep_ascii_layout():
    tree = parse(lex("dejavu false\n  trace 1\nflatline\n"))
    assert render_glyph(tree) == "ﾃ ｷ\n  ﾄ ｧ\nﾗ\n"
```

In `tests/test_architecture.py`, add to `_ALLOWED`:

```python
    "render": {"glyphs", "nodes", "tokens"},
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_render.py -v`
Expected: FAIL with `ModuleNotFoundError: matrixlang.render`.

- [ ] **Step 3: Write the renderer**

Create `src/matrixlang/render.py`:

```python
"""Canonical source rendering: syntax tree in, source text out.

One emitter serves both faces (design S4-5). The walk is identical; a
face table maps the 32 glyph slots at emission time, so identifiers,
string contents, and comment text bypass the table BY CONSTRUCTION —
the reason this is not textual substitution, which would corrupt the
digit in `x2` and the keyword inside "trace".

This module owns literal formatting outright. values.to_display is a
runtime-value formatter (no quotes, raw newlines) and must never be
used here — a string literal it printed would not re-lex.

Whitespace is canonical, not preserved (design S4-1): 2-space indent
per block depth, one statement per line, single spaces around binary
operators, no blank lines, trailing comments after two spaces.
"""

from matrixlang.glyphs import GLYPHS
from matrixlang.nodes import (
    Assign,
    Binary,
    BoolLiteral,
    Declare,
    Expr,
    If,
    Name,
    NumberLiteral,
    Program,
    Stmt,
    StringLiteral,
    Trace,
    Unary,
    While,
)
from matrixlang.tokens import TokenType

Face = dict[str, str]

ASCII_FACE: Face = {}
GLYPH_FACE: Face = GLYPHS

_OPS: dict[TokenType, str] = {
    TokenType.PLUS: "+",
    TokenType.MINUS: "-",
    TokenType.STAR: "*",
    TokenType.SLASH: "/",
    TokenType.EQ: "==",
    TokenType.NEQ: "!=",
    TokenType.LT: "<",
    TokenType.GT: ">",
    TokenType.LTE: "<=",
    TokenType.GTE: ">=",
}

# Precedence levels, loosest to tightest (language spec §4). Parens are
# reconstructed from these plus associativity — there is no Grouping
# node, so this table IS the §6.4 contract.
_LEVEL: dict[TokenType, int] = {
    TokenType.EQ: 1,
    TokenType.NEQ: 1,
    TokenType.LT: 2,
    TokenType.GT: 2,
    TokenType.LTE: 2,
    TokenType.GTE: 2,
    TokenType.PLUS: 3,
    TokenType.MINUS: 3,
    TokenType.STAR: 4,
    TokenType.SLASH: 4,
}
_UNARY_LEVEL = 5
_ATOM_LEVEL = 6

_STRING_ESCAPES: dict[str, str] = {"\\": "\\\\", '"': '\\"', "\n": "\\n"}


def render_ascii(program: Program) -> str:
    """The authoring view."""
    return render(program, ASCII_FACE)


def render_glyph(program: Program) -> str:
    """The operator view."""
    return render(program, GLYPH_FACE)


def render(program: Program, face: Face) -> str:
    """Render a program through a face table (any subset of the slots)."""
    lines: list[str] = []
    for statement in program.statements:
        _statement(statement, 0, face, lines)
    for comment in program.trailing_comments:
        lines.append(_comment(comment, face))
    return "".join(line + "\n" for line in lines)


def _map(face: Face, slot: str) -> str:
    return face.get(slot, slot)


def _comment(text: str, face: Face) -> str:
    # §6.2: the '#' marker maps; the comment text is unchanged. Trivia is
    # stored canonically (leading ASCII '#', lexer's guarantee).
    return _map(face, "#") + text[1:]


# --- statements ----------------------------------------------------------


def _statement(stmt: Stmt, depth: int, face: Face, lines: list[str]) -> None:
    pad = "  " * depth
    for comment in stmt.leading_comments:
        lines.append(pad + _comment(comment, face))
    if isinstance(stmt, Declare):
        head = (
            f"{_map(face, 'construct')} {stmt.name} {_map(face, '=')} "
            f"{_expression(stmt.value, 0, face)}"
        )
        lines.append(pad + head + _trail(stmt, face))
    elif isinstance(stmt, Assign):
        head = f"{stmt.name} {_map(face, '=')} {_expression(stmt.value, 0, face)}"
        lines.append(pad + head + _trail(stmt, face))
    elif isinstance(stmt, Trace):
        head = f"{_map(face, 'trace')} {_expression(stmt.value, 0, face)}"
        lines.append(pad + head + _trail(stmt, face))
    elif isinstance(stmt, If):
        lines.append(
            pad + f"{_map(face, 'redpill')} {_expression(stmt.condition, 0, face)}"
        )
        for child in stmt.then_body:
            _statement(child, depth + 1, face, lines)
        for comment in stmt.then_trailing:
            lines.append(pad + "  " + _comment(comment, face))
        # `is not None`, never truthiness: else_body=[] is a bluepill with
        # an empty body and must render its header, or the round trip
        # conflates it with no bluepill at all.
        if stmt.else_body is not None:
            lines.append(pad + _map(face, "bluepill"))
            for child in stmt.else_body:
                _statement(child, depth + 1, face, lines)
            for comment in stmt.else_trailing:
                lines.append(pad + "  " + _comment(comment, face))
        lines.append(pad + _map(face, "flatline") + _trail(stmt, face))
    elif isinstance(stmt, While):
        lines.append(
            pad + f"{_map(face, 'dejavu')} {_expression(stmt.condition, 0, face)}"
        )
        for child in stmt.body:
            _statement(child, depth + 1, face, lines)
        for comment in stmt.body_trailing:
            lines.append(pad + "  " + _comment(comment, face))
        lines.append(pad + _map(face, "flatline") + _trail(stmt, face))
    else:
        raise AssertionError(f"unhandled statement node: {type(stmt).__name__}")


def _trail(stmt: Stmt, face: Face) -> str:
    if stmt.trailing_comment is None:
        return ""
    return "  " + _comment(stmt.trailing_comment, face)


# --- expressions ----------------------------------------------------------


def _expression(expr: Expr, minimum: int, face: Face) -> str:
    """Render `expr`, parenthesized if it binds looser than `minimum`."""
    text, level = _emit(expr, face)
    if level < minimum:
        return _map(face, "(") + text + _map(face, ")")
    return text


def _emit(expr: Expr, face: Face) -> tuple[str, int]:
    if isinstance(expr, NumberLiteral):
        return _number(expr.value, face), _ATOM_LEVEL
    if isinstance(expr, StringLiteral):
        return _string(expr.value), _ATOM_LEVEL
    if isinstance(expr, BoolLiteral):
        return _map(face, "true" if expr.value else "false"), _ATOM_LEVEL
    if isinstance(expr, Name):
        return expr.ident, _ATOM_LEVEL
    if isinstance(expr, Unary):
        # R-PAREN-3: any binary operand is looser than _UNARY_LEVEL and
        # gets parens; atoms and nested unaries do not.
        operand = _expression(expr.operand, _UNARY_LEVEL, face)
        return _map(face, "-") + operand, _UNARY_LEVEL
    if isinstance(expr, Binary):
        level = _LEVEL[expr.op]
        # Left-associative grammar: the left child may sit at the same
        # level (R-PAREN-1); the right child must bind STRICTLY tighter
        # or the chain re-parses left-first (R-PAREN-2).
        left = _expression(expr.left, level, face)
        right = _expression(expr.right, level + 1, face)
        return f"{left} {_map(face, _OPS[expr.op])} {right}", level
    raise AssertionError(f"unhandled expression node: {type(expr).__name__}")


def _number(value: int, face: Face) -> str:
    # §6.2: digits map per-digit, positionally. NumberLiteral values are
    # non-negative — a minus sign is a Unary node, never part of a number.
    return "".join(_map(face, digit) for digit in str(value))


def _string(value: str) -> str:
    body = "".join(_STRING_ESCAPES.get(char, char) for char in value)
    return f'"{body}"'
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_render.py tests/test_architecture.py -v`
Expected: all PASS.

- [ ] **Step 5: Teeth-check R-PAREN-2 and R-PAREN-3**

Two deliberate bug injections, one at a time, each reverted before the next:

1. In `_emit`'s Binary branch, change `level + 1` to `level`. Run `.venv/bin/python -m pytest tests/test_render.py -v`. Expected: `test_r_paren_2_equal_precedence_right_children_get_parens` FAILS (and the round-trip suite would too, once it exists). Revert.
2. In `_emit`'s Unary branch, change `_UNARY_LEVEL` in the `_expression` call to `0`. Run the same command. Expected: `test_r_paren_3_binary_operands_of_unary_get_parens` FAILS. Revert.

If either injection does NOT fail its test, the test is decorative — fix the test before proceeding.

- [ ] **Step 6: Run the full suite, then commit**

Run: `.venv/bin/python -m pytest`
Expected: all PASS.

```bash
git add src/matrixlang/render.py tests/test_render.py tests/test_architecture.py
git commit -m "feat: canonical renderer — one emitter, two faces, §6.4 parens rules"
```

---

### Task 5: The tree generator and the §4.3 property test

**Files:**
- Create: `tests/treegen.py`, `tests/test_roundtrip.py`

**Interfaces:**
- Consumes: AST nodes; `TokenType`; `lex`, `parse`; `render`, `render_ascii`, `render_glyph`; `GLYPHS`.
- Produces: `treegen.gen_program(rng: random.Random) -> Program` — deterministic per seed, bounded size, honours the §6.1 trivia invariant, deliberately produces the R-PAREN shapes and all three else-body shapes.

- [ ] **Step 1: Write the generator**

Create `tests/treegen.py`:

```python
"""Seeded random tree generator for the §4.3 round-trip property test.

Hand-rolled on purpose (design S4-2): stdlib random.Random, bounded
sizes, no shrinking — a failing seed reproduces the tree exactly, and
trees stay small by construction.

Coverage is deliberate, not hoped-for: equal-precedence right children
and unary-over-binary shapes (the §6.4 parens rules), all three
else_body shapes (None / [] / populated), trivia honouring the §6.1
invariant, and string/comment content chosen to smoke out corruption
(a quote, a backslash, a newline escape, a keyword spelling, a glyph
char, digits). test_roundtrip has a test asserting this coverage
actually occurs — a generator that stops producing the hard shapes
would quietly gut the property.
"""

import random

from matrixlang.nodes import (
    Assign,
    Binary,
    BoolLiteral,
    Declare,
    Expr,
    If,
    Name,
    NumberLiteral,
    Program,
    Stmt,
    StringLiteral,
    Trace,
    Unary,
    While,
)
from matrixlang.tokens import TokenType

_IDENTS = ["x", "y", "neo", "trinity", "n1", "x2", "_tmp", "constructor"]
# 'flatline' inside a string and 'ｱ' in strings/comments prove that
# string contents and comment text bypass keyword recognition and the
# face table. '"' and '\\' and '\n' exercise every escape.
_STRING_CHARS = ["a", "b", "z", " ", "_", '"', "\\", "\n", "0", "7", "ｱ", "flatline"]
_COMMENT_CHARS = ["a", "b", " ", "9", "+", "ｱ", '"', "flatline"]
_NUMBERS = [0, 1, 7, 10, 42, 305]
_BINARY_OPS = [
    TokenType.EQ, TokenType.NEQ,
    TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE,
    TokenType.PLUS, TokenType.MINUS, TokenType.STAR, TokenType.SLASH,
]


def gen_program(rng: random.Random) -> Program:
    statements = [gen_statement(rng, 2) for _ in range(rng.randint(0, 5))]
    return Program(statements, trailing_comments=gen_comments(rng))


def gen_comment(rng: random.Random) -> str:
    # §6.1 invariant: starts with '#', contains no newline.
    body = "".join(rng.choice(_COMMENT_CHARS) for _ in range(rng.randint(0, 5)))
    return "#" + body


def gen_comments(rng: random.Random) -> list[str]:
    return [gen_comment(rng) for _ in range(rng.randint(0, 2))]


def gen_statement(rng: random.Random, depth: int) -> Stmt:
    kinds = ["declare", "assign", "trace"]
    if depth > 0:
        kinds += ["if", "while"]
    kind = rng.choice(kinds)
    stmt: Stmt
    if kind == "declare":
        stmt = Declare(rng.choice(_IDENTS), gen_expression(rng, 3))
    elif kind == "assign":
        stmt = Assign(rng.choice(_IDENTS), gen_expression(rng, 3))
    elif kind == "trace":
        stmt = Trace(gen_expression(rng, 3))
    elif kind == "if":
        else_body: list[Stmt] | None = rng.choice(
            [None, [], [gen_statement(rng, depth - 1)]]
        )
        stmt = If(
            gen_expression(rng, 2),
            [gen_statement(rng, depth - 1) for _ in range(rng.randint(0, 2))],
            else_body,
            then_trailing=gen_comments(rng),
            # else_trailing renders only when a bluepill exists; comments
            # there with else_body=None would be silently dropped and the
            # property would (rightly) fail on the generator's own bug.
            else_trailing=gen_comments(rng) if else_body is not None else [],
        )
    else:
        stmt = While(
            gen_expression(rng, 2),
            [gen_statement(rng, depth - 1) for _ in range(rng.randint(0, 2))],
            body_trailing=gen_comments(rng),
        )
    stmt.leading_comments = gen_comments(rng)
    if rng.random() < 0.4:
        stmt.trailing_comment = gen_comment(rng)
    return stmt


def gen_expression(rng: random.Random, depth: int) -> Expr:
    if depth == 0:
        return gen_atom(rng)
    roll = rng.random()
    if roll < 0.40:
        # Both children draw from the full depth-1 space, so equal-
        # precedence right children (R-PAREN-2) and nested chains occur
        # constantly rather than by luck.
        return Binary(
            gen_expression(rng, depth - 1),
            rng.choice(_BINARY_OPS),
            gen_expression(rng, depth - 1),
        )
    if roll < 0.55:
        # Unary over a full subexpression: the R-PAREN-3 shape.
        return Unary(TokenType.MINUS, gen_expression(rng, depth - 1))
    return gen_atom(rng)


def gen_atom(rng: random.Random) -> Expr:
    roll = rng.random()
    if roll < 0.40:
        return NumberLiteral(rng.choice(_NUMBERS))
    if roll < 0.60:
        return BoolLiteral(rng.choice([True, False]))
    if roll < 0.80:
        return Name(rng.choice(_IDENTS))
    return StringLiteral(
        "".join(rng.choice(_STRING_CHARS) for _ in range(rng.randint(0, 4)))
    )
```

- [ ] **Step 2: Write the property test**

Create `tests/test_roundtrip.py`:

```python
"""The §4.3 acceptance criterion, property-tested.

For any well-formed AST t:  parse(render_glyph(t)) == parse(render_ascii(t)) == t

Equality includes comment trivia and excludes positions (compare=False
on Node). The mixed face makes §6.3's mixed-face claim a tested
property instead of an asserted one — the emitter is table-driven, so
ANY subset of the table is a legal face.
"""

import random

import pytest

from matrixlang.glyphs import GLYPHS
from matrixlang.lexer import lex
from matrixlang.nodes import Binary, If, Unary
from matrixlang.parser import parse
from matrixlang.render import render, render_ascii, render_glyph
from treegen import gen_program

_LEVEL_GROUPS = {
    "EQ": 1, "NEQ": 1, "LT": 2, "GT": 2, "LTE": 2, "GTE": 2,
    "PLUS": 3, "MINUS": 3, "STAR": 4, "SLASH": 4,
}


def _mixed_face(rng: random.Random) -> dict[str, str]:
    return {slot: glyph for slot, glyph in GLYPHS.items() if rng.random() < 0.5}


@pytest.mark.parametrize("seed", range(300))
def test_round_trip(seed):
    rng = random.Random(seed)
    tree = gen_program(rng)

    ascii_source = render_ascii(tree)
    assert parse(lex(ascii_source)) == tree, f"seed {seed} ascii:\n{ascii_source}"

    glyph_source = render_glyph(tree)
    assert parse(lex(glyph_source)) == tree, f"seed {seed} glyph:\n{glyph_source}"

    mixed_source = render(tree, _mixed_face(rng))
    assert parse(lex(mixed_source)) == tree, f"seed {seed} mixed:\n{mixed_source}"


def test_the_generator_is_deterministic_per_seed():
    # The no-shrinking bargain (design S4-2) only holds if a seed
    # reproduces its tree exactly.
    assert gen_program(random.Random(7)) == gen_program(random.Random(7))


def test_the_generator_produces_the_shapes_the_parens_rules_need():
    # §6.4: "the property test only catches violations if the generator
    # produces those shapes, so the generator must produce them
    # deliberately." This is the check that it actually does — across
    # the same seeds the property runs on.
    equal_precedence_right = False
    unary_over_binary = False
    empty_else = False
    absent_else = False

    def walk_expr(expr):
        nonlocal equal_precedence_right, unary_over_binary
        if isinstance(expr, Binary):
            if (
                isinstance(expr.right, Binary)
                and _LEVEL_GROUPS[expr.right.op.name] == _LEVEL_GROUPS[expr.op.name]
            ):
                equal_precedence_right = True
            walk_expr(expr.left)
            walk_expr(expr.right)
        elif isinstance(expr, Unary):
            if isinstance(expr.operand, Binary):
                unary_over_binary = True
            walk_expr(expr.operand)

    def walk_stmt(stmt):
        nonlocal empty_else, absent_else
        if isinstance(stmt, If):
            if stmt.else_body == []:
                empty_else = True
            if stmt.else_body is None:
                absent_else = True
            for child in stmt.then_body + (stmt.else_body or []):
                walk_stmt(child)
            walk_expr(stmt.condition)
        else:
            for field in ("value", "condition"):
                if hasattr(stmt, field):
                    walk_expr(getattr(stmt, field))
            for child in getattr(stmt, "body", []):
                walk_stmt(child)

    for seed in range(300):
        for statement in gen_program(random.Random(seed)).statements:
            walk_stmt(statement)

    assert equal_precedence_right, "no R-PAREN-2 shape in 300 seeds"
    assert unary_over_binary, "no R-PAREN-3 shape in 300 seeds"
    assert empty_else, "no empty-else If in 300 seeds"
    assert absent_else, "no else-less If in 300 seeds"
```

- [ ] **Step 3: Run the property test**

Run: `.venv/bin/python -m pytest tests/test_roundtrip.py -v`
Expected: all 302 PASS in well under a minute. If a seed fails, the message prints the seed and the rendered source — reproduce with `gen_program(random.Random(<seed>))`, diagnose whether the bug is in the renderer, the lexer, or the generator (the generator violating a parser normalization — e.g. else_trailing on an else-less If — is a *generator* bug), fix, and re-run the full 300.

- [ ] **Step 4: Teeth-check the property itself**

Re-inject the Task 4 R-PAREN-2 bug (`level + 1` → `level` in `_emit`). Run `.venv/bin/python -m pytest tests/test_roundtrip.py::test_round_trip -x -q`. Expected: at least one seed FAILS — this proves the generator reaches the shape and the property catches the class of bug §4.3 exists for. Revert. If all 300 seeds pass with the bug in place, the generator's expression weights are broken; fix `gen_expression`, not the property.

- [ ] **Step 5: Run the full suite, then commit**

Run: `.venv/bin/python -m pytest`
Expected: all PASS (now ~250 + 302 tests).

```bash
git add tests/treegen.py tests/test_roundtrip.py
git commit -m "test: the §4.3 round-trip property over ascii, glyph, and mixed faces"
```

---

### Task 6: `matrixlang render` — the view toggle

**Files:**
- Modify: `src/matrixlang/cli.py`, `tests/test_cli.py`, `tests/test_architecture.py`

**Interfaces:**
- Consumes: `render_ascii`, `render_glyph` from `matrixlang.render`; existing `_read_source`, error-report pattern.
- Produces: `matrixlang render --face {ascii,glyph} PATH` → canonical rendering on stdout, exit 0; lex/parse errors on stderr, exit 1; unreadable file, exit 2. `_PENDING` retires entirely.

- [ ] **Step 1: Write the failing tests**

In `tests/test_cli.py`, **delete** `test_only_render_remains_unimplemented` (the pending map it tests retires this task — same pattern as Stage 3's retirement commit). Append:

```python
def test_render_glyph_prints_the_glyph_face(source_file, capsys):
    exit_code = main(["render", "--face", "glyph", source_file("trace 1 + 2\n")])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "ﾄ ｧ ﾀ ｨ\n"


def test_render_ascii_is_a_formatter(source_file, capsys):
    # Whitespace normalizes (design S4-1): the blank line goes, the
    # indent becomes canonical. render --face ascii doubles as fmt.
    exit_code = main(
        ["render", "--face", "ascii", source_file("\n\ntrace      1\n")]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "trace 1\n"


def test_render_round_trips_through_a_file(source_file, capsys, tmp_path):
    # The toggle demo end-to-end: ascii -> glyph -> ascii, byte-identical.
    source = 'construct n = 0\ndejavu n < 2\n  trace "go"\nflatline\n'
    exit_code = main(["render", "--face", "glyph", source_file(source)])
    glyph_text = capsys.readouterr().out
    assert exit_code == 0

    glyph_path = tmp_path / "glyph.rain"
    glyph_path.write_text(glyph_text, encoding="utf-8")
    exit_code = main(["render", "--face", "ascii", str(glyph_path)])
    assert exit_code == 0
    assert capsys.readouterr().out == source


def test_render_reports_parse_errors_and_exits_one(source_file, capsys):
    exit_code = main(["render", "--face", "glyph", source_file("redpill true\n")])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "flatline" in captured.err


def test_render_requires_a_face():
    with pytest.raises(SystemExit) as excinfo:
        main(["render", "some.rain"])
    assert excinfo.value.code == 2


def test_render_missing_file_exits_two(capsys, tmp_path):
    exit_code = main(["render", "--face", "ascii", str(tmp_path / "nope.rain")])
    assert exit_code == 2
    assert "nope.rain" in capsys.readouterr().err
```

In `tests/test_architecture.py`, change the cli entry:

```python
    "cli": {
        "errors", "interpreter", "lexer", "parser", "render", "repl", "treeview",
    },
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: the new render tests FAIL (the subcommand takes no arguments and exits 2 via `_PENDING`).

- [ ] **Step 3: Implement the subcommand**

In `src/matrixlang/cli.py`:

1. Add the import:

```python
from matrixlang.render import render_ascii, render_glyph
```

2. Delete the `_PENDING` dict.

3. Replace the bare `render` subparser registration with:

```python
    render_parser = subcommands.add_parser(
        "render", help="Print a source file in the ASCII or glyph face."
    )
    render_parser.add_argument("path", help="Path to a .rain source file.")
    render_parser.add_argument(
        "--face",
        choices=("ascii", "glyph"),
        required=True,
        help="Which face to print. Rendering is canonical: whitespace normalizes.",
    )
```

4. Replace the dispatch fall-through (the `stage = _PENDING[...]` block) with:

```python
    if args.command == "render":
        return _command_render(args.path, args.face)
    raise AssertionError(f"unhandled command: {args.command}")
```

(The `AssertionError` is unreachable — argparse rejects unknown subcommands — and exists so a future subcommand that forgets its dispatch branch fails loudly instead of exiting 2 with a stale message.)

5. Add the command function, following `_command_parse`'s shape:

```python
def _command_render(path: str, face: str) -> int:
    source = _read_source(path)
    if source is None:
        return 2
    try:
        tree = parse(lex(source))
    except MatrixLangError as error:
        print(f"matrixlang: {error}", file=sys.stderr)
        return 1
    text = render_glyph(tree) if face == "glyph" else render_ascii(tree)
    print(text, end="")
    return 0
```

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/cli.py tests/test_cli.py tests/test_architecture.py
git commit -m "feat(cli): render --face toggles the view; _PENDING retires"
```

---

### Task 7: The glyph-echo REPL

The R-01 demo (design S4-3): you type ASCII at full speed; the machine shows you the operator view.

**Files:**
- Modify: `src/matrixlang/repl.py`, `tests/test_repl.py`, `tests/test_architecture.py`

**Interfaces:**
- Consumes: `render_glyph` from `matrixlang.render`; existing `Repl` internals.
- Produces: `Repl.feed` recognizes `:glyph` / `:ascii` (exact match after strip, only at a fresh prompt — an empty buffer). In glyph mode, each successfully parsed input is echoed as its glyph rendering before execution output. Glyph *input* needs no mode and no new code.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_repl.py`:

```python
def test_the_glyph_command_turns_on_glyph_echo():
    # ﾄ=trace ｧ=1 ﾀ=+ ｨ=2 — the echo is the statement re-rendered in the
    # operator view, printed before the execution output.
    buffer = io.StringIO()
    session = Repl(out=buffer)
    assert session.feed(":glyph") is False
    session.feed("trace 1 + 2")
    assert buffer.getvalue() == "ﾄ ｧ ﾀ ｨ\n3\n"


def test_the_ascii_command_turns_echo_back_off():
    assert feed_all([":glyph", ":ascii", "trace 1"]) == "1\n"


def test_glyph_echo_covers_a_whole_block():
    # ﾃ=dejavu ｷ=false ﾗ=flatline. The echo appears once, after the block
    # completes, in canonical block form.
    output = feed_all([":glyph", "dejavu false", "  trace 1", "flatline"])
    assert output == "ﾃ ｷ\n  ﾄ ｧ\nﾗ\n"


def test_glyph_input_runs_without_any_mode():
    # §6.3: one lexer, no mode flag — the REPL accepts glyph source
    # as-is, even in the default ascii face. ﾄ ｩ == trace 3.
    assert feed_all(["ﾄ ｩ"]) == "3\n"


def test_a_face_command_mid_block_is_just_source():
    # Meta-commands exist only at a fresh prompt. Mid-block, ':glyph' is
    # source text, and ':' is not a MatrixLang character.
    output = feed_all(["dejavu false", ":glyph", "flatline"])
    assert "unexpected character" in output


def test_echo_still_prints_when_execution_fails():
    # The echo shows what was ABOUT to run; a runtime error follows it.
    output = feed_all([":glyph", "trace nope"])
    assert output.startswith("ﾄ nope\n")
    assert "not declared" in output
```

In `tests/test_architecture.py`, change the repl entry:

```python
    "repl": {"errors", "interpreter", "lexer", "parser", "render", "tokens"},
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_repl.py -v`
Expected: the `:glyph` tests FAIL (`:` is an unknown character today). `test_glyph_input_runs_without_any_mode` PASSES already — it documents Task 3's work reaching the REPL for free; keep it.

- [ ] **Step 3: Implement**

In `src/matrixlang/repl.py`:

1. Add the import:

```python
from matrixlang.render import render_glyph
```

2. Add a module-level table under `_OPENERS`:

```python
_FACE_COMMANDS: dict[str, str] = {":ascii": "ascii", ":glyph": "glyph"}
```

3. In `Repl.__init__`, add:

```python
        self._face = "ascii"
```

4. Replace `Repl.feed` with:

```python
    def feed(self, line: str) -> bool:
        """Take one line. Return True if more input is needed."""
        if not self._buffer and line.strip() in _FACE_COMMANDS:
            self._face = _FACE_COMMANDS[line.strip()]
            return False
        self._buffer.append(line)
        source = "\n".join(self._buffer) + "\n"

        try:
            depth = _open_blocks(source)
        except MatrixLangError as error:
            self._fail(error)
            return False

        if depth > 0:
            return True

        try:
            tree = parse(lex(source))
        except MatrixLangError as error:
            self._fail(error)
            return False

        if self._face == "glyph":
            # The echo precedes execution: it shows what is about to run,
            # and still appears when execution then fails.
            print(render_glyph(tree), end="", file=self._out)

        try:
            self.interpreter.run(tree)
        except MatrixLangError as error:
            self._fail(error)
        self._buffer.clear()
        return False
```

(Behaviour-preserving beyond the two additions: parse and run split so the echo can sit between them; the error paths still clear the buffer via `_fail`.)

- [ ] **Step 4: Run the full suite**

Run: `.venv/bin/python -m pytest`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add src/matrixlang/repl.py tests/test_repl.py tests/test_architecture.py
git commit -m "feat(repl): :glyph echoes each statement in the operator view"
```

---

### Task 8: Version bump and close-out

**Files:**
- Modify: `pyproject.toml`, `src/matrixlang/__init__.py`, `README.md`

**Interfaces:** none — documentation and metadata only.

- [ ] **Step 1: Bump the version**

In `pyproject.toml` line 3 and `src/matrixlang/__init__.py` line 3, change `0.3.0` to `0.4.0`.

- [ ] **Step 2: Update the README**

1. Replace the Status line (`Stage 3 — interpreter. The language runs.`) with:

```markdown
Stage 4 — bidirectional glyph rendering. One tree, two faces.
```

2. Replace the sentence `` `render` is reserved for Stage 4 and currently exits 2. `` (end of the paragraph under the `lex` example) with:

```markdown
`render --face glyph` prints the same
program in half-width katakana; `render --face ascii` converts it back
(and doubles as a formatter — whitespace normalizes to canonical form).
```

3. After that paragraph, add a demo block:

````markdown
```bash
.venv/bin/matrixlang render --face glyph examples/hello.rain
```

In the REPL, `:glyph` echoes each statement in the operator view as you
type ASCII; `:ascii` turns it back off. Glyph and mixed-face source are
accepted everywhere with no mode flag — glyphs and ASCII identifiers
occupy disjoint alphabets, so one lexer reads both.
````

- [ ] **Step 3: Run the full suite one last time**

Run: `.venv/bin/python -m pytest`
Expected: all PASS. Confirm the count grew by roughly 350 over Stage 3's 206.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml src/matrixlang/__init__.py README.md
git commit -m "chore: v0.4.0 — Stage 4, the glyph face"
```
