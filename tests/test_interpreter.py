import io

import pytest

from matrixlang.errors import RuntimeErrorML
from matrixlang.interpreter import Interpreter, run
from matrixlang.lexer import lex
from matrixlang.parser import parse


def output(source: str) -> str:
    """Run a program and return everything it printed."""
    buffer = io.StringIO()
    run(parse(lex(source)), out=buffer)
    return buffer.getvalue()


def env(source: str) -> dict:
    """Run a program and return its final global scope.

    Stage 6 replaced the flat dict with a chain of Environments, so this
    reaches for the globals rather than the whole of scope — which is now
    a tree rather than a dictionary.
    """
    interpreter = Interpreter(out=io.StringIO())
    interpreter.run(parse(lex(source)))
    return interpreter.globals.values


def test_trace_prints_an_integer_with_a_newline():
    assert output("trace 7\n") == "7\n"


def test_trace_prints_a_string_without_quotes():
    assert output('trace "wake up, Neo"\n') == "wake up, Neo\n"


def test_trace_prints_booleans_in_the_language_s_spelling():
    assert output("trace true\ntrace false\n") == "true\nfalse\n"


def test_several_traces_appear_in_order():
    assert output("trace 1\ntrace 2\ntrace 3\n") == "1\n2\n3\n"


def test_an_empty_program_prints_nothing():
    assert output("") == ""


def test_comments_do_not_execute():
    assert output("# just a comment\ntrace 1  # and another\n") == "1\n"


def test_a_fresh_interpreter_starts_with_an_empty_global_scope():
    # `construct` does not exist until Task 3, so this task can only assert
    # the empty case. Task 3's test_environment_holds_every_declared_name
    # covers a populated environment.
    assert env("trace 1\n") == {}


def test_construct_declares_and_name_reads_back():
    assert output("construct x = 5\ntrace x\n") == "5\n"


def test_assignment_updates_an_existing_name():
    assert output("construct x = 1\nx = 2\ntrace x\n") == "2\n"


def test_the_global_scope_holds_every_declared_name():
    assert env('construct a = 1\nconstruct b = "two"\nconstruct c = true\n') == {
        "a": 1,
        "b": "two",
        "c": True,
    }


def test_redeclaring_a_name_is_an_error():
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("construct x = 1\nconstruct x = 2\n")
    assert "already declared" in str(excinfo.value)
    assert excinfo.value.line == 2


def test_assigning_to_an_undeclared_name_is_an_error():
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("x = 1\n")
    assert "not declared" in str(excinfo.value)
    assert excinfo.value.line == 1


def test_reading_an_undeclared_name_is_an_error():
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("trace nope\n")
    assert "not declared" in str(excinfo.value)
    assert excinfo.value.column == 7


def test_a_name_may_hold_a_different_type_after_assignment():
    # Dynamic typing, spec §5: no declared types, so this is legal.
    assert output('construct x = 1\nx = "now a string"\ntrace x\n') == "now a string\n"


def test_integer_arithmetic():
    assert output("trace 2 + 3 * 4\n") == "14\n"
    assert output("trace (2 + 3) * 4\n") == "20\n"
    assert output("trace 10 - 3 - 2\n") == "5\n"


def test_division_truncates_toward_zero_not_floor():
    # Python's // floors: -7 // 2 == -4. Spec §5 requires -3.
    # All four sign combinations. (-,-) matters most: it is the case that
    # still looks right if someone "simplifies" the sign logic back to //,
    # because -7 // -2 == 3 agrees with truncation. Assert it anyway, so the
    # test pins the rule rather than two-thirds of it.
    assert output("trace 7 / 2\n") == "3\n"
    assert output("trace -7 / 2\n") == "-3\n"
    assert output("trace 7 / -2\n") == "-3\n"
    assert output("trace -7 / -2\n") == "3\n"


def test_division_by_zero_is_a_runtime_error():
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("trace 1 / 0\n")
    assert "divide by zero" in str(excinfo.value)


def test_unary_minus():
    assert output("trace -5\n") == "-5\n"
    assert output("construct x = 3\ntrace -x\n") == "-3\n"


def test_string_concatenation():
    assert output('trace "wake up, " + "Neo"\n') == "wake up, Neo\n"


def test_mixing_a_string_and_an_integer_is_an_error():
    with pytest.raises(RuntimeErrorML) as excinfo:
        output('trace "count: " + 1\n')
    assert "string" in str(excinfo.value)
    assert "integer" in str(excinfo.value)


def test_booleans_are_not_integers_in_arithmetic():
    # THE bool-is-an-int trap. Python would evaluate True + 1 to 2.
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("trace true + 1\n")
    assert "boolean" in str(excinfo.value)


def test_booleans_are_not_integers_under_unary_minus():
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("trace -true\n")
    assert "boolean" in str(excinfo.value)


def test_ordering_type_errors_point_at_the_offending_operand():
    # 'trace true < 1': '<' is the operator, at column 12 (not the operand at column 7).
    # Matches `cannot compare` and `cannot add`, which report the operator's position.
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("trace true < 1\n")
    assert excinfo.value.line == 1
    assert excinfo.value.column == 12


def test_integer_equality_and_ordering():
    assert output("trace 1 == 1\ntrace 1 != 1\n") == "true\nfalse\n"
    assert output("trace 1 < 2\ntrace 2 <= 2\ntrace 3 > 4\ntrace 4 >= 4\n") == (
        "true\ntrue\nfalse\ntrue\n"
    )


