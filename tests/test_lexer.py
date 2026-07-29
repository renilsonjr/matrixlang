import pytest

from matrixlang.errors import LexError
from matrixlang.lexer import lex
from matrixlang.tokens import TokenType


def kinds(source: str) -> list[TokenType]:
    """Token types only — keeps assertions readable."""
    return [t.type for t in lex(source)]


def pairs(source: str) -> list[tuple[TokenType, str]]:
    """(type, lexeme) pairs."""
    return [(t.type, t.lexeme) for t in lex(source)]


def test_single_character_operators():
    assert kinds("+ - * / ( )") == [
        TokenType.PLUS,
        TokenType.MINUS,
        TokenType.STAR,
        TokenType.SLASH,
        TokenType.LPAREN,
        TokenType.RPAREN,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_whitespace_is_skipped_but_newlines_are_not():
    assert kinds("+\t+\r+") == [
        TokenType.PLUS,
        TokenType.PLUS,
        TokenType.PLUS,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_trailing_newline_is_synthesised_exactly_once():
    with_newline = kinds("+\n")
    without_newline = kinds("+")
    assert with_newline == without_newline
    assert with_newline == [TokenType.PLUS, TokenType.NEWLINE, TokenType.EOF]


def test_empty_source_yields_only_eof():
    assert kinds("") == [TokenType.EOF]


def test_blank_lines_produce_newlines_and_nothing_else():
    # Acceptance case 7.
    assert kinds("\n\n\n+") == [
        TokenType.NEWLINE,
        TokenType.NEWLINE,
        TokenType.NEWLINE,
        TokenType.PLUS,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_line_and_column_are_one_indexed_and_track_newlines():
    tokens = lex("+\n  +")
    assert (tokens[0].line, tokens[0].column) == (1, 1)
    assert (tokens[2].line, tokens[2].column) == (2, 3)


def test_unknown_character_reports_line_and_column():
    # Acceptance case 9.
    with pytest.raises(LexError) as excinfo:
        lex("+ +\n+ @")
    error = excinfo.value
    assert error.line == 2
    assert error.column == 3
    assert "@" in str(error)


def test_two_character_operators_win_over_single():
    # Acceptance case 4.
    assert kinds("<= >= == !=") == [
        TokenType.LTE,
        TokenType.GTE,
        TokenType.EQ,
        TokenType.NEQ,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_single_character_comparisons_still_work():
    assert kinds("< > =") == [
        TokenType.LT,
        TokenType.GT,
        TokenType.ASSIGN,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_two_character_operator_advances_column_by_two():
    tokens = lex("<= <=")
    assert tokens[0].column == 1
    assert tokens[1].column == 4


def test_bare_bang_is_an_error():
    with pytest.raises(LexError) as excinfo:
        lex("! ")
    assert excinfo.value.column == 1


def test_multi_digit_number_is_one_token_with_int_value():
    tokens = lex("1024")
    assert tokens[0].type is TokenType.NUMBER
    assert tokens[0].lexeme == "1024"
    assert tokens[0].value == 1024


def test_numbers_and_operators_interleave():
    assert pairs("2+3") == [
        (TokenType.NUMBER, "2"),
        (TokenType.PLUS, "+"),
        (TokenType.NUMBER, "3"),
        (TokenType.NEWLINE, ""),
        (TokenType.EOF, ""),
    ]


def test_number_column_points_at_first_digit():
    tokens = lex("  42")
    assert tokens[0].column == 3


def test_non_ascii_digits_are_rejected():
    # str.isdigit() would accept these. See Global Constraints.
    with pytest.raises(LexError):
        lex("４")
