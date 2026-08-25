"""Seeded random tree generator for the §4.3 round-trip property test.

Hand-rolled on purpose (design S4-2): stdlib random.Random, bounded
sizes, no shrinking — a failing seed reproduces the tree exactly, and
trees stay small by construction.

Coverage is deliberate, not hoped-for: equal-precedence right children
and unary-over-binary shapes (the §6.4 parens rules), all three
else_body shapes (None / [] / populated), trivia honouring the §6.1
invariant, string/comment content chosen to smoke out corruption
(a quote, a backslash, a newline escape, a keyword spelling, a glyph
char, digits), calls with binary arguments and calls on calls (Stage
6), and — Stage 7 — empty and populated list literals, nested lists,
indexing a list literal and chaining an index over an index
(`[1,2][0]`, `xs[0][1]`), `length` over a binary expression, and
index-assignment statements. And — Stage 9 — splice and fork with both
children drawn from the full expression space (so `a fork (b splice
c)` and logical-over-comparison shapes occur), and `unplug` alongside
the other unary operators (so `unplug (a == b)` occurs). Stage 9
renumbered every level in render._LEVEL, and these are the shapes that
make a wrong level in that table loud instead of silent. And — Stage 10
— dict literals (empty and populated, keys drawn from the full
expression space rather than only strings, so a nonsense key like a
binary expression still exercises precedence), `keymaker` alongside the
other unary operators, and `oracle` alongside the other binary
operators: a node type added to the language but not here would sit
outside this property exactly as `decode`/`encode` once did, silently.
And, for string methods (#132) — `fold` and `trim` alongside the other
unary operators, and `cleave` alongside the other binary operators.
`cleave` sits on a precedence rung of its own between comparison and
term (parser._CLEAVE_OPS), which renumbered render._LEVEL end to end;
`(a cleave b) == c` and `a + b cleave c` are exactly the shapes that
would go silently wrong if that rung's level were off by one.
test_roundtrip has a test asserting this coverage actually occurs — a
generator that stops producing the hard shapes would quietly gut the
property.

And, for loop control — `wake` and `glitch` (STMT-2), the two node
types with no operand at all: the whole statement is the keyword. Both
sit in `gen_statement`'s BASE kind list (alongside
`declare`/`assign`/... , not gated on `depth > 0`), which is what gets
them generated as children of `While`/`If`/agent bodies rather than
only at a program's top level — a `wake` at the top level round-trips
trivially, and a nested one proves the node SURVIVES being a child
rather than a top-level statement (parses back to the same tree either
way). It proves nothing about indentation: `lexer.py` has no INDENT
concept, so render's leading whitespace is cosmetic and
`parse(render(t)) == t` holds whether or not a nested `wake`/`glitch`
is indented at all — deleting `pad +` from both of render.py's
branches for these two node types leaves every seed in this file
passing. Indentation for these two is guarded only by
`tests/test_loops_render.py`'s `test_they_render_inside_a_loop_body`
and `test_they_render_indented_inside_a_loop_in_the_glyph_face`;
deleting either as "redundant with the property" would remove the only
coverage of it. A node type outside this file is invisible to
parse(render(t)) == t exactly as `decode`/`encode` once were, silently
— that is what makes this file the third one (after render.py and
treeview.py) a new statement kind must touch.
"""

import random
from decimal import Decimal

