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


def test_a_break_in_an_ifs_else_arm_is_still_ours():
    # `orelse` is an `if`'s `else:` arm, not just a loop's -- dropping it
    # from the fields `_suites` walks would leave a `break` sitting there
    # unmarked, and the loop-else body would wrongly run alongside it.
    assert rewritten(
        "for x in xs:\n"
        "    if c:\n"
        "        print(1)\n"
        "    else:\n"
        "        break\n"
        "else:\n"
        "    print(9)\n"
    ) == (
        "broke = False\n"
        "for x in xs:\n"
        "    if c:\n"
        "        print(1)\n"
        "    else:\n"
        "        broke = True\n"
        "        break\n"
        "if broke == False:\n"
        "    print(9)"
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


def test_a_break_in_a_nested_while_is_not_ours_even_when_our_flag_is_needed():
    # Unlike the test above, the outer loop has a break of its OWN here
    # (the `if a == t` guard), so the flag path is taken. The nested
    # while's break still must not be marked with the outer flag -- only
    # `_mark`'s own skip of `ast.While` keeps it that way.
    assert rewritten(
        "for a in A:\n"
        "    while c:\n"
        "        break\n"
        "    if a == t:\n"
        "        break\n"
        "else:\n"
        "    print(1)\n"
    ) == (
        "broke = False\n"
        "for a in A:\n"
        "    while c:\n"
        "        break\n"
        "    if a == t:\n"
        "        broke = True\n"
        "        break\n"
        "if broke == False:\n"
        "    print(1)"
    )


def test_a_break_in_an_inner_loops_else_belongs_to_the_outer_loop():
    # Verified against CPython: this breaks the OUTER loop, so the outer
    # else must not run. It works because the inner loop-else is rewritten
    # first -- its `else` is gone by the time the outer loop looks, and the
    # `break` is sitting in the outer body where the ordinary walk finds it.
    assert rewritten(
        "for a in A:\n"
        "    for b in B:\n"
        "        print(b)\n"
        "    else:\n"
        "        break\n"
        "else:\n"
        "    print(9)\n"
    ) == (
        "broke = False\n"
        "for a in A:\n"
        "    for b in B:\n"
        "        print(b)\n"
        "    broke = True\n"
        "    break\n"
        "if broke == False:\n"
        "    print(9)"
    )


def test_nested_loop_elses_each_get_their_own_flag():
    # The INNER loop is named first, because the recursion reaches it
    # first -- so the outer one is `broke1`, not `broke`.
    assert rewritten(
        "for a in A:\n"
        "    for b in B:\n"
        "        if b == t:\n"
        "            break\n"
        "    else:\n"
        "        print(3)\n"
        "    if a == t:\n"
        "        break\n"
        "else:\n"
        "    print(1)\n"
    ) == (
        "broke1 = False\n"
        "for a in A:\n"
        "    broke = False\n"
        "    for b in B:\n"
        "        if b == t:\n"
        "            broke = True\n"
        "            break\n"
        "    if broke == False:\n"
        "        print(3)\n"
        "    if a == t:\n"
        "        broke1 = True\n"
        "        break\n"
        "if broke1 == False:\n"
        "    print(1)"
    )


def test_a_loop_else_inside_a_loop_keeps_its_flag_in_the_loop_body():
    # The flag has to reset each turn, so the assignment stays inside the
    # outer loop rather than being hoisted above it. `_hoist_declares`
    # lifts the DECLARATION later; the assignment must stay put.
    assert rewritten(
        "for r in rows:\n"
        "    for v in r:\n"
        "        if v == t:\n"
        "            break\n"
        "    else:\n"
        "        print(r)\n"
    ) == (
        "for r in rows:\n"
        "    broke = False\n"
        "    for v in r:\n"
        "        if v == t:\n"
        "            broke = True\n"
        "            break\n"
        "    if broke == False:\n"
        "        print(r)"
    )


def test_two_sibling_loop_elses_get_different_flags():
    assert rewritten(
        "for x in xs:\n    break\nelse:\n    print(1)\n"
        "for y in ys:\n    break\nelse:\n    print(2)\n"
    ) == (
        "broke = False\n"
        "for x in xs:\n"
        "    broke = True\n"
        "    break\n"
        "if broke == False:\n"
        "    print(1)\n"
        "broke1 = False\n"
        "for y in ys:\n"
        "    broke1 = True\n"
        "    break\n"
        "if broke1 == False:\n"
        "    print(2)"
    )


def test_a_return_in_the_loop_skips_the_else():
    # Python skips the else when the loop is left by `return`. The rewrite
    # gets it free -- `return` leaves the function, so the trailing
    # statements never run -- but it is pinned rather than assumed.
    assert rewritten(
        "def f(xs):\n"
        "    for x in xs:\n"
        "        return 1\n"
        "    else:\n"
        "        return 2\n"
    ) == (
        "def f(xs):\n"
        "    for x in xs:\n"
        "        return 1\n"
        "    return 2"
    )
