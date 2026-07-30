"""Canonical-form and face-table tests for the renderer.

The parenthesization tests are the load-bearing ones: there is no
Grouping node, so a renderer that ignores associativity (R-PAREN-2) or
unary operands (R-PAREN-3) emits source that parses to a DIFFERENT tree
— silently changed meaning, the worst failure this stage can have.
"""

from matrixlang.lexer import lex
from matrixlang.nodes import (
    Binary,
    BoolLiteral,
    If,
    Name,
    NumberLiteral,
    Program,
    StringLiteral,
    Trace,
    Unary,
)
from matrixlang.parser import parse
from matrixlang.render import render, render_ascii, render_glyph
from matrixlang.tokens import TokenType


def prog(*statements) -> Program:
    return Program(list(statements))


# --- literals -------------------------------------------------------------


def test_numbers_render_in_decimal():
    assert render_ascii(prog(Trace(NumberLiteral(42)))) == "trace 42\n"


def test_strings_render_quoted_with_escapes_reapplied():
    # NEVER values.to_display: that drops the quotes and leaves \n raw,
    # which renders a newline INSIDE a string literal — a lex error on
    # re-parse, §4.3 dead on arrival.
    value = 'say "no"\\' + "\n" + "end"
    expected = 'trace "say \\"no\\"\\\\\\nend"\n'
    assert render_ascii(prog(Trace(StringLiteral(value)))) == expected


def test_booleans_render_in_the_language_s_spelling():
    assert render_ascii(prog(Trace(BoolLiteral(True)))) == "trace true\n"
    assert render_ascii(prog(Trace(BoolLiteral(False)))) == "trace false\n"


# --- parenthesization (spec §6.4) ----------------------------------------


def test_r_paren_1_lower_precedence_children_get_parens():
    tree = prog(
        Trace(Binary(Binary(NumberLiteral(1), TokenType.PLUS, NumberLiteral(2)),
                     TokenType.STAR, NumberLiteral(3)))
    )
    assert render_ascii(tree) == "trace (1 + 2) * 3\n"


def test_r_paren_1_flat_left_chains_need_no_parens():
    tree = prog(
        Trace(Binary(Binary(NumberLiteral(1), TokenType.PLUS, NumberLiteral(2)),
                     TokenType.PLUS, NumberLiteral(3)))
    )
    assert render_ascii(tree) == "trace 1 + 2 + 3\n"


def test_r_paren_2_equal_precedence_right_children_get_parens():
    # Binary(1, +, Binary(2, +, 3)) is NOT the tree '1 + 2 + 3' parses to.
    # Rendering it without parens changes the tree; for '-' and '/' it
    # changes the VALUE: 10 - (3 - 2) is 9, 10 - 3 - 2 is 5.
    plus = prog(Trace(Binary(NumberLiteral(1), TokenType.PLUS,
                             Binary(NumberLiteral(2), TokenType.PLUS,
                                    NumberLiteral(3)))))
    assert render_ascii(plus) == "trace 1 + (2 + 3)\n"

    minus = prog(Trace(Binary(NumberLiteral(10), TokenType.MINUS,
                              Binary(NumberLiteral(3), TokenType.MINUS,
                                     NumberLiteral(2)))))
    assert render_ascii(minus) == "trace 10 - (3 - 2)\n"

    slash = prog(Trace(Binary(NumberLiteral(8), TokenType.SLASH,
                              Binary(NumberLiteral(4), TokenType.SLASH,
                                     NumberLiteral(2)))))
    assert render_ascii(slash) == "trace 8 / (4 / 2)\n"


def test_r_paren_3_binary_operands_of_unary_get_parens():
    # Unary(-, Binary(2, *, 3)) naively renders '-2 * 3', which re-parses
    # as Binary(Unary(-,2), *, 3): same value here, different tree — and
    # for '+' a different VALUE: -(2 + 3) is -5, -2 + 3 is 1.
    tree = prog(Trace(Unary(TokenType.MINUS,
                            Binary(NumberLiteral(2), TokenType.STAR,
                                   NumberLiteral(3)))))
    assert render_ascii(tree) == "trace -(2 * 3)\n"


def test_unary_needs_no_parens_for_atoms_or_nested_unary():
    assert render_ascii(prog(Trace(Unary(TokenType.MINUS, NumberLiteral(5))))) == (
        "trace -5\n"
    )
    tree = prog(Trace(Unary(TokenType.MINUS, Unary(TokenType.MINUS, Name("x")))))
    assert render_ascii(tree) == "trace --x\n"


