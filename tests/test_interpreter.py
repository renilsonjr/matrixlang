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


def test_ordering_type_errors_point_at_the_operator():
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


def _run_with_input(source_text: str, lines: list[str]) -> list[str]:
    """Run a program with supplied input, returning its output lines."""
    import io

    from matrixlang.input import ListSource
    from matrixlang.interpreter import Interpreter
    from matrixlang.lexer import lex
    from matrixlang.parser import parse

    out = io.StringIO()
    Interpreter(out=out, source=ListSource(lines)).run(parse(lex(source_text)))
    return out.getvalue().splitlines()


def test_jackin_reads_a_line_as_text():
    assert _run_with_input("trace jackin\n", ["Neo"]) == ["Neo"]


def test_jackin_reads_successive_lines_in_order():
    program = "trace jackin\ntrace jackin\n"
    assert _run_with_input(program, ["Neo", "Trinity"]) == ["Neo", "Trinity"]


def test_jackin_yields_text_not_a_number():
    # "5" stays text, so concatenation works and arithmetic does not.
    assert _run_with_input('trace jackin + "!"\n', ["5"]) == ["5!"]


def test_running_out_of_input_is_an_error_with_a_position():
    from matrixlang.errors import MatrixLangError

    with pytest.raises(MatrixLangError) as caught:
        _run_with_input("trace jackin\n", [])
    assert "no input left to read" in caught.value.message
    assert caught.value.line == 1


def test_decode_turns_text_into_a_number():
    assert _run_with_input("trace decode jackin + 1\n", ["41"]) == ["42"]


def test_decode_accepts_a_negative_number_and_surrounding_spaces():
    assert _run_with_input("trace decode jackin\n", ["  -3 "]) == ["-3"]


def test_decode_rejects_text_that_is_not_a_number():
    from matrixlang.errors import MatrixLangError

    with pytest.raises(MatrixLangError) as caught:
        _run_with_input("trace decode jackin\n", ["abc"])
    assert "decode" in caught.value.message


def test_decode_rejects_a_float_spelling():
    # The language has integers only.
    from matrixlang.errors import MatrixLangError

    with pytest.raises(MatrixLangError) as caught:
        _run_with_input("trace decode jackin\n", ["5.5"])
    assert "decode" in caught.value.message


def test_decode_rejects_an_underscore_grouped_number():
    # int("1_000") == 1000, but the lexer never lexes "1_000" as a single
    # number token, so decode must not treat it as one either.
    from matrixlang.errors import MatrixLangError

    with pytest.raises(MatrixLangError) as caught:
        _run_with_input("trace decode jackin\n", ["1_000"])
    assert "decode" in caught.value.message


def test_decode_rejects_arabic_indic_digits():
    # int("٣٤٥") == 345, but the lexer's digit set is explicitly ASCII-only.
    from matrixlang.errors import MatrixLangError

    with pytest.raises(MatrixLangError) as caught:
        _run_with_input("trace decode jackin\n", ["٣٤٥"])
    assert "decode" in caught.value.message


def test_decode_rejects_mathematical_digits():
    # int("𝟝") == 5, another Unicode decimal digit outside the ASCII set.
    from matrixlang.errors import MatrixLangError

    with pytest.raises(MatrixLangError) as caught:
        _run_with_input("trace decode jackin\n", ["𝟝"])
    assert "decode" in caught.value.message


def test_decode_rejects_a_value_that_is_already_a_number():
    # Strict like `splice`, which refuses an integer rather than coercing.
    # A decode that passed numbers through would hide a double decode.
    from matrixlang.errors import MatrixLangError

    with pytest.raises(MatrixLangError) as caught:
        _run_with_input("trace decode 5\n", [])
    assert "decode" in caught.value.message


def test_decode_rejects_a_leading_plus_although_it_accepts_a_leading_minus():
    # Asymmetric on purpose, and pinned here so it is a decision rather
    # than an accident: "-3" is how the language itself writes a negative
    # number, while "+3" is a spelling the lexer never produces. §17 of
    # LEARNING-MATRIXLANG says so out loud.
    from matrixlang.errors import MatrixLangError

    assert _run_with_input("trace decode jackin\n", ["-3"]) == ["-3"]
    with pytest.raises(MatrixLangError) as caught:
        _run_with_input("trace decode jackin\n", ["+3"])
    assert "decode" in caught.value.message


