"""Pins the module dependency graph the Stage 2 plan specifies.

These are not style rules. `parser` must not import `lexer` because Stage 4
feeds the parser tokens from two different source faces; an import would let
that coupling creep back in silently. Asserted against the import graph rather
than against behaviour, because an unused import breaks no test that runs code.
"""

import ast
from pathlib import Path

import pytest

_SRC = Path(__file__).parent.parent / "src" / "matrixlang"

# module -> the matrixlang siblings it may import
_ALLOWED: dict[str, set[str]] = {
    "tokens": set(),
    "errors": set(),
    "nodes": {"tokens"},
    "lexer": {"errors", "tokens"},
    "parser": {"errors", "nodes", "tokens"},
    "treeview": {"nodes", "tokens"},
    "cli": {"errors", "lexer", "parser", "treeview"},
}


def _sibling_imports(module: str) -> set[str]:
    """The matrixlang submodules `module` imports, by reading its source."""
    tree = ast.parse((_SRC / f"{module}.py").read_text(encoding="utf-8"))
    found: set[str] = set()
    for node in ast.walk(tree):
        names: list[str] = []
        if isinstance(node, ast.ImportFrom) and node.module:
            names = [node.module]
        elif isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        for name in names:
            parts = name.split(".")
            if parts[0] == "matrixlang" and len(parts) > 1:
                found.add(parts[1])
    return found


def test_the_parser_never_imports_the_lexer():
    # The load-bearing one. A parser that merely *works* on hand-built tokens
    # would still pass with an unused lexer import sitting in it, so this is
    # asserted against the imports themselves.
    assert "lexer" not in _sibling_imports("parser")


@pytest.mark.parametrize("module", sorted(_ALLOWED))
def test_module_imports_stay_inside_the_planned_graph(module):
    assert _sibling_imports(module) <= _ALLOWED[module]
