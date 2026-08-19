# Input for MatrixLang Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give MatrixLang input — a `jackin` keyword that reads one line as text, a `decode` keyword that turns text into a number, and an `InputSource` protocol that lets the CLI, the REPL, the browser and the tests each supply lines their own way.

**Architecture:** Input copies the shape `events.py` already uses for output. A new `src/matrixlang/input.py` declares an `InputSource` protocol and five providers; `Interpreter` gains a `source` parameter defaulting to `EmptySource`, so nothing blocks on a terminal by accident. `jackin` is a zero-operand expression node; `decode` reuses the existing `Unary` node with a new `TokenType`, joining `length` at the `_unary` precedence level. Both keywords take glyph slots, so the glyph budget's two hand-tracked counts move deliberately.

**Tech Stack:** Python 3.11+ stdlib, pytest, plain HTML/CSS/JS, Node's built-in `node --test`. No new dependencies, no build step.

## Global Constraints

- Keywords are **`jackin`** and **`decode`** — single words, no underscore, matching `jackout` and every other keyword (JI-1).
- `jackin` **always yields text**, never auto-detecting a number (JI-2).
- Numbers are **integers only** — the lexer builds them with `int(...)`, so `decode "5.5"` is an error (JI-3).
- `decode` **binds tighter than arithmetic**, at the same `_unary` level as `length`: `decode jackin + 1` is `(decode jackin) + 1` (JI-5).
- `Interpreter`'s source default is **`EmptySource`, never `StdinSource`** — a default that read a terminal could hang a server request (JI-7).
- Running out of input is a **runtime error** carrying line and column: `no input left to read` (JI-8).
- `operator/validate.py`'s `check()` **must** supply a canned source, or every program Operator writes with `jackin` fails its dry run (JI-9).
- `site/checks/no_semantics.py` and `site/checks/key_handling.py` must stay passing, **unmodified**.
- The full suite stays green: `python3 -m pytest -q` and `node --test site/tests/*.test.mjs`.
- Run every command from the repo root with `PYTHONPATH="$PWD/src"` prefixed for `python3 -m pytest`, matching how this worktree is set up.

## File Structure

| Path | Responsibility |
| --- | --- |
| `src/matrixlang/input.py` | **New.** The `InputSource` protocol and five providers. Pure protocol and data, imports nothing from the interpreter — the same rule `events.py` follows. |
| `src/matrixlang/tokens.py` | Two `TokenType` members, two `KEYWORDS` entries. Lexing both faces then works automatically (see Task 2). |
| `src/matrixlang/glyphs.py` | Two table entries. |
| `tests/test_glyphs.py` | The two hand-tracked counts and the budget ledger. |
| `src/matrixlang/nodes.py` | A `JackIn` expression node. `decode` reuses `Unary`. |
| `src/matrixlang/parser.py` | `JACKIN` in `_primary`, `DECODE` in `_unary`. |
| `src/matrixlang/interpreter.py` | The `source` parameter; evaluating both nodes. |
| `src/matrixlang/render.py` | Both keywords in both faces, with the word-separator rule `length` already needs. |
| `src/matrixlang/cli.py`, `repl.py` | Wire a `StdinSource`. |
| `src/matrixlang/operator/validate.py` | The canned source. |
| `site/glue.py` | `run(..., stdin=...)`. |
| `site/index.html`, `style.css`, `playground.js` | The input textarea and its wiring. |
| `docs/LEARNING-MATRIXLANG.md` | Both keywords documented. |

**Deliberately left alone:** `server/runs.py:139` constructs an `Interpreter` for the local `web-ui` server. It keeps the `EmptySource` default, so a program using `jackin` there fails with `no input left to read` — truthful, since that surface has no input box. Adding one is out of scope (Task 8 records this).

---

### Task 1: The InputSource protocol and its providers

**Files:**
- Create: `src/matrixlang/input.py`
- Create: `tests/test_input.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `InputSource` protocol with `next_line(self) -> str | None` (None means exhausted); classes `EmptySource()`, `ListSource(lines: Sequence[str])`, `BufferSource(text: str)`, `StdinSource(stream: TextIO | None = None)`, `ConstantSource(line: str)`. Every later task imports from `matrixlang.input`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_input.py`:

```python
"""The input providers, exercised directly.

`events.py` has TextSink and the cascade; this is the same split for the
other direction. Each provider is tested here so the interpreter tests can
use ListSource without wondering whether the source itself is correct.
"""

import io

from matrixlang.input import (
    BufferSource,
    ConstantSource,
    EmptySource,
    ListSource,
    StdinSource,
)


def test_empty_source_is_exhausted_immediately():
    assert EmptySource().next_line() is None


def test_list_source_yields_each_line_then_none():
    source = ListSource(["Neo", "Trinity"])
    assert source.next_line() == "Neo"
    assert source.next_line() == "Trinity"
    assert source.next_line() is None
    # Still exhausted on a second ask -- no wrapping around.
    assert source.next_line() is None


def test_buffer_source_splits_text_into_lines():
    source = BufferSource("Neo\nTrinity\n")
    assert source.next_line() == "Neo"
    assert source.next_line() == "Trinity"
    assert source.next_line() is None


def test_buffer_source_of_empty_text_has_no_lines():
    assert BufferSource("").next_line() is None


def test_stdin_source_strips_only_the_newline():
    # Trailing spaces are content. Python's input() keeps them and so does
    # this -- a program reading "  " should see two spaces, not "".
    source = StdinSource(io.StringIO("Neo  \nTrinity\n"))
    assert source.next_line() == "Neo  "
    assert source.next_line() == "Trinity"
    assert source.next_line() is None


def test_stdin_source_handles_a_final_line_without_a_newline():
    source = StdinSource(io.StringIO("Neo"))
    assert source.next_line() == "Neo"
    assert source.next_line() is None


def test_stdin_source_distinguishes_a_blank_line_from_the_end():
    # readline() returns "\n" for a blank line and "" at EOF. Collapsing
    # the two would make a blank line look like exhaustion.
    source = StdinSource(io.StringIO("\nNeo\n"))
    assert source.next_line() == ""
    assert source.next_line() == "Neo"
    assert source.next_line() is None


def test_constant_source_never_runs_out():
    source = ConstantSource("1")
    assert [source.next_line() for _ in range(3)] == ["1", "1", "1"]
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH="$PWD/src" python3 -m pytest tests/test_input.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'matrixlang.input'`.

