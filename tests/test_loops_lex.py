"""Loop control — lexing wake and glitch in both faces."""

from matrixlang.lexer import lex
from matrixlang.tokens import KEYWORDS, TokenType


def test_both_words_are_keywords():
    types = [t.type for t in lex("wake glitch\n")]
    assert types[:2] == [TokenType.WAKE, TokenType.GLITCH]


def test_both_words_lex_in_the_glyph_face():
    # The glyph face must lex to the same tokens as the ASCII face, or
    # D-03's round-trip claim is false for these two keywords.
    types = [t.type for t in lex("ﾉ ﾕ\n")]
    assert types[:2] == [TokenType.WAKE, TokenType.GLITCH]


def test_a_name_that_merely_starts_with_a_keyword_is_still_a_name():
    # `waken` must not lex as `wake` followed by `n`. The lexer reads a
    # whole word and looks it up, so this holds by construction -- but it
    # is what would turn `construct waken = 1` into a parse error in
    # somebody's existing program.
    types = [t.type for t in lex("waken glitches\n")]
    assert types[:2] == [TokenType.IDENT, TokenType.IDENT]


def test_registration_is_all_the_lexer_needs():
    # lexer.py builds its glyph table by walking GLYPHS and looking each
    # slot up in KEYWORDS, so registering a word in tokens.py and
    # glyphs.py is the whole of adding it to both faces.
    for word in ("wake", "glitch"):
        assert word in KEYWORDS
