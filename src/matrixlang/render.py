"""Canonical source rendering: syntax tree in, source text out.

One emitter serves both faces (design S4-5). The walk is identical; a
face table maps the 54 glyph slots at emission time, so identifiers,
string contents, and comment text bypass the table BY CONSTRUCTION —
the reason this is not textual substitution, which would corrupt the
digit in `x2` and the keyword inside "trace".

This module owns literal formatting outright. values.to_display is a
runtime-value formatter (no quotes, raw newlines) and must never be
used here — a string literal it printed would not re-lex.

Whitespace is canonical, not preserved (design S4-1): 2-space indent
per block depth, one statement per line, single spaces around binary
operators, no blank lines, trailing comments after two spaces.
"""

from matrixlang.glyphs import GLYPHS
from matrixlang.nodes import (
    Call,
    DictLiteral,
    ExprStmt,
    FunctionDef,
    Glitch,
    Index,
    IndexAssign,
    JackIn,
    ListLiteral,
    Return,
    Wake,
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

Face = dict[str, str]

ASCII_FACE: Face = {}
GLYPH_FACE: Face = GLYPHS

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
    TokenType.LENGTH: "length",
    TokenType.DECODE: "decode",
    TokenType.ENCODE: "encode",
    TokenType.UNPLUG: "unplug",
    TokenType.SPLICE: "splice",
    TokenType.FORK: "fork",
    TokenType.KEYMAKER: "keymaker",
    TokenType.ORACLE: "oracle",
    TokenType.FOLD: "fold",
    TokenType.TRIM: "trim",
    TokenType.CLEAVE: "cleave",
}

# Precedence levels, loosest to tightest (language spec §4). Parens are
# reconstructed from these plus associativity — there is no Grouping
# node, so this table IS the §6.4 contract.
_LEVEL: dict[TokenType, int] = {
    # The whole table is renumbered in one move rather than shifted
    # twice: this structure is what decides where parentheses go, and an
    # off-by-one here changes what a program means without failing
    # loudly anywhere else.
    TokenType.FORK: 1,
    TokenType.SPLICE: 2,
    TokenType.EQ: 4,
    TokenType.NEQ: 4,
    TokenType.LT: 5,
    TokenType.GT: 5,
    TokenType.LTE: 5,
    TokenType.GTE: 5,
    # `oracle` parses at the comparison level (parser._COMPARISON_OPS), so
    # it shares that level here -- a different number would parenthesise
    # `d oracle "a" == true` differently than the parser groups it.
    TokenType.ORACLE: 5,
    # `cleave` has a rung of its own (parser._CLEAVE_OPS) between
    # comparison and term. It is why every level below this line moved up
    # by one when string methods landed.
    TokenType.CLEAVE: 6,
    TokenType.PLUS: 7,
    TokenType.MINUS: 7,
    TokenType.STAR: 8,
    TokenType.SLASH: 8,
}
# `unplug` is unary, so it is a constant rather than a _LEVEL entry — but
# unlike `-` and `length` it binds LOOSER than every binary operator
# except fork and splice.
_NOT_LEVEL = 3
_UNARY_LEVEL = 9
_ATOM_LEVEL = 10
# A call is postfix and binds tighter than every operator, including unary
# minus: -f(1) is -(f(1)), never (-f)(1). That makes it an atom for
# parenthesisation purposes, and saying so is better than the two constants
# happening to be equal.
_CALL_LEVEL = _ATOM_LEVEL

_STRING_ESCAPES: dict[str, str] = {"\\": "\\\\", '"': '\\"', "\n": "\\n"}


def render_ascii(program: Program) -> str:
    """The authoring view."""
    return render(program, ASCII_FACE)


def render_glyph(program: Program) -> str:
    """The operator view."""
    return render(program, GLYPH_FACE)


def render(program: Program, face: Face) -> str:
    """Render a program through a face table (any subset of the slots)."""
    lines: list[str] = []
    for statement in program.statements:
        _statement(statement, 0, face, lines)
    for comment in program.trailing_comments:
        lines.append(_comment(comment, face))
    return "".join(line + "\n" for line in lines)


def _map(face: Face, slot: str) -> str:
    return face.get(slot, slot)


def _comment(text: str, face: Face) -> str:
    # §6.2: the '#' marker maps; the comment text is unchanged. Trivia is
    # stored canonically (leading ASCII '#', lexer's guarantee).
    return _map(face, "#") + text[1:]


# --- statements ----------------------------------------------------------


