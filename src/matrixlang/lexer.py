"""The MatrixLang scanner: source text in, token list out."""

import string

from matrixlang.errors import LexError
from matrixlang.glyphs import GLYPHS, REVERSE
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
# would let glyphs lex as identifiers. Glyphs enter through REVERSE only.
_DIGITS = frozenset(string.digits)
_GLYPH_DIGITS = frozenset(GLYPHS[digit] for digit in string.digits)
_ANY_DIGIT = _DIGITS | _GLYPH_DIGITS
_COMMENT_MARKERS = frozenset({"#", GLYPHS["#"]})

# Glyph char -> TokenType for the single-glyph tokens (keywords, operators,
# parens). Digits and the comment marker are handled by their own branches.
_GLYPH_TOKENS: dict[str, TokenType] = {}
for _slot, _glyph in GLYPHS.items():
    if _slot in KEYWORDS:
        _GLYPH_TOKENS[_glyph] = KEYWORDS[_slot]
    elif _slot in _DOUBLE:
        _GLYPH_TOKENS[_glyph] = _DOUBLE[_slot]
    elif _slot in _SINGLE:
        _GLYPH_TOKENS[_glyph] = _SINGLE[_slot]

_ID_START = frozenset(string.ascii_letters + "_")
_ID_CONTINUE = frozenset(string.ascii_letters + string.digits + "_")

_ESCAPES: dict[str, str] = {'"': '"', "\\": "\\", "n": "\n"}

# Control characters are refused in source text, inside strings and comments
# alike. Raw bytes there reach a reader's terminal unescaped through `trace`,
# `matrixlang parse`, `matrixlang render` and the REPL's glyph echo, so an ESC
# in a .rain file can drive the terminal of someone merely INSPECTING it.
#
# Refusing them here rather than escaping at those output sites is what keeps
# the round-trip criterion (parent spec §4.3) intact: `render` must reproduce
# source exactly, and an escaped byte would re-lex as the escape text rather
# than the byte. Refused at the boundary, such trees cannot be built from
# source at all, so every output path is closed at once.
#
# Two carve-outs. Tab cannot drive a terminal, and refusing it would break
# working programs for no security gain. Newline inside a string never reaches
# this check — `_scan_string` reports the better "unterminated string" first.
_EXEMPT_CONTROLS = frozenset("\t")


def _is_control(char: str) -> bool:
    """C0, DEL and C1, minus the exemptions above."""
    codepoint = ord(char)
    return (
        codepoint < 0x20 or 0x7F <= codepoint <= 0x9F
    ) and char not in _EXEMPT_CONTROLS


def _reject_control(char: str, line: int, column: int, where: str) -> None:
    if _is_control(char):
        raise LexError(
            f"control character U+{ord(char):04X} is not allowed in {where}",
            line,
            column,
        )


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

        if char in _COMMENT_MARKERS:
            start = index
            start_column = column
            while index < length and source[index] != "\n":
                _reject_control(source[index], line, column, "a comment")
                index += 1
                column += 1
            # Canonical trivia (§6.1): a glyph marker is stored as '#', so
            # the same comment re-lexed from either face compares equal.
            lexeme = "#" + source[start + 1 : index]
            tokens.append(Token(TokenType.COMMENT, lexeme, line, start_column))
            continue

        if char == '"':
            token, index, column = _scan_string(source, index, line, column)
            tokens.append(token)
            continue

        if char in _ANY_DIGIT:
            start = index
            start_column = column
            while index < length and source[index] in _ANY_DIGIT:
                index += 1
                column += 1
            lexeme = source[start:index]
            value = int("".join(REVERSE.get(c, c) for c in lexeme))
            tokens.append(
                Token(TokenType.NUMBER, lexeme, line, start_column, value)
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

        if char in _GLYPH_TOKENS:
            token_type = _GLYPH_TOKENS[char]
            value = None
            if token_type is TokenType.TRUE:
                value = True
            elif token_type is TokenType.FALSE:
                value = False
            tokens.append(Token(token_type, char, line, column, value))
            index += 1
            column += 1
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
    at the opening quote, which is the position a reader needs to find,
    except unknown escapes, which report at the backslash.
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

        # Only literal source bytes are screened. A control character that
        # came from an escape — `\n` decoding to U+000A above — is explicit
        # and intended, and the round trip depends on it surviving.
        _reject_control(char, line, column, "a string")
        decoded.append(char)
        index += 1
        column += 1
