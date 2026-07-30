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
    a = Binary(NumberLiteral(2), TokenType.PLUS, NumberLiteral(3))
    b = Binary(NumberLiteral(2), TokenType.PLUS, NumberLiteral(3))
    assert a == b


def test_positions_do_not_participate_in_equality():
    # Load-bearing for the parent spec §4.3 round-trip: a re-rendered face
    # has different columns, so positional equality would make the
    # criterion unsatisfiable.
    a = NumberLiteral(5, line=1, column=1)
    b = NumberLiteral(5, line=9, column=42)
    assert a == b


def test_comment_trivia_participates_in_equality():
    a = Trace(Name("x"))
    b = Trace(Name("x"))
    b.trailing_comment = "# wake up"
    assert a != b


def test_trivia_defaults_are_empty():
    s = Declare("x", NumberLiteral(0))
    assert s.leading_comments == []
    assert s.trailing_comment is None


def test_trivia_lists_are_not_shared_between_nodes():
    a = Trace(Name("x"))
    b = Trace(Name("y"))
    a.leading_comments.append("# only a")
    assert b.leading_comments == []


def test_distinct_node_types_are_never_equal():
    # Guards the Python quirk that 1 == True.
    assert NumberLiteral(1) != BoolLiteral(True)
