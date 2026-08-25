"""Runtime value rules for MatrixLang.

Values are `decimal.Decimal`, `bool` and `str` — the environment really is
a dictionary, which is the point of Stage 3. Numbers used to be plain
Python `int`; they are `Decimal` now, so that `/` can be true division and
`+ - * %` can stay exact instead of silently rounding through a float.

That still has a sharp edge, left over from when numbers WERE `int`: in
Python, `bool` is a subclass of `int`, `isinstance(True, int)` is True, and
`True + 1` evaluates to 2. Spec §5 forbids coercion, so `true + 1` must be
a runtime error. Booleans no longer share a type with numbers, so
`isinstance` would not resurrect that particular bug today — but nothing
in this module rules out a future value type where the same shape of
problem returns, and `type(value) is X` costs nothing to keep everywhere.

Every predicate here uses `type(value) is X`. Never `isinstance`.

`Function` lives here rather than in the interpreter because it is a
runtime value type, and this module is where the rules describing runtime
values live. Keeping it here also means `values.py` still imports nothing:
the body and the captured environment are held opaquely, so no dependency
on `nodes` or the interpreter is created.
"""

import sys
from dataclasses import dataclass, field
from decimal import ROUND_HALF_EVEN, Context, Decimal, Overflow
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
    produces it is a runtime error. This keeps the language at five types
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
    """A value that contains itself, directly or through other values.

    Lists were the only container that could when this was written;
    dictionaries can too (`d["me"] = d`), and the walk in `_display`
    descends into both.

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


class BadKey(Exception):
    """A value was used as a dictionary key that cannot be one.

    Position-less, and converted to a MatrixLangError by the interpreter,
    for the same reason as CyclicValue and Incomparable: this module has
    no source positions and must not invent them.
    """

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class TooManyDigits(Exception):
    """A number with more digits than Python will turn into text.

    CPython refuses `str(int)` past `sys.get_int_max_str_digits()` — 4300
    by default — and raises a bare ValueError. Repeated squaring reaches
    that well inside a step budget, so it is a thing a program does, not
    an impossibility: it has to come out as the language's own error
    rather than as a Python exception escaping the interpreter (which
    `site/glue.py`'s `run()` promises never to emit, and catches nothing
    but MatrixLangError to stop).

    Carries the limit so the interpreter can build the message. Not a
    MatrixLangError for the same reason as CyclicValue and Incomparable:
    this module may import nothing, and has no line or column to report.
    """

    def __init__(self, limit: int) -> None:
        self.limit = limit
        super().__init__(f"more than {limit} digits")


class NumberOverflow(Exception):
    """An arithmetic result too large to represent.

    decimal.Context traps Overflow by default (inherited from
    decimal.DefaultContext) and raises decimal.Overflow for it -- a bare
    Python ArithmeticError, not a MatrixLangError. Integers never had this
    failure: an oversized int only ever failed at *display* time, as
    TooManyDigits above. Decimal fails earlier, inside the arithmetic
    itself -- prec=1000 pushes EXACT's Emax to 999999, but repeated
    squaring gets there well inside any step budget (`10`, squared 19
    times, is already past it).

    Not a MatrixLangError for the same reason as TooManyDigits and
    CyclicValue: this module may import nothing but the standard library,
    and has no line or column to report. The interpreter attaches the
    position.
    """


def _overflow_guarded(method):
    """Wrap a decimal.Context arithmetic method to raise NumberOverflow.

    EXACT and DIVISION are exposed as plain decimal.Context objects for
    later tasks to call directly -- `EXACT.add(...)`, `DIVISION.divide(
    ...)` -- so the guard has to live on the objects themselves. A helper
    function at a call site can't be trusted to be used by every call
    site that ever gets written; the context that raises decimal.Overflow
    in the first place is the one place a guard is certain to run.
    """

    def wrapped(self, a, b):
        try:
            return method(self, a, b)
        except Overflow:
            raise NumberOverflow() from None

    return wrapped


class _GuardedContext(Context):
    """A decimal.Context whose arithmetic raises NumberOverflow instead of
    letting decimal.Overflow -- a bare ArithmeticError -- escape.

    Traps stay ON (the decimal.DefaultContext default): Overflow is
    caught and converted the instant it would fire, before decimal ever
    materializes an infinite result. That is what keeps
    `is_whole(Decimal("Infinity"))` -- which is True, since Infinity
    equals its own to_integral_value() -- from becoming reachable through
    ordinary arithmetic: nothing this module's own operations can produce
    is ever infinite. A Decimal literally spelled "Infinity" could still
    reach here through the Decimal constructor itself (a lexer parsing a
    number token, say) -- that is out of this module's reach and is a
    later task's guard to add, not this one's.
    """

    add = _overflow_guarded(Context.add)
    subtract = _overflow_guarded(Context.subtract)
    multiply = _overflow_guarded(Context.multiply)
    remainder = _overflow_guarded(Context.remainder)
    divide = _overflow_guarded(Context.divide)


# Two contexts, one rule: division is the only operation that can go on
# forever, so it is the only one that rounds.
#
# Decimal rounds every operation to its context precision, and the default
# 28 is not enough -- `Decimal("9" * 40) * 2` comes back as
# 2.000000000000000000000000000E+40, losing precision AND leaking
# scientific notation on a value `int` handled exactly. 1000 is far above
# anything display can emit, so `+ - * %` are exact for every number a
# program can show a reader.
EXACT = _GuardedContext(prec=1000, rounding=ROUND_HALF_EVEN)
# 28 is where 0.3333333333333333333333333333 comes from.
DIVISION = _GuardedContext(prec=28, rounding=ROUND_HALF_EVEN)


def is_number(value: object) -> bool:
    """The language's one numeric type.

    `type(value) is Decimal`, not isinstance, for the same reason every
    other predicate here is exact: a bool is not a number, and an
    isinstance check on a Decimal subclass would let something else in.
    """
    return type(value) is Decimal


def is_whole(value: object) -> bool:
    """A number with nothing after the point.

    Indexes, `length`'s result and dictionary keys all need this. `3.0`
    is whole; `3.5` is not.
    """
    return is_number(value) and value == value.to_integral_value()


def is_bool(value: object) -> bool:
    return type(value) is bool


def is_str(value: object) -> bool:
    return type(value) is str


def is_function(value: object) -> bool:
    return type(value) is Function


def is_list(value: object) -> bool:
    return type(value) is list


def is_dict(value: object) -> bool:
    return type(value) is dict


def check_key(key: object) -> None:
    """Strings and numbers only.

    Booleans are refused because CPython gives True and 1 the same hash
    and calls them equal, so `{true: "a", 1: "b"}` would collapse into one
    entry -- the reader writes two keys and gets one, with nothing to tell
    them. Lists and dictionaries are refused because they are mutable: a
    key that changes after insertion is a lookup that stops working for
    reasons invisible where it is written.

    `Decimal("1")` and `Decimal("1.0")` hash equal, so `{1: "a", 1.0: "b"}`
    collapses to one entry too -- matching Python, where the same thing
    happens, so it is intended rather than the bug the bool case describes.
    """
    if is_bool(key) or not (is_str(key) or is_number(key)):
        raise BadKey(type_name(key))


def type_name(value: object) -> str:
    """The language's own word for a value's type, for error messages."""
    if is_number(value):
        return "number"
    if is_bool(value):
        return "boolean"
    if is_str(value):
        return "string"
    if is_function(value):
        return "agent"
    if is_list(value):
        return "list"
    if is_dict(value):
        return "dictionary"
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
    if is_dict(value):
        if id(value) in seen:
            raise CyclicValue
        seen = seen | {id(value)}
        inner = ", ".join(
            f"{_display(k, True, seen)}: {_display(v, True, seen)}"
            for k, v in value.items()
        )
        return "{" + inner + "}"
    if is_number(value):
        # format(value, "f") rather than str(value): str emits scientific
        # notation for large and small exponents -- str(Decimal("1e3")) is
        # "1E+3" -- and a reader must never see that. "f" is always
        # positional, and preserves trailing zeros, which are significant
        # here (2.50 * 2 is 5.00).
        if value.is_zero():
            # adjusted() on a zero reports its exponent, not its
            # magnitude -- Decimal("0E-5000").adjusted() is -5000, well
            # past the digit cap below, for a value that is exactly zero
            # and renders in one character. The guard exists for numbers
            # too big to write out; zero is never that.
            #
            # copy_abs() rather than a sign check: EXACT.multiply(0, -1)
            # is Decimal("-0"), and Python's own `0 * -1` is `0`. A
            # translated program must not print a minus sign its Python
            # twin never would, so the sign is dropped here, once, for
            # every zero -- not chased at every call site that might
            # produce one.
            value = value.copy_abs()
        elif abs(value.adjusted()) > sys.get_int_max_str_digits():
            # The positional form would be enormous. Same cap and same
            # reasoning as the old str(int) guard: report the limit the
            # running interpreter actually enforces rather than a
            # constant copied into this file.
            raise TooManyDigits(sys.get_int_max_str_digits())
        return format(value, "f")
    try:
        return str(value)
    except ValueError:
        # Not a number branch -- is_number(value) already failed above --
        # so this is the generic fallback shared with every other type
        # this module doesn't otherwise know how to render. The only
        # value shaped like this that has ever hit the cap was a plain
        # int; kept as a guard rather than deleted, because this branch
        # has no type check of its own and must not let a bare Python
        # exception through either.
        raise TooManyDigits(sys.get_int_max_str_digits()) from None


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
    if is_dict(left):
        # Same hole as the list branch, twice over: Python says
        # {"a": 1} == {"a": True} and {1: "x"} == {True: "x"}. The second
        # is closed upstream -- check_key refuses boolean keys before one
        # ever reaches a dictionary, so `key not in right` below can trust
        # Python's own hashing/equality on KEYS. The first is not closed
        # anywhere else, so values are recursed into manually here exactly
        # as list elements are, rather than compared with Python's `==`.
        if len(left) != len(right):
            return False
        pair = (id(left), id(right))
        if pair in seen:
            return True
        seen.add(pair)
        for key, value in left.items():
            if key not in right:
                return False
            if not _equal(value, right[key], seen):
                return False
        return True
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
