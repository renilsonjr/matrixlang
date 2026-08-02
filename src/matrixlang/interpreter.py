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
from matrixlang.events import EventSink, Output, Statement, TextSink
from matrixlang.nodes import (
    Assign,
    Binary,
    BoolLiteral,
    Call,
    Declare,
    Expr,
    ExprStmt,
    FunctionDef,
    If,
    Index,
    IndexAssign,
    ListLiteral,
    Name,
    NumberLiteral,
    Program,
    Return,
    Stmt,
    StringLiteral,
    Trace,
    Unary,
    While,
)
from matrixlang.tokens import TokenType
from matrixlang.values import (
    NOTHING,
    CyclicValue,
    Function,
    Incomparable,
    equal,
    is_bool,
    is_function,
    is_int,
    is_list,
    is_str,
    to_display,
    type_name,
)

# Generous enough that no program a person writes on purpose will reach it,
# small enough that a runaway loop stops in well under a second. A guess,
# not a measurement — it will want raising once collections make loops over
# real data possible.
DEFAULT_MAX_STEPS = 200_000

_EQUALITY_OPS = (TokenType.EQ, TokenType.NEQ)
_ORDERING_OPS = (TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE)


class Environment:
    """One scope, linked to the one that encloses it.

    Replaces Stage 3's flat dict. `construct` defines here; `=` and a read
    walk outward to the nearest binding. That walk is the only thing
    lexical scoping is, and it is what functions gave the language a
    reason to have.
    """

    __slots__ = ("values", "parent")

    def __init__(self, parent: "Environment | None" = None) -> None:
        self.values: dict[str, object] = {}
        self.parent = parent

    def declare(self, name: str, value: object) -> bool:
        """Define in THIS scope. False if it is already declared here.

        Shadowing an outer binding is fine; redeclaring in the same scope
        is the error, exactly as it was when there was only one scope.
        """
        if name in self.values:
            return False
        self.values[name] = value
        return True

    def assign(self, name: str, value: object) -> bool:
        scope: Environment | None = self
        while scope is not None:
            if name in scope.values:
                scope.values[name] = value
                return True
            scope = scope.parent
        return False

    def lookup(self, name: str) -> tuple[bool, object]:
        scope: Environment | None = self
        while scope is not None:
            if name in scope.values:
                return True, scope.values[name]
            scope = scope.parent
        return False, None


class _Jackout(Exception):
    """A `jackout`, unwinding to the call site.

    Deliberately not a MatrixLangError. A jackout is not a diagnostic, and
    a stray `except MatrixLangError` must never swallow a return.
    """

    __slots__ = ("value",)

    def __init__(self, value: object) -> None:
        super().__init__()
        self.value = value


