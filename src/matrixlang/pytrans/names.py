"""Two questions about names the translator cannot answer from a token.

The first: names the translator has to invent, and how they avoid the
reader's. A `for` loop needs a counter, and an iterable that is not
already a name needs somewhere to live. Both are names the reader never
wrote, so both must be guaranteed not to collide with one they did.

The second: which of the reader's OWN names hold a dictionary. The
translator carries no type information and never evaluates anything, so
`dict_names` proves this from syntax alone, conservatively — a name
left unproven costs a fix, a name proven wrongly costs a runtime error
this analysis would itself be introducing.
"""

import ast
import copy
import symtable


def bound_names(tree: ast.AST) -> set[str]:
    """Every name the Python program binds, anywhere.

    Deliberately over-inclusive: it counts targets inside constructs that
    will be refused anyway. A name that turns out not to exist costs one
    counter suffix; a name that is missed collides with the reader's.
    """
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            found.add(node.id)
        elif isinstance(node, ast.arg):
            found.add(node.arg)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            found.add(node.name)
    return found


def free_name(bound: set[str], stem: str = "n") -> str:
    """The first of `n`, `n1`, `n2`, ... that nothing else uses.

    The caller adds the result to `bound` before asking again, so nested
    loops get different counters.
    """
    if stem not in bound:
        return stem
    index = 1
    while f"{stem}{index}" in bound:
        index += 1
    return f"{stem}{index}"


# Python 3.12+ only; isinstance against an empty tuple is always False,
# which is what keeps this working on the 3.11 floor.
_TYPE_ALIAS = getattr(ast, "TypeAlias", ())

# Every binding form that carries its name as a plain string rather than
# an ast.Name node puts it in one of these fields.
_NAME_FIELDS = ("name", "rest", "asname", "arg")


def dict_names(tree: ast.AST) -> set[str]:
    """Names every one of whose bindings is a dict literal.

    Deliberately conservative, and the asymmetry is the reason. A name
    that holds a dictionary but is not proven here costs the fix; a name
    wrongly proven costs a `keymaker` on a list, which is a runtime error
    this analysis would be introducing. So anything unclear disqualifies.

    Denial is structural rather than a list of node types, with two
    nodes handled by hand: `ast.keyword`, whose name binds nothing, and
    `ast.alias`, whose name is a dotted path rather than the identifier
    it binds. This is the second design this had. The first enumerated binding forms and missed
    four of them in a row -- `match ... case d`, and PEP 695's `type d =`,
    `def f[d]`, `class C[d]` -- every one a binding that carries its name
    as a plain string field where a walk looking for ast.Name finds
    nothing. Denying on the FIELD rather than the node type closes that
    class instead of adding a fifth special case, and covers forms this
    version of Python does not have yet.

    A subscript target is NOT a binding. `d = {}` followed by
    `d["a"] = 1` leaves `d` proven, which matters because building a
    dictionary and then walking it is the shape a reader actually writes.

    There is no scope sensitivity, on purpose. A module-level `d` and an
    unrelated parameter named `d` disqualify the name everywhere. That
    costs a fix we could have made; the alternative costs a failure we
    would have introduced.
    """
    proven: dict[str, bool] = {}

    def deny(target: ast.AST) -> None:
        for inner in ast.walk(target):
            if isinstance(inner, ast.Name) and isinstance(inner.ctx, ast.Store):
                proven[inner.id] = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                # A tuple target binds no single name to the literal,
                # whatever the right-hand side is: unpacking a dictionary
                # binds its KEYS.
                ok = isinstance(node.value, ast.Dict) and isinstance(target, ast.Name)
                for inner in ast.walk(target):
                    if isinstance(inner, ast.Name) and isinstance(inner.ctx, ast.Store):
                        proven[inner.id] = proven.get(inner.id, True) and ok
            continue

        if isinstance(
            node,
            (ast.AugAssign, ast.AnnAssign, ast.NamedExpr,
             ast.For, ast.AsyncFor, ast.comprehension),
        ):
            deny(node.target)
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            deny(node.optional_vars)
        elif isinstance(node, _TYPE_ALIAS):
            # The one string-named form whose name IS an ast.Name node.
            deny(node.name)

        if isinstance(node, ast.alias):
            # The one field whose value is not the identifier it binds:
            # `import d.b.c` has name="d.b.c" and binds only `d`. Denying
            # the raw string would deny a name nobody wrote and leave the
            # real one proven.
            proven[node.asname or node.name.split(".")[0]] = False
            continue

        if isinstance(node, ast.keyword):
            # A call's keyword argument name binds nothing: `f(d=1)` must
            # leave a dictionary named `d` proven.
            continue
        for field in _NAME_FIELDS:
            value = getattr(node, field, None)
            if isinstance(value, str):
                proven[value] = False

    walked = {name for name, ok in proven.items() if ok}
    return walked - _still_bound_without_their_proofs(tree, walked)


