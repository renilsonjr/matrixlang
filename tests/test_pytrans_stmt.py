"""Binding: assignment, `+=`, element assignment, and `.append()` -- and
the `construct` versus plain-assignment distinction Python doesn't make."""

from matrixlang.pytrans import translate, Translated, Refusals


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


def test_a_first_binding_uses_construct():
    assert ml("x = 1\n") == "construct x = 1\n"


def test_a_later_binding_is_a_plain_assignment():
    assert ml("x = 1\nx = 2\n") == "construct x = 1\nx = 2\n"


def test_augmented_assignment_expands():
    assert ml("x = 1\nx += 2\n") == "construct x = 1\nx = x + 2\n"


def test_augmented_assignment_before_any_binding_is_refused():
    assert "before changing it" in refused("x += 1\n")[0].idiom


def test_index_assignment():
    assert ml("xs = [1]\nxs[0] = 9\n") == "construct xs = [1]\nxs[0] = 9\n"


def test_dictionary_key_assignment():
    assert ml('d = {}\nd["a"] = 1\n') == 'construct d = {}\nd["a"] = 1\n'


def test_append_becomes_concatenation():
    assert ml("xs = []\nxs.append(1)\n") == "construct xs = []\nxs = xs + [1]\n"


def test_append_inside_an_expression_is_refused():
    assert refused("xs = []\ny = xs.append(1)\n")[0].reason != ""


def test_an_unknown_method_call_is_refused():
    refusal = refused("xs = []\nxs.sort()\n")[0]
    assert "sort" in refusal.reason or "method" in refusal.reason


def test_multiple_assignment_is_refused():
    assert refused("a = b = 0\n")[0].idiom is not None


def test_tuple_unpacking_is_refused():
    assert refused("a, b = 1, 2\n")[0].idiom is not None


def test_if_becomes_redpill():
    assert ml("if a == 1:\n    print(a)\n") == "redpill a == 1\n  trace a\nflatline\n"


def test_if_else_becomes_redpill_bluepill():
    source = "if a == 1:\n    print(1)\nelse:\n    print(2)\n"
    assert ml(source) == (
        "redpill a == 1\n  trace 1\nbluepill\n  trace 2\nflatline\n"
    )


def test_elif_nests_inside_the_else():
    source = "if a == 1:\n    print(1)\nelif a == 2:\n    print(2)\n"
    assert ml(source) == (
        "redpill a == 1\n"
        "  trace 1\n"
        "bluepill\n"
        "  redpill a == 2\n"
        "    trace 2\n"
        "  flatline\n"
        "flatline\n"
    )


def test_while_becomes_dejavu():
    source = "n = 0\nwhile n < 3:\n    n += 1\n"
    assert ml(source) == "construct n = 0\ndejavu n < 3\n  n = n + 1\nflatline\n"


def test_a_function_becomes_an_agent():
    source = "def double(x):\n    return x * 2\n"
    assert ml(source) == "agent double(x)\n  jackout x * 2\nflatline\n"


def test_a_bare_return_becomes_a_bare_jackout():
    source = "def f(x):\n    return\n"
    assert ml(source) == "agent f(x)\n  jackout\nflatline\n"


def test_a_function_body_is_its_own_scope():
    # `x` is declared in the agent and again outside it, because MatrixLang
    # gives an agent body its own frame.
    source = "def f():\n    x = 1\n    return x\nx = 2\n"
    assert ml(source) == (
        "agent f()\n  construct x = 1\n  jackout x\nflatline\nconstruct x = 2\n"
    )


def test_truthiness_is_refused_with_both_rewrites():
    refusal = refused("result = f()\nif result:\n    print(1)\n")[0]
    assert "truthiness" in refusal.reason
    assert "len(result) > 0" in refusal.idiom
    assert "result != 0" in refusal.idiom


def test_a_comparison_condition_is_not_refused():
    assert ml("if a == 1:\n    print(1)\n").startswith("redpill a == 1")


def test_a_boolean_operator_condition_is_not_refused():
    assert ml("if a == 1 and b == 2:\n    print(1)\n").startswith("redpill")


def test_a_not_condition_is_not_refused():
    assert ml("if not a == 1:\n    print(1)\n").startswith("redpill unplug")


def test_a_while_with_a_truthy_condition_is_refused():
    assert "truthiness" in refused("while xs:\n    print(1)\n")[0].reason


def test_default_arguments_are_refused():
    assert "positional" in refused("def f(a=1):\n    return a\n")[0].idiom


def test_a_bare_operand_inside_a_boolean_operator_is_refused():
    # The outer node is a BoolOp, which the guard admits -- but `y` is a
    # bare value, and admitting the wrapper must not admit its operands.
    assert "truthiness" in refused("if a == 1 or y:\n    print(1)\n")[0].reason


def test_not_over_a_bare_value_is_refused():
    # `if not xs:` is the ordinary Python emptiness test, and the single
    # most likely way this hole would have reached a reader.
    assert "truthiness" in refused("if not xs:\n    print(1)\n")[0].reason


def test_a_while_condition_is_guarded_the_same_way():
    assert "truthiness" in refused("while not xs:\n    print(1)\n")[0].reason
