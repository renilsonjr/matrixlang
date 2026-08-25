"""Arithmetic, ordering and equality on the one number type."""

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


def test_whole_numbers_still_print_as_they_did():
    assert run("trace 3\n") == "3\n"
    assert run("trace 1 + 2\n") == "3\n"


def test_decimals_add_exactly():
    # The whole reason for exact decimals: 0.1 + 0.2 is 0.3, not
    # 0.30000000000000004.
    assert run("trace 0.1 + 0.2\n") == "0.3\n"


def test_money_adds_the_way_a_reader_expects():
    assert run("trace 49.90 + 120.00\n") == "169.90\n"


def test_trailing_zeros_are_significant():
    assert run("trace 2.50 * 2\n") == "5.00\n"


def test_big_whole_numbers_stay_exact():
    # Decimal's default precision would round this to 28 significant
    # digits and print it in scientific notation. values.EXACT is why it
    # does not.
    digits = "9" * 40
    expected = "1" + "9" * 39 + "8"
    assert run(f"trace {digits} * 2\n") == f"{expected}\n"


def test_subtraction_and_multiplication():
    assert run("trace 1.5 - 0.5\n") == "1.0\n"
    assert run("trace 1.5 * 2\n") == "3.0\n"


def test_ordering_compares_by_value_not_by_text():
    assert run("trace 2 < 10\n") == "true\n"
    assert run("trace 1.5 < 2\n") == "true\n"
    assert run("trace 2.50 == 2.5\n") == "true\n"


def test_a_whole_number_equals_its_decimal_spelling():
    # One type, one value. Python agrees: 1 == 1.0.
    assert run("trace 3 == 3.0\n") == "true\n"


@pytest.mark.parametrize(
    "operand,name",
    [('"a"', "string"), ("true", "boolean"), ("[1]", "list")],
)
def test_arithmetic_refuses_a_non_number(operand, name):
    error = fails(f"trace 1 + {operand}\n")
    assert name in error.message


def test_the_error_says_number_not_integer():
    error = fails("trace 1 - true\n")
    assert "number" in error.message
    assert "integer" not in error.message


def test_a_runaway_multiplication_reports_a_positioned_matrixlang_error():
    # values.NumberOverflow is position-less and not a MatrixLangError --
    # nothing converts it before this task wires EXACT into `*`. Squaring
    # 10 about twenty times overflows EXACT's Emax (prec=1000 pushes it to
    # 999999), well inside 30 iterations and well inside the step limit.
    # This must come out as a positioned RuntimeErrorML, not a bare Python
    # exception -- that promise (site/glue.py's run() never raises
    # anything else) has been broken six times already.
    lines = ["construct n = 10"] + ["n = n * n"] * 30 + ["trace n"]
    error = fails("\n".join(lines) + "\n")
    assert "too large" in error.message
    assert 2 <= error.line <= 31


def test_unary_minus_agrees_with_zero_minus_past_28_digits():
    # Decimal's own __neg__ rounds through the thread-local DEFAULT
    # context (prec=28), not EXACT -- so `-x` and `0 - x` could silently
    # disagree past 28 significant digits, with no error and no
    # scientific notation, just a different, wrong number. 29 nines is
    # one digit past that boundary.
    digits = "9" * 29
    assert run(f"trace -{digits}\n") == run(f"trace 0 - {digits}\n")
    assert run(f"trace -{digits}\n") == f"-{digits}\n"


def test_division_rounds_to_28_significant_digits_on_huge_operands():
    # This test used to pin truncation past 28 digits: the old SLASH
    # branch's abs()/// dance rounded through the thread-local default
    # context, silently wrong past 28 significant digits. Task 4 (#135)
    # replaced it with DIVISION.divide, a context call, so the rounding
    # is now correct by construction: the quotient is rounded to
    # DIVISION's 28 significant digits, not truncated. Both operands
    # here are 40 digits long, so the exact quotient of the first case
    # (40 threes) has more than 28 significant digits and comes back
    # rounded, with the dropped digits standing in as trailing zeros in
    # positional form -- this is not the exact mathematical answer, and
    # is not supposed to be.
    assert (
        run("trace 9999999999999999999999999999999999999999 / 3\n")
        == "3333333333333333333333333333000000000000\n"
    )
    assert (
        run(
            "trace 9999999999999999999999999999999999999999 / "
            "10000000000000\n"
        )
        == "1000000000000000000000000000\n"
    )


def test_division_is_true_division():
    # Was 3. This is the branch's breaking change: Python's `/` and this
    # one now agree exactly, which is what makes `a / b` translatable at
    # all.
    assert run("trace 7 / 2\n") == "3.5\n"


def test_division_agrees_with_python_on_negatives():
    # The old truncating `/` gave -3 and Python's `//` gives -4; neither
    # matched Python's `/`. This does.
    assert run("trace -7 / 2\n") == "-3.5\n"


def test_division_that_does_not_terminate_rounds():
    assert run("trace 1 / 3\n") == "0.3333333333333333333333333333\n"


def test_division_by_zero_is_still_an_error():
    error = fails("trace 1 / 0\n")
    assert "cannot divide by zero" in error.message


def test_dividing_money_in_half():
    assert run("trace 49.90 / 2\n") == "24.95\n"
