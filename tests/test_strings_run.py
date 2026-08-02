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


# --- Reading a character ------------------------------------------------


def test_a_string_can_be_indexed():
    assert run('trace "Neo"[0]\n') == "N\n"
    assert run('trace "Neo"[2]\n') == "o\n"


def test_a_character_is_a_one_character_string():
    # There is no character type. `s[0]` is a string, so it can be
    # concatenated, compared and measured like any other.
    assert run('trace "Neo"[0] + "eo"\n') == "Neo\n"
    assert run('trace "Neo"[0] == "N"\n') == "true\n"
    assert run('trace length "Neo"[0]\n') == "1\n"


def test_the_regress_terminates_because_you_stop_asking():
    assert run('trace "Neo"[0][0][0]\n') == "N\n"


def test_indexing_a_name_holding_a_string():
    assert run('construct name = "Neo"\ntrace name[1]\n') == "e\n"


def test_walking_a_string_character_by_character():
    # The program this stage exists for.
    source = (
        'construct name = "Neo"\n'
        "construct n = 0\n"
        "dejavu n < length name\n"
        "  trace name[n]\n"
        "  n = n + 1\n"
        "flatline\n"
    )
    assert run(source) == "N\ne\no\n"


def test_a_string_inside_a_list_can_be_indexed():
    assert run('construct xs = ["Neo"]\ntrace xs[0][1]\n') == "e\n"


# --- Read errors, shared with lists -------------------------------------


def test_indexing_past_the_end_of_a_string_says_string():
    error = fails('trace "Neo"[5]\n')
    assert error.message == "index 5 is past the end of a string of length 3"


def test_the_bounds_message_differs_from_the_list_one_only_by_the_noun():
    # They come from the same _check_index. Asserting them together is
    # what stops a future edit from forking one and not the other.
    string_error = fails('trace "Neo"[5]\n').message
    list_error = fails("construct xs = [1, 2, 3]\ntrace xs[5]\n").message
    assert string_error == "index 5 is past the end of a string of length 3"
    assert list_error == "index 5 is past the end of a list of length 3"
    assert string_error.replace("string", "list") == list_error


def test_a_negative_string_index_is_an_error():
    assert (
        fails('trace "Neo"[-1]\n').message
        == "an index cannot be negative — use xs[length xs - 1]"
    )


def test_a_non_integer_string_index_is_an_error():
    assert (
        fails('trace "Neo"["a"]\n').message
        == "an index must be an integer, got string"
    )


def test_indexing_an_empty_string_is_an_error():
    assert (
        fails('trace ""[0]\n').message
        == "index 0 is past the end of a string of length 0"
    )


def test_indexing_a_boolean_is_still_an_error():
    assert fails("trace true[0]\n").message == "cannot index boolean"
