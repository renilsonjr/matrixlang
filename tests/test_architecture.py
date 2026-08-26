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
    "ansi": set(),
    "tokens": set(),
    "errors": set(),
    "glyphs": set(),
    "input": set(),
    "nodes": {"tokens"},
    "values": set(),
    "events": {"nodes"},
    "translit": {"glyphs"},
    # Not {"events", "ansi"} as the design sketched. Selection deliberately
    # does not route through detect_color_mode: that vetoes on TERM, and a
    # window is not a terminal. Dropping the ansi import makes the deviation
    # visible here rather than only in a comment.
    "display": {"events"},
    "cascade": {"events", "nodes", "render", "translit"},
    # The load-bearing entry: `window` may depend on everything above it,
    # and nothing may depend on `window`. A backend leaking into the core
    # would make the language unrunnable without a display.
    "window": {"cascade", "display", "events"},
    "lexer": {"errors", "glyphs", "tokens"},
    "parser": {"errors", "nodes", "tokens"},
    "render": {"glyphs", "nodes", "tokens"},
    # The pure-contract half of the guard: scribe may reach nodes, render
    # and tokens (for TokenType) and nothing else — no operator, no SDK.
    "scribe": {"nodes", "render", "tokens"},
    "treeview": {"nodes", "tokens"},
    "cli": {
        "display", "errors", "events", "input", "interpreter", "lexer",
        "parser", "render", "repl", "treeview", "window",
    },
    "interpreter": {"errors", "events", "input", "nodes", "tokens", "values"},
    # The operator subpackage. Not {} as the design's table sketched for
    # prompt: the keyword list is read from tokens rather than retyped,
    # because a hardcoded grammar is how web/interpreter.js drifted from
    # the language it claimed to implement.
    "operator.prompt": {"tokens", "operator.validate"},
    "operator.validate": {
        "errors", "input", "interpreter", "lexer", "nodes", "parser",
    },
    # The impure edge. Imports no matrixlang sibling and no SDK at module
    # scope — `anthropic` is imported inside the calling function.
    "operator.client": set(),
    "operator.loop": {"nodes", "operator.prompt", "operator.validate"},
    "repl": {
        "errors", "input", "interpreter", "lexer", "parser", "render", "tokens",
    },
    # The Python-to-MatrixLang translator subpackage. refuse.py is the pure
    # contract half -- dataclasses only, no sibling imports, same shape as
    # scribe.py's promise never to raise. translate.py builds real nodes and
    # renders them with the real renderer rather than re-deriving precedence
    # rules, which is why it reaches nodes and render.
    "pytrans.refuse": set(),
    # names.py invents counters and holder names for `for`; it only walks
    # the Python ast, so it reaches no matrixlang sibling at all.
    "pytrans.names": set(),
    # comprehensions.py rewrites simple list comprehensions into loops
    # using free_name from pytrans.names.
    "pytrans.comprehensions": {"pytrans.names"},
    # `errors` for the same reason lexer/parser/interpreter/repl already
    # reach it: recursion_guard()/TooDeepError turn a RecursionError from
    # arbitrarily deep Python source (a long flat expression chain, no
    # syntax-level depth cap the way indentation and parens have) into
    # something translate() can hand back as a Refusal instead of raising.
    "pytrans.translate": {
        "errors", "nodes", "tokens", "render", "pytrans.refuse", "pytrans.names",
    },
}


_MODULES = {path.stem for path in _SRC.glob("*.py")} - {"__init__", "__main__"}

