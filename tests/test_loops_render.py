"""Loop control — rendering wake and glitch in both faces."""

from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.render import render_ascii, render_glyph


def ascii_face(source):
    return render_ascii(parse(lex(source)))


def glyph_face(source):
    return render_glyph(parse(lex(source)))


def test_wake_renders_bare():
    source = "wake\n"
    assert ascii_face(source) == source


def test_glitch_renders_bare():
    source = "glitch\n"
    assert ascii_face(source) == source


def test_they_render_inside_a_loop_body():
    source = "dejavu true\n  wake\nflatline\n"
    assert ascii_face(source) == source


def test_they_render_in_the_glyph_face():
    assert glyph_face("wake\n") == "ﾉ\n"
    assert glyph_face("glitch\n") == "ﾕ\n"


def test_they_render_indented_inside_a_loop_in_the_glyph_face():
    # Indentation is structural in the rendered output, and a statement
    # with no operand is the shape most likely to lose it.
    source = "dejavu true\n  glitch\nflatline\n"
    assert glyph_face(source) == "ﾃ ｼ\n  ﾕ\nﾗ\n"


def test_a_trailing_comment_survives_the_render():
    source = "wake  # done\n"
    assert ascii_face(source) == source


def test_the_tree_view_names_both():
    from matrixlang.treeview import format_tree

    tree = format_tree(parse(lex("dejavu true\n  wake\n  glitch\nflatline\n")))
    assert "Wake" in tree
    assert "Glitch" in tree
