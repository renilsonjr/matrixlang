# Dictionaries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give MatrixLang a dictionary type — `{"id": 1}` literals, bracket lookup and assignment, `keymaker` for the key list, and `oracle` as an infix membership test — so data stops living in parallel lists kept in step by hand.

**Architecture:** A dictionary is a Python `dict` at runtime, exactly as a MatrixLang list is a Python `list`. The existing `Index` and `IndexAssign` nodes already cover `d["k"]` and `d["k"] = v`, so the parser gains only a literal and two keyword operators. The work spreads thinly across every layer — tokens, glyph table, lexer, parser, values, interpreter, render, treegen — which is why the tasks are cut by layer rather than by feature.

**Tech Stack:** Python 3.11+ stdlib, pytest. No new dependencies, no build step.

## Global Constraints

- **Keys are strings or integers only.** Booleans, lists and dictionaries are rejected with a positioned `RuntimeErrorML`.
- **Insertion order is guaranteed**, and pinned by a test that says what breaks if it fails.
- **A missing key is an error, never a null.** `NOTHING` must not leak into a user-visible position.
- **Equality is order-independent** and must NOT delegate to Python's `dict.__eq__` — see Task 3 for why.
- **Type name is `dictionary`**, joining integer, string, boolean, list, agent in `type_name`.
- **One line, no trailing comma** — dictionary literals inherit the rule list literals already follow.
- **`keymaker`** is prefix at the `_unary` rung beside `length`. **`oracle`** is infix at the `_comparison` rung beside `<`, `>`, `<=`, `>=`.
- **Glyph budget: 12 free before, 7 after.** `tests/test_glyphs.py` tracks this by hand on purpose; its ledger comment gains `12 → 7` and its slot count goes 44 → 49.
- **D-03:** both faces must satisfy `parse(lex(render_X(t))) == t`.
- **Every new node type must enter `tests/treegen.py` in the same change that adds it.** This has already bitten once — see Task 6.
- Run tests from the repo root: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest -q`. Use `python3`, not `python`. The full suite is ~1550 tests and takes 10–140s depending on machine load.
- Commit messages: conventional-commit subjects. **Never write "Closes #121"** in a commit message — the issue must not auto-close before the feature lands.

## File Structure

| Path | Change |
| --- | --- |
| `src/matrixlang/tokens.py` | 5 new `TokenType` members; `keymaker` and `oracle` in `KEYWORDS` |
| `src/matrixlang/glyphs.py` | 5 new table entries |
| `src/matrixlang/lexer.py` | `{`, `}`, `:` in `_SINGLE` |
| `src/matrixlang/nodes.py` | `DictLiteral` |
| `src/matrixlang/parser.py` | dict literal in `_primary`; `KEYMAKER` in `_unary`; `ORACLE` in `_COMPARISON_OPS` |
| `src/matrixlang/values.py` | `is_dict`, `type_name`, `_display`, `_equal`, `check_key` |
| `src/matrixlang/interpreter.py` | `DictLiteral` eval; dict cases in `Index`, `IndexAssign`, `LENGTH`; `KEYMAKER`; `ORACLE` |
| `src/matrixlang/render.py` | `DictLiteral` in both faces; `_OPS` entries |
| `tests/treegen.py` | `gen_dict`; `KEYMAKER` in the unary list; `ORACLE` in `_BINARY_OPS` |
| `docs/LEARNING-MATRIXLANG.md` | a dictionaries section |

### Where the tests go

**Follow the `test_lists_*.py` convention, not the generic files.** Lists — the
feature dictionaries most resembles — are tested in four files split by stage:

```
tests/test_lists_lex.py    tests/test_lists_parse.py
tests/test_lists_render.py tests/test_lists_run.py
```

Dictionaries get the matching four: `tests/test_dicts_lex.py`,
`test_dicts_parse.py`, `test_dicts_render.py`, `test_dicts_run.py`. Do **not**
append to `test_lexer.py` / `test_parser.py` / `test_render.py` /
`test_interpreter.py`; those hold the core-language cases, and a feature of this
size has its own files here by established practice.

The one exception is Task 3, which extends `tests/test_values.py` — that file is
about the value model itself rather than about any one feature.

Each of the four new files opens with a one-line docstring naming the stage,
and `test_dicts_run.py` carries its own helpers copied from
`tests/test_lists_run.py:13-22` verbatim:

```python
"""Dictionaries — running dictionary programs end to end."""

import io

import pytest

from matrixlang.errors import RuntimeErrorML
from matrixlang.interpreter import Interpreter
from matrixlang.lexer import lex
from matrixlang.parser import parse


def run(source):
    out = io.StringIO()
    Interpreter(out=out).run(parse(lex(source)))
    return out.getvalue()


def fails(source):
    with pytest.raises(RuntimeErrorML) as caught:
        run(source)
    return caught.value
