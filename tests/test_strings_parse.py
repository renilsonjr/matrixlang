"""String methods — where fold, trim and cleave bind."""

from matrixlang.lexer import lex
from matrixlang.nodes import Binary, Unary
from matrixlang.parser import parse, parse_expression
from matrixlang.tokens import TokenType


def expr(source):
    return parse_expression(lex(source))


def test_fold_is_a_unary_operator():
    tree = expr("fold s")
    assert isinstance(tree, Unary)
    assert tree.op is TokenType.FOLD


def test_trim_is_a_unary_operator():
    tree = expr("trim s")
    assert isinstance(tree, Unary)
    assert tree.op is TokenType.TRIM


def test_cleave_is_infix():
    tree = expr('s cleave ","')
    assert isinstance(tree, Binary)
    assert tree.op is TokenType.CLEAVE


def test_fold_binds_tighter_than_plus():
    # `fold a + b` is `(fold a) + b`, the same reading `length`, `decode`,
    # `encode` and `keymaker` already get: these operators PRODUCE a value
    # that the arithmetic then consumes.
    tree = expr("fold a + b")
    assert tree.op is TokenType.PLUS
    assert isinstance(tree.left, Unary)
    assert tree.left.op is TokenType.FOLD


def test_trim_binds_tighter_than_equality():
    # `trim a == b` is `(trim a) == b`. The loose reading would ask trim
    # for a boolean, which is an error for every possible a and b.
    tree = expr("trim a == b")
    assert tree.op is TokenType.EQ
    assert isinstance(tree.left, Unary)
    assert tree.left.op is TokenType.TRIM


def test_fold_over_fold_nests():
    tree = expr("fold fold s")
    assert tree.op is TokenType.FOLD
    assert tree.operand.op is TokenType.FOLD


def test_fold_over_trim_nests():
    tree = expr("fold trim s")
    assert tree.op is TokenType.FOLD
    assert tree.operand.op is TokenType.TRIM


def test_cleave_binds_looser_than_plus():
    # `a + b cleave ","` is `(a + b) cleave ","` -- concatenate, THEN
    # split. This is why cleave's rung sits below _term.
    tree = expr('a + b cleave ","')
    assert tree.op is TokenType.CLEAVE
    assert isinstance(tree.left, Binary)
    assert tree.left.op is TokenType.PLUS


def test_cleave_binds_tighter_than_equality():
    # `s cleave "," == xs` is `(s cleave ",") == xs` -- comparison is
    # looser. This is why cleave's rung sits above _comparison.
    tree = expr('s cleave "," == xs')
    assert tree.op is TokenType.EQ
    assert isinstance(tree.left, Binary)
    assert tree.left.op is TokenType.CLEAVE


def test_cleave_binds_tighter_than_ordering():
    tree = expr('s cleave "," < xs')
    assert tree.op is TokenType.LT
    assert tree.left.op is TokenType.CLEAVE


def test_cleave_binds_tighter_than_oracle():
    # `oracle` shares the comparison rung, so it must land on the same
    # side of cleave as `==` does.
    tree = expr('d oracle s cleave ","')
    assert tree.op is TokenType.ORACLE
    assert tree.right.op is TokenType.CLEAVE


def test_cleave_is_left_associative():
    # Nonsense as a program -- the outer cleave's left operand is a list
    # -- but the SHAPE is what a left-associative rung must produce, and
    # the parser never runs anything.
    tree = expr("a cleave b cleave c")
    assert tree.op is TokenType.CLEAVE
    assert isinstance(tree.left, Binary)
    assert tree.left.op is TokenType.CLEAVE
    assert tree.right.ident == "c"


def test_a_unary_word_over_a_cleave_needs_its_parens():
    # `length keymaker d` already has this shape: a prefix word binds
    # tightest, so reaching a binary result takes parentheses.
    tree = expr('length (s cleave ",")')
    assert tree.op is TokenType.LENGTH
    assert isinstance(tree.operand, Binary)
    assert tree.operand.op is TokenType.CLEAVE


def test_the_operators_work_in_a_whole_program():
    program = parse(lex('trace fold "Mouse"\n'))
    assert program.statements[0].value.op is TokenType.FOLD
