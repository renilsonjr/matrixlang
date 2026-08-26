"""Stage 7 — the three new lexical units, in both faces.

The glyph path is not hand-written: lexer._GLYPH_TOKENS builds itself by
walking GLYPHS and looking each slot up in KEYWORDS/_DOUBLE/_SINGLE. So
adding the slots is what makes the glyph face work, and these tests are
what prove that machinery actually covered the new entries.
"""

import pytest

from matrixlang.glyphs import GLYPHS
from matrixlang.lexer import lex
from matrixlang.tokens import TokenType


def types(source):
    return [t.type for t in lex(source) if t.type is not TokenType.NEWLINE]


def test_brackets_lex_in_the_ascii_face():
    assert types("[]") == [
        TokenType.LBRACKET,
        TokenType.RBRACKET,
        TokenType.EOF,
    ]


def test_brackets_lex_in_the_glyph_face():
    assert types(GLYPHS["["] + GLYPHS["]"]) == [
        TokenType.LBRACKET,
        TokenType.RBRACKET,
        TokenType.EOF,
    ]


def test_length_is_a_keyword_not_an_identifier():
    # If `length` were left out of KEYWORDS it would lex as IDENT and the
    # parser would report a baffling error two stages from the cause.
    assert types("length") == [TokenType.LENGTH, TokenType.EOF]


def test_length_lexes_in_the_glyph_face():
    assert types(GLYPHS["length"]) == [TokenType.LENGTH, TokenType.EOF]


def test_a_mixed_face_list_lexes():
    # Mixed-face source is a tested property of this language, not an
    # accident: glyphs and ASCII occupy disjoint alphabets.
    assert types("[1" + GLYPHS["]"]) == [
        TokenType.LBRACKET,
        TokenType.NUMBER,
        TokenType.RBRACKET,
        TokenType.EOF,
    ]


def test_an_identifier_starting_with_length_is_still_an_identifier():
    assert types("lengths") == [TokenType.IDENT, TokenType.EOF]


@pytest.mark.parametrize("slot", ["[", "]", "length"])
def test_each_new_slot_has_a_glyph(slot):
    assert slot in GLYPHS
    assert len(GLYPHS[slot]) == 1


def test_the_table_is_still_bijective():
    # 56 since `%`; the same count tests/test_glyphs.py tracks.
    assert len(set(GLYPHS.values())) == len(GLYPHS) == 56
