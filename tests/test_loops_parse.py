"""Loop control — parsing wake and glitch."""

import pytest

from matrixlang.errors import ParseError
from matrixlang.lexer import lex
from matrixlang.nodes import Glitch, Wake, While
from matrixlang.parser import parse


def first(source):
    return parse(lex(source)).statements[0]


def test_wake_is_a_bare_statement():
    assert isinstance(first("wake\n"), Wake)


def test_glitch_is_a_bare_statement():
    assert isinstance(first("glitch\n"), Glitch)


def test_they_carry_the_keywords_position():
    # The Wake node's position is the `wake` keyword's own position, not
    # the statement list's -- it sits second here, after an unrelated
    # `trace`, so line/column can't just default to the start of the file.
    second = parse(lex("trace 1\nwake\n")).statements[1]
    assert isinstance(second, Wake)
    assert second.line == 2
    assert second.column == 1


def test_they_parse_inside_a_loop_body():
    loop = first("dejavu true\n  wake\nflatline\n")
    assert isinstance(loop, While)
    assert isinstance(loop.body[0], Wake)


def test_they_take_no_operand():
    # `wake 1` is not an early exit carrying a value -- there is no such
    # thing. The trailing expression has nowhere to go, so the statement
    # must end at the keyword and the parser must object to what follows.
    with pytest.raises(ParseError):
        parse(lex("wake 1\n"))


def test_they_are_statements_not_expressions():
    # The whole reason they are Stmt rather than Expr. If either reached
    # _primary, `construct x = wake` would build a tree for a program
    # with no meaning.
    with pytest.raises(ParseError):
        parse(lex("construct x = wake\n"))
    with pytest.raises(ParseError):
        parse(lex("trace glitch\n"))


def test_a_trailing_comment_attaches():
    statement = first("wake  # done\n")
    assert statement.trailing_comment == "# done"
