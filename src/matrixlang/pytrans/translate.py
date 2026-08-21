"""Python source in, MatrixLang source out.

Builds real `matrixlang.nodes` objects and renders them with the real
renderer, rather than emitting text. render.py already knows every
precedence rule and where parentheses are needed; a second copy of that
knowledge here is the shape of mistake that produced the deleted
web/interpreter.js. Building nodes also means the output parses by
construction -- it came from the same classes the parser produces.
"""

import ast

from matrixlang.nodes import (
    Assign, Binary, BoolLiteral, Call, Declare, DictLiteral, Expr, ExprStmt,
    FunctionDef, If, Index, IndexAssign, ListLiteral, Name, NumberLiteral,
    Program, Return, Stmt, StringLiteral, Trace, Unary, While,
)
from matrixlang.render import render_ascii
from matrixlang.tokens import TokenType

from matrixlang.pytrans.refuse import Refusal, Refusals, Translated, _Unsupported
from matrixlang.pytrans.names import bound_names, free_name

_BINOP = {
    ast.Add: TokenType.PLUS, ast.Sub: TokenType.MINUS,
    ast.Mult: TokenType.STAR, ast.Div: TokenType.SLASH,
}

_COMPARE = {
    ast.Eq: TokenType.EQ, ast.NotEq: TokenType.NEQ,
    ast.Lt: TokenType.LT, ast.Gt: TokenType.GT,
    ast.LtE: TokenType.LTE, ast.GtE: TokenType.GTE,
}

_NAMED_CALL = {
    "len": TokenType.LENGTH,
    "str": TokenType.ENCODE,
    "int": TokenType.DECODE,
}


def translate(source: str) -> Translated | Refusals:
    """Translate Python to MatrixLang. Never raises."""
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        return Refusals([
            Refusal(
                f"this is not valid Python: {error.msg}",
                error.lineno or 1,
                (error.offset or 1) - 1,
            )
        ])

    walker = _Translator(bound_names(tree))
    statements = walker.body(tree.body)
    if walker.refusals:
        return Refusals(sorted(walker.refusals, key=lambda r: (r.line, r.column)))
    return Translated(render_ascii(Program(statements)))


