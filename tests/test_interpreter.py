import io

import pytest

from matrixlang.errors import RuntimeErrorML
from matrixlang.interpreter import Interpreter, run
from matrixlang.lexer import lex
from matrixlang.parser import parse


def output(source: str) -> str:
    """Run a program and return everything it printed."""
    buffer = io.StringIO()
    run(parse(lex(source)), out=buffer)
    return buffer.getvalue()


def env(source: str) -> dict:
    """Run a program and return its final environment."""
    interpreter = Interpreter(out=io.StringIO())
    interpreter.run(parse(lex(source)))
    return interpreter.environment


def test_trace_prints_an_integer_with_a_newline():
    assert output("trace 7\n") == "7\n"


def test_trace_prints_a_string_without_quotes():
    assert output('trace "wake up, Neo"\n') == "wake up, Neo\n"


def test_trace_prints_booleans_in_the_language_s_spelling():
    assert output("trace true\ntrace false\n") == "true\nfalse\n"


def test_several_traces_appear_in_order():
    assert output("trace 1\ntrace 2\ntrace 3\n") == "1\n2\n3\n"


def test_an_empty_program_prints_nothing():
    assert output("") == ""


def test_comments_do_not_execute():
    assert output("# just a comment\ntrace 1  # and another\n") == "1\n"


def test_a_fresh_interpreter_starts_with_an_empty_environment():
    # `construct` does not exist until Task 3, so this task can only assert
    # the empty case. Task 3's test_environment_holds_every_declared_name
    # covers a populated environment.
    assert env("trace 1\n") == {}
