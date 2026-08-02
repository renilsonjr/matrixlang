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
    produces it is a runtime error. This keeps the language at four types
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


class CyclicValue(Exception):
    """A list that contains itself, directly or through other lists.

    Raised rather than recursing forever. It is NOT a MatrixLangError,
    because this module may import nothing (tests/test_architecture.py)
    and has never had access to a line or column — every MatrixLangError
    carries one. The interpreter catches this and attaches the position,
    which is the module that actually knows it.
    """


class Incomparable(Exception):
    """Two values the language refuses to compare.

    Carries both type names so the interpreter can build the message. Not
    a MatrixLangError for the same reason as CyclicValue: this module may
    import nothing, and has no line or column to report.
    """

    def __init__(self, left: str, right: str) -> None:
        self.left = left
        self.right = right
        super().__init__(f"cannot compare {left} with {right}")


def is_int(value: object) -> bool:
    return type(value) is int


def is_bool(value: object) -> bool:
    return type(value) is bool


def is_str(value: object) -> bool:
    return type(value) is str


def is_function(value: object) -> bool:
    return type(value) is Function


def is_list(value: object) -> bool:
    return type(value) is list


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
    if is_list(value):
        return "list"
    return type(value).__name__


def to_display(value: object) -> str:
    """How `trace` renders a value.

    Strings print without quotes at the top level; booleans print in the
    language's own lowercase spelling, not Python's True/False.

    Inside a list, strings ARE quoted. The inconsistency is deliberate:
    without quotes `[hi, 1]` gives a reader no way to tell a string from
    a name. The top level keeps its old behaviour because changing it
    would alter the output of every program written so far.
    """
    return _display(value, nested=False, seen=frozenset())


def _display(value: object, nested: bool, seen: frozenset) -> str:
    if is_bool(value):
        return "true" if value else "false"
    if is_str(value):
        if not nested:
            return value
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if is_function(value):
        # Never str(value): that would put a Python class name and a
        # memory address into output a program produced, which is a hole
        # in the claim that a .rain program has no route into Python.
        return f"<agent {value.name}>"
    if is_list(value):
        if id(value) in seen:
            raise CyclicValue
        seen = seen | {id(value)}
        return "[" + ", ".join(_display(v, True, seen) for v in value) + "]"
    return str(value)


def equal(left: object, right: object) -> bool:
    """The language's `==`, at every depth.

    **Never delegates to Python's `==` for a list.** Python compares list
    elements with its own `==`, where `1 == True` — so `[1] == [true]`
    returned True while the top-level guard correctly rejected
    `1 == true`. The rule held at the surface and broke at every level
    beneath it. Recursing here with `type_name` is what makes it total.

    Cycles are handled with a seen-set of id-pairs rather than left to
    RecursionError: two mutually referential lists blow the stack under
    Python's own comparison, and mutation is what makes such lists
    reachable at all (Stage 7 design §3).
    """
    return _equal(left, right, set())


def _equal(left: object, right: object, seen: set) -> bool:
    if type_name(left) != type_name(right):
        raise Incomparable(type_name(left), type_name(right))
    if not is_list(left):
        # Agents are identity-compared by Function.__eq__; scalars are
        # value-compared. Both are correct here because the type check
        # above has already ruled out the bool/int confusion.
        return left == right
    if len(left) != len(right):
        return False
    pair = (id(left), id(right))
    if pair in seen:
        # Already comparing this pair further up the stack, or already
        # proven equal earlier in this same call. Either way, assuming
        # equality is the standard coinductive treatment of cycles and is
        # what terminates.
        return True
    seen.add(pair)
    # No finally/discard here: this is a memo, not a path-scoped visited
    # set. The pair is added BEFORE recursing, but it is only ever
    # CONSULTED again in two situations, and both are sound. On the
    # stack (a genuine cycle): the lookup above assumes equality, which
    # is the standard coinductive treatment of cycles. Off the stack,
    # after this recursion has already returned (shared, DAG structure
    # reached by a second path): that can only happen if this recursion
    # completed `True`, because a `False` return cascades straight
    # through every enclosing `if not _equal(...)` and an Incomparable
    # exception unwinds just as fast — either one aborts the whole
    # outermost `equal()` call before any sibling gets a chance to run
    # and look this pair up again. A completed pair therefore completed
    # `True`. Discarding it on the way back up would only throw that memo
    # away, forcing shared structure to be re-walked once per path to it
    # — exponential in depth for something like `node = [node, node]`
    # repeated N times. `seen` is fresh per `equal()` call, so nothing
    # leaks between calls.
    for a, b in zip(left, right):
        if not _equal(a, b, seen):
            return False
    return True