- [ ] **Step 3: Write `src/matrixlang/input.py`**

```python
"""Where a running program's input comes from.

The mirror of `events.py`. That module exists because printing decides
*where* output goes at the point that knows least about it; reading is the
same decision in the other direction. The interpreter asks for a line and
never learns whether it came from a terminal, a textarea, or a list in a
test.

`next_line` returns None for "exhausted", never a sentinel string: a blank
line is real input, and "" would make the two indistinguishable.

Pure protocol and data, like `tokens.py` and `nodes.py`. Imports nothing
from the interpreter.
"""

import sys
from typing import Protocol, Sequence, TextIO


class InputSource(Protocol):
    """Anything a running program can read lines from."""

    def next_line(self) -> str | None: ...


class EmptySource:
    """No input at all. The Interpreter's default.

    The default is deliberately NOT StdinSource. A default that read a
    terminal would hang any caller that forgot to pass a source --
    including `operator/validate.py`'s dry run, which executes untrusted
    candidate programs inside a server request.
    """

    def next_line(self) -> str | None:
        return None


class ListSource:
    """Lines from a list. What the tests use."""

    def __init__(self, lines: Sequence[str]) -> None:
        self._lines = list(lines)
        self._index = 0

    def next_line(self) -> str | None:
        if self._index >= len(self._lines):
            return None
        line = self._lines[self._index]
        self._index += 1
        return line


class BufferSource(ListSource):
    """Lines from text supplied before the program ran. The browser's.

    Never blocks, which is the whole reason the playground can offer input:
    JavaScript is single-threaded, so a read that waited would freeze the
    tab and the cascade drawing in it.
    """

    def __init__(self, text: str) -> None:
        super().__init__(text.splitlines())


class StdinSource:
    """Lines from a stream, normally the real stdin. The CLI's and REPL's.

    May block, which is correct at a terminal and nowhere else.
    """

    def __init__(self, stream: TextIO | None = None) -> None:
        self._stream = sys.stdin if stream is None else stream

    def next_line(self) -> str | None:
        line = self._stream.readline()
        # readline() returns "" only at end of stream; a blank line is
        # "\n". Testing for "" rather than falsiness keeps them apart.
        if line == "":
            return None
        return line.rstrip("\r\n")


class ConstantSource:
    """The same line, forever. Used by the validate gate.

    A dry run asks "does this parse and execute without crashing", not
    "what does this print". Immediate exhaustion would answer a question
    nobody asked and reject correct programs for lacking input the gate
    never had. Bounded by the caller's step limit, so it cannot hang.
    """

    def __init__(self, line: str) -> None:
        self._line = line

    def next_line(self) -> str | None:
        return self._line
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH="$PWD/src" python3 -m pytest tests/test_input.py -q`
Expected: PASS, 8 tests.

- [ ] **Step 5: Run the full suite**

Run: `PYTHONPATH="$PWD/src" python3 -m pytest -q`
Expected: PASS — a new module nothing imports yet cannot affect anything.

- [ ] **Step 6: Commit**

```bash
git add src/matrixlang/input.py tests/test_input.py
git commit -m "feat: add the InputSource protocol and its providers"
```

---

### Task 2: Tokens, glyphs, and the hand-tracked budget

**Files:**
- Modify: `src/matrixlang/tokens.py`
- Modify: `src/matrixlang/glyphs.py`
- Modify: `tests/test_glyphs.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces: `TokenType.JACKIN`, `TokenType.DECODE`; `KEYWORDS["jackin"]`, `KEYWORDS["decode"]`; `GLYPHS["jackin"] == "ｲ"`, `GLYPHS["decode"] == "ｺ"`. Later tasks reference these token types by name.

**Why lexing needs no change:** `lexer.py` builds `_GLYPH_TOKENS` by walking `GLYPHS` and looking each slot up in `KEYWORDS`. Adding to both dicts makes both faces lex the new keywords automatically. Do not edit `lexer.py`.

- [ ] **Step 1: Write the failing lexer test**

Append to `tests/test_lexer.py`:

```python
def test_the_input_keywords_lex_in_both_faces():
    from matrixlang.glyphs import GLYPHS

    for ascii_word in ("jackin", "decode"):
        (token, _eof) = [t for t in lex(ascii_word) if t.type is not TokenType.NEWLINE]
        assert token.type is KEYWORDS[ascii_word], f"{ascii_word} did not lex"
        (glyph_token, _) = [
            t for t in lex(GLYPHS[ascii_word]) if t.type is not TokenType.NEWLINE
        ]
        assert glyph_token.type is token.type, f"{ascii_word}'s glyph face did not lex"
```

If `tests/test_lexer.py` does not already import `KEYWORDS` and `TokenType`, add them to its imports from `matrixlang.tokens`.

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH="$PWD/src" python3 -m pytest tests/test_lexer.py -q -k input_keywords`
Expected: FAIL with `KeyError: 'jackin'`.

- [ ] **Step 3: Add the token types and keywords**

In `src/matrixlang/tokens.py`, add to the `TokenType` enum after `UNPLUG`:

```python
    UNPLUG = auto()
    JACKIN = auto()
    DECODE = auto()
```