class Interpreter:
    def __init__(
        self,
        out: TextIO | None = None,
        sink: EventSink | None = None,
        max_steps: int | None = DEFAULT_MAX_STEPS,
    ) -> None:
        """Execute into a sink. `out` is the shorthand for "a TextSink on this".

        Both parameters exist because printing to a stream is still the common
        case and `Interpreter(out=buffer)` reads better than wrapping it by
        hand at every call site. `sink` wins if both are given.
        """
        self.globals = Environment()
        self._env = self.globals
        # Breadth, not depth. Python's recursion limit already bounds how
        # deep a call stack goes; nothing bounded how many statements ran.
        # A `dejavu true` loop never grows the stack, so a depth limit
        # would never catch it — this is what does.
        #
        # A step count rather than a wall-clock timeout because a clock is
        # not pure: enforcing a deadline needs a thread, and a test for it
        # needs sleep() and flakes in CI. A counter is exact — a test can
        # assert it raises at max_steps + 1 and not at max_steps.
        #
        # None disables it, which is what preserves every prior behaviour.
        self._max_steps = max_steps
        self._steps = 0
        self._sink = (
            sink
            if sink is not None
            else TextSink(sys.stdout if out is None else out)
        )

    def run(self, program: Program) -> None:
        for statement in program.statements:
            try:
                self._execute(statement)
            except _Jackout:
                raise RuntimeErrorML(
                    "'jackout' outside an agent",
                    statement.line,
                    statement.column,
                ) from None
            except RecursionError:
                raise RuntimeErrorML(
                    "expression is nested too deeply",
                    statement.line,
                    statement.column,
                ) from None

    # --- statements -------------------------------------------------------

    def _execute(self, stmt: Stmt) -> None:
        # Counted before anything else happens, so a statement that trips the
        # limit does not also emit an event or produce output.
        if self._max_steps is not None:
            self._steps += 1
            if self._steps > self._max_steps:
                raise RuntimeErrorML(
                    "program exceeded the step limit — likely an infinite loop",
                    stmt.line,
                    stmt.column,
                )

        # Emitted before the statement runs, and for every statement including
        # the children of a block. A loop body therefore emits once per
        # iteration, which is what lets a display show a `dejavu` loop running
        # rather than reporting it once it has finished.
        self._sink.emit(Statement(node=stmt, line=stmt.line))

        if isinstance(stmt, Trace):
            value = self._value_of(stmt.value, stmt)
            try:
                text = to_display(value)
            except CyclicValue:
                # NOT "expression is nested too deeply", which is what the
                # RecursionError path reports and which is false: a list
                # that contains itself may be one element long.
                raise RuntimeErrorML(
                    "cannot display a list that contains a cycle",
                    stmt.line,
                    stmt.column,
                ) from None
            self._sink.emit(Output(text=text, line=stmt.line))
        elif isinstance(stmt, Declare):
            value = self._value_of(stmt.value, stmt)
            if not self._env.declare(stmt.name, value):
                raise RuntimeErrorML(
                    f"'{stmt.name}' is already declared", stmt.line, stmt.column
                )
        elif isinstance(stmt, Assign):
            value = self._value_of(stmt.value, stmt)
            if not self._env.assign(stmt.name, value):
                raise RuntimeErrorML(
                    f"'{stmt.name}' is not declared — use 'construct' first",
                    stmt.line,
                    stmt.column,
                )
        elif isinstance(stmt, IndexAssign):
            target = self._value_of(stmt.target, stmt)
            index = self._value_of(stmt.index, stmt)
            value = self._value_of(stmt.value, stmt)
            if not is_list(target):
                raise RuntimeErrorML(
                    f"cannot index {type_name(target)}",
                    stmt.index.line,
                    stmt.index.column,
                )
            self._check_index(target, index, stmt.index)
            target[index] = value
        elif isinstance(stmt, FunctionDef):
            agent = Function(stmt.name, stmt.params, stmt.body, self._env)
            if not self._env.declare(stmt.name, agent):
                raise RuntimeErrorML(
                    f"'{stmt.name}' is already declared", stmt.line, stmt.column
                )
        elif isinstance(stmt, Return):
            value = NOTHING if stmt.value is None else self._evaluate(stmt.value)
            raise _Jackout(value)
        elif isinstance(stmt, ExprStmt):
            # NOTHING is legal here and nowhere else: this is the position
            # that makes a procedure a legal thing to write.
            self._evaluate(stmt.value)
        elif isinstance(stmt, If):
            if self._condition(stmt.condition):
                for child in stmt.then_body:
                    self._execute(child)
            # `is not None`, not truthiness: Stage 2 distinguishes None (no
            # `bluepill` at all) from [] (a `bluepill` with an empty body),
            # and both are falsy. The two behave identically here — an empty
            # body runs nothing either way — so no test can catch a change to
            # truthiness. Keep the identity check anyway: it states the AST's
            # contract, and Stage 4's renderer depends on that distinction.
            elif stmt.else_body is not None:
                for child in stmt.else_body:
                    self._execute(child)
        elif isinstance(stmt, While):
            while self._condition(stmt.condition):
                for child in stmt.body:
                    self._execute(child)
        else:
            raise AssertionError(f"unhandled statement node: {type(stmt).__name__}")

    def _condition(self, expr: Expr) -> bool:
        """Evaluate a condition, requiring a boolean.

        Spec §5: no truthy integers, no truthy strings. `redpill 1` is an
        error, not a taken branch.

        Routes through `_value_of`, not `_evaluate`, so a valueless agent
        used as a condition reports "did not jack out a value" instead of
        leaking NOTHING into `type_name`'s `type(value).__name__` fallback
        — the Python class name `_Nothing` is not a diagnostic.
        """
        value = self._value_of(expr, expr)
        if not is_bool(value):
            raise RuntimeErrorML(
                f"condition must be a boolean, got {type_name(value)}",
                expr.line,
                expr.column,
            )
        return value

    # --- expressions ------------------------------------------------------

    def _evaluate(self, expr: Expr) -> object:
        if isinstance(expr, NumberLiteral):
            return expr.value
        if isinstance(expr, StringLiteral):
            return expr.value
        if isinstance(expr, BoolLiteral):
            return expr.value
        if isinstance(expr, Name):
            found, value = self._env.lookup(expr.ident)
            if not found:
                raise RuntimeErrorML(
                    f"'{expr.ident}' is not declared — use 'construct' first",
                    expr.line,
                    expr.column,
                )
            return value
        if isinstance(expr, Unary):
            operand = self._value_of(expr.operand, expr)
            if expr.op is TokenType.LENGTH:
                if not (is_list(operand) or is_str(operand)):
                    raise RuntimeErrorML(
                        f"'length' takes a list or a string, got "
                        f"{type_name(operand)}",
                        expr.line,
                        expr.column,
                    )
                return len(operand)
            self._require_int(operand, expr.operand, "operand of unary '-'")
            return -operand
        if isinstance(expr, Binary):
            left = self._value_of(expr.left, expr)
            right = self._value_of(expr.right, expr)
            return self._binary(expr, left, right)
        if isinstance(expr, Call):
            return self._call(expr)
        if isinstance(expr, ListLiteral):
            # _value_of, not _evaluate: `[f()]` where f jacks out no value
            # must be an error, not a list holding NOTHING. Routing every
            # position through _value_of is what keeps NOTHING from being
            # stored, compared, printed or added to anything.
            return [self._value_of(element, expr) for element in expr.elements]
        if isinstance(expr, Index):
            target = self._value_of(expr.target, expr)
            index = self._value_of(expr.index, expr)
            return self._element(target, index, expr)
        raise AssertionError(f"unhandled expression node: {type(expr).__name__}")

    def _element(self, target: object, index: object, node) -> object:
        """Bounds-check and read. Shared by Index and IndexAssign so the
        two cannot disagree about what a legal index is."""
        if not is_list(target):
            raise RuntimeErrorML(
                f"cannot index {type_name(target)}", node.line, node.column
            )
        self._check_index(target, index, node)
        return target[index]

    def _check_index(self, target: list, index: object, node) -> None:
        if not is_int(index):
            raise RuntimeErrorML(
                f"an index must be an integer, got {type_name(index)}",
                node.line,
                node.column,
            )
        if index < 0:
            raise RuntimeErrorML(
                "an index cannot be negative — use xs[length xs - 1]",
                node.line,
                node.column,
            )
        if index >= len(target):
            raise RuntimeErrorML(
                f"index {index} is past the end of a list of length "
                f"{len(target)}",
                node.line,
                node.column,
            )

    def _call(self, expr: Call) -> object:
        callee = self._value_of(expr.callee, expr)
        if not is_function(callee):
            raise RuntimeErrorML(
                f"{type_name(callee)} is not an agent", expr.line, expr.column
            )
        args = [self._value_of(arg, expr) for arg in expr.args]
        if len(args) != len(callee.params):
            raise RuntimeErrorML(
                f"agent '{callee.name}' takes {len(callee.params)} "
                f"argument{'' if len(callee.params) == 1 else 's'}, "
                f"got {len(args)}",
                expr.line,
                expr.column,
            )

        # The closure, not the caller. This is the whole of what closures
        # are: the body sees where it was DEFINED.
        frame = Environment(callee.closure)
        for name, value in zip(callee.params, args):
            frame.values[name] = value

        previous = self._env
        self._env = frame
        try:
            for statement in callee.body:
                self._execute(statement)
        except _Jackout as jackout:
            return jackout.value
        finally:
            self._env = previous
        # Fell off the end without jacking out.
        return NOTHING

    def _value_of(self, expr: Expr, where: Expr | Stmt) -> object:
        """Evaluate, refusing NOTHING.

        Every position except a bare call statement needs a real value.
        Routing them all through here is what keeps NOTHING from ever
        being stored, compared, printed or added to anything.
        """
        value = self._evaluate(expr)
        if value is NOTHING:
            name = expr.callee.ident if isinstance(expr, Call) and isinstance(
                expr.callee, Name
            ) else "the agent"
            raise RuntimeErrorML(
                f"agent '{name}' did not jack out a value",
                where.line,
                where.column,
            )
        return value

    def _binary(self, node: Binary, left: object, right: object) -> object:
        if node.op in _EQUALITY_OPS or node.op in _ORDERING_OPS:
            return self._comparison(node, left, right)
        if node.op is TokenType.PLUS and is_str(left) and is_str(right):
            return left + right
        if node.op is TokenType.PLUS and is_str(left) != is_str(right):
            raise RuntimeErrorML(
                f"cannot add {type_name(left)} and {type_name(right)}",
                node.line,
                node.column,
            )
        if node.op is TokenType.PLUS and is_list(left) and is_list(right):
            # A NEW list. Concatenation copies, which is why `+` alone
            # cannot build a cycle — element assignment is the only door.
            return left + right
        if node.op is TokenType.PLUS and is_list(left) != is_list(right):
            raise RuntimeErrorML(
                f"cannot add {type_name(left)} and {type_name(right)}",
                node.line,
                node.column,
            )
        return self._arithmetic(node, left, right)

    def _comparison(self, node: Binary, left: object, right: object) -> object:
        if node.op in _ORDERING_OPS:
            # Not _require_int: that helper also serves unary minus and
            # arithmetic, which still require integers. Ordering is now a
            # rule about the PAIR — both integers or both strings — so it
            # gets its own check and reports the operator's position, the
            # way `cannot compare` and `cannot add` already do.
            orderable = (is_int(left) and is_int(right)) or (
                is_str(left) and is_str(right)
            )
            if not orderable:
                raise RuntimeErrorML(
                    f"cannot order {type_name(left)} with {type_name(right)}",
                    node.line,
                    node.column,
                )
            if node.op is TokenType.LT:
                return left < right
            if node.op is TokenType.GT:
                return left > right
            if node.op is TokenType.LTE:
                return left <= right
            if node.op is TokenType.GTE:
                return left >= right
            raise AssertionError(f"unhandled ordering operator: {node.op.name}")

        # Equality routes through values.equal, which applies type_name at
        # EVERY depth. The old code checked the operands here and then
        # handed off to Python's ==, where 1 == True — so `1 == true` was
        # correctly an error while `[1] == [true]` returned True.
        try:
            same = equal(left, right)
        except Incomparable as mismatch:
            raise RuntimeErrorML(
                f"cannot compare {mismatch.left} with {mismatch.right}",
                node.line,
                node.column,
            ) from None
        if node.op is TokenType.EQ:
            return same
        if node.op is TokenType.NEQ:
            return not same
        raise AssertionError(f"unhandled equality operator: {node.op.name}")

    def _arithmetic(self, node: Binary, left: object, right: object) -> object:
        self._require_int(left, node.left, "left operand")
        self._require_int(right, node.right, "right operand")
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
