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
    BoolLiteral,
    Declare,
    Expr,
    Name,
    NumberLiteral,
    Program,
    Stmt,
    StringLiteral,
    Trace,
)
from matrixlang.values import to_display


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
        raise AssertionError(f"unhandled expression node: {type(expr).__name__}")


def run(program: Program, out: TextIO | None = None) -> None:
    """Execute a program. Convenience wrapper over Interpreter."""
    Interpreter(out=out).run(program)