and to the `KEYWORDS` dict after `"unplug"`:

```python
    "unplug": TokenType.UNPLUG,
    "jackin": TokenType.JACKIN,
    "decode": TokenType.DECODE,
```

- [ ] **Step 4: Add the glyphs**

In `src/matrixlang/glyphs.py`, after the `"unplug": "ｳ",` line and before the `# operators` comment:

```python
    # Input. `jackin` takes ｲ for the "i" of "in", pairing with jackout's
    # ﾖ: one carries a value out of a function, the other brings one in
    # from the world. `decode` takes ｺ for the "co" in the middle of it.
    "jackin": "ｲ",
    "decode": "ｺ",
```

- [ ] **Step 5: Update the two hand-tracked counts**

Both are hardcoded on purpose — `test_the_glyph_budget_is_tracked_not_discovered` says so in its own name. A budget that recomputed itself would let a keyword take a slot with nobody noticing.

In `tests/test_glyphs.py`, in `test_the_table_covers_exactly_the_41_slots`, extend the comment and change the count:

```python
def test_the_table_covers_exactly_the_43_slots():
    # Language spec §3.1, plus Stage 6: 11 keywords (agent and jackout
    # join, length in Stage 7) + 11 operators + 2 parens + a comma +
    # 2 brackets + 10 digits + the '#' comment marker + Stage 9: 3 logical
    # operators (splice, fork, unplug) + input: jackin and decode.
    # Nothing more (identifiers and string contents stay ASCII, per D-03),
    # nothing less.
    expected = (
        set(KEYWORDS)
        | {"+", "-", "*", "/", "=", "==", "!=", "<", ">", "<=", ">="}
        | {"(", ")", ","}
        | {"[", "]"}
        | set(string.digits)
        | {"#"}
    )
    assert set(GLYPHS) == expected
    assert len(expected) == 43
```

and in `test_the_glyph_budget_is_tracked_not_discovered`, add this change to the ledger:

```python
def test_the_glyph_budget_is_tracked_not_discovered():
    # Stage 6 design §1: 24 free before, 3 spent, 21 left. Stage 7
    # spends 3 more for lists: 21 - 3 = 18 left. Stage 9 spends 3 more
    # for logical operators: 18 - 3 = 15 left. Input spends 2 for jackin
    # and decode: 15 - 2 = 13 left. Finite, and worth knowing.
    free = sum(
        1
        for code in range(BLOCK_START, BLOCK_END + 1)
        if chr(code) not in set(GLYPHS.values())
    )
    assert free == 13
```

Rename the first test to `test_the_table_covers_exactly_the_43_slots` as shown, so the name keeps matching what it asserts.

- [ ] **Step 6: Run the lexer and glyph tests**

Run: `PYTHONPATH="$PWD/src" python3 -m pytest tests/test_lexer.py tests/test_glyphs.py -q`
Expected: PASS.

- [ ] **Step 7: Run the full suite**

Run: `PYTHONPATH="$PWD/src" python3 -m pytest -q`
Expected: PASS. If a test elsewhere asserts a keyword count, update it the same deliberate way and say so in the commit message.

- [ ] **Step 8: Commit**

```bash
git add src/matrixlang/tokens.py src/matrixlang/glyphs.py tests/test_glyphs.py tests/test_lexer.py
git commit -m "feat: add jackin and decode to the token and glyph tables"
```

---

### Task 3: The nodes and the parser

**Files:**
- Modify: `src/matrixlang/nodes.py`
- Modify: `src/matrixlang/parser.py`
- Modify: `tests/test_parser.py`

**Interfaces:**
- Consumes: `TokenType.JACKIN`, `TokenType.DECODE` (Task 2).
- Produces: `nodes.JackIn` — an `Expr` subclass with no fields of its own, carrying only the inherited `line`/`column`. `decode` produces `Unary(TokenType.DECODE, operand)`, reusing the existing node exactly as `length` and `unplug` do.

- [ ] **Step 1: Write the failing parser tests**

Append to `tests/test_parser.py`:

```python
def test_jackin_parses_as_an_expression():
    from matrixlang.nodes import Declare, JackIn

    program = parse(lex("construct name = jackin\n"))
    (declare,) = program.statements
    assert isinstance(declare, Declare)
    assert isinstance(declare.value, JackIn)


def test_decode_parses_as_a_unary_on_its_operand():
    from matrixlang.nodes import JackIn, Unary

    program = parse(lex("construct n = decode jackin\n"))
    (declare,) = program.statements
    assert isinstance(declare.value, Unary)
    assert declare.value.op is TokenType.DECODE
    assert isinstance(declare.value.operand, JackIn)


def test_decode_binds_tighter_than_arithmetic():
    # `decode jackin + 1` must be `(decode jackin) + 1`. The loose reading
    # would decode the result of adding 1 to text, which is an error for
    # every possible input -- the same argument that puts `length` at this
    # level. This differs from `unplug`, which binds LOOSER than
    # comparison, and that asymmetry is deliberate: see the design doc §3.
    from matrixlang.nodes import Binary, Unary

    program = parse(lex("construct n = decode jackin + 1\n"))
    (declare,) = program.statements
    assert isinstance(declare.value, Binary), "decode swallowed the addition"
    assert declare.value.op is TokenType.PLUS
    assert isinstance(declare.value.left, Unary)
    assert declare.value.left.op is TokenType.DECODE


def test_decode_of_a_parenthesised_expression_still_works():
    from matrixlang.nodes import StringLiteral, Unary

    program = parse(lex('construct n = decode ("5")\n'))
    (declare,) = program.statements
    assert isinstance(declare.value, Unary)
    assert isinstance(declare.value.operand, StringLiteral)
```

