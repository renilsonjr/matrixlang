# Design — Control-Character Rejection at the Lexer

Status: Approved (brainstorm 2026-07-30)
Context: a whole-repository security review of main @ v0.5.0.

## 1. The problem

The lexer preserves raw source bytes verbatim inside string literals and comments.
That is correct for round-tripping, but several output paths write that text to a
terminal with no escaping, so a `.rain` file can drive the reader's terminal.
Confirmed against the shipped code:

```
trace  -> '\x1b[31mRED\x1b[0m\n'
parse  -> "Program\n  Declare 'x'  #\x1b[8mhidden\x1b[0m\n    NumberLiteral 1\n"
render -> 'construct x = 1  #\x1b[8mhidden\x1b[0m\n'
```

`parse` and `render` matter most. They are the *inspection* commands — the safe
thing a cautious reader reaches for before running an unknown file — and they are
affected too.

`treeview.py` already escapes string literals via `!r` (`StringLiteral '\x1bX'`)
while passing comment text through raw, in the same function, to the same stream.
That inconsistency is the evidence this is an oversight rather than a decision.

**Not affected**, and confirmed by grep over `src/`: there is no `eval`, `exec`,
`compile`, `pickle`, `marshal`, `subprocess`, `os.system`, `__import__`, socket,
or XML/YAML use anywhere. A MatrixLang program has no route into Python, no file
writes, and no network. This is the only finding.

## 2. Why the obvious fix is wrong

Escaping at the output sites breaks the parent spec's §4.3 criterion.

Trees carrying a raw control byte round-trip correctly **today**, because
`render` emits the byte raw and the lexer reads it back:

```
comment: parse(lex(render_ascii(t))) == t  ->  True
string : parse(lex(render_ascii(t))) == t  ->  True
```

If `render` escaped that byte to `\x1b`, re-lexing would yield those four literal
characters instead, and equality would fail. Comments have no escape syntax at
all, so there is no decode path that could rescue it.

## 3. The decision

**Reject control characters at the lexer.** Generalize the rule the lexer already
enforces — *"a newline inside a string literal is an error"* (language-surface
spec §3.2), which today produces `[line 1, column 7] unterminated string` — to
all control characters, in both string literals and comments.

This fixes every output path at once, because such trees can no longer be built
from source. `values.py`, `treeview.py` and `render.py` need no changes, and §4.3
is untouched: the trees that would have broken it are now unconstructible.

### Rejected set

C0 (U+0000–U+001F), DEL (U+007F), and C1 (U+0080–U+009F), with two carve-outs:

- **Tab (U+0009) stays legal.** It is harmless for terminal injection and
  rejecting it would break working programs for no security gain.
- **Newline (U+000A) keeps its current error.** Inside a string it already
  reports `unterminated string`, which is more useful than a generic
  control-character message. That path is untouched.

### Where

- `_scan_string` in `lexer.py` — the character loop, before a byte is appended
  to the decoded value.
- The comment branch of `lex` — the scan to end of line.

A shared module-level predicate keeps the rule in one place.

### Error

A `LexError` reporting line and column, consistent with every other lexer error,
naming the offending codepoint — for example
`control character U+001B is not allowed in a string`.

## 4. Testing

- Rejection of ESC in a string literal and in a comment, each asserting line and
  column.
- The boundaries of the rejected set: NUL, DEL (U+007F), and a C1 character.
- Tab still accepted inside a string, with its value preserved.
- Newline inside a string still reports `unterminated string`, not the new
  message — the existing test stays green unmodified.
- **The regression test that states the actual security property:** a hostile
  source file carrying escape bytes in both a string and a comment is fed to
  `lex`, and every one of `parse`, `render_ascii`, `render_glyph` and `run` is
  unreachable because lexing raises first.
- A teeth-check on the guard: remove it, confirm the rejection tests fail,
  restore.

## 5. Documentation

- Language-surface spec §3.2 (Strings) and §3.2 (Comments) gain the
  control-character rule.
- The README's untrusted-`.rain` note narrows from "does not sanitize terminal
  control characters" to the accurate post-fix statement.

## 6. Deliberate limits

- **Hand-built ASTs are unaffected.** Python code can still construct a
  `StringLiteral` containing a control character and render it raw. Not
  attacker-reachable: an attacker supplies source text, not Python objects.
- **CLI error messages are unaffected**, and do not need to change — they
  interpolate only ASCII identifiers (the lexer restricts identifiers to
  `[A-Za-z_][A-Za-z0-9_]*`) and type names from a fixed internal set.
- **Terminal output from the rain is unaffected.** `ansi.py` builds fixed-shape
  sequences parameterized by internal ints and floats, never by source text.
