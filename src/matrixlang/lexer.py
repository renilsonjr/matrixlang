"""The MatrixLang scanner: source text in, token list out."""

import string

from matrixlang.errors import LexError
from matrixlang.tokens import KEYWORDS, Token, TokenType

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

_DOUBLE: dict[str, TokenType] = {
    "==": TokenType.EQ,
    "!=": TokenType.NEQ,
    "<=": TokenType.LTE,
    ">=": TokenType.GTE,
}

# Explicit ASCII sets. str.isdigit() and str.isalpha() accept Unicode, which
# would let Stage 4 glyphs lex as identifiers. See Global Constraints.
_DIGITS = frozenset(string.digits)
_ID_START = frozenset(string.ascii_letters + "_")
_ID_CONTINUE = frozenset(string.ascii_letters + string.digits + "_")

_ESCAPES: dict[str, str] = {'"': '"', "\\": "\\", "n": "\n"}


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

        if char == '"':
            token, index, column = _scan_string(source, index, line, column)
            tokens.append(token)
            continue

        if char in _DIGITS:
            start = index
            start_column = column
            while index < length and source[index] in _DIGITS:
                index += 1
                column += 1
            lexeme = source[start:index]
            tokens.append(
                Token(TokenType.NUMBER, lexeme, line, start_column, int(lexeme))
            )
            continue

        if char in _ID_START:
            start = index
            start_column = column
            while index < length and source[index] in _ID_CONTINUE:
                index += 1
                column += 1
            lexeme = source[start:index]
            token_type = KEYWORDS.get(lexeme, TokenType.IDENT)
            value: bool | None = None
            if token_type is TokenType.TRUE:
                value = True
            elif token_type is TokenType.FALSE:
                value = False
            tokens.append(Token(token_type, lexeme, line, start_column, value))
            continue

        two = source[index : index + 2]
        if two in _DOUBLE:
            tokens.append(Token(_DOUBLE[two], two, line, column))
            index += 2
            column += 2
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


def _scan_string(
    source: str, index: int, line: int, column: int
) -> tuple[Token, int, int]:
    """Scan a double-quoted string starting at `index`.

    Returns the token plus the updated index and column. Errors are reported
    at the opening quote, which is the position a reader needs to find.
    """
    length = len(source)
    start = index
    start_column = column
    index += 1
    column += 1
    decoded: list[str] = []

    while True:
        if index >= length or source[index] == "\n":
            raise LexError("unterminated string", line, start_column)

        char = source[index]

        if char == '"':
            index += 1
            column += 1
            return (
                Token(
                    TokenType.STRING,
                    source[start:index],
                    line,
                    start_column,
                    "".join(decoded),
                ),
                index,
                column,
            )

        if char == "\\":
            if index + 1 >= length or source[index + 1] == "\n":
                raise LexError("unterminated string", line, start_column)
            escape = source[index + 1]
            if escape not in _ESCAPES:
                raise LexError(
                    f"unknown escape sequence '\\{escape}'", line, column
                )
            decoded.append(_ESCAPES[escape])
            index += 2
            column += 2
            continue

        decoded.append(char)
        index += 1
        column += 1
