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


def test_bitwise_truth_table_operations():
    assert run("trace 6 mask 3\n") == "2\n"
    assert run("trace 6 merge 3\n") == "7\n"
    assert run("trace 6 flip 3\n") == "5\n"
    assert run("trace invert 5\n") == "-6\n"


def test_bitwise_shifts():
    assert run("trace 3 uplink 2\n") == "12\n"
    assert run("trace 13 downlink 2\n") == "3\n"
    assert run("trace -5 downlink 1\n") == "-3\n"


def test_bitwise_precedence():
    assert run("trace 1 merge 2 mask 4\n") == "1\n"
    assert run("trace 1 uplink 2 + 1\n") == "8\n"


@pytest.mark.parametrize(
    "source",
    [
        "trace true mask 1\n",
        "trace 1 merge false\n",
        "trace 1 flip true\n",
        "trace invert false\n",
        "trace 1 uplink true\n",
        "trace 1 downlink false\n",
    ],
)
def test_bitwise_operators_require_integers(source):
    error = fails(source)
    assert "integer" in error.message


def test_shifts_reject_negative_counts():
    error = fails("trace 1 uplink -1\n")
    assert "negative" in error.message
