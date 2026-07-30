"""Runtime value rules for MatrixLang.

Values are plain Python `int`, `bool` and `str` — the environment really is
a dictionary, which is the point of Stage 3.

That choice has one sharp edge, and this module exists to blunt it: in
Python, `bool` is a subclass of `int`. `isinstance(True, int)` is True and
`True + 1` evaluates to 2. Spec §5 forbids coercion, so `true + 1` must be
a runtime error — and with `isinstance` that error would never fire.

Every predicate here uses `type(value) is X`. Never `isinstance`.
"""


def is_int(value: object) -> bool:
    return type(value) is int


def is_bool(value: object) -> bool:
    return type(value) is bool


def is_str(value: object) -> bool:
    return type(value) is str


def type_name(value: object) -> str:
    """The language's own word for a value's type, for error messages."""
    if is_int(value):
        return "integer"
    if is_bool(value):
        return "boolean"
    if is_str(value):
        return "string"
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
    return str(value)
