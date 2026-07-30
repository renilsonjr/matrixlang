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
    BoolLiteral,
    Expr,
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
        raise AssertionError(f"unhandled expression node: {type(expr).__name__}")


def run(program: Program, out: TextIO | None = None) -> None:
    """Execute a program. Convenience wrapper over Interpreter."""
    Interpreter(out=out).run(program)
