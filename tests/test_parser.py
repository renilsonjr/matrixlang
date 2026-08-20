from pathlib import Path

import pytest

from matrixlang.errors import ParseError
from matrixlang.lexer import lex
from matrixlang.nodes import (
    Assign,
    Binary,
    BoolLiteral,
    Declare,
    If,
    Name,
    NumberLiteral,
    Program,
    StringLiteral,
    Trace,
    Unary,
    While,
)
from matrixlang.parser import parse, parse_expression
from matrixlang.tokens import Token, TokenType


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


def test_if_without_else():
    tree = program("redpill x == 1\n  trace x\nflatline\n")
    assert tree.statements == [
        If(
            Binary(Name("x"), TokenType.EQ, NumberLiteral(1)),
            [Trace(Name("x"))],
            None,
        )
    ]


def test_if_with_else():
    branch = program(
        "redpill x\n  trace 1\nbluepill\n  trace 2\nflatline\n"
    ).statements[0]
    assert branch.then_body == [Trace(NumberLiteral(1))]
    assert branch.else_body == [Trace(NumberLiteral(2))]


def test_nested_ifs():
    source = "redpill x\n  redpill y\n    trace 1\n  flatline\nflatline\n"
    outer = program(source).statements[0]
    inner = outer.then_body[0]
    assert isinstance(inner, If)
    assert inner.then_body == [Trace(NumberLiteral(1))]


def test_empty_bodies_are_legal():
    branch = program("redpill x\nbluepill\nflatline\n").statements[0]
    assert branch.then_body == []
    assert branch.else_body == []


def test_missing_flatline_reports_end_of_input():
    with pytest.raises(ParseError) as excinfo:
        program("redpill x\n  trace 1\n")
    assert "flatline" in str(excinfo.value)


def test_header_comment_normalizes_into_the_body():
    branch = program("redpill x  # why\n  trace 1\nflatline\n").statements[0]
    assert branch.then_body[0].leading_comments == ["# why"]


def test_comment_on_the_flatline_line_trails_the_whole_if():
    branch = program("redpill x\n  trace 1\nflatline  # done\n").statements[0]
    assert branch.trailing_comment == "# done"


def test_dangling_comments_before_flatline_are_kept():
    branch = program("redpill x\n  trace 1\n  # tail\nflatline\n").statements[0]
    assert branch.then_trailing == ["# tail"]


def test_bluepill_outside_redpill_is_an_error():
    with pytest.raises(ParseError):
        program("bluepill\n")


def test_while_loop():
    loop = program("dejavu n < 3\n  n = n + 1\nflatline\n").statements[0]
    assert loop == While(
        Binary(Name("n"), TokenType.LT, NumberLiteral(3)),
        [Assign("n", Binary(Name("n"), TokenType.PLUS, NumberLiteral(1)))],
    )


def test_while_missing_flatline_names_dejavu():
    with pytest.raises(ParseError) as excinfo:
        program("dejavu true\n  trace 1\n")
    assert "dejavu" in str(excinfo.value)


def test_bluepill_inside_while_is_an_error():
    # The message matters, not just the raise. `bluepill` must fall through to
    # _statement and be rejected there — NOT be accepted as a block closer. A
    # _while that passed BLUEPILL to _body would still raise a ParseError here,
    # just a different one, so a bare pytest.raises cannot tell the two apart.
    with pytest.raises(ParseError) as excinfo:
        program("dejavu true\nbluepill\nflatline\n")
    assert "expected a statement" in str(excinfo.value)
    assert excinfo.value.line == 2


def test_dangling_comments_before_a_loop_flatline_are_kept():
    loop = program("dejavu true\n  trace 1\n  # tail\nflatline\n").statements[0]
    assert loop.body_trailing == ["# tail"]


def test_if_nested_in_while():
    loop = program(
        "dejavu x < 3\n"
        "  redpill x == 1\n"
        "    trace x\n"
        "  flatline\n"
        "  x = x + 1\n"
        "flatline\n"
    ).statements[0]
    assert [type(s).__name__ for s in loop.body] == ["If", "Assign"]


def test_hello_rain_parses_end_to_end():
    source = (Path(__file__).parent.parent / "examples" / "hello.rain").read_text(
        encoding="utf-8"
    )
    tree = program(source)
    assert [type(s).__name__ for s in tree.statements] == [
        "Declare",
        "Declare",
        "While",
    ]
    assert tree.statements[0].leading_comments == [
        "# The Stage 3 demo. This runs: `matrixlang run examples/hello.rain`."
    ]
    loop = tree.statements[2]
    assert [type(s).__name__ for s in loop.body] == ["If", "Assign"]
    branch = loop.body[0]
    assert branch.else_body is not None
    concat = branch.then_body[0].value
    assert isinstance(concat, Binary)
    assert concat.op is TokenType.PLUS


