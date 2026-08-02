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


# --- unplug's shape -----------------------------------------------------


def first(source):
    return parse(lex(source)).statements[0]


def test_unplug_is_a_unary_over_the_whole_comparison():
    # THE precedence test for unplug. `unplug n == 1` must be
    # unplug (n == 1). The C reading, (unplug n) == 1, is an error for
    # every possible n — either n is not boolean and unplug fails, or it
    # is and a boolean is compared to an integer.
    from matrixlang.nodes import Binary, Unary

    parsed = first("construct b = unplug n == 1\n").value
    assert isinstance(parsed, Unary)
    assert parsed.op is TokenType.UNPLUG
    assert isinstance(parsed.operand, Binary)
    assert parsed.operand.op is TokenType.EQ


def test_unplug_nests():
    from matrixlang.nodes import Unary

    parsed = first("construct b = unplug unplug flag\n").value
    assert isinstance(parsed, Unary)
    assert isinstance(parsed.operand, Unary)


def test_unplug_over_a_parenthesised_expression():
    from matrixlang.nodes import Binary, Unary

    parsed = first("construct b = unplug (a == b)\n").value
    assert isinstance(parsed, Unary)
    assert isinstance(parsed.operand, Binary)


# --- unplug round-trips -------------------------------------------------


def roundtrip(source):
    from matrixlang.render import render_ascii, render_glyph

    tree = parse(lex(source))
    assert parse(lex(render_ascii(tree))) == tree, "ascii face"
    assert parse(lex(render_glyph(tree))) == tree, "glyph face"
    return tree


@pytest.mark.parametrize(
    "source",
    [
        "construct b = unplug flag\n",
        "construct b = unplug n == 1\n",
        "construct b = unplug unplug flag\n",
        "construct b = unplug (a == b)\n",
    ],
)
def test_unplug_round_trips(source):
    roundtrip(source)


def test_unplug_renders_with_a_separator_and_no_parens_over_a_comparison():
    # A word operator needs the space or `unplug flag` becomes
    # `unplugflag` and re-lexes as one identifier. And because unplug
    # binds LOOSER than comparison, no parens are needed here — adding
    # them would be harmless but adding them in the wrong place would not.
    from matrixlang.render import render_ascii

    tree = parse(lex("construct b = unplug n == 1\n"))
    assert render_ascii(tree) == "construct b = unplug n == 1\n"
