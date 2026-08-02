"""Indented text view of a MatrixLang syntax tree.

Presentation only: nothing here participates in parsing or in the Stage 4
round-trip. This output is the Stage 2 teaching artifact — the shape of
the tree IS the precedence lesson.
"""

from matrixlang.nodes import (
    Assign,
    Binary,
    BoolLiteral,
    Declare,
    Expr,
    Call,
    ExprStmt,
    FunctionDef,
    If,
    ListLiteral,
    Return,
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

_OPS: dict[TokenType, str] = {
    TokenType.PLUS: "+",
    TokenType.MINUS: "-",
    TokenType.STAR: "*",
    TokenType.SLASH: "/",
    TokenType.EQ: "==",
    TokenType.NEQ: "!=",
    TokenType.LT: "<",
    TokenType.GT: ">",
    TokenType.LTE: "<=",
    TokenType.GTE: ">=",
}


def format_tree(program: Program) -> str:
    lines: list[str] = ["Program"]
    for statement in program.statements:
        _statement(statement, 1, lines)
    for comment in program.trailing_comments:
        lines.append("  " + comment)
    return "\n".join(lines) + "\n"


def _statement(stmt: Stmt, depth: int, lines: list[str]) -> None:
    pad = "  " * depth
    for comment in stmt.leading_comments:
        lines.append(pad + comment)
    tail = f"  {stmt.trailing_comment}" if stmt.trailing_comment else ""
    if isinstance(stmt, Declare):
        lines.append(f"{pad}Declare '{stmt.name}'{tail}")
        _expression(stmt.value, depth + 1, lines)
    elif isinstance(stmt, Assign):
        lines.append(f"{pad}Assign '{stmt.name}'{tail}")
        _expression(stmt.value, depth + 1, lines)
    elif isinstance(stmt, Trace):
        lines.append(f"{pad}Trace{tail}")
        _expression(stmt.value, depth + 1, lines)
    elif isinstance(stmt, If):
        lines.append(f"{pad}If{tail}")
        lines.append(f"{pad}  condition:")
        _expression(stmt.condition, depth + 2, lines)
        lines.append(f"{pad}  then:")
        for child in stmt.then_body:
            _statement(child, depth + 2, lines)
        for comment in stmt.then_trailing:
            lines.append(f"{pad}    {comment}")
        if stmt.else_body is not None:
            lines.append(f"{pad}  else:")
            for child in stmt.else_body:
                _statement(child, depth + 2, lines)
            for comment in stmt.else_trailing:
                lines.append(f"{pad}    {comment}")
    elif isinstance(stmt, While):
        lines.append(f"{pad}While{tail}")
        lines.append(f"{pad}  condition:")
        _expression(stmt.condition, depth + 2, lines)
        lines.append(f"{pad}  body:")
        for child in stmt.body:
            _statement(child, depth + 2, lines)
        for comment in stmt.body_trailing:
            lines.append(f"{pad}    {comment}")
    elif isinstance(stmt, FunctionDef):
        params = ", ".join(stmt.params)
        lines.append(f"{pad}FunctionDef '{stmt.name}' ({params}){tail}")
        lines.append(f"{pad}  body:")
        for child in stmt.body:
            _statement(child, depth + 2, lines)
        for comment in stmt.body_trailing:
            lines.append(f"{pad}    {comment}")
    elif isinstance(stmt, Return):
        lines.append(f"{pad}Return{tail}")
        if stmt.value is not None:
            _expression(stmt.value, depth + 1, lines)
    elif isinstance(stmt, ExprStmt):
        lines.append(f"{pad}ExprStmt{tail}")
        _expression(stmt.value, depth + 1, lines)
    else:
        raise AssertionError(f"unhandled statement node: {type(stmt).__name__}")


def _expression(expr: Expr, depth: int, lines: list[str]) -> None:
    pad = "  " * depth
    if isinstance(expr, NumberLiteral):
        lines.append(f"{pad}NumberLiteral {expr.value}")
    elif isinstance(expr, StringLiteral):
        lines.append(f"{pad}StringLiteral {expr.value!r}")
    elif isinstance(expr, BoolLiteral):
        lines.append(f"{pad}BoolLiteral {str(expr.value).lower()}")
    elif isinstance(expr, Name):
        lines.append(f"{pad}Name '{expr.ident}'")
    elif isinstance(expr, Call):
        lines.append(f"{pad}Call")
        lines.append(f"{pad}  callee:")
        _expression(expr.callee, depth + 2, lines)
        # Printed even when empty: "no arguments" is a fact about the tree
        # and the shape is the lesson.
        lines.append(f"{pad}  args:")
        for arg in expr.args:
            _expression(arg, depth + 2, lines)
    elif isinstance(expr, Unary):
        lines.append(f"{pad}Unary {_OPS[expr.op]}")
        _expression(expr.operand, depth + 1, lines)
    elif isinstance(expr, Binary):
        lines.append(f"{pad}Binary {_OPS[expr.op]}")
        _expression(expr.left, depth + 1, lines)
        _expression(expr.right, depth + 1, lines)
    elif isinstance(expr, ListLiteral):
        lines.append(f"{pad}ListLiteral ({len(expr.elements)})")
        for element in expr.elements:
            _expression(element, depth + 1, lines)
    else:
        raise AssertionError(f"unhandled expression node: {type(expr).__name__}")
