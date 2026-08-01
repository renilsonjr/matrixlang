"""Runtime value rules for MatrixLang.

Values are plain Python `int`, `bool` and `str` — the environment really is
a dictionary, which is the point of Stage 3.

That choice has one sharp edge, and this module exists to blunt it: in
Python, `bool` is a subclass of `int`. `isinstance(True, int)` is True and
`True + 1` evaluates to 2. Spec §5 forbids coercion, so `true + 1` must be
a runtime error — and with `isinstance` that error would never fire.

Every predicate here uses `type(value) is X`. Never `isinstance`.

`Function` lives here rather than in the interpreter because it is a
runtime value type, and this module is where the rules describing runtime
values live. Keeping it here also means `values.py` still imports nothing:
the body and the captured environment are held opaquely, so no dependency
on `nodes` or the interpreter is created.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Function:
    """An agent: parameters, a body, and the environment it was defined in.

    The closure is the environment where the agent was **defined**, not the
    one it is called from. That distinction is the whole of what closures
    are, and holding it on the value is what makes it survive the call that
    created it.

    Compared by identity: two agents with the same source are not the same
    agent, and nothing in the language can compare them anyway.
    """

    name: str
    params: list[str]
    body: Any = field(repr=False)
    closure: Any = field(repr=False)

    __hash__ = object.__hash__

    def __eq__(self, other: object) -> bool:
        return self is other


class _Nothing:
    """What an agent that never jacks out produces.

    Not a language value and not reachable as one: a call in statement
    position may produce it, and a call in expression position that
    produces it is a runtime error. This keeps the language at three types
    while still allowing a procedure to exist.
    """

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "NOTHING"


NOTHING = _Nothing()


def is_int(value: object) -> bool:
    return type(value) is int


def is_bool(value: object) -> bool:
    return type(value) is bool


def is_str(value: object) -> bool:
    return type(value) is str


def is_function(value: object) -> bool:
    return type(value) is Function


def type_name(value: object) -> str:
    """The language's own word for a value's type, for error messages."""
    if is_int(value):
        return "integer"
    if is_bool(value):
        return "boolean"
    if is_str(value):
        return "string"
    if is_function(value):
        return "agent"
    return type(value).__name__


def to_display(value: object) -> str:
    """How `trace` renders a value.

    Strings print without quotes; booleans print in the language's own
    lowercase spelling, not Python's `True`/`False`.
    """
    if is_bool(value):
        return "true" if value else "false"
    if is_str(value):
        return value
    if is_function(value):
        # Never str(value): that would put a Python class name and a
        # memory address into output a program produced, which is a hole
        # in the claim that a .rain program has no route into Python.
        return f"<agent {value.name}>"
    return str(value)