```

Note `run` returns the **raw captured string including trailing newlines**, not
a list of lines. Every assertion below is written against that.

---

### Task 1: Tokens, glyph table, lexer

**Files:**
- Modify: `src/matrixlang/tokens.py`
- Modify: `src/matrixlang/glyphs.py`
- Modify: `src/matrixlang/lexer.py:10-25` (`_SINGLE`)
- Create: `tests/test_dicts_lex.py`
- Test: `tests/test_glyphs.py`

**Interfaces:**
- Produces: `TokenType.LBRACE`, `TokenType.RBRACE`, `TokenType.COLON`, `TokenType.KEYMAKER`, `TokenType.ORACLE`. Keyword spellings `"keymaker"` and `"oracle"`. Glyphs `{`→`ﾐ`, `}`→`ﾑ`, `:`→`ﾓ`, `keymaker`→`ﾔ`, `oracle`→`ｵ`.

**Why these glyphs.** `ﾐ`/`ﾑ` are adjacent in the half-width block (U+FF90, U+FF91), mirroring the existing convention that `[`/`]` and `(`/`)` are adjacent pairs. `ｵ` is the katakana "o", a real mnemonic for **o**racle, in the spirit of `ｲ` for jack**i**n. `ﾓ` and `ﾔ` are arbitrary, which the table's own docstring says is normal.

- [ ] **Step 1: Write the failing lexer test**

Create `tests/test_dicts_lex.py`, opening with the imports
`tests/test_lists_lex.py` uses:

```python
"""Dictionaries — lexing braces, colons, keymaker and oracle."""

from matrixlang.lexer import lex
from matrixlang.tokens import TokenType


def test_dictionary_punctuation_lexes():
    types = [t.type for t in lex('{"a": 1}\n')]
    assert types[:6] == [
        TokenType.LBRACE,
        TokenType.STRING,
        TokenType.COLON,
        TokenType.NUMBER,
        TokenType.RBRACE,
        TokenType.NEWLINE,
    ]


def test_keymaker_and_oracle_are_keywords():
    types = [t.type for t in lex("keymaker oracle\n")]
    assert types[:2] == [TokenType.KEYMAKER, TokenType.ORACLE]


def test_keymaker_and_oracle_lex_in_the_glyph_face():
    # The glyph face must lex to the same tokens as the ASCII face, or
    # D-03's round-trip claim is false for these two keywords.
    types = [t.type for t in lex("ﾔ ｵ\n")]
    assert types[:2] == [TokenType.KEYMAKER, TokenType.ORACLE]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_dicts_lex.py -q`
Expected: FAIL with `AttributeError: LBRACE` — the token types do not exist yet.

- [ ] **Step 3: Add the token types**

In `src/matrixlang/tokens.py`, add to the Keywords group of `TokenType`, after `ENCODE`:

```python
    KEYMAKER = auto()
    ORACLE = auto()
```

and to the Punctuation group, after `RBRACKET`:

```python
    LBRACE = auto()
    RBRACE = auto()
    COLON = auto()
```

and to `KEYWORDS`, after `"encode"`:

```python
    "keymaker": TokenType.KEYMAKER,
    "oracle": TokenType.ORACLE,
```

- [ ] **Step 4: Add the glyph entries**

In `src/matrixlang/glyphs.py`, after the `encode` entry:

```python
    # Dictionaries. `oracle` takes ｵ for the "o" it starts with, the same
    # kind of mnemonic as ｲ for jackin. `keymaker` takes ﾔ arbitrarily --
    # the Keymaker's own sounds were long gone by this point in the table.
    "keymaker": "ﾔ",
    "oracle": "ｵ",
```

and after the `"]"` entry:

```python
    # Adjacent, for the same reason ( ) and [ ] are adjacent.
    "{": "ﾐ",
    "}": "ﾑ",
    ":": "ﾓ",
```

- [ ] **Step 5: Add the punctuation to the lexer**

In `src/matrixlang/lexer.py`, add to `_SINGLE` after the `"]"` entry:

```python
    "{": TokenType.LBRACE,
    "}": TokenType.RBRACE,
    ":": TokenType.COLON,
```

`_GLYPH_TOKENS` is built from `_SINGLE` and `KEYWORDS` at import time, so the glyph face needs no separate change.

- [ ] **Step 6: Run the lexer tests**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_dicts_lex.py -q`
Expected: PASS.

- [ ] **Step 7: Update the hand-tracked glyph budget**

`tests/test_glyphs.py` asserts the slot count and the free count as literals, on purpose — spending budget is a decision someone writes down. Update `test_the_table_covers_exactly_the_44_slots`: rename it to `test_the_table_covers_exactly_the_49_slots`, add `| {"{", "}", ":"}` to `expected`, and change `assert len(expected) == 44` to `49`. The comment above it gains a sentence:

```python
    # + dictionaries: keymaker and oracle, and { } : for the literal.
```

In `test_the_glyph_budget_is_tracked_not_discovered`, extend the ledger comment and the assertion:

```python
    # ... encode spends 1: 13 - 1 = 12 left. Dictionaries spend 5 --
    # keymaker, oracle, and the three punctuation slots { } : -- so
    # 12 - 5 = 7 left. Finite, and worth knowing.
    assert free == 7
```

