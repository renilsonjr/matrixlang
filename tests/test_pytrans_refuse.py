"""The translator's refusal machinery, and its promise never to raise."""

import ast
import io

import pytest

from matrixlang.errors import RuntimeErrorML
from matrixlang.interpreter import Interpreter
from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.pytrans import Refusals, Translated, translate
from matrixlang.pytrans.translate import _none_then_truth_test


def test_invalid_python_is_a_refusal_not_an_exception():
    result = translate("def (:\n")
    assert isinstance(result, Refusals)
    assert result.items[0].line == 1


def test_an_empty_program_translates_to_an_empty_program():
    result = translate("")
    assert isinstance(result, Translated)
    assert result.source == ""


def test_an_unsupported_statement_is_refused_with_its_line():
    result = translate("import os\n")
    assert isinstance(result, Refusals)
    assert result.items[0].line == 1
    assert "import" in result.items[0].reason


def test_every_refusal_is_collected_not_just_the_first():
    result = translate("import os\nimport sys\nclass A: pass\n")
    assert isinstance(result, Refusals)
    assert [r.line for r in result.items] == [1, 2, 3]


def test_refusals_are_in_line_order():
    result = translate("class A: pass\nimport os\n")
    assert [r.line for r in translate("class A: pass\nimport os\n").items] == [1, 2]


def test_a_refusal_names_an_idiom_when_one_exists():
    refusal = translate("xs = [f(x) for x in ys]\n").items[0]
    assert refusal.idiom is not None
    assert "dejavu" in refusal.idiom


def test_an_unsupported_statement_reports_itself_not_what_it_contains():
    # `class` is unsupported whatever is inside it. Naming the comprehension
    # would send the reader to rewrite working code and change nothing.
    refusal = translate("class A:\n    xs = [f(x) for x in ys]\n").items[0]
    assert "class" in refusal.reason
    assert refusal.line == 1


def test_a_try_statement_also_reports_itself_not_what_it_contains():
    refusal = translate("try:\n    xs = [f(x) for x in ys]\nexcept Exception:\n    pass\n").items[0]
    assert "try" in refusal.reason
    assert refusal.line == 1


def test_a_lone_surrogate_is_a_refusal_not_an_exception():
    # Exactly what a JS string with an unpaired surrogate becomes crossing
    # into Python under Pyodide -- a plain browser <textarea> can hold one.
    # ast.parse() fails encoding it as UnicodeEncodeError, not SyntaxError.
    result = translate("print('\udcff')")
    assert isinstance(result, Refusals)
    assert result.items[0].line == 1


def test_a_deeply_nested_expression_is_a_refusal_not_a_stack_overflow():
    # 500 levels of `1 + 1 + ...` is well within what a reader could paste,
    # and the walker's recursive descent has no depth guard of its own.
    source = "x = " + "1 + " * 500 + "1\n"
    result = translate(source)
    assert isinstance(result, Refusals)
    assert result.items[0].line == 1


def test_a_deeply_nested_expression_alongside_valid_statements_still_refuses_cleanly():
    # translate() only reaches the render step -- the one the nesting
    # actually defeats -- once every statement has walked clean, so when the
    # nesting is the only problem this is the only refusal, however many
    # ordinary statements sit around it and however many of them come after
    # the deep one.
    source = "z = 1\n" + "y = " + "1 + " * 500 + "1\n" + "w = 2\n"
    result = translate(source)
    assert isinstance(result, Refusals)
    assert len(result.items) == 1
    assert "nested too deeply" in result.items[0].reason


def test_an_unsupported_statement_before_a_deep_one_is_still_collected():
    # If a statement refuses on its own terms, translate() never reaches the
    # render step at all -- the deep statement after it walks clean and
    # simply never gets rendered, so this refuses for the ordinary reason,
    # not the nesting.
    source = "import os\n" + "y = " + "1 + " * 500 + "1\n"
    result = translate(source)
    assert isinstance(result, Refusals)
    assert len(result.items) == 1
    assert "import" in result.items[0].reason
    assert result.items[0].line == 1


