"""Loop-else, tested as Python in and Python out.

Nothing here goes through the translator. A failure means the rewrite is
wrong, not that something downstream broke.
"""

import ast

from matrixlang.pytrans.loop_else import rewrite_loop_else
from matrixlang.pytrans.names import bound_names
from matrixlang import tokens


def rewritten(source):
    """The Python a snippet becomes once loop-else is a flag."""
    tree = ast.parse(source)
    return ast.unparse(rewrite_loop_else(tree, bound_names(tree)))


def test_a_loop_else_becomes_a_flag_and_a_guard():
    assert rewritten(
        "for x in xs:\n    if x == t:\n        break\nelse:\n    print(1)\n"
    ) == (
        "broke = False\n"
        "for x in xs:\n"
        "    if x == t:\n"
        "        broke = True\n"
        "        break\n"
        "if broke == False:\n"
        "    print(1)"
    )


def test_the_guard_compares_rather_than_negating():
    # `not broke` would refuse: MatrixLang has no truthiness and the
    # translator will not take a bare name as a condition. The comparison
    # is what makes the rewrite's own output translatable.
    assert "if broke == False:" in rewritten(
        "for x in xs:\n    break\nelse:\n    print(1)\n"
    )
    assert "not broke" not in rewritten(
        "for x in xs:\n    break\nelse:\n    print(1)\n"
    )


def test_a_nested_loops_break_is_not_ours():
    # The inner `break` belongs to the inner loop. Marking it would set our
    # flag on a loop that never broke, and the else would wrongly not run.
    assert rewritten(
        "for a in A:\n"
        "    for b in B:\n"
        "        break\n"
        "    if a == t:\n"
        "        break\n"
        "else:\n"
        "    print(1)\n"
    ) == (
        "broke = False\n"
        "for a in A:\n"
        "    for b in B:\n"
        "        break\n"
        "    if a == t:\n"
        "        broke = True\n"
        "        break\n"
        "if broke == False:\n"
        "    print(1)"
    )


def test_a_break_inside_a_try_is_still_ours():
    assert rewritten(
        "for x in xs:\n"
        "    try:\n"
        "        break\n"
        "    finally:\n"
        "        print(2)\n"
        "else:\n"
        "    print(1)\n"
    ) == (
        "broke = False\n"
        "for x in xs:\n"
        "    try:\n"
        "        broke = True\n"
        "        break\n"
        "    finally:\n"
        "        print(2)\n"
        "if broke == False:\n"
        "    print(1)"
    )


def test_the_flag_avoids_the_readers_names():
    assert rewritten(
        "broke = 1\nfor x in xs:\n    break\nelse:\n    print(1)\n"
    ) == (
        "broke = 1\n"
        "broke1 = False\n"
        "for x in xs:\n"
        "    broke1 = True\n"
        "    break\n"
        "if broke1 == False:\n"
        "    print(1)"
    )


def test_the_flag_stem_is_not_a_matrixlang_keyword():
    from matrixlang.pytrans.loop_else import _FLAG_STEM

    assert _FLAG_STEM not in tokens.KEYWORDS


def test_a_while_else_is_left_alone_until_task_3():
    # Scaffolding, and Task 3 deletes it. Until `while` is supported it
    # must be left byte-identical so it keeps the refusal it already has,
    # rather than being half-handled.
    source = "while c:\n    break\nelse:\n    print(1)\n"
    assert rewritten(source) == ast.unparse(ast.parse(source))


def test_a_program_without_loop_else_is_untouched():
    source = "for x in xs:\n    break\n"
    assert rewritten(source) == ast.unparse(ast.parse(source))