- [ ] **Step 8: Run the glyph tests**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_glyphs.py -q`
Expected: PASS, including `test_the_mapping_is_bijective` — if a chosen glyph collided with an existing one, that test is what catches it.

- [ ] **Step 9: Commit**

```bash
git add src/matrixlang/tokens.py src/matrixlang/glyphs.py src/matrixlang/lexer.py tests/test_dicts_lex.py tests/test_glyphs.py
git commit -m "feat: lex dictionary punctuation, keymaker and oracle"
```

---

### Task 2: The `DictLiteral` node and the parser

**Files:**
- Modify: `src/matrixlang/nodes.py:82-96` (beside `ListLiteral`)
- Modify: `src/matrixlang/parser.py` — `_primary` (~line 507), `_unary` (~line 437), `_COMPARISON_OPS`
- Create: `tests/test_dicts_parse.py`

**Interfaces:**
- Consumes: `TokenType.LBRACE`, `RBRACE`, `COLON`, `KEYMAKER`, `ORACLE` from Task 1.
- Produces: `DictLiteral(entries: list[tuple[Expr, Expr]])`, a dataclass `Expr` with the standard `line`/`column`. `keymaker` parses to `Unary(TokenType.KEYMAKER, operand)`. `oracle` parses to `Binary(left, TokenType.ORACLE, right)`.

**Why `entries` is a list of pairs, not a dict.** The AST must preserve what was *written*, including a duplicate key written twice, so that `parse(lex(render(t))) == t` holds. Collapsing to a Python dict at parse time would silently drop a duplicate and break D-03.

- [ ] **Step 1: Write the failing parser tests**

Create `tests/test_dicts_parse.py`. Mirror `tests/test_lists_parse.py:1-14` for the header — note it imports `ParseError` from `matrixlang.errors`, **not** `MatrixLangError`, and that is what the rejection tests below expect:

```python
def test_empty_dictionary_literal():
    program = parse(lex("construct d = {}\n"))
    assert program.statements[0].value == DictLiteral([])


def test_dictionary_literal_keeps_written_order():
    program = parse(lex('construct d = {"b": 1, "a": 2}\n'))
    entries = program.statements[0].value.entries
    assert [k.value for k, _ in entries] == ["b", "a"]


def test_dictionary_literal_keeps_a_duplicate_key():
    # The AST records what was written, not what it evaluates to. Folding
    # duplicates here would make render(parse(x)) lose a token and break
    # the D-03 round-trip property.
    program = parse(lex('construct d = {"a": 1, "a": 2}\n'))
    assert len(program.statements[0].value.entries) == 2


def test_dictionary_literal_rejects_a_trailing_comma():
    # Exactly how list literals behave; dictionaries inherit the rule.
    with pytest.raises(ParseError):
        parse(lex('construct d = {"a": 1,}\n'))


def test_dictionary_literal_rejects_a_newline_inside_braces():
    with pytest.raises(ParseError):
        parse(lex('construct d = {\n  "a": 1\n}\n'))


def test_keymaker_parses_like_length():
    program = parse(lex("trace keymaker d\n"))
    assert program.statements[0].value == Unary(TokenType.KEYMAKER, Name("d"))


def test_oracle_binds_tighter_than_unplug():
    # `unplug d oracle "k"` must mean `unplug (d oracle "k")`. The tight
    # reading is an error for every possible d.
    program = parse(lex('trace unplug d oracle "k"\n'))
    node = program.statements[0].value
    assert node.op is TokenType.UNPLUG
    assert node.operand.op is TokenType.ORACLE


def test_oracle_binds_tighter_than_splice():
    program = parse(lex('trace d oracle "k" splice e oracle "j"\n'))
    node = program.statements[0].value
    assert node.op is TokenType.SPLICE
    assert node.left.op is TokenType.ORACLE
    assert node.right.op is TokenType.ORACLE


def test_oracle_takes_a_full_term_on_the_right():
    # `_comparison` draws its operands from `_term`, so the concatenation
    # is the key rather than `d oracle "gr"` then a dangling `+ "ade"`.
    program = parse(lex('trace d oracle "gr" + "ade"\n'))
    node = program.statements[0].value
    assert node.op is TokenType.ORACLE
    assert node.right.op is TokenType.PLUS


def test_oracle_is_looser_than_equality_is_not_true():
    # Comparison is TIGHTER than equality, so this groups as
    # `(d oracle "k") == true`.
    program = parse(lex('trace d oracle "k" == true\n'))
    node = program.statements[0].value
    assert node.op is TokenType.EQ
    assert node.left.op is TokenType.ORACLE
```

The node imports needed are `DictLiteral`, `Unary`, `Name`, plus `TokenType` from `matrixlang.tokens`.

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_dicts_parse.py -q`
Expected: FAIL with `ImportError` / `NameError` on `DictLiteral`.

- [ ] **Step 3: Add the node**

In `src/matrixlang/nodes.py`, after `ListLiteral`:

```python
@dataclass
class DictLiteral(Expr):
    """`{"a": 1}`. Entries are pairs rather than a dict so the AST records
    what was WRITTEN: a duplicate key written twice survives to render,
    which is what keeps D-03's round-trip property true. Each key and each
    value is its own precedence context, like ListLiteral.elements."""

    entries: list[tuple[Expr, Expr]]
```

- [ ] **Step 4: Parse the literal**