class _WithoutProvingAssigns(ast.NodeTransformer):
    """Replaces the dict-literal assignments the walk credited for a proof.

    `pass` rather than deletion, and that is not a style choice. Removing
    the only statement in a block leaves an empty body, which `ast.unparse`
    renders as invalid source -- `class C:` with nothing under it -- and
    `symtable` then refuses the whole program. The failure path denies
    every proven name, so one `def f(): d = {...}` would cost every fix in
    the file, including names with nothing to do with it.
    """

    def __init__(self, names: set[str]) -> None:
        self.names = names

    def visit_Assign(self, node: ast.Assign):
        if isinstance(node.value, ast.Dict) and all(
            isinstance(t, ast.Name) and t.id in self.names for t in node.targets
        ):
            return ast.copy_location(ast.Pass(), node)
        return node


def _still_bound_without_their_proofs(tree: ast.AST, proven: set[str]) -> set[str]:
    """Of `proven`, the names Python still binds once their proofs are gone.

    The backstop, and the reason it is shaped this way. Asking symtable
    which names are bound cannot catch anything on its own: a name that is
    both assigned a dict literal AND captured by a form the walk missed is
    reported bound either way, so subtracting what the walk saw leaves
    nothing. Removing the assignments the walk is relying on and asking
    again is what makes the missed binding the only one left to report.

    Any name that survives that has a binding the walk did not classify.
    It is denied, and the cost is one lost fix rather than a `keymaker`
    emitted onto a list.
    """
    if not proven:
        return set()
    for node in ast.walk(tree):
        # `from m import *` brings in names nobody can enumerate --
        # symtable does not know them either, so it would report every
        # proven name as unbound and wave them all through. The only
        # honest answer is to prove nothing.
        if isinstance(node, ast.alias) and node.name == "*":
            return set(proven)
    try:
        stripped = _WithoutProvingAssigns(proven).visit(copy.deepcopy(tree))
        ast.fix_missing_locations(stripped)
        table = symtable.symtable(ast.unparse(stripped) or "pass", "<dict_names>", "exec")
    except (SyntaxError, ValueError, RecursionError, AttributeError, TypeError):
        # Fall back to the walk, which is complete for Python as it
        # stands -- an exhaustive hunt over 192 binding forms could not
        # falsify it. The backstop exists for binding forms Python has
        # not shipped yet, so losing it here is exactly the behaviour
        # this module had before the backstop was added, and that was
        # reviewed sound. Denying everything instead would silently
        # switch the whole fix off for any file containing one long
        # expression, anywhere -- which is the defect this branch exists
        # to close.
        return set()

    still: set[str] = set()

    def visit(scope) -> None:
        for symbol in scope.get_symbols():
            name = symbol.get_name()
            if name in proven and (
                symbol.is_assigned() or symbol.is_parameter() or symbol.is_imported()
            ):
                still.add(name)
        for child in scope.get_children():
            visit(child)

    visit(table)
    return still
