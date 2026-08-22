# SPEC — MatrixLang Language Surface

**Addendum to `SPEC-matrixlang.md` (Draft v1).**

Status: Draft v1
Last updated: 2026-07-29
Scope: defines *what the language is*. The parent spec defines *how it gets built*.

---

## 0. Why this document exists

`SPEC-matrixlang.md` specifies the build path in detail — lexer, parser, interpreter,
glyph rendering, runner — and defends the architecture well. It does not specify the
language. Across roughly 300 lines there is no grammar, no keyword list, no type system,
and exactly one fragment of example code (`ｱ x = 5`).

That gap blocks Stage 1. The parent spec mandates tests-first (`tests/test_lexer.py`
written before `src/lexer.py`), and a lexer test cannot be written without a defined token
set. This document defines it.

## 1. Decisions

| ID | Decision | Rationale |
| --- | --- | --- |
| D-01 | In-universe keyword vocabulary | Places the language in the established themed-esolang genre (ArnoldC, Chef, LOLCODE). §3.1 of the parent spec governs how this is described publicly — the genre is not novel and must never be claimed as such. |
| D-02 | Keyword-delimited blocks (`flatline` closes) | Costs the lexer nothing — a closer is just another keyword — while making every block boundary a glyph rather than Latin punctuation. Braces would sit untranslated in the glyph face and undercut the visual payoff that Stage 4 exists to deliver. |
| D-03 | Glyphs cover keywords, operators, and digits; identifiers and string contents stay ASCII | Under R-02 the two faces are renderings of one AST, so wider glyph coverage costs nothing at authoring time — you write ASCII and toggle. Leaving identifiers in ASCII preserves the debuggability R-02 was written to protect: in a wall of green, the only Latin text is the thing you need to find. |
| D-04 | Types: integer, boolean, string. No floats. | Strings are required for the Stage 3 payoff demo, and unterminated-string is the most natural way to satisfy Stage 1's "malformed input reporting line and column" criterion. Floats buy nothing pedagogically and cost `.` disambiguation, a second numeric type, and a division-semantics tangent. |
| D-05 | Booleans are `true` / `false`, not in-universe | `construct x = awake` reads badly as a literal. Keeps one familiar anchor in every condition. |
| D-06 | Comments are preserved as AST trivia, not discarded | Required for §4.3 of the parent spec to be honest. See §6.1 below. |

## 2. Vocabulary

| Concept | Keyword | Source |
| --- | --- | --- |
| declare | `construct` | The Construct — the film's loading program, where objects are materialized from nothing. |
| assign | *(none — bare `x = 5`)* | Reassignment is not a ceremony. |
| output | `trace` | Agents trace calls. Also a real debugging term, so it teaches a transferable word rather than a private joke. |
| if | `redpill` | The choice. |
| else | `bluepill` | The other choice. |
| while | `dejavu` | *"A déjà vu is usually a glitch in the Matrix"* — canonically a repetition. |
| end block | `flatline` | Ends a running process. |
| booleans | `true` / `false` | D-05. |

All eight are reserved words and may not be used as identifiers.

**Design note.** `redpill` / `bluepill` / `flatline` as an if/else/end triple is the load-
bearing choice in this table. It is not a translation tax laid over a conditional — the red
pill / blue pill *is* a two-branch choice in the source material, so the mapping carries its
own explanation. Spending `redpill` on variable declaration would have used the most
recognizable word in the film on the least interesting construct.

## 3. Lexical structure

### 3.1 Token set

**Keywords (8):** `construct` `trace` `redpill` `bluepill` `dejavu` `flatline` `true` `false`

**Operators (11):** `+` `-` `*` `/` `=` `==` `!=` `<` `>` `<=` `>=`

**Punctuation (2):** `(` `)`

**Literals and names:** `NUMBER` `STRING` `IDENT`

**Structural:** `COMMENT` `NEWLINE` `EOF`

`COMMENT` is a token, not a discarded scrap of text — see §6.1. The lexer emits it into the
stream; the parser attaches it to the AST as trivia. Keeping attachment out of the lexer
means the lexer stays a pure scanner with no knowledge of statements.

Total distinct glyph-mapped slots: 8 keywords + 11 operators + 2 parens + 10 digits +
the `#` comment marker = **32**. Comfortably inside the 135-glyph *Resurrections* set.

### 3.2 Rules

- **Numbers.** Decimal integers only: `[0-9]+`. No sign (unary minus is a parser concern),
  no separators, no exponent.
