"""Stage 7 — running list programs end to end."""

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


def test_a_list_traces():
    assert run("trace [1, 2, 3]\n") == "[1, 2, 3]\n"


def test_an_empty_list_traces():
    assert run("trace []\n") == "[]\n"


def test_indexing_reads_an_element():
    assert run('construct xs = ["a", "b"]\ntrace xs[1]\n') == "b\n"


def test_element_assignment_writes():
    assert run("construct xs = [1, 2]\nxs[0] = 9\ntrace xs[0]\n") == "9\n"


def test_element_assignment_is_visible_through_an_alias():
    # Reference semantics: this is the observable consequence of S7-1.
    source = (
        "construct xs = [1]\n"
        "construct ys = xs\n"
        "xs[0] = 9\n"
        "trace ys[0]\n"
    )
    assert run(source) == "9\n"


def test_an_agent_mutates_the_caller_s_list():
    source = (
        "agent bump(zs)\n"
        "  zs[0] = zs[0] + 1\n"
        "flatline\n"
        "construct xs = [1]\n"
        "bump(xs)\n"
        "trace xs[0]\n"
    )
    assert run(source) == "2\n"


def test_length_of_a_list():
    assert run("trace length [1, 2, 3]\n") == "3\n"


def test_length_of_a_string():
    assert run('trace length "Neo"\n') == "3\n"


def test_length_of_an_empty_list_and_string():
    assert run('trace length []\ntrace length ""\n') == "0\n0\n"


def test_concatenation_produces_a_new_list():
    assert run("trace [1] + [2]\n") == "[1, 2]\n"


def test_concatenation_does_not_mutate_either_operand():
    source = (
        "construct xs = [1]\n"
        "construct ys = xs + [2]\n"
        "trace length xs\n"
        "trace length ys\n"
    )
    assert run(source) == "1\n2\n"


def test_lists_compare_structurally_at_runtime():
    assert run("trace [1, 2] == [1, 2]\n") == "true\n"
    assert run("trace [1] != [2]\n") == "true\n"


def test_a_bool_never_equals_an_int_inside_a_list_at_runtime():
    # The end-to-end form of Task 8's central case.
    error = fails("trace [1] == [true]\n")
    assert "cannot compare integer with boolean" in error.message
    assert error.line == 1


def test_walking_a_list_with_dejavu():
    source = (
        'construct crew = ["Neo", "Trinity"]\n'
        "construct n = 0\n"
        "dejavu n < length crew\n"
        "  trace crew[n]\n"
        "  n = n + 1\n"
        "flatline\n"
    )
    assert run(source) == "Neo\nTrinity\n"


def test_tracing_a_cyclic_list_says_what_is_wrong():
    # NOT "expression is nested too deeply", which is what the naive
    # implementation reports and which is false — nothing is nested.
    error = fails("construct xs = [1]\nxs[0] = xs\ntrace xs\n")
    assert "cycle" in error.message.lower()
    assert "nested too deeply" not in error.message
    assert error.line == 3