def _statement(stmt: Stmt, depth: int, face: Face, lines: list[str]) -> None:
    pad = "  " * depth
    for comment in stmt.leading_comments:
        lines.append(pad + _comment(comment, face))
    if isinstance(stmt, Declare):
        head = (
            f"{_map(face, 'construct')} {stmt.name} {_map(face, '=')} "
            f"{_expression(stmt.value, 0, face)}"
        )
        lines.append(pad + head + _trail(stmt, face))
    elif isinstance(stmt, Assign):
        head = f"{stmt.name} {_map(face, '=')} {_expression(stmt.value, 0, face)}"
        lines.append(pad + head + _trail(stmt, face))
    elif isinstance(stmt, IndexAssign):
        target = _expression(stmt.target, _CALL_LEVEL, face)
        index = _expression(stmt.index, 0, face)
        head = (
            f"{target}{_map(face, '[')}{index}{_map(face, ']')} "
            f"{_map(face, '=')} {_expression(stmt.value, 0, face)}"
        )
        lines.append(pad + head + _trail(stmt, face))
    elif isinstance(stmt, Trace):
        head = f"{_map(face, 'trace')} {_expression(stmt.value, 0, face)}"
        lines.append(pad + head + _trail(stmt, face))
    elif isinstance(stmt, If):
        lines.append(
            pad + f"{_map(face, 'redpill')} {_expression(stmt.condition, 0, face)}"
        )
        for child in stmt.then_body:
            _statement(child, depth + 1, face, lines)
        for comment in stmt.then_trailing:
            lines.append(pad + "  " + _comment(comment, face))
        # `is not None`, never truthiness: else_body=[] is a bluepill with
        # an empty body and must render its header, or the round trip
        # conflates it with no bluepill at all.
        if stmt.else_body is not None:
            lines.append(pad + _map(face, "bluepill"))
            for child in stmt.else_body:
                _statement(child, depth + 1, face, lines)
            for comment in stmt.else_trailing:
                lines.append(pad + "  " + _comment(comment, face))
        lines.append(pad + _map(face, "flatline") + _trail(stmt, face))
    elif isinstance(stmt, While):
        lines.append(
            pad + f"{_map(face, 'dejavu')} {_expression(stmt.condition, 0, face)}"
        )
        for child in stmt.body:
            _statement(child, depth + 1, face, lines)
        for comment in stmt.body_trailing:
            lines.append(pad + "  " + _comment(comment, face))
        lines.append(pad + _map(face, "flatline") + _trail(stmt, face))
    elif isinstance(stmt, FunctionDef):
        params = f"{_map(face, ',')} ".join(stmt.params)
        lines.append(
            pad
            + f"{_map(face, 'agent')} {stmt.name}"
            + f"{_map(face, '(')}{params}{_map(face, ')')}"
        )
        for child in stmt.body:
            _statement(child, depth + 1, face, lines)
        for comment in stmt.body_trailing:
            lines.append(pad + "  " + _comment(comment, face))
        lines.append(pad + _map(face, "flatline") + _trail(stmt, face))
    elif isinstance(stmt, Return):
        # A bare jackout renders bare, or the round trip turns an early
        # exit into a returned value.
        head = _map(face, "jackout")
        if stmt.value is not None:
            head += f" {_expression(stmt.value, 0, face)}"
        lines.append(pad + head + _trail(stmt, face))
    elif isinstance(stmt, ExprStmt):
        lines.append(pad + _expression(stmt.value, 0, face) + _trail(stmt, face))
    elif isinstance(stmt, Wake):
        lines.append(pad + _map(face, "wake") + _trail(stmt, face))
    elif isinstance(stmt, Glitch):
        lines.append(pad + _map(face, "glitch") + _trail(stmt, face))
    else:
        raise AssertionError(f"unhandled statement node: {type(stmt).__name__}")


def _trail(stmt: Stmt, face: Face) -> str:
    if stmt.trailing_comment is None:
        return ""
    return "  " + _comment(stmt.trailing_comment, face)


# --- expressions ----------------------------------------------------------


def _expression(expr: Expr, minimum: int, face: Face) -> str:
    """Render `expr`, parenthesized if it binds looser than `minimum`."""
    text, level = _emit(expr, face)
    if level < minimum:
        return _map(face, "(") + text + _map(face, ")")
    return text


