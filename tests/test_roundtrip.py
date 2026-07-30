"""The §4.3 acceptance criterion, property-tested.

For any well-formed AST t:  parse(render_glyph(t)) == parse(render_ascii(t)) == t

Equality includes comment trivia and excludes positions (compare=False
on Node). The mixed face makes §6.3's mixed-face claim a tested
property instead of an asserted one — the emitter is table-driven, so
ANY subset of the table is a legal face.
"""

import random

import pytest

from matrixlang.glyphs import GLYPHS
from matrixlang.lexer import lex
from matrixlang.nodes import Binary, If, Unary
from matrixlang.parser import parse
from matrixlang.render import _LEVEL, render, render_ascii, render_glyph
from treegen import gen_program


def _mixed_face(rng: random.Random) -> dict[str, str]:
    return {slot: glyph for slot, glyph in GLYPHS.items() if rng.random() < 0.5}


@pytest.mark.parametrize("seed", range(300))
def test_round_trip(seed):
    rng = random.Random(seed)
    tree = gen_program(rng)

    ascii_source = render_ascii(tree)
    assert parse(lex(ascii_source)) == tree, f"seed {seed} ascii:\n{ascii_source}"

    glyph_source = render_glyph(tree)
    assert parse(lex(glyph_source)) == tree, f"seed {seed} glyph:\n{glyph_source}"

    mixed_source = render(tree, _mixed_face(rng))
    assert parse(lex(mixed_source)) == tree, f"seed {seed} mixed:\n{mixed_source}"


def test_the_generator_is_deterministic_per_seed():
    # The no-shrinking bargain (design S4-2) only holds if a seed
    # reproduces its tree exactly.
    assert gen_program(random.Random(7)) == gen_program(random.Random(7))


def test_the_generator_produces_the_shapes_the_parens_rules_need():
    # §6.4: "the property test only catches violations if the generator
    # produces those shapes, so the generator must produce them
    # deliberately." This is the check that it actually does — across
    # the same seeds the property runs on.
    equal_precedence_right = False
    unary_over_binary = False
    empty_else = False
    absent_else = False

    def walk_expr(expr):
        nonlocal equal_precedence_right, unary_over_binary
        if isinstance(expr, Binary):
            if (
                isinstance(expr.right, Binary)
                and _LEVEL[expr.right.op] == _LEVEL[expr.op]
            ):
                equal_precedence_right = True
            walk_expr(expr.left)
            walk_expr(expr.right)
        elif isinstance(expr, Unary):
            if isinstance(expr.operand, Binary):
                unary_over_binary = True
            walk_expr(expr.operand)

    def walk_stmt(stmt):
        nonlocal empty_else, absent_else
        if isinstance(stmt, If):
            if stmt.else_body == []:
                empty_else = True
            if stmt.else_body is None:
                absent_else = True
            for child in stmt.then_body + (stmt.else_body or []):
                walk_stmt(child)
            walk_expr(stmt.condition)
        else:
            for field in ("value", "condition"):
                if hasattr(stmt, field):
                    walk_expr(getattr(stmt, field))
            for child in getattr(stmt, "body", []):
                walk_stmt(child)

    for seed in range(300):
        for statement in gen_program(random.Random(seed)).statements:
            walk_stmt(statement)

    assert equal_precedence_right, "no R-PAREN-2 shape in 300 seeds"
    assert unary_over_binary, "no R-PAREN-3 shape in 300 seeds"
    assert empty_else, "no empty-else If in 300 seeds"
    assert absent_else, "no else-less If in 300 seeds"