In `src/matrixlang/parser.py`, in `_primary`, immediately after the `LBRACKET` branch and before the closing `raise ParseError`:

```python
        if token.type is TokenType.LBRACE:
            self.advance()
            entries: list[tuple[Expr, Expr]] = []
            if not self.check(TokenType.RBRACE):
                while True:
                    key = self.expression()
                    self.expect(TokenType.COLON, "expected ':' after the key")
                    entries.append((key, self.expression()))
                    if not self.check(TokenType.COMMA):
                        break
                    self.advance()
            self.expect(TokenType.RBRACE, "expected '}' to close the dictionary")
            return DictLiteral(entries, line=token.line, column=token.column)
```

A trailing comma and a newline inside braces both fall out of this without extra code: after consuming the comma the loop calls `self.expression()`, which raises on `}` or on the newline token, exactly as the list branch does.

Add `DictLiteral` to the node imports at the top of `parser.py`.

- [ ] **Step 5: Add `keymaker` to `_unary`**

In `_unary`, add `TokenType.KEYMAKER` to the tuple of token types it accepts, beside `LENGTH`, `DECODE` and `ENCODE`. It belongs at this rung for the reason the existing comment gives: it PRODUCES a value that later operations consume, so `length keymaker d` and `keymaker alunos[0]` both group tightly.

- [ ] **Step 6: Add `oracle` to the comparison rung**

Add `TokenType.ORACLE` to `_COMPARISON_OPS`. That single change gives every row of the spec's precedence table, because `_not` and `_splice` already sit above `_comparison` and `_comparison` already draws its operands from `_term`.

- [ ] **Step 7: Run the parser tests**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_dicts_parse.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/matrixlang/nodes.py src/matrixlang/parser.py tests/test_dicts_parse.py
git commit -m "feat: parse dictionary literals, keymaker and oracle"
```

---

### Task 3: The dictionary value — `values.py`

**Files:**
- Modify: `src/matrixlang/values.py` — `is_dict` (new), `type_name:138`, `_display:167`, `_equal:214`, `check_key` (new)
- Test: `tests/test_values.py`

**Interfaces:**
- Consumes: nothing from earlier tasks — this task operates on Python `dict` objects built directly in its tests.
- Produces:
  - `is_dict(value) -> bool`
  - `type_name(value)` returns `"dictionary"` for a dict
  - `to_display` renders `{"a": 1, "b": "x"}` — keys always quoted when strings, values with the existing nested rules
  - `equal` compares dictionaries order-independently, recursively, cycle-safely
  - `check_key(key) -> None`, raising `BadKey(type_name)` — a position-less signal in the shape of `CyclicValue` and `Incomparable`, converted to a positioned `RuntimeErrorML` by the interpreter in Task 4

**Why equality cannot delegate to Python.** `_equal`'s docstring already records that `[1] == [true]` returned True before it recursed manually, because Python compares list elements with its own `==` where `1 == True`. A dictionary has the same hole twice over: `{"a": 1} == {"a": True}` is True in Python, and so is `{1: "x"} == {True: "x"}`. Rejecting boolean keys closes the second; the first needs the same manual recursion lists already get.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_values.py`:

```python
def test_a_dictionary_names_itself_dictionary():
    assert type_name({}) == "dictionary"


def test_a_dictionary_displays_with_quoted_string_keys():
    assert to_display({"a": 1, "b": "x"}) == '{"a": 1, "b": "x"}'


def test_a_dictionary_displays_integer_keys_unquoted():
    assert to_display({1: "x"}) == '{1: "x"}'


def test_an_empty_dictionary_displays_as_empty_braces():
    assert to_display({}) == "{}"


def test_a_self_containing_dictionary_raises_cyclic():
    d = {}
    d["self"] = d
    with pytest.raises(CyclicValue):
        to_display(d)


def test_dictionary_equality_ignores_order():
    assert equal({"a": 1, "b": 2}, {"b": 2, "a": 1})


def test_dictionary_equality_does_not_use_pythons_equals():
    # Python says {"a": 1} == {"a": True}. The language must not: 1 and
    # true are different types, and comparing them is an error at every
    # depth. This is the list bug -- [1] == [true] -- one level down.
    with pytest.raises(Incomparable):
        equal({"a": 1}, {"a": True})


def test_dictionaries_with_different_keys_are_unequal():
    assert not equal({"a": 1}, {"b": 1})


def test_dictionaries_of_different_size_are_unequal():
    assert not equal({"a": 1}, {"a": 1, "b": 2})


def test_two_mutually_referential_dictionaries_compare_without_recursing_forever():
    a, b = {}, {}
    a["x"], b["x"] = b, a
    assert equal(a, b)


def test_a_string_key_is_accepted():
    check_key("a")


def test_an_integer_key_is_accepted():
    check_key(1)


def test_a_boolean_key_is_rejected():
    # Not squeamishness. Python hashes True and 1 identically, so a
    # dictionary holding both would silently collapse to one entry --
    # two keys written, one given, and no diagnostic anywhere.
    with pytest.raises(BadKey):
        check_key(True)


def test_a_list_key_is_rejected():
    with pytest.raises(BadKey):
        check_key([1])


def test_a_dictionary_key_is_rejected():
    with pytest.raises(BadKey):
        check_key({})
```

