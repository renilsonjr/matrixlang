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
