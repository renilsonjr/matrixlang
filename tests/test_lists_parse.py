"""Stage 7 — parsing lists, indexing, length and element assignment."""

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
        [NumberLiteral(1), NumberLiteral(2)]
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
        [Binary(NumberLiteral(1), TokenType.PLUS, NumberLiteral(2))]
    )


def test_lists_nest():
    assert first("construct xs = [[1]]\n").value == ListLiteral(
        [ListLiteral([NumberLiteral(1)])]
    )


def test_elements_may_be_mixed_types():
    # Refusing this would need a type system the language does not have.
    parsed = first('construct xs = [1, "a", true]\n').value
    assert len(parsed.elements) == 3


def test_indexing_a_name_parses():
    assert first("construct a = xs[0]\n").value == Index(
        Name("xs"), NumberLiteral(0)
    )


def test_indexing_chains():
    # Nested lists are legal, so xs[0][1] must be too.
    assert first("construct a = xs[0][1]\n").value == Index(
        Index(Name("xs"), NumberLiteral(0)), NumberLiteral(1)
    )


def test_a_call_result_can_be_indexed():
    # _call is a postfix loop, so f()[0] falls out for free.
    parsed = first("construct a = f()[0]\n").value
    assert isinstance(parsed, Index)


def test_indexing_a_list_literal_parses():
    assert first("construct a = [1, 2][0]\n").value == Index(
        ListLiteral([NumberLiteral(1), NumberLiteral(2)]), NumberLiteral(0)
    )


def test_an_unclosed_index_reports_the_bracket():
    with pytest.raises(ParseError) as caught:
        first("construct a = xs[0\n")
    assert "']'" in caught.value.message


def test_an_empty_index_is_an_error():
    with pytest.raises(ParseError) as caught:
        first("construct a = xs[]\n")
    assert "expected an expression" in caught.value.message
