"""The MatrixLang parser: token list in, syntax tree out.

Recursive descent. One method per grammar rule; precedence is encoded in
the call chain, tightest binding deepest. The parser never imports the
lexer — it consumes any list[Token], which is what lets one parser serve
both source faces in Stage 4.
"""

from matrixlang.errors import ParseError
from matrixlang.nodes import (
    BoolLiteral,
    Expr,
    Name,
    NumberLiteral,
    StringLiteral,
    Unary,
)
from matrixlang.tokens import Token, TokenType


def parse_expression(tokens: list[Token]) -> Expr:
    """Parse a single expression — the Stage 3 REPL's entry point.

    A trailing comment is accepted and discarded: expression parsing is a
    REPL convenience; the round-trip criterion applies to whole programs
    via parse(), where trivia is preserved.
    """
    parser = _Parser(tokens)
    expr = parser.expression()
    if parser.check(TokenType.COMMENT):
        parser.advance()
    if parser.check(TokenType.NEWLINE):
        parser.advance()
    end = parser.peek()
    if end.type is not TokenType.EOF:
        raise ParseError(
            f"unexpected input after expression: {_describe(end)}",
            end.line,
            end.column,
        )
    return expr


def _describe(token: Token) -> str:
    if token.type is TokenType.EOF:
        return "end of input"
    if token.type is TokenType.NEWLINE:
        return "end of line"
    return f"'{token.lexeme}'"


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._pos = 0

    # --- cursor -----------------------------------------------------------

    def peek(self) -> Token:
        return self._tokens[self._pos]

    def advance(self) -> Token:
        token = self._tokens[self._pos]
        self._pos += 1
        return token

    def check(self, type_: TokenType) -> bool:
        return self.peek().type is type_

    def expect(self, type_: TokenType, message: str) -> Token:
        token = self.peek()
        if token.type is not type_:
            raise ParseError(
                f"{message}, found {_describe(token)}", token.line, token.column
            )
        return self.advance()

    # --- expressions ------------------------------------------------------

    def expression(self) -> Expr:
        return self._unary()

    def _unary(self) -> Expr:
        if self.check(TokenType.MINUS):
            op = self.advance()
            operand = self._unary()
            return Unary(TokenType.MINUS, operand, line=op.line, column=op.column)
        return self._primary()

    def _primary(self) -> Expr:
        token = self.peek()
        if token.type is TokenType.NUMBER:
            self.advance()
            return NumberLiteral(token.value, line=token.line, column=token.column)
        if token.type is TokenType.STRING:
            self.advance()
            return StringLiteral(token.value, line=token.line, column=token.column)
        if token.type in (TokenType.TRUE, TokenType.FALSE):
            self.advance()
            return BoolLiteral(token.value, line=token.line, column=token.column)
        if token.type is TokenType.IDENT:
            self.advance()
            return Name(token.lexeme, line=token.line, column=token.column)
        if token.type is TokenType.LPAREN:
            self.advance()
            inner = self.expression()
            self.expect(TokenType.RPAREN, "expected ')' to close '('")
            return inner
        raise ParseError(
            f"expected an expression, found {_describe(token)}",
            token.line,
            token.column,
        )