def test_decode_rejects_non_ascii_spacing_around_a_number():
    # str.strip() with no argument eats NBSP and the rest of Unicode's
    # spaces, which would let "\xa05" through the same door the digit
    # check exists to shut. See _DECODE_SPACE.
    from matrixlang.errors import MatrixLangError

    with pytest.raises(MatrixLangError) as caught:
        _run_with_input("trace decode jackin\n", ["\xa05"])
    assert "decode" in caught.value.message


def test_decode_reports_an_over_long_digit_string_rather_than_raising():
    # CPython refuses int(str) past sys.int_info.default_max_str_digits
    # (4300). Every character is an ASCII digit, so the check above passes
    # it straight to int(), which raises ValueError -- a raw Python
    # exception escaping the interpreter, out through site/glue.py's
    # run() ("Never raises"), the operator's dry run and the CLI.
    import sys

    from matrixlang.errors import MatrixLangError

    too_long = "9" * (sys.int_info.default_max_str_digits + 1)
    with pytest.raises(MatrixLangError) as caught:
        _run_with_input("trace decode jackin\n", [too_long])
    assert "decode" in caught.value.message
    assert caught.value.line == 1


def test_an_over_long_digit_string_needs_no_input_at_all():
    # Reachable from a literal, so it is not gated behind the input box:
    # anybody typing this into the playground editor hits it.
    import sys

    from matrixlang.errors import MatrixLangError

    too_long = "9" * (sys.int_info.default_max_str_digits + 1)
    with pytest.raises(MatrixLangError):
        _run_with_input(f'trace decode "{too_long}"\n', [])


def test_the_default_source_is_empty_never_stdin():
    # A default that read a terminal would hang validate.py's dry run
    # inside a server request. Empty is the only safe default.
    import io

    from matrixlang.errors import MatrixLangError
    from matrixlang.interpreter import Interpreter
    from matrixlang.lexer import lex
    from matrixlang.parser import parse

    with pytest.raises(MatrixLangError) as caught:
        Interpreter(out=io.StringIO()).run(parse(lex("trace jackin\n")))
    assert "no input left to read" in caught.value.message


def _run(source_text: str) -> list[str]:
    import io

    from matrixlang.interpreter import Interpreter
    from matrixlang.lexer import lex
    from matrixlang.parser import parse

    out = io.StringIO()
    Interpreter(out=out).run(parse(lex(source_text)))
    return out.getvalue().splitlines()


def test_encode_turns_a_number_into_text():
    assert _run('trace "ID: " + encode 42\n') == ["ID: 42"]


def test_encode_handles_negatives_and_zero():
    assert _run('trace encode -3 + "/" + encode 0\n') == ["-3/0"]


def test_encode_agrees_with_what_trace_prints():
    # Necessary but not sufficient. to_display(n) == str(n) for every
    # plain int (values._display's fallback is `return str(value)`), so
    # this passes whether encode calls to_display or just reimplements it
    # with str(). It still catches gross formatting bugs -- a wrong sign,
    # stray quotes, a digit-grouping change -- for free, so it stays. See
    # test_encode_delegates_to_to_display for the test that actually pins
    # the delegation itself.
    for n in ["0", "7", "-3", "1000", "-1000"]:
        (encoded,) = _run(f"trace encode {n}\n")
        (printed,) = _run(f"trace {n}\n")
        assert encoded == printed, f"encode {n} disagreed with trace {n}"


def test_encode_delegates_to_to_display(monkeypatch):
    # The requirement is that `encode` CALLS to_display rather than
    # reimplementing its formatting, so that if to_display's rendering
    # ever changes, encode follows automatically. No black-box test can
    # observe that: to_display(n) == str(n) for every int today, so a
    # reimplementation is indistinguishable from delegation by output
    # alone (see test_encode_agrees_with_what_trace_prints above). This
    # patches to_display where interpreter.py imports it by name -- the
    # only place patching takes effect -- and checks the substitution
    # actually reaches encode's result.
    import matrixlang.interpreter as interpreter_module

    def fake_to_display(value):
        # Strings pass through unchanged so `trace`'s OWN final
        # to_display call -- on encode's already-stringified result --
        # stays invisible here; only encode's internal call on the raw
        # int operand should produce the marker. If encode stopped
        # calling to_display, the marker would never appear and this
        # assertion would see the real digits instead.
        if isinstance(value, str):
            return value
        return "PATCHED"

    monkeypatch.setattr(interpreter_module, "to_display", fake_to_display)
    assert _run("trace encode 42\n") == ["PATCHED"]


