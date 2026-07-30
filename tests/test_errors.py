import pytest

from matrixlang.errors import LexError, MatrixLangError, ParseError


def test_message_format_pins_line_and_column():
    # This exact format is a contract: the CLI, and every future stage's
    # errors, present positions this way.
    error = MatrixLangError("something broke", 3, 7)
    assert str(error) == "[line 3, column 7] something broke"


def test_attributes_survive():
    error = ParseError("bad tree", 2, 5)
    assert (error.message, error.line, error.column) == ("bad tree", 2, 5)


def test_hierarchy():
    assert issubclass(LexError, MatrixLangError)
    assert issubclass(ParseError, MatrixLangError)


def test_runtime_error_joins_the_hierarchy():
    from matrixlang.errors import RuntimeErrorML

    error = RuntimeErrorML("boom", 4, 9)
    assert isinstance(error, MatrixLangError)
    assert str(error) == "[line 4, column 9] boom"


# --- I-1: RecursionError at a boundary with no statement to blame ---------


def test_too_deep_error_joins_the_hierarchy_without_a_position():
    # Interpreter.run's own guard (interpreter.py) has a statement to
    # attach a real line/column to. Lexing, parsing, and rendering are
    # each one recursive descent with no per-statement loop, so there is
    # no honest position to report — None beats a fabricated line 0.
    from matrixlang.errors import TooDeepError

    error = TooDeepError()
    assert isinstance(error, MatrixLangError)
    assert error.line is None
    assert error.column is None
    assert "matrixlang:" not in str(error)
    assert "nested too deeply" in str(error)


def test_recursion_guard_converts_a_raw_recursion_error():
    from matrixlang.errors import TooDeepError, recursion_guard

    def blow_up(n: int) -> int:
        return blow_up(n + 1)

    with pytest.raises(TooDeepError):
        with recursion_guard():
            blow_up(0)


def test_recursion_guard_is_silent_when_nothing_goes_wrong():
    from matrixlang.errors import recursion_guard

    with recursion_guard():
        pass  # must not raise