- **Identifiers.** `[A-Za-z_][A-Za-z0-9_]*`. ASCII only, per R-02.
- **Strings.** Double-quoted. Escapes: `\"`, `\\`, `\n`. A newline inside a string literal
  is an error; an unterminated string at end-of-line is an error reporting line and column.
  **This is the Stage 1 error case.**
  A raw control character inside a string literal is also an error — C0 (U+0000–U+001F),
  DEL (U+007F) and C1 (U+0080–U+009F), except tab. A control character produced by an
  escape (`\n` decoding to U+000A) is fine; the rule screens literal source bytes only.
  See §3.4.
- **Comments.** `#` to end of line. Not discarded — see §6.1. Raw control characters are
  refused here too, on the same terms as strings — a comment needs no quoting, so it is the
  easier carrier of the two. See §3.4.
- **NEWLINE is a token.** Blocks are keyword-delimited and there are no semicolons, so
  statements terminate at end of line. Consecutive newlines and comment-only lines produce
  no statement; the parser skips empty NEWLINEs.
- **Indentation is cosmetic and ignored.** No INDENT/DEDENT. Leading whitespace is skipped
  like any other whitespace.
- **Longest-match on operators.** `==` before `=`, `<=` before `<`.

### 3.3 Teaching point

Episode 1 has a natural beat here: *why does the lexer care about one whitespace character
and not the others?* NEWLINE is significant, spaces and tabs are not. That question has a
concrete answer in this grammar, and it is the first place a viewer sees that lexical
design is a set of choices rather than a set of facts.

### 3.4 Why control characters are refused at the lexer

The lexer preserves raw source bytes verbatim, which is what makes the §4.3 round trip
possible. It is also how a `.rain` file could drive a reader's terminal: an ESC byte in a
string or a comment reached the terminal unescaped through `trace`, `matrixlang parse`,
`matrixlang render` and the REPL's glyph echo. `parse` and `render` are the *inspection*
commands — the safe thing a cautious reader reaches for before running an unknown file —
so the exposure survived the obvious precaution.

Escaping at those output sites is the obvious fix and it is wrong: `render` must reproduce
source exactly, so an escaped byte would re-lex as the escape text rather than the byte,
and §4.3 would fail. Comments have no escape syntax at all, so nothing could decode them
back.

Refusing the byte at the lexer closes every output path at once, because such trees can no
longer be built from source. `values.py`, `treeview.py` and `render.py` need no knowledge
of the rule. It is also the smaller change conceptually: the lexer already refused a raw
newline inside a string, and this generalizes that rule rather than inventing one.

## 4. Grammar

```
program     := statement* EOF

statement   := declare | assign | trace | if | while

declare     := "construct" IDENT "=" expression NEWLINE
assign      := IDENT "=" expression NEWLINE
trace       := "trace" expression NEWLINE
if          := "redpill" expression NEWLINE statement*
               ( "bluepill" NEWLINE statement* )? "flatline" NEWLINE
while       := "dejavu" expression NEWLINE statement* "flatline" NEWLINE

expression  := equality
equality    := comparison ( ( "==" | "!=" ) comparison )*
comparison  := term ( ( "<" | ">" | "<=" | ">=" ) term )*
term        := factor ( ( "+" | "-" ) factor )*
factor      := unary ( ( "*" | "/" ) unary )*
unary       := "-" unary | primary
primary     := NUMBER | STRING | "true" | "false" | IDENT | "(" expression ")"
```

Precedence, loosest to tightest: merge → flip → fork → splice → mask →
equality → comparison → shifts → term → factor → unary → primary.
This satisfies the parent spec's Stage 2 criterion — `2 + 3 * 4` yields 14, with `*` below
`+` in the tree. (Stage 9 adds two further rungs and one word-unary not shown in this
Stage 1 grammar: `fork` is loosest of all, `splice` sits directly tighter than `fork`, and
`unplug` — despite being unary — binds looser than every binary operator except those two,
sitting between `splice` and `equality` rather than at the `unary` rung; see `render.py`'s
`_LEVEL` table for the current, authoritative numbering.)

Bitwise vocabulary is themed: `mask` is integer AND, `merge` is integer OR,
`flip` is integer XOR, `invert` is integer NOT, `uplink` is left shift, and
`downlink` is right shift. All operands are integers; shift counts must be
non-negative. Right shift follows Python's arithmetic right-shift semantics
for negative integers.

The shape is deliberately close to *Crafting Interpreters* Ch. 4–6 so the reference
material lines up with the episodes rather than diverging from them.

## 5. Semantics

