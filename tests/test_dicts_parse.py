"""Stage 7 — parsing dictionary literals, keymaker and oracle."""

import pytest

from matrixlang.errors import ParseError
from matrixlang.lexer import lex
from matrixlang.nodes import (
    DictLiteral,
    Name,
    Unary,
)
from matrixlang.parser import parse
from matrixlang.tokens import TokenType


def test_empty_dictionary_literal():
    program = parse(lex("construct d = {}\n"))
    assert program.statements[0].value == DictLiteral([])


def test_dictionary_literal_keeps_written_order():
    program = parse(lex('construct d = {"b": 1, "a": 2}\n'))
    entries = program.statements[0].value.entries
    assert [k.value for k, _ in entries] == ["b", "a"]


def test_dictionary_literal_keeps_a_duplicate_key():
    # The AST records what was written, not what it evaluates to. Folding
    # duplicates here would make render(parse(x)) lose a token and break
    # the D-03 round-trip property.
    program = parse(lex('construct d = {"a": 1, "a": 2}\n'))
    assert len(program.statements[0].value.entries) == 2


def test_dictionary_literal_rejects_a_trailing_comma():
    # Exactly how list literals behave; dictionaries inherit the rule.
    with pytest.raises(ParseError):
        parse(lex('construct d = {"a": 1,}\n'))


def test_dictionary_literal_rejects_a_newline_inside_braces():
    with pytest.raises(ParseError):
        parse(lex('construct d = {\n  "a": 1\n}\n'))


def test_keymaker_parses_like_length():
    program = parse(lex("trace keymaker d\n"))
    assert program.statements[0].value == Unary(TokenType.KEYMAKER, Name("d"))


def test_oracle_binds_tighter_than_unplug():
    # `unplug d oracle "k"` must mean `unplug (d oracle "k")`. The tight
    # reading is an error for every possible d.
    program = parse(lex('trace unplug d oracle "k"\n'))
    node = program.statements[0].value
    assert node.op is TokenType.UNPLUG
    assert node.operand.op is TokenType.ORACLE


def test_oracle_binds_tighter_than_splice():
    program = parse(lex('trace d oracle "k" splice e oracle "j"\n'))
    node = program.statements[0].value
    assert node.op is TokenType.SPLICE
    assert node.left.op is TokenType.ORACLE
    assert node.right.op is TokenType.ORACLE


def test_oracle_takes_a_full_term_on_the_right():
    # `_comparison` draws its operands from `_term`, so the concatenation
    # is the key rather than `d oracle "gr"` then a dangling `+ "ade"`.
    program = parse(lex('trace d oracle "gr" + "ade"\n'))
    node = program.statements[0].value
    assert node.op is TokenType.ORACLE
    assert node.right.op is TokenType.PLUS


def test_oracle_is_looser_than_equality_is_not_true():
    # Comparison is TIGHTER than equality, so this groups as
    # `(d oracle "k") == true`.
    program = parse(lex('trace d oracle "k" == true\n'))
    node = program.statements[0].value
    assert node.op is TokenType.EQ
    assert node.left.op is TokenType.ORACLE