# Every refused construct a reader can plausibly reach, and the words the
# refusal has to use for it. Before this the reason fell back to the raw
# Python ast class name -- "Delete cannot be translated", "Global", "Mod",
# "FloorDiv" -- which describes CPython's parser, not their program.
_REFUSALS = [
    ("del x\n", "`del`"),
    ("global x\n", "`global`"),
    ("with open('f') as f:\n    pass\n", "`with`"),
    ("assert x == 1\n", "`assert`"),
    ("pass\n", "`pass`"),
    ("print(2 ** 3)\n", "`**`"),
    ("print(7 // 2)\n", "`//`"),
    ("print(1 << 2)\n", "`<<`"),
    ("print(~1)\n", "`~`"),
    ("print(1j)\n", "complex"),
    ("print(b'x')\n", "bytes"),
    ("print(x if y > 0 else z)\n", "conditional expression"),
    ("print(f(*xs))\n", "unpacking"),
    ("print(o.attr)\n", "attribute"),
    ("x: int = 1\n", "annotation"),
    ("async def f():\n    pass\n", "`async def`"),
    ("def f():\n    yield 1\n", "`yield`"),
    ("match x:\n    case 1:\n        pass\n", "`match`"),
    ("print(1, 2)\n", "one value"),
    ("1 + 1\n", "has to be a call"),
    ("xs = []\ny = xs.append(1)\n", "`.append()`"),
    ("for i in range(0, 10, 2):\n    print(i)\n", "`range` with a step"),
    ("name = input('a', 'b')\n", "one prompt"),
    ("print(input('x') + 1)\n", "larger expression"),
    ("print(len(1, 2))\n", "`len` takes exactly one"),
    ("print(f(a=1))\n", "keyword argument"),
    ("d = {**e}\n", "dictionary literal"),
    ("print(f'{x!r}')\n", "format spec"),
    ("xs = [1]\nxs[1:2] = [1]\n", "slice"),
    ("a = b = 0\n", "several names at once"),
    ("xs = [1]\nxs[0] += 1\n", "not an element"),
    ("x += 1\n", "`x` has no value yet"),
]


def test_every_refusal_names_the_construct_in_the_reader_s_words():
    for source, wanted in _REFUSALS:
        result = translate(source)
        assert isinstance(result, Refusals), (source, result)
        assert wanted in result.items[0].reason, (source, result.items[0].reason)


def test_no_refusal_leaks_a_python_ast_class_name():
    # The structural half of the same guarantee: a reason may never contain
    # a bare CamelCase word that is one of Python's ast node classes, which
    # is exactly what the old `_DESCRIBE.get(name, name)` fallback emitted.
    import ast
    import re

    ast_names = {
        name for name in dir(ast)
        if name[:1].isupper() and isinstance(getattr(ast, name), type)
    }
    for source, _ in _REFUSALS:
        for refusal in translate(source).items:
            words = set(re.findall(r"\b[A-Z][A-Za-z]+\b", refusal.reason))
            assert not (words & ast_names), (source, refusal.reason)


def test_upper_is_refused_with_an_idiom():
    result = translate("s = 'a'\nprint(s.upper())\n")
    assert isinstance(result, Refusals)
    (refusal,) = result.items
    assert "`.upper()`" in refusal.reason
    assert refusal.idiom is not None
    assert "lower" in refusal.idiom


def test_floor_division_is_still_refused():
    # MatrixLang has no floor operator now that `/` is true division, so
    # `//` would be a silent difference on exactly the negative operands
    # `%` was made careful about.
    result = translate("print(7 // 2)\n")
    assert isinstance(result, Refusals)
    assert "//" in result.items[0].reason or "//" in (result.items[0].idiom or "")


def test_a_bare_split_is_refused_rather_than_guessed():
    # Python's bare .split() splits on RUNS of whitespace and discards
    # empty strings. `cleave " "` is different behaviour, not a missing
    # argument, so translating one to the other would be silently wrong --
    # which is exactly what the governing rule forbids.
    result = translate("s = 'a b'\nprint(s.split())\n")
    assert isinstance(result, Refusals)
    (refusal,) = result.items
    assert "split" in refusal.reason
    assert refusal.idiom is not None


