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


def test_a_break_inside_a_match_case_is_still_ours():
    # `ast.Match` holds its suites under `cases`, so a field-list walk
    # misses them and leaves the `break` unmarked -- the loop would break
    # without setting the flag and the else would wrongly run. `match` is
    # refused by the translator today, which makes this unreachable rather
    # than harmless; `try` is refused too and is walked all the same.
    assert rewritten(
        "for x in xs:\n"
        "    match x:\n"
        "        case 1:\n"
        "            break\n"
        "else:\n"
        "    print(1)\n"
    ) == (
        "broke = False\n"
        "for x in xs:\n"
        "    match x:\n"
        "        case 1:\n"
        "            broke = True\n"
        "            break\n"
        "if broke == False:\n"
        "    print(1)"
    )


def test_the_flag_stem_is_not_a_matrixlang_keyword():
    from matrixlang.pytrans.loop_else import _FLAG_STEM

    assert _FLAG_STEM not in tokens.KEYWORDS




def test_a_program_without_loop_else_is_untouched():
    source = "for x in xs:\n    break\n"
    assert rewritten(source) == ast.unparse(ast.parse(source))


def test_a_loop_that_cannot_break_gets_no_flag():
    assert rewritten(
        "for x in xs:\n    print(x)\nelse:\n    print(1)\n"
    ) == (
        "for x in xs:\n"
        "    print(x)\n"
        "print(1)"
    )


def test_continue_is_not_a_break():
    # `continue` does not skip the else, so it must not suppress the flag
    # shortcut either.
    assert rewritten(
        "for x in xs:\n    if c:\n        continue\nelse:\n    print(1)\n"
    ) == (
        "for x in xs:\n"
        "    if c:\n"
        "        continue\n"
        "print(1)"
    )


def test_only_a_nested_break_still_means_no_flag():
    # The inner break is the inner loop's, so OUR loop cannot break --
    # the else always runs and needs no guard.
    assert rewritten(
        "for a in A:\n    for b in B:\n        break\nelse:\n    print(1)\n"
    ) == (
        "for a in A:\n"
        "    for b in B:\n"
        "        break\n"
        "print(1)"
    )


def test_a_while_else_becomes_a_flag_and_a_guard():
    assert rewritten(
        "while c:\n    if d:\n        break\nelse:\n    print(1)\n"
    ) == (
        "broke = False\n"
        "while c:\n"
        "    if d:\n"
        "        broke = True\n"
        "        break\n"
        "if broke == False:\n"
        "    print(1)"
    )


def test_a_while_that_cannot_break_gets_no_flag():
    assert rewritten(
        "while c:\n    n = n + 1\nelse:\n    print(1)\n"
    ) == (
        "while c:\n"
        "    n = n + 1\n"
        "print(1)"
    )


def test_a_break_in_a_nested_while_is_not_ours():
    assert rewritten(
        "for a in A:\n    while c:\n        break\nelse:\n    print(1)\n"
    ) == (
        "for a in A:\n"
        "    while c:\n"
        "        break\n"
        "print(1)"
    )
