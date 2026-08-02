"""Stage 7 — rendering lists in both faces, and the round trip.

The §4.3 criterion is what these protect: parse(render(t)) == t. A
renderer that drops a bracket or mis-levels a node fails here rather
than silently changing what a program means.
"""

import pytest

from matrixlang.glyphs import GLYPHS
from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.render import render_ascii, render_glyph


def roundtrip(source):
    tree = parse(lex(source))
    assert parse(lex(render_ascii(tree))) == tree, "ascii face"
    assert parse(lex(render_glyph(tree))) == tree, "glyph face"
    return tree


@pytest.mark.parametrize(
    "source",
    [
        "construct xs = []\n",
        "construct xs = [1]\n",
        "construct xs = [1, 2, 3]\n",
        "construct xs = [[1], [2]]\n",
        'construct xs = [1, "a", true]\n',
        "construct xs = [1 + 2, -3]\n",
    ],
)
def test_a_list_literal_round_trips(source):
    roundtrip(source)


def test_the_ascii_face_uses_brackets():
    tree = parse(lex("construct xs = [1, 2]\n"))
    assert render_ascii(tree) == "construct xs = [1, 2]\n"


def test_the_glyph_face_uses_the_bracket_glyphs():
    tree = parse(lex("construct xs = [1]\n"))
    rendered = render_glyph(tree)
    assert GLYPHS["["] in rendered
    assert GLYPHS["]"] in rendered
    assert "[" not in rendered


@pytest.mark.parametrize(
    "source",
    [
        "construct a = xs[0]\n",
        "construct a = xs[0][1]\n",
        "construct a = xs[n + 1]\n",
        "construct a = [1, 2][0]\n",
        "construct a = f()[0]\n",
        "construct a = -xs[0]\n",
    ],
)
def test_indexing_round_trips(source):
    roundtrip(source)


def test_indexing_binds_tighter_than_unary_minus():
    # -xs[0] is -(xs[0]), never (-xs)[0]. Rendering it as the latter
    # would be a different tree with a different meaning.
    tree = parse(lex("construct a = -xs[0]\n"))
    assert render_ascii(tree) == "construct a = -xs[0]\n"


def test_an_index_expression_keeps_its_parens_where_needed():
    tree = parse(lex("construct a = xs[n + 1]\n"))
    assert render_ascii(tree) == "construct a = xs[n + 1]\n"


@pytest.mark.parametrize(
    "source",
    [
        "construct n = length xs\n",
        "construct n = length xs + 1\n",
        "construct n = length [1, 2]\n",
        "construct n = length xs[0]\n",
        'construct n = length "Neo"\n',
        "construct n = -length xs\n",
    ],
)
def test_length_round_trips(source):
    roundtrip(source)


def test_length_renders_with_a_space_and_keeps_precedence():
    # Unary minus renders with no space (-x); length is a WORD and needs
    # one, or `length xs` becomes `lengthxs` and re-lexes as an identifier.
    tree = parse(lex("construct n = length xs + 1\n"))
    assert render_ascii(tree) == "construct n = length xs + 1\n"


def test_length_over_a_binary_gets_parens():
    tree = parse(lex("construct n = length (xs + ys)\n"))
    assert render_ascii(tree) == "construct n = length (xs + ys)\n"
