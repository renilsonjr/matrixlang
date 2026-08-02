"""Stage 7 — parsing lists, indexing, length and element assignment."""

import pytest

from matrixlang.errors import ParseError
from matrixlang.lexer import lex
from matrixlang.nodes import (
    Binary,
    ListLiteral,
    NumberLiteral,
    StringLiteral,
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
