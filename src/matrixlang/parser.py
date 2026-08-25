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
    DictLiteral,
    ExprStmt,
    FunctionDef,
    Glitch,
    Index,
    IndexAssign,
    JackIn,
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
    Wake,
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


_FORK_OPS = (TokenType.FORK,)
_SPLICE_OPS = (TokenType.SPLICE,)
_EQUALITY_OPS = (TokenType.EQ, TokenType.NEQ)
_COMPARISON_OPS = (
    TokenType.LT,
    TokenType.GT,
    TokenType.LTE,
    TokenType.GTE,
    TokenType.ORACLE,
)
# `cleave` gets a rung of its own between comparison and term. Above
# comparison so `s cleave "," == xs` compares the LIST, and below term so
# `a + b cleave ","` concatenates before it splits. Both are the natural
# reading, and this is the only placement that gives both without
# parentheses.
_CLEAVE_OPS = (TokenType.CLEAVE,)
_TERM_OPS = (TokenType.PLUS, TokenType.MINUS)
_FACTOR_OPS = (TokenType.STAR, TokenType.SLASH, TokenType.PERCENT)


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
        if token.type is TokenType.WAKE:
            return self._bare(Wake)
        if token.type is TokenType.GLITCH:
            return self._bare(Glitch)
        if token.type is TokenType.IDENT:
            # One token of lookahead decides, and it is the suffix rather
            # than the '='. Dispatching on the paren means `x + 1` still
            # reaches _assign and still reports "expected '='", which is
            # the more useful message for what that mistake usually is.
            nxt = self._tokens[self._pos + 1].type
            if nxt is TokenType.LPAREN:
                return self._expression_statement()
            if nxt is TokenType.LBRACKET:
                return self._index_assign()
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

    def _index_assign(self) -> IndexAssign:
        """`xs[0] = 9`, and `xs[0][1] = 9`.

        The target is a name followed by one or more index suffixes.
        Parsing it as a full postfix chain and then rejecting a Call is
        what produces a message about the real problem — a call result is
        not a place — instead of a confusing one about the '['.
        """
        start = self.peek()
        chain = self._call()
        if not isinstance(chain, Index):
            raise ParseError(
                "cannot assign to this — only a name or an element of one",
                start.line,
                start.column,
            )
        if isinstance(chain.target, Call):
            raise ParseError(
                "cannot assign to the result of a call",
                start.line,
                start.column,
            )
        self.expect(TokenType.ASSIGN, "expected '=' after the element")
        value = self.expression()
        node = IndexAssign(
            chain.target,
            chain.index,
            value,
            line=start.line,
            column=start.column,
        )
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

    def _bare(self, kind: type[Stmt]) -> Stmt:
        """A statement that is nothing but its keyword.

        `wake` and `glitch` take no operand -- unlike `jackout`, which
        may carry a value -- so anything after the keyword on the line is
        an error rather than an expression to attach.
        """
        keyword = self.advance()
        node = kind(line=keyword.line, column=keyword.column)
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
            # This branch is only reached when the statement started with
            # IDENT '(' — a call — so an Index here always has a Call
            # somewhere at the base of its chain (e.g. f()[0]). If it's
            # sitting right before '=', the mistake is an assignment to
            # that call result, not a missing statement.
            if isinstance(value, Index) and self.check(TokenType.ASSIGN):
                raise ParseError(
                    "cannot assign to the result of a call",
                    token.line,
                    token.column,
                )
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
        return self._fork()

    # The ladder: each level parses the next-tighter level, then folds a
    # left-associative chain of its own operators. Named levels keep the
    # grammar visible; the shared loop lives once in _binary_level. `_not`
    # sits above the ladder's top rung (_equality) rather than in it: it is
    # unary and right-recursive, not a left-associative binary chain.

    def _fork(self) -> Expr:
        return self._binary_level(_FORK_OPS, self._splice)

    def _splice(self) -> Expr:
        return self._binary_level(_SPLICE_OPS, self._not)

    def _not(self) -> Expr:
        """`unplug`, binding looser than comparison.

        Recurses into itself so `unplug unplug flag` works. Placed above
        _equality rather than at the unary level because `unplug n == 1`
        must mean `unplug (n == 1)`: the tight reading, `(unplug n) == 1`,
        is an error for every possible n.
        """
        if self.check(TokenType.UNPLUG):
            op = self.advance()
            operand = self._not()
            return Unary(op.type, operand, line=op.line, column=op.column)
        return self._equality()

    def _equality(self) -> Expr:
        return self._binary_level(_EQUALITY_OPS, self._comparison)

    def _comparison(self) -> Expr:
        return self._binary_level(_COMPARISON_OPS, self._cleave)

    def _cleave(self) -> Expr:
        return self._binary_level(_CLEAVE_OPS, self._term)

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
        # `decode` and `encode` sit here beside `length` rather than at
        # `_not`'s level, and for the same reason: they PRODUCE values
        # that subsequent operations consume, so `decode jackin + 1` and
        # `encode n + 1` must both be `(op operand) + 1`. `unplug` binds
        # looser because it CONSUMES a boolean that comparison produces.
        # Different operand types, different natural reach -- design doc §3.
        # `keymaker` joins them for the same reason: it PRODUCES a list of
        # keys that later operations consume, so `length keymaker d` and
        # `keymaker alunos[0]` both group tightly.
        # `fold` and `trim` join on the same argument: each produces a
        # string, so `fold a + b` is `(fold a) + b` and `trim a == b` is
        # `(trim a) == b`. The loose reading of either would hand the
        # operator a value it cannot take, for every possible operand.
        if (
            self.check(TokenType.MINUS)
            or self.check(TokenType.LENGTH)
            or self.check(TokenType.DECODE)
            or self.check(TokenType.ENCODE)
            or self.check(TokenType.KEYMAKER)
            or self.check(TokenType.FOLD)
            or self.check(TokenType.TRIM)
        ):
            op = self.advance()
            operand = self._unary()
            return Unary(op.type, operand, line=op.line, column=op.column)
        return self._call()

    def _call(self) -> Expr:
        """Postfix application, so a call or an index binds tighter than
        any operator.

        Loops rather than recurses so `f()()` is a call on a call and
        `xs[0][1]` is an index of an index. Nothing reaches across a
        NEWLINE: the lexer emits one between statements, and `check` sees
        it before it sees a '(' or a '['.
        """
        expr = self._primary()
        while True:
            if self.check(TokenType.LPAREN):
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
            elif self.check(TokenType.LBRACKET):
                bracket = self.advance()
                index = self.expression()
                self.expect(TokenType.RBRACKET, "expected ']' to close the index")
                expr = Index(expr, index, line=bracket.line, column=bracket.column)
            else:
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
        if token.type is TokenType.JACKIN:
            self.advance()
            return JackIn(line=token.line, column=token.column)
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
        if token.type is TokenType.LBRACE:
            self.advance()
            entries: list[tuple[Expr, Expr]] = []
            if not self.check(TokenType.RBRACE):
                while True:
                    key = self.expression()
                    self.expect(TokenType.COLON, "expected ':' after the key")
                    entries.append((key, self.expression()))
                    if not self.check(TokenType.COMMA):
                        break
                    self.advance()
            self.expect(TokenType.RBRACE, "expected '}' to close the dictionary")
            return DictLiteral(entries, line=token.line, column=token.column)
        raise ParseError(
            f"expected an expression, found {_describe(token)}",
            token.line,
            token.column,
        )