If `tests/test_parser.py` does not already import `TokenType`, add `from matrixlang.tokens import TokenType`.

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH="$PWD/src" python3 -m pytest tests/test_parser.py -q -k "jackin or decode"`
Expected: FAIL — `ImportError: cannot import name 'JackIn'`.

- [ ] **Step 3: Add the `JackIn` node**

In `src/matrixlang/nodes.py`, after the `Name` dataclass and before `Unary`:

```python
@dataclass
class JackIn(Expr):
    """Read one line of input. No operand — the source supplies it.

    A node of its own rather than a Unary with no operand, because every
    Unary carries one and a None operand would make every consumer test
    for it.
    """
```

A dataclass whose body is only a docstring is valid; it inherits `line` and `column` from `Node` and adds nothing.

- [ ] **Step 4: Parse `jackin` in `_primary`**

In `src/matrixlang/parser.py`, add `JackIn` to the imports from `matrixlang.nodes`, then in `_primary`, immediately after the `TokenType.IDENT` branch:

```python
        if token.type is TokenType.JACKIN:
            self.advance()
            return JackIn(line=token.line, column=token.column)
```

- [ ] **Step 5: Parse `decode` in `_unary`**

In `src/matrixlang/parser.py`, change `_unary`'s guard to include `DECODE`:

```python
    def _unary(self) -> Expr:
        # `decode` sits here beside `length` rather than at `_not`'s level,
        # and for the same reason: it PRODUCES a number that arithmetic
        # then consumes, so `decode jackin + 1` must be
        # `(decode jackin) + 1`. `unplug` binds looser because it CONSUMES
        # a boolean that comparison produces. Different operand types,
        # different natural reach -- design doc §3.
        if (
            self.check(TokenType.MINUS)
            or self.check(TokenType.LENGTH)
            or self.check(TokenType.DECODE)
        ):
            op = self.advance()
            operand = self._unary()
            return Unary(op.type, operand, line=op.line, column=op.column)
        return self._call()
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `PYTHONPATH="$PWD/src" python3 -m pytest tests/test_parser.py -q`
Expected: PASS.

- [ ] **Step 7: Run the full suite**

Run: `PYTHONPATH="$PWD/src" python3 -m pytest -q`
Expected: PASS. Rendering is not wired yet (Task 5), but no existing test builds a tree containing these nodes, so nothing reaches `render.py`.

- [ ] **Step 8: Commit**

```bash
git add src/matrixlang/nodes.py src/matrixlang/parser.py tests/test_parser.py
git commit -m "feat: parse jackin and decode"
```

---

### Task 4: Evaluating both keywords

**Files:**
- Modify: `src/matrixlang/interpreter.py`
- Modify: `tests/test_interpreter.py`

**Interfaces:**
- Consumes: `matrixlang.input.EmptySource`, `matrixlang.input.InputSource`, `matrixlang.input.ListSource` (Task 1); `nodes.JackIn`, `Unary` with `TokenType.DECODE` (Task 3).
- Produces: `Interpreter(out=None, sink=None, max_steps=DEFAULT_MAX_STEPS, source: InputSource | None = None)`. `source=None` means `EmptySource()`. Later tasks pass a source by keyword.

- [ ] **Step 1: Write the failing interpreter tests**

Append to `tests/test_interpreter.py`, using whatever run-and-capture helper that file already defines. If it has none, use this local one:

```python
def _run_with_input(source_text: str, lines: list[str]) -> list[str]:
    """Run a program with supplied input, returning its output lines."""
    import io

    from matrixlang.input import ListSource
    from matrixlang.interpreter import Interpreter
    from matrixlang.lexer import lex
    from matrixlang.parser import parse

    out = io.StringIO()
    Interpreter(out=out, source=ListSource(lines)).run(parse(lex(source_text)))
    return out.getvalue().splitlines()


def test_jackin_reads_a_line_as_text():
    assert _run_with_input("trace jackin\n", ["Neo"]) == ["Neo"]


def test_jackin_reads_successive_lines_in_order():
    program = "trace jackin\ntrace jackin\n"
    assert _run_with_input(program, ["Neo", "Trinity"]) == ["Neo", "Trinity"]


def test_jackin_yields_text_not_a_number():
    # "5" stays text, so concatenation works and arithmetic does not.
    assert _run_with_input('trace jackin + "!"\n', ["5"]) == ["5!"]


def test_running_out_of_input_is_an_error_with_a_position():
    from matrixlang.errors import MatrixLangError

    with pytest.raises(MatrixLangError) as caught:
        _run_with_input("trace jackin\n", [])
    assert "no input left to read" in caught.value.message
    assert caught.value.line == 1


def test_decode_turns_text_into_a_number():
    assert _run_with_input("trace decode jackin + 1\n", ["41"]) == ["42"]


def test_decode_accepts_a_negative_number_and_surrounding_spaces():
    assert _run_with_input("trace decode jackin\n", ["  -3 "]) == ["-3"]


def test_decode_rejects_text_that_is_not_a_number():
    from matrixlang.errors import MatrixLangError

    with pytest.raises(MatrixLangError) as caught:
        _run_with_input("trace decode jackin\n", ["abc"])
    assert "decode" in caught.value.message


def test_decode_rejects_a_float_spelling():
    # The language has integers only -- the lexer builds numbers with int().
    from matrixlang.errors import MatrixLangError

    with pytest.raises(MatrixLangError):
        _run_with_input("trace decode jackin\n", ["5.5"])


def test_decode_rejects_a_value_that_is_already_a_number():
    # Strict like `splice`, which refuses an integer rather than coercing.
    # A decode that passed numbers through would hide a double decode.
    from matrixlang.errors import MatrixLangError

    with pytest.raises(MatrixLangError) as caught:
        _run_with_input("trace decode 5\n", [])
    assert "decode" in caught.value.message


def test_the_default_source_is_empty_never_stdin():
    # A default that read a terminal would hang validate.py's dry run
    # inside a server request. Empty is the only safe default.
    import io

    from matrixlang.errors import MatrixLangError
    from matrixlang.interpreter import Interpreter
    from matrixlang.lexer import lex
    from matrixlang.parser import parse

    with pytest.raises(MatrixLangError) as caught:
        Interpreter(out=io.StringIO()).run(parse(lex("trace jackin\n")))
    assert "no input left to read" in caught.value.message
```

