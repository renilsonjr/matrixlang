"""Stage 8 — strings stop being opaque: ordering, then indexing.

Split from test_lists_run.py the way Stage 6 and Stage 7 each got their
own run-tests file. Nothing here needs new syntax: indexing already
parsed before this stage and failed at runtime.
"""

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


# --- Ordering -----------------------------------------------------------


def test_two_strings_can_be_ordered():
    assert run('trace "Neo" < "Trinity"\n') == "true\n"
    assert run('trace "Trinity" < "Neo"\n') == "false\n"


def test_every_ordering_operator_works_on_strings():
    assert run('trace "a" < "b"\n') == "true\n"
    assert run('trace "a" > "b"\n') == "false\n"
    assert run('trace "a" <= "a"\n') == "true\n"
    assert run('trace "a" >= "b"\n') == "false\n"


def test_ordering_is_codepoint_order_not_alphabetical():
    # THE gotcha. Every uppercase letter sorts before every lowercase one,
    # same as Python, Java and C. Pinned rather than only documented,
    # because documentation drifts and a test does not.
    assert run('trace "a" < "B"\n') == "false\n"
    assert run('trace "B" < "a"\n') == "true\n"


def test_integers_still_order():
    assert run("trace 3 < 5\n") == "true\n"
    assert run("trace 5 <= 5\n") == "true\n"


def test_mixed_operands_report_the_pair_exactly():
    # Exact string, not a substring. The old message ("left operand must
    # be an integer, got string") becomes FALSE once strings are
    # orderable, and a substring check like `"string" in message` would
    # pass against both. That exact failure shipped in Stage 7.
    assert fails('trace "a" < 1\n').message == "cannot order string with integer"
    assert fails('trace 1 < "a"\n').message == "cannot order integer with string"


def test_booleans_are_still_unorderable():
    assert fails("trace true < 5\n").message == "cannot order boolean with integer"
    assert fails("trace true < false\n").message == "cannot order boolean with boolean"


def test_lists_are_still_unorderable():
    # Element-wise ordering needs rules for unequal lengths and mixed
    # element types that the spec deliberately does not give (§8).
    assert fails("trace [1] < [2]\n").message == "cannot order list with list"


def test_the_ordering_error_points_at_the_operator():
    # Matches `cannot compare` and `cannot add`, which both report the
    # operator's position rather than an operand's.
    error = fails('trace "a" < 1\n')
    assert (error.line, error.column) == (1, 11)


def test_arithmetic_still_requires_integers():
    # _require_int has four call sites and only the two ordering ones
    # changed. These must not have moved.
    assert 'must be an integer' in fails('trace 1 - "a"\n').message
    assert 'must be an integer' in fails('trace -"a"\n').message
    assert 'must be an integer' in fails('trace "a" * 2\n').message
