"""Python source in, MatrixLang source out.

Builds real `matrixlang.nodes` objects and renders them with the real
renderer, rather than emitting text. render.py already knows every
precedence rule and where parentheses are needed; a second copy of that
knowledge here is the shape of mistake that produced the deleted
web/interpreter.js. Building nodes also means the output parses by
construction -- it came from the same classes the parser produces.
"""

import ast

from matrixlang.errors import TooDeepError, recursion_guard
from matrixlang.nodes import (
    Assign, Binary, BoolLiteral, Call, Declare, DictLiteral, Expr, ExprStmt,
    FunctionDef, Glitch, If, Index, IndexAssign, JackIn, ListLiteral, Name,
    NumberLiteral, Program, Return, Stmt, StringLiteral, Trace, Unary, Wake,
    While,
)
from matrixlang.render import render_ascii
from matrixlang.tokens import TokenType

from matrixlang.pytrans.refuse import Refusal, Refusals, Translated, _Unsupported
from matrixlang.pytrans.names import bound_names, free_name

# Deliberately no division. MatrixLang's `/` truncates toward zero
# (interpreter.py's _arithmetic), which is neither of Python's two
# divisions: `/` produces a fraction MatrixLang has no value for, and `//`
# floors, which differs from truncation on negative operands (-7 // 2 is
# -4 in Python, -7 / 2 is -3 here). Which of the two a given `a // b`
# agrees with depends on the SIGN of values that do not exist yet at
# translation time -- the same "the translator cannot know the runtime
# value, so it must not guess" argument that refuses truthiness. Both are
# refused; see _DESCRIBE/_IDIOM for what the reader is told.
_BINOP = {
    ast.Add: TokenType.PLUS, ast.Sub: TokenType.MINUS,
    ast.Mult: TokenType.STAR,
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

# Python string methods that have a MatrixLang operator. Kept separate
# from _NAMED_CALL because these arrive as `receiver.method()` rather than
# `name(argument)` -- MatrixLang has no attribute access at all, which is
# why the translator has to special-case each one it can reach.
_STRING_UNARY = {
    "lower": TokenType.FOLD,
    "strip": TokenType.TRIM,
}

# Shared between the value-position refusal (_call) and the
# statement-position one (_expression_statement): `.upper()` is not
# translatable either way, and the reason it isn't does not depend on
# which position it sits in, so there is exactly one place to word it.
_UPPER_REASON = (
    "`.upper()` cannot be translated — MatrixLang has no upper-casing "
    "operator"
)
_UPPER_IDIOM = (
    "to compare ignoring case, use `.lower()` on both sides; to display "
    "in capitals there is no MatrixLang form yet"
)


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
    except ValueError as error:
        # ast.parse() encodes `source` to UTF-8 before parsing it, and an
        # unpaired surrogate fails that step as a UnicodeEncodeError -- a
        # ValueError subclass, not a SyntaxError, so the clause above never
        # catches it. Not a contrived input: it is exactly what a JS string
        # with an unpaired surrogate becomes crossing into Python under
        # Pyodide, and a plain browser <textarea> can hold one. Unlike a
        # SyntaxError, it carries no .lineno/.offset -- only a character
        # index into `source` -- so the position is derived rather than
        # read straight off the exception, the way error.offset is above.
        return Refusals([Refusal(str(error), *_position(source, getattr(error, "start", 0)))])

    walker = _Translator(bound_names(tree))
    statements = walker.body(tree.body)
    if walker.refusals:
        return Refusals(sorted(walker.refusals, key=lambda r: (r.line, r.column)))
    try:
        # A second guard, not a redundant one: body()'s per-statement guard
        # protects the WALK (turning Python's AST into MatrixLang nodes),
        # but rendering the result is a separate recursive descent over the
        # same tree (render.py's mutual _emit/_expression), done once for
        # the whole program rather than per statement -- and empirically
        # (500 terms of `1 + 1 + ...`, the reproduction this guards) it is
        # the one that actually exhausts the stack, not the walk. There is
        # no single statement to blame once every statement has already
        # walked clean, so unlike body()'s guard this can only report the
        # program as a whole, at (1, 1) -- the same honest-about-having-no-
        # position choice TooDeepError itself documents (errors.py).
        with recursion_guard():
            source_out = render_ascii(Program(statements))
    except TooDeepError:
        return Refusals([Refusal("this is nested too deeply to translate", 1, 1)])
    return Translated(source_out)


def _position(source: str, index: int) -> tuple[int, int]:
    """1-based line, 0-based column for a character offset into `source`.

    Mirrors how error.offset is read for a SyntaxError above -- that value
    is already 1-based, hence the `- 1` there and not here.
    """
    index = max(0, min(index, len(source)))
    line = source.count("\n", 0, index) + 1
    column = index - source.rfind("\n", 0, index) - 1
    return line, column


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
        # Every zero-initialised `Declare` the hoist itself invented, keyed
        # by identity (the dict's values are only there to keep the nodes
        # alive, so an id() can never be reused under us). Hoists nest --
        # an `if` inside a `for` hoists first, then the loop hoists what
        # the `if` left behind -- and a placeholder met a second time must
        # be moved rather than rewritten. See _hoist_declares.
        self.placeholders: dict[int, Declare] = {}

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
        pass to fix instead of five -- and it is why a recursion guard sits
        here too, rather than only once around the whole walk in
        translate(). Deep Python source (a long flat expression chain has no
        syntax-level depth cap the way indentation and parens do -- see the
        pytrans.translate entry in test_architecture.py) can exhaust the
        stack while translating a single statement into nodes; catching it
        here, per statement, means it unwinds no further than the statement
        that caused it, so refusals already collected for earlier statements
        -- and translation of the ones after it -- both survive. In practice
        the walk tends to survive depths that later defeat render_ascii's
        own recursive descent over the resulting tree, which is why
        translate() carries a second, whole-program guard around that call
        too; this one stays regardless, both as a real second line of
        defence and because which recursive descent a given input happens
        to exhaust first is an implementation detail, not something a
        caller should have to rely on. recursion_guard() is the same
        conversion glue.run() already applies around its own parse, for the
        same underlying hazard (see site/glue.py); TooDeepError carries no
        position of its own by design (errors.py), so one is supplied here
        from the statement's own node, the same as _Unsupported's already
        is.
        """
        out: list[Stmt] = []
        for node in statements:
            try:
                with recursion_guard():
                    out.extend(self.statement(node))
            except _Unsupported as stop:
                self.refusals.append(stop.refusal)
            except TooDeepError:
                self.refusals.append(
                    Refusal(
                        "this is nested too deeply to translate",
                        node.lineno, node.col_offset,
                    )
                )
        return out

    def statement(self, node: ast.stmt) -> list[Stmt]:
        if isinstance(node, ast.Expr):
            return self._expression_statement(node)
        if isinstance(node, ast.Assign):
            return self._assign(node)
        if isinstance(node, ast.AugAssign):
            return self._aug_assign(node)
        if isinstance(node, ast.If):
            # The branch variant of the same hazard the loops hoist around.
            # `construct` is a runtime statement that only runs on the
            # branch taken, but bindings are recorded in one flat set per
            # scope, so the SECOND branch to bind a name was treated as
            # already declared and emitted a bare assignment -- and plain
            # `if x > 0: s = 1` / `else: s = 0` died with "'s' is not
            # declared" whichever way it went. Hoisting is correct here for
            # the same reason it is correct for a loop: interpreter.py's If
            # opens no scope, so a `construct` above the `redpill` declares
            # the same name the branches assign. It also fixes a name bound
            # in a branch and reassigned after the `if`, which had the same
            # cause. Where the Python would have raised NameError -- `if c:
            # s = 1` with `c` false, then reading `s` -- the reader gets the
            # placeholder `0` instead of an error; that is the same trade
            # the loop hoist has always made, on Python that is already
            # broken.
            condition = self.condition(node.test)
            then_body, hoisted = _hoist_declares(self.body(node.body), self.placeholders)
            else_body = None
            if node.orelse:
                else_body, from_else = _hoist_declares(
                    self.body(node.orelse), self.placeholders
                )
                hoisted.extend(from_else)
            return [*hoisted, If(condition, then_body, else_body)]
        if isinstance(node, ast.While):
            if node.orelse:
                raise _Unsupported(self._no(node, "MatrixLang has no `while ... else`"))
            _refuse_function_in_loop(node.body)
            condition = self.condition(node.test)
            # Same hazard `_for` hoists around: `construct` inside a
            # `dejavu` body fails on the second iteration, and a plain
            # Python `while` lands its first-bound names in exactly that
            # body just like a `for`'s translated body does. `_for` gets
            # this by construction (it always runs `_hoist_declares` on
            # its own body); a `while` needs the same call explicitly,
            # because `_hoist_declares`'s recursion into a nested `While`
            # only reaches a `while` sitting *inside* another loop's
            # body -- a top-level `while` is never visited by anyone
            # else's walk.
            body, hoisted = _hoist_declares(self.body(node.body), self.placeholders)
            return [*hoisted, While(condition, body)]
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
        if isinstance(node, ast.Break):
            return [Wake()]
        if isinstance(node, ast.Continue):
            return [Glitch()]
        # An unsupported STATEMENT reports itself, never something nested
        # inside it. `class`, `try`, `raise` and `import` refuse whatever
        # they contain, so letting a `class` body's comprehension steal the
        # refusal would send the reader off to rewrite working code and
        # then hand them a different refusal for the same still-unsupported
        # statement. (This used to route through a _culprit() helper that
        # searched the statement's own value expression -- dead code by the
        # time it was found, because Assign, Expr and Return are all
        # intercepted above and nothing else reaching here has a `.value`.
        # `xs = [f(x) for x in ys]` still names the comprehension, from
        # _assign's own walk into the expression; the one place the search
        # was genuinely doing work is spelled out in _expression_statement.)
        raise _Unsupported(self._no(node))

    def _expression_statement(self, node: ast.Expr) -> list[Stmt]:
        call = node.value
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute):
            attr = call.func.attr
            if attr == "upper":
                # Same refusal as the value position: `.upper()` is not
                # translatable there either, and for the same reason --
                # position doesn't change what's wrong with it.
                raise _Unsupported(self._because(node, _UPPER_REASON, _UPPER_IDIOM))
            if attr in _STRING_UNARY or attr == "split":
                # This branch made `.lower()`, `.strip()` and `.split()`
                # translatable as VALUES, so the blanket "MatrixLang has
                # no `.{attr}()` method" below is now false for them --
                # they have one, it just doesn't mutate. The mistake this
                # catches is real: `name.strip()` on its own line reads,
                # to someone coming from a mutating-method language, as
                # "strip name in place". It doesn't in Python either.
                noun = "list" if attr == "split" else "string"
                raise _Unsupported(
                    self._because(
                        node,
                        f"`.{attr}()` gives back a NEW {noun} and changes "
                        "nothing",
                        "MatrixLang is the same — put the result "
                        f"somewhere: `s = s.{attr}(...)`",
                    )
                )
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
                raise _Unsupported(
                    self._because(
                        node,
                        "`.append()` needs a plain name to append to",
                        "put the list in its own name first, then append to it",
                    )
                )
            # Through expression(), not `.id` off the ast: inside a `for`
            # body the receiver is very often the loop variable, which has
            # no name in the output at all -- it is substituted (rule 2).
            # Read straight off the ast, `for r in rs: r.append(9)` emitted
            # `r = r + [9]`, which assigns to whatever OUTER `r` happens to
            # exist and leaves `rs` untouched: it ran clean and gave a
            # different answer from the Python. Substituted, the same line
            # becomes `rs[n] = rs[n] + [9]`, which is what Python's
            # in-place append means for the element being visited.
            receiver = self.expression(call.func.value)
            # Concatenation, not mutation: `+` copies, which is what makes
            # this an assignment rather than a call.
            appended = Binary(
                receiver, TokenType.PLUS,
                ListLiteral([self.expression(call.args[0])]),
            )
            if isinstance(receiver, Name):
                return [Assign(receiver.ident, appended)]
            if isinstance(receiver, Index):
                return [IndexAssign(receiver.target, receiver.index, appended)]
            raise _Unsupported(
                self._because(node, "there is nothing here to append to")
            )
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
            if call.func.id == "print":
                if len(call.args) != 1 or call.keywords:
                    raise _Unsupported(
                        self._because(
                            node,
                            "`trace` prints exactly one value",
                            "print one value at a time: `print(a)` then `print(b)`, "
                            "or join them with `+`",
                        )
                    )
                return [Trace(self.expression(call.args[0]))]
            return [ExprStmt(self.expression(call))]
        # The one surviving job of the deleted _culprit(): an expression
        # statement built out of something the catalogue can name --
        # `yield 1`, `(y := 1)`, `o.attr` -- reports THAT rather than the
        # generic "not a call", because naming it is what tells the reader
        # which part to change. Anything else (`1 + 1`) genuinely has no
        # culprit smaller than the statement.
        if type(node.value).__name__ in _DESCRIBE:
            raise _Unsupported(self._no(node.value, at=node))
        raise _Unsupported(
            self._because(
                node,
                "a statement on its own line has to be a call",
                "MatrixLang runs a statement only when it is a call — "
                "assign the value to a name if you meant to keep it",
            )
        )

    def _assign(self, node: ast.Assign) -> list[Stmt]:
        if len(node.targets) != 1:
            raise _Unsupported(
                self._because(
                    node,
                    "assigning several names at once cannot be translated",
                    "assign one name at a time: `a = 0` then `b = 0`",
                )
            )
        target = node.targets[0]
        prelude: list[Stmt] = []
        source = node.value
        if _is_input_call(source):
            if source.args:
                if len(source.args) != 1:
                    raise _Unsupported(
                        self._because(
                            source,
                            "`input` takes at most one prompt",
                            "join the parts with `+`: `input(a + b)`",
                        )
                    )
                prelude.append(Trace(self.expression(source.args[0])))
            value: Expr = JackIn()
        else:
            value = self.expression(source)
        if isinstance(target, ast.Name):
            if self._bind(target.id):
                return prelude + [Declare(target.id, value)]
            return prelude + [Assign(target.id, value)]
        if isinstance(target, ast.Subscript):
            if isinstance(target.slice, ast.Slice):
                raise _Unsupported(self._no(target.slice, at=target))
            return prelude + [
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
        if op is None:
            raise _Unsupported(self._no(node.op, at=node))
        if not isinstance(node.target, ast.Name):
            raise _Unsupported(
                self._because(
                    node,
                    "`+=` only changes a name, not an element",
                    "write it out: `xs[0] = xs[0] + 1`",
                )
            )
        if node.target.id not in self.scopes[-1]:
            raise _Unsupported(
                self._because(
                    node,
                    f"`{node.target.id}` has no value yet",
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
        if node.target.id in self.scopes[-1]:
            # Python's `for` BINDS its variable in the enclosing scope, and
            # leaves it there afterwards holding the last element. The
            # output has no such name -- rule 2 substitutes every use
            # inside the body and declares nothing -- so a read after the
            # loop gets whatever the name held BEFORE it. When the name is
            # new that read fails loudly ("'x' is not declared"), which the
            # governing rule allows; when the reader already had an `x`, it
            # quietly returns the old value instead. `x = 5` then
            # `for x in [1, 2, 3]` then `print(x)` gave 5 where Python
            # gives 3, so the collision is refused rather than the read.
            raise _Unsupported(
                Refusal(
                    f"the loop variable `{node.target.id}` is already a name in "
                    "this program",
                    node.target.lineno,
                    node.target.col_offset,
                    "a `for` variable has no name of its own in MatrixLang — "
                    "give the loop a different one",
                )
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
        _refuse_function_in_loop(node.body)

        before: list[Stmt] = []
        counter = self._fresh()

        start, stop = self._range_bounds(node.iter)
        if stop is not None:
            # `for i in range(...)`: the counter IS the value.
            self.substitutions[node.target.id] = Name(counter)
            before.append(Declare(counter, start))
            if not isinstance(stop, NumberLiteral):
                # Evaluated once, for the same reason a non-name iterable
                # is hoisted below: Python builds the range object at loop
                # ENTRY, so `for i in range(n)` with a body that changes
                # `n` still runs the original number of times. Inlined into
                # the `dejavu` condition, `n` was re-read every iteration
                # -- `n = 5` counting down inside the body printed 0 1 2
                # instead of 0 1 2 3 4, with nothing to show for it. A
                # literal bound is left inline: it cannot change, and
                # `dejavu n < 3` is what the reader expects to see.
                limit = self._fresh("stop")
                before.append(Declare(limit, stop))
                stop = Name(limit)
            condition = Binary(Name(counter), TokenType.LT, stop)
        else:
            # Through expression(), not `.id` off the ast: the iterable of a
            # NESTED `for` is very often the outer loop's variable, which has
            # no name in the output at all (it is substituted, rule 2). Read
            # straight off the ast, `for v in row:` emitted `length row` for
            # a `row` that was never declared, and the most ordinary nested
            # loop there is died with "'row' is not declared".
            value = self.expression(node.iter)
            if isinstance(value, Name):
                holder = value.ident
                if _rebinds(node.body, holder):
                    # The list path's counterpart to hoisting a `range`
                    # bound, and it has to be a refusal rather than a hoist.
                    # Python's `for` holds the LIST OBJECT it was given, so
                    # rebinding the name inside the body changes nothing;
                    # indexing the name, as the output does, follows the
                    # rebinding and walks a different list from the next
                    # iteration on. Hoisting `xs` into a generated holder
                    # would fix that shape and break another -- `xs` growing
                    # by `xs.append(v)` inside its own loop runs forever in
                    # Python, and the holder would quietly make it finish.
                    # There is no output that is right for both, so this one
                    # is named and refused.
                    raise _Unsupported(
                        Refusal(
                            f"the loop reassigns `{holder}`, the list it walks; "
                            "copy it to another name first",
                            node.iter.lineno,
                            node.iter.col_offset,
                        )
                    )
            else:
                # Evaluated once. Substituting a call inline would run it
                # on every iteration -- a different program.
                holder = self._fresh("xs")
                before.append(Declare(holder, value))
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
        body, hoisted = _hoist_declares(body, self.placeholders)
        before.extend(hoisted)

        del self.substitutions[node.target.id]
        body = _increment_before_glitches(body, counter)
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
            self._because(
                node,
                "`range` with a step cannot be translated",
                "count with a `dejavu` loop and your own step",
            )
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
                raise _Unsupported(self._no(node.op, at=node))
            return Binary(self.expression(node.left), op, self.expression(node.right))
        if isinstance(node, ast.UnaryOp):
            if isinstance(node.op, ast.USub):
                return Unary(TokenType.MINUS, self.expression(node.operand))
            if isinstance(node.op, ast.Not):
                return Unary(TokenType.UNPLUG, self.expression(node.operand))
            raise _Unsupported(self._no(node.op, at=node))
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
        if isinstance(node, ast.JoinedStr):
            return self._fstring(node)
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
        if isinstance(value, complex):
            raise _Unsupported(
                self._because(
                    node,
                    "a complex number cannot be translated",
                    "MatrixLang has only whole numbers",
                )
            )
        if isinstance(value, bytes):
            raise _Unsupported(
                self._because(
                    node,
                    "a bytes literal cannot be translated",
                    "MatrixLang has only text strings",
                )
            )
        raise _Unsupported(self._because(node, "this literal cannot be translated"))

    def _compare(self, node: ast.Compare) -> Expr:
        if len(node.ops) != 1:
            raise _Unsupported(
                self._no(node, "split the chain with `and`")
            )
        op, right = node.ops[0], node.comparators[0]
        if isinstance(op, ast.In):
            # Unconditional: `k in d`, `2 in xs` and `"a" in s` are the same
            # syntax, and telling them apart would be the type inference
            # the governing rule forbids. That was once an unavoidable
            # narrowing; now it is simply correct, because `oracle`
            # answers the question for a dictionary, a list and a string
            # alike.
            return Binary(
                self.expression(right), TokenType.ORACLE, self.expression(node.left)
            )
        mapped = _COMPARE.get(type(op))
        if mapped is None:
            raise _Unsupported(self._no(op, at=node))
        return Binary(self.expression(node.left), mapped, self.expression(right))

    def _dict(self, node: ast.Dict) -> Expr:
        entries = []
        for key, value in zip(node.keys, node.values):
            if key is None:
                raise _Unsupported(
                    self._because(
                        node,
                        "`**` in a dictionary literal cannot be translated",
                        "add the entries one at a time with `d[k] = v`",
                    )
                )
            entries.append((self.expression(key), self.expression(value)))
        return DictLiteral(entries)

    def _call(self, node: ast.Call) -> Expr:
        if node.keywords:
            raise _Unsupported(
                self._because(
                    node,
                    "a keyword argument cannot be translated",
                    "MatrixLang agents take positional arguments only",
                )
            )
        if isinstance(node.func, ast.Name) and node.func.id == "input":
            # Reaching here means `input(...)` was not the whole right-hand
            # side of an assignment -- the only place it can become the two
            # statements (`trace`, then bind to `jackin`) it needs to be.
            raise _Unsupported(
                self._because(
                    node,
                    "`input(...)` cannot be translated inside a larger expression",
                    "read the line into its own name first: "
                    "`answer = input(...)`, then use `answer`",
                )
            )
        if isinstance(node.func, ast.Name) and node.func.id in _NAMED_CALL:
            if len(node.args) != 1:
                raise _Unsupported(
                    self._because(
                        node,
                        f"`{node.func.id}` takes exactly one value",
                        f"MatrixLang's `{_NAMED_CALL[node.func.id].name.lower()}` "
                        "is a one-operand operator",
                    )
                )
            return Unary(_NAMED_CALL[node.func.id], self.expression(node.args[0]))
        if isinstance(node.func, ast.Attribute):
            method = node.func.attr
            if method in _STRING_UNARY:
                if node.args:
                    # `.strip()` with no arguments is `trim` exactly.
                    # `.strip(chars)` is not an arity mismatch that a
                    # future `trim` could grow past -- it strips a
                    # character SET, where `trim` only ever strips
                    # whitespace. `.lower()` never takes an argument in
                    # real Python; reaching this branch for it means
                    # something already nonsensical, so it keeps the
                    # generic one-operand wording.
                    if method == "strip":
                        idiom = (
                            "`trim` strips whitespace, not a character "
                            "set -- `.strip(chars)` has no MatrixLang form"
                        )
                    else:
                        idiom = (
                            f"MatrixLang's "
                            f"`{_STRING_UNARY[method].name.lower()}` is a "
                            "one-operand operator"
                        )
                    raise _Unsupported(
                        self._because(
                            node,
                            f"`.{method}()` can only be translated with no "
                            "arguments",
                            idiom,
                        )
                    )
                return Unary(
                    _STRING_UNARY[method], self.expression(node.func.value)
                )
            if method == "split":
                if not node.args:
                    # Bare `.split()` is NOT `.split(" ")`. Python splits
                    # on RUNS of whitespace and discards empty strings, so
                    # translating it to `cleave " "` would give a program
                    # that runs and quietly means something else -- which
                    # is exactly what the governing rule forbids.
                    raise _Unsupported(
                        self._because(
                            node,
                            "`.split()` can only be translated with exactly "
                            "one separator",
                            'bare `.split()` splits on runs of whitespace and '
                            'drops empty pieces, which `cleave` does not do — '
                            'name the separator: `.split(" ")`',
                        )
                    )
                if len(node.args) > 1:
                    # A distinct refusal from the zero-argument case above:
                    # the reason there is a MISSING separator, the reason
                    # here is a maxsplit that `cleave` has no way to honour
                    # -- telling a reader who already named the separator
                    # to "name the separator" would send them chasing a
                    # mistake they didn't make.
                    raise _Unsupported(
                        self._because(
                            node,
                            "`.split()` with a limit cannot be translated "
                            "— `cleave` always splits at every separator",
                            "split the whole string and use the pieces "
                            'you want: `parts = s.split(",")`, then '
                            "`parts[0]`",
                        )
                    )
                return Binary(
                    self.expression(node.func.value),
                    TokenType.CLEAVE,
                    self.expression(node.args[0]),
                )
            if method == "upper":
                raise _Unsupported(self._because(node, _UPPER_REASON, _UPPER_IDIOM))
            raise _Unsupported(
                self._because(
                    node,
                    f"`.{node.func.attr}()` cannot be translated as a value",
                    "`.append()` becomes an assignment, so it only works as a "
                    "statement on its own line",
                )
            )
        if not isinstance(node.func, ast.Name):
            raise _Unsupported(
                self._because(
                    node,
                    "calling something that is not a name cannot be translated",
                    "MatrixLang calls an agent by its name",
                )
            )
        return Call(Name(node.func.id), [self.expression(a) for a in node.args])

    def _fstring(self, node: ast.JoinedStr) -> Expr:
        """An f-string as a `+` chain, with `encode` around each hole.

        `encode` gives the text form of any value, so wrapping every hole
        in it is not a bet that the hole is a number: a string
        interpolation translates and runs cleanly instead of dying at Run
        the way it used to when the hole was not a number. `encode` still
        refuses a value that contains itself and an integer past the
        digit ceiling, and those refusals surface at runtime with a line
        and column rather than silently meaning something else.

        That does not make every hole's printed text agree with Python's.
        `encode` and `trace` share `to_display`, and `to_display` already
        had its own spelling for a handful of shapes -- a list or
        dictionary quotes the strings it holds, a boolean prints
        lowercase, an agent prints as `<agent name>` -- so `print(xs)`
        for such a value diverged before this branch touched anything.
        What this change adds is more roads to that same divergence: an
        f-string hole used to fail loudly on those shapes instead of
        printing MatrixLang's spelling, and now it prints it, same as
        `trace` always did.
        """
        parts: list[Expr] = []
        for piece in node.values:
            if isinstance(piece, ast.Constant):
                if piece.value:
                    parts.append(StringLiteral(piece.value))
            elif isinstance(piece, ast.FormattedValue):
                if piece.conversion != -1 or piece.format_spec is not None:
                    raise _Unsupported(
                        self._because(
                            piece,
                            "an f-string conversion or format spec cannot be "
                            "translated",
                            "MatrixLang has no formatting; build the text with `+`",
                        )
                    )
                parts.append(Unary(TokenType.ENCODE, self.expression(piece.value)))
            else:
                raise _Unsupported(
                    self._because(node, "this f-string cannot be translated")
                )
        if not parts:
            return StringLiteral("")
        result = parts[0]
        for part in parts[1:]:
            result = Binary(result, TokenType.PLUS, part)
        return result

    def _because(
        self, node: ast.AST, reason: str, idiom: str | None = None
    ) -> Refusal:
        """A refusal whose reason is written out, positioned at `node`.

        `_no` names a CONSTRUCT, keyed by its Python ast class -- which is
        the right answer whenever the class is the whole story (`import`,
        a tuple, `%`). It is the wrong answer whenever several different
        refusals share one class: every `print` arity problem, every
        `input` misuse and every wrong-arity `len` is an `ast.Call`, and
        "Call cannot be translated" tells the reader nothing they can act
        on. Those say what is actually wrong, here.
        """
        return Refusal(
            reason,
            getattr(node, "lineno", 1),
            getattr(node, "col_offset", 0),
            idiom,
        )

    def _no(
        self, node: ast.AST, idiom: str | None = None, at: ast.AST | None = None
    ) -> Refusal:
        """Refuse `node`, positioned at `at` when `node` has no position.

        Python's operator nodes (`ast.Div`, `ast.Mod`, `ast.Is`, ...) carry
        no lineno/col_offset at all -- they are singletons hanging off the
        expression that uses them -- so naming one as the culprit without
        `at` would report every `%` in a file at line 1, column 0. The
        operator is still what gets NAMED; only the position comes from
        the expression around it.
        """
        name = type(node).__name__
        where = node if at is None else at
        return Refusal(
            f"{_DESCRIBE.get(name, _UNNAMED)} cannot be translated",
            getattr(where, "lineno", 1),
            getattr(where, "col_offset", 0),
            idiom if idiom is not None else _IDIOM.get(name),
        )


def _is_input_call(node: ast.expr) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "input"
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


def _increment_before_glitches(body: list[Stmt], counter: str) -> list[Stmt]:
    """Put the loop counter's increment before every `glitch` in `body`.

    A `glitch` jumps to the loop's condition, so it skips the increment
    the desugaring appends at the END of the body -- and a correct Python
    loop becomes one that spins until the step limit.

    Walks the ALREADY-TRANSLATED statements rather than the Python ast,
    which is what makes the boundary rule fall out for free:

      - A nested Python loop is already a While node here, so its own
        `glitch` sits behind the stop and keeps the increment its own
        translation inserted.
      - A Python `while` has no counter, and stopping at While gives that
        too.
      - A nested `for` in a `for` gets the INNER counter incremented by
        the inner translation, and this walk leaves it alone.

    `wake` needs nothing: it leaves the loop, so a skipped increment is
    exactly right.
    """
    out: list[Stmt] = []
    for statement in body:
        if isinstance(statement, Glitch):
            out.append(
                Assign(counter, Binary(Name(counter), TokenType.PLUS, NumberLiteral(1)))
            )
            out.append(statement)
        elif isinstance(statement, If):
            statement.then_body = _increment_before_glitches(
                statement.then_body, counter
            )
            if statement.else_body is not None:
                statement.else_body = _increment_before_glitches(
                    statement.else_body, counter
                )
            out.append(statement)
        else:
            # While and FunctionDef fall here deliberately -- a `glitch`
            # inside either belongs to that loop, not this one.
            out.append(statement)
    return out


def _hoist_declares(
    body: list[Stmt], placeholders: dict[int, Declare]
) -> tuple[list[Stmt], list[Declare]]:
    """Rewrite every `Declare` anywhere in `body` to a plain `Assign` in
    place, and return placeholder declarations (each initialised to `0`)
    to hoist above the enclosing loop or `if`.

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

    `placeholders` records, by identity, every declaration this function
    has itself invented, because hoists nest: an `if` inside a `for` hoists
    first, and then the loop hoists what the `if` left behind. A
    placeholder met a second time is MOVED rather than rewritten -- it is
    lifted out whole and nothing is left in its place. Rewriting it the
    ordinary way would leave `s = 0` at the top of the loop body, silently
    resetting on every pass a name the reader expects to survive from the
    iteration that set it. A `Declare` the READER's own program produced
    (`x = 0` written inside the loop) is not a placeholder and still
    becomes an assignment in place, because that reset is theirs.

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
                if id(statement) in placeholders:
                    hoisted.append(statement)
                    continue
                placeholder = Declare(statement.name, NumberLiteral(0))
                placeholders[id(placeholder)] = placeholder
                hoisted.append(placeholder)
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


def _defines_function(
    body: list[ast.stmt],
) -> ast.FunctionDef | ast.AsyncFunctionDef | None:
    """The first `def` sitting directly in `body`, or nested only through
    `if`/`while` -- the same reach `_hoist_declares` gives a `Declare`,
    because a `def` binds its name on every pass through a `dejavu`
    exactly the way a first assignment does (interpreter.py's `FunctionDef`
    branch calls the same `_env.declare` a `Declare` does, so it hits the
    identical "already declared" quirk on the second iteration).

    Does not recurse into a nested `for` or `while`: each of those runs
    this exact check against its own immediate body when IT is
    translated, so recursing into one here would only re-report the same
    `def` from a second call site, never catch a new one.
    """
    for statement in body:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return statement
        if isinstance(statement, ast.If):
            found = _defines_function(statement.body) or _defines_function(
                statement.orelse
            )
            if found is not None:
                return found
        if isinstance(statement, ast.While):
            found = _defines_function(statement.body)
            if found is not None:
                return found
    return None


def _refuse_function_in_loop(body: list[ast.stmt]) -> None:
    """Refuse a `def` written directly in a loop body, rather than hoist
    it above the loop the way a `Declare` gets hoisted.

    Hoisting was considered and rejected: the loop variable is substituted
    inline (`x` becomes `xs[n]`), never declared, so a function written in
    Python to close over `x` would -- if hoisted -- close over a counter
    that means nothing yet at the point the hoisted `agent` sits, above
    the loop it indexes. That would silently change what the closure
    captures, which is exactly the kind of difference this translator
    refuses rather than risk. A `def` outside any loop is unaffected --
    only one written directly inside a `for` or `while` body is refused.
    """
    found = _defines_function(body)
    if found is None:
        return
    raise _Unsupported(
        Refusal(
            "a function defined inside a loop cannot be translated",
            found.lineno,
            found.col_offset,
            "define the agent once, outside the loop",
        )
    )


# What a reader calls each construct, keyed by its ast class name. Without
# this a refusal says "ImportFrom", which is Python's word, not theirs --
# and the fallback below is deliberately anonymous for the same reason:
# leaking "Delete" or "AnnAssign" tells the reader about CPython's parser,
# not about their program. Anything a reader can plausibly write has an
# entry; the fallback exists only so a Python version that grows a new
# node type cannot start printing its internals at them.
_UNNAMED = "this construct"

_DESCRIBE = {
    "Import": "`import`",
    "ImportFrom": "`import`",
    "ClassDef": "`class`",
    "Try": "`try`",
    "TryStar": "`try`",
    "Raise": "`raise`",
    "Lambda": "`lambda`",
    "FunctionDef": "`def`",
    "AsyncFunctionDef": "`async def`",
    "AsyncFor": "`async for`",
    "AsyncWith": "`async with`",
    "Await": "`await`",
    "Yield": "`yield`",
    "YieldFrom": "`yield from`",
    "Delete": "`del`",
    "Global": "`global`",
    "Nonlocal": "`nonlocal`",
    "With": "`with`",
    "Assert": "`assert`",
    "Pass": "`pass`",
    "Match": "`match`",
    "AnnAssign": "a type annotation",
    "NamedExpr": "`:=`",
    "IfExp": "a conditional expression",
    "Starred": "`*` unpacking",
    "Attribute": "attribute access",
    "Mod": "`%`",
    "Pow": "`**`",
    "MatMult": "`@`",
    "LShift": "`<<`",
    "RShift": "`>>`",
    "BitAnd": "`&`",
    "BitOr": "`|`",
    "BitXor": "`^`",
    "Invert": "`~`",
    "UAdd": "unary `+`",
    "ListComp": "a list comprehension",
    "SetComp": "a set comprehension",
    "DictComp": "a dict comprehension",
    "GeneratorExp": "a generator expression",
    "Tuple": "a tuple",
    "Set": "a set",
    "Slice": "a slice",
    "Div": "`/`",
    "FloorDiv": "`//`",
    "Is": "`is`",
    "IsNot": "`is not`",
    # No "In" entry, deliberately. _compare handles ast.In before it ever
    # reaches the _COMPARE lookup that would refuse it: `in` always becomes
    # `oracle`, because nothing at translation time distinguishes a
    # dictionary from a list from a string, and `oracle` now answers the
    # membership question correctly for all three. "NotIn" stays -- that
    # one genuinely does refuse, since MatrixLang has no negated form of
    # `oracle`.
    "NotIn": "`not in`",
    # Not in the brief's list: the ast.Compare node itself is the culprit
    # when a comparison chains more than one operator (`a < b < c`), and
    # without an entry here the reason falls back to the literal ast class
    # name "Compare", which the chained-comparison test can't match on.
    "Compare": "a chained comparison",
}

_IDIOM = {
    "Div": (
        "MatrixLang has no fractions, and its own `/` truncates toward zero — "
        "`7 / 2` there is `3`, not `3.5`. Write the division in MatrixLang "
        "directly if truncation is what you want"
    ),
    "FloorDiv": (
        "MatrixLang's `/` truncates toward zero and `//` floors, so they part "
        "company on negatives (`-7 // 2` is -4, `-7 / 2` here is -3). Write the "
        "division in MatrixLang directly once you know the signs"
    ),
    "Pass": "MatrixLang needs no filler statement; leave the body empty",
    "Delete": "MatrixLang has no `del`; a name lives as long as its scope",
    "Global": "an agent cannot rebind a name outside it; `jackout` the new value",
    "Nonlocal": "an agent cannot rebind a name outside it; `jackout` the new value",
    "With": "MatrixLang has no context managers",
    "Assert": "test it with `redpill` and `trace` what went wrong",
    "Match": "use `redpill` / `bluepill`",
    "AnnAssign": "drop the annotation: `x = 1`",
    "NamedExpr": "assign on its own line first, then use the name",
    "IfExp": "write it as `if` / `else` over two statements",
    "Starred": "pass the arguments one at a time",
    "Attribute": (
        "MatrixLang has no objects; `xs.append(v)` on its own line is the "
        "one thing it can translate"
    ),
    "Yield": "build the whole list and `jackout` it",
    "YieldFrom": "build the whole list and `jackout` it",
    "Await": "MatrixLang runs one statement after another and never waits",
    "Mod": "MatrixLang has no remainder operator",
    "Pow": "multiply in a `dejavu` loop",
    "MatMult": "MatrixLang has no matrix multiply, despite the name",
    "LShift": "MatrixLang has no bitwise operators",
    "RShift": "MatrixLang has no bitwise operators",
    "BitAnd": "MatrixLang has no bitwise operators; `splice` is `and` on booleans",
    "BitOr": "MatrixLang has no bitwise operators; `fork` is `or` on booleans",
    "BitXor": "MatrixLang has no bitwise operators",
    "Invert": "MatrixLang has no bitwise operators; `unplug` is `not` on booleans",
    "UAdd": "a leading `+` does nothing; write the value on its own",
    "ListComp": "build the list with a `dejavu` loop and `xs = xs + [v]`",
    "SetComp": "MatrixLang has no sets; use a list",
    "DictComp": "build the dictionary with a `dejavu` loop and `d[k] = v`",
    "GeneratorExp": "build the list with a `dejavu` loop",
    "Tuple": "MatrixLang has no tuples; use a list",
    "Set": "MatrixLang has no sets; use a list",
    "Slice": "MatrixLang has no slicing; copy with a `dejavu` loop",
    "Is": "MatrixLang has no identity check; compare values with `==`",
    "IsNot": "MatrixLang has no identity check; compare values with `!=`",
    "NotIn": "MatrixLang has no `not in`; write `unplug (xs oracle x)`",
}