Import `BadKey`, `check_key`, `is_dict` alongside the existing imports.

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_values.py -q -k "dictionar or key"`
Expected: FAIL with `ImportError` on `BadKey`.

- [ ] **Step 3: Add `BadKey` and `check_key`**

In `src/matrixlang/values.py`, beside `CyclicValue` and `Incomparable`:

```python
class BadKey(Exception):
    """A value was used as a dictionary key that cannot be one.

    Position-less, and converted to a MatrixLangError by the interpreter,
    for the same reason as CyclicValue and Incomparable: this module has
    no source positions and must not invent them.
    """

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name
```

and, after `is_list`:

```python
def is_dict(value: object) -> bool:
    return type(value) is dict


def check_key(key: object) -> None:
    """Refuse keys that cannot work, before one reaches a dictionary.

    Strings and integers only. Booleans are refused because CPython gives
    True and 1 the same hash and calls them equal, so `{true: "a", 1: "b"}`
    would collapse into one entry -- the reader writes two keys and gets
    one, with nothing to tell them. Lists and dictionaries are refused
    because they are mutable: a key that changes after insertion is a
    lookup that stops working for reasons invisible where it is written.
    """
    if is_bool(key) or not (is_str(key) or is_int(key)):
        raise BadKey(type_name(key))
```

**Correction, found in review:** an earlier draft of this step justified checking
`is_bool` first by saying Python's `bool` subclasses `int`, so `is_int(True)` is True.
That is true of Python but **false of this codebase** — `is_int` is `type(value) is int`
(`values.py:131`), which is already False for `True`. The ordering is therefore
harmless but not load-bearing, and the real reason to reject boolean keys is the hash
collision described in `check_key`'s docstring, not an ordering hazard. Do not
reproduce the subclass rationale in a comment.

- [ ] **Step 4: Add `dictionary` to `type_name`**

In `type_name`, after the `is_list` branch:

```python
    if is_dict(value):
        return "dictionary"
```

- [ ] **Step 5: Add display**

In `_display`, after the `is_list` branch:

```python
    if is_dict(value):
        if id(value) in seen:
            raise CyclicValue
        seen = seen | {id(value)}
        inner = ", ".join(
            f"{_display(k, True, seen)}: {_display(v, True, seen)}"
            for k, v in value.items()
        )
        return "{" + inner + "}"
```

Keys pass `nested=True` so a string key prints quoted — `{"a": 1}`, not `{a: 1}` — for exactly the reason the list branch quotes its elements: without quotes a reader cannot tell a string from a name.

- [ ] **Step 6: Add equality**

In `_equal`, replace the `if not is_list(left):` early return with a dictionary branch placed before it:

```python
    if is_dict(left):
        if len(left) != len(right):
            return False
        pair = (id(left), id(right))
        if pair in seen:
            return True
        seen.add(pair)
        for key, value in left.items():
            if key not in right:
                return False
            if not _equal(value, right[key], seen):
                return False
        return True
    if not is_list(left):
        ...
```

`key not in right` uses Python's own hashing, which is safe here precisely because `check_key` has already excluded booleans — the one type whose Python hashing would confuse two distinct MatrixLang values. The `seen` pair memo is the same mechanism lists use, and the long comment in the list branch explaining why it is not discarded applies unchanged.

- [ ] **Step 7: Run the tests**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_values.py -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add src/matrixlang/values.py tests/test_values.py
git commit -m "feat: dictionaries as values, with equality that refuses Python's"
```

---

### Task 4: The interpreter

**Files:**
- Modify: `src/matrixlang/interpreter.py`
- Create: `tests/test_dicts_run.py`

**Interfaces:**
- Consumes: `DictLiteral` (Task 2); `is_dict`, `check_key`, `BadKey`, `type_name` (Task 3).
- Produces: runtime dictionary behaviour. No new names other modules import.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_dicts_run.py` with the header and the `run`/`fails` helpers shown in **Where the tests go** above, then:

```python
def test_a_dictionary_literal_evaluates():
    assert run('construct d = {"a": 1}\ntrace d["a"]\n') == "1\n"


def test_lookup_of_a_missing_key_is_an_error():
    error = fails('construct d = {"a": 1}\ntrace d["b"]\n')
    assert 'no key "b" in this dictionary' in error.message


def test_assignment_inserts_a_new_key():
    assert run('construct d = {"a": 1}\nd["b"] = 2\ntrace d["b"]\n') == "2\n"


def test_assignment_updates_an_existing_key_without_moving_it():
    source = 'construct d = {"a": 1, "b": 2}\nd["a"] = 9\ntrace keymaker d\n'
    assert run(source) == '["a", "b"]\n'


def test_length_of_a_dictionary_is_its_entry_count():
    assert run('trace length {"a": 1, "b": 2}\n') == "2\n"