def test_string_and_boolean_equality():
    assert output('trace "a" == "a"\ntrace "a" != "b"\n') == "true\ntrue\n"
    assert output("trace true == true\ntrace true != false\n") == "true\ntrue\n"


def test_comparing_across_types_is_an_error():
    with pytest.raises(RuntimeErrorML) as excinfo:
        output('trace 1 == "1"\n')
    assert "integer" in str(excinfo.value)
    assert "string" in str(excinfo.value)


def test_true_does_not_equal_one():
    # Python says True == 1. MatrixLang says these are different types.
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("trace true == 1\n")
    assert "boolean" in str(excinfo.value)


def test_ordering_booleans_is_an_error():
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("trace true < false\n")
    assert excinfo.value.message == "cannot order boolean with boolean"


def test_redpill_takes_the_then_branch():
    assert output("redpill true\n  trace 1\nflatline\n") == "1\n"


def test_redpill_skips_an_untaken_branch_with_no_else():
    assert output("redpill false\n  trace 1\nflatline\n") == ""


def test_bluepill_takes_the_else_branch():
    source = "redpill false\n  trace 1\nbluepill\n  trace 2\nflatline\n"
    assert output(source) == "2\n"


def test_nested_conditionals():
    source = (
        "construct x = 2\n"
        "redpill x > 1\n"
        "  redpill x > 5\n"
        "    trace 100\n"
        "  bluepill\n"
        "    trace 50\n"
        "  flatline\n"
        "flatline\n"
    )
    assert output(source) == "50\n"


def test_a_non_boolean_condition_is_an_error():
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("redpill 1\n  trace 1\nflatline\n")
    assert "must be a boolean" in str(excinfo.value)
    assert "integer" in str(excinfo.value)


def test_a_string_condition_is_an_error():
    with pytest.raises(RuntimeErrorML) as excinfo:
        output('dejavu "yes"\n  trace 1\nflatline\n')
    assert "must be a boolean" in str(excinfo.value)


def test_a_loop_that_never_runs():
    assert output("dejavu false\n  trace 1\nflatline\n") == ""


def test_counting_loop_runs():
    # THE parent spec's Stage 3 done-when criterion. At this point the
    # language exists.
    source = (
        "construct n = 1\n"
        "dejavu n <= 10\n"
        "  trace n\n"
        "  n = n + 1\n"
        "flatline\n"
    )
    assert output(source) == "".join(f"{i}\n" for i in range(1, 11))


def test_the_stage_3_demo_program_runs():
    source = (
        "construct n = 0\n"
        'construct name = "Neo"\n'
        "\n"
        "dejavu n < 3\n"
        "  redpill n == 1\n"
        '    trace "wake up, " + name\n'
        "  bluepill\n"
        "    trace n\n"
        "  flatline\n"
        "  n = n + 1\n"
        "flatline\n"
    )
    assert output(source) == "0\nwake up, Neo\n2\n"


def test_construct_inside_a_loop_body_fails_on_the_second_iteration():
    # Falls straight out of spec §5: one flat environment, and re-declaring an
    # existing name is an error. Pinned because it is a sharp emergent
    # interaction and because it is a FEATURE — a future "helpful" fix that let
    # the second iteration re-declare would violate §5.
    with pytest.raises(RuntimeErrorML) as excinfo:
        output(
            "construct n = 0\n"
            "dejavu n < 3\n"
            "  construct m = n\n"
            "  n = n + 1\n"
            "flatline\n"
        )
    assert "already declared" in str(excinfo.value)
    assert excinfo.value.line == 3


def test_a_name_declared_inside_a_block_outlives_it():
    # The positive observable of "blocks do not introduce scope" (spec §5).
    assert output("redpill true\n  construct inner = 9\nflatline\ntrace inner\n") == "9\n"


def test_a_very_deep_expression_is_a_language_error_not_a_crash():
    # A ~900-deep chain kills the process with a raw RecursionError today,
    # which in the REPL ends the session (feed catches MatrixLangError only).
    # Built programmatically: lex/parse would hit their own recursion first.
    from matrixlang.nodes import NumberLiteral, Program, Trace, Unary
    from matrixlang.tokens import TokenType

    expr = NumberLiteral(1)
    for _ in range(50_000):
        expr = Unary(TokenType.MINUS, expr)
    program = Program([Trace(expr, line=3, column=7)])
    with pytest.raises(RuntimeErrorML) as excinfo:
        run(program, out=io.StringIO())
    assert "nested too deeply" in str(excinfo.value)
    assert excinfo.value.line == 3
    assert excinfo.value.column == 7


def test_type_errors_point_at_the_offending_operand():
    # 'trace 1 + true': the operator is at column 9, 'true' at column 11.
    # The operand is what the reader must fix, so that is the position.
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("trace 1 + true\n")
    assert excinfo.value.line == 1
    assert excinfo.value.column == 11


def test_unary_type_errors_point_at_the_operand():
    # 'trace -true': '-' at column 7, 'true' at column 8.
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("trace -true\n")
    assert excinfo.value.column == 8


def test_reading_an_undeclared_name_suggests_construct():
    # The Assign error already carries this hint; the Name error did not.
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("trace nope\n")
    assert "use 'construct' first" in str(excinfo.value)
