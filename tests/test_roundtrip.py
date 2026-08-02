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
from matrixlang.nodes import Binary, Call, If, Unary
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


def test_the_generator_produces_the_stage_6_shapes_too():
    # Same reasoning as the test above, extended to the four new nodes.
    # A generator that never emits a call with a binary argument would let
    # the f(a + b) / f(a) + b bug through while looking green.
    from matrixlang.nodes import Call, ExprStmt, FunctionDef, Return

    call_with_binary_arg = False
    call_on_a_call = False
    bare_jackout = False
    jackout_with_value = False
    agent_with_params = False
    agent_without_params = False
    expression_statement = False

    def walk_expr(expr):
        nonlocal call_with_binary_arg, call_on_a_call
        if isinstance(expr, Call):
            if any(isinstance(a, Binary) for a in expr.args):
                call_with_binary_arg = True
            if isinstance(expr.callee, Call):
                call_on_a_call = True
            walk_expr(expr.callee)
            for arg in expr.args:
                walk_expr(arg)
        elif isinstance(expr, Binary):
            walk_expr(expr.left)
            walk_expr(expr.right)
        elif isinstance(expr, Unary):
            walk_expr(expr.operand)

    def walk_stmt(stmt):
        nonlocal bare_jackout, jackout_with_value
        nonlocal agent_with_params, agent_without_params, expression_statement
        if isinstance(stmt, Return):
            if stmt.value is None:
                bare_jackout = True
            else:
                jackout_with_value = True
                walk_expr(stmt.value)
        elif isinstance(stmt, ExprStmt):
            expression_statement = True
            walk_expr(stmt.value)
        elif isinstance(stmt, FunctionDef):
            if stmt.params:
                agent_with_params = True
            else:
                agent_without_params = True
            for child in stmt.body:
                walk_stmt(child)
        else:
            for attr in ("value", "condition"):
                node = getattr(stmt, attr, None)
                if node is not None:
                    walk_expr(node)
            for attr in ("body", "then_body", "else_body"):
                for child in getattr(stmt, attr, None) or []:
                    walk_stmt(child)

    for seed in range(300):
        for stmt in gen_program(random.Random(seed)).statements:
            walk_stmt(stmt)

    assert call_with_binary_arg, "no call with a binary argument was generated"
    assert call_on_a_call, "no call on a call was generated"
    assert bare_jackout, "no bare jackout was generated"
    assert jackout_with_value, "no jackout with a value was generated"
    assert agent_with_params, "no agent with parameters was generated"
    assert agent_without_params, "no agent without parameters was generated"
    assert expression_statement, "no expression statement was generated"


def test_the_generator_produces_the_stage_7_shapes_too():
    # Same reasoning as the two tests above, extended to lists. A
    # generator that never emits an index over a list literal would let
    # a precedence bug in [1,2][0] through while looking green.
    from matrixlang.nodes import Index, IndexAssign, ListLiteral, Unary
    from matrixlang.tokens import TokenType

    empty_list = False
    populated_list = False
    nested_list = False
    index_of_index = False
    index_of_literal = False
    length_over_binary = False
    index_assignment = False

    def walk_expr(expr):
        nonlocal empty_list, populated_list, nested_list
        nonlocal index_of_index, index_of_literal, length_over_binary
        if isinstance(expr, ListLiteral):
            if expr.elements:
                populated_list = True
            else:
                empty_list = True
            if any(isinstance(e, ListLiteral) for e in expr.elements):
                nested_list = True
            for element in expr.elements:
                walk_expr(element)
        elif isinstance(expr, Index):
            if isinstance(expr.target, Index):
                index_of_index = True
            if isinstance(expr.target, ListLiteral):
                index_of_literal = True
            walk_expr(expr.target)
            walk_expr(expr.index)
        elif isinstance(expr, Unary):
            if expr.op is TokenType.LENGTH and isinstance(expr.operand, Binary):
                length_over_binary = True
            walk_expr(expr.operand)
        elif isinstance(expr, Binary):
            walk_expr(expr.left)
            walk_expr(expr.right)
        elif isinstance(expr, Call):
            walk_expr(expr.callee)
            for arg in expr.args:
                walk_expr(arg)

    def walk_stmt(stmt):
        nonlocal index_assignment
        if isinstance(stmt, IndexAssign):
            index_assignment = True
            walk_expr(stmt.target)
            walk_expr(stmt.index)
            walk_expr(stmt.value)
            return
        for field in ("value", "condition"):
            if hasattr(stmt, field) and getattr(stmt, field) is not None:
                walk_expr(getattr(stmt, field))
        for child in getattr(stmt, "body", []):
            walk_stmt(child)
        for child in getattr(stmt, "then_body", []):
            walk_stmt(child)
        for child in getattr(stmt, "else_body", None) or []:
            walk_stmt(child)

    for seed in range(300):
        for statement in gen_program(random.Random(seed)).statements:
            walk_stmt(statement)

    assert empty_list, "no [] in 300 seeds"
    assert populated_list, "no populated list in 300 seeds"
    assert nested_list, "no nested list in 300 seeds"
    assert index_of_index, "no xs[0][1] shape in 300 seeds"
    assert index_of_literal, "no [1,2][0] shape in 300 seeds"
    assert length_over_binary, "no `length (a + b)` shape in 300 seeds"
    assert index_assignment, "no IndexAssign in 300 seeds"