def test_keymaker_returns_keys_in_insertion_order():
    # Insertion order is a REQUIREMENT, not an accident of CPython. The
    # playground re-runs a program from the start when it needs input and
    # draws only the events it has not drawn yet, which is honest only
    # because a re-run reproduces the one before it exactly. A keymaker
    # whose order varied would make the second run diverge from the first
    # and the reader would watch their own output change underneath them.
    source = 'construct d = {"z": 1, "a": 2}\nd["m"] = 3\ntrace keymaker d\n'
    assert run(source) == '["z", "a", "m"]\n'


def test_oracle_finds_a_present_key():
    assert run('trace {"a": 1} oracle "a"\n') == "true\n"


def test_oracle_rejects_an_absent_key():
    assert run('trace {"a": 1} oracle "b"\n') == "false\n"


def test_a_boolean_key_is_refused_with_a_position():
    error = fails("construct d = {true: 1}\n")
    assert "boolean" in error.message
    assert error.line == 1


def test_a_list_key_is_refused():
    assert "list" in fails("construct d = {[1]: 2}\n").message


def test_a_key_assigned_later_is_also_checked():
    assert "boolean" in fails('construct d = {}\nd[true] = 1\n').message


def test_keymaker_of_a_non_dictionary_is_an_error():
    error = fails("trace keymaker [1, 2]\n")
    assert "'keymaker' takes a dictionary, got list" in error.message


def test_oracle_on_a_non_dictionary_is_an_error():
    error = fails('trace [1, 2] oracle "a"\n')
    assert "'oracle' takes a dictionary, got list" in error.message


def test_a_later_duplicate_key_wins():
    assert run('trace {"a": 1, "a": 2}["a"]\n') == "2\n"


def test_nested_dictionaries_index_through():
    source = 'construct xs = [{"g": "A"}, {"g": "B"}]\ntrace xs[1]["g"]\n'
    assert run(source) == "B\n"
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_dicts_run.py -q`
Expected: FAIL — `DictLiteral` reaches `_evaluate` with no branch for it.

- [ ] **Step 3: Evaluate the literal**

In `_evaluate`, beside the `ListLiteral` branch:

```python
        if isinstance(expr, DictLiteral):
            result: dict = {}
            for key_expr, value_expr in expr.entries:
                key = self._value_of(key_expr, expr)
                try:
                    check_key(key)
                except BadKey as bad:
                    raise RuntimeErrorML(
                        f"a dictionary key must be a string or a number, got {bad.name}",
                        key_expr.line, key_expr.column,
                    ) from None
                result[key] = self._value_of(value_expr, expr)
            return result
```

A later duplicate overwrites an earlier one, which is what `dict.__setitem__` does and what a reader expects; the insertion position of the first write is kept, which is also what CPython does.

- [ ] **Step 4: Lookup, assignment, and length**

In the `Index` evaluation, add a dictionary case before the existing list handling:

```python
            if is_dict(target):
                key = self._value_of(expr.index, expr)
                try:
                    check_key(key)
                except BadKey as bad:
                    raise RuntimeErrorML(
                        f"a dictionary key must be a string or a number, got {bad.name}",
                        expr.index.line, expr.index.column,
                    ) from None
                if key not in target:
                    raise RuntimeErrorML(
                        f"no key {_display_key(key)} in this dictionary",
                        expr.index.line, expr.index.column,
                    )
                return target[key]
```

Add the same key-check-and-set shape to `IndexAssign` (inserting rather than erroring when the key is absent), and add a dictionary case to the `LENGTH` branch returning `len(value)`.

`_display_key` is a two-line module-level helper in `interpreter.py`:

```python
def _display_key(key: object) -> str:
    """A key as it should read inside a diagnostic: strings quoted."""
    return to_display([key])[1:-1]
```

Reusing `to_display`'s nested rules through a one-element list is deliberate — it means the quoting and escaping in the error message can never drift from the quoting in `trace` output.

- [ ] **Step 5: `keymaker` and `oracle`**

In the unary evaluation, beside `LENGTH`:

```python
        if expr.op is TokenType.KEYMAKER:
            if not is_dict(operand):
                raise RuntimeErrorML(
                    f"'keymaker' takes a dictionary, got {type_name(operand)}",
                    expr.line, expr.column,
                )
            return list(operand.keys())
```

In the binary evaluation:

```python
        if expr.op is TokenType.ORACLE:
            if not is_dict(left):
                raise RuntimeErrorML(
                    f"'oracle' takes a dictionary, got {type_name(left)}",
                    expr.line, expr.column,
                )
            try:
                check_key(right)
            except BadKey as bad:
                raise RuntimeErrorML(
                    f"a dictionary key must be a string or a number, got {bad.name}",
                    expr.line, expr.column,
                ) from None
            return right in left
```

`list(operand.keys())` copies, so mutating the returned list cannot reach the dictionary.

- [ ] **Step 6: Run the tests**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_dicts_run.py -q`
Expected: PASS.

