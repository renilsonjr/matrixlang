"""The ground truth for generated code.

Operator proposes; this decides. A candidate is never trusted because the
model said it was fine — it is fed to the real lexer, the real parser and,
since Stage 6, a real bounded execution.

**Why running is now part of validating.** Before Stage 6 the language was
small enough that a program which parsed essentially ran. Functions
changed that on their own terms: arity mismatches, calling a non-agent,
and using a `NOTHING` as a value are all runtime errors, so a program can
be syntactically perfect MatrixLang and still fail the moment it starts.
Checking only the syntax would hand Operator a candidate that is wrong in
exactly the way it cannot see.

The dry run is untrusted execution, so it is bounded by the same step
counter the CLI uses, at a visibly lower ceiling. That is safe rather than
merely bounded: a `.rain` program has no file access, no network, no
process spawning and no route into Python.
"""

import io
from dataclasses import dataclass
from enum import Enum, auto

from matrixlang.errors import MatrixLangError, recursion_guard
from matrixlang.interpreter import Interpreter
from matrixlang.lexer import lex
from matrixlang.nodes import Program
from matrixlang.parser import parse

# Generous enough for anything Operator should be writing, small enough
# that a runaway candidate costs milliseconds. Deliberately far below the
# CLI default: a human running their own file has read it and can Ctrl-C;
# generated code has been read by nobody.
DRY_RUN_MAX_STEPS = 20_000


class Stage(Enum):
    """Where a candidate failed. The caller treats these differently."""

    PARSE = auto()
    RUN = auto()
    # Exhausted the budget. Distinct from RUN because it is not proof of a
    # defect — the program may be an infinite loop, or may be legitimately
    # longer than a dry run should wait for.
    LIMIT = auto()


@dataclass(frozen=True)
class Valid:
    program: Program


@dataclass(frozen=True)
class Invalid:
    stage: Stage
    message: str
    line: int
    column: int

    def as_diagnostic(self) -> str:
        """The failure as the toolchain would have printed it.

        Fed back into the next prompt verbatim. Rewriting it into something
        friendlier would hide the exact thing the retry has to fix.
        """
        return f"[line {self.line}, column {self.column}] {self.message}"


def check(source: str, max_steps: int = DRY_RUN_MAX_STEPS) -> Valid | Invalid:
    """Parse and dry-run a candidate. Never raises."""
    try:
        with recursion_guard():
            program = parse(lex(source))
    except MatrixLangError as error:
        return Invalid(Stage.PARSE, error.message, error.line, error.column)

    # Output goes to a buffer that is thrown away. A dry run must not put
    # the candidate's output where a person would mistake it for the real
    # thing, and stdout is where they would.
    try:
        Interpreter(out=io.StringIO(), max_steps=max_steps).run(program)
    except MatrixLangError as error:
        stage = Stage.LIMIT if "step limit" in error.message else Stage.RUN
        return Invalid(stage, error.message, error.line, error.column)

    return Valid(program)
