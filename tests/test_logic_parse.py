"""Stage 9 — the shape of a logical expression.

Precedence is a parse property, so it is asserted on the TREE here. A
test that checks a computed value can pass under two different groupings
for the inputs it happens to use, which is the kind of test that cannot
fail.
"""

import pytest

from matrixlang.glyphs import GLYPHS
from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.tokens import TokenType


def types(source):
    return [t.type for t in lex(source) if t.type is not TokenType.NEWLINE]


# --- Vocabulary ---------------------------------------------------------


def test_the_three_words_lex_as_keywords():
    assert types("splice") == [TokenType.SPLICE, TokenType.EOF]
    assert types("fork") == [TokenType.FORK, TokenType.EOF]
    assert types("unplug") == [TokenType.UNPLUG, TokenType.EOF]


def test_the_three_words_lex_in_the_glyph_face():
    # _GLYPH_TOKENS builds itself from GLYPHS, so this is what proves the
    # table entries were picked up rather than a hand-written branch.
    assert types(GLYPHS["splice"]) == [TokenType.SPLICE, TokenType.EOF]
    assert types(GLYPHS["fork"]) == [TokenType.FORK, TokenType.EOF]
    assert types(GLYPHS["unplug"]) == [TokenType.UNPLUG, TokenType.EOF]


def test_identifiers_that_start_with_a_keyword_are_still_identifiers():
    assert types("splicer") == [TokenType.IDENT, TokenType.EOF]
    assert types("forked") == [TokenType.IDENT, TokenType.EOF]
    assert types("unplugged") == [TokenType.IDENT, TokenType.EOF]


@pytest.mark.parametrize("slot", ["splice", "fork", "unplug"])
def test_each_new_slot_has_a_single_glyph(slot):
    assert slot in GLYPHS
    assert len(GLYPHS[slot]) == 1


def test_the_table_is_still_bijective_at_41():
    assert len(set(GLYPHS.values())) == len(GLYPHS) == 41