def test_a_bare_split_keeps_the_whitespace_runs_idiom():
    # Fails if the zero-argument and multi-argument branches were ever
    # merged back into one message: the limit-specific idiom below names
    # neither "whitespace" nor "runs".
    result = translate("s = 'a b'\nprint(s.split())\n")
    assert isinstance(result, Refusals)
    (refusal,) = result.items
    assert refusal.idiom is not None
    assert "whitespace" in refusal.idiom
    assert "runs" in refusal.idiom


def test_split_with_two_arguments_is_refused():
    # `.split(",", 1)` names its separator -- a reader who wrote this
    # already did the thing the zero-argument message tells them to do.
    # The real reason is the maxsplit, which `cleave` has no way to
    # honour; this must fail if that branch collapsed back into the
    # zero-argument one, which never mentions a limit or `cleave` at all.
    result = translate("s = 'a,b,c'\nprint(s.split(',', 1))\n")
    assert isinstance(result, Refusals)
    refusal = result.items[0]
    assert "split" in refusal.reason
    assert "limit" in refusal.reason
    assert "cleave" in refusal.reason
    assert refusal.idiom is not None
    assert "whitespace" not in refusal.idiom
    assert "parts[0]" in refusal.idiom


def test_strip_with_an_argument_is_refused():
    # `trim` takes no argument; .strip("x") strips a character SET, which
    # is a different operation.
    result = translate("s = 'xax'\nprint(s.strip('x'))\n")
    assert isinstance(result, Refusals)
    assert "strip" in result.items[0].reason


def test_lower_as_a_bare_statement_is_refused_with_the_new_reason():
    # `name.lower()` on its own line is a classic beginner slip -- thinking
    # the method mutates. This branch made `.lower()` translatable, so the
    # OLD blanket "MatrixLang has no `.lower()` method" is now false; it
    # must say the real thing instead: the call produces a new value that
    # this line throws away.
    result = translate("s = 'A'\ns.lower()\n")
    assert isinstance(result, Refusals)
    refusal = result.items[0]
    assert "no `.lower()` method" not in refusal.reason
    assert "NEW string" in refusal.reason
    assert refusal.idiom is not None
    assert "s = s.lower(...)" in refusal.idiom


def test_strip_as_a_bare_statement_is_refused_with_the_new_reason():
    result = translate("s = ' a '\ns.strip()\n")
    assert isinstance(result, Refusals)
    refusal = result.items[0]
    assert "no `.strip()` method" not in refusal.reason
    assert "NEW string" in refusal.reason
    assert refusal.idiom is not None
    assert "s = s.strip(...)" in refusal.idiom


def test_upper_as_a_bare_statement_gets_the_upper_casing_refusal():
    # Not the list-method blanket message ("the only list method it can
    # translate is `.append()`") -- `.upper()` gets the same refusal here
    # as it does in value position, because there is still no MatrixLang
    # upper-casing operator regardless of where the call sits.
    result = translate("s = 'a'\ns.upper()\n")
    assert isinstance(result, Refusals)
    refusal = result.items[0]
    assert "no upper-casing operator" in refusal.reason
    assert refusal.idiom is not None
    assert "lower" in refusal.idiom
    assert "append" not in refusal.idiom


def test_sort_as_a_bare_statement_still_gets_the_old_blanket_message():
    # The control: a method this branch did NOT touch must still hit the
    # unchanged blanket refusal.
    result = translate("xs = [2, 1]\nxs.sort()\n")
    assert isinstance(result, Refusals)
    refusal = result.items[0]
    assert refusal.reason == "MatrixLang has no `.sort()` method"
    assert refusal.idiom == "the only list method it can translate is `.append()`"


def test_an_untranslatable_method_still_refuses_as_before():
    # Not in this change. The blanket message must still be reachable.
    result = translate("s = 'a'\nprint(s.replace('a', 'b'))\n")
    assert isinstance(result, Refusals)
    assert "`.replace()`" in result.items[0].reason


def test_a_refusal_still_carries_its_python_position():
    result = translate("s = 'a'\nprint(s.upper())\n")
    assert result.items[0].line == 2


