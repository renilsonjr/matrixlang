"""`for`: the most invented structure in the translator.

MatrixLang has no `for`. A loop is a counter, `length`, and `dejavu`
(`while`), and the loop variable is substituted inline rather than
declared -- there is no loop variable in the output at all.
"""

import ast

from matrixlang.pytrans import translate, Translated, Refusals
from matrixlang.pytrans.names import bound_names, free_name


def ml(python_source):
    """The MatrixLang a Python snippet translates to. Fails loudly on refusal."""
    result = translate(python_source)
    assert isinstance(result, Translated), getattr(result, "items", result)
    return result.source


def refused(python_source):
    """The refusals a Python snippet produces. Fails loudly if it translated."""
    result = translate(python_source)
    assert isinstance(result, Refusals), result
    return result.items


def test_free_name_avoids_a_taken_stem():
    assert free_name({"n"}) == "n1"
    assert free_name({"n", "n1", "n2"}) == "n3"
    assert free_name(set()) == "n"


def test_bound_names_sees_parameters_and_function_names():
    tree = ast.parse("def f(a, b):\n    c = 1\n")
    assert {"f", "a", "b", "c"} <= bound_names(tree)


def test_a_for_loop_substitutes_the_index_inline():
    source = "xs = [1]\nfor x in xs:\n    print(x)\n"
    assert ml(source) == (
        "construct xs = [1]\n"
        "construct n = 0\n"
        "dejavu n < length xs\n"
        "  trace xs[n]\n"
        "  n = n + 1\n"
        "flatline\n"
    )


def test_the_counter_avoids_a_name_the_reader_used():
    source = "n = 5\nxs = [1]\nfor x in xs:\n    print(x)\n"
    assert "construct n1 = 0" in ml(source)
    assert "dejavu n1 < length xs" in ml(source)


def test_nested_loops_get_different_counters():
    source = "xs = [1]\nfor a in xs:\n    for b in xs:\n        print(b)\n"
    out = ml(source)
    assert "construct n = 0" in out and "construct n1 = 0" in out


def test_a_non_name_iterable_is_evaluated_once():
    # Substituting `f(1)[n]` inline would call f on every iteration -- a
    # different program from the one written.
    source = "for x in f(1):\n    print(x)\n"
    out = ml(source)
    assert "construct xs = f(1)\n" in out
    assert "f(1)[" not in out


def test_range_uses_the_counter_itself():
    source = "for i in range(3):\n    print(i)\n"
    assert ml(source) == (
        "construct n = 0\ndejavu n < 3\n  trace n\n  n = n + 1\nflatline\n"
    )


def test_range_with_a_start():
    source = "for i in range(2, 5):\n    print(i)\n"
    assert ml(source) == (
        "construct n = 2\ndejavu n < 5\n  trace n\n  n = n + 1\nflatline\n"
    )


def test_range_with_a_step_is_refused():
    assert "step" in refused("for i in range(0, 10, 2):\n    print(i)\n")[0].idiom


def test_reassigning_the_loop_variable_is_refused():
    source = "xs = [1]\nfor x in xs:\n    x = 2\n"
    assert "reassigns `x`" in refused(source)[0].reason


def test_a_name_first_bound_inside_a_loop_is_hoisted():
    # `construct` inside a loop body fails on iteration 2, so the
    # declaration moves above the loop with a placeholder.
    source = "xs = [1]\nfor x in xs:\n    total = x\n"
    out = ml(source)
    assert out.index("construct total = 0") < out.index("dejavu")
    assert "  total = xs[n]" in out


def test_for_else_is_refused():
    source = "xs = [1]\nfor x in xs:\n    print(x)\nelse:\n    print(2)\n"
    assert "for ... else" in refused(source)[0].idiom



def test_a_function_defined_directly_in_a_loop_is_refused():
    # Not hoisted, unlike a Declare: the loop variable is substituted
    # inline (`x` becomes `xs[n]`), never declared, so a def written to
    # close over `x` would -- hoisted above the loop -- close over a
    # counter that means nothing there yet. Refusing avoids silently
    # changing what the closure captures.
    source = (
        "xs = [1]\n"
        "for x in xs:\n"
        "    def helper(v):\n"
        "        return v * 2\n"
        "    print(helper(x))\n"
    )
    refusal = refused(source)[0]
    assert "inside a loop" in refusal.reason
    assert "outside the loop" in refusal.idiom


def test_a_function_defined_inside_an_if_inside_a_loop_is_refused():
    # Same hazard, one level deeper: a `def` nested under `if` inside the
    # loop body hits interpreter.py's FunctionDef branch on every pass
    # exactly like a top-level one does.
    source = (
        "xs = [1]\n"
        "for x in xs:\n"
        "    if x > 0:\n"
        "        def helper(v):\n"
        "            return v * 2\n"
        "        print(helper(x))\n"
    )
    assert "inside a loop" in refused(source)[0].reason


def test_a_function_defined_directly_in_a_while_is_refused():
    source = (
        "n = 0\n"
        "while n < 3:\n"
        "    def helper(v):\n"
        "        return v * 2\n"
        "    print(helper(n))\n"
        "    n += 1\n"
    )
    assert "inside a loop" in refused(source)[0].reason


def test_a_literal_range_bound_stays_inline():
    # A number cannot change, so hoisting it would only add a line the
    # reader has to account for.
    assert "construct stop" not in ml("for i in range(3):\n    print(i)\n")


def test_a_loop_that_reassigns_the_list_it_walks_is_refused():
    # Python's `for` holds the list OBJECT, so rebinding the name inside
    # the body changes nothing; the output indexes the name, so it would
    # follow the rebinding onto a different list. No output is right for
    # both that and `xs.append(v)` inside its own loop, so it is refused.
    source = "xs = [1, 2, 3]\nfor x in xs:\n    xs = [1]\n    print(x)\n"
    refusal = refused(source)[0]
    assert "reassigns `xs`" in refusal.reason
    assert refusal.line == 2


def test_a_loop_variable_that_is_already_a_name_is_refused():
    # Python's `for` leaves its variable bound after the loop; the output
    # has no such name, so a read after the loop returns whatever the name
    # held BEFORE it. New name: loud "not declared". Reused name: silently
    # the old value, so the collision is refused.
    source = "x = 5\nxs = [1, 2, 3]\nfor x in xs:\n    print(x)\nprint(x)\n"
    refusal = refused(source)[0]
    assert "`x` is already a name" in refusal.reason
    assert refusal.line == 3
    assert "different one" in refusal.idiom
