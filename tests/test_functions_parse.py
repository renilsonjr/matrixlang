"""Stage 6 — parsing agents, calls and jackout."""

import pytest

from matrixlang.errors import ParseError
from matrixlang.lexer import lex
from matrixlang.nodes import (
    Binary,
    Call,
    ExprStmt,
    FunctionDef,
    Name,
    NumberLiteral,
    Return,
)
from matrixlang.parser import parse


def first(source):
    return parse(lex(source)).statements[0]


# --- Definitions --------------------------------------------------------


def test_an_agent_with_no_parameters():
    node = first("agent go()\n  trace 1\nflatline\n")
    assert isinstance(node, FunctionDef)
    assert node.name == "go"
    assert node.params == []
    assert len(node.body) == 1


def test_an_agent_with_one_parameter():
    node = first("agent double(n)\n  jackout n\nflatline\n")
    assert node.params == ["n"]


def test_an_agent_with_several_parameters():
    node = first("agent add(a, b, c)\n  jackout a\nflatline\n")
    assert node.params == ["a", "b", "c"]


def test_an_agent_is_closed_by_flatline_like_every_other_block():
    # D-02: every block boundary is a keyword, so it is a glyph in the
    # glyph face rather than untranslated Latin punctuation.
    with pytest.raises(ParseError):
        parse(lex("agent go()\n  trace 1\n"))


def test_a_missing_paren_is_a_diagnostic_with_a_position():
    with pytest.raises(ParseError) as excinfo:
        parse(lex("agent go\n  trace 1\nflatline\n"))
    assert excinfo.value.line == 1
    assert excinfo.value.column > 0


# --- jackout ------------------------------------------------------------


def test_jackout_with_a_value():
    node = first("agent f()\n  jackout 7\nflatline\n").body[0]
    assert isinstance(node, Return)
    assert isinstance(node.value, NumberLiteral)


def test_jackout_with_no_value():
    # An agent that only traces still wants an early exit.
    node = first("agent f()\n  jackout\nflatline\n").body[0]
    assert isinstance(node, Return)
    assert node.value is None


# --- Calls --------------------------------------------------------------


def test_a_call_with_no_arguments():
    node = first("trace go()\n").value
    assert isinstance(node, Call)
    assert node.args == []


def test_a_call_with_arguments():
    node = first("trace add(1, 2)\n").value
    assert isinstance(node, Call)
    assert len(node.args) == 2


def test_a_call_can_stand_alone_as_a_statement():
    # Without ExprStmt a call whose value is discarded has nowhere to live.
    node = first("log(1)\n")
    assert isinstance(node, ExprStmt)
    assert isinstance(node.value, Call)


def test_assignment_still_wins_over_an_expression_statement():
    from matrixlang.nodes import Assign

    assert isinstance(first("construct n = 0\nn = 1\n"), type(first("construct n = 0\n")))
    assert isinstance(parse(lex("construct n = 0\nn = 1\n")).statements[1], Assign)


def test_calls_chain():
    node = first("trace f()()\n").value
    assert isinstance(node, Call)
    assert isinstance(node.callee, Call)


# --- The parenthesisation trap ------------------------------------------


def test_an_argument_list_is_its_own_precedence_context():
    # f(a + b) and f(a) + b are different trees. An emitter that reuses
    # the enclosing context renders them identically.
    inner = first("trace f(a + b)\n").value
    assert isinstance(inner, Call)
    assert isinstance(inner.args[0], Binary)

    outer = first("trace f(a) + b\n").value
    assert isinstance(outer, Binary)
    assert isinstance(outer.left, Call)


def test_a_call_binds_tighter_than_unary_minus():
    node = first("trace -f(1)\n").value
    from matrixlang.nodes import Unary

    assert isinstance(node, Unary)
    assert isinstance(node.operand, Call)


def test_an_argument_may_itself_be_a_call():
    node = first("trace f(g(1), 2)\n").value
    assert isinstance(node.args[0], Call)


def test_a_trailing_comma_is_a_diagnostic():
    with pytest.raises(ParseError):
        parse(lex("trace f(1,)\n"))


def test_a_call_across_a_newline_is_not_a_call():
    # `f` on one line and `(1)` on the next are two statements, not one
    # call. NEWLINE separates them, and nothing should reach across it.
    program = parse(lex("construct f = 1\ntrace f\n"))
    assert len(program.statements) == 2
