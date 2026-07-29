"""Error hierarchy for the MatrixLang toolchain.

Every error carries a line and column. Stage 2 and Stage 3 add siblings to
LexError rather than inventing their own reporting.
"""


class MatrixLangError(Exception):
    """Base class for every error raised by MatrixLang."""

    def __init__(self, message: str, line: int, column: int) -> None:
        self.message = message
        self.line = line
        self.column = column
        super().__init__(f"[line {line}, column {column}] {message}")


class LexError(MatrixLangError):
    """The scanner could not turn the source into tokens."""
