"""Dictionaries — lexing braces, colons, keymaker and oracle."""

from matrixlang.lexer import lex
from matrixlang.tokens import TokenType


def test_dictionary_punctuation_lexes():
    types = [t.type for t in lex('{"a": 1}\n')]
    assert types[:6] == [
        TokenType.LBRACE,
        TokenType.STRING,
        TokenType.COLON,
        TokenType.NUMBER,
        TokenType.RBRACE,
        TokenType.NEWLINE,
    ]


def test_keymaker_and_oracle_are_keywords():
    types = [t.type for t in lex("keymaker oracle\n")]
    assert types[:2] == [TokenType.KEYMAKER, TokenType.ORACLE]


def test_keymaker_and_oracle_lex_in_the_glyph_face():
    # The glyph face must lex to the same tokens as the ASCII face, or
    # D-03's round-trip claim is false for these two keywords.
    types = [t.type for t in lex("ﾔ ｵ\n")]
    assert types[:2] == [TokenType.KEYMAKER, TokenType.ORACLE]
