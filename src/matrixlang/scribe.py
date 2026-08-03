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
        parts[i] = part
    return " ".join('"'.join(parts).split())


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
    """A suggestion for an unmatched request, from the known intents."""
    for intent in INTENTS:
        # Reuse the catalogue's own descriptions as hints.
        if intent.hint and any(word in text for word in intent.hint.split()):
            return intent.hint
    return None


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
