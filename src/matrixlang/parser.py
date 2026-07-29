"""The MatrixLang parser: token list in, syntax tree out.

Recursive descent. One method per grammar rule; precedence is encoded in
the call chain, tightest binding deepest. The parser never imports the
lexer — it consumes any list[Token], which is what lets one parser serve
both source faces in Stage 4.
"""

from matrixlang.errors import ParseError
from matrixlang.nodes import (
    Assign,
    Binary,
    BoolLiteral,
    Declare,
    Expr,
    Name,
    NumberLiteral,
    Program,
    StringLiteral,
    Stmt,
    Trace,
    Unary,
)
from matrixlang.tokens import Token, TokenType


def parse(tokens: list[Token]) -> Program:
    """Parse a complete program."""
    return _Parser(tokens).parse_program()


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


_EQUALITY_OPS = (TokenType.EQ, TokenType.NEQ)
_COMPARISON_OPS = (TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE)
_TERM_OPS = (TokenType.PLUS, TokenType.MINUS)
_FACTOR_OPS = (TokenType.STAR, TokenType.SLASH)


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

    # --- statements -------------------------------------------------------

    def parse_program(self) -> Program:
        statements: list[Stmt] = []
        while True:
            self._skip_blank_lines()
            if self.check(TokenType.EOF):
                return Program(statements)
            statements.append(self._statement())

    def _skip_blank_lines(self) -> None:
        while self.check(TokenType.NEWLINE):
            self.advance()

    def _statement(self) -> Stmt:
        token = self.peek()
        if token.type is TokenType.CONSTRUCT:
            return self._declare()
        if token.type is TokenType.TRACE:
            return self._trace()
        if token.type is TokenType.IDENT:
            return self._assign()
        raise ParseError(
            f"expected a statement, found {_describe(token)}",
            token.line,
            token.column,
        )

    def _declare(self) -> Declare:
        keyword = self.advance()
        name = self.expect(TokenType.IDENT, "expected a name after 'construct'")
        self.expect(TokenType.ASSIGN, "expected '=' after the name")
        value = self.expression()
        node = Declare(name.lexeme, value, line=keyword.line, column=keyword.column)
        self._end_statement(node)
        return node

    def _assign(self) -> Assign:
        name = self.advance()
        self.expect(TokenType.ASSIGN, "expected '=' after the name")
        value = self.expression()
        node = Assign(name.lexeme, value, line=name.line, column=name.column)
        self._end_statement(node)
        return node

    def _trace(self) -> Trace:
        keyword = self.advance()
        value = self.expression()
        node = Trace(value, line=keyword.line, column=keyword.column)
        self._end_statement(node)
        return node

    def _end_statement(self, node: Stmt) -> None:
        """Consume the statement's line ending. Task 5 teaches it about
        trailing comments."""
        self.expect(TokenType.NEWLINE, "expected end of line after the statement")

    # --- expressions ------------------------------------------------------

    def expression(self) -> Expr:
        return self._equality()

    # The ladder: each level parses the next-tighter level, then folds a
    # left-associative chain of its own operators. Named levels keep the
    # grammar visible; the shared loop lives once in _binary_level.

    def _equality(self) -> Expr:
        return self._binary_level(_EQUALITY_OPS, self._comparison)

    def _comparison(self) -> Expr:
        return self._binary_level(_COMPARISON_OPS, self._term)

    def _term(self) -> Expr:
        return self._binary_level(_TERM_OPS, self._factor)

    def _factor(self) -> Expr:
        return self._binary_level(_FACTOR_OPS, self._unary)

    def _binary_level(self, operators, next_level) -> Expr:
        expr = next_level()
        while self.peek().type in operators:
            op = self.advance()
            right = next_level()
            expr = Binary(expr, op.type, right, line=op.line, column=op.column)
        return expr

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