- **Dynamic typing.** Values are int, bool, or string. No declared types, no coercion.
- **One flat environment.** A single global dictionary. Blocks do not introduce scope.
  This is consistent with the parent spec §6, which defers functions and closures — with no
  functions there is nothing for lexical scoping to do yet, and a flat dict is exactly the
  "an environment is a dictionary" demystification Stage 3 is built around.
- **`construct` declares; `=` requires a prior declaration.** Re-declaring a live name is an
  error, and assigning to a name that was never declared is an error. This is what makes `construct`
  carry meaning rather than being decoration.
- **Conditions must be boolean.** No truthy integers, no truthy strings. Strict typing here
  produces better error messages and a cleaner lesson.
- **Arithmetic is integer-only.** `/` truncates toward zero. Division by zero is a runtime
  error.
- **`+` is overloaded** for integer addition and string concatenation. Mixed operands are an
  error — no implicit stringification.
- **`==` and `!=` work on any two values of the same type.** Ordering comparisons
  (`< > <= >=`) are integers only.
- **Unary `-` is integers only.**
- **`trace` prints one value followed by a newline.** Strings print without quotes; booleans
  print as `true` / `false`.
- **All errors report line and column.**

## 6. Glyph rendering

### 6.1 Comments and the round-trip criterion

The parent spec §4.3 states, for any valid program `t`:

```
parse(render_glyph(t)) == parse(render_ascii(t)) == t
```

Comments are not normally present in an AST. Under a discard-at-lex-time design, that
criterion is satisfied while the toggle **silently deletes every comment in the file** —
which contradicts R-02's promise that round-tripping is loss-free.

**Resolution (D-06):** comments are preserved as trivia on the AST.

- Each statement node carries `leading_comments: list[str]` and an optional
  `trailing_comment: str` for a same-line comment.
- The program node carries `trailing_comments` for anything after the last statement.
- AST equality in §4.3 includes trivia.
- Source positions (line, column) are carried on nodes for error reporting but are
  **excluded** from AST equality — a re-rendered face has different columns, and the
  §4.3 criterion must still hold.

Cheap at Stage 1, expensive to retrofit at Stage 4. It also gives episode 1 a good aside:
*where do comments live in a compiler, and why is the obvious answer wrong?*

**Trivia well-formedness invariant.** Every trivia string starts with `#` and contains
no newline. Two shapes would otherwise break the round trip: a trailing comment without
a leading `#` renders as code and re-lexes as tokens; a comment containing a newline
renders as two lines and re-parses as two comments. The Stage 4 tree generator must
enforce this invariant; dataclass-level validation is optional.

**Whitespace is outside the loss-free promise.** Blank lines and indentation are not
trivia and are not preserved: rendering normalizes them to the canonical form (one
statement per line, fixed indentation, no blank lines — see the Stage 4 design spec).
Loss-free round-tripping covers semantics and comments. The §4.3 criterion is unaffected
because it is tree-level; the user-facing consequence is that the view toggle also
pretty-prints.

### 6.2 Mapping policy

- A fixed **bijective** table over the 32 slots in §3.1. Glyph assignments are drawn from
  the Rezmason set at Stage 4 and are not specified here.
- **Digits map per-digit**, positionally: `10` renders as two glyphs.
- Identifiers, string contents, and whitespace are unchanged.
- Comments render with their `#` marker mapped; comment text is unchanged.

### 6.3 A property worth noting

Because glyphs and ASCII identifiers occupy **disjoint alphabets**, the glyph face is
trivially unambiguous to lex: anything in the glyph range is a keyword, operator, digit, or
paren; anything Latin is an identifier or string content. Two consequences:

1. One lexer handles both faces. There is no mode flag and no separate glyph lexer.
2. **Mixed-face source is valid** — a file may contain glyph keywords and ASCII operators in
   any combination and still lex correctly.

Consequence 2 is a free win from D-03 that is worth demonstrating on camera in Stage 4,
because it makes the "two renderings of one tree" claim concrete rather than asserted.

### 6.4 Renderer parenthesization duties

There is no Grouping node (deliberate — parens are a parse-time instruction, not
structure). The renderer must therefore reconstruct parentheses from precedence AND
associativity, or rendering silently changes meaning:

- **R-PAREN-1 (precedence):** parenthesize a child whose precedence is lower than its
  context requires.
- **R-PAREN-2 (associativity):** parenthesize the right child of a left-associative
  binary when precedences are *equal* — `Binary(1, +, Binary(2, +, 3))` must emit
  `1 + (2 + 3)`, not `1 + 2 + 3`; likewise for `-` and `/`.