class _Translator:
    def __init__(self, taken: set[str] | None = None) -> None:
        self.refusals: list[Refusal] = []
        # One set of bound names per MatrixLang scope. An agent body is its
        # own scope, so a name declared inside one does not collide with the
        # same name outside it. `construct` is emitted the first time a name
        # is bound in the current scope and never again -- re-declaring is an
        # error in MatrixLang and Python draws no such distinction.
        self.scopes: list[set[str]] = [set()]
        # Every name the reader's program binds anywhere, seeded up front
        # (see names.py) so a generated counter or holder never collides
        # with one they wrote -- even one bound in a scope this walker
        # hasn't reached yet.
        self.taken: set[str] = set(taken or ())
        # Loop variable -> the expression it stands for (a counter, or an
        # index into a hoisted holder). `for` has no declared variable in
        # the output, so every `ast.Name` read of it is rewritten in place
        # instead. Scoped to the loop's own body: popped before the loop
        # returns, so a name outside it is never rewritten.
        self.substitutions: dict[str, Expr] = {}

    def _fresh(self, stem: str = "n") -> str:
        name = free_name(self.taken, stem)
        self.taken.add(name)
        return name

    def _bind(self, name: str) -> bool:
        """Record a binding. True if this is the first one in this scope."""
        first = name not in self.scopes[-1]
        self.scopes[-1].add(name)
        return first

    def body(self, statements: list[ast.stmt]) -> list[Stmt]:
        """Translate a block, collecting refusals rather than stopping.

        Catching per statement is what makes a thirty-line program take one
        pass to fix instead of five.
        """
        out: list[Stmt] = []
        for node in statements:
            try:
                out.extend(self.statement(node))
            except _Unsupported as stop:
                self.refusals.append(stop.refusal)
        return out

    def statement(self, node: ast.stmt) -> list[Stmt]:
        if isinstance(node, ast.Expr):
            return self._expression_statement(node)
        if isinstance(node, ast.Assign):
            return self._assign(node)
        if isinstance(node, ast.AugAssign):
            return self._aug_assign(node)
        if isinstance(node, ast.If):
            return [
                If(
                    self.condition(node.test),
                    self.body(node.body),
                    self.body(node.orelse) if node.orelse else None,
                )
            ]
        if isinstance(node, ast.While):
            if node.orelse:
                raise _Unsupported(self._no(node, "MatrixLang has no `while ... else`"))
            return [While(self.condition(node.test), self.body(node.body))]
        if isinstance(node, ast.For):
            return self._for(node)
        if isinstance(node, ast.FunctionDef):
            # A `def` nested inside another `def` falls out of this
            # recursion for free and happens to work, but neither the brief
            # nor the spec says anything about it -- noted as untested
            # territory, not overlooked.
            return self._function(node)
        if isinstance(node, ast.Return):
            return [Return(self.expression(node.value) if node.value else None)]
        raise _Unsupported(self._no(self._culprit(node)))

    def _expression_statement(self, node: ast.Expr) -> list[Stmt]:
        call = node.value
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute):
            if call.func.attr != "append" or len(call.args) != 1:
                # Built via Refusal directly, not self._no(): the reason
                # needs to name the method (`.sort()`), and self._no's
                # reason is always "<ast class name> cannot be translated" --
                # here that would say "Expr", naming neither the method nor
                # the fact that it's a method at all.
                raise _Unsupported(
                    Refusal(
                        f"MatrixLang has no `.{call.func.attr}()` method",
                        node.lineno,
                        node.col_offset,
                        "the only list method it can translate is `.append()`",
                    )
                )
            if not isinstance(call.func.value, ast.Name):
                raise _Unsupported(self._no(node))
            # Concatenation, not mutation: `+` copies, which is what makes
            # this an assignment rather than a call.
            target = call.func.value.id
            return [
                Assign(
                    target,
                    Binary(
                        Name(target), TokenType.PLUS,
                        ListLiteral([self.expression(call.args[0])]),
                    ),
                )
            ]
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
            if call.func.id == "print":
                if len(call.args) != 1 or call.keywords:
                    raise _Unsupported(
                        self._no(
                            node,
                            'print one value at a time: `print(a)` then `print(b)`, '
                            'or join them with `+`',
                        )
                    )
                return [Trace(self.expression(call.args[0]))]
            return [ExprStmt(self.expression(call))]
        raise _Unsupported(
            self._no(
                node,
                "MatrixLang runs a statement only when it is a call — "
                "assign the value to a name if you meant to keep it",
            )
        )

    def _assign(self, node: ast.Assign) -> list[Stmt]:
        if len(node.targets) != 1:
            raise _Unsupported(
                self._no(node, "assign one name at a time: `a = 0` then `b = 0`")
            )
        target = node.targets[0]
        value = self.expression(node.value)
        if isinstance(target, ast.Name):
            if self._bind(target.id):
                return [Declare(target.id, value)]
            return [Assign(target.id, value)]
        if isinstance(target, ast.Subscript):
            if isinstance(target.slice, ast.Slice):
                raise _Unsupported(self._no(target))
            return [
                IndexAssign(
                    self.expression(target.value),
                    self.expression(target.slice),
                    value,
                )
            ]
        raise _Unsupported(
            self._no(target, "assign to one name or one element at a time")
        )

    def _aug_assign(self, node: ast.AugAssign) -> list[Stmt]:
        op = _BINOP.get(type(node.op))
        if op is None or not isinstance(node.target, ast.Name):
            raise _Unsupported(self._no(node))
        if node.target.id not in self.scopes[-1]:
            raise _Unsupported(
                self._no(
                    node,
                    f"give `{node.target.id}` a value before changing it",
                )
            )
        return [
            Assign(
                node.target.id,
                Binary(Name(node.target.id), op, self.expression(node.value)),
            )
        ]

    def _for(self, node: ast.For) -> list[Stmt]:
        if node.orelse:
            raise _Unsupported(self._no(node, "MatrixLang has no `for ... else`"))
        if not isinstance(node.target, ast.Name):
            raise _Unsupported(
                self._no(node.target, "loop over one name at a time")
            )
        if _rebinds(node.body, node.target.id):
            # Built via Refusal directly, not self._no(): self._no's reason
            # is always "<ast class name> cannot be translated" -- here
            # that would say "For cannot be translated", never naming the
            # loop variable the test (and the reader) needs to see.
            raise _Unsupported(
                Refusal(
                    f"the loop reassigns `{node.target.id}`; copy it to another "
                    "name first",
                    node.lineno,
                    node.col_offset,
                )
            )

        before: list[Stmt] = []
        counter = self._fresh()

        start, stop = self._range_bounds(node.iter)
        if stop is not None:
            # `for i in range(...)`: the counter IS the value.
            self.substitutions[node.target.id] = Name(counter)
            before.append(Declare(counter, start))
            condition = Binary(Name(counter), TokenType.LT, stop)
        else:
            source = node.iter
            if isinstance(source, ast.Name):
                holder = source.id
            else:
                # Evaluated once. Substituting a call inline would run it
                # on every iteration -- a different program.
                holder = self._fresh("xs")
                before.append(Declare(holder, self.expression(source)))
            self.substitutions[node.target.id] = Index(Name(holder), Name(counter))
            before.append(Declare(counter, NumberLiteral(0)))
            condition = Binary(
                Name(counter), TokenType.LT, Unary(TokenType.LENGTH, Name(holder))
            )

        body = self.body(node.body)
        # Any `construct` left ANYWHERE inside the loop body fails on the
        # second iteration -- not only a name the reader first binds at the
        # body's top level, but one bound inside an `if`, or inside a
        # nested `while`, because "inside the loop body" doesn't stop at
        # the first nesting level. This also catches a nested `for`'s own
        # counter/holder Declare, which a recursive `for` call already
        # hoisted to just above itself -- that Declare now sits at THIS
        # body's top level (a `for` returns its `before` declarations and
        # its `While` flattened together), so it is hoisted again, one
        # level further out, same as anything else found here. See
        # _hoist_declares for what the walk does and does not reach.
        body, hoisted = _hoist_declares(body)
        before.extend(hoisted)

        del self.substitutions[node.target.id]
        body.append(
            Assign(counter, Binary(Name(counter), TokenType.PLUS, NumberLiteral(1)))
        )
        return before + [While(condition, body)]

    def _range_bounds(self, node: ast.expr) -> tuple[Expr, Expr | None]:
        """(start, stop) for a `range(...)` iterable, or (0, None) otherwise."""
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "range"
        ):
            return NumberLiteral(0), None
        if len(node.args) == 1:
            return NumberLiteral(0), self.expression(node.args[0])
        if len(node.args) == 2:
            return self.expression(node.args[0]), self.expression(node.args[1])
        raise _Unsupported(
            self._no(node, "count with a `dejavu` loop and your own step")
        )

    def condition(self, node: ast.expr) -> Expr:
        """A condition, refusing anything that leans on truthiness.

        MatrixLang's `redpill` takes a boolean and nothing else -- an empty
        list is not false, and 0 is not false. Python's `if xs:` means four
        different things depending on a runtime type, and choosing between
        them would mean inferring that type and sometimes guessing wrong.
        A program that runs and means something slightly different is the
        one outcome worth engineering against, so this refuses instead.
        """
        if isinstance(node, ast.Compare):
            # Admitted wholesale: a comparison's operands are values being
            # compared (`a == len(xs)`), not conditions, so they don't get
            # re-checked here.
            return self.expression(node)
        if isinstance(node, ast.BoolOp):
            # Admitting the wrapper must not admit its operands -- each one
            # is itself a condition (`a == 1 or y` must refuse on `y`), so
            # each recurses through condition(), not expression().
            op = TokenType.SPLICE if isinstance(node.op, ast.And) else TokenType.FORK
            result = self.condition(node.values[0])
            for value in node.values[1:]:
                result = Binary(result, op, self.condition(value))
            return result
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return Unary(TokenType.UNPLUG, self.condition(node.operand))
        if isinstance(node, ast.Constant) and node.value in (True, False):
            return self.expression(node)
        shown = ast.unparse(node)
        raise _Unsupported(
            Refusal(
                f"`{shown}` relies on truthiness, which MatrixLang does not "
                "have — a condition must already be a boolean",
                node.lineno,
                node.col_offset,
                f"a list or string →  len({shown}) > 0\n"
                f"a number        →  {shown} != 0",
            )
        )

    def _function(self, node: ast.FunctionDef) -> list[Stmt]:
        args = node.args
        if (
            args.defaults or args.kw_defaults or args.vararg or args.kwarg
            or args.posonlyargs or args.kwonlyargs
        ):
            raise _Unsupported(
                self._no(node, "MatrixLang agents take plain positional parameters")
            )
        if node.decorator_list:
            raise _Unsupported(self._no(node, "MatrixLang has no decorators"))
        names = [a.arg for a in args.args]
        # An agent body is its own frame, so it gets its own scope, seeded
        # with the parameters -- they are bound on entry and must not be
        # re-declared inside.
        self.scopes.append(set(names))
        body = self.body(node.body)
        self.scopes.pop()
        self._bind(node.name)
        return [FunctionDef(node.name, names, body)]

    def expression(self, node: ast.expr) -> Expr:
        if isinstance(node, ast.Constant):
            return self._constant(node)
        if isinstance(node, ast.Name):
            replacement = self.substitutions.get(node.id)
            if replacement is not None:
                # Shared, not copied: rendering never mutates a node, and
                # line/column do not take part in equality.
                return replacement
            return Name(node.id)
        if isinstance(node, ast.BinOp):
            op = _BINOP.get(type(node.op))
            if op is None:
                raise _Unsupported(self._no(node.op))
            return Binary(self.expression(node.left), op, self.expression(node.right))
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.USub):
                return Unary(TokenType.MINUS, self.expression(node.operand))
            if isinstance(node.op, ast.Not):
                return Unary(TokenType.UNPLUG, self.expression(node.operand))
            raise _Unsupported(self._no(node.op))
        if isinstance(node, ast.BoolOp):
            op = TokenType.SPLICE if isinstance(node.op, ast.And) else TokenType.FORK
            result = self.expression(node.values[0])
            for value in node.values[1:]:
                result = Binary(result, op, self.expression(value))
            return result
        if isinstance(node, ast.Compare):
            return self._compare(node)
        if isinstance(node, ast.List):
            return ListLiteral([self.expression(e) for e in node.elts])
        if isinstance(node, ast.Dict):
            return self._dict(node)
        if isinstance(node, ast.Subscript):
            if not isinstance(node.slice, ast.expr) or isinstance(node.slice, ast.Slice):
                raise _Unsupported(
                    self._no(node, "MatrixLang has no slicing; copy with a `dejavu` loop")
                )
            return Index(self.expression(node.value), self.expression(node.slice))
        if isinstance(node, ast.Call):
            return self._call(node)
        raise _Unsupported(self._no(node))

    def _constant(self, node: ast.Constant) -> Expr:
        # None and float go through Refusal directly rather than self._no():
        # both share the ast class "Constant" with every other literal, so
        # the name-keyed _DESCRIBE catalogue can't tell them apart, and a
        # reason of "Constant cannot be translated" would name neither.
        value = node.value
        if value is True or value is False:
            return BoolLiteral(value)
        if value is None:
            raise _Unsupported(
                Refusal(
                    "None cannot be translated",
                    node.lineno,
                    node.col_offset,
                    "MatrixLang has no null; use a value your program can test",
                )
            )
        if isinstance(value, float):
            raise _Unsupported(
                Refusal(
                    "a float cannot be translated",
                    node.lineno,
                    node.col_offset,
                    "MatrixLang has no floats; use whole numbers",
                )
            )
        if isinstance(value, int):
            return NumberLiteral(value)
        if isinstance(value, str):
            return StringLiteral(value)
        raise _Unsupported(self._no(node))

    def _compare(self, node: ast.Compare) -> Expr:
        if len(node.ops) != 1:
            raise _Unsupported(
                self._no(node, "split the chain with `and`")
            )
        op, right = node.ops[0], node.comparators[0]
        if isinstance(op, ast.In):
            # Only a dictionary. `in` over a list or a string has no
            # MatrixLang form -- oracle asks a dictionary for a key.
            return Binary(
                self.expression(right), TokenType.ORACLE, self.expression(node.left)
            )
        mapped = _COMPARE.get(type(op))
        if mapped is None:
            raise _Unsupported(self._no(op))
        return Binary(self.expression(node.left), mapped, self.expression(right))

    def _dict(self, node: ast.Dict) -> Expr:
        entries = []
        for key, value in zip(node.keys, node.values):
            if key is None:
                raise _Unsupported(self._no(node))
            entries.append((self.expression(key), self.expression(value)))
        return DictLiteral(entries)

    def _call(self, node: ast.Call) -> Expr:
        if node.keywords:
            raise _Unsupported(
                self._no(node, "MatrixLang agents take positional arguments only")
            )
        if isinstance(node.func, ast.Name) and node.func.id in _NAMED_CALL:
            if len(node.args) != 1:
                raise _Unsupported(self._no(node))
            return Unary(_NAMED_CALL[node.func.id], self.expression(node.args[0]))
        if not isinstance(node.func, ast.Name):
            raise _Unsupported(self._no(node))
        return Call(Name(node.func.id), [self.expression(a) for a in node.args])

    def _culprit(self, node: ast.stmt) -> ast.AST:
        """The construct actually responsible for the refusal.

        Scoped to the statement's own value expression -- `Assign`, `Expr`,
        `Return` -- never to the whole subtree. A statement kind that is
        itself unsupported (`class`, `try`, `raise`, `import`) must report
        itself, because it refuses no matter what's nested inside it;
        walking the full subtree would let a `class` body's comprehension
        steal the refusal from the `class`, and a reader who "fixes" the
        comprehension would rerun and get a different refusal for the same
        still-unsupported statement. `xs = [f(x) for x in ys]` still names
        the comprehension, because there the comprehension genuinely *is*
        what the statement is built from (and once translation exists, this
        is also where that expression would be found).
        """
        value = None
        if isinstance(node, (ast.Assign, ast.Expr, ast.Return)):
            value = node.value
        if value is None:
            return node
        for child in ast.walk(value):
            if type(child).__name__ in _IDIOM:
                return child
        return node

    def _no(self, node: ast.AST, idiom: str | None = None) -> Refusal:
        name = type(node).__name__
        return Refusal(
            f"{_DESCRIBE.get(name, name)} cannot be translated",
            getattr(node, "lineno", 1),
            getattr(node, "col_offset", 0),
            idiom if idiom is not None else _IDIOM.get(name),
        )


