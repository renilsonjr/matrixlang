"""Names the translator has to invent, and how they avoid the reader's.

A `for` loop needs a counter, and an iterable that is not already a name
needs somewhere to live. Both are names the reader never wrote, so both
must be guaranteed not to collide with one they did.
"""

import ast


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


def dict_names(tree: ast.AST) -> set[str]:
    """Names every one of whose bindings is a dict literal.

    Deliberately conservative, and the asymmetry is the reason. A name
    that holds a dictionary but is not proven here costs the fix; a name
    wrongly proven costs a `keymaker` on a list, which is a runtime error
    this analysis would be introducing. So anything unclear disqualifies:
    a parameter, a loop target, a tuple target, a value from a call.

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
                # whatever the right-hand side is.
                ok = isinstance(node.value, ast.Dict) and isinstance(target, ast.Name)
                for inner in ast.walk(target):
                    if isinstance(inner, ast.Name) and isinstance(inner.ctx, ast.Store):
                        proven[inner.id] = proven.get(inner.id, True) and ok
        elif isinstance(node, ast.arg):
            proven[node.arg] = False
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            proven[node.name] = False
        elif isinstance(node, (ast.AugAssign, ast.AnnAssign, ast.NamedExpr)):
            deny(node.target)
        elif isinstance(node, (ast.For, ast.AsyncFor, ast.comprehension)):
            deny(node.target)
        elif isinstance(node, ast.alias):
            proven[node.asname or node.name.split(".")[0]] = False
        elif isinstance(node, ast.ExceptHandler) and node.name:
            proven[node.name] = False
        elif isinstance(node, ast.withitem) and node.optional_vars is not None:
            deny(node.optional_vars)

    return {name for name, ok in proven.items() if ok}
