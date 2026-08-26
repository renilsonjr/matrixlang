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
