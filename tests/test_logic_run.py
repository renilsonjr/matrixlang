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
    assert fails("trace unplug 1\n").message == "'unplug' takes a boolean, got number"
    assert (
        fails('trace unplug "a"\n').message == "'unplug' takes a boolean, got string"
    )


def test_unplug_carries_a_position():
    # Measured directly from a real run: "trace unplug 1\n" places the
    # 'u' of unplug at column 7 (t-r-a-c-e-space = 6 characters, then
    # unplug starts). unplug reports the OPERATOR's position (expr.column
    # in interpreter.py), not the operand's — see the comment in
    # interpreter.py contrasting this with splice/fork.
    error = fails("trace unplug 1\n")
    assert (error.line, error.column) == (1, 7)


# --- splice and fork ----------------------------------------------------


def test_splice_is_and():
    assert run("trace true splice true\n") == "true\n"
    assert run("trace true splice false\n") == "false\n"
    assert run("trace false splice true\n") == "false\n"
    assert run("trace false splice false\n") == "false\n"


def test_fork_is_or():
    assert run("trace true fork true\n") == "true\n"
    assert run("trace true fork false\n") == "true\n"
    assert run("trace false fork true\n") == "true\n"
    assert run("trace false fork false\n") == "false\n"


def test_they_compose_with_comparisons():
    assert run("trace 1 < 2 splice 3 > 2\n") == "true\n"
    assert run("trace 1 > 2 fork 3 > 2\n") == "true\n"


def test_unplug_composes_with_them():
    # With both operands true, (unplug true) splice true and
    # unplug (true splice true) are BOTH false -- the pair could not
    # distinguish the two groupings. With both false they disagree:
    # (unplug false) splice false is true splice false = false, while
    # unplug (false splice false) is unplug false = true. Only operands
    # that make the groupings disagree can prove which one the
    # unparenthesised form actually uses.
    assert run("trace unplug false splice false\n") == "false\n"
    assert run("trace unplug (false splice false)\n") == "true\n"


# --- Short-circuit: the reason this stage exists ------------------------


def test_the_bounded_search_does_not_run_off_the_end():
    # THE test for this task. The target is absent from crew, so the
    # search runs all the way to n == length crew. Without short-circuit,
    # crew[n] is evaluated at that boundary and the program dies with
    # "index 3 is past the end of a list of length 3" — an error that
    # looks like a bug in the program rather than in the language.
    source = (
        'construct crew = ["Neo", "Trinity", "Tank"]\n'
        "construct n = 0\n"
        'dejavu n < length crew splice crew[n] != "Cypher"\n'
        "  n = n + 1\n"
        "flatline\n"
        "trace n\n"
    )
    assert run(source) == "3\n"


def test_a_search_finds_a_target_at_the_last_index():
    # Not a short-circuit test: the target sits one before the boundary,
    # so crew[n] never gets read out of range even without short-circuit.
    # This is a plain regression test that the search itself lands on the
    # right index.
    source = (
        'construct crew = ["Neo", "Trinity", "Tank"]\n'
        "construct n = 0\n"
        'dejavu n < length crew splice crew[n] != "Tank"\n'
        "  n = n + 1\n"
        "flatline\n"
        "trace n\n"
    )
    assert run(source) == "2\n"


def test_a_search_that_finds_nothing_still_terminates():
    source = (
        'construct crew = ["Neo", "Trinity"]\n'
        "construct n = 0\n"
        'dejavu n < length crew splice crew[n] != "Cypher"\n'
        "  n = n + 1\n"
        "flatline\n"
        "trace n == length crew\n"
    )
    assert run(source) == "true\n"


def test_splice_does_not_evaluate_the_right_side_when_the_left_is_false():
    # An observable side effect on the right proves the short circuit
    # rather than inferring it.
    source = (
        "agent shout()\n"
        '  trace "evaluated"\n'
        "  jackout true\n"
        "flatline\n"
        "trace false splice shout()\n"
    )
    assert run(source) == "false\n"


def test_fork_does_not_evaluate_the_right_side_when_the_left_is_true():
    source = (
        "agent shout()\n"
        '  trace "evaluated"\n'
        "  jackout false\n"
        "flatline\n"
        "trace true fork shout()\n"
    )
    assert run(source) == "true\n"


def test_the_right_side_does_run_when_it_is_needed():
    source = (
        "agent shout()\n"
        '  trace "evaluated"\n'
        "  jackout true\n"
        "flatline\n"
        "trace true splice shout()\n"
    )
    assert run(source) == "evaluated\ntrue\n"


# --- The asymmetry short-circuit creates --------------------------------


def test_an_unevaluated_operand_is_never_type_checked():
    # Whether a type error appears depends on a VALUE, which is unlike
    # every other operator here. Python, Java and C all behave this way;
    # it is the price of the guard idiom above. Both directions are
    # pinned so neither can drift.
    assert run("trace false splice 1\n") == "false\n"
    assert fails("trace true splice 1\n").message == "'splice' takes booleans, got number"

    assert run("trace true fork 1\n") == "true\n"
    assert fails("trace false fork 1\n").message == "'fork' takes booleans, got number"


def test_a_non_boolean_left_operand_is_always_an_error():
    assert fails("trace 1 splice true\n").message == "'splice' takes booleans, got number"
    assert fails('trace "a" fork true\n').message == "'fork' takes booleans, got string"


def test_the_error_carries_a_position():
    # Measured directly from a real run: "trace 1 splice true\n" places
    # the failing operand '1' at column 7 (t-r-a-c-e-space = 6
    # characters). splice/fork report the OPERAND's position
    # (node.column in _require_bool), not the operator's.
    error = fails("trace 1 splice true\n")
    assert (error.line, error.column) == (1, 7)
