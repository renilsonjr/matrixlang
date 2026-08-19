"""Canonical-form and face-table tests for the renderer.

The parenthesization tests are the load-bearing ones: there is no
Grouping node, so a renderer that ignores associativity (R-PAREN-2) or
unary operands (R-PAREN-3) emits source that parses to a DIFFERENT tree
— silently changed meaning, the worst failure this stage can have.
"""

import ast
import string
from pathlib import Path

from matrixlang.glyphs import GLYPHS
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
from matrixlang.render import _OPS, render, render_ascii, render_glyph
from matrixlang.tokens import TokenType

_RENDER_SRC = Path(__file__).parent.parent / "src" / "matrixlang" / "render.py"


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


def _slots_the_renderer_can_emit() -> set[str]:
    """Every slot `render.py` can pass through `_map(face, slot)`.

    I-2: `_map` is `face.get(slot, slot)` — a slot the renderer names but
    GLYPHS lacks silently falls back to its ASCII spelling INSIDE the
    glyph face, and the §4.3 round-trip property cannot see that: ASCII
    text embedded in the glyph face still lexes and still round-trips.
    So this derives the vocabulary from render.py's own tables instead of
    retyping a second list — the point is that a future stage teaching
    the renderer a new operator or keyword, without adding it to GLYPHS,
    must make THIS test fail on its own, the same way it would silently
    slip past every round-trip seed.

    Most slots reach `_map` as a literal string argument (`_map(face,
    "trace")`, `_map(face, "(")`, ...), or as a ternary between two
    literals (`_map(face, "true" if expr.value else "false")`); walking
    render.py's AST for `_map(face, ...)` calls and collecting every
    string constant reachable from the second argument (through nested
    ternaries) picks up the keywords, punctuation, and the comment marker
    without hand-copying them. Two slot families aren't literals-or-
    ternaries at their call site and are added separately, for the same
    non-duplication reason: `_OPS[expr.op]` (imported as `_OPS`, not
    retyped) and the per-digit call in `_number` (`string.digits` is a
    fact about base 10, not a copy of anything render.py could drift
    from).
    """

    def string_leaves(node: ast.expr) -> set[str]:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return {node.value}
        if isinstance(node, ast.IfExp):
            return string_leaves(node.body) | string_leaves(node.orelse)
        return set()

    tree = ast.parse(_RENDER_SRC.read_text(encoding="utf-8"))
    literal_slots: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_map"
            and len(node.args) == 2
        ):
            literal_slots |= string_leaves(node.args[1])
    return literal_slots | set(_OPS.values()) | set(string.digits)


def test_the_glyph_table_covers_every_slot_the_renderer_can_emit():
    # See _slots_the_renderer_can_emit for why this is derived rather
    # than hardcoded. A missing entry here means render(tree, GLYPH_FACE)
    # can silently print ASCII where a glyph belongs.
    assert _slots_the_renderer_can_emit() <= set(GLYPHS)


def test_both_faces_round_trip_a_program_using_input():
    # D-03: parse(lex(render_X(t))) == t, for both faces. A word operator
    # rendered without a separator would re-lex as one identifier, which
    # is precisely what this catches.
    source = "construct n = decode jackin + 1\ntrace n\n"
    tree = parse(lex(source))
    for render in (render_ascii, render_glyph):
        assert parse(lex(render(tree))) == tree, f"{render.__name__} did not round-trip"


def test_the_ascii_face_spells_the_keywords_out():
    tree = parse(lex("construct n = decode jackin\n"))
    rendered = render_ascii(tree)
    assert "decode jackin" in rendered


def test_the_glyph_face_uses_the_table_not_the_words():
    from matrixlang.glyphs import GLYPHS

    tree = parse(lex("construct n = decode jackin\n"))
    rendered = render_glyph(tree)
    assert GLYPHS["decode"] in rendered
    assert GLYPHS["jackin"] in rendered
    assert "decode" not in rendered
    assert "jackin" not in rendered
