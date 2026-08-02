"""Token vocabulary for MatrixLang.

Pure data. This module must not import from any sibling module — the Stage 2
parser depends on it and has no business pulling in the scanner.
"""

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    # Literals and names
    NUMBER = auto()
    STRING = auto()
    IDENT = auto()

    # Keywords
    CONSTRUCT = auto()
    TRACE = auto()
    REDPILL = auto()
    BLUEPILL = auto()
    DEJAVU = auto()
    FLATLINE = auto()
    TRUE = auto()
    FALSE = auto()
    AGENT = auto()
    JACKOUT = auto()
    LENGTH = auto()
    SPLICE = auto()
    FORK = auto()
    UNPLUG = auto()

    # Operators
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    ASSIGN = auto()
    EQ = auto()
    NEQ = auto()
    LT = auto()
    GT = auto()
    LTE = auto()
    GTE = auto()

    # Punctuation
    LPAREN = auto()
    RPAREN = auto()
    COMMA = auto()
    LBRACKET = auto()
    RBRACKET = auto()

    # Structural
    COMMENT = auto()
    NEWLINE = auto()
    EOF = auto()


KEYWORDS: dict[str, TokenType] = {
    "construct": TokenType.CONSTRUCT,
    "trace": TokenType.TRACE,
    "redpill": TokenType.REDPILL,
    "bluepill": TokenType.BLUEPILL,
    "dejavu": TokenType.DEJAVU,
    "flatline": TokenType.FLATLINE,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "agent": TokenType.AGENT,
    "jackout": TokenType.JACKOUT,
    "length": TokenType.LENGTH,
    "splice": TokenType.SPLICE,
    "fork": TokenType.FORK,
    "unplug": TokenType.UNPLUG,
}


@dataclass(frozen=True)
class Token:
    """One lexical unit.

    `lexeme` is the exact source text, preserved so Stage 4 can re-render.
    `value` is the decoded Python value for NUMBER, STRING, TRUE and FALSE;
    None for everything else.
    """

    type: TokenType
    lexeme: str
    line: int
    column: int
    value: int | str | bool | None = None
