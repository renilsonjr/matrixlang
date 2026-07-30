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