def test_break_and_continue_are_no_longer_refused():
    result = translate("for x in xs:\n    break\n")
    assert isinstance(result, Translated)
    result = translate("for x in xs:\n    continue\n")
    assert isinstance(result, Translated)


def test_a_bare_break_outside_a_loop_now_translates():
    # Before `wake`/`glitch` existed, `Break` sat in the refusal
    # catalogue unconditionally, so a bare `break` at module level --
    # invalid Python outside a loop, but `ast.parse` accepts what
    # `compile` would reject -- was refused at translate time. That
    # catalogue entry is gone now that `break` maps to `wake`, so this
    # same input translates instead of refusing. This is a deliberate
    # decision, not an oversight: the input was invalid Python either
    # way, and the interpreter's own "'wake' outside a loop" points at
    # the real problem at least as well as a translate-time refusal
    # did. Pinning down the new behaviour so a future change to it is
    # a choice, not a surprise.
    result = translate("break\n")
    assert isinstance(result, Translated)
    assert result.source == "wake\n"

    out = io.StringIO()
    with pytest.raises(RuntimeErrorML) as caught:
        Interpreter(out=out).run(parse(lex(result.source)))
    assert caught.value.message == "'wake' outside a loop"
    assert caught.value.line == 1
    assert caught.value.column == 1


def test_a_bare_continue_outside_a_loop_now_translates():
    # Same story as the `break` case above, for `continue` / `glitch`.
    result = translate("continue\n")
    assert isinstance(result, Translated)
    assert result.source == "glitch\n"

    out = io.StringIO()
    with pytest.raises(RuntimeErrorML) as caught:
        Interpreter(out=out).run(parse(lex(result.source)))
    assert caught.value.message == "'glitch' outside a loop"
    assert caught.value.line == 1
    assert caught.value.column == 1


def test_loop_else_is_still_refused():
    # Python's loop-else runs only when no `break` fired. Adding `break`
    # without keeping this refusal would let a `for ... else` translate
    # into something that quietly means the wrong thing.
    #
    # "for ... else" is carried in .idiom, not .reason -- self._no()'s
    # reason falls back to _DESCRIBE.get("For", _UNNAMED), and "For" has
    # no _DESCRIBE entry, so the reason is the generic "this construct
    # cannot be translated". test_for_else_is_refused in
    # test_pytrans_loops.py already checks .idiom for the plain (no
    # `break`) case; this one checks the same field so it agrees with
    # that established convention.
    result = translate("for x in xs:\n    break\nelse:\n    print(1)\n")
    assert isinstance(result, Refusals)
    assert "for ... else" in result.items[0].idiom


FIND_BOOK = """def find_book(books, term):
    for book in books:
        if book["name"] == term:
            return book
    return None

result = find_book(library, user_input)
if result:
    print(result["name"])
"""


def _detect(source):
    return _none_then_truth_test(ast.parse(source))


def test_the_none_then_truth_test_shape_is_detected():
    found = _detect(FIND_BOOK)
    assert found is not None
    refusal, positions = found
    # Anchored at the `return None`, naming the condition's line.
    assert refusal.line == 5
    assert "find_book" in refusal.reason
    assert "line 8" in refusal.reason
    # The two positions it stands in for: the None constant and the If test,
    # exactly as _constant and condition() report them.
    assert positions == frozenset({(5, 11), (8, 3)})


def test_the_idiom_shows_both_ends_of_the_rewrite():
    refusal, _ = _detect(FIND_BOOK)
    # The function's contract has to change, and the value has to be
    # unwrapped afterwards. A reader who is told neither hits a fresh
    # error on the next run.
    assert "return []" in refusal.idiom
    assert "len(result) > 0" in refusal.idiom
    assert "result[0]" in refusal.idiom


def test_a_function_whose_every_path_returns_none_is_not_the_shape():
    assert _detect(
        "def f(x):\n"
        "    return None\n"
        "\n"
        "result = f(1)\n"
        "if result:\n"
        "    print(result)\n"
    ) is None


def test_a_function_whose_every_path_returns_a_value_is_not_the_shape():
    assert _detect(
        "def f(x):\n"
        "    return x\n"
        "\n"
        "result = f(1)\n"
        "if result:\n"
        "    print(result)\n"
    ) is None


