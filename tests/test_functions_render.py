"""Stage 6 — the round trip must survive four new node types.

§4.3 is the project's acceptance criterion: for any tree, rendering it in
either face and re-parsing gives back an identical tree, comments and all.
Four new nodes is four new ways for that to quietly stop being true.
"""

import pytest

from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.render import render_ascii, render_glyph

PROGRAMS = [
    "agent go()\n  trace 1\nflatline\n",
    "agent double(n)\n  jackout n * 2\nflatline\n",
    "agent add(a, b, c)\n  jackout a + b + c\nflatline\n",
    "agent f()\n  jackout\nflatline\n",
    "agent f()\n  trace 1\nflatline\nf()\n",
    "trace f(1, 2)\n",
    "trace f(a + b)\n",
    "trace f(a) + b\n",
    "trace f(g(1), 2)\n",
    "trace -f(1)\n",
    "trace f()()\n",
    "trace (a + b) * f(c)\n",
    "agent fib(n)\n  redpill n < 2\n    jackout n\n  flatline\n"
    "  jackout fib(n - 1) + fib(n - 2)\nflatline\ntrace fib(10)\n",
    "# leading\nagent f(n) # trailing\n  jackout n\nflatline\n",
    "agent outer(n)\n  agent inner(m)\n    jackout n + m\n  flatline\n"
    "  jackout inner\nflatline\n",
]


@pytest.mark.parametrize("source", PROGRAMS)
def test_the_ascii_face_round_trips(source):
    tree = parse(lex(source))
    assert parse(lex(render_ascii(tree))) == tree


@pytest.mark.parametrize("source", PROGRAMS)
def test_the_glyph_face_round_trips(source):
    tree = parse(lex(source))
    assert parse(lex(render_glyph(tree))) == tree


@pytest.mark.parametrize("source", PROGRAMS)
def test_both_faces_produce_the_same_tree(source):
    tree = parse(lex(source))
    assert parse(lex(render_ascii(tree))) == parse(lex(render_glyph(tree)))


# --- The parenthesisation trap, directed ---------------------------------


def test_an_argument_does_not_inherit_the_enclosing_context():
    # f(a + b) and f(a) + b are different trees. An emitter that reuses
    # the enclosing precedence renders them identically.
    inner = parse(lex("trace f(a + b)\n"))
    outer = parse(lex("trace f(a) + b\n"))
    assert render_ascii(inner) != render_ascii(outer)
    assert parse(lex(render_ascii(inner))) == inner
    assert parse(lex(render_ascii(outer))) == outer


def test_a_call_on_a_binary_callee_keeps_its_parens():
    tree = parse(lex("trace (a + b)(c)\n"))
    assert parse(lex(render_ascii(tree))) == tree


def test_unary_applied_to_a_call_round_trips():
    tree = parse(lex("trace -f(1)\n"))
    assert parse(lex(render_ascii(tree))) == tree


def test_the_glyph_face_uses_the_language_glyphs_for_the_new_slots():
    from matrixlang.glyphs import GLYPHS

    rendered = render_glyph(parse(lex("agent f(a, b)\n  jackout a\nflatline\n")))
    assert GLYPHS["agent"] in rendered
    assert GLYPHS["jackout"] in rendered
    assert GLYPHS[","] in rendered


# --- treeview -----------------------------------------------------------


def test_the_tree_view_handles_every_new_node():
    # `matrixlang parse` crashed on an agent while 871 tests passed. The
    # suite covered the round trip and the interpreter and never asked
    # whether the teaching view could print the thing.
    from matrixlang.treeview import format_tree

    source = (
        "agent add(a, b)\n"
        "  jackout a + b\n"
        "flatline\n"
        "add(1, 2)\n"
        "agent bare()\n"
        "  jackout\n"
        "flatline\n"
    )
    out = format_tree(parse(lex(source)))
    assert "FunctionDef" in out
    assert "Return" in out
    assert "Call" in out
    assert "ExprStmt" in out


def test_the_tree_view_shows_an_agents_name_and_parameters():
    from matrixlang.treeview import format_tree

    out = format_tree(parse(lex("agent add(a, b)\n  jackout a\nflatline\n")))
    assert "add" in out
    assert "a, b" in out