def test_comparison_inside_equality_needs_no_parens_on_the_left():
    # 'a < b == c' parses as Binary(EQ, Binary(LT, a, b), c) — the same
    # tree — so no parens. The other nesting direction does need them.
    same = prog(Trace(Binary(Binary(Name("a"), TokenType.LT, Name("b")),
                             TokenType.EQ, Name("c"))))
    assert render_ascii(same) == "trace a < b == c\n"

    other = prog(Trace(Binary(Binary(Name("a"), TokenType.EQ, Name("b")),
                              TokenType.LT, Name("c"))))
    assert render_ascii(other) == "trace (a == b) < c\n"


# --- statements, blocks, comments ----------------------------------------


def test_the_stage_3_demo_renders_canonically():
    # The spec §7.1 program: same statements, blank line dropped (design
    # S4-1 — whitespace normalizes), 2-space indent per depth.
    source = (
        'construct n = 0\n'
        'construct name = "Neo"\n'
        '\n'
        'dejavu n < 3\n'
        '  redpill n == 1\n'
        '    trace "wake up, " + name\n'
        '  bluepill\n'
        '    trace n\n'
        '  flatline\n'
        '  n = n + 1\n'
        'flatline\n'
    )
    expected = (
        'construct n = 0\n'
        'construct name = "Neo"\n'
        'dejavu n < 3\n'
        '  redpill n == 1\n'
        '    trace "wake up, " + name\n'
        '  bluepill\n'
        '    trace n\n'
        '  flatline\n'
        '  n = n + 1\n'
        'flatline\n'
    )
    assert render_ascii(parse(lex(source))) == expected


def test_comments_survive_in_place():
    source = "# lead\ntrace 1  # tail\n# after everything\n"
    assert render_ascii(parse(lex(source))) == source


def test_body_trailing_comments_render_inside_the_block():
    source = "dejavu true\n  trace 1\n  # last words\nflatline\n"
    assert render_ascii(parse(lex(source))) == source


def test_an_empty_else_renders_its_bluepill_and_none_does_not():
    # else_body=[] and else_body=None are different trees (the Task 1
    # treeview pin); the renderer must keep them distinguishable in
    # SOURCE too, or the §4.3 round trip conflates them.
    with_empty = prog(If(BoolLiteral(True), [], []))
    assert render_ascii(with_empty) == "redpill true\nbluepill\nflatline\n"

    without = prog(If(BoolLiteral(True), [], None))
    assert render_ascii(without) == "redpill true\nflatline\n"


def test_an_empty_program_renders_empty():
    assert render_ascii(prog()) == ""


# --- faces ----------------------------------------------------------------


def test_the_glyph_face_maps_structure_and_only_structure():
    # ﾄ=trace ﾀ=+ ｧ=1 ｨ=2. Identifiers stay ASCII (D-03: in a wall of
    # green, the Latin text is the thing you need to find).
    tree = prog(Trace(Binary(NumberLiteral(1), TokenType.PLUS, NumberLiteral(2))))
    assert render_glyph(tree) == "ﾄ ｧ ﾀ ｨ\n"


def test_glyph_digits_map_per_digit():
    assert render_glyph(prog(Trace(NumberLiteral(42)))) == "ﾄ ｪｨ\n"


def test_identifiers_strings_and_comment_text_bypass_the_table():
    # 'x2' contains a digit; the string contains a keyword spelling and a
    # digit. Naive textual substitution corrupts both; the structure-aware
    # emitter cannot touch them. THE design argument, as a test.
    tree = parse(lex('construct x2 = "trace 42"  # note 42\n'))
    assert render_glyph(tree) == 'ｱ x2 ﾅ "trace 42"  ﾒ note 42\n'


def test_a_partial_face_renders_mixed_source():
    # Any subset of the table is a legal face — §6.3's mixed-face claim.
    tree = prog(Trace(Binary(NumberLiteral(1), TokenType.PLUS, NumberLiteral(2))))
    assert render(tree, {"trace": "ﾄ"}) == "ﾄ 1 + 2\n"


def test_glyph_blocks_keep_ascii_layout():
    tree = parse(lex("dejavu false\n  trace 1\nflatline\n"))
    assert render_glyph(tree) == "ﾃ ｷ\n  ﾄ ｧ\nﾗ\n"
