"""OP-B — validation. The parser is ground truth; the LLM is not.

Operator never gets to declare its own output valid. Every candidate goes
through the real lexer, the real parser, and — since Stage 6 landed — a
real bounded execution, because a program can now be syntactically
perfect and still fail the moment it runs.
"""

import pytest

from matrixlang.operator.validate import Invalid, Stage, Valid, check


# --- Accepting ----------------------------------------------------------


def test_a_good_program_is_valid():
    result = check('trace "wake up, Neo"\n')
    assert isinstance(result, Valid)
    assert result.program.statements


def test_a_program_using_functions_is_valid():
    result = check("agent double(n)\n  jackout n * 2\nflatline\ntrace double(21)\n")
    assert isinstance(result, Valid)


def test_the_glyph_face_is_accepted_too():
    # Operator may emit either face; both are the same language.
    from matrixlang.render import render_glyph

    tree = check("construct n = 1\n").program
    assert isinstance(check(render_glyph(tree)), Valid)


# --- Rejecting at parse -------------------------------------------------


def test_a_syntax_error_is_reported_at_the_parse_stage():
    result = check("construct = 5\n")
    assert isinstance(result, Invalid)
    assert result.stage is Stage.PARSE


def test_the_real_diagnostic_survives_unchanged():
    # The whole point: the message Operator sees is the message the parser
    # produced. Rewriting it would hide what the retry has to fix.
    result = check("construct = 5\n")
    assert "expected a name" in result.message
    assert result.line == 1
    assert result.column > 0


def test_a_lex_error_is_a_parse_stage_failure():
    result = check('trace "unterminated\n')
    assert isinstance(result, Invalid)
    assert result.stage is Stage.PARSE


# --- Rejecting at run: what Stage 6 made possible -----------------------


def test_a_program_that_parses_can_still_fail_to_run():
    # §7 of the Operator design. Before Stage 6 the language was too small
    # for parse success and run success to diverge; arity and NOTHING
    # changed that on their own terms.
    result = check("agent add(a, b)\n  jackout a\nflatline\ntrace add(1)\n")
    assert isinstance(result, Invalid)
    assert result.stage is Stage.RUN
    assert "takes 2" in result.message


def test_using_a_nothing_as_a_value_is_caught():
    result = check('agent log()\n  trace "hi"\nflatline\ntrace log()\n')
    assert isinstance(result, Invalid)
    assert result.stage is Stage.RUN
    assert "did not jack out" in result.message


def test_an_undeclared_name_is_caught():
    result = check("trace nope\n")
    assert isinstance(result, Invalid)
    assert result.stage is Stage.RUN


def test_a_run_failure_carries_a_position():
    result = check("trace nope\n")
    assert result.line == 1
    assert result.column > 0


# --- The dry run is bounded ---------------------------------------------


def test_an_infinite_loop_is_reported_as_its_own_stage():
    # Distinct from RUN on purpose. A program that exhausts the budget may
    # be an infinite loop or may be legitimately long, and the caller
    # should be able to tell those apart from a definite error.
    result = check("construct n = 0\ndejavu true\n  n = n + 1\nflatline\n")
    assert isinstance(result, Invalid)
    assert result.stage is Stage.LIMIT


def test_the_dry_run_budget_is_adjustable():
    source = "construct n = 0\ndejavu n < 300\n  n = n + 1\nflatline\n"
    assert isinstance(check(source, max_steps=50), Invalid)
    assert isinstance(check(source, max_steps=100_000), Valid)


def test_the_dry_run_budget_is_lower_than_the_cli_default():
    # Design §3: code nobody has read yet gets a visibly lower ceiling
    # than a human running their own file.
    from matrixlang.interpreter import DEFAULT_MAX_STEPS
    from matrixlang.operator.validate import DRY_RUN_MAX_STEPS

    assert DRY_RUN_MAX_STEPS < DEFAULT_MAX_STEPS


# --- The dry run must not leak ------------------------------------------


def test_the_dry_run_produces_no_output():
    import io
    import sys

    captured = io.StringIO()
    original = sys.stdout
    sys.stdout = captured
    try:
        check('trace "this must not appear"\n')
    finally:
        sys.stdout = original
    assert captured.getvalue() == ""


def test_validation_is_repeatable():
    # No state carried between calls: the same source validates the same
    # way every time, which is what makes a retry loop meaningful.
    source = "agent add(a, b)\n  jackout a\nflatline\ntrace add(1)\n"
    first, second = check(source), check(source)
    assert type(first) is type(second)
    assert first.message == second.message


# --- Reporting ----------------------------------------------------------


def test_an_invalid_result_renders_as_a_diagnostic_line():
    result = check("construct = 5\n")
    assert result.as_diagnostic().startswith("[line 1, column")
    assert "expected a name" in result.as_diagnostic()
