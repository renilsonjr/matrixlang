"""Stage 9 — running logical expressions."""

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


# --- unplug -------------------------------------------------------------


def test_unplug_negates():
    assert run("trace unplug true\n") == "false\n"
    assert run("trace unplug false\n") == "true\n"


def test_unplug_over_a_comparison():
    assert run("trace unplug 1 == 2\n") == "true\n"
    assert run("trace unplug 1 == 1\n") == "false\n"


def test_unplug_nests_at_runtime():
    assert run("trace unplug unplug true\n") == "true\n"


def test_unplug_in_a_condition():
    source = 'redpill unplug false\n  trace "yes"\nflatline\n'
    assert run(source) == "yes\n"


def test_unplug_requires_a_boolean():
    assert fails("trace unplug 1\n").message == "'unplug' takes a boolean, got integer"
    assert (
        fails('trace unplug "a"\n').message == "'unplug' takes a boolean, got string"
    )


def test_unplug_carries_a_position():
    error = fails("trace unplug 1\n")
    assert error.line == 1
    assert error.column >= 1
