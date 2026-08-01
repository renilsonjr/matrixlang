"""OP-A — the step limit.

`_execute` is the single place every statement passes through, including
every iteration of a loop body, which makes it the only place that needs
to count.

Deterministic on purpose. A wall-clock timeout would need a clock and a
thread, and a test for it would need `sleep()` and would flake in CI.
This asserts the exact boundary: no raise at `max_steps`, raise at
`max_steps + 1`.
"""

import io

import pytest

from matrixlang.errors import RuntimeErrorML
from matrixlang.interpreter import DEFAULT_MAX_STEPS, Interpreter
from matrixlang.lexer import lex
from matrixlang.parser import parse


def run(source: str, **kwargs):
    Interpreter(out=io.StringIO(), **kwargs).run(parse(lex(source)))


THREE = 'trace 1\ntrace 2\ntrace 3\n'


# --- The exact boundary -------------------------------------------------


def test_a_program_at_the_limit_runs():
    run(THREE, max_steps=3)


def test_a_program_one_step_over_the_limit_raises():
    with pytest.raises(RuntimeErrorML):
        run(THREE, max_steps=2)


def test_the_boundary_is_exact_not_approximate():
    # If the counter is off by one, exactly one of these fails.
    run(THREE, max_steps=3)
    with pytest.raises(RuntimeErrorML):
        run(THREE, max_steps=2)


# --- What it is for -----------------------------------------------------


def test_an_infinite_loop_is_stopped():
    source = "construct n = 0\ndejavu true\n  n = n + 1\nflatline\n"
    with pytest.raises(RuntimeErrorML) as excinfo:
        run(source, max_steps=500)
    assert "step limit" in str(excinfo.value)


def test_loop_body_statements_count_towards_the_limit():
    # Breadth, not depth. A while-true never grows the stack, so a
    # recursion-depth limit would never catch it.
    source = "construct n = 0\ndejavu n < 100\n  n = n + 1\nflatline\n"
    run(source, max_steps=10_000)
    with pytest.raises(RuntimeErrorML):
        run(source, max_steps=50)


# --- The diagnostic -----------------------------------------------------


def test_the_error_carries_the_offending_statement_position():
    source = "construct n = 0\ndejavu true\n  n = n + 1\nflatline\n"
    with pytest.raises(RuntimeErrorML) as excinfo:
        run(source, max_steps=20)
    error = excinfo.value
    assert error.line == 3
    assert error.column > 0


def test_the_error_says_what_probably_happened():
    with pytest.raises(RuntimeErrorML) as excinfo:
        run(THREE, max_steps=1)
    assert "infinite loop" in str(excinfo.value)


# --- Opting out ---------------------------------------------------------


def test_none_disables_the_limit_entirely():
    source = "construct n = 0\ndejavu n < 5000\n  n = n + 1\nflatline\n"
    run(source, max_steps=None)


def test_the_default_is_generous_enough_for_real_programs():
    assert DEFAULT_MAX_STEPS >= 100_000


def test_the_default_applies_when_nothing_is_passed():
    # A limit nobody opts into is a limit nobody gets.
    interpreter = Interpreter(out=io.StringIO())
    assert interpreter._max_steps == DEFAULT_MAX_STEPS


# --- It must not change working programs --------------------------------


def test_output_is_unchanged_for_a_program_well_under_the_limit():
    buffer = io.StringIO()
    Interpreter(out=buffer).run(parse(lex(THREE)))
    assert buffer.getvalue() == "1\n2\n3\n"


# --- The CLI escape hatch -----------------------------------------------


def test_the_cli_applies_the_limit_by_default(tmp_path, capsys):
    from matrixlang.cli import main

    path = tmp_path / "loop.rain"
    path.write_text("construct n = 0\ndejavu true\n  n = n + 1\nflatline\n")
    assert main(["run", "--no-window", str(path)]) == 1
    assert "step limit" in capsys.readouterr().err


def test_max_steps_zero_removes_the_limit(tmp_path, capsys):
    # A limit with no way out would break a legitimately long program.
    from matrixlang.cli import main

    path = tmp_path / "long.rain"
    path.write_text("construct n = 0\ndejavu n < 3000\n  n = n + 1\nflatline\n")
    assert main(["run", "--no-window", "--max-steps", "0", str(path)]) == 0


def test_max_steps_can_be_lowered(tmp_path, capsys):
    from matrixlang.cli import main

    path = tmp_path / "short.rain"
    path.write_text("trace 1\ntrace 2\ntrace 3\n")
    assert main(["run", "--no-window", "--max-steps", "2", str(path)]) == 1
