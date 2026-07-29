import pytest

from matrixlang.errors import ParseError
from matrixlang.lexer import lex
from matrixlang.nodes import (
    Binary,
    BoolLiteral,
    Name,
    NumberLiteral,
    StringLiteral,
    Unary,
)
from matrixlang.parser import parse_expression
from matrixlang.tokens import TokenType


def expr(source):
    return parse_expression(lex(source))


def test_number_literal():
    assert expr("42") == NumberLiteral(42)


def test_string_literal():
    assert expr('"Neo"') == StringLiteral("Neo")


def test_bool_literals():
    assert expr("true") == BoolLiteral(True)
    assert expr("false") == BoolLiteral(False)


def test_name():
    assert expr("counter") == Name("counter")


def test_parens_group_without_a_wrapper_node():
    # No Grouping node: parens live in tree shape. The Stage 4 renderer
    # re-derives them from precedence, which is lossless at AST level.
    assert expr("(42)") == NumberLiteral(42)


def test_unary_minus_nests():
    assert expr("--3") == Unary(
        TokenType.MINUS, Unary(TokenType.MINUS, NumberLiteral(3))
    )


def test_positions_are_captured_but_not_compared():
    node = expr("  42")
    assert (node.line, node.column) == (1, 3)
    assert node == NumberLiteral(42)


def test_unclosed_paren_reports_position():
    with pytest.raises(ParseError) as excinfo:
        expr("(1 + 2")
    assert excinfo.value.column == 7


def test_missing_expression_is_an_error():
    with pytest.raises(ParseError) as excinfo:
        expr("+")
    assert "expected an expression" in str(excinfo.value)


def test_trailing_input_is_an_error():
    with pytest.raises(ParseError):
        expr("1 2")


def test_trailing_comment_is_tolerated_and_discarded():
    # REPL convenience. The §4.3 round-trip criterion applies to whole
    # programs via parse(), where trivia is preserved.
    assert expr("1  # note") == NumberLiteral(1)


def test_multiplication_binds_tighter_than_addition():
    # THE Stage 2 done-when from the parent spec: * sits BELOW + in the tree.
    assert expr("2 + 3 * 4") == Binary(
        NumberLiteral(2),
        TokenType.PLUS,
        Binary(NumberLiteral(3), TokenType.STAR, NumberLiteral(4)),
    )


def test_same_level_operators_associate_left():
    assert expr("10 - 3 - 2") == Binary(
        Binary(NumberLiteral(10), TokenType.MINUS, NumberLiteral(3)),
        TokenType.MINUS,
        NumberLiteral(2),
    )


def test_parens_override_precedence():
    assert expr("(2 + 3) * 4") == Binary(
        Binary(NumberLiteral(2), TokenType.PLUS, NumberLiteral(3)),
        TokenType.STAR,
        NumberLiteral(4),
    )


def test_comparison_sits_below_arithmetic():
    assert expr("1 + 2 < 4") == Binary(
        Binary(NumberLiteral(1), TokenType.PLUS, NumberLiteral(2)),
        TokenType.LT,
        NumberLiteral(4),
    )


def test_equality_sits_below_comparison():
    assert expr("1 < 2 == 3 < 4") == Binary(
        Binary(NumberLiteral(1), TokenType.LT, NumberLiteral(2)),
        TokenType.EQ,
        Binary(NumberLiteral(3), TokenType.LT, NumberLiteral(4)),
    )


def test_unary_binds_tighter_than_multiplication():
    assert expr("-2 * 3") == Binary(
        Unary(TokenType.MINUS, NumberLiteral(2)), TokenType.STAR, NumberLiteral(3)
    )