- [ ] **Step 7: Run the whole suite**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest -q`
Expected: PASS. A failure here most likely means an exhaustiveness guard elsewhere (`treeview.py`, `render.py`) now sees a node or operator it has no entry for — that is the guard doing its job, and Task 5 is where those entries land.

- [ ] **Step 8: Commit**

```bash
git add src/matrixlang/interpreter.py tests/test_dicts_run.py
git commit -m "feat: run dictionaries — lookup, assignment, keymaker, oracle"
```

---

### Task 5: Rendering both faces

**Files:**
- Modify: `src/matrixlang/render.py` — `_OPS:50`, `_expression:223`
- Modify: `src/matrixlang/treeview.py` if its `_OPS` parity test demands it
- Create: `tests/test_dicts_render.py`

**Interfaces:**
- Consumes: `DictLiteral` (Task 2), `TokenType.KEYMAKER`/`ORACLE` (Task 1).
- Produces: ASCII and glyph rendering for all three.

**Note on the parity test.** A test already asserts `set(treeview._OPS) == set(render._OPS)`. Adding operators to one and not the other fails it — which is the point. Expect to touch both.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_dicts_render.py`, importing `lex`, `parse`, `render_ascii` and `render_glyph`:

```python
def test_dictionary_literal_renders_ascii():
    source = 'construct d = {"a": 1, "b": 2}\n'
    assert render_ascii(parse(lex(source))) == source


def test_empty_dictionary_literal_renders_ascii():
    source = "construct d = {}\n"
    assert render_ascii(parse(lex(source))) == source


def test_keymaker_and_oracle_render_ascii():
    source = 'trace keymaker d\ntrace d oracle "a"\n'
    assert render_ascii(parse(lex(source))) == source


def test_dictionary_round_trips_through_the_glyph_face():
    program = parse(lex('construct d = {"a": 1}\ntrace d oracle "a"\n'))
    assert parse(lex(render_glyph(program))) == program


def test_a_dictionary_inside_a_list_renders():
    source = 'construct xs = [{"a": 1}, {"b": 2}]\n'
    assert render_ascii(parse(lex(source))) == source
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_dicts_render.py -q`
Expected: FAIL — `_expression` has no `DictLiteral` branch and `_OPS` has no `KEYMAKER`.

- [ ] **Step 3: Add the operator spellings**

In `render.py`'s `_OPS`, add `TokenType.KEYMAKER: "keymaker"` and `TokenType.ORACLE: "oracle"`. Mirror both into `treeview.py`'s `_OPS` so the parity test passes.

- [ ] **Step 4: Render the literal**

In `_expression`, beside the `ListLiteral` branch:

```python
    if isinstance(expr, DictLiteral):
        inner = ", ".join(
            f"{_expression(k, _ATOM_LEVEL, face)}: {_expression(v, _ATOM_LEVEL, face)}"
            for k, v in expr.entries
        )
        return (
            _map(face, "{") + inner + _map(face, "}"),
            _ATOM_LEVEL,
        )
```

Follow the `ListLiteral` branch's exact treatment of levels and `_map` rather than the sketch above if the two disagree — keys and values are their own precedence contexts, like `Call.args`, so neither needs parenthesising.

`keymaker` needs no new branch: it is a `Unary` and the existing unary branch already renders `_OPS[expr.op] + " " + operand`. `oracle` needs none either, for the same reason on the binary side.

- [ ] **Step 5: Run the render tests**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_dicts_render.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add src/matrixlang/render.py src/matrixlang/treeview.py tests/test_dicts_render.py
git commit -m "feat: render dictionaries in both faces"
```

---

### Task 6: `treegen` and the round-trip property

**Files:**
- Modify: `tests/treegen.py` — `_BINARY_OPS:67`, `gen_expression:148`, the unary list at ~line 181, a new `gen_dict`
- Test: the existing round-trip property test picks this up automatically

**Interfaces:**
- Consumes: `DictLiteral` (Task 2).
- Produces: dictionaries, `keymaker` and `oracle` in the 300-seed generated corpus.

**Why this task exists as its own gate.** The round-trip property only covers node shapes `treegen` actually generates. This has already gone wrong once in this repository: on the `encode` branch, `treegen`'s unary list was found generating three of the five unary operators, so `decode` and `encode` had been silently outside the property for as long as they had existed — the property was green and proving less than it claimed. Adding a node type without adding it here reproduces that exactly, and nothing fails to tell you.

- [ ] **Step 1: Add `oracle` to the binary operators**

```python
_BINARY_OPS = [
    TokenType.EQ, TokenType.NEQ,
    TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE,
    TokenType.PLUS, TokenType.MINUS, TokenType.STAR, TokenType.SLASH,
    TokenType.ORACLE,
]
```

- [ ] **Step 2: Add `keymaker` to the unary operators**

Add `TokenType.KEYMAKER` to the `rng.choice([...])` list beside `MINUS`, `LENGTH`, `UNPLUG`, `DECODE` and `ENCODE`. The comment above it already explains that nonsense operands are fine because the property never runs the tree.

- [ ] **Step 3: Add `gen_dict`**

Beside `gen_list`:

```python
def gen_dict(rng: random.Random, depth: int) -> DictLiteral:
    if depth <= 0 or rng.random() < 0.2:
        return DictLiteral([])
    return DictLiteral(
        [
            (gen_expression(rng, depth - 1), gen_expression(rng, depth - 1))
            for _ in range(rng.randint(1, 3))
        ]
    )
