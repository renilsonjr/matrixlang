import pytest

from matrixlang.errors import ParseError
from matrixlang.lexer import lex
from matrixlang.nodes import (
    Assign,
    Binary,
    BoolLiteral,
    Declare,
    Name,
    NumberLiteral,
    Program,
    StringLiteral,
    Trace,
    Unary,
)
from matrixlang.parser import parse, parse_expression
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


def program(source):
    return parse(lex(source))


def test_declare_statement():
    assert program("construct x = 5\n") == Program([Declare("x", NumberLiteral(5))])


def test_assign_and_trace():
    tree = program("x = x + 1\ntrace x\n")
    assert tree.statements == [
        Assign("x", Binary(Name("x"), TokenType.PLUS, NumberLiteral(1))),
        Trace(Name("x")),
    ]


def test_blank_lines_are_skipped():
    assert program("\n\ntrace 1\n\n") == Program([Trace(NumberLiteral(1))])


def test_empty_source_is_an_empty_program():
    assert program("") == Program([])


def test_statement_positions_point_at_the_keyword():
    statement = program("  trace 1\n").statements[0]
    assert (statement.line, statement.column) == (1, 3)


def test_declare_without_name_is_an_error():
    with pytest.raises(ParseError) as excinfo:
        program("construct = 5\n")
    assert "expected a name" in str(excinfo.value)


def test_bare_expression_is_not_a_statement():
    with pytest.raises(ParseError) as excinfo:
        program("x + 1\n")
    assert "expected '='" in str(excinfo.value)


def test_two_statements_on_one_line_is_an_error():
    with pytest.raises(ParseError) as excinfo:
        program("trace 1 trace 2\n")
    assert "expected end of line" in str(excinfo.value)


def test_flatline_without_a_block_is_an_error():
    with pytest.raises(ParseError) as excinfo:
        program("flatline\n")
    assert "expected a statement" in str(excinfo.value)


def test_leading_comments_attach_to_the_next_statement():
    tree = program("# a\n# b\ntrace 1\n")
    assert tree.statements[0].leading_comments == ["# a", "# b"]


def test_trailing_comment_attaches_to_its_statement():
    tree = program("trace 1  # loud\n")
    assert tree.statements[0].trailing_comment == "# loud"


def test_comments_after_the_last_statement_belong_to_the_program():
    tree = program("trace 1\n# end\n")
    assert tree.trailing_comments == ["# end"]


def test_comment_only_source():
    assert program("# ghost\n") == Program([], trailing_comments=["# ghost"])


def test_blank_lines_between_comments_and_statement_do_not_detach_them():
    tree = program("# a\n\ntrace 1\n")
    assert tree.statements[0].leading_comments == ["# a"]


def test_trivia_changes_equality():
    # The whole point of D-06: dropping a comment must break AST equality.
    assert program("trace 1\n") != program("trace 1  # hi\n")
