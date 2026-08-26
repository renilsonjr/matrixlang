"""The comprehension pass, tested as Python in and Python out.

Nothing here goes through the translator. A failure means the rewrite is
wrong, not that something downstream broke -- which is the whole reason
the pass is source-to-source in the first place.
"""

import ast

from matrixlang.pytrans.comprehensions import rewrite_comprehensions
from matrixlang.pytrans.names import bound_names
from matrixlang import tokens


def rewritten(source):
    """The Python a snippet becomes once comprehensions are loops."""
    tree = ast.parse(source)
    return ast.unparse(rewrite_comprehensions(tree, bound_names(tree)))


def test_a_comprehension_becomes_an_accumulator_loop():
    assert rewritten("print([f(x) for x in xs])\n") == (
        "out = []\n"
        "for item in xs:\n"
        "    out = out + [f(item)]\n"
        "print(out)"
    )


def test_the_loop_variable_does_not_leak():
    # Python 3 gives a comprehension its own scope, so `x` is still 5
    # afterwards. A rewrite that reused `x` as the loop variable would
    # leave it as 3 -- a wrong answer, silently.
    assert rewritten("x = 5\nout = [x for x in ys]\nprint(x)\n") == (
        "x = 5\n"
        "out1 = []\n"
        "for item in ys:\n"
        "    out1 = out1 + [item]\n"
        "out = out1\n"
        "print(x)"
    )


def test_invented_names_avoid_the_readers():
    assert rewritten("out = 1\nitem = 2\nprint([x for x in xs])\n") == (
        "out = 1\n"
        "item = 2\n"
        "out1 = []\n"
        "for item1 in xs:\n"
        "    out1 = out1 + [item1]\n"
        "print(out1)"
    )


def test_two_comprehensions_get_different_names():
    assert rewritten("print([a for a in xs])\nprint([b for b in ys])\n") == (
        "out = []\n"
        "for item in xs:\n"
        "    out = out + [item]\n"
        "print(out)\n"
        "out1 = []\n"
        "for item1 in ys:\n"
        "    out1 = out1 + [item1]\n"
        "print(out1)"
    )


def test_the_invented_stems_are_not_matrixlang_keywords():
    # A later rename of these stems to, say, `fold` would emit MatrixLang
    # that does not parse, and no other test would catch it.
    from matrixlang.pytrans.comprehensions import _ITEM_STEM, _RESULT_STEM

    assert _RESULT_STEM not in tokens.KEYWORDS
    assert _ITEM_STEM not in tokens.KEYWORDS


def test_a_program_without_comprehensions_is_untouched():
    source = "x = 1\nfor y in ys:\n    print(y)\n"
    assert rewritten(source) == ast.unparse(ast.parse(source))


def test_one_condition_becomes_a_guard():
    assert rewritten("print([f(x) for x in xs if x > 2])\n") == (
        "out = []\n"
        "for item in xs:\n"
        "    if item > 2:\n"
        "        out = out + [f(item)]\n"
        "print(out)"
    )


def test_conditions_nest_rather_than_combine():
    # `if c1 if c2` nests instead of becoming `c1 and c2`: one less
    # expression to build, and c2 is not evaluated when c1 is false.
    assert rewritten("print([x for x in xs if c1 if c2])\n") == (
        "out = []\n"
        "for item in xs:\n"
        "    if c1:\n"
        "        if c2:\n"
        "            out = out + [item]\n"
        "print(out)"
    )


def test_the_rename_reaches_the_conditions():
    assert rewritten("print([1 for x in xs if x])\n") == (
        "out = []\n"
        "for item in xs:\n"
        "    if item:\n"
        "        out = out + [1]\n"
        "print(out)"
    )


def test_inside_a_loop_body_the_rewrite_stays_in_the_loop():
    assert rewritten("for y in ys:\n    print([f(x) for x in y])\n") == (
        "for y in ys:\n"
        "    out = []\n"
        "    for item in y:\n"
        "        out = out + [f(item)]\n"
        "    print(out)"
    )


def test_inside_a_conditional_the_rewrite_stays_in_the_branch():
    # Hoisting above the `if` would call f() when c is false -- the same
    # silent difference accepted for `and`/`or`, but here there is a
    # statement boundary to emit at, so it costs nothing to be correct.
    assert rewritten("if c:\n    print([f(x) for x in xs])\n") == (
        "if c:\n"
        "    out = []\n"
        "    for item in xs:\n"
        "        out = out + [f(item)]\n"
        "    print(out)"
    )


def test_in_an_else_branch():
    assert rewritten("if c:\n    pass\nelse:\n    print([x for x in xs])\n") == (
        "if c:\n"
        "    pass\n"
        "else:\n"
        "    out = []\n"
        "    for item in xs:\n"
        "        out = out + [item]\n"
        "    print(out)"
    )


def test_a_while_test_is_left_alone():
    # `while` re-evaluates its test every turn; a hoisted loop runs once.
    # Left in place, the comprehension keeps the refusal it already has.
    source = "while [x for x in xs]:\n    print(1)\n"
    assert rewritten(source) == ast.unparse(ast.parse(source))


def test_a_comprehension_in_a_while_body_is_still_rewritten():
    assert rewritten("while c:\n    print([x for x in xs])\n") == (
        "while c:\n"
        "    out = []\n"
        "    for item in xs:\n"
        "        out = out + [item]\n"
        "    print(out)"
    )


def test_as_a_call_argument_and_in_a_return():
    assert rewritten("def f():\n    return [x for x in xs]\n") == (
        "def f():\n"
        "    out = []\n"
        "    for item in xs:\n"
        "        out = out + [item]\n"
        "    return out"
    )


def test_a_tuple_target_is_left_alone():
    source = "print([k for k, v in items])\n"
    assert rewritten(source) == ast.unparse(ast.parse(source))


def test_more_than_one_for_is_left_alone():
    source = "print([f(x, y) for x in xs for y in ys])\n"
    assert rewritten(source) == ast.unparse(ast.parse(source))


def test_other_comprehension_kinds_are_left_alone():
    for source in (
        "print({x for x in xs})\n",
        "print({k: v for k in xs})\n",
        "print(sum(x for x in xs))\n",
    ):
        assert rewritten(source) == ast.unparse(ast.parse(source))