```

Keys are drawn from the full expression space rather than only string literals. The property under test is `parse(render(t)) == t`, which never evaluates the tree, so a key that could not be a real key at runtime is still a valid shape to render and re-parse — and it is the shape most likely to expose a precedence bug.

- [ ] **Step 4: Wire it into `gen_expression`**

The dispatch is a ladder of `if roll < N` bands. Insert a dictionary band beside the list band, widening the ladder rather than stealing from a neighbour — for example, change the `roll < 0.72` list band to also allow dictionaries:

```python
    if roll < 0.72:
        if rng.random() < 0.5:
            return gen_dict(rng, depth - 1)
        return gen_list(rng, depth - 1)
```

Import `DictLiteral` at the top of `treegen.py`.

- [ ] **Step 5: Prove the corpus actually contains the new shapes**

Do not assume the wiring worked. Run:

```bash
PYTHONPATH="$PWD/src:$PWD" python3 -c "
import random
from tests import treegen
from matrixlang.render import render_ascii
corpus = [render_ascii(treegen.gen_program(random.Random(s))) for s in range(300)]
for needle in ('{', 'keymaker', 'oracle'):
    hits = sum(1 for c in corpus if needle in c)
    print(f'{needle}: {hits}/300 programs')
"
```

Expected: all three well above zero. A zero here means the property is green while proving nothing about that shape — the exact failure this task exists to prevent. Paste the counts into your report.

- [ ] **Step 6: Run the property test**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest -q -k "round_trip or property"`
Expected: PASS across all 300 seeds, in both faces.

- [ ] **Step 7: Run the whole suite**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add tests/treegen.py
git commit -m "test: generate dictionaries, keymaker and oracle in the corpus"
```

---

### Task 7: The tutorial and an end-to-end program

**Files:**
- Modify: `docs/LEARNING-MATRIXLANG.md` — a new section after the lists section
- Modify: `tests/test_dicts_run.py` (the file created in Task 4)

**Interfaces:**
- Consumes: everything above.

- [ ] **Step 1: Write the end-to-end test**

This is the program that motivated the feature — a reader's Python, translated. Add it as a whole-program test:

```python
def test_the_students_search_program_runs():
    source = (
        'construct alunos = [{"id": 1, "grade": "A"}, {"id": 2, "grade": "B"}, '
        '{"id": 3, "grade": "A"}]\n'
        "agent find_students(alunos, busca)\n"
        "  construct encontrados = []\n"
        "  construct n = 0\n"
        "  dejavu n < length alunos\n"
        "    construct aluno = alunos[n]\n"
        '    redpill busca == encode aluno["id"] fork busca == aluno["grade"]\n'
        '      encontrados = encontrados + [aluno["id"]]\n'
        "    flatline\n"
        "    n = n + 1\n"
        "  flatline\n"
        "  jackout encontrados\n"
        "flatline\n"
        'trace find_students(alunos, "A")\n'
    )
    assert run(source) == "[1, 3]\n"
```

**Watch for one known quirk:** `construct` inside a loop body fails on the second iteration with "already declared". If `construct aluno = alunos[n]` inside the `dejavu` body hits that, index directly — `alunos[n]["grade"]` — rather than binding a name, and note it in your report.

- [ ] **Step 2: Run it**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest -q -k students`
Expected: PASS.

- [ ] **Step 3: Write the tutorial section**

Add a dictionaries section to `docs/LEARNING-MATRIXLANG.md`, after lists and before the section that follows them. Match the surrounding register exactly: short prose, a code block, its output in a second block. Cover the literal, lookup, insert and update, `length`, `keymaker`, `oracle`, and the one-line rule. State plainly that a missing key is an error and why there is no null to return instead.

Include the parallel-lists problem as the motivation, since that is what a reader coming from the lists section has just learned to do.

- [ ] **Step 4: Verify every tutorial snippet runs**

The tutorial's examples are prose, not tests, so they rot silently. Run each new snippet through the interpreter and confirm the output block matches what it actually prints:

```bash
PYTHONPATH="$PWD/src" python3 -c "
import sys
from matrixlang.cli import main
sys.argv = ['matrixlang', 'run', '/tmp/snippet.rain']
main()
"
```

- [ ] **Step 5: Run the whole suite**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add docs/LEARNING-MATRIXLANG.md tests/
git commit -m "docs: teach dictionaries, and run the program that asked for them"
```

---

## Self-review notes

**Spec coverage.** Literals (T2), lookup and assignment (T4), `keymaker` (T2/T4), `oracle` and its precedence table (T2), key restriction with the boolean rationale (T3/T4), insertion order with the determinism reason (T4), missing-key error (T4), order-independent equality (T3), `length` (T4), cycles (T3), glyph budget 12→7 and slot count 44→49 (T1), D-03 both faces (T5), the treegen trap (T6), the one-line rule (T2), tutorial and end-to-end (T7). Every "Testing" row in the spec maps to a task.

**Out of scope, per the spec** and absent from every task: deletion, iterating values directly, Scribe support, multi-line bracketed literals.

**Naming consistency check.** `DictLiteral.entries` is used identically in Tasks 2, 5 and 6. `check_key`/`BadKey`/`is_dict` are defined in Task 3 and consumed in Task 4 under those exact names. `_display_key` is defined and used only in Task 4.
