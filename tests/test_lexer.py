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
