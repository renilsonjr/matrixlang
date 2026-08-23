"""String methods — lexing fold, trim and cleave in both faces."""

from matrixlang.lexer import lex
from matrixlang.tokens import KEYWORDS, TokenType


def test_the_three_words_are_keywords():
    types = [t.type for t in lex("fold trim cleave\n")]
    assert types[:3] == [TokenType.FOLD, TokenType.TRIM, TokenType.CLEAVE]


def test_the_three_words_lex_in_the_glyph_face():
    # The glyph face must lex to the same tokens as the ASCII face, or
    # D-03's round-trip claim is false for these three keywords.
    types = [t.type for t in lex("ﾊ ﾘ ﾛ\n")]
    assert types[:3] == [TokenType.FOLD, TokenType.TRIM, TokenType.CLEAVE]


def test_a_name_that_merely_starts_with_a_keyword_is_still_a_name():
    # `folder` must not lex as `fold` followed by `er`. The lexer reads a
    # whole word and looks it up, so this holds by construction -- but it
    # is the failure that would turn `construct folder = 1` into a parse
    # error in somebody's existing program, so it is worth pinning.
    types = [t.type for t in lex("folder trimmed cleaver\n")]
    assert types[:3] == [TokenType.IDENT, TokenType.IDENT, TokenType.IDENT]


def test_registration_is_all_the_lexer_needs():
    # lexer.py builds its glyph table by walking GLYPHS and looking each
    # slot up in KEYWORDS, so registering a word in tokens.py and
    # glyphs.py is the whole of adding it to both faces. This asserts the
    # mechanism rather than the outcome: a future refactor that hard-codes
    # a keyword list somewhere else fails here with a reason.
    for word in ("fold", "trim", "cleave"):
        assert word in KEYWORDS
