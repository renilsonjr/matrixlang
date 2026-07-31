"""C1 — the execution event stream.

The interpreter no longer prints. It emits events into a sink, and the
default sink prints exactly what printing used to print. That is the
property the whole design rests on: stdout is byte-identical, so the
existing suite is the proof this refactor changed no behaviour.
"""

import io

import pytest

from matrixlang.events import Error, Output, Statement, TextSink
from matrixlang.interpreter import Interpreter, run
from matrixlang.lexer import lex
from matrixlang.parser import parse


class Recorder:
    """A sink that keeps every event, so tests can assert on the stream."""

    def __init__(self) -> None:
        self.events: list[object] = []

    def emit(self, event: object) -> None:
        self.events.append(event)


def events(source: str) -> list[object]:
    recorder = Recorder()
    Interpreter(sink=recorder).run(parse(lex(source)))
    return recorder.events


def outputs(source: str) -> list[Output]:
    return [e for e in events(source) if isinstance(e, Output)]


def statements(source: str) -> list[Statement]:
    return [e for e in events(source) if isinstance(e, Statement)]


# --- Output events ------------------------------------------------------


def test_a_trace_emits_an_output_event_carrying_the_displayed_text():
    assert [e.text for e in outputs('trace "wake up, Neo"\n')] == ["wake up, Neo"]


def test_an_integer_is_carried_already_displayed_not_as_an_int():
    # The sink must not need values.to_display; the event is display-ready.
    (event,) = outputs("trace 7\n")
    assert event.text == "7"


def test_output_events_carry_the_source_line():
    (event,) = outputs('construct n = 1\ntrace n\n')
    assert event.line == 2


def test_a_loop_emits_one_output_event_per_iteration():
    source = "construct n = 0\ndejavu n < 3\n  trace n\n  n = n + 1\nflatline\n"
    assert [e.text for e in outputs(source)] == ["0", "1", "2"]


# --- Statement events ---------------------------------------------------


def test_each_executed_statement_emits_a_statement_event():
    source = 'construct name = "Neo"\ntrace name\n'
    assert [e.line for e in statements(source)] == [1, 2]


def test_a_statement_event_carries_the_node_so_the_display_can_render_it():
    (declare, _trace) = statements('construct name = "Neo"\ntrace name\n')
    assert declare.node.name == "name"


def test_a_loop_body_emits_a_statement_event_per_iteration():
    # This is what makes a dejavu loop cascade while it runs rather than
    # arriving as a burst when it finishes.
    source = "construct n = 0\ndejavu n < 2\n  n = n + 1\nflatline\n"
    bodies = [e for e in statements(source) if e.line == 3]
    assert len(bodies) == 2


# --- The TextSink equivalence property ----------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "trace 7\n",
        'trace "wake up, Neo"\n',
        "trace true\n",
        "construct n = 0\ndejavu n < 3\n  trace n\n  n = n + 1\nflatline\n",
        'construct n = 1\nredpill n == 1\n  trace "yes"\nbluepill\n  trace "no"\nflatline\n',
    ],
)
def test_the_text_sink_prints_exactly_what_the_interpreter_used_to_print(source):
    buffer = io.StringIO()
    run(parse(lex(source)), out=buffer)

    expected = io.StringIO()
    Interpreter(sink=TextSink(expected)).run(parse(lex(source)))

    assert buffer.getvalue() == expected.getvalue()


def test_the_text_sink_ignores_statement_events():
    # Only Output reaches stdout. If Statement events printed, every
    # program's output would gain a line per statement.
    buffer = io.StringIO()
    sink = TextSink(buffer)
    sink.emit(Statement(node=None, line=1))
    assert buffer.getvalue() == ""


def test_the_text_sink_writes_an_error_event_to_nothing_by_default():
    # Diagnostics travel their own path (stderr, via the CLI). The text
    # sink is stdout only, and an error must not contaminate it.
    buffer = io.StringIO()
    sink = TextSink(buffer)
    sink.emit(Error(message="boom"))
    assert buffer.getvalue() == ""


# --- Backwards compatibility -------------------------------------------


def test_out_still_works_and_is_equivalent_to_a_text_sink():
    # 645 existing tests construct Interpreter(out=...). That must keep
    # working, or the refactor is not a refactor.
    buffer = io.StringIO()
    Interpreter(out=buffer).run(parse(lex("trace 7\n")))
    assert buffer.getvalue() == "7\n"
