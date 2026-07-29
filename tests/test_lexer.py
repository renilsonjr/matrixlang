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


def test_identifier_is_scanned():
    tokens = lex("counter")
    assert tokens[0].type is TokenType.IDENT
    assert tokens[0].lexeme == "counter"
    assert tokens[0].value is None


def test_keyword_is_recognised():
    # Acceptance case 2.
    assert kinds("construct") == [
        TokenType.CONSTRUCT,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_keyword_matching_does_not_fire_on_a_prefix():
    # Acceptance case 3. 'constructor' starts with 'construct'.
    tokens = lex("constructor = 1")
    assert tokens[0].type is TokenType.IDENT
    assert tokens[0].lexeme == "constructor"


def test_booleans_carry_python_bool_values():
    tokens = lex("true false")
    assert (tokens[0].type, tokens[0].value) == (TokenType.TRUE, True)
    assert (tokens[1].type, tokens[1].value) == (TokenType.FALSE, False)


def test_identifiers_may_contain_digits_and_underscores():
    tokens = lex("_x1 count_2")
    assert [t.lexeme for t in tokens[:2]] == ["_x1", "count_2"]


def test_identifiers_may_not_start_with_a_digit():
    assert kinds("1x") == [
        TokenType.NUMBER,
        TokenType.IDENT,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_katakana_is_not_an_identifier():
    # str.isalpha() would accept this. Stage 4 needs glyphs to stay unclaimed.
    with pytest.raises(LexError):
        lex("ｱ")


def test_assignment_statement_lexes_as_specified():
    # Acceptance case 1 — the parent spec's opening commit.
    assert kinds("x = 2 + 3") == [
        TokenType.IDENT,
        TokenType.ASSIGN,
        TokenType.NUMBER,
        TokenType.PLUS,
        TokenType.NUMBER,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_string_keeps_raw_lexeme_and_decoded_value():
    # Acceptance case 5.
    tokens = lex('"wake up, "')
    assert tokens[0].type is TokenType.STRING
    assert tokens[0].lexeme == '"wake up, "'
    assert tokens[0].value == "wake up, "


def test_string_escapes_are_decoded():
    tokens = lex(r'"a\"b\\c\nd"')
    assert tokens[0].value == 'a"b\\c\nd'


def test_string_concatenation_expression_lexes():
    assert kinds('"wake up, " + name') == [
        TokenType.STRING,
        TokenType.PLUS,
        TokenType.IDENT,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_unterminated_string_reports_the_opening_quote():
    # Acceptance case 8.
    with pytest.raises(LexError) as excinfo:
        lex('trace "unterminated')
    error = excinfo.value
    assert error.line == 1
    assert error.column == 7
    assert "unterminated" in str(error)


def test_newline_inside_string_is_unterminated():
    with pytest.raises(LexError) as excinfo:
        lex('"broken\n"')
    assert excinfo.value.line == 1


def test_unknown_escape_is_an_error():
    with pytest.raises(LexError) as excinfo:
        lex(r'"\q"')
    assert "\\q" in str(excinfo.value)


def test_empty_string_is_valid():
    tokens = lex('""')
    assert tokens[0].value == ""


def test_comment_is_emitted_not_discarded():
    # Acceptance case 6.
    tokens = lex("trace x  # wake up")
    assert [t.type for t in tokens] == [
        TokenType.TRACE,
        TokenType.IDENT,
        TokenType.COMMENT,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]
    assert tokens[2].lexeme == "# wake up"


def test_comment_stops_at_the_newline():
    assert kinds("# one\n# two\n") == [
        TokenType.COMMENT,
        TokenType.NEWLINE,
        TokenType.COMMENT,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_hash_inside_a_string_is_not_a_comment():
    tokens = lex('"# not a comment"')
    assert tokens[0].type is TokenType.STRING
    assert tokens[0].value == "# not a comment"


def test_comment_column_points_at_the_hash():
    tokens = lex("x # here")
    assert tokens[1].column == 3