If `tests/test_interpreter.py` does not already import `pytest`, add it.

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH="$PWD/src" python3 -m pytest tests/test_interpreter.py -q -k "jackin or decode or default_source"`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'source'`.

- [ ] **Step 3: Add the `source` parameter**

In `src/matrixlang/interpreter.py`, add to the imports:

```python
from matrixlang.input import EmptySource, InputSource
```

and add `JackIn` to the existing `from matrixlang.nodes import (...)` block.

Then extend `Interpreter.__init__`'s signature and body:

```python
    def __init__(
        self,
        out: TextIO | None = None,
        sink: EventSink | None = None,
        max_steps: int | None = DEFAULT_MAX_STEPS,
        source: InputSource | None = None,
    ) -> None:
```

and inside the body, alongside where the sink is resolved:

```python
        # EmptySource, never StdinSource. A default that read a terminal
        # would hang any caller that forgot to pass one -- including
        # operator/validate.py's dry run, which executes untrusted
        # candidate programs inside a server request.
        self._source = EmptySource() if source is None else source
```

- [ ] **Step 4: Evaluate `JackIn`**

In `_evaluate`, immediately after the `Name` branch and before the `Unary` branch:

```python
        if isinstance(expr, JackIn):
            line = self._source.next_line()
            if line is None:
                raise RuntimeErrorML(
                    "no input left to read", expr.line, expr.column
                )
            return line
```

- [ ] **Step 5: Evaluate `decode`**

In `_evaluate`'s `Unary` branch, after the `LENGTH` case and before the unary-minus fallthrough:

```python
            if expr.op is TokenType.DECODE:
                if not is_str(operand):
                    raise RuntimeErrorML(
                        f"'decode' takes text, got {type_name(operand)}",
                        expr.line,
                        expr.column,
                    )
                try:
                    return int(operand)
                except ValueError:
                    # int() already tolerates surrounding whitespace and a
                    # leading sign, and rejects "5.5" -- the language has
                    # integers only.
                    raise RuntimeErrorML(
                        f"'decode' needs a whole number, got \"{operand}\"",
                        expr.line,
                        expr.column,
                    ) from None
```

Confirm `is_str` and `type_name` are already imported from `matrixlang.values` in this file; the `LENGTH` branch above uses both, so they are.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `PYTHONPATH="$PWD/src" python3 -m pytest tests/test_interpreter.py -q`
Expected: PASS.

- [ ] **Step 7: Run the full suite**

Run: `PYTHONPATH="$PWD/src" python3 -m pytest -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/matrixlang/interpreter.py tests/test_interpreter.py
git commit -m "feat: evaluate jackin and decode"
```

---

### Task 5: Rendering both faces, and the round-trip

**Files:**
- Modify: `src/matrixlang/render.py`
- Modify: `tests/test_render.py`

**Interfaces:**
- Consumes: `nodes.JackIn`, `TokenType.DECODE` (Tasks 2–3); `GLYPHS["jackin"]`, `GLYPHS["decode"]` (Task 2).
- Produces: nothing later tasks import. This closes D-03 for the new keywords.

**The rule that matters:** a word operator needs a separator or `decode x` renders as `decodex` and re-lexes as one identifier — a silent change of meaning, which is exactly what the round-trip criterion exists to catch. `length` already carries this comment; `decode` needs the same treatment.

- [ ] **Step 1: Write the failing render tests**

Append to `tests/test_render.py`:

```python
def test_both_faces_round_trip_a_program_using_input():
    # D-03: parse(lex(render_X(t))) == t, for both faces. A word operator
    # rendered without a separator would re-lex as one identifier, which
    # is precisely what this catches.
    source = "construct n = decode jackin + 1\ntrace n\n"
    tree = parse(lex(source))
    for render in (render_ascii, render_glyph):
        assert parse(lex(render(tree))) == tree, f"{render.__name__} did not round-trip"


def test_the_ascii_face_spells_the_keywords_out():
    tree = parse(lex("construct n = decode jackin\n"))
    rendered = render_ascii(tree)
    assert "decode jackin" in rendered


def test_the_glyph_face_uses_the_table_not_the_words():
    from matrixlang.glyphs import GLYPHS

    tree = parse(lex("construct n = decode jackin\n"))
    rendered = render_glyph(tree)
    assert GLYPHS["decode"] in rendered
    assert GLYPHS["jackin"] in rendered
    assert "decode" not in rendered
    assert "jackin" not in rendered
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH="$PWD/src" python3 -m pytest tests/test_render.py -q -k "input or keywords_out or table_not_the_words"`
Expected: FAIL — an unhandled `JackIn` node, or `decode` rendered without a separator.

- [ ] **Step 3: Register `decode` in the operator table**

In `src/matrixlang/render.py`, add to `_OPS` beside `LENGTH`:

```python
    TokenType.LENGTH: "length",
    TokenType.DECODE: "decode",
    TokenType.UNPLUG: "unplug",
```

- [ ] **Step 4: Render `decode` with its separator**

In `_expression`'s `Unary` branch, change the `LENGTH` special case to cover both word unaries:

```python
        if expr.op in (TokenType.LENGTH, TokenType.DECODE):
            # A word operator needs a separator or `length xs` renders as
            # `lengthxs` and re-lexes as one identifier — a silent change
            # of meaning, which is exactly what §4.3 exists to catch.
            # `decode` is the same shape and shares the rule.
            return _map(face, _OPS[expr.op]) + " " + operand, _UNARY_LEVEL
```