def _emit(expr: Expr, face: Face) -> tuple[str, int]:
    if isinstance(expr, NumberLiteral):
        return _number(expr.value, face), _ATOM_LEVEL
    if isinstance(expr, StringLiteral):
        return _string(expr.value), _ATOM_LEVEL
    if isinstance(expr, BoolLiteral):
        return _map(face, "true" if expr.value else "false"), _ATOM_LEVEL
    if isinstance(expr, Name):
        return expr.ident, _ATOM_LEVEL
    if isinstance(expr, JackIn):
        # An atom: no operand, so nothing can need parenthesising around it.
        return _map(face, "jackin"), _ATOM_LEVEL
    if isinstance(expr, Unary):
        if expr.op is TokenType.UNPLUG:
            # Looser than every binary operator except fork and splice, so
            # `unplug n == 1` needs no parens while `unplug (a fork b)`
            # does. Rendering the operand at _UNARY_LEVEL instead would
            # parenthesise the common case unnecessarily.
            operand = _expression(expr.operand, _NOT_LEVEL, face)
            return _map(face, "unplug") + " " + operand, _NOT_LEVEL
        # R-PAREN-3: any binary operand is looser than _UNARY_LEVEL and
        # gets parens; atoms and nested unaries do not.
        operand = _expression(expr.operand, _UNARY_LEVEL, face)
        if expr.op in (
            TokenType.LENGTH,
            TokenType.DECODE,
            TokenType.ENCODE,
            TokenType.KEYMAKER,
            TokenType.FOLD,
            TokenType.TRIM,
        ):
            # A word operator needs a separator or `length xs` renders as
            # `lengthxs` and re-lexes as one identifier — a silent change
            # of meaning, which is exactly what §4.3 exists to catch.
            # `decode`, `encode`, `keymaker`, `fold` and `trim` are the
            # same shape and share the rule.
            return _map(face, _OPS[expr.op]) + " " + operand, _UNARY_LEVEL
        return _map(face, "-") + operand, _UNARY_LEVEL
    if isinstance(expr, Call):
        # A call binds tighter than every operator, so the callee needs
        # parens unless it is already an atom or another call.
        callee = _expression(expr.callee, _CALL_LEVEL, face)
        # Each argument is its OWN precedence context, reset to 0. Reusing
        # the enclosing level would render f(a + b) as f(a) + b -- a
        # different tree with a different meaning.
        args = f"{_map(face, ',')} ".join(
            _expression(arg, 0, face) for arg in expr.args
        )
        return (
            f"{callee}{_map(face, '(')}{args}{_map(face, ')')}",
            _CALL_LEVEL,
        )
    if isinstance(expr, Index):
        # _CALL_LEVEL for the target for the same reason a call uses it:
        # the suffix binds tighter than every operator, so a looser target
        # needs parens. The index itself renders from 0 — the brackets
        # delimit it, exactly like call arguments.
        target = _expression(expr.target, _CALL_LEVEL, face)
        inner = _expression(expr.index, 0, face)
        return (
            f"{target}{_map(face, '[')}{inner}{_map(face, ']')}",
            _CALL_LEVEL,
        )
    if isinstance(expr, ListLiteral):
        # Elements render from level 0: the brackets delimit them, so no
        # element ever needs parens for the list's sake. Same reasoning as
        # Call.args. The literal itself is an atom — [1] + [2] must never
        # come back as [1] + [2] with parens, and never as [1 + [2]].
        inner = f"{_map(face, ',')} ".join(
            _expression(e, 0, face) for e in expr.elements
        )
        return f"{_map(face, '[')}{inner}{_map(face, ']')}", _ATOM_LEVEL
    if isinstance(expr, DictLiteral):
        # Keys and values render from level 0, same reasoning as
        # ListLiteral.elements and Call.args: the braces delimit each pair,
        # so neither ever needs parens for the dict's sake. entries is a
        # list of pairs rather than a dict, so a key written twice renders
        # as two entries -- collapsing them would lose a token.
        inner = f"{_map(face, ',')} ".join(
            f"{_expression(k, 0, face)}{_map(face, ':')} {_expression(v, 0, face)}"
            for k, v in expr.entries
        )
        return f"{_map(face, '{')}{inner}{_map(face, '}')}", _ATOM_LEVEL
    if isinstance(expr, Binary):
        level = _LEVEL[expr.op]
        # Left-associative grammar: the left child may sit at the same
        # level (R-PAREN-1); the right child must bind STRICTLY tighter
        # or the chain re-parses left-first (R-PAREN-2).
        left = _expression(expr.left, level, face)
        right = _expression(expr.right, level + 1, face)
        return f"{left} {_map(face, _OPS[expr.op])} {right}", level
    raise AssertionError(f"unhandled expression node: {type(expr).__name__}")


def _number(value: int, face: Face) -> str:
    # §6.2: digits map per-digit, positionally. NumberLiteral values are
    # non-negative — a minus sign is a Unary node, never part of a number.
    return "".join(_map(face, digit) for digit in str(value))


def _string(value: str) -> str:
    body = "".join(_STRING_ESCAPES.get(char, char) for char in value)
    return f'"{body}"'
