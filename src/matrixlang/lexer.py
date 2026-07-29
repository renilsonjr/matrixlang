"""The MatrixLang scanner: source text in, token list out."""

import string

from matrixlang.errors import LexError
from matrixlang.tokens import Token, TokenType

_SINGLE: dict[str, TokenType] = {
    "+": TokenType.PLUS,
    "-": TokenType.MINUS,
    "*": TokenType.STAR,
    "/": TokenType.SLASH,
    "(": TokenType.LPAREN,
    ")": TokenType.RPAREN,
    "=": TokenType.ASSIGN,
    "<": TokenType.LT,
    ">": TokenType.GT,
}

# Explicit ASCII sets. str.isdigit() and str.isalpha() accept Unicode, which
# would let Stage 4 glyphs lex as identifiers. See Global Constraints.
_DIGITS = frozenset(string.digits)
_ID_START = frozenset(string.ascii_letters + "_")
_ID_CONTINUE = frozenset(string.ascii_letters + string.digits + "_")


def lex(source: str) -> list[Token]:
    """Scan `source` into a flat token list terminated by NEWLINE, EOF."""
    tokens: list[Token] = []
    index = 0
    line = 1
    column = 1
    length = len(source)

    while index < length:
        char = source[index]

        if char == "\n":
            tokens.append(Token(TokenType.NEWLINE, "\n", line, column))
            index += 1
            line += 1
            column = 1
            continue

        if char in " \t\r":
            index += 1
            column += 1
            continue

        if char in _SINGLE:
            tokens.append(Token(_SINGLE[char], char, line, column))
            index += 1
            column += 1
            continue

        raise LexError(f"unexpected character {char!r}", line, column)

    if tokens and tokens[-1].type is not TokenType.NEWLINE:
        tokens.append(Token(TokenType.NEWLINE, "", line, column))
    tokens.append(Token(TokenType.EOF, "", line, column))
    return tokens
