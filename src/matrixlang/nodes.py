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
class Unary(Expr):
    op: TokenType
    operand: Expr


@dataclass
class Binary(Expr):
    left: Expr
    op: TokenType
    right: Expr


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
class Program(Node):
    statements: list[Stmt]
    trailing_comments: list[str] = field(default_factory=list, kw_only=True)