from matrixlang.nodes import (
    Assign,
    Binary,
    BoolLiteral,
    Declare,
    DictLiteral,
    Expr,
    Glitch,
    If,
    Index,
    IndexAssign,
    ListLiteral,
    Name,
    NumberLiteral,
    Program,
    Stmt,
    StringLiteral,
    Call,
    ExprStmt,
    FunctionDef,
    Return,
    Trace,
    Unary,
    Wake,
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
# Decimals as well as whole numbers, and a trailing zero among them --
# `2.50` renders differently from `2.5` while comparing equal, so the
# corpus has to contain one for the render to be exercised at all.
_NUMBERS = [
    Decimal(0), Decimal(1), Decimal(7), Decimal(10), Decimal(42), Decimal(305),
    Decimal("0.5"), Decimal("2.50"), Decimal("1.25"), Decimal("0.001"),
]
_BINARY_OPS = [
    TokenType.EQ, TokenType.NEQ,
    TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE,
    TokenType.PLUS, TokenType.MINUS, TokenType.STAR, TokenType.SLASH,
    TokenType.ORACLE,
    TokenType.CLEAVE,
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
    kinds = [
        "declare", "assign", "trace", "return", "exprstmt", "indexassign",
        # Loop control. In the BASE list, not gated on depth: these are
        # leaves, and putting them here is what gets them nested inside
        # While, If and agent bodies -- which proves the node SURVIVES
        # being a child rather than a top-level statement. It does NOT
        # exercise the render's indentation: lexer.py has no INDENT
        # concept, so parse(render(t)) == t holds whether or not a
        # nested wake/glitch is indented -- deleting `pad +` from both
        # render.py branches for these two leaves this property green.
        # Indentation is guarded only by tests/test_loops_render.py's
        # two hand-written nested-render tests.
        "wake", "glitch",
    ]
    if depth > 0:
        kinds += ["if", "while", "agent"]
    kind = rng.choice(kinds)
    stmt: Stmt
    if kind == "wake":
        stmt = Wake()
    elif kind == "glitch":
        stmt = Glitch()
    elif kind == "indexassign":
        stmt = IndexAssign(
            gen_assignable_chain(rng) if rng.random() < 0.3 else Name(rng.choice(_IDENTS)),
            gen_expression(rng, 2),
            gen_expression(rng, 3),
        )
    elif kind == "return":
        # Both shapes: a bare jackout is an early exit and must not
        # round-trip into a returned value.
        stmt = Return(
            None if rng.random() < 0.3 else gen_expression(rng, 3)
        )
    elif kind == "exprstmt":
        stmt = ExprStmt(gen_call(rng, 2))
    elif kind == "agent":
        body = [gen_statement(rng, depth - 1) for _ in range(rng.randint(1, 2))]
        stmt = FunctionDef(
            rng.choice(_IDENTS),
            [rng.choice(_IDENTS) for _ in range(rng.randint(0, 3))],
            body,
            body_trailing=gen_comments(rng),
        )
    elif kind == "declare":
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
    if roll < 0.28:
        # Both children draw from the full depth-1 space, so equal-
        # precedence right children (R-PAREN-2) and nested chains occur
        # constantly rather than by luck.
        return Binary(
            gen_expression(rng, depth - 1),
            rng.choice(_BINARY_OPS),
            gen_expression(rng, depth - 1),
        )
    if roll < 0.40:
        # splice and fork, drawing both children from the full space so
        # `a fork (b splice c)` and logical-over-comparison shapes occur.
        # These are the shapes that catch a wrong level in render._LEVEL,
        # which Stage 9 renumbered end to end.
        return Binary(
            gen_expression(rng, depth - 1),
            rng.choice([TokenType.SPLICE, TokenType.FORK]),
            gen_expression(rng, depth - 1),
        )
    if roll < 0.50:
        # Every unary operator — all eight. Keeping this list complete is
        # what puts each keyword through the mixed-face round trip, which
        # nothing else covers: the hand-written render tests read one face
        # at a time. unplug over a binary is the shape that would render
        # as `unplug a == b` re-parsing differently if its level were
        # wrong. The operands are nonsense for `decode`, `encode` and
        # `keymaker` — the property under test is parse(render(t)) == t,
        # which never runs the tree.
        return Unary(
            rng.choice(
                [
                    TokenType.MINUS,
                    TokenType.LENGTH,
                    TokenType.UNPLUG,
                    TokenType.DECODE,
                    TokenType.ENCODE,
                    TokenType.KEYMAKER,
                    TokenType.FOLD,
                    TokenType.TRIM,
                ]
            ),
            gen_expression(rng, depth - 1),
        )
    if roll < 0.60:
        # Calls, with arguments drawn from the full space so f(a + b)
        # occurs constantly rather than by luck.
        return gen_call(rng, depth - 1)
    if roll < 0.66:
        # List and dict literals split this band down the middle rather
        # than dict stealing a slice from a neighbouring band. The split
        # reuses the `roll` already drawn for this node instead of a
        # fresh rng.random() call, so it doesn't shift the RNG stream
        # consumed by this node's children and siblings relative to
        # before dict literals existed.
        return gen_list(rng, depth - 1)
    if roll < 0.72:
        return gen_dict(rng, depth - 1)
    if roll < 0.82:
        return gen_index(rng, depth - 1)
    return gen_atom(rng)


def gen_call(rng: random.Random, depth: int) -> Call:
    """A call whose callee may itself be a call, so f()() occurs."""
    callee: Expr = Name(rng.choice(_IDENTS))
    if depth > 0 and rng.random() < 0.25:
        callee = gen_call(rng, depth - 1)
    args = [gen_expression(rng, max(0, depth)) for _ in range(rng.randint(0, 2))]
    return Call(callee, args)


def gen_list(rng: random.Random, depth: int) -> ListLiteral:
    """A list literal, empty a fifth of the time so [] is covered."""
    if rng.random() < 0.2:
        return ListLiteral([])
    return ListLiteral(
        [gen_expression(rng, max(0, depth)) for _ in range(rng.randint(1, 3))]
    )


def gen_dict(rng: random.Random, depth: int) -> DictLiteral:
    """A dict literal, empty a fifth of the time so {} is covered. Keys
    are drawn from the full expression space like values, not just string
    literals: parse(render(t)) == t never evaluates the tree, so a key
    that could never be a real key at runtime is still a valid shape to
    render and re-parse, and it's the shape most likely to expose a
    precedence bug."""
    if depth <= 0 or rng.random() < 0.2:
        return DictLiteral([])
    return DictLiteral(
        [
            (gen_expression(rng, depth - 1), gen_expression(rng, depth - 1))
            for _ in range(rng.randint(1, 3))
        ]
    )


def gen_index(rng: random.Random, depth: int) -> Index:
    """An index whose target may be a name, a list literal or another
    index, so xs[0][1] and [1,2][0] both occur."""
    roll = rng.random()
    target: Expr
    if roll < 0.5 or depth <= 0:
        target = Name(rng.choice(_IDENTS))
    elif roll < 0.75:
        target = gen_list(rng, depth - 1)
    else:
        target = gen_index(rng, depth - 1)
    return Index(target, gen_expression(rng, max(0, depth - 1)))


def gen_assignable_chain(rng: random.Random) -> Expr:
    """A Name, or an Index chain rooted in a Name -- the only shapes the
    parser accepts as the base of `xs[0] = v` / `xs[0][1] = v`. Unlike
    gen_index's target, this must never bottom out in a list literal:
    the parser only enters index-assignment when the statement starts
    with an IDENT (see parser._call/_primary), so `[1,2][0] = v` isn't a
    parseable statement even though it's a parseable expression. So
    unlike gen_index, this stays rooted in a Name at every level."""
    target: Expr = Name(rng.choice(_IDENTS))
    while rng.random() < 0.5:
        target = Index(target, gen_expression(rng, 1))
    return target


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
