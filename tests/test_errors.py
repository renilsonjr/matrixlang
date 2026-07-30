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