def _rebinds(body: list[ast.stmt], name: str) -> bool:
    """Does this block assign to `name`? Substitution cannot express that."""
    for node in ast.walk(ast.Module(body=body, type_ignores=[])):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            if node.id == name:
                return True
        if isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name):
            if node.target.id == name:
                return True
    return False


def _as_assignment(statement: Stmt) -> Stmt:
    """A Declare becomes an Assign; everything else is unchanged.

    Paired with hoisting the Declare above the loop -- together they turn
    a first binding inside a loop body into a declaration outside it and a
    plain assignment inside, which is the only shape MatrixLang accepts.
    """
    if isinstance(statement, Declare):
        return Assign(statement.name, statement.value)
    return statement


def _hoist_declares(body: list[Stmt]) -> tuple[list[Stmt], list[Declare]]:
    """Rewrite every `Declare` anywhere in `body` to a plain `Assign` in
    place, and return placeholder declarations (each initialised to `0`)
    to hoist above the enclosing loop.

    Recurses into `If.then_body`/`If.else_body` and `While.body`: a name
    first bound inside a nested `if`, or inside a Python `while` nested in
    the loop body, is still bound "inside the loop body" for rule (c)'s
    purposes -- MatrixLang's `construct` fails on the second pass through
    a `dejavu` no matter how many branches deep it sits, and conditional
    accumulation (`if cond: total = ...`) is one of the most common shapes
    a `for` loop takes.

    Deliberately does NOT recurse into a `FunctionDef` body. A nested
    agent's body is its own MatrixLang scope (see `_function`), re-entered
    fresh on every call rather than replayed on every pass through this
    `dejavu` -- so a `construct` inside it never hits the same-scope-twice
    quirk this hoist exists to dodge, and hoisting it out would be wrong,
    not just unnecessary.

    Order is the statements' own order: a pre-order, left-to-right walk
    (an `If`'s `then_body` fully before its `else_body`), so the hoisted
    declarations appear above the loop in the same order the reader's
    names first appear in it -- deterministic without needing a sort.
    """
    hoisted: list[Declare] = []

    def walk(statements: list[Stmt]) -> list[Stmt]:
        out: list[Stmt] = []
        for statement in statements:
            if isinstance(statement, Declare):
                hoisted.append(Declare(statement.name, NumberLiteral(0)))
                out.append(_as_assignment(statement))
            elif isinstance(statement, If):
                statement.then_body = walk(statement.then_body)
                if statement.else_body is not None:
                    statement.else_body = walk(statement.else_body)
                out.append(statement)
            elif isinstance(statement, While):
                statement.body = walk(statement.body)
                out.append(statement)
            else:
                out.append(statement)
        return out

    return walk(body), hoisted


