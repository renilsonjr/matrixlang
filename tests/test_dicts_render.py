"""Stage 7 — rendering dictionaries in both faces, and the round trip.

The §4.3 criterion is what these protect: parse(render(t)) == t. A
renderer that collapses a duplicate key or mis-levels a node fails here
rather than silently changing what a program means.
"""

import pytest

from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.render import render_ascii, render_glyph


def roundtrip(source):
    tree = parse(lex(source))
    assert parse(lex(render_ascii(tree))) == tree, "ascii face"
    assert parse(lex(render_glyph(tree))) == tree, "glyph face"
    return tree


def test_dictionary_literal_renders_ascii():
    source = 'construct d = {"a": 1, "b": 2}\n'
    assert render_ascii(parse(lex(source))) == source


def test_empty_dictionary_literal_renders_ascii():
    source = "construct d = {}\n"
    assert render_ascii(parse(lex(source))) == source


def test_keymaker_and_oracle_render_ascii():
    source = 'trace keymaker d\ntrace d oracle "a"\n'
    assert render_ascii(parse(lex(source))) == source


def test_dictionary_round_trips_through_the_glyph_face():
    program = parse(lex('construct d = {"a": 1}\ntrace d oracle "a"\n'))
    assert parse(lex(render_glyph(program))) == program


def test_a_dictionary_inside_a_list_renders():
    source = 'construct xs = [{"a": 1}, {"b": 2}]\n'
    assert render_ascii(parse(lex(source))) == source


@pytest.mark.parametrize(
    "source",
    [
        "construct d = {}\n",
        'construct d = {"a": 1}\n',
        'construct d = {"a": 1, "b": 2}\n',
        'construct d = {"a": 1, "a": 2}\n',
        'construct d = {"a": 1 + 2}\n',
        'construct d = {"a": {"b": 1}}\n',
        "trace keymaker d\n",
        'trace d oracle "a"\n',
    ],
)
def test_dictionaries_round_trip(source):
    roundtrip(source)


def test_duplicate_keys_survive_rendering_as_two_entries():
    # entries is a list of pairs, not a dict -- collapsing a duplicate key
    # during rendering would lose a token and break the round trip.
    source = 'construct d = {"a": 1, "a": 2}\n'
    assert render_ascii(parse(lex(source))) == source


def test_the_glyph_face_uses_the_dict_glyphs():
    from matrixlang.glyphs import GLYPHS

    tree = parse(lex('construct d = {"a": 1, "b": 2}\n'))
    rendered = render_glyph(tree)
    assert GLYPHS["{"] in rendered
    assert GLYPHS["}"] in rendered
    assert GLYPHS[":"] in rendered
    assert GLYPHS[","] in rendered
    assert "{" not in rendered
    assert "}" not in rendered


def test_the_glyph_face_uses_the_keymaker_and_oracle_glyphs():
    from matrixlang.glyphs import GLYPHS

    tree = parse(lex('trace keymaker d\ntrace d oracle "a"\n'))
    rendered = render_glyph(tree)
    assert GLYPHS["keymaker"] in rendered
    assert GLYPHS["oracle"] in rendered