- [ ] **Step 5: Render `JackIn` as an atom**

Add `JackIn` to `render.py`'s imports from `matrixlang.nodes`, then in `_expression`, beside the `Name` case:

```python
    if isinstance(expr, JackIn):
        # An atom: no operand, so nothing can need parenthesising around it.
        return _map(face, "jackin"), _ATOM_LEVEL
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `PYTHONPATH="$PWD/src" python3 -m pytest tests/test_render.py -q`
Expected: PASS.

- [ ] **Step 7: Run the full suite**

Run: `PYTHONPATH="$PWD/src" python3 -m pytest -q`
Expected: PASS. Any property-based round-trip test that generates trees now covers the new nodes if its generator includes them; if it does not, that is fine — the explicit test above covers D-03 for these keywords.

- [ ] **Step 8: Commit**

```bash
git add src/matrixlang/render.py tests/test_render.py
git commit -m "feat: render jackin and decode in both faces"
```

---

### Task 6: The CLI, the REPL, and the validate gate

**Files:**
- Modify: `src/matrixlang/cli.py`
- Modify: `src/matrixlang/repl.py`
- Modify: `src/matrixlang/operator/validate.py`
- Modify: `tests/test_cli.py`
- Modify: `tests/test_operator_validate.py`

**Interfaces:**
- Consumes: `matrixlang.input.StdinSource`, `matrixlang.input.ConstantSource` (Task 1); `Interpreter(..., source=...)` (Task 4).
- Produces: nothing later tasks import.

**The one that matters:** `operator/prompt.py` builds Operator's prompt from `tokens.KEYWORDS`, so from Task 2 onward Operator writes programs using `jackin`. Without a canned source in `check()`, every one of them fails its dry run and is rejected — and it looks like the model got worse, not like a plumbing bug.

- [ ] **Step 1: Write the failing validate-gate test**

Append to `tests/test_operator_validate.py` (if the file has a different name, use the one that tests `operator/validate.py`):

```python
def test_a_program_that_reads_input_still_validates():
    # operator/prompt.py builds the prompt from tokens.KEYWORDS, so
    # Operator writes `jackin` programs the moment the keyword exists. With
    # no input, the dry run would raise "no input left to read" and reject
    # every one of them -- a plumbing failure that would read as a model
    # failure. check() supplies a canned source instead.
    outcome = check("construct name = jackin\ntrace name\n")
    assert isinstance(outcome, Valid), outcome.as_diagnostic()


def test_a_program_that_decodes_input_still_validates():
    outcome = check("construct n = decode jackin\ntrace n + 1\n")
    assert isinstance(outcome, Valid), outcome.as_diagnostic()


def test_a_loop_reading_input_forever_is_still_bounded():
    # The canned source never runs out, so the step limit is what stops
    # this -- exactly as it stops any other infinite loop.
    outcome = check("dejavu true\n  trace jackin\nflatline\n", max_steps=200)
    assert not isinstance(outcome, Valid)
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_operator_validate.py -q -k "reads_input or decodes_input or reading_input_forever"`
Expected: FAIL — the first two report `no input left to read`.

- [ ] **Step 3: Give the dry run a canned source**

In `src/matrixlang/operator/validate.py`, add the import:

```python
from matrixlang.input import ConstantSource
```

and change the dry-run construction:

```python
        # A canned source, not EmptySource. A dry run answers "does this
        # parse and execute without crashing", not "what does this print",
        # so immediate exhaustion would reject correct programs for lacking
        # input the gate never had. "1" is both valid text and decodes
        # cleanly, so it exercises `jackin` and `decode jackin` alike, and
        # max_steps still bounds a program that loops reading forever.
        Interpreter(
            out=io.StringIO(), max_steps=max_steps, source=ConstantSource("1")
        ).run(program)
```

- [ ] **Step 4: Run the validate tests**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_operator_validate.py -q`
Expected: PASS.

- [ ] **Step 5: Write the failing CLI test**

Append to `tests/test_cli.py`, following that file's existing pattern for invoking the CLI and capturing output. If it invokes `main(argv)` directly, monkeypatch stdin:

```python
def test_run_reads_input_from_stdin(tmp_path, monkeypatch, capsys):
    import io

    program = tmp_path / "greet.rain"
    program.write_text('construct name = jackin\ntrace "Hello, " + name\n')
    monkeypatch.setattr("sys.stdin", io.StringIO("Neo\n"))

    exit_code = main(["run", str(program)])

    assert exit_code == 0
    assert capsys.readouterr().out.splitlines() == ["Hello, Neo"]
```

- [ ] **Step 6: Run it to verify it fails**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_cli.py -q -k reads_input_from_stdin`
Expected: FAIL with `no input left to read`.

- [ ] **Step 7: Wire `StdinSource` into the CLI and the REPL**

In `src/matrixlang/cli.py`, add `from matrixlang.input import StdinSource` and pass it at both construction sites:

```python
        Interpreter(
            sink=TextDisplay(sys.stdout), max_steps=max_steps, source=StdinSource()
        ).run(tree)
```

```python
            Interpreter(
                sink=window, max_steps=max_steps, source=StdinSource()
            ).run(tree)
```

In `src/matrixlang/repl.py`, add `from matrixlang.input import StdinSource` and:

```python
        # Shares stdin with the prompt: a `jackin` during execution consumes
        # the next line typed. At a terminal that is exactly right. Piping a
        # script into the REPL interleaves program input with program source,
        # which is a documented sharp edge rather than something special-cased
        # -- branching language behaviour on whether stdin is a TTY would be
        # worse than the edge.
        self.interpreter = Interpreter(out=self._out, source=StdinSource())
