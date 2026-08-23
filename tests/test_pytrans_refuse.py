"""The translator's refusal machinery, and its promise never to raise."""

from matrixlang.pytrans import Refusals, Translated, translate


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
    ("while 1 < 2:\n    break\n", "`break`"),
    ("while 1 < 2:\n    continue\n", "`continue`"),
    ("pass\n", "`pass`"),
    ("print(1 % 2)\n", "`%`"),
    ("print(2 ** 3)\n", "`**`"),
    ("print(7 // 2)\n", "`//`"),
    ("print(7 / 2)\n", "`/`"),
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


def test_break_and_continue_carry_an_idiom():
    # The two a Python reader hits hardest in a loop-heavy subset, and the
    # two that shipped with no idiom at all.
    assert "condition" in translate("while 1 < 2:\n    break\n").items[0].idiom
    assert "redpill" in translate("while 1 < 2:\n    continue\n").items[0].idiom


def test_upper_is_refused_with_an_idiom():
    result = translate("s = 'a'\nprint(s.upper())\n")
    assert isinstance(result, Refusals)
    (refusal,) = result.items
    assert "`.upper()`" in refusal.reason
    assert refusal.idiom is not None
    assert "lower" in refusal.idiom


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
