"""`oracle` over a dictionary, a list and a string."""

import io

import pytest

from matrixlang.errors import RuntimeErrorML
from matrixlang.interpreter import Interpreter
from matrixlang.lexer import lex
from matrixlang.parser import parse


def run(source):
    out = io.StringIO()
    Interpreter(out=out).run(parse(lex(source)))
    return out.getvalue()


def fails(source):
    with pytest.raises(RuntimeErrorML) as caught:
        run(source)
    return caught.value


# --- the dictionary, which must not have changed ----------------------


def test_a_present_key_is_still_true():
    assert run('trace {"a": 1} oracle "a"\n') == "true\n"


def test_an_absent_key_is_still_false():
    assert run('trace {"a": 1} oracle "b"\n') == "false\n"


def test_a_bad_key_is_still_an_error():
    error = fails('trace {"a": 1} oracle ["x"]\n')
    assert "a dictionary key must be a string or a number" in error.message


def test_an_empty_dictionary_has_no_keys():
    assert run('trace {} oracle "a"\n') == "false\n"


# --- the list ----------------------------------------------------------


def test_a_present_element_is_true():
    assert run('trace ["a", "b"] oracle "a"\n') == "true\n"


def test_an_absent_element_is_false():
    assert run('trace ["a", "b"] oracle "c"\n') == "false\n"


def test_an_empty_list_contains_nothing():
    assert run("trace [] oracle 1\n") == "false\n"


def test_numbers_work_too():
    assert run("trace [1, 2, 3] oracle 2\n") == "true\n"


def test_a_nested_list_compares_by_value():
    # `equal` recurses, so a list element that is itself a list is found
    # by what it holds rather than by identity.
    assert run("trace [[1], [2]] oracle [1]\n") == "true\n"


def test_an_incomparable_element_is_skipped_not_raised():
    # THE decision. `["a"] oracle 1` asks "does this list contain the
    # integer 1?", which has a truthful answer -- no, it holds a string.
    # `1 == "a"` genuinely has no answer and raises; membership is a
    # different question. This is the one place in the language where a
    # type mismatch declines to raise where `==` would.
    assert run('trace ["a"] oracle 1\n') == "false\n"


@pytest.mark.parametrize(
    "literal", ['["a", 1]', '[1, "a"]']
)
def test_the_skip_is_order_independent(literal):
    # The alternative -- raise on the first incomparable element -- would
    # make `["a", 1] oracle 1` an error and `[1, "a"] oracle 1` true: the
    # same list, reordered, deciding whether the program runs. That is
    # why the skip was chosen, so both orders are pinned.
    assert run(f"trace {literal} oracle 1\n") == "true\n"


def test_a_mixed_list_still_answers_for_the_other_type():
    assert run('trace [1, "a"] oracle "a"\n') == "true\n"


# --- the string --------------------------------------------------------


def test_a_substring_is_found():
    assert run('trace "matrix" oracle "rix"\n') == "true\n"


def test_a_single_character_is_found():
    assert run('trace "matrix" oracle "m"\n') == "true\n"


def test_an_absent_substring_is_false():
    assert run('trace "matrix" oracle "zion"\n') == "false\n"


def test_every_string_contains_the_empty_string():
    # CPython: `"" in "abc"` is True. Verified, not assumed. Note this is
    # NOT inconsistent with `cleave ""` being an error -- CPython itself
    # raises for `"abc".split("")` and returns True here, and each
    # operator follows the language it is matched against.
    assert run('trace "matrix" oracle ""\n') == "true\n"


def test_a_non_string_against_a_string_is_an_error():
    # CPython raises TypeError for `1 in "abc"`. Here it is a positioned
    # MatrixLang error instead -- nothing but MatrixLangError may escape.
    error = fails('trace "matrix" oracle 1\n')
    assert "'oracle'" in error.message
    assert "string" in error.message


# --- everything else ---------------------------------------------------


@pytest.mark.parametrize(
    "left,name",
    [("1", "integer"), ("true", "boolean")],
)
def test_oracle_refuses_a_non_container(left, name):
    error = fails(f"trace {left} oracle 1\n")
    assert error.message == (
        f"'oracle' takes a dictionary, a list or a string, got {name}"
    )


def test_an_agent_is_not_a_container():
    source = "agent f()\n  jackout 1\nflatline\ntrace f oracle 1\n"
    error = fails(source)
    assert "got agent" in error.message


def test_the_error_carries_the_operators_position():
    error = fails("trace 1\ntrace 1 oracle 1\n")
    assert error.line == 2
