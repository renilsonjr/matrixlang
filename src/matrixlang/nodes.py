"""AST node definitions for MatrixLang.

Pure data. Imports only the token vocabulary — the parser depends on this
module, never the reverse.

Two equality rules matter for the Stage 4 round-trip criterion (parent
spec §4.3): comment trivia PARTICIPATES in equality; source positions DO
NOT. Rendering a tree and re-parsing it yields identical trivia but
different line/column numbers, so positions carry compare=False.
"""

from dataclasses import dataclass, field

from matrixlang.tokens import TokenType


@dataclass
class Node:
    line: int = field(default=0, kw_only=True, compare=False)
    column: int = field(default=0, kw_only=True, compare=False)


# --- Expressions ---------------------------------------------------------


@dataclass
class Expr(Node):
    pass


@dataclass
class NumberLiteral(Expr):
    value: int


@dataclass
class StringLiteral(Expr):
    value: str


@dataclass
class BoolLiteral(Expr):
    value: bool


@dataclass
class Name(Expr):
    ident: str


@dataclass
class JackIn(Expr):
    """Read one line of input. No operand — the source supplies it.

    A node of its own rather than a Unary with no operand, because every
    Unary carries one and a None operand would make every consumer test
    for it.
    """


@dataclass
class Unary(Expr):
    op: TokenType
    operand: Expr


@dataclass
class Binary(Expr):
    left: Expr
    op: TokenType
    right: Expr


@dataclass
class Call(Expr):
    """A call. `args` is its own precedence context — see render.py."""

    callee: Expr
    args: list[Expr]


@dataclass
class ListLiteral(Expr):
    """`[1, 2]`. Elements are their own precedence context, like Call.args."""

    elements: list[Expr]


@dataclass
class DictLiteral(Expr):
    """`{"a": 1}`. Entries are pairs rather than a dict so the AST records
    what was WRITTEN: a duplicate key written twice survives to render,
    which is what keeps D-03's round-trip property true. Each key and each
    value is its own precedence context, like ListLiteral.elements."""

    entries: list[tuple[Expr, Expr]]


@dataclass
class Index(Expr):
    """`xs[0]`. Postfix, so it binds tighter than every operator — see
    render.py's _CALL_LEVEL, which this shares for exactly that reason."""

    target: Expr
    index: Expr


# --- Statements ----------------------------------------------------------


@dataclass
class Stmt(Node):
    """Base statement. Trivia fields per language spec §6.1."""

    leading_comments: list[str] = field(default_factory=list, kw_only=True)
    trailing_comment: str | None = field(default=None, kw_only=True)


@dataclass
class Declare(Stmt):
    name: str
    value: Expr


@dataclass
class Assign(Stmt):
    name: str
    value: Expr


@dataclass
class IndexAssign(Stmt):
    """`xs[0] = 9`. The first statement in the language that mutates a
    VALUE rather than rebinding a NAME — which is what makes cyclic
    lists reachable. See the Stage 7 design §3."""

    target: Expr
    index: Expr
    value: Expr


@dataclass
class Trace(Stmt):
    value: Expr


@dataclass
class If(Stmt):
    """then_trailing/else_trailing hold comments after each body's last
    statement — the per-body analogue of Program.trailing_comments."""

    condition: Expr
    then_body: list[Stmt]
    else_body: list[Stmt] | None = None
    then_trailing: list[str] = field(default_factory=list, kw_only=True)
    else_trailing: list[str] = field(default_factory=list, kw_only=True)


@dataclass
class While(Stmt):
    condition: Expr
    body: list[Stmt]
    body_trailing: list[str] = field(default_factory=list, kw_only=True)


@dataclass
class FunctionDef(Stmt):
    """An agent. Keyword-delimited and closed by `flatline`, per D-02."""

    name: str
    params: list[str]
    body: list[Stmt]
    body_trailing: list[str] = field(default_factory=list, kw_only=True)


@dataclass
class Return(Stmt):
    """`jackout`. A bare one produces NOTHING, which is legal in a
    procedure and an error the moment anybody uses the result."""

    value: Expr | None = None


@dataclass
class ExprStmt(Stmt):
    """An expression evaluated for its effect. Without this, a call whose
    value is discarded has nowhere to live."""

    value: Expr


@dataclass
class Program(Node):
    statements: list[Stmt]
    trailing_comments: list[str] = field(default_factory=list, kw_only=True)
