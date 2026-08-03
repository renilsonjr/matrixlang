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
    if _CONDITIONAL_PREFIX.match(text) and not intent.conditional:
        # The request opens with a conditional prefix but the conditional
        # regexes did not win — longest-match-wins fell through to the bare
        # `trace <value>` intent, which always matches. Silently returning
        # `trace "bigger"` drops the condition and runs unconditionally, so
        # this is a miss, not a check()-valid-but-wrong program.
        return ScribeMiss(
            "conditional comparisons need numbers, like 'if 5 is greater than 3'",
            closest=_closest(text),
        )
    program = intent.build(match)
    return ScribeProgram(program=program, source=render_ascii(program))


# --- Normalization ------------------------------------------------------


def normalize(request: str) -> str:
    """Collapse whitespace and map synonyms, leaving quoted text alone.

    "print hello world" and "show hello world" both become the canonical
    phrasing the patterns look for. Number operands are digits only —
    the patterns match `-?\\d+`, so a word operand ("add five and three")
    is a miss rather than a program that names an undeclared variable.

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


# A request that opens with a conditional prefix (`if` / `if not`) but whose
# condition did not match must be a miss, never a bare unconditional trace.
_CONDITIONAL_PREFIX = re.compile(r"^if(?: not)?\b")


# --- Intent registry ----------------------------------------------------

INTENTS: list["_Intent"] = []


class _Intent:
    """One pattern: a regex, a builder, and a human hint.

    Registration order carries no meaning — `scribe()` picks the widest
    match, not the first. Intents are free to overlap. A conditional
    intent marks itself so `scribe()` can turn a request that opens with
    `if`/`if not` but matches nothing conditional into a miss.
    """

    def __init__(self, regex: str, build, hint: str, conditional: bool = False):
        self.regex = re.compile(regex)
        self.build = build
        self.hint = hint
        self.conditional = conditional
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
    if re.fullmatch(r"-?\d+", token):
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
    r"add\s+(?P<a>-?\d+)\s+and\s+(?P<b>-?\d+)",
    _build_add,
    "add <a> and <b>",
)
_Intent(
    r"subtract\s+(?P<a>-?\d+)\s+(?P<conn>minus|from)\s+(?P<b>-?\d+)",
    _build_sub,
    "subtract <a> minus <b>",
)
_Intent(
    r"multiply\s+(?P<a>-?\d+)\s+times\s+(?P<b>-?\d+)",
    _build_mul,
    "multiply <a> times <b>",
)
_Intent(
    r"divide\s+(?P<a>-?\d+)\s+by\s+(?P<b>-?\d+)",
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


_Intent(r"double\s+(?P<a>-?\d+)", _build_double, "double <a>")
_Intent(r"half\s+of\s+(?P<a>-?\d+)", _build_half, "half of <a>")


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
    r"is\s+(?P<a>-?\d+)\s+(?P<op>greater than or equal to|less than or equal to|"
    r"greater than|less than|equal to)\s+(?P<b>-?\d+)",
    _build_compare,
    "is <a> greater than <b>",
)


# --- Conditional intents ----------------------------------------------------


def _compare_expr(a, op_word, b) -> Binary:
    op = _COMPARE[op_word]
    return Binary(left=_num_or_name(a), op=op, right=_num_or_name(b))


def _build_if(m):
    cond = _compare_expr(m.group("a"), m.group("op"), m.group("b"))
    then_body = [Trace(value=_value(m.group("action")))]
    return Program(statements=[If(condition=cond, then_body=then_body)])


# `is` is part of the phrasing the tests feed in ("if 5 IS greater than 3")
# and must be in the pattern. `print` is already normalized to `trace`
# before matching, so listing it as an alternative here would be dead.
_Intent(
    r"if\s+(?P<a>-?\d+)\s+is\s+"
    r"(?P<op>greater than or equal to|less than or equal to|greater than|less than|equal to)"
    r"\s+(?P<b>-?\d+)\s+trace\s+(?P<action>.+)",
    _build_if,
    "if <a> is greater than <b> trace <value>",
    conditional=True,
)


def _build_if_not(m):
    cond = _compare_expr(m.group("a"), m.group("op"), m.group("b"))
    cond = Unary(op=TokenType.UNPLUG, operand=cond)
    then_body = [Trace(value=_value(m.group("action")))]
    return Program(statements=[If(condition=cond, then_body=then_body)])


_Intent(
    r"if\s+not\s+(?P<a>-?\d+)\s+is\s+"
    r"(?P<op>greater than or equal to|less than or equal to|greater than|less than|equal to)"
    r"\s+(?P<b>-?\d+)\s+trace\s+(?P<action>.+)",
    _build_if_not,
    "if not <a> is greater than <b> trace <value>",
    conditional=True,
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
    if re.fullmatch(r"-?\d+", token):
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


# --- Loop intents ------------------------------------------------------------


def _counter_step(name: str, step: int) -> Assign:
    """The loop's increment: `i = i + 1` up, `i = i - 1` down.

    Negative steps use the MINUS op with a positive literal — render.py
    keeps NumberLiteral non-negative (§6.2), so `-1` must never be a
    literal value.
    """
    op = TokenType.MINUS if step < 0 else TokenType.PLUS
    return Assign(
        name=name,
        value=Binary(
            left=Name(ident=name),
            op=op,
            right=NumberLiteral(value=abs(step)),
        ),
    )


def _loop(name: str, start, end_op: TokenType, end, step: int) -> Program:
    return Program(statements=[
        Declare(name=name, value=start),
        While(
            condition=Binary(left=Name(ident=name), op=end_op, right=end),
            body=[Trace(value=Name(ident=name)), _counter_step(name, step)],
        ),
    ])


def _build_count_up(m):
    start = _num_or_name(m.group("a"))
    end = _num_or_name(m.group("b"))
    return _loop("i", start, TokenType.LTE, end, 1)


def _build_count_down(m):
    start = _num_or_name(m.group("a"))
    end = _num_or_name(m.group("b"))
    return _loop("i", start, TokenType.GTE, end, -1)


_Intent(r"count\s+down\s+from\s+(?P<a>-?\d+)\s+to\s+(?P<b>-?\d+)", _build_count_down, "count down from <a> to <b>")
_Intent(r"count\s+from\s+(?P<a>-?\d+)\s+to\s+(?P<b>-?\d+)", _build_count_up, "count from <a> to <b>")


# --- List intents ------------------------------------------------------------


def _build_list(m):
    elems = [_num_or_name(t) for t in m.group("elems").split()]
    return Program(statements=[
        Declare(name="xs", value=ListLiteral(elements=elems)),
    ])


# A Scribe program is the whole program, so an intent that reads `xs` must
# also declare it. `trace xs[0]` alone parses fine and then dies at runtime
# with "'xs' is not declared" — which means check() rejects it and the user
# gets an error instead of a program. The declaration is what makes these
# runnable; _DEMO_LIST is the stand-in the request did not supply.
_DEMO_LIST = [10, 20, 30]

# Every accepted input must produce a program check() dry-runs as valid.
# The demo list fixes the list at len(_DEMO_LIST) elements, so an index at
# or past that length dies at runtime (`index N is past the end of a list`).
# The get-element regex below bounds its `i` group to this range so an
# out-of-bounds request is a ScribeMiss instead of a check()-invalid
# program. Single-digit assumption is safe for a 3-element demo list.
_INDEX_MAX = len(_DEMO_LIST) - 1


def _demo_list(name: str) -> Declare:
    return Declare(
        name=name,
        value=ListLiteral(elements=[NumberLiteral(value=v) for v in _DEMO_LIST]),
    )


def _build_get_element(m):
    name = m.group("name")
    index = _num_or_name(m.group("i"))
    return Program(statements=[
        _demo_list(name),
        Trace(value=Index(target=Name(ident=name), index=index)),
    ])


def _build_length(m):
    name = m.group("name")
    return Program(statements=[
        _demo_list(name),
        Trace(value=Unary(op=TokenType.LENGTH, operand=Name(ident=name))),
    ])


_Intent(
    r"make\s+a\s+list\s+of\s+(?P<elems>-?\d+(?:\s+-?\d+)*)",
    _build_list,
    "make a list of <values>",
)
_Intent(
    rf"get\s+element\s+(?P<i>[0-{_INDEX_MAX}])\s+of\s+(?P<name>[a-z_]\w*)",
    _build_get_element,
    "get element <i> of <list>",
)
_Intent(r"length\s+of\s+(?P<name>[a-z_]\w*)", _build_length, "length of <list>")


# --- String intents -----------------------------------------------------------


def _build_string(m):
    return Program(statements=[
        Declare(name="s", value=StringLiteral(value=m.group("v"))),
    ])


# A Scribe program is the whole program, so an intent that reads a name must
# also declare it. The demo string is the stand-in the request did not supply.
_DEMO_STRING = "neo"

# Every accepted input must produce a program check() dry-runs as valid.
# The demo string fixes the string at len(_DEMO_STRING) characters, so an
# index at or past that length dies at runtime (`index N is past the end of
# a string of length 3`) and a negative index is rejected outright. The
# get-character regex below bounds its `i` group to this range so an
# out-of-bounds request is a ScribeMiss instead of a check()-invalid
# program. Single-digit assumption is safe for a 3-character demo string.
_CHAR_MAX = len(_DEMO_STRING) - 1


def _build_get_char(m):
    # Same rule as the list intents: declare what you read, or check()
    # rejects the program for naming an undeclared variable.
    name = m.group("name")
    return Program(statements=[
        Declare(name=name, value=StringLiteral(value=_DEMO_STRING)),
        Trace(value=Index(target=Name(ident=name), index=_num_or_name(m.group("i")))),
    ])


_Intent(r"make\s+a\s+string\s+(?P<v>\w+)", _build_string, "make a string <word>")
_Intent(rf"get\s+character\s+(?P<i>[0-{_CHAR_MAX}])\s+of\s+(?P<name>[a-z_]\w*)", _build_get_char, "get character <i> of <name>")


# --- Function intents -----------------------------------------------------------


def _build_double_fn(m):
    return Program(statements=[
        FunctionDef(
            name="double",
            params=["n"],
            body=[Return(value=Binary(left=Name(ident="n"), op=TokenType.STAR, right=NumberLiteral(value=2)))],
        ),
    ])


def _build_adder_factory(m):
    inner = FunctionDef(
        name="add",
        params=["m"],
        body=[Return(value=Binary(left=Name(ident="n"), op=TokenType.PLUS, right=Name(ident="m")))],
    )
    outer = FunctionDef(
        name="adder",
        params=["n"],
        body=[inner, Return(value=Name(ident="add"))],
    )
    return Program(statements=[outer])


_Intent(r"define\s+an?\s+adder\s+factory", _build_adder_factory, "define an adder factory")
_Intent(r"define\s+a\s+function\s+that\s+doubles", _build_double_fn, "define a function that doubles")
