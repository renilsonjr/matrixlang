"""The MatrixLang parser: token list in, syntax tree out.

Recursive descent. One method per grammar rule; precedence is encoded in
the call chain, tightest binding deepest. The parser never imports the
lexer — it consumes any list[Token], which is what lets one parser serve
both source faces in Stage 4.
"""

from collections.abc import Callable

from matrixlang.errors import ParseError
from matrixlang.nodes import (
    Call,
    ExprStmt,
    FunctionDef,
    ListLiteral,
    Return,
    Assign,
    Binary,
    BoolLiteral,
    Declare,
    Expr,
    If,
    Name,
    NumberLiteral,
    Program,
    StringLiteral,
    Stmt,
    Trace,
    Unary,
    While,
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


def _adopt_header_comment(
    comment: str | None, body: list[Stmt], trailing: list[str]
) -> None:
    """A comment on a block-header line normalizes into the block's body.

    Lossless at AST level: the text survives in the tree and re-parses
    equal; only its line placement is normalized by a render.
    """
    if comment is None:
        return
    if body:
        body[0].leading_comments.insert(0, comment)
    else:
        trailing.insert(0, comment)


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
            leading = self._collect_leading()
            if self.check(TokenType.EOF):
                return Program(statements, trailing_comments=leading)
            statement = self._statement()
            statement.leading_comments = leading
            statements.append(statement)

    def _collect_leading(self) -> list[str]:
        """Blank lines and full-line comments before a statement position."""
        comments: list[str] = []
        while True:
            if self.check(TokenType.NEWLINE):
                self.advance()
                continue
            if self.check(TokenType.COMMENT):
                comments.append(self.advance().lexeme)
                self.expect(TokenType.NEWLINE, "expected end of line after comment")
                continue
            return comments

    def _statement(self) -> Stmt:
        token = self.peek()
        if token.type is TokenType.CONSTRUCT:
            return self._declare()
        if token.type is TokenType.TRACE:
            return self._trace()
        if token.type is TokenType.REDPILL:
            return self._if()
        if token.type is TokenType.DEJAVU:
            return self._while()
        if token.type is TokenType.AGENT:
            return self._agent()
        if token.type is TokenType.JACKOUT:
            return self._return()
        if token.type is TokenType.IDENT:
            # One token of lookahead decides, and it is the '(' rather
            # than the '='. Dispatching on the paren means `x + 1` still
            # reaches _assign and still reports "expected '='", which is
            # the more useful message for what that mistake usually is.
            if self._tokens[self._pos + 1].type is TokenType.LPAREN:
                return self._expression_statement()
            return self._assign()
        raise ParseError(
            f"expected a statement, found {_describe(token)}",
            token.line,
            token.column,
        )
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

    def _if(self) -> If:
        keyword = self.advance()
        condition = self.expression()
        header_comment = self._end_header()
        then_body, then_trailing = self._body(
            TokenType.BLUEPILL, TokenType.FLATLINE
        )
        _adopt_header_comment(header_comment, then_body, then_trailing)
        else_body: list[Stmt] | None = None
        else_trailing: list[str] = []
        if self.check(TokenType.BLUEPILL):
            self.advance()
            else_header = self._end_header()
            else_body, else_trailing = self._body(TokenType.FLATLINE)
            _adopt_header_comment(else_header, else_body, else_trailing)
        self.expect(TokenType.FLATLINE, "expected 'flatline' to close 'redpill'")
        node = If(
            condition,
            then_body,
            else_body,
            line=keyword.line,
            column=keyword.column,
            then_trailing=then_trailing,
            else_trailing=else_trailing,
        )
        self._end_statement(node)
        return node

    def _while(self) -> While:
        keyword = self.advance()
        condition = self.expression()
        header_comment = self._end_header()
        body, body_trailing = self._body(TokenType.FLATLINE)
        _adopt_header_comment(header_comment, body, body_trailing)
        self.expect(TokenType.FLATLINE, "expected 'flatline' to close 'dejavu'")
        node = While(
            condition,
            body,
            line=keyword.line,
            column=keyword.column,
            body_trailing=body_trailing,
        )
        self._end_statement(node)
        return node

    def _agent(self) -> FunctionDef:
        keyword = self.advance()
        name = self.expect(TokenType.IDENT, "expected a name after 'agent'")
        self.expect(TokenType.LPAREN, "expected '(' after the agent's name")
        params: list[str] = []
        if not self.check(TokenType.RPAREN):
            while True:
                param = self.expect(
                    TokenType.IDENT, "expected a parameter name"
                )
                params.append(param.lexeme)
                if not self.check(TokenType.COMMA):
                    break
                self.advance()
        self.expect(TokenType.RPAREN, "expected ')' to close the parameter list")

        header_comment = self._end_header()
        body, body_trailing = self._body(TokenType.FLATLINE)
        _adopt_header_comment(header_comment, body, body_trailing)
        self.expect(TokenType.FLATLINE, "expected 'flatline' to close 'agent'")
        node = FunctionDef(
            name.lexeme,
            params,
            body,
            line=keyword.line,
            column=keyword.column,
            body_trailing=body_trailing,
        )
        self._end_statement(node)
        return node

    def _return(self) -> Return:
        keyword = self.advance()
        # A bare `jackout` is an early exit from a procedure. Anything that
        # can begin an expression means a value is coming.
        value = None
        if not self.check(TokenType.NEWLINE) and not self.check(TokenType.EOF):
            if not self.check(TokenType.COMMENT):
                value = self.expression()
        node = Return(value, line=keyword.line, column=keyword.column)
        self._end_statement(node)
        return node

    def _expression_statement(self) -> ExprStmt:
        """A call, evaluated for its effect.

        Only a call. `1 + 1` and a bare name compute something and throw it
        away, which is a mistake rather than a statement — the grammar said
        so before Stage 6 and still does. What changed is that a call may
        now legitimately be run for what it does rather than what it
        returns.
        """
        token = self.peek()
        value = self.expression()
        if not isinstance(value, Call):
            raise ParseError(
                f"expected a statement, found {_describe(token)}",
                token.line,
                token.column,
            )
        node = ExprStmt(value, line=token.line, column=token.column)
        self._end_statement(node)
        return node

    def _end_header(self) -> str | None:
        """Line ending after a block header; returns its trailing comment."""
        comment = None
        if self.check(TokenType.COMMENT):
            comment = self.advance().lexeme
        self.expect(TokenType.NEWLINE, "expected end of line")
        return comment

    def _body(self, *closers: TokenType) -> tuple[list[Stmt], list[str]]:
        """Statements until a closer keyword. Returns (statements, dangling
        comments collected after the last statement)."""
        statements: list[Stmt] = []
        while True:
            leading = self._collect_leading()
            if self.peek().type in closers or self.check(TokenType.EOF):
                return statements, leading
            statement = self._statement()
            statement.leading_comments = leading
            statements.append(statement)

    def _end_statement(self, node: Stmt) -> None:
        if self.check(TokenType.COMMENT):
            node.trailing_comment = self.advance().lexeme
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

    def _binary_level(
        self, operators: tuple[TokenType, ...], next_level: Callable[[], Expr]
    ) -> Expr:
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
        return self._call()

    def _call(self) -> Expr:
        """Postfix application, so a call binds tighter than any operator.

        Loops rather than recurses so `f()()` is a call on a call. Nothing
        reaches across a NEWLINE: the lexer emits one between statements,
        and `check` sees it before it sees a '('.
        """
        expr = self._primary()
        while self.check(TokenType.LPAREN):
            paren = self.advance()
            args: list[Expr] = []
            if not self.check(TokenType.RPAREN):
                while True:
                    args.append(self.expression())
                    if not self.check(TokenType.COMMA):
                        break
                    self.advance()
            self.expect(TokenType.RPAREN, "expected ')' to close the arguments")
            expr = Call(expr, args, line=paren.line, column=paren.column)
        return expr

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
        if token.type is TokenType.LBRACKET:
            self.advance()
            elements: list[Expr] = []
            if not self.check(TokenType.RBRACKET):
                while True:
                    elements.append(self.expression())
                    if not self.check(TokenType.COMMA):
                        break
                    self.advance()
            self.expect(TokenType.RBRACKET, "expected ']' to close the list")
            return ListLiteral(elements, line=token.line, column=token.column)
        raise ParseError(
            f"expected an expression, found {_describe(token)}",
            token.line,
            token.column,
        )