# What a reader calls each construct, keyed by its ast class name. Without
# this a refusal says "ImportFrom", which is Python's word, not theirs.
_DESCRIBE = {
    "Import": "`import`",
    "ImportFrom": "`import`",
    "ClassDef": "`class`",
    "Try": "`try`",
    "Raise": "`raise`",
    "Lambda": "`lambda`",
    "ListComp": "a list comprehension",
    "SetComp": "a set comprehension",
    "DictComp": "a dict comprehension",
    "GeneratorExp": "a generator expression",
    "Tuple": "a tuple",
    "Set": "a set",
    "Slice": "a slice",
    "Is": "`is`",
    "IsNot": "`is not`",
    "In": "`in`",
    "NotIn": "`not in`",
    # Not in the brief's list: the ast.Compare node itself is the culprit
    # when a comparison chains more than one operator (`a < b < c`), and
    # without an entry here the reason falls back to the literal ast class
    # name "Compare", which the chained-comparison test can't match on.
    "Compare": "a chained comparison",
}

_IDIOM = {
    "ListComp": "build the list with a `dejavu` loop and `xs = xs + [v]`",
    "SetComp": "MatrixLang has no sets; use a list",
    "DictComp": "build the dictionary with a `dejavu` loop and `d[k] = v`",
    "GeneratorExp": "build the list with a `dejavu` loop",
    "Tuple": "MatrixLang has no tuples; use a list",
    "Set": "MatrixLang has no sets; use a list",
    "Slice": "MatrixLang has no slicing; copy with a `dejavu` loop",
    "Is": "MatrixLang has no identity check; compare values with `==`",
    "IsNot": "MatrixLang has no identity check; compare values with `!=`",
    "In": "MatrixLang's `in` only reads a dictionary; write `d oracle key`",
    "NotIn": "MatrixLang has no `not in`; write `unplug (d oracle key)`",
}
