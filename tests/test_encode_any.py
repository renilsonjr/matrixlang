"""encode widens to any value, not only a number."""

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


def test_encode_still_renders_a_number():
    assert run("trace encode 2\n") == "2\n"


def test_encode_renders_a_string_unchanged():
    # The case that motivated this: an f-string interpolating a name.
    assert run('trace encode "hi"\n') == "hi\n"


def test_encode_renders_a_boolean_in_the_languages_own_spelling():
    # The deleted guard's comment feared this would give "1". It cannot:
    # values._display checks is_bool before anything else.
    assert run("trace encode true\n") == "true\n"
    assert run("trace encode false\n") == "false\n"


def test_encode_renders_a_list():
    assert run("trace encode [1, 2]\n") == "[1, 2]\n"


def test_encode_renders_a_dictionary():
    assert run('trace encode {"a": 1}\n') == '{"a": 1}\n'


def test_a_string_inside_a_list_keeps_its_quotes():
    # to_display's existing nesting rule, unchanged: bare at the top level,
    # quoted inside a container, so a reader can tell a string from a name.
    assert run('trace encode ["a"]\n') == '["a"]\n'


def test_encode_composes_with_string_concatenation():
    # What the translator emits for f"Name: {name}, ID: {id}".
    source = 'construct name = "clean code"\nconstruct id = 1\n' \
             'trace "Name: " + encode name + ", ID: " + encode id\n'
    assert run(source) == "Name: clean code, ID: 1\n"


def test_encode_refuses_a_value_that_contains_itself():
    # Newly reachable: the type guard used to make this impossible.
    # Uncaught it would escape as a raw Python exception, which
    # site/glue.py carries into the browser as an unhandled traceback.
    error = fails('construct xs = [1]\nxs[0] = xs\ntrace encode xs\n')
    assert "cannot display a value that contains a cycle" in error.message


def test_encode_refuses_a_dictionary_that_contains_itself():
    # "a value", not "a list" -- a dictionary can hold itself too.
    error = fails('construct d = {"a": 1}\nd["a"] = d\ntrace encode d\n')
    assert "cannot display a value that contains a cycle" in error.message


def test_encode_still_refuses_a_number_past_the_digit_ceiling():
    # The one guard that survives, unchanged.
    source = "construct n = 10\nconstruct i = 0\ndejavu i < 14\n" \
             "  n = n * n\n  i = i + 1\nflatline\ntrace encode n\n"
    assert "digits" in fails(source).message
