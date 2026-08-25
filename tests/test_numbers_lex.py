"""Decimal literals, in both faces."""

from decimal import Decimal

import pytest

from matrixlang.errors import LexError
from matrixlang.lexer import lex
from matrixlang.tokens import TokenType


def first_number(source):
    return [t for t in lex(source) if t.type is TokenType.NUMBER][0]


def test_a_whole_number_lexes_as_a_decimal():
    token = first_number("42\n")
    assert token.value == Decimal(42)
    assert type(token.value) is Decimal


def test_a_decimal_literal_lexes():
    assert first_number("0.5\n").value == Decimal("0.5")


def test_trailing_zeros_survive_lexing():
    # Significant in this language: 2.50 * 2 is 5.00.
    assert str(first_number("2.50\n").value) == "2.50"


def test_a_decimal_lexes_in_the_glyph_face():
    # ｰ is the point; digits map per-digit as they always have.
    assert first_number("ｦｰｫ\n").value == Decimal("0.5")


def test_a_point_needs_a_digit_before_it():
    with pytest.raises(LexError):
        lex(".5\n")


def test_a_point_needs_a_digit_after_it():
    with pytest.raises(LexError):
        lex("1.\n")


def test_a_second_point_is_an_error():
    with pytest.raises(LexError):
        lex("1.2.3\n")


def test_a_long_literal_is_exact():
    # The constructor is exact regardless of context precision, so a
    # literal longer than any context is preserved as written.
    digits = "9" * 60
    assert first_number(f"{digits}\n").value == Decimal(digits)


def test_an_oversized_literal_fails_at_trace_not_at_lex_or_parse():
    # This file is about lexing, and this test is not -- it lives here
    # anyway because #135 is what moved the digit cap out of the lexer
    # (see test_lexer.py::test_a_number_literal_past_the_old_digit_ceiling_
    # now_lexes) and into display, where
    # tests/test_values.py::test_a_number_too_long_to_render_raises_a_named_signal
    # pins it. Task 2 moved the behaviour, so Task 2 owns the regression
    # guard for the chain it moved it into.
    #
    # `run()` promises never to let a bare Python exception escape, and
    # that promise has broken six times on this project already. Moving a
    # cap between layers -- lex, now succeeds; display, now raises -- is
    # exactly the kind of change that breaks it a seventh time, so this
    # proves the whole chain end to end: lex -> parse -> trace fails with
    # a positioned RuntimeErrorML, not a raw exception.
    #
    # Blocked on Tasks 3-5: interpreter.py still imports the now-removed
    # `is_int` at module level (Task 1's commit message says its call
    # sites move "in the next three tasks"), so importing it here raises
    # the same ImportError as the rest of the suite's collection errors.
    # Imported lazily, inside the test, so that failure lands as this one
    # test failing rather than this whole file refusing to collect --
    # every other test above stays green while this one is red for the
    # documented, predicted reason. It turns green on its own once Task 5
    # lands.
    import sys

    from matrixlang.errors import RuntimeErrorML
    from matrixlang.interpreter import run
    from matrixlang.parser import parse

    digits = "9" * (sys.get_int_max_str_digits() + 1)
    tokens = lex(f"trace {digits}\n")
    program = parse(tokens)

    with pytest.raises(RuntimeErrorML) as excinfo:
        run(program)
    assert excinfo.value.line == 1
