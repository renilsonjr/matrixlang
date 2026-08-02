from matrixlang.tokens import KEYWORDS, Token, TokenType


def test_all_fourteen_keywords_are_registered():
    assert set(KEYWORDS) == {
        "construct",
        "trace",
        "redpill",
        "bluepill",
        "dejavu",
        "flatline",
        "true",
        "false",
        # Stage 6
        "agent",
        "jackout",
        # Stage 7
        "length",
        # Stage 9
        "splice",
        "fork",
        "unplug",
    }


def test_keywords_map_to_distinct_token_types():
    assert len(set(KEYWORDS.values())) == len(KEYWORDS)
    assert KEYWORDS["construct"] is TokenType.CONSTRUCT
    assert KEYWORDS["dejavu"] is TokenType.DEJAVU


def test_token_carries_position_and_defaults_value_to_none():
    token = Token(TokenType.PLUS, "+", line=3, column=7)
    assert token.lexeme == "+"
    assert token.line == 3
    assert token.column == 7
    assert token.value is None


def test_token_is_hashable_and_compares_by_value():
    a = Token(TokenType.NUMBER, "2", 1, 1, 2)
    b = Token(TokenType.NUMBER, "2", 1, 1, 2)
    assert a == b
    assert len({a, b}) == 1
