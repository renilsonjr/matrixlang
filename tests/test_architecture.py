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
    "values": set(),
    "lexer": {"errors", "tokens"},
    "parser": {"errors", "nodes", "tokens"},
    "treeview": {"nodes", "tokens"},
    "cli": {"errors", "interpreter", "lexer", "parser", "repl", "treeview"},
    "interpreter": {"errors", "nodes", "tokens", "values"},
    "repl": {"errors", "interpreter", "lexer", "parser", "tokens"},
}


_MODULES = {path.stem for path in _SRC.glob("*.py")} - {"__init__", "__main__"}


def _imports_in_source(source: str) -> set[str]:
    """The matrixlang submodules `source` imports, by any spelling.

    Five ways to reach a sibling, all handled:
        import matrixlang.lexer
        from matrixlang.lexer import lex
        from matrixlang import lexer
        from .lexer import lex
        from . import lexer
    """
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            for alias in node.names:
                parts = alias.name.split(".")
                if parts[0] == "matrixlang" and len(parts) > 1:
                    found.add(parts[1])
        elif isinstance(node, ast.ImportFrom):
            head = (node.module or "").split(".")[0]
            if node.level and not node.module:
                found.update(a.name for a in node.names if a.name in _MODULES)
            elif node.level:
                if head in _MODULES:
                    found.add(head)
            elif head == "matrixlang":
                parts = node.module.split(".")
                if len(parts) > 1:
                    found.add(parts[1])
                else:
                    found.update(a.name for a in node.names if a.name in _MODULES)
    return found


def _sibling_imports(module: str) -> set[str]:
    return _imports_in_source((_SRC / f"{module}.py").read_text(encoding="utf-8"))


def test_the_parser_never_imports_the_lexer():
    # The load-bearing one. A parser that merely *works* on hand-built tokens
    # would still pass with an unused lexer import sitting in it, so this is
    # asserted against the imports themselves.
    assert "lexer" not in _sibling_imports("parser")


@pytest.mark.parametrize("module", sorted(_ALLOWED))
def test_module_imports_stay_inside_the_planned_graph(module):
    assert _sibling_imports(module) <= _ALLOWED[module]


def test_every_module_has_an_entry_in_the_allow_table():
    # The graph test parametrizes over _ALLOWED, so a module missing from the
    # table is never checked — it could import anything. Stage 4 adds modules;
    # this is the assertion that makes the guard hold when it does.
    assert _MODULES == set(_ALLOWED)


@pytest.mark.parametrize(
    "statement",
    [
        "import matrixlang.lexer",
        "from matrixlang.lexer import lex",
        "from matrixlang import lexer",
        "from .lexer import lex",
        "from . import lexer",
    ],
)
def test_the_guard_detects_every_import_spelling(statement):
    # A guard is worth exactly what it catches. An earlier version of this
    # helper caught two of these five and looked green on the other three.
    assert "lexer" in _imports_in_source(statement)
