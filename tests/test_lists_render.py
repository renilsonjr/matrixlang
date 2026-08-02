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
