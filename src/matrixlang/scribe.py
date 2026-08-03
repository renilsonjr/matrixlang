"""Scribe — a keyless, deterministic companion to Operator.

Operator asks an LLM and lets the parser decide. Scribe skips the LLM
entirely: a finite catalogue of intent patterns builds nodes.* ASTs
directly from a plain-language request. Pure — no I/O, no network, no
SDK, no key. The server owns the validate gate (operator/validate.check);
this module only produces.
"""

import re
from dataclasses import dataclass

from matrixlang.nodes import (
    Assign, Binary, BoolLiteral, Call, Declare, Expr, ExprStmt, FunctionDef,
    If, Index, IndexAssign, ListLiteral, Name, NumberLiteral, Program, Return,
    Stmt, StringLiteral, Trace, Unary, While,
)
from matrixlang.render import render_ascii
from matrixlang.tokens import TokenType


@dataclass(frozen=True)
class ScribeProgram:
    program: Program
    source: str


@dataclass(frozen=True)
class ScribeMiss:
    reason: str
    closest: str | None = None


ScribeResult = ScribeProgram | ScribeMiss


def scribe(request: str) -> ScribeResult:
    """Turn a plain-language request into a MatrixLang program.

    Pure and deterministic. Never raises for an unmatched request — that
    is what ScribeMiss is for.
    """
    text = normalize(request)
    if not text:
        return ScribeMiss("the request was empty", closest=None)

    # Longest match wins (design §3), NOT first-registered. "if 5 is greater
    # than 3 trace bigger" matches both the conditional intent (35 chars) and
    # the bare `trace <value>` intent (12 chars, via .search() finding the
    # tail). First-match would return the trace and silently discard the `if`.
    # Scoring by width makes the catalogue order-independent, so a task that
    # adds an intent cannot break one added earlier.
    best = None
    best_width = 0
    for intent in INTENTS:
        match = intent.regex.search(text)
        if match and (match.end() - match.start()) > best_width:
            best, best_width = (intent, match), match.end() - match.start()

    if best is None:
        return ScribeMiss("no pattern matched this request", closest=_closest(text))

    intent, match = best
    program = intent.build(match)
    return ScribeProgram(program=program, source=render_ascii(program))


# --- Normalization ------------------------------------------------------


def normalize(request: str) -> str:
    """Collapse whitespace and map synonyms, leaving quoted text alone.

    "print hello world" and "show hello world" both become the canonical
    phrasing the patterns look for. Written numbers stay as words; the
    number patterns handle both.

    **Quoted spans are never rewritten.** They are the user's literal
    output, not phrasing to canonicalize — lowercasing or substituting
    inside them turns `trace "print this"` into `trace "trace this"` and
    `trace "Wake Up Neo"` into lowercase. Splitting on the quote character
    and transforming only the odd-indexed (outside) segments keeps a string
    literal byte-exact while still canonicalizing the words around it.
    """
    parts = request.split('"')
    for i, part in enumerate(parts):
        if i % 2:  # inside quotes — leave exactly as written
            continue
        part = part.lower()
        for synonym, canonical in _SYNONYMS.items():
            part = _WORD[synonym].sub(canonical, part)
        part = re.sub(r"\s+", " ", part)
        parts[i] = part
    return '"'.join(parts).strip()


_SYNONYMS = {
    "print": "trace",
    "show": "trace",
    "display": "trace",
    "output": "trace",
    "say": "trace",
}

# Whole words only. A bare str.replace turns "fingerprint" into
# "fingertrace" and "says" into "traces".
_WORD = {word: re.compile(rf"\b{word}\b") for word in _SYNONYMS}


def _closest(text: str) -> str | None:
    """A suggestion for an unmatched request, from the known intents.

    The first hint whose word appears in the request wins; otherwise the
    first registered hint stands in, so a miss always has a concrete
    pattern to offer ("make soup" → "add <a> and <b>", say).
    """
    for intent in INTENTS:
        # Reuse the catalogue's own descriptions as hints.
        if intent.hint and any(word in text for word in intent.hint.split()):
            return intent.hint
    return INTENTS[0].hint if INTENTS else None


# --- Intent registry ----------------------------------------------------

INTENTS: list["_Intent"] = []


class _Intent:
    """One pattern: a regex, a builder, and a human hint.

    Registration order carries no meaning — `scribe()` picks the widest
    match, not the first. Intents are free to overlap.
    """

    def __init__(self, regex: str, build, hint: str):
        self.regex = re.compile(regex)
        self.build = build
        self.hint = hint
        INTENTS.append(self)


# --- Arithmetic intents ---------------------------------------------------


