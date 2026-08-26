from decimal import Decimal

import pytest

from matrixlang.nodes import (
    Binary,
    BoolLiteral,
    Declare,
    Name,
    NumberLiteral,
    Trace,
)
from matrixlang.tokens import TokenType


def test_equality_is_structural():
    a = Binary(NumberLiteral(Decimal(2)), TokenType.PLUS, NumberLiteral(Decimal(3)))
    b = Binary(NumberLiteral(Decimal(2)), TokenType.PLUS, NumberLiteral(Decimal(3)))
    assert a == b


def test_positions_do_not_participate_in_equality():
    # Load-bearing for the parent spec §4.3 round-trip: a re-rendered face
    # has different columns, so positional equality would make the
    # criterion unsatisfiable.
    a = NumberLiteral(Decimal(5), line=1, column=1)
    b = NumberLiteral(Decimal(5), line=9, column=42)
    assert a == b


def test_comment_trivia_participates_in_equality():
    a = Trace(Name("x"))
    b = Trace(Name("x"))
    b.trailing_comment = "# wake up"
    assert a != b


def test_trivia_defaults_are_empty():
    s = Declare("x", NumberLiteral(Decimal(0)))
    assert s.leading_comments == []
    assert s.trailing_comment is None


def test_trivia_lists_are_not_shared_between_nodes():
    a = Trace(Name("x"))
    b = Trace(Name("y"))
    a.leading_comments.append("# only a")
    assert b.leading_comments == []


def test_distinct_node_types_are_never_equal():
    # Guards the Python quirk that 1 == True.
    assert NumberLiteral(Decimal(1)) != BoolLiteral(True)


def test_number_literal_refuses_a_bare_int():
    # The invariant the whole display layer rests on: render._number walks
    # format(value, "f"), and format(5, "f") silently succeeds as
    # "5.000000" rather than raising, so a bare int here renders `trace
    # 5.000000` with no error anywhere. Task 6 of the numbers branch had to
    # find that class of mistake by grepping thirteen construction sites.
    #
    # `==` cannot police it -- Decimal(42) == 42 is True, so every
    # comparison target in this suite would still pass against a parser
    # that produced ints. Only a type check at construction sees it.
    with pytest.raises(TypeError) as caught:
        NumberLiteral(5)
    assert "Decimal" in str(caught.value)


def test_number_literal_refuses_a_float_and_a_bool():
    # A float is the type this language exists to not have (0.1 + 0.2), and
    # `isinstance(True, int)` is True in Python, which is the reason this
    # guard is `type(...) is not Decimal` rather than an isinstance check.
    for wrong in (5.0, True, "5", Decimal):
        with pytest.raises(TypeError):
            NumberLiteral(wrong)
