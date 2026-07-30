"""Seeded random tree generator for the §4.3 round-trip property test.

Hand-rolled on purpose (design S4-2): stdlib random.Random, bounded
sizes, no shrinking — a failing seed reproduces the tree exactly, and
trees stay small by construction.

Coverage is deliberate, not hoped-for: equal-precedence right children
and unary-over-binary shapes (the §6.4 parens rules), all three
else_body shapes (None / [] / populated), trivia honouring the §6.1
invariant, and string/comment content chosen to smoke out corruption
(a quote, a backslash, a newline escape, a keyword spelling, a glyph
char, digits). test_roundtrip has a test asserting this coverage
actually occurs — a generator that stops producing the hard shapes
would quietly gut the property.
"""

import random

from matrixlang.nodes import (
    Assign,
    Binary,
    BoolLiteral,
    Declare,
    Expr,
    If,
    Name,
    NumberLiteral,
    Program,
    Stmt,
    StringLiteral,
    Trace,
    Unary,
    While,
)
from matrixlang.tokens import TokenType

_IDENTS = ["x", "y", "neo", "trinity", "n1", "x2", "_tmp", "constructor"]
# 'flatline' inside a string and 'ｱ' in strings/comments prove that
# string contents and comment text bypass keyword recognition and the
# face table. '"' and '\\' and '\n' exercise every escape. '#' is the one
# character whose mishandling inside a comment would corrupt it — a stray
# unescaped '#' would (wrongly) look like the start of a NEW comment or
# change where one ends, so it belongs in both pools alongside the other
# corruption-prone characters.
_STRING_CHARS = [
    "a", "b", "z", " ", "_", '"', "\\", "\n", "0", "7", "#", "ｱ", "flatline",
]
_COMMENT_CHARS = ["a", "b", " ", "9", "+", "#", "ｱ", '"', "flatline"]
_NUMBERS = [0, 1, 7, 10, 42, 305]
_BINARY_OPS = [
    TokenType.EQ, TokenType.NEQ,
    TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE,
    TokenType.PLUS, TokenType.MINUS, TokenType.STAR, TokenType.SLASH,
]


def gen_program(rng: random.Random) -> Program:
    statements = [gen_statement(rng, 2) for _ in range(rng.randint(0, 5))]
    return Program(statements, trailing_comments=gen_comments(rng))


def gen_comment(rng: random.Random) -> str:
    # §6.1 invariant: starts with '#', contains no newline.
    body = "".join(rng.choice(_COMMENT_CHARS) for _ in range(rng.randint(0, 5)))
    return "#" + body


def gen_comments(rng: random.Random) -> list[str]:
    return [gen_comment(rng) for _ in range(rng.randint(0, 2))]


def gen_statement(rng: random.Random, depth: int) -> Stmt:
    kinds = ["declare", "assign", "trace"]
    if depth > 0:
        kinds += ["if", "while"]
    kind = rng.choice(kinds)
    stmt: Stmt
    if kind == "declare":
        stmt = Declare(rng.choice(_IDENTS), gen_expression(rng, 3))
    elif kind == "assign":
        stmt = Assign(rng.choice(_IDENTS), gen_expression(rng, 3))
    elif kind == "trace":
        stmt = Trace(gen_expression(rng, 3))
    elif kind == "if":
        else_body: list[Stmt] | None = rng.choice(
            [None, [], [gen_statement(rng, depth - 1)]]
        )
        stmt = If(
            gen_expression(rng, 2),
            [gen_statement(rng, depth - 1) for _ in range(rng.randint(0, 2))],
            else_body,
            then_trailing=gen_comments(rng),
            # else_trailing renders only when a bluepill exists; comments
            # there with else_body=None would be silently dropped and the
            # property would (rightly) fail on the generator's own bug.
            else_trailing=gen_comments(rng) if else_body is not None else [],
        )
    else:
        stmt = While(
            gen_expression(rng, 2),
            [gen_statement(rng, depth - 1) for _ in range(rng.randint(0, 2))],
            body_trailing=gen_comments(rng),
        )
    stmt.leading_comments = gen_comments(rng)
    if rng.random() < 0.4:
        stmt.trailing_comment = gen_comment(rng)
    return stmt


def gen_expression(rng: random.Random, depth: int) -> Expr:
    if depth == 0:
        return gen_atom(rng)
    roll = rng.random()
    if roll < 0.40:
        # Both children draw from the full depth-1 space, so equal-
        # precedence right children (R-PAREN-2) and nested chains occur
        # constantly rather than by luck.
        return Binary(
            gen_expression(rng, depth - 1),
            rng.choice(_BINARY_OPS),
            gen_expression(rng, depth - 1),
        )
    if roll < 0.55:
        # Unary over a full subexpression: the R-PAREN-3 shape.
        return Unary(TokenType.MINUS, gen_expression(rng, depth - 1))
    return gen_atom(rng)


def gen_atom(rng: random.Random) -> Expr:
    roll = rng.random()
    if roll < 0.40:
        return NumberLiteral(rng.choice(_NUMBERS))
    if roll < 0.60:
        return BoolLiteral(rng.choice([True, False]))
    if roll < 0.80:
        return Name(rng.choice(_IDENTS))
    return StringLiteral(
        "".join(rng.choice(_STRING_CHARS) for _ in range(rng.randint(0, 4)))
    )