```

- [ ] **Step 8: Run the CLI tests, then the full suite**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_cli.py -q`
Expected: PASS.

Run: `PYTHONPATH="$PWD/src" python3 -m pytest -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add src/matrixlang/cli.py src/matrixlang/repl.py src/matrixlang/operator/validate.py tests/test_cli.py tests/test_operator_validate.py
git commit -m "feat: wire input into the CLI, the REPL, and the validate gate"
```

---

### Task 7: The browser — `glue.py` and the input box

**Files:**
- Modify: `site/glue.py`
- Modify: `tests/test_site_glue.py`
- Modify: `site/index.html`
- Modify: `site/style.css`
- Modify: `site/playground.js`
- Modify: `site/tests/dom.mjs`
- Modify: `site/tests/playground.test.mjs`

**Interfaces:**
- Consumes: `matrixlang.input.BufferSource` (Task 1); `Interpreter(..., source=...)` (Task 4).
- Produces: `glue.run(source: str, stdin: str = "", max_steps: int = BROWSER_MAX_STEPS) -> list[dict]`; a `#program-input` textarea in the page.

- [ ] **Step 1: Write the failing `glue` tests**

Append to `tests/test_site_glue.py`:

```python
def test_run_reads_supplied_input():
    events = glue.run('construct name = jackin\ntrace "Hello, " + name\n', stdin="Neo\n")
    outputs = [e for e in events if e["kind"] == "output"]
    assert [o["text"] for o in outputs] == ["Hello, Neo"]


def test_run_without_input_reports_the_shortfall_rather_than_raising():
    # Never raises -- the JS side walks one list and has no error path.
    events = glue.run("trace jackin\n")
    assert events[-1]["kind"] == "error"
    assert "no input left to read" in events[-1]["message"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_site_glue.py -q -k "supplied_input or shortfall"`
Expected: FAIL — `run() got an unexpected keyword argument 'stdin'`.

- [ ] **Step 3: Add `stdin` to `glue.run`**

In `site/glue.py`, add `from matrixlang.input import BufferSource` to the imports and change `run`:

```python
def run(
    source: str, stdin: str = "", max_steps: int = BROWSER_MAX_STEPS
) -> list[dict]:
    """Execute `source`, returning every event in wire shape. Never raises.

    A failure is the last event rather than an exception, so the JS side
    has one list to walk and no error path of its own.

    `stdin` is whatever the reader typed into the input box, supplied up
    front. The browser cannot block -- JavaScript is single-threaded, so a
    read that waited would freeze the tab and the cascade drawing in it --
    so input is buffered rather than prompted for.
    """
```

and change the execution line to pass the source:

```python
        Interpreter(
            sink=sink, max_steps=max_steps, source=BufferSource(stdin)
        ).run(program)
```

- [ ] **Step 4: Run the `glue` tests, then the site checks**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_site_glue.py -q`
Expected: PASS.

Run: `python3 site/checks/no_semantics.py && python3 site/checks/key_handling.py`
Expected: both print their success line, unmodified.

- [ ] **Step 5: Add the input box to the page**

In `site/index.html`, inside `.editor-pane`, between the `#editor-glyph` `<pre>` and the `#run` button:

```html
        <label for="program-input">Input (one line per <code>jackin</code>)</label>
        <textarea id="program-input" rows="3" spellcheck="false"
                  placeholder="Refactoring"></textarea>
```

- [ ] **Step 6: Style it**

In `site/style.css`, in the playground section after the `#miss` rule:

```css
/* The input box. Deliberately short: it is supplied up front rather than
   prompted for, because the browser cannot block on a read without
   freezing the tab and the cascade with it. */
#program-input {
  min-height: 3.5rem;
}
```

- [ ] **Step 7: Write the failing JS test**

In `site/tests/dom.mjs`, add to `INITIAL` after `"editor-glyph"`:

```javascript
  "program-input": {},
```

In `site/tests/playground.test.mjs`, append:

```javascript
test("running passes the input box's contents to the Python half", () => {
  const page = loadPlayground();
  let seen = null;
  page.setGlue({
    run: (source, stdin) => {
      seen = { source, stdin };
      return [];
    },
  });

  page.el("editor").value = "trace jackin";
  page.el("program-input").value = "Neo";
  page.el("run").click();

  assert.equal(seen.stdin, "Neo", "the input box never reached glue.run");
});
```

- [ ] **Step 8: Run it to verify it fails**

Run: `node --test site/tests/playground.test.mjs`
Expected: FAIL — `seen.stdin` is `undefined`, because `runProgram` passes only the source.

- [ ] **Step 9: Pass the input box through**

In `site/playground.js`, change `runProgram`'s first line:

```javascript
function runProgram() {
  const events = glue
    .run(el("editor").value, el("program-input").value)
    .toJs({ dict_converter: Object.fromEntries });
```