# Subpackages, as dotted names. The glob above only sees top-level files,
# so without this a whole subpackage would be invisible to every guard in
# here — which is exactly how web/ escaped the katakana rule before it was
# deleted.
_SUBPACKAGES = {
    f"{package.name}.{path.stem}"
    for package in _SRC.iterdir()
    if package.is_dir() and (package / "__init__.py").exists()
    for path in package.glob("*.py")
    if path.stem != "__init__"
}
_MODULES |= _SUBPACKAGES


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
                    found.add(_name(parts))
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
                    # `from matrixlang.operator import prompt` names a
                    # MODULE in the imported list, not in node.module.
                    # Resolving only node.module would report the package
                    # and hide which submodule was actually pulled in.
                    submodules = {
                        f"{parts[1]}.{a.name}"
                        for a in node.names
                        if f"{parts[1]}.{a.name}" in _MODULES
                    }
                    found.update(submodules or {_name(parts)})
                else:
                    found.update(a.name for a in node.names if a.name in _MODULES)
    return found


def _name(parts: list[str]) -> str:
    """`matrixlang.operator.validate` names a module, not the package.

    Flattening to the first segment would let anything inside a subpackage
    import anything else and still look compliant, because every edge would
    read as the same name.
    """
    dotted = ".".join(parts[1:3])
    return dotted if dotted in _MODULES else parts[1]


def _sibling_imports(module: str) -> set[str]:
    path = _SRC / (module.replace(".", "/") + ".py")
    return _imports_in_source(path.read_text(encoding="utf-8"))


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


# I-3: glyphs.py is the ONLY place a katakana literal may appear. D-03
# calls the glyph set swappable — "if a real film-glyph font ever exists,
# only this table changes" (glyphs.py's own docstring) — and that promise
# is only true if no other module carries a second, hidden copy of a
# glyph assignment. Half-width katakana (U+FF66-FF9D) is the exact block
# GLYPHS draws from (test_glyphs.py pins every value into it), so a
# character in that range anywhere else is either a stray glyph literal
# or a duplicate assignment, either way a violation of "assignments live
# only in glyphs.py."
_KATAKANA_LOW = 0xFF66
_KATAKANA_HIGH = 0xFF9D


@pytest.mark.parametrize("module", sorted(_MODULES - {"glyphs"}))
def test_only_glyphs_contains_a_katakana_character(module):
    source = (_SRC / (module.replace(".", "/") + ".py")).read_text(encoding="utf-8")
    offenders = {ch for ch in source if _KATAKANA_LOW <= ord(ch) <= _KATAKANA_HIGH}
    assert not offenders, f"{module}.py contains katakana glyph(s): {offenders!r}"


# --- The operator must stay optional -------------------------------------

_CORE = sorted(m for m in _MODULES if not m.startswith("operator."))


@pytest.mark.parametrize("module", _CORE)
def test_no_core_module_imports_the_operator(module):
    """The load-bearing rule, the same shape as the window's.

    The interpreter and the parser must stay runnable with no SDK
    installed, no key configured and no network reachable. A core module
    importing `operator` would make the language depend on the assistant
    that was built on top of it.
    """
    source = (_SRC / (module.replace(".", "/") + ".py")).read_text(encoding="utf-8")
    leaked = {i for i in _imports_in_source(source) if i.startswith("operator")}
    assert not leaked, f"{module} imports {leaked}"


def test_the_subpackage_guard_actually_sees_the_subpackage():
    # A guard is worth exactly what it catches. The module glob only looks
    # at top-level files, so this pins that the subpackage is enumerated —
    # otherwise every assertion above would pass by not looking.
    assert "operator.prompt" in _MODULES
    assert "operator.validate" in _MODULES


def test_importing_the_operator_does_not_shadow_the_standard_library():
    # The package is named after the role in the films and collides with
    # Python's own `operator`. Absolute imports make that harmless, and
    # this is the test that says so out loud.
    import operator as stdlib_operator

    import matrixlang.operator  # noqa: F401

    assert stdlib_operator.add(1, 2) == 3
    assert not hasattr(stdlib_operator, "build")


def test_the_guard_resolves_a_submodule_imported_from_its_package():
    # `from matrixlang.operator import prompt` must report
    # "operator.prompt", not the bare package — otherwise every import
    # inside a subpackage reads as the same name and the allow-table
    # stops distinguishing them.
    found = _imports_in_source("from matrixlang.operator import prompt")
    assert "operator.prompt" in found
