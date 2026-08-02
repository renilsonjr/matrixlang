import pytest

from matrixlang.values import is_bool, is_int, is_str, to_display, type_name


def test_bool_is_not_an_integer():
    # In Python, bool subclasses int: isinstance(True, int) is True and
    # True + 1 is 2. Spec §5 forbids coercion, so the interpreter must be
    # able to tell them apart. This is THE rule this module exists for.
    assert is_int(True) is False
    assert is_int(False) is False
    assert is_bool(True) is True
    assert is_int(7) is True
    assert is_bool(7) is False


def test_string_predicate():
    assert is_str("Neo") is True
    assert is_str(7) is False
    assert is_str(True) is False


def test_type_names_are_the_language_s_words():
    assert type_name(7) == "integer"
    assert type_name(True) == "boolean"
    assert type_name("Neo") == "string"


def test_display_prints_strings_without_quotes():
    assert to_display("wake up") == "wake up"


def test_display_prints_booleans_in_the_language_s_spelling():
    # Python renders these "True"/"False"; MatrixLang spells them lowercase.
    assert to_display(True) == "true"
    assert to_display(False) == "false"


def test_display_prints_integers():
    assert to_display(0) == "0"
    assert to_display(-7) == "-7"


def test_a_list_is_recognised_by_identity_of_type_not_isinstance():
    from matrixlang.values import is_list

    assert is_list([]) is True
    assert is_list([1, 2]) is True
    assert is_list("no") is False
    assert is_list(1) is False


def test_a_list_names_itself_list():
    from matrixlang.values import type_name

    assert type_name([1]) == "list"


def test_a_list_displays_with_brackets():
    from matrixlang.values import to_display

    assert to_display([]) == "[]"
    assert to_display([1, 2]) == "[1, 2]"
    assert to_display([True, False]) == "[true, false]"


def test_strings_are_quoted_inside_a_list_but_not_outside_one():
    # Bare `trace "hi"` prints hi. Inside a list, without quotes there is
    # no way to tell a string from a name and a list of strings becomes
    # unreadable, so the inconsistency is deliberate.
    from matrixlang.values import to_display

    assert to_display("hi") == "hi"
    assert to_display(["hi"]) == '["hi"]'
    assert to_display(["a", 1]) == '["a", 1]'


def test_a_quote_inside_a_displayed_string_is_escaped():
    from matrixlang.values import to_display

    assert to_display(['say "hi"']) == '["say \\"hi\\""]'


def test_nested_lists_display():
    from matrixlang.values import to_display

    assert to_display([[1], [2, 3]]) == "[[1], [2, 3]]"


def test_an_agent_inside_a_list_displays_by_name():
    from matrixlang.values import Function, to_display

    agent = Function("fib", ["n"], None, None)
    assert to_display([agent]) == "[<agent fib>]"


def test_displaying_a_cyclic_list_raises_a_named_error_not_a_recursion_error():
    # Measured before the design was written: the naive recursive
    # to_display raises RecursionError, which the interpreter converts to
    # "expression is nested too deeply" — a false statement about a
    # one-element list. A named exception is what lets the interpreter
    # report the truth.
    from matrixlang.values import CyclicValue, to_display

    xs = [1]
    xs[0] = xs
    with pytest.raises(CyclicValue):
        to_display(xs)