def test_parser_consumes_tokens_from_any_source():
    # The parser must never import the lexer — Stage 4 feeds it tokens from
    # both the ASCII and glyph faces. Building the list by hand is the only
    # test here that would fail if someone added a lexer import to parser.py.
    tokens = [
        Token(TokenType.TRACE, "trace", 1, 1),
        Token(TokenType.NUMBER, "7", 1, 7, 7),
        Token(TokenType.NEWLINE, "", 1, 8),
        Token(TokenType.EOF, "", 1, 8),
    ]
    assert parse(tokens) == Program([Trace(NumberLiteral(7))])


def test_parser_performs_no_semantic_checks():
    # Language spec §5 puts all three of these errors in Stage 3, at runtime.
    # The parser builds trees and judges nothing.
    assert len(program("zzz = 1\n").statements) == 1
    assert len(program("construct x = 1\nconstruct x = 2\n").statements) == 2
    assert len(program('redpill "neo"\n  trace 1\nflatline\n').statements) == 1


def test_eof_where_an_expression_was_expected():
    with pytest.raises(ParseError) as excinfo:
        expr("")
    assert "expected an expression" in str(excinfo.value)
    assert excinfo.value.column == 1


def test_chained_comparison_associates_left():
    assert expr("1 < 2 < 3") == Binary(
        Binary(NumberLiteral(1), TokenType.LT, NumberLiteral(2)),
        TokenType.LT,
        NumberLiteral(3),
    )


def test_leading_and_trailing_trivia_coexist_on_one_statement():
    statement = program("# above\ntrace 1  # beside\n").statements[0]
    assert statement.leading_comments == ["# above"]
    assert statement.trailing_comment == "# beside"


def test_comment_on_the_bluepill_header_adopts_into_the_else_body():
    branch = program(
        "redpill x\n  trace 1\nbluepill  # why\n  trace 2\nflatline\n"
    ).statements[0]
    assert branch.else_body[0].leading_comments == ["# why"]


def test_jackin_parses_as_an_expression():
    from matrixlang.nodes import Declare, JackIn

    program_obj = program("construct name = jackin\n")
    (declare,) = program_obj.statements
    assert isinstance(declare, Declare)
    assert isinstance(declare.value, JackIn)


def test_decode_parses_as_a_unary_on_its_operand():
    from matrixlang.nodes import JackIn, Unary

    program_obj = program("construct n = decode jackin\n")
    (declare,) = program_obj.statements
    assert isinstance(declare.value, Unary)
    assert declare.value.op is TokenType.DECODE
    assert isinstance(declare.value.operand, JackIn)


def test_decode_binds_tighter_than_arithmetic():
    # `decode jackin + 1` must be `(decode jackin) + 1`. The loose reading
    # would decode the result of adding 1 to text, which is an error for
    # every possible input -- the same argument that puts `length` at this
    # level. This differs from `unplug`, which binds LOOSER than
    # comparison, and that asymmetry is deliberate: see the design doc §3.
    from matrixlang.nodes import Binary, Unary

    program_obj = program("construct n = decode jackin + 1\n")
    (declare,) = program_obj.statements
    assert isinstance(declare.value, Binary), "decode swallowed the addition"
    assert declare.value.op is TokenType.PLUS
    assert isinstance(declare.value.left, Unary)
    assert declare.value.left.op is TokenType.DECODE


def test_decode_of_a_parenthesised_expression_still_works():
    from matrixlang.nodes import StringLiteral, Unary

    program_obj = program('construct n = decode ("5")\n')
    (declare,) = program_obj.statements
    assert isinstance(declare.value, Unary)
    assert isinstance(declare.value.operand, StringLiteral)


def test_encode_parses_as_a_unary():
    from matrixlang.nodes import NumberLiteral, Unary

    tree = program("construct s = encode 42\n")
    (declare,) = tree.statements
    assert isinstance(declare.value, Unary)
    assert declare.value.op is TokenType.ENCODE
    assert isinstance(declare.value.operand, NumberLiteral)


def test_encode_binds_tighter_than_arithmetic():
    # `encode n + 1` must be `(encode n) + 1`. The loose reading is not an
    # error -- it would quietly encode n+1 and produce "43" where "42" was
    # meant -- which is exactly why this needs pinning. Same level as
    # `decode` and `length`, and deliberately unlike `unplug`.
    from matrixlang.nodes import Binary, Unary

    tree = program("construct s = encode 42 + 1\n")
    (declare,) = tree.statements
    assert isinstance(declare.value, Binary), "encode swallowed the addition"
    assert declare.value.op is TokenType.PLUS
    assert isinstance(declare.value.left, Unary)
    assert declare.value.left.op is TokenType.ENCODE
