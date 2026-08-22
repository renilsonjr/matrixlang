import pytest

from matrixlang.glyphs import GLYPHS
from matrixlang.lexer import lex
from matrixlang.nodes import Binary, Unary
from matrixlang.parser import parse
from matrixlang.tokens import TokenType


def types(source):
    return [token.type for token in lex(source) if token.type is not TokenType.NEWLINE]


def first(source):
    return parse(lex(source)).statements[0].value


def test_bitwise_words_lex_as_keywords():
    assert types("mask merge flip invert uplink downlink") == [
        TokenType.MASK,
        TokenType.MERGE,
        TokenType.FLIP,
        TokenType.INVERT,
        TokenType.UPLINK,
        TokenType.DOWNLINK,
        TokenType.EOF,
    ]


@pytest.mark.parametrize("slot", ["mask", "merge", "flip", "invert", "uplink", "downlink"])
def test_each_bitwise_word_has_a_glyph(slot):
    assert slot in GLYPHS
    assert len(GLYPHS[slot]) == 1
    assert types(GLYPHS[slot]) == [getattr(TokenType, slot.upper()), TokenType.EOF]


def test_bitwise_operators_parse_with_conventional_precedence():
    parsed = first("construct x = a merge b flip c mask d uplink e + f\n")
    assert isinstance(parsed, Binary)
    assert parsed.op is TokenType.MERGE
    assert parsed.right.op is TokenType.FLIP
    assert parsed.right.right.op is TokenType.MASK
    assert parsed.right.right.right.op is TokenType.UPLINK
    assert parsed.right.right.right.right.op is TokenType.PLUS


def test_invert_is_a_unary_operator():
    parsed = first("construct x = invert a == b\n")
    assert isinstance(parsed, Binary)
    assert parsed.op is TokenType.EQ
    assert isinstance(parsed.left, Unary)
    assert parsed.left.op is TokenType.INVERT


@pytest.mark.parametrize(
    "source",
    [
        "construct x = 5 mask 3\n",
        "construct x = 5 merge 3 flip 1\n",
        "construct x = invert 5\n",
        "construct x = 1 uplink 3 downlink 1\n",
    ],
)
def test_bitwise_expressions_round_trip(source):
    from matrixlang.render import render_ascii, render_glyph

    tree = parse(lex(source))
    assert parse(lex(render_ascii(tree))) == tree
    assert parse(lex(render_glyph(tree))) == tree
