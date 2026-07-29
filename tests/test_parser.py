import pytest

from matrixlang.errors import ParseError
from matrixlang.lexer import lex
from matrixlang.nodes import (
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
    assert excinfo.value.column == 4


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
