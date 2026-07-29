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
