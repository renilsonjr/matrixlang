"""List comprehensions, turned into loops before translation begins.

The translator's own `for` desugaring already emits exactly the shape a
comprehension needs -- an empty list, a counter, and `out = out + [v]`.
So there is nothing to teach it. This pass rewrites the comprehension into
that loop in Python, and `_Translator` never learns what a comprehension
is.

Python in, Python out, which is what makes it testable with `ast.unparse`
and no translator involved: a failure here says the rewrite is wrong
rather than that something downstream broke.

Anything this pass declines to rewrite it leaves exactly as it found it,
so the construct keeps the refusal it already had. Declining is the whole
error-handling strategy; there is no failure mode of its own.
"""

import ast

from matrixlang.pytrans.names import free_name

# Names the reader never wrote. Readable rather than mangled, because the
# emitted MatrixLang is something a person reads -- `construct out = []`
# reads as a program, `construct _c0 = []` reads as machine output.
# free_name keeps them off the reader's own names; neither is a MatrixLang
# keyword (pinned in the tests).
_RESULT_STEM = "out"
_ITEM_STEM = "item"


def rewrite_comprehensions(tree: ast.Module, taken: set[str]) -> ast.Module:
    """Replace supported list comprehensions with the loops they mean.

    `taken` is the caller's set of names already in use. It is the pass's
    running record, not a snapshot: every name invented here is added to
    it, so two comprehensions in one program cannot both be `out`, and the
    counters `_Translator` invents afterwards cannot collide with either.
    """
    tree.body = _block(tree.body, taken)
    return tree


def _block(statements: list[ast.stmt], taken: set[str]) -> list[ast.stmt]:
    """Rewrite one suite, emitting each loop just before it is needed."""
    out: list[ast.stmt] = []
    for statement in statements:
        _rewrite_nested_blocks(statement, taken)
        emitted: list[ast.stmt] = []
        _rewrite_own_expressions(statement, taken, emitted)
        out.extend(emitted)
        out.append(statement)
    return out


_BLOCK_FIELDS = ("body", "orelse", "finalbody")


def _rewrite_nested_blocks(statement: ast.stmt, taken: set[str]) -> None:
    """Recurse into the suites a statement contains.

    Doing this before the statement's own expressions is what keeps a
    comprehension inside a loop body inside that loop, rather than hoisted
    above it where it would run once instead of every turn.
    """
    for field in _BLOCK_FIELDS:
        block = getattr(statement, field, None)
        if isinstance(block, list) and all(isinstance(s, ast.stmt) for s in block):
            setattr(statement, field, _block(block, taken))
    for handler in getattr(statement, "handlers", []):
        handler.body = _block(handler.body, taken)


def _rewrite_own_expressions(
    statement: ast.stmt, taken: set[str], emitted: list[ast.stmt]
) -> None:
    """Rewrite the expressions belonging to this statement itself.

    Walking the statement's own expr-typed fields, rather than the whole
    subtree, is what stops the walk at statement boundaries -- the nested
    suites were already handled above, and re-entering them here would
    hoist their comprehensions out to the wrong level.
    """
    hoister = _Hoister(taken, emitted)
    for field, value in ast.iter_fields(statement):
        if isinstance(value, ast.expr):
            setattr(statement, field, hoister.visit(value))
        elif isinstance(value, list) and any(isinstance(v, ast.expr) for v in value):
            setattr(statement, field, [
                hoister.visit(item) if isinstance(item, ast.expr) else item
                for item in value
            ])


class _Hoister(ast.NodeTransformer):
    """Swaps each comprehension for a name, and records the loop it needs.

    `emitted` is where the loops go, and which list it points at is the
    whole scoping mechanism: the top-level instance writes before the
    containing statement, and instances made for a comprehension's element
    or conditions write inside the loop body being built.
    """

    def __init__(self, taken: set[str], emitted: list[ast.stmt]) -> None:
        self.taken = taken
        self.emitted = emitted

    def visit_ListComp(self, node: ast.ListComp) -> ast.expr:
        clause = node.generators[0] if len(node.generators) == 1 else None
        if clause is None or clause.is_async:
            return node
        if not isinstance(clause.target, ast.Name):
            return node

        result = self._invent(_RESULT_STEM)
        item = self._invent(_ITEM_STEM)
        element = _renamed(node.elt, clause.target.id, item)
        conditions = [
            _renamed(test, clause.target.id, item) for test in clause.ifs
        ]

        append = ast.Assign(
            targets=[ast.Name(id=result, ctx=ast.Store())],
            value=ast.BinOp(
                left=ast.Name(id=result, ctx=ast.Load()),
                op=ast.Add(),
                right=ast.List(elts=[element], ctx=ast.Load()),
            ),
        )
        body: list[ast.stmt] = [append]
        for test in reversed(conditions):
            body = [ast.If(test=test, body=body, orelse=[])]
        loop = ast.For(
            target=ast.Name(id=item, ctx=ast.Store()),
            iter=clause.iter,
            body=body,
            orelse=[],
        )
        start = ast.Assign(
            targets=[ast.Name(id=result, ctx=ast.Store())],
            value=ast.List(elts=[], ctx=ast.Load()),
        )
        for made in (start, loop):
            self.emitted.append(ast.fix_missing_locations(ast.copy_location(made, node)))
        return ast.copy_location(ast.Name(id=result, ctx=ast.Load()), node)

    def _invent(self, stem: str) -> str:
        name = free_name(self.taken, stem)
        self.taken.add(name)
        return name


def _renamed(node: ast.expr, old: str, new: str) -> ast.expr:
    """`node` with the comprehension's variable renamed to ours."""
    return _Rename(old, new).visit(node)


class _Rename(ast.NodeTransformer):
    def __init__(self, old: str, new: str) -> None:
        self.old = old
        self.new = new

    def visit_Name(self, node: ast.Name) -> ast.Name:
        if node.id != self.old:
            return node
        return ast.copy_location(ast.Name(id=self.new, ctx=node.ctx), node)