- **R-PAREN-3 (unary operand):** parenthesize a binary operand of a unary —
  `Unary(-, Binary(2, *, 3))` naively renders `-2 * 3`, which changes the meaning; it
  must emit `-(2 * 3)`. (Stage 9 carve-out: this rule holds for `-` and `length`, whose
  operand binds tighter than everything else in the unary's context. It does NOT hold
  for `unplug`, which binds looser than comparison — `unplug n == 1` needs no parens
  around `n == 1` to mean `unplug (n == 1)`. R-PAREN-3 as stated applies to `-` and
  `length` only; `unplug`'s own operand precedence is documented where `_LEVEL` is
  defined in `render.py`.)

Each is a named requirement with its own directed test. The §4.3 property test only
catches violations if the tree generator produces these shapes, so the generator must
produce them deliberately.

## 7. Example programs

### 7.1 The Stage 3 demo

```
construct n = 0
construct name = "Neo"

dejavu n < 3
  redpill n == 1
    trace "wake up, " + name
  bluepill
    trace n
  flatline
  n = n + 1
flatline
```

Output:

```
0
wake up, Neo
2
```

Exercises declaration, all three types, assignment, a loop, a two-branch conditional,
nested blocks, string concatenation, and both comparison forms. Not exercised: `-`, `*`,
`/`, unary minus, and parenthesized grouping — those belong in Stage 2's precedence demo
(`2 + 3 * 4`), not here.

### 7.2 The Stage 1 opening commit

The parent spec §8 specifies `lex("x = 2 + 3")` as the first action. That remains valid
under this grammar — it is an `assign` statement — and now has a defined expected output:

```python
lex("x = 2 + 3")
# [IDENT(x), ASSIGN, NUMBER(2), PLUS, NUMBER(3), NEWLINE, EOF]
```

No change to the parent spec's first action is required.

## 8. Stage 1 acceptance tests

The parent spec's Stage 1 criterion is "numbers, identifiers, operators, and whitespace,
plus at least one malformed input reporting line and column." Concretely:

| # | Input | Expectation |
| --- | --- | --- |
| 1 | `x = 2 + 3` | `[IDENT, ASSIGN, NUMBER, PLUS, NUMBER, NEWLINE, EOF]` |
| 2 | `construct n = 0` | keyword recognized as `CONSTRUCT`, not `IDENT` |
| 3 | `constructor = 1` | `IDENT(constructor)` — keyword matching does not fire on a prefix |
| 4 | `n <= 10` | `LTE`, one token, not `LT` followed by `ASSIGN` |
| 5 | `"wake up, " + name` | `STRING` with escapes resolved, contents preserved verbatim |
| 6 | `trace x  # comment` | comment captured as trivia, not dropped |
| 7 | `\n\n\nx = 1` | blank lines produce NEWLINEs, no spurious tokens |
| 8 | `trace "unterminated` | error reporting line **and column** |
| 9 | `construct x = 5 @ 3` | unknown character error with line and column |

Tests 3, 4, and 8 are the ones that actually catch bugs; the rest are regression cover.

## 9. Deferred

Out of scope for v1, consistent with the parent spec §6:

- Floats, and any second numeric type
- Functions, closures, lexical scope, return values
- Collections of any kind
- `else if` chaining — nest a `redpill` inside a `bluepill` instead
- Logical operators (`and`, `or`, `not`) — reachable, but not needed for Turing completeness
  and not needed for any Stage 1–5 demo
- String indexing, slicing, length, or any string method
- `bluepill` as a standalone statement (unset / delete a variable). The word is free and the
  semantics are cute; there is no v1 use for it.

## 10. Amendments to the parent spec

Both amendments below were applied to `SPEC-matrixlang.md` during Stage 1 and are
recorded here for provenance:

1. **§4.3** — state that AST equality includes comment trivia (§6.1 above). As written, the
   criterion passes while the feature it exists to guarantee is broken.
2. **§8** — the first action is unchanged, but the expected token list from §7.2 above
   should be inlined so the opening commit has a test to write against.

Applied before the Stage 4 plan (2026-07-30, per the Stage 2/3 final reviews and the
Stage 4 design spec):

3. **§4.3** — quantifies over ASTs, not programs; `t` is compared against `parse(...)`
   output, so it was always a tree.
4. **R-02 (§4.2)** — loss-free covers semantics and comments; whitespace normalizes to
   the canonical rendering. Mirrored in §6.1 above.
5. **§6.1 above** — trivia well-formedness invariant stated.
6. **§6.4 above** — renderer parenthesization duties stated as named requirements.
