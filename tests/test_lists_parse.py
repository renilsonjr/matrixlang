"""Stage 7 — parsing lists, indexing, length and element assignment."""

from decimal import Decimal

import pytest

from matrixlang.errors import ParseError
from matrixlang.lexer import lex
from matrixlang.nodes import (
    Binary,
    Index,
    ListLiteral,
    NumberLiteral,
    StringLiteral,
    Name,
)
from matrixlang.parser import parse
from matrixlang.tokens import TokenType


def first(source):
    return parse(lex(source)).statements[0]


def test_an_empty_list_parses():
    assert first("construct xs = []\n").value == ListLiteral([])


def test_a_list_of_numbers_parses():
    assert first("construct xs = [1, 2]\n").value == ListLiteral(
        [NumberLiteral(Decimal(1)), NumberLiteral(Decimal(2))]
    )


def test_a_trailing_element_is_required_after_a_comma():
    with pytest.raises(ParseError) as caught:
        first("construct xs = [1, ]\n")
    assert "expected an expression" in caught.value.message


def test_an_unclosed_list_reports_the_bracket():
    with pytest.raises(ParseError) as caught:
        first("construct xs = [1\n")
    assert "']'" in caught.value.message


def test_elements_may_be_arbitrary_expressions():
    assert first("construct xs = [1 + 2]\n").value == ListLiteral(
        [Binary(NumberLiteral(Decimal(1)), TokenType.PLUS, NumberLiteral(Decimal(2)))]
    )


def test_lists_nest():
    assert first("construct xs = [[1]]\n").value == ListLiteral(
        [ListLiteral([NumberLiteral(Decimal(1))])]
    )


def test_elements_may_be_mixed_types():
    # Refusing this would need a type system the language does not have.
    parsed = first('construct xs = [1, "a", true]\n').value
    assert len(parsed.elements) == 3


def test_indexing_a_name_parses():
    assert first("construct a = xs[0]\n").value == Index(
        Name("xs"), NumberLiteral(Decimal(0))
    )


def test_indexing_chains():
    # Nested lists are legal, so xs[0][1] must be too.
    assert first("construct a = xs[0][1]\n").value == Index(
        Index(Name("xs"), NumberLiteral(Decimal(0))), NumberLiteral(Decimal(1))
    )


def test_a_call_result_can_be_indexed():
    # _call is a postfix loop, so f()[0] falls out for free.
    parsed = first("construct a = f()[0]\n").value
    assert isinstance(parsed, Index)


def test_indexing_a_list_literal_parses():
    assert first("construct a = [1, 2][0]\n").value == Index(
        ListLiteral([NumberLiteral(Decimal(1)), NumberLiteral(Decimal(2))]), NumberLiteral(Decimal(0))
    )


def test_an_unclosed_index_reports_the_bracket():
    with pytest.raises(ParseError) as caught:
        first("construct a = xs[0\n")
    assert "']'" in caught.value.message


def test_an_empty_index_is_an_error():
    with pytest.raises(ParseError) as caught:
        first("construct a = xs[]\n")
    assert "expected an expression" in caught.value.message


def test_length_parses_as_a_unary():
    from matrixlang.nodes import Unary

    assert first("construct n = length xs\n").value == Unary(
        TokenType.LENGTH, Name("xs")
    )


def test_length_binds_tighter_than_plus():
    # `length xs + 1` must be `(length xs) + 1`, matching `-x + 1`.
    from matrixlang.nodes import Unary

    parsed = first("construct n = length xs + 1\n").value
    assert isinstance(parsed, Binary)
    assert isinstance(parsed.left, Unary)
    assert parsed.left.op is TokenType.LENGTH


def test_length_applies_to_an_index():
    from matrixlang.nodes import Unary

    parsed = first("construct n = length xs[0]\n").value
    assert isinstance(parsed, Unary)
    assert isinstance(parsed.operand, Index)


def test_length_of_a_parenthesised_expression_parses():
    from matrixlang.nodes import Unary

    parsed = first("construct n = length (xs + ys)\n").value
    assert isinstance(parsed, Unary)


def test_element_assignment_parses():
    from matrixlang.nodes import IndexAssign

    stmt = first("xs[0] = 9\n")
    assert stmt == IndexAssign(Name("xs"), NumberLiteral(Decimal(0)), NumberLiteral(Decimal(9)))


def test_nested_element_assignment_parses():
    from matrixlang.nodes import IndexAssign

    stmt = first("xs[0][1] = 9\n")
    assert isinstance(stmt, IndexAssign)
    assert stmt.target == Index(Name("xs"), NumberLiteral(Decimal(0)))
    assert stmt.index == NumberLiteral(Decimal(1))


def test_assigning_to_a_call_result_is_a_parse_error():
    with pytest.raises(ParseError) as caught:
        first("f()[0] = 9\n")
    assert "cannot assign" in caught.value.message


def test_a_bare_index_is_not_a_statement():
    # Same rule as a bare name: it computes something and throws it away,
    # which is a mistake rather than a statement.
    with pytest.raises(ParseError):
        first("xs[0]\n")


def test_plain_assignment_still_reports_the_equals_sign():
    # Regression: the IDENT dispatch must not swallow this case.
    with pytest.raises(ParseError) as caught:
        first("x + 1\n")
    assert "'='" in caught.value.message
