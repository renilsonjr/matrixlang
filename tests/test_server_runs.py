"""OP-D — running a program and streaming its events.

The same shape as `window.py`: the interpreter runs on a worker thread
and pushes into a queue; the consumer drains it. There the consumer was
Tk's `after()`; here it is an HTTP response. No socket in this file.
"""

import pytest

from server.runs import DEADLINE_SECONDS, Runs


def drain(run, limit=100_000):
    """Everything the run emits, until it says it is done.

    The bound is high on purpose: a runaway program emits one statement
    event per executed statement, so the stream is large before either
    guard trips. That is a real property of the stream, not a test
    artefact — see the known limit in server/runs.py.
    """
    seen = []
    for _ in range(limit):
        event = run.next(timeout=2.0)
        seen.append(event)
        if event["kind"] in ("done", "error"):
            break
    return seen


def kinds(events):
    return [e["kind"] for e in events]


# --- Happy path ---------------------------------------------------------


def test_a_program_streams_output_then_done():
    runs = Runs()
    run = runs.start('trace "wake up, Neo"\n')
    events = drain(run)
    assert kinds(events)[-1] == "done"
    assert any(e["kind"] == "output" and e["text"] == "wake up, Neo" for e in events)


def test_statements_arrive_before_the_output_they_produce():
    runs = Runs()
    events = drain(runs.start('trace "hi"\n'))
    assert kinds(events).index("statement") < kinds(events).index("output")


def test_a_loop_streams_each_iteration_as_it_runs():
    # The property C1 existed to make possible: not a burst at the end.
    runs = Runs()
    src = "construct n = 0\ndejavu n < 3\n  trace n\n  n = n + 1\nflatline\n"
    events = drain(runs.start(src))
    assert [e["text"] for e in events if e["kind"] == "output"] == ["0", "1", "2"]


def test_a_run_is_addressable_by_id():
    runs = Runs()
    run = runs.start("trace 1\n")
    assert runs.get(run.id) is run


def test_an_unknown_run_id_is_none_not_an_exception():
    assert Runs().get("nope") is None


# --- Failure ------------------------------------------------------------


def test_a_runtime_error_arrives_as_an_error_event():
    runs = Runs()
    events = drain(runs.start("trace nope\n"))
    assert kinds(events)[-1] == "error"
    assert "not declared" in events[-1]["message"]


def test_a_syntax_error_is_reported_without_starting_a_thread():
    runs = Runs()
    events = drain(runs.start("construct = 5\n"))
    assert kinds(events) == ["error"]
    assert "expected a name" in events[0]["message"]


# --- The two guards -----------------------------------------------------


def test_a_runaway_program_is_stopped_by_the_step_limit():
    # Bounded low so this asserts the guard, not the default budget.
    runs = Runs(max_steps=200)
    events = drain(runs.start("construct n = 0\ndejavu true\n  n = n + 1\nflatline\n"))
    assert kinds(events)[-1] == "error"
    assert "step limit" in events[-1]["message"]


def test_the_server_has_its_own_wall_clock_deadline():
    # Design §4: defence in depth. The step counter bounds work inside the
    # interpreter; this bounds the request even if something outside the
    # interpreter hangs. They protect different failure modes.
    assert DEADLINE_SECONDS > 0


def test_the_deadline_is_enforced():
    # A zero deadline trips on the first emit — deterministic, no sleep,
    # no wall-clock flake in CI.
    runs = Runs(deadline=0.0, max_steps=10_000_000)
    events = drain(runs.start("construct n = 0\ndejavu true\n  n = n + 1\nflatline\n"))
    assert kinds(events)[-1] == "error"
    assert "too long" in events[-1]["message"]


# --- Isolation ----------------------------------------------------------


def test_two_runs_do_not_share_events():
    runs = Runs()
    first = runs.start('trace "first"\n')
    second = runs.start('trace "second"\n')
    texts = {
        e["text"] for e in drain(first) if e["kind"] == "output"
    }
    assert texts == {"first"}
    assert {e["text"] for e in drain(second) if e["kind"] == "output"} == {"second"}


def test_a_finished_run_replays_nothing_and_says_done():
    runs = Runs()
    run = runs.start("trace 1\n")
    drain(run)
    assert run.next(timeout=0.5)["kind"] == "done"


# --- One definition of the wire shape ------------------------------------


def test_the_queue_holds_exactly_what_the_wire_carries():
    # The bug this exists to prevent: `sse.encode` gained a transliterated
    # `glyphs` field for output and the queue did not, so the browser drew
    # Latin with the glyph wall selected while every test of `encode`
    # passed. Both now come from `sse.payload`.
    import json

    from matrixlang.events import Output
    from server.sse import encode

    runs = Runs()
    events = drain(runs.start('trace "wake up, Neo"\n'))
    queued = next(e for e in events if e["kind"] == "output")
    encoded = json.loads(encode(Output(text="wake up, Neo", line=1))[6:])
    assert queued["glyphs"] == encoded["glyphs"]
    assert not any(ch.isascii() and ch.isalnum() for ch in queued["glyphs"])
