import pytest

from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.treeview import format_tree


def test_if_else_and_comments_render():
    source = (
        "# intro\n"
        "redpill true\n"
        "  trace 1  # then side\n"
        "bluepill\n"
        "  trace 2\n"
        "flatline\n"
    )
    assert format_tree(parse(lex(source))) == (
        "Program\n"
        "  # intro\n"
        "  If\n"
        "    condition:\n"
        "      BoolLiteral true\n"
        "    then:\n"
        "      Trace  # then side\n"
        "        NumberLiteral 1\n"
        "    else:\n"
        "      Trace\n"
        "        NumberLiteral 2\n"
    )


def test_while_unary_and_dangling_comments_render():
    # Covers the branches the If/Trace fixture never reaches: Declare, While,
    # Unary, Name, body_trailing, and Program.trailing_comments.
    source = (
        "construct total = -1\n"
        "dejavu total <= 10\n"
        "  total = total - 1\n"
        "  # loop tail\n"
        "flatline\n"
        "# program tail\n"
    )
    assert format_tree(parse(lex(source))) == (
        "Program\n"
        "  Declare 'total'\n"
        "    Unary -\n"
        "      NumberLiteral 1\n"
        "  While\n"
        "    condition:\n"
        "      Binary <=\n"
        "        Name 'total'\n"
        "        NumberLiteral 10\n"
        "    body:\n"
        "      Assign 'total'\n"
        "        Binary -\n"
        "          Name 'total'\n"
        "          NumberLiteral 1\n"
        "      # loop tail\n"
        "  # program tail\n"
    )


def test_block_body_dangling_comments_render_on_both_branches():
    source = (
        "redpill true\n"
        "  trace \"Neo\"\n"
        "  # then tail\n"
        "bluepill\n"
        "  trace false\n"
        "  # else tail\n"
        "flatline\n"
    )
    assert format_tree(parse(lex(source))) == (
        "Program\n"
        "  If\n"
        "    condition:\n"
        "      BoolLiteral true\n"
        "    then:\n"
        "      Trace\n"
        "        StringLiteral 'Neo'\n"
        "      # then tail\n"
        "    else:\n"
        "      Trace\n"
        "        BoolLiteral false\n"
        "      # else tail\n"
    )


@pytest.mark.parametrize(
    ("expression", "symbol"),
    [
        ("1 + 2", "+"),
        ("1 - 2", "-"),
        ("1 * 2", "*"),
        ("1 / 2", "/"),
        ("1 == 2", "=="),
        ("1 != 2", "!="),
        ("1 < 2", "<"),
        ("1 > 2", ">"),
        ("1 <= 2", "<="),
        ("1 >= 2", ">="),
    ],
)
def test_every_operator_in_the_table_renders(expression, symbol):
    # _OPS is a lookup: a missing entry is a KeyError on valid input, and a
    # wrong entry renders a lie. Ten cases, one per table row.
    text = format_tree(parse(lex(f"trace {expression}\n")))
    assert f"Binary {symbol}" in text


def test_an_empty_bluepill_block_still_prints_an_else_header():
    # else_body=[] (a bluepill with no statements) and else_body=None (no
    # bluepill at all) are DIFFERENT trees, and treeview's `is not None`
    # check is what keeps them distinguishable. Under a truthiness check
    # the empty else would vanish. Stage 4's renderer relies on the same
    # distinction, so this pins the AST contract behaviourally.
    from matrixlang.lexer import lex
    from matrixlang.parser import parse

    with_empty_else = format_tree(parse(lex("redpill true\nbluepill\nflatline\n")))
    assert "else:" in with_empty_else

    without_else = format_tree(parse(lex("redpill true\nflatline\n")))
    assert "else:" not in without_else


def test_a_list_literal_has_a_treeview_case():
    # treeview.py had no case for the Stage 6 nodes and `matrixlang parse`
    # crashed on an agent while 878 tests passed. One test per new node.
    out = format_tree(parse(lex("construct xs = [1, 2]\n")))
    assert "ListLiteral (2)" in out
    assert "NumberLiteral 1" in out


def test_an_index_has_a_treeview_case():
    from matrixlang.lexer import lex
    from matrixlang.parser import parse
    from matrixlang.treeview import format_tree

    out = format_tree(parse(lex("construct a = xs[0]\n")))
    assert "Index" in out
    assert "Name 'xs'" in out or "'xs'" in out