def _num_or_name(token: str) -> Expr:
    """A captured token is a number literal or a name.

    Negative numbers are a Unary MINUS over a positive literal — render.py
    keeps NumberLiteral non-negative (§6.2), so `-5` is
    `Unary(MINUS, NumberLiteral(5))`, never a literal -5. (Not `unplug`:
    that is logical negation over a boolean, a different operator.)
    """
    token = token.strip()
    if token.lstrip("-").isdigit():
        value = int(token)
        if value < 0:
            return Unary(op=TokenType.MINUS, operand=NumberLiteral(value=-value))
        return NumberLiteral(value=value)
    return Name(ident=token)


def _trace_binary(m, op: TokenType, left_g, right_g):
    left = _num_or_name(m.group(left_g))
    right = _num_or_name(m.group(right_g))
    return Program(statements=[Trace(value=Binary(left=left, op=op, right=right))])


def _build_add(m):
    return _trace_binary(m, TokenType.PLUS, "a", "b")


def _build_sub(m):
    # "subtract 7 from 2" means 2 - 7, while "subtract 7 minus 2" means
    # 7 - 2 — the connector decides which operand comes first.
    if m.group("conn") == "from":
        return _trace_binary(m, TokenType.MINUS, "b", "a")
    return _trace_binary(m, TokenType.MINUS, "a", "b")


def _build_mul(m):
    return _trace_binary(m, TokenType.STAR, "a", "b")


def _build_div(m):
    return _trace_binary(m, TokenType.SLASH, "a", "b")


_Intent(
    r"add\s+(?P<a>-?\d+|\w+)\s+and\s+(?P<b>-?\d+|\w+)",
    _build_add,
    "add <a> and <b>",
)
_Intent(
    r"subtract\s+(?P<a>-?\d+|\w+)\s+(?P<conn>minus|from)\s+(?P<b>-?\d+|\w+)",
    _build_sub,
    "subtract <a> minus <b>",
)
_Intent(
    r"multiply\s+(?P<a>-?\d+|\w+)\s+times\s+(?P<b>-?\d+|\w+)",
    _build_mul,
    "multiply <a> times <b>",
)
_Intent(
    r"divide\s+(?P<a>-?\d+|\w+)\s+by\s+(?P<b>-?\d+|\w+)",
    _build_div,
    "divide <a> by <b>",
)


def _build_double(m):
    a = _num_or_name(m.group("a"))
    expr = Binary(left=a, op=TokenType.STAR, right=NumberLiteral(value=2))
    return Program(statements=[Trace(value=expr)])


def _build_half(m):
    a = _num_or_name(m.group("a"))
    expr = Binary(left=a, op=TokenType.SLASH, right=NumberLiteral(value=2))
    return Program(statements=[Trace(value=expr)])


_Intent(r"double\s+(?P<a>-?\d+|\w+)", _build_double, "double <a>")
_Intent(r"half\s+of\s+(?P<a>-?\d+|\w+)", _build_half, "half of <a>")


_COMPARE = {
    "greater than": TokenType.GT,
    "less than": TokenType.LT,
    "greater than or equal to": TokenType.GTE,
    "less than or equal to": TokenType.LTE,
    "equal to": TokenType.EQ,
}


def _build_compare(m):
    op = _COMPARE[m.group("op")]
    left = _num_or_name(m.group("a"))
    right = _num_or_name(m.group("b"))
    return Program(statements=[Trace(value=Binary(left=left, op=op, right=right))])


_Intent(
    r"is\s+(?P<a>-?\d+|\w+)\s+(?P<op>greater than or equal to|less than or equal to|"
    r"greater than|less than|equal to)\s+(?P<b>-?\d+|\w+)",
    _build_compare,
    "is <a> greater than <b>",
)


# --- Trace and declare intents -------------------------------------------


def _value(token: str) -> Expr:
    """A value: a number literal, or a string literal (quoted or bare).

    A bare word is a string literal, not a Name — "trace hello" outputs
    the string "hello". Names are reserved for explicit "store X as Y"
    bindings and arithmetic operands (via _num_or_name).
    """
    token = token.strip()
    if token.startswith('"') and token.endswith('"'):
        return StringLiteral(value=token[1:-1])
    if token.lstrip("-").isdigit():
        return _num_or_name(token)
    return StringLiteral(value=token)


def _build_trace(m):
    return Program(statements=[Trace(value=_value(m.group("v")))])


def _build_declare(m):
    return Program(statements=[
        Declare(name=m.group("name"), value=_value(m.group("v"))),
    ])


_Intent(r"trace\s+(?P<v>.+)", _build_trace, "trace <value>")
_Intent(r"store\s+(?P<v>.+)\s+as\s+(?P<name>[a-z_]\w*)", _build_declare, "store <value> as <name>")
