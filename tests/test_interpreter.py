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
    """Run a program and return its final environment."""
    interpreter = Interpreter(out=io.StringIO())
    interpreter.run(parse(lex(source)))
    return interpreter.environment


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


def test_a_fresh_interpreter_starts_with_an_empty_environment():
    # `construct` does not exist until Task 3, so this task can only assert
    # the empty case. Task 3's test_environment_holds_every_declared_name
    # covers a populated environment.
    assert env("trace 1\n") == {}


def test_construct_declares_and_name_reads_back():
    assert output("construct x = 5\ntrace x\n") == "5\n"


def test_assignment_updates_an_existing_name():
    assert output("construct x = 1\nx = 2\ntrace x\n") == "2\n"


def test_environment_holds_every_declared_name():
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
    assert output("trace 7 / 2\n") == "3\n"
    assert output("trace -7 / 2\n") == "-3\n"
    assert output("trace 7 / -2\n") == "-3\n"


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


def test_arithmetic_errors_report_the_operator_position():
    with pytest.raises(RuntimeErrorML) as excinfo:
        output("trace 1 + true\n")
    assert excinfo.value.line == 1
    assert excinfo.value.column == 9
