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


def test_tracing_a_mutual_cycle_also_says_cycle():
    # a[0] is b and b[0] is a: neither list literally contains itself, but
    # walking either one from `trace a` still revisits an id already on
    # the path. This is exactly why the diagnostic says "contains a
    # cycle" rather than "contains itself" -- the self-referential case
    # above would be satisfied by either wording, this one would not.
    source = (
        "construct a = [1]\n"
        "construct b = [2]\n"
        "a[0] = b\n"
        "b[0] = a\n"
        "trace a\n"
    )
    error = fails(source)
    assert "cycle" in error.message.lower()
    assert error.line == 5


# --- Errors ----------------------------------------------------------------


def test_indexing_past_the_end_reports_both_numbers():
    error = fails("construct xs = [1, 2]\ntrace xs[5]\n")
    assert "5" in error.message and "2" in error.message
    assert error.line == 2


def test_a_negative_index_suggests_the_idiom():
    error = fails("construct xs = [1]\ntrace xs[-1]\n")
    assert "length xs - 1" in error.message


def test_a_non_integer_index_is_an_error():
    error = fails('construct xs = [1]\ntrace xs["a"]\n')
    assert "must be an integer" in error.message


def test_indexing_a_non_list_is_an_error():
    error = fails("construct n = 1\ntrace n[0]\n")
    assert "cannot index integer" in error.message


def test_indexing_an_empty_list_is_an_error():
    error = fails("construct xs = []\ntrace xs[0]\n")
    assert "length 0" in error.message


def test_adding_a_list_to_an_integer_is_an_error():
    # Asserting the exact message, not just that both words appear
    # somewhere in it: "left operand must be an integer, got list" (the
    # arithmetic fallback this test exists to rule out) also contains both
    # "list" and "integer", so a substring check cannot tell the correct
    # message from the wrong one. Only the exact string can.
    error = fails("trace [1] + 2\n")
    assert error.message == "cannot add list and integer"


def test_adding_an_integer_to_a_list_is_an_error():
    error = fails("trace 2 + [1]\n")
    assert error.message == "cannot add integer and list"


def test_length_of_an_integer_is_an_error():
    error = fails("trace length 5\n")
    assert "'length' takes a list, a string or a dictionary" in error.message


def test_length_of_a_boolean_is_an_error():
    error = fails("trace length true\n")
    assert "boolean" in error.message


def test_assigning_past_the_end_is_an_error():
    error = fails("construct xs = [1]\nxs[3] = 9\n")
    assert "past the end" in error.message
    assert error.line == 2


def test_the_write_path_index_error_points_at_the_index_not_the_statement():
    # IndexAssign used to pass `stmt` to the bounds helpers, anchoring
    # every error at the statement's own start regardless of where the
    # index expression actually sits. `xs[3]` begins at column 3 ('x' is
    # column 1) so the index literal '3' sits at column 4 — not column 1,
    # which is where the statement itself starts.
    error = fails("construct xs = [1]\nxs[3] = 9\n")
    assert error.column == 4


def test_every_list_error_carries_a_line_and_a_column():
    for source in [
        "construct xs = []\ntrace xs[0]\n",
        "trace length 5\n",
        "trace [1] + 2\n",
        "construct xs = [1]\nxs[9] = 1\n",
    ]:
        error = fails(source)
        assert error.line >= 1
        assert error.column >= 1
