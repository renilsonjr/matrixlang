"""Rendering decimal literals in both faces."""

from decimal import Decimal

from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.render import render_ascii, render_glyph


def ascii_face(source):
    return render_ascii(parse(lex(source)))


def glyph_face(source):
    return render_glyph(parse(lex(source)))


def test_a_decimal_renders_back_to_itself():
    assert ascii_face("trace 0.5\n") == "trace 0.5\n"


def test_a_trailing_zero_survives_the_render():
    # THE test for this task. The round-trip property CANNOT catch this:
    # Decimal("2.50") == Decimal("2.5") is True, so a renderer that
    # dropped the zero would compare equal and pass. Trailing zeros are
    # significant -- 2.50 * 2 is 5.00 -- so this asserts the TEXT.
    assert ascii_face("trace 2.50\n") == "trace 2.50\n"


def test_a_whole_number_renders_without_a_point():
    assert ascii_face("trace 3\n") == "trace 3\n"


def test_a_decimal_renders_in_the_glyph_face():
    assert glyph_face("trace 0.5\n") == "ﾄ ｦｰｫ\n"


def test_a_negative_decimal_keeps_its_sign_outside_the_literal():
    # NumberLiteral values are non-negative; the minus is a Unary node.
    assert ascii_face("trace -0.5\n") == "trace -0.5\n"