def test_a_bare_return_is_not_the_shape():
    # Measured, not assumed: a bare `return` produces only ONE refusal
    # today, so admitting it here would detect a shape the safety property
    # in Task 2 then forbids acting on.
    assert _detect(
        "def f(x):\n"
        "    if x:\n"
        "        return x\n"
        "    return\n"
        "\n"
        "result = f(1)\n"
        "if result:\n"
        "    print(result)\n"
    ) is None


def test_a_rebound_name_is_not_the_shape():
    # Without this, the condition gets paired with the wrong function and
    # the refusal explains a shape the reader did not write.
    assert _detect(
        "def f(x):\n"
        "    if x:\n"
        "        return x\n"
        "    return None\n"
        "\n"
        "result = f(1)\n"
        "result = other()\n"
        "if result:\n"
        "    print(result)\n"
    ) is None


def test_a_test_that_is_not_a_bare_name_is_not_the_shape():
    assert _detect(
        "def f(x):\n"
        "    if x:\n"
        "        return x\n"
        "    return None\n"
        "\n"
        "result = f(1)\n"
        "if result.name:\n"
        "    print(result)\n"
    ) is None


def test_a_nested_defs_returns_do_not_count_as_the_outer_functions():
    # The inner def supplies the `return None`; the outer only ever returns
    # a value. Treating the inner's returns as the outer's would invent a
    # mixed shape that is not there.
    assert _detect(
        "def f(x):\n"
        "    def inner():\n"
        "        return None\n"
        "    return inner\n"
        "\n"
        "result = f(1)\n"
        "if result:\n"
        "    print(result)\n"
    ) is None


# Fix round 1: the `functions` dict is built from module-level defs only,
# then reused while scanning every scope body -- including nested ones --
# without checking whether the call site's own scope shadows that name.
# These are the reviewer's repro and its variants.


def test_a_called_name_shadowed_by_a_nested_def_is_not_the_shape():
    # The reviewer's repro: the inner `find_book` shadows the outer one,
    # so the call resolves to a function that never returns None. Blaming
    # the outer function's `return None` for it is a wrong, confident
    # claim about a shape the reader did not write.
    assert _detect(
        "def find_book(x):\n"
        "    if x:\n"
        "        return x\n"
        "    return None\n"
        "\n"
        "def g():\n"
        "    def find_book(y):\n"
        "        return y\n"
        "    result = find_book(1)\n"
        "    if result:\n"
        "        print(result)\n"
    ) is None


def test_a_called_name_shadowed_by_a_local_assignment_is_not_the_shape():
    assert _detect(
        "def find_book(x):\n"
        "    if x:\n"
        "        return x\n"
        "    return None\n"
        "\n"
        "def g():\n"
        "    find_book = lambda y: y\n"
        "    result = find_book(1)\n"
        "    if result:\n"
        "        print(result)\n"
    ) is None


def test_a_called_name_shadowed_by_an_enclosing_parameter_is_not_the_shape():
    assert _detect(
        "def find_book(x):\n"
        "    if x:\n"
        "        return x\n"
        "    return None\n"
        "\n"
        "def g(find_book):\n"
        "    result = find_book(1)\n"
        "    if result:\n"
        "        print(result)\n"
    ) is None


def test_the_ordinary_module_level_case_still_fires():
    # Regression guard for this round: the shadow check must not swallow
    # the base case just because the call and its def share one scope --
    # the def statement itself is not a shadow of itself.
    found = _detect(FIND_BOOK)
    assert found is not None


def test_a_call_from_an_unshadowed_nested_function_still_fires():
    # A fix that closes the shadowing hole by never firing from a nested
    # scope at all would pass the negative tests above and break the
    # feature. This call is nested but not shadowed, so it must still
    # fire.
    found = _detect(
        "def find_book(x):\n"
        "    if x:\n"
        "        return x\n"
        "    return None\n"
        "\n"
        "def g():\n"
        "    result = find_book(1)\n"
        "    if result:\n"
        "        print(result)\n"
    )
    assert found is not None
    refusal, _ = found
    assert "find_book" in refusal.reason
