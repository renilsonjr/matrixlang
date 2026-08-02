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


# --- Writing to a string is refused -------------------------------------


def test_assigning_to_a_character_explains_rather_than_refusing_bare():
    # The asymmetry with lists is real (xs[0] = 9 works) so the message
    # has to teach it, not just say no.
    error = fails('construct s = "Neo"\ns[0] = "X"\n')
    assert error.message == "a string cannot be changed — build a new one with +"


def test_assigning_to_a_character_never_raises_a_python_exception():
    # THE test for this task. Widening this guard the way _element's was
    # widened lets s[0] = "X" reach Python's item assignment and raise
    # TypeError: 'str' object does not support item assignment — a Python
    # exception name escaping into a .rain program, which technical
    # overview §6 says cannot happen.
    with pytest.raises(RuntimeErrorML):
        run('construct s = "Neo"\ns[0] = "X"\n')


def test_the_refusal_carries_a_position():
    error = fails('construct s = "Neo"\ns[0] = "X"\n')
    assert error.line == 2
    assert error.column >= 1


def test_assigning_to_a_string_literal_is_refused_at_parse_time():
    # Verified: this never reaches the interpreter. The statement
    # dispatcher requires an IDENT to begin an assignment, so a literal
    # target is rejected by the parser with "expected a statement, found
    # '"Neo"'". Pinned so a future parser change cannot silently route it
    # into the branch this task edits without anyone noticing.
    from matrixlang.errors import ParseError

    with pytest.raises(ParseError) as caught:
        run('"Neo"[0] = "X"\n')
    assert "expected a statement" in caught.value.message


def test_a_nested_string_inside_a_list_is_still_immutable():
    error = fails('construct xs = ["Neo"]\nxs[0][0] = "X"\n')
    assert error.message == "a string cannot be changed — build a new one with +"


def test_assigning_to_a_list_element_still_works():
    # The branch this task edits is the one lists go through. Regression
    # guard: do not break Stage 7 while adding the string case.
    assert run("construct xs = [1, 2]\nxs[0] = 9\ntrace xs[0]\n") == "9\n"


def test_assigning_to_a_non_indexable_still_says_cannot_index():
    assert fails("construct n = 1\nn[0] = 2\n").message == "cannot index integer"