def test_decode_of_encode_returns_the_number():
    # The round-trip invariant. The REVERSE does not hold -- decode
    # tolerates whitespace and a leading sign, so it is many-to-one --
    # and the design doc says so; do not add the symmetric test.
    for n in ["0", "7", "-3", "1000"]:
        assert _run(f"trace decode encode {n}\n") == [n]


def test_encode_rejects_text():
    from matrixlang.errors import MatrixLangError

    with pytest.raises(MatrixLangError) as caught:
        _run('trace encode "already text"\n')
    # values.type_name maps str to "string" (see values.py), the same word
    # every other type error in this file uses -- not "text", which is
    # decode's ROLE word for what it wants, never type_name's output for
    # what it got. The brief's literal said "text"; corrected here to match
    # the language's actual vocabulary and this file's own convention.
    assert "'encode' takes a number, got string" in caught.value.message


def test_encode_rejects_a_boolean():
    # Strict like splice, which refuses a non-boolean rather than coercing.
    from matrixlang.errors import MatrixLangError

    with pytest.raises(MatrixLangError) as caught:
        _run("trace encode true\n")
    assert "'encode' takes a number, got boolean" in caught.value.message


def test_encode_rejects_a_list():
    from matrixlang.errors import MatrixLangError

    with pytest.raises(MatrixLangError) as caught:
        _run("trace encode [1, 2]\n")
    assert "'encode' takes a number, got list" in caught.value.message


def test_adding_a_number_to_text_is_still_an_error():
    # encode exists precisely so this stays an error. No implicit coercion.
    from matrixlang.errors import MatrixLangError

    with pytest.raises(MatrixLangError) as caught:
        _run('trace "ID: " + 1\n')
    assert "cannot add" in caught.value.message


# A number with more digits than CPython will render. Squaring is what
# makes it reachable: thirteen doublings of the exponent from 10 is
# 8193 digits, and costs the step budget almost nothing.
_OVER_LONG = """construct n = 10
construct i = 0
dejavu i < 13
  n = n * n
  i = i + 1
flatline
"""


def test_tracing_a_number_too_long_to_render_is_a_language_error():
    # CPython refuses str(int) past 4300 digits with a bare ValueError.
    # Nothing in the language stops a program reaching that, so without a
    # guard the exception leaves the interpreter as a Python traceback --
    # through the CLI, the operator's dry run and site/glue.py's run(),
    # none of which catch anything but MatrixLangError.
    from matrixlang.errors import MatrixLangError

    with pytest.raises(MatrixLangError) as caught:
        _run(_OVER_LONG + "trace n\n")
    assert "cannot display a number longer than 4300 digits" in caught.value.message
    assert caught.value.line == 7


def test_encoding_a_number_too_long_to_render_is_a_language_error():
    # The same ceiling reached through the other door. `trace` is one
    # statement; `encode` is an expression, so it puts the hazard
    # everywhere a value can go. Both report, because the guard lives in
    # values._display rather than in either branch.
    from matrixlang.errors import MatrixLangError

    with pytest.raises(MatrixLangError) as caught:
        _run(_OVER_LONG + "trace encode n\n")
    assert "'encode' got a number too long to write" in caught.value.message
    assert "4300 digits" in caught.value.message


def test_a_number_just_under_the_ceiling_still_traces_and_encodes():
    # The boundary from below, run through the whole language rather than
    # through to_display alone: 4299 digits must still print, and must
    # still encode to text of exactly that length.
    source = """construct n = 1
construct i = 0
dejavu i < 4298
  n = n * 10
  i = i + 1
flatline
trace length encode n
"""
    assert _run(source) == ["4299"]
