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


def test_numbers_still_order():
    assert run("trace 3 < 5\n") == "true\n"
    assert run("trace 5 <= 5\n") == "true\n"


def test_mixed_operands_report_the_pair_exactly():
    # Exact string, not a substring. The old message ("left operand must
    # be a number, got string") becomes FALSE once strings are
    # orderable, and a substring check like `"string" in message` would
    # pass against both. That exact failure shipped in Stage 7.
    assert fails('trace "a" < 1\n').message == "cannot order string with number"
    assert fails('trace 1 < "a"\n').message == "cannot order number with string"


def test_booleans_are_still_unorderable():
    assert fails("trace true < 5\n").message == "cannot order boolean with number"
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


def test_arithmetic_still_requires_numbers():
    # _require_number has three call sites (unary minus, and the two
    # arithmetic operands — ordering moved off it in this stage). These
    # must not have moved.
    assert 'must be a number' in fails('trace 1 - "a"\n').message
    assert 'must be a number' in fails('trace -"a"\n').message
    assert 'must be a number' in fails('trace "a" * 2\n').message


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
    # The placeholder names the type: a string sees `s`, not `xs` — telling
    # a string user to fix their code with list vocabulary would be wrong.
    assert (
        fails('trace "Neo"[-1]\n').message
        == "an index cannot be negative — use s[length s - 1]"
    )


def test_a_negative_list_index_is_an_error():
    # Pinned alongside the string case above so the two cannot drift apart
    # again: this one keeps the original `xs` placeholder.
    assert (
        fails("construct xs = [1, 2, 3]\ntrace xs[-1]\n").message
        == "an index cannot be negative — use xs[length xs - 1]"
    )


def test_a_non_number_string_index_is_an_error():
    assert (
        fails('trace "Neo"["a"]\n').message
        == "an index must be a whole number, got string"
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
    assert fails("construct n = 1\nn[0] = 2\n").message == "cannot index number"


# --- Fold, trim, cleave ---------------------------------------------------


def test_fold_lower_cases():
    assert run('trace fold "Mouse"\n') == "mouse\n"


def test_fold_leaves_a_lower_case_string_alone():
    assert run('trace fold "mouse"\n') == "mouse\n"


def test_fold_is_lower_not_casefold():
    # The distinction is real and the NAME points the wrong way:
    # "STRAßE".lower() is "straße" but .casefold() is "strasse". The
    # translator maps Python's .lower() onto fold, so fold must be
    # .lower() or the two disagree on exactly this input.
    assert run('trace fold "STRAßE"\n') == "straße\n"


def test_trim_removes_whitespace_from_both_ends():
    assert run('trace "[" + trim "  hi  " + "]"\n') == "[hi]\n"


def test_trim_removes_newlines_too():
    assert run('trace "[" + trim "\\n hi \\n" + "]"\n') == "[hi]\n"


def test_trim_is_pythons_strip_not_decodes_ascii_only_one():
    # U+00A0 is whitespace to str.strip() but is NOT in string.whitespace,
    # which is what interpreter._DECODE_SPACE is. If trim were built on
    # _DECODE_SPACE the U+00A0s come back still attached, and a
    # translated program disagrees with the Python it came from.
    #
    # Written as an escape, never as a literal: a raw U+00A0 in a source
    # file is invisible, and the next editor to touch the line would
    # silently turn it into a plain space and delete the only thing this
    # test proves.
    nbsp = "\u00a0"
    source = f'trace "[" + trim "{nbsp} hi {nbsp}" + "]"\n'
    assert run(source) == "[hi]\n"


def test_trim_of_a_blank_string_is_empty():
    assert run('trace "[" + trim "   " + "]"\n') == "[]\n"


def test_cleave_splits_on_a_separator():
    assert run('trace "a,b,c" cleave ","\n') == '["a", "b", "c"]\n'


def test_cleave_keeps_empty_pieces():
    assert run('trace "a,,b" cleave ","\n') == '["a", "", "b"]\n'


def test_cleave_of_an_empty_string_is_one_empty_piece():
    # CPython: "".split(",") == [""], NOT []. Verified, not assumed.
    assert run('trace "" cleave ","\n') == '[""]\n'


def test_cleave_with_the_separator_absent_gives_the_whole_string():
    assert run('trace "abc" cleave ","\n') == '["abc"]\n'


def test_cleave_takes_a_multi_character_separator():
    assert run('trace "a::b" cleave "::"\n') == '["a", "b"]\n'


def test_cleave_with_an_empty_separator_is_an_error():
    # CPython raises ValueError("empty separator"). That must arrive as a
    # positioned MatrixLang error, not a Python exception escaping the
    # interpreter -- site/glue.py's run() promises never to raise.
    error = fails('trace "abc" cleave ""\n')
    assert "'cleave'" in error.message
    assert "separator" in error.message


@pytest.mark.parametrize(
    "operand,name",
    [
        ("1", "number"),
        ("true", "boolean"),
        ('["a"]', "list"),
        ('{"a": 1}', "dictionary"),
    ],
)
def test_fold_refuses_every_non_string(operand, name):
    error = fails(f"trace fold {operand}\n")
    assert error.message == f"'fold' takes a string, got {name}"


@pytest.mark.parametrize(
    "operand,name",
    [
        ("1", "number"),
        ("true", "boolean"),
        ('["a"]', "list"),
        ('{"a": 1}', "dictionary"),
    ],
)
def test_trim_refuses_every_non_string(operand, name):
    error = fails(f"trace trim {operand}\n")
    assert error.message == f"'trim' takes a string, got {name}"


@pytest.mark.parametrize(
    "left,name", [("1", "number"), ("true", "boolean"), ('["a"]', "list")]
)
def test_cleave_refuses_a_non_string_on_the_left(left, name):
    error = fails(f'trace {left} cleave ","\n')
    assert error.message == f"'cleave' takes a string, got {name}"


@pytest.mark.parametrize(
    "right,name", [("1", "number"), ("true", "boolean"), ('["a"]', "list")]
)
def test_cleave_refuses_a_non_string_separator(right, name):
    error = fails(f'trace "a,b" cleave {right}\n')
    assert error.message == f"'cleave' needs a string separator, got {name}"


def test_a_type_error_carries_the_operators_position():
    error = fails("trace 1\ntrace fold 2\n")
    assert error.line == 2


def test_the_three_compose_in_one_program():
    # `fold trim "  Mouse  " cleave "s"` is
    # `(fold (trim "  Mouse  ")) cleave "s"`. CPython:
    # "  Mouse  ".strip().lower().split("s") == ["mou", "e"].
    assert run('trace fold trim "  Mouse  " cleave "s"\n') == '["mou", "e"]\n'


def test_a_case_insensitive_comparison_works():
    source = 'construct a = "Mouse"\nconstruct b = "MOUSE"\ntrace fold a == fold b\n'
    assert run(source) == "true\n"
