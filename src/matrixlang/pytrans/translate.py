"""Python source in, MatrixLang source out.

Builds real `matrixlang.nodes` objects and renders them with the real
renderer, rather than emitting text. render.py already knows every
precedence rule and where parentheses are needed; a second copy of that
knowledge here is the shape of mistake that produced the deleted
web/interpreter.js. Building nodes also means the output parses by
construction -- it came from the same classes the parser produces.
"""

import ast

from matrixlang.nodes import Program, Stmt
from matrixlang.render import render_ascii

from matrixlang.pytrans.refuse import Refusal, Refusals, Translated, _Unsupported


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

    walker = _Translator()
    statements = walker.body(tree.body)
    if walker.refusals:
        return Refusals(sorted(walker.refusals, key=lambda r: (r.line, r.column)))
    return Translated(render_ascii(Program(statements)))


class _Translator:
    def __init__(self) -> None:
        self.refusals: list[Refusal] = []

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
        raise _Unsupported(self._no(self._culprit(node)))

    def _culprit(self, node: ast.stmt) -> ast.AST:
        """The construct actually responsible for the refusal.

        Every statement refuses in this skeleton, but a statement that is
        otherwise ordinary -- an assignment, say -- can still be carrying an
        unsupported expression, such as a comprehension. Naming the
        assignment would be technically true and useless; the reader needs
        to know it's the `[... for ...]` that has no MatrixLang idiom yet
        (once translation exists, this is also where that expression would
        be found).
        """
        for child in ast.walk(node):
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
}

_IDIOM = {
    "ListComp": "build the list with a `dejavu` loop and `xs = xs + [v]`",
    "SetComp": "MatrixLang has no sets; use a list",
    "DictComp": "build the dictionary with a `dejavu` loop and `d[k] = v`",
    "GeneratorExp": "build the list with a `dejavu` loop",
}
