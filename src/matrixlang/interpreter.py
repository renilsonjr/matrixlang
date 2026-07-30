"""The MatrixLang tree-walking interpreter: syntax tree in, effects out.

The environment is a dictionary. That is not a simplification for teaching
purposes — with no functions and no closures yet (spec §5), a flat dict is
the whole of what scope means in this language.

This module consumes a Program node and nothing else. It never imports the
lexer, the parser or the CLI, so Stage 4 can hand it a tree that came from
either source face.
"""

import sys
from typing import TextIO

from matrixlang.errors import RuntimeErrorML
from matrixlang.nodes import (
    Assign,
    Binary,
    BoolLiteral,
    Declare,
    Expr,
    Name,
    NumberLiteral,
    Program,
    Stmt,
    StringLiteral,
    Trace,
    Unary,
)
from matrixlang.tokens import TokenType
from matrixlang.values import is_int, is_str, to_display, type_name


class Interpreter:
    def __init__(self, out: TextIO | None = None) -> None:
        self.environment: dict[str, object] = {}
        self._out = sys.stdout if out is None else out

    def run(self, program: Program) -> None:
        for statement in program.statements:
            self._execute(statement)

    # --- statements -------------------------------------------------------

    def _execute(self, stmt: Stmt) -> None:
        if isinstance(stmt, Trace):
            print(to_display(self._evaluate(stmt.value)), file=self._out)
        elif isinstance(stmt, Declare):
            if stmt.name in self.environment:
                raise RuntimeErrorML(
                    f"'{stmt.name}' is already declared", stmt.line, stmt.column
                )
            self.environment[stmt.name] = self._evaluate(stmt.value)
        elif isinstance(stmt, Assign):
            if stmt.name not in self.environment:
                raise RuntimeErrorML(
                    f"'{stmt.name}' is not declared — use 'construct' first",
                    stmt.line,
                    stmt.column,
                )
            self.environment[stmt.name] = self._evaluate(stmt.value)
        else:
            raise AssertionError(f"unhandled statement node: {type(stmt).__name__}")

    # --- expressions ------------------------------------------------------

    def _evaluate(self, expr: Expr) -> object:
        if isinstance(expr, NumberLiteral):
            return expr.value
        if isinstance(expr, StringLiteral):
            return expr.value
        if isinstance(expr, BoolLiteral):
            return expr.value
        if isinstance(expr, Name):
            if expr.ident not in self.environment:
                raise RuntimeErrorML(
                    f"'{expr.ident}' is not declared", expr.line, expr.column
                )
            return self.environment[expr.ident]
        if isinstance(expr, Unary):
            operand = self._evaluate(expr.operand)
            self._require_int(operand, expr, "operand of unary '-'")
            return -operand
        if isinstance(expr, Binary):
            left = self._evaluate(expr.left)
            right = self._evaluate(expr.right)
            return self._binary(expr, left, right)
        raise AssertionError(f"unhandled expression node: {type(expr).__name__}")

    def _binary(self, node: Binary, left: object, right: object) -> object:
        if node.op is TokenType.PLUS and is_str(left) and is_str(right):
            return left + right
        return self._arithmetic(node, left, right)

    def _arithmetic(self, node: Binary, left: object, right: object) -> object:
        self._require_int(left, node, "left operand")
        self._require_int(right, node, "right operand")
        if node.op is TokenType.PLUS:
            return left + right
        if node.op is TokenType.MINUS:
            return left - right
        if node.op is TokenType.STAR:
            return left * right
        if node.op is TokenType.SLASH:
            if right == 0:
                raise RuntimeErrorML("cannot divide by zero", node.line, node.column)
            # Truncate toward zero. Python's // floors, which differs for
            # negatives: -7 // 2 is -4, but the spec requires -3.
            quotient = abs(left) // abs(right)
            return -quotient if (left < 0) != (right < 0) else quotient
        raise AssertionError(f"unhandled binary operator: {node.op.name}")

    def _require_int(self, value: object, node: Expr, role: str) -> None:
        if not is_int(value):
            raise RuntimeErrorML(
                f"{role} must be an integer, got {type_name(value)}",
                node.line,
                node.column,
            )


def run(program: Program, out: TextIO | None = None) -> None:
    """Execute a program. Convenience wrapper over Interpreter."""
    Interpreter(out=out).run(program)