Also add `"program-input"` to the disabled-controls list, so a failed boot leaves it dead like every other control. In the `GATED_CONTROL_IDS` array (or the equivalent id list in `boot()`'s failure branch and success branch), add `"program-input"`.

- [ ] **Step 10: Run the JS suite and the site checks**

Run: `node --test site/tests/*.test.mjs`
Expected: PASS, including `index-html.test.mjs`'s drift checks for the new id.

Run: `python3 site/checks/no_semantics.py && python3 site/checks/key_handling.py`
Expected: both pass, unmodified — the browser gains no language logic and no persistence sink.

- [ ] **Step 11: Commit**

```bash
git add site/glue.py site/index.html site/style.css site/playground.js site/tests/dom.mjs site/tests/playground.test.mjs tests/test_site_glue.py
git commit -m "feat: give the playground an input box"
```

---

### Task 8: Documentation and full verification

**Files:**
- Modify: `docs/LEARNING-MATRIXLANG.md`

**Interfaces:**
- Consumes: everything above.
- Produces: nothing.

- [ ] **Step 1: Document both keywords**

In `docs/LEARNING-MATRIXLANG.md`, add the new section as **§17, immediately before the `## What the language does not have` section**. Do **not** insert it after §8 and renumber: the document runs to §16, other sections cite each other by number (the "does not have" list cites §7), and renumbering eight headings plus their cross-references is a large, error-prone edit for no reader benefit.

Match the file's existing voice — every example in that document is executed before it ships, so run each one and paste its real output.

```markdown
## 17. Input — `jackin` and `decode`

`jackin` reads one line and gives you the text of it.

```
construct name = jackin
trace "Hello, " + name
```

```
$ echo "Neo" | matrixlang run greet.rain
Hello, Neo
```

It is always text, never a number, even when the line looks like one. That
is deliberate: a value whose type depended on what somebody typed would send
the same program down different branches on different runs.

So `decode` turns text into a number when you want one:

```
construct n = decode jackin
trace n + 1
```

```
$ echo "41" | matrixlang run add.rain
42
```

`decode` is strict. It refuses text that is not a whole number, refuses a
decimal point (this language has integers only), and refuses a value that is
already a number — the same way `splice` refuses anything that is not a
boolean rather than guessing what you meant.

### `decode` binds tighter than arithmetic

`decode jackin + 1` means `(decode jackin) + 1`, not `decode (jackin + 1)`.
This is the same level `length` sits at, and for the same reason: both
produce a number that the arithmetic around them then consumes.

Note that `unplug` goes the other way — `unplug n == 1` means
`unplug (n == 1)`. The two are not inconsistent by accident. `unplug`
*consumes* a boolean that comparison *produces*, so it has to reach across
the comparison; `decode` *produces* a number that arithmetic *consumes*, so
reaching across the `+` would only ever produce an error.

### Running out of input

Asking for a line that is not there stops the program:

```
matrixlang: [line 3, column 17] no input left to read
```

Not an empty string. A loop reading input would otherwise spin forever on
blanks while the real mistake stayed invisible.

### Where input comes from

At the terminal, `jackin` reads what you type, and `echo "Neo" | matrixlang
run greet.rain` works the way you would expect. In the browser it reads the
input box beside the editor, one line per `jackin`, supplied before you press
Run — a web page cannot stop and wait for you without freezing the tab.
```

- [ ] **Step 2: Correct the "what the language does not have" list**

This is the step most likely to be skipped, and skipping it leaves the
document contradicting itself in the one section readers trust most.
`## What the language does not have` currently says:

```
- no input — a program's only channel out is `trace`
```

That becomes false with this change. Replace that single bullet with:

```
- no way to *prompt* for input and wait — `jackin` (§17) reads lines that
  were already supplied, from the terminal or from the box beside the
  editor, and a program cannot stop mid-run to ask a question
```

Leave every other bullet alone. In particular **do not** touch "no file or
network access" or the paragraph after the list explaining that this is a
property rather than an omission — input from a supplied buffer does not
give a `.rain` file access to your filesystem, your network, or Python, so
that claim still holds exactly as written.

- [ ] **Step 3: Verify every documented example actually runs**

Write each example to a scratch `.rain` file and run it with the input shown, confirming the output matches what the document claims. This document's standing promise is that every example was executed before it shipped.

Run: `PYTHONPATH="$PWD/src" python3 -m matrixlang run <scratch file>` with the input piped in.
Expected: output identical to the fenced blocks above.

- [ ] **Step 4: Run the full Python suite**

Run: `PYTHONPATH="$PWD/src" python3 -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Run the full JS suite**

Run: `node --test site/tests/*.test.mjs`
Expected: PASS.

- [ ] **Step 6: Run both site checks**

Run: `python3 site/checks/no_semantics.py && python3 site/checks/key_handling.py`
Expected: both print their success line, unmodified.

- [ ] **Step 7: Check the motivating program end to end**

The program that started this. Write it to a scratch file:

```
construct books = ["Clean Code", "Refactoring", "Design Patterns", "The Pragmatic Programmer"]
construct target = jackin

agent find_item(shelf, wanted)
  construct n = 0
  dejavu n < length shelf
    redpill shelf[n] == wanted
      jackout "Found: " + wanted
    flatline
    n = n + 1
  flatline
  jackout "not found"
flatline

trace find_item(books, target)
```

Run: `echo "Refactoring" | PYTHONPATH="$PWD/src" python3 -m matrixlang run <scratch file>`
Expected: `Found: Refactoring`. Then run it with `echo "Moby Dick"` and expect `not found`.

- [ ] **Step 8: Verify it in the real browser**

Assemble and serve the site the way `.github/workflows/pages.yml` does, then check the input box works end to end — boot the interpreter, type `Refactoring` into the input box, run the book program in the editor, and confirm the cascade shows `Found: Refactoring`.

```bash
python3 -m build --wheel --outdir dist/
mkdir -p /tmp/ml-site && cp site/index.html site/style.css site/layout.js site/intro.js site/tabs.js site/playground.js site/glue.py site/examples.json site/intro.json /tmp/ml-site/
cp -R site/fonts /tmp/ml-site/fonts && cp web-ui/cascade.js server/sse.py dist/*.whl /tmp/ml-site/
cd /tmp/ml-site && python3 -m http.server 8123
```

Report what was checked and any deviation. This step is what confirms the feature works, not just that unit tests pass against stubs.

- [ ] **Step 9: Commit and open the PR**

```bash
git add docs/LEARNING-MATRIXLANG.md
git commit -m "docs: document jackin and decode"
git push -u origin <branch>
```

Open the PR with `gh pr create --body-file <prepared file>` rather than an inline `--body`, so code spans and backticks survive. Reference #108; do **not** write "Closes #108" in any commit message before the feature actually lands, or the issue closes on the first merge.
