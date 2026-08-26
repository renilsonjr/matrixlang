"""The MatrixLang tree-walking interpreter: syntax tree in, effects out.

The environment is a dictionary. That is not a simplification for teaching
purposes — with no functions and no closures yet (spec §5), a flat dict is
the whole of what scope means in this language.

This module consumes a Program node and nothing else. It never imports the
lexer, the parser or the CLI, so Stage 4 can hand it a tree that came from
either source face.
"""

import dataclasses
import string
import sys
from decimal import Decimal
from typing import TextIO

from matrixlang.errors import RuntimeErrorML
from matrixlang.events import EventSink, Output, Statement, TextSink
from matrixlang.input import EmptySource, InputSource
from matrixlang.nodes import (
    Assign,
    Binary,
    BoolLiteral,
    Call,
    Declare,
    DictLiteral,
    Expr,
    ExprStmt,
    FunctionDef,
    Glitch,
    If,
    Index,
    IndexAssign,
    JackIn,
    ListLiteral,
    Name,
    NumberLiteral,
    Program,
    Return,
    Stmt,
    StringLiteral,
    Trace,
    Unary,
    Wake,
    While,
)
from matrixlang.tokens import TokenType
from matrixlang.values import (
    DIVISION,
    EXACT,
    NOTHING,
    BadKey,
    CyclicValue,
    Function,
    Incomparable,
    NumberOverflow,
    TooManyDigits,
    check_key,
    equal,
    is_bool,
    is_dict,
    is_function,
    is_list,
    is_number,
    is_str,
    is_whole,
    remainder_floor,
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
_LOGICAL_OPS = (TokenType.SPLICE, TokenType.FORK)

# The operator's own word, for its diagnostic. Not render._OPS: importing
# render into the interpreter would put a presentation module underneath
# execution, which tests/test_architecture.py forbids.
_OP_WORDS = {TokenType.SPLICE: "splice", TokenType.FORK: "fork"}


def _display_key(key: object) -> str:
    """A key as it should read inside a diagnostic: strings quoted.

    Routed through to_display's own nested rules, via a one-element list,
    rather than reimplementing "quote if it's a string": that is what
    keeps the quoting and escaping in this error message from ever
    drifting away from the quoting `trace` would produce for the same
    value.
    """
    return to_display([key])[1:-1]


# Explicit ASCII set, matching lexer._DIGITS. Bare int() is far more
# tolerant than the lexer's own number grammar -- it accepts "1_000",
# Arabic-Indic digits ("٣٤٥"), and other Unicode decimal digits, none of
# which the lexer would ever produce as a single number token. `decode`
# reads external input rather than lexed source, so nothing upstream has
# filtered it; do not "simplify" this back to bare int().
_DECODE_DIGITS = frozenset(string.digits)

# The surrounding space `decode` forgives, and no more. str.strip() with
# no argument strips every Unicode space -- NBSP, the ideographic space,
# U+2028 -- so "\xa05" would decode to 5 while the lexer would never read
# that as a number. ASCII only, for the same reason _DECODE_DIGITS is.
_DECODE_SPACE = string.whitespace


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


class _LoopSignal(Exception):
    """A `wake` or a `glitch`, unwinding to the innermost loop.

    Deliberately not a MatrixLangError, for the same reason _Jackout is
    not: these are control flow, not diagnostics, and a stray
    `except MatrixLangError` must never swallow one.

    Carries the position so the "outside a loop" error -- raised where
    the signal escapes rather than where it was written -- can still
    point at the keyword the reader typed.
    """

    __slots__ = ("word", "line", "column")

    def __init__(self, word: str, line: int, column: int) -> None:
        super().__init__()
        self.word = word
        self.line = line
        self.column = column


class _Wake(_LoopSignal):
    pass


class _Glitch(_LoopSignal):
    pass


class Interpreter:
    def __init__(
        self,
        out: TextIO | None = None,
        sink: EventSink | None = None,
        max_steps: int | None = DEFAULT_MAX_STEPS,
        source: InputSource | None = None,
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
        # EmptySource, never StdinSource. A default that read a terminal
        # would hang any caller that forgot to pass one -- including
        # operator/validate.py's dry run, which executes untrusted
        # candidate programs inside a server request.
        self._source = EmptySource() if source is None else source

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
            except _LoopSignal as signal:
                raise RuntimeErrorML(
                    f"'{signal.word}' outside a loop",
                    signal.line,
                    signal.column,
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
                # RecursionError path reports and which is false: a value
                # that contains itself may be one element long.
                #
                # "a value", not "a list": a dictionary can hold itself
                # too (`d["me"] = d`), and naming a list in that case is
                # simply false — the message reaches the browser verbatim
                # in the SSE error payload.
                raise RuntimeErrorML(
                    "cannot display a value that contains a cycle",
                    stmt.line,
                    stmt.column,
                ) from None
            except TooManyDigits as size:
                # Same shape as the cycle above: values.py knows the value
                # cannot be rendered, this module knows where it was
                # written. Reachable from `trace n` alone -- squaring in a
                # loop passes 4300 digits long before the step limit.
                raise RuntimeErrorML(
                    f"cannot display a number longer than "
                    f"{size.limit} digits",
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
            if is_dict(target):
                # Insert, not error, on a missing key: a write is how a
                # dictionary gains entries. A read, by contrast, errors on
                # a missing key in the Index branch of `_evaluate` — the
                # same asymmetry the language already has between reading
                # past a list's end (error) and appending to it (no such
                # operation exists, so the question does not arise there).
                try:
                    check_key(index)
                except BadKey as bad:
                    raise RuntimeErrorML(
                        f"a dictionary key must be a string or a number, "
                        f"got {bad.name}",
                        stmt.index.line,
                        stmt.index.column,
                    ) from None
                target[index] = value
                return
            # Three ways, not two. A string IS indexable — _element reads
            # one happily — so `cannot index string` would now be a lie.
            # And widening this to `is_list or is_str` the way _element
            # was widened would let the assignment reach Python's own item
            # assignment and raise TypeError, putting a Python exception
            # name in front of someone running a .rain file.
            if is_str(target):
                raise RuntimeErrorML(
                    "a string cannot be changed — build a new one with +",
                    stmt.index.line,
                    stmt.index.column,
                )
            if not is_list(target):
                raise RuntimeErrorML(
                    f"cannot index {type_name(target)}",
                    stmt.index.line,
                    stmt.index.column,
                )
            position = self._check_index(target, index, stmt.index)
            target[position] = value
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
                try:
                    for child in stmt.body:
                        self._execute(child)
                except _Glitch:
                    continue
                except _Wake:
                    break
        elif isinstance(stmt, Wake):
            raise _Wake("wake", stmt.line, stmt.column)
        elif isinstance(stmt, Glitch):
            raise _Glitch("glitch", stmt.line, stmt.column)
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
        if isinstance(expr, JackIn):
            line = self._source.next_line()
            if line is None:
                raise RuntimeErrorML(
                    "no input left to read", expr.line, expr.column
                )
            return line
        if isinstance(expr, Unary):
            operand = self._value_of(expr.operand, expr)
            if expr.op is TokenType.UNPLUG:
                if not is_bool(operand):
                    # Reports the OPERATOR's position (expr.column), unlike
                    # _require_bool below which reports the OPERAND's
                    # (node.column) for splice/fork. Both are defensible —
                    # this matches `length`, unplug's fellow word-unary,
                    # while `-` and _require_bool point at the operand —
                    # but the two operators shipped this stage disagree,
                    # so it is worth saying so rather than leaving it to
                    # look like an oversight.
                    raise RuntimeErrorML(
                        f"'unplug' takes a boolean, got {type_name(operand)}",
                        expr.line,
                        expr.column,
                    )
                return not operand
            if expr.op is TokenType.LENGTH:
                if not (is_list(operand) or is_str(operand) or is_dict(operand)):
                    raise RuntimeErrorML(
                        f"'length' takes a list, a string or a dictionary, got "
                        f"{type_name(operand)}",
                        expr.line,
                        expr.column,
                    )
                # A number, not a plain int: everything in the language is
                # one type now, and `length xs + 1` must add like any other
                # number rather than colliding with `cannot order number
                # with int`.
                return Decimal(len(operand))
            if expr.op is TokenType.KEYMAKER:
                if not is_dict(operand):
                    raise RuntimeErrorML(
                        f"'keymaker' takes a dictionary, got "
                        f"{type_name(operand)}",
                        expr.line,
                        expr.column,
                    )
                # A copy, not the dict's own view: mutating what the
                # caller does with the returned list must never reach
                # back into the dictionary.
                return list(operand.keys())
            if expr.op is TokenType.FOLD:
                if not is_str(operand):
                    raise RuntimeErrorML(
                        f"'fold' takes a string, got {type_name(operand)}",
                        expr.line,
                        expr.column,
                    )
                # str.lower(), NOT str.casefold(), despite the name.
                # "STRAßE".lower() is "straße"; .casefold() is "strasse".
                # The Python translator maps `.lower()` onto this
                # operator, so switching to casefold would make a
                # translated program and its original disagree on that
                # input, silently -- which is the one thing the
                # translator's governing rule exists to prevent.
                return operand.lower()
            if expr.op is TokenType.TRIM:
                if not is_str(operand):
                    raise RuntimeErrorML(
                        f"'trim' takes a string, got {type_name(operand)}",
                        expr.line,
                        expr.column,
                    )
                # Bare str.strip() -- all Unicode whitespace.
                # Deliberately NOT _DECODE_SPACE, which is ASCII-only
                # because `decode` is validating a number grammar against
                # text that came from outside. `trim` is trimming text for
                # a reader, and the translator maps Python's `.strip()`
                # onto it, so it has to agree with `.strip()` on U+00A0.
                return operand.strip()
            if expr.op is TokenType.DECODE:
                if not is_str(operand):
                    raise RuntimeErrorML(
                        f"'decode' takes text, got {type_name(operand)}",
                        expr.line,
                        expr.column,
                    )
                # Explicit check, not bare int()/Decimal(): both accept far
                # more than the lexer's own number grammar ever produces --
                # "1_000", Arabic-Indic digits, "1E+3", other Unicode
                # decimal digits or exponent forms -- because decode reads
                # external input that nothing upstream has filtered. See
                # _DECODE_DIGITS. Widened to allow at most one point, so
                # `decode` accepts exactly what the lexer's own literal
                # grammar accepts -- one point, digits required on both
                # sides of it -- rather than inventing a second rule.
                stripped = operand.strip(_DECODE_SPACE)
                digits = stripped[1:] if stripped.startswith("-") else stripped
                if digits.count(".") > 1:
                    ok = False
                elif "." in digits:
                    whole, _, fraction = digits.partition(".")
                    ok = bool(whole) and bool(fraction) and all(
                        c in _DECODE_DIGITS for c in whole + fraction
                    )
                else:
                    ok = bool(digits) and all(c in _DECODE_DIGITS for c in digits)
                if not ok:
                    raise RuntimeErrorML(
                        f"'decode' needs a number, got \"{operand}\"",
                        expr.line,
                        expr.column,
                    )
                # Decimal does not raise for long inputs the way int() did
                # -- the old try/except ValueError around int(stripped) is
                # gone. The digit cap now lives in display (values.py's
                # TooManyDigits), reached through `trace`/`encode` rather
                # than here.
                return Decimal(stripped)
            if expr.op is TokenType.ENCODE:
                # Any value, deliberately. This was numbers-only, guarded by
                # is_int, until a reader's f-string interpolating a string
                # translated cleanly and died on Run naming an operator they
                # never typed. `trace` prints every type through to_display;
                # there was no reason `encode` could not hand back the same
                # text. The old guard's own comment feared `encode true`
                # giving "1" -- to_display gives "true", because _display
                # checks is_bool first, so it was guarding against something
                # values.py already prevented.
                try:
                    return to_display(operand)
                except CyclicValue:
                    # Newly reachable: the type guard above used to make a
                    # self-containing value impossible here. Same wording as
                    # `trace`'s -- "a value", not "a list", because a
                    # dictionary can hold itself too and the message reaches
                    # the browser verbatim in the SSE error payload.
                    raise RuntimeErrorML(
                        "cannot display a value that contains a cycle",
                        expr.line,
                        expr.column,
                    ) from None
                except TooManyDigits as size:
                    # The mirror of decode's ValueError guard above, and
                    # for the same CPython cap -- but the guard itself
                    # lives in values.py, so `trace` gets it too and the
                    # two operators cannot end up with two answers about
                    # what a number too long to write looks like.
                    raise RuntimeErrorML(
                        f"'encode' got a number too long to write — "
                        f"more than {size.limit} digits",
                        expr.line,
                        expr.column,
                    ) from None
            self._require_number(operand, expr.operand, "operand of unary '-'")
            # copy_negate(), NOT Python's `-operand`: Decimal's own
            # __neg__ rounds through the thread-local DEFAULT context
            # (prec=28), not EXACT -- so `-x` and `0 - x` could silently
            # disagree past 28 significant digits, with no error and no
            # scientific notation, just a wrong number. copy_negate is a
            # context-free, exact sign flip; it cannot round and cannot
            # raise.
            return operand.copy_negate()
        if isinstance(expr, Binary) and expr.op in _LOGICAL_OPS:
            # Intercepted HERE, not in _binary, and that is the whole
            # point: the Binary branch below evaluates both operands
            # before dispatching, so routing these through _binary would
            # give operators that work and do not short-circuit. Every
            # truth-table test would still pass, and the bounded search
            # `n < length xs splice xs[n] != target` would die at the
            # boundary with an out-of-bounds error.
            return self._logical(expr)
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
        if isinstance(expr, DictLiteral):
            result: dict = {}
            for key_expr, value_expr in expr.entries:
                key = self._value_of(key_expr, expr)
                try:
                    check_key(key)
                except BadKey as bad:
                    raise RuntimeErrorML(
                        f"a dictionary key must be a string or a number, "
                        f"got {bad.name}",
                        key_expr.line,
                        key_expr.column,
                    ) from None
                # A later duplicate overwrites an earlier one, which is
                # what dict.__setitem__ does and what a reader expects;
                # the FIRST write's insertion position is kept, which is
                # also what CPython does. The AST kept both entries (see
                # DictLiteral's own docstring) so this overwrite is where
                # a written duplicate actually collapses to one.
                result[key] = self._value_of(value_expr, expr)
            return result
        if isinstance(expr, Index):
            target = self._value_of(expr.target, expr)
            if is_dict(target):
                key = self._value_of(expr.index, expr)
                try:
                    check_key(key)
                except BadKey as bad:
                    raise RuntimeErrorML(
                        f"a dictionary key must be a string or a number, "
                        f"got {bad.name}",
                        expr.index.line,
                        expr.index.column,
                    ) from None
                if key not in target:
                    try:
                        shown = _display_key(key)
                    except TooManyDigits as size:
                        # The third door onto values.py's digit ceiling,
                        # after `trace` and `encode`, and the same guard
                        # they carry. Naming the key in the diagnostic
                        # RENDERS it, so a key past CPython's cap would
                        # turn a missing-key error into a raw Python
                        # exception -- which Interpreter.run() must never
                        # emit and site/glue.py's run() promises never to.
                        raise RuntimeErrorML(
                            f"cannot display a number longer than "
                            f"{size.limit} digits",
                            expr.index.line,
                            expr.index.column,
                        ) from None
                    raise RuntimeErrorML(
                        f"no key {shown} in this dictionary",
                        expr.index.line,
                        expr.index.column,
                    )
                return target[key]
            index = self._value_of(expr.index, expr)
            return self._element(target, index, expr)
        raise AssertionError(f"unhandled expression node: {type(expr).__name__}")

    def _element(self, target: object, index: object, node) -> object:
        """Bounds-check and read. The only caller is the Index branch of
        `_evaluate` — this method itself is not shared. What IS shared is
        `_check_index`, called from here and from the IndexAssign branch
        of `_execute`, so the two paths cannot disagree about what a
        legal index is.

        Strings read like lists: `s[i]` is a one-character string, because
        the language has no character type. `target[index]` on a Python
        str already returns exactly that, so the read generalises for
        free. WRITING to a string is refused separately, before it ever
        reaches this method — see the IndexAssign branch in `_execute`.
        """
        if not (is_list(target) or is_str(target)):
            raise RuntimeErrorML(
                f"cannot index {type_name(target)}", node.line, node.column
            )
        position = self._check_index(target, index, node)
        return target[position]

    def _check_index(self, target: list | str, index: object, node) -> int:
        """Validate `index` and return it as a Python `int` subscript.

        Two branches, not one: a non-number and a fractional number are
        different mistakes and deserve different messages. `int(index)`
        for the final conversion is safe — it does not round, it
        truncates a value already checked whole by `is_whole` above.

        Neither diagnostic below interpolates `index` or `position`
        directly. `decode` no longer caps digit count (Task 5 removed its
        `try/except ValueError` around `int()`, since `Decimal` does not
        raise for a long digit string), so an index reaching this method
        can carry thousands of digits with nothing upstream to have
        stopped it — from a literal (the lexer's own cap moved to display,
        #135) or from `xs[decode "<huge digit string>"]` alike. `str(a
        4301-digit Python int)` raises a bare ValueError under CPython's
        own conversion cap, same as `str()` on the equivalent `Decimal`
        does — so both branches route the value through `_display_index`,
        which is the one place that cap is caught and turned into a
        RuntimeErrorML, instead of ever formatting `position` or `index`
        straight into an f-string.
        """
        if not is_number(index):
            raise RuntimeErrorML(
                f"an index must be a whole number, got {type_name(index)}",
                node.line,
                node.column,
            )
        if not is_whole(index):
            # Reachable now that `/` is true division: `xs[length xs / 2]`
            # lands here rather than silently truncating. Showing the
            # value, not the type, because the type is right and the
            # value is not.
            raise RuntimeErrorML(
                f"an index must be a whole number, got "
                f"{self._display_index(index, node)}",
                node.line,
                node.column,
            )
        position = int(index)
        if position < 0:
            # The placeholder name mirrors the bounds message's noun below:
            # a list example says `xs`, a string example says `s`, so
            # neither reader is told to fix a string with list vocabulary.
            example = "s" if is_str(target) else "xs"
            raise RuntimeErrorML(
                f"an index cannot be negative — use {example}[length {example} - 1]",
                node.line,
                node.column,
            )
        if position >= len(target):
            # type_name rather than a hardcoded "list": one message serves
            # both, so the two can never drift into disagreeing about the
            # same rule. `_display_index`, not bare `position`: see this
            # method's docstring -- `position` can be a Python int with
            # thousands of digits, and formatting one of those directly
            # into an f-string raises a bare ValueError.
            raise RuntimeErrorML(
                f"index {self._display_index(index, node)} is past the end "
                f"of a {type_name(target)} of length {len(target)}",
                node.line,
                node.column,
            )
        return position

    def _display_index(self, index: object, node) -> str:
        """`to_display(index)` for an index diagnostic, guarded the same
        way `trace` guards it at the top of `_execute` (and `encode`
        guards it in `_evaluate`): `TooManyDigits` is not a
        MatrixLangError on purpose (see its docstring in values.py) so
        that every caller is forced to convert it, and this is the one
        call site `_check_index` has for it. Without this, a whole
        number past the digit cap -- reachable from a literal or from
        `decode`, since neither caps digit count anymore -- would raise
        a bare TooManyDigits (not even a Python built-in) straight out
        of the interpreter.
        """
        try:
            return to_display(index)
        except TooManyDigits as size:
            raise RuntimeErrorML(
                f"cannot display a number longer than {size.limit} digits",
                node.line,
                node.column,
            ) from None

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
        except _LoopSignal as signal:
            # THE agent boundary. Without this, `wake` inside an agent
            # called from inside a loop escapes the call and breaks the
            # CALLER's loop -- a program that runs and quietly does
            # something the reader never wrote. The agent's own body is
            # not inside a loop, so this is an error, exactly as Python's
            # `break` in a function body is a SyntaxError.
            raise RuntimeErrorML(
                f"'{signal.word}' outside a loop",
                signal.line,
                signal.column,
            ) from None
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

    def _logical(self, expr: Binary) -> bool:
        """`splice` and `fork`, short-circuiting.

        The right operand is evaluated only when the left does not already
        decide the answer. That is what makes a bounded search safe:
        `n < length xs splice xs[n] != target` must not read xs[n] at the
        boundary.

        The cost, which is documented rather than hidden: an operand that
        is never evaluated is never type-checked, so `false splice 1` is
        false while `true splice 1` is an error.
        """
        left = self._value_of(expr.left, expr)
        self._require_bool(left, expr.left, expr.op)
        if expr.op is TokenType.SPLICE and not left:
            return False
        if expr.op is TokenType.FORK and left:
            return True
        right = self._value_of(expr.right, expr)
        self._require_bool(right, expr.right, expr.op)
        return right

    def _require_bool(self, value: object, node: Expr, op: TokenType) -> None:
        if not is_bool(value):
            raise RuntimeErrorML(
                f"'{_OP_WORDS[op]}' takes booleans, got {type_name(value)}",
                node.line,
                node.column,
            )

    def _binary(self, node: Binary, left: object, right: object) -> object:
        if node.op in _EQUALITY_OPS or node.op in _ORDERING_OPS:
            return self._comparison(node, left, right)
        if node.op is TokenType.ORACLE:
            # One question -- does this hold that? -- asked of the three
            # things that can hold anything. The dictionary arm is
            # unchanged; the other two are what issue #134 added.
            if is_dict(left):
                try:
                    check_key(right)
                except BadKey as bad:
                    raise RuntimeErrorML(
                        f"a dictionary key must be a string or a number, "
                        f"got {bad.name}",
                        node.line,
                        node.column,
                    ) from None
                return right in left
            if is_list(left):
                for element in left:
                    try:
                        if equal(element, right):
                            return True
                    except Incomparable:
                        # Skipped, not raised, and this is THE decision of
                        # the design. `["a"] oracle 1` asks whether the
                        # list contains the integer 1 -- which has a
                        # truthful answer, no -- while `1 == "a"` asks
                        # something with no answer at all, and rightly
                        # raises. Membership is not equality.
                        #
                        # This is the one place in the language where a
                        # type mismatch declines to raise where `==`
                        # would. The alternative, raising on the first
                        # incomparable element, would make the answer
                        # depend on element ORDER: `["a", 1] oracle 1`
                        # would error while `[1, "a"] oracle 1` would be
                        # true. Same list, reordered, deciding whether
                        # the program runs.
                        continue
                return False
            if is_str(left):
                if not is_str(right):
                    raise RuntimeErrorML(
                        f"'oracle' on a string looks for a string, got "
                        f"{type_name(right)}",
                        node.line,
                        node.column,
                    )
                # A SUBSTRING test, matching Python -- so
                # `"matrix" oracle "rix"` is true even though "rix" is not
                # one of its characters. Everywhere else in the language a
                # string is a sequence of characters (`length` counts
                # them, `[i]` reads one), and this operator is the
                # exception. It is bought deliberately: substring is what
                # `if "@" in email:` means, and the translator cannot tell
                # a string from a list to warn anyone if the two differed.
                return right in left
            raise RuntimeErrorML(
                f"'oracle' takes a list, a string or a dictionary, got "
                f"{type_name(left)}",
                node.line,
                node.column,
            )
        if node.op is TokenType.CLEAVE:
            if not is_str(left):
                raise RuntimeErrorML(
                    f"'cleave' takes a string, got {type_name(left)}",
                    node.line,
                    node.column,
                )
            if not is_str(right):
                raise RuntimeErrorML(
                    f"'cleave' needs a string separator, got "
                    f"{type_name(right)}",
                    node.line,
                    node.column,
                )
            if not right:
                # CPython raises ValueError("empty separator") here.
                # Nothing may escape this interpreter but MatrixLangError
                # -- site/glue.py's run() promises never to raise, and
                # that promise has been broken five times already.
                raise RuntimeErrorML(
                    "'cleave' needs a separator with something in it",
                    node.line,
                    node.column,
                )
            return left.split(right)
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
            # Not _require_number: that helper also serves unary minus and
            # arithmetic, which still require numbers. Ordering is now a
            # rule about the PAIR — both numbers or both strings — so it
            # gets its own check and reports the operator's position, the
            # way `cannot compare` and `cannot add` already do.
            orderable = (is_number(left) and is_number(right)) or (
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
        self._require_number(left, node.left, "left operand")
        self._require_number(right, node.right, "right operand")
        try:
            if node.op is TokenType.PLUS:
                return EXACT.add(left, right)
            if node.op is TokenType.MINUS:
                return EXACT.subtract(left, right)
            if node.op is TokenType.STAR:
                return EXACT.multiply(left, right)
        except NumberOverflow:
            # Same shape as the TooManyDigits conversions above: values.py
            # knows the result cannot be represented, this module knows
            # where it was written. Newly reachable now that `+ - *` run
            # through EXACT instead of Python's arbitrary-precision int --
            # squaring a value about twenty times gets here well inside
            # the step limit, and nothing but MatrixLangError may escape
            # this interpreter (site/glue.py's run() promises that, and
            # the promise has been broken six times already).
            raise RuntimeErrorML(
                "arithmetic result is too large to represent",
                node.line,
                node.column,
            ) from None
        if node.op is TokenType.SLASH:
            if right == 0:
                raise RuntimeErrorML("cannot divide by zero", node.line, node.column)
            # True division, in the one context that rounds. Division is
            # the only operation that can go on forever -- 1 / 3 has no
            # finite decimal form -- so it is the only one that needs a
            # precision, and DIVISION's 28 is where
            # 0.3333333333333333333333333333 comes from.
            #
            # This replaced truncation, which matched neither of Python's
            # two divisions: `/` is true division and `//` floors, while
            # this truncated toward zero. That mismatch is why the
            # translator refused BOTH for the language's whole history.
            #
            # DIVISION is a _GuardedContext, so an overflowing quotient
            # raises NumberOverflow rather than a bare decimal.Overflow
            # -- but NumberOverflow is not itself a MatrixLangError, so
            # it still needs converting here, the same as + - * above.
            # Reachable: DIVISION.divide(Decimal("1E+999990"),
            # Decimal("1E-999990")) overflows even though neither
            # operand does, because the quotient's exponent is
            # (roughly) the sum of the two.
            try:
                return DIVISION.divide(left, right)
            except NumberOverflow:
                raise RuntimeErrorML(
                    "arithmetic result is too large to represent",
                    node.line,
                    node.column,
                ) from None
        if node.op is TokenType.PERCENT:
            if right == 0:
                raise RuntimeErrorML(
                    "cannot take the remainder by zero", node.line, node.column
                )
            # Python's rule, not Decimal's -- `left - floor(left / right)
            # * right`. values.remainder_floor owns the whole of it,
            # including why it must not compute the quotient: rounding
            # `left / right` to EXACT's 1000 digits before flooring it
            # rounds UP past 1000 digits, which returned a NEGATIVE
            # remainder for a positive divisor. Read its docstring before
            # touching this.
            #
            # Every step of it goes through EXACT explicitly, never
            # through a bare Python operator (`//`, `%`, unary `-`) on a
            # Decimal -- those round through the thread-local default
            # context at precision 28, not through this language's own
            # contexts. That exact mistake has cost this branch a
            # Critical already (unary minus) and an escaping
            # decimal.InvalidOperation since.
            #
            # remainder_floor calls _GuardedContext methods, so it can
            # raise NumberOverflow rather than a bare decimal.Overflow --
            # and NumberOverflow is not itself a MatrixLangError, so it
            # still needs converting here, the same as + - * and / above.
            # No input is currently known to reach it: dropping the
            # quotient dropped the one shape that did (a huge dividend
            # over a tiny divisor overflowed EXACT.divide before the
            # subtract). The guard stays anyway -- it costs nothing, it
            # is the same guard the other three operators carry, and
            # "nothing but MatrixLangError may escape" is not a promise
            # to re-derive every time remainder_floor changes.
            try:
                return remainder_floor(left, right)
            except NumberOverflow:
                raise RuntimeErrorML(
                    "arithmetic result is too large to represent",
                    node.line,
                    node.column,
                ) from None
        raise AssertionError(f"unhandled binary operator: {node.op.name}")

    def _require_number(self, value: object, node: Expr, role: str) -> None:
        if not is_number(value):
            raise RuntimeErrorML(
                f"{role} must be a number, got {type_name(value)}",
                node.line,
                node.column,
            )


def run(program: Program, out: TextIO | None = None) -> None:
    """Execute a program. Convenience wrapper over Interpreter."""
    Interpreter(out=out).run(program)


def reads_input(program: Program) -> bool:
    """Whether running this program can ever ask its source for a line.

    A fact about executing the tree rather than about drawing it, which is
    why it lives beside the branch that does the asking. Callers use it to
    decide what to hand the interpreter and where to run it — see cli.py's
    backend choice.

    Walked generically over the dataclass fields instead of by an
    isinstance chain per node type. A chain would need editing every time
    a node gains a child, and forgetting that edit is exactly the bug
    treeview.py has now shipped twice.
    """
    pending: list[object] = [program]
    while pending:
        item = pending.pop()
        if isinstance(item, JackIn):
            return True
        if isinstance(item, list):
            pending.extend(item)
        elif dataclasses.is_dataclass(item) and not isinstance(item, type):
            pending.extend(
                getattr(item, field.name) for field in dataclasses.fields(item)
            )
    return False
