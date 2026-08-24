"""Loop control — running wake and glitch end to end."""

import io

import pytest

from matrixlang.errors import RuntimeErrorML
from matrixlang.interpreter import Interpreter
from matrixlang.lexer import lex
from matrixlang.parser import parse


def run(source):
    out = io.StringIO()
    Interpreter(out=out).run(parse(lex(source)))
    return out.getvalue()


def fails(source):
    with pytest.raises(RuntimeErrorML) as caught:
        run(source)
    return caught.value


def test_wake_leaves_the_loop():
    source = (
        "construct n = 0\n"
        "dejavu n < 10\n"
        "  redpill n == 3\n"
        "    wake\n"
        "  flatline\n"
        "  trace n\n"
        "  n = n + 1\n"
        "flatline\n"
    )
    assert run(source) == "0\n1\n2\n"


def test_glitch_skips_to_the_next_iteration():
    source = (
        "construct n = 0\n"
        "dejavu n < 5\n"
        "  n = n + 1\n"
        "  redpill n == 3\n"
        "    glitch\n"
        "  flatline\n"
        "  trace n\n"
        "flatline\n"
    )
    assert run(source) == "1\n2\n4\n5\n"


def test_glitch_re_tests_the_condition():
    # Not "jump to the last statement" -- `glitch` goes back to the top,
    # so a condition that has gone false ends the loop rather than
    # running one more body.
    source = (
        "construct n = 0\n"
        "dejavu n < 3\n"
        "  n = n + 1\n"
        "  glitch\n"
        "flatline\n"
        "trace n\n"
    )
    assert run(source) == "3\n"


def test_wake_leaves_only_the_innermost_loop():
    # `j` is declared once, before the outer loop, and reset with `=`
    # rather than re-declared with `construct` on each outer pass --
    # `construct` inside a loop body that runs more than once is a
    # separate, pre-existing "already declared" error unrelated to
    # wake/glitch, since a loop body does not get a fresh scope per
    # iteration.
    source = (
        "construct i = 0\n"
        "construct j = 0\n"
        "dejavu i < 2\n"
        "  j = 0\n"
        "  dejavu j < 5\n"
        "    redpill j == 1\n"
        "      wake\n"
        "    flatline\n"
        "    trace j\n"
        "    j = j + 1\n"
        "  flatline\n"
        "  trace 9\n"
        "  i = i + 1\n"
        "flatline\n"
    )
    # Inner loop prints 0 then wakes; the OUTER loop keeps going, so the
    # 9 prints twice. If wake broke both, there would be one 9.
    assert run(source) == "0\n9\n0\n9\n"


def test_glitch_belongs_to_the_innermost_loop():
    # Same reset-with-`=` reasoning as above.
    source = (
        "construct i = 0\n"
        "construct j = 0\n"
        "dejavu i < 2\n"
        "  j = 0\n"
        "  dejavu j < 3\n"
        "    j = j + 1\n"
        "    glitch\n"
        "  flatline\n"
        "  trace i\n"
        "  i = i + 1\n"
        "flatline\n"
    )
    assert run(source) == "0\n1\n"


def test_wake_outside_a_loop_is_an_error():
    error = fails("wake\n")
    assert error.message == "'wake' outside a loop"


def test_glitch_outside_a_loop_is_an_error():
    error = fails("glitch\n")
    assert error.message == "'glitch' outside a loop"


def test_an_error_outside_a_loop_carries_its_position():
    error = fails("trace 1\nwake\n")
    assert error.line == 2


def test_the_position_is_the_keywords_not_an_enclosing_statements():
    # Catches `run`'s except _LoopSignal reporting statement.line/column
    # (the outer, top-level `redpill`, line 2) instead of signal.line/
    # signal.column (the `wake` itself, line 4). A bare top-level `wake`
    # can't distinguish the two, since its own position and the
    # enclosing statement's position coincide -- this fixture nests the
    # keyword two `redpill`s deep so they don't.
    source = (
        "trace 0\n"
        "redpill true\n"
        "  redpill true\n"
        "    wake\n"
        "  flatline\n"
        "flatline\n"
    )
    error = fails(source)
    assert error.line == 4
    assert error.column == 5


def test_wake_inside_an_agent_does_not_reach_the_callers_loop():
    # THE case. An agent called from inside a loop must not be able to
    # break that loop -- the agent's body is not inside a loop, so the
    # wake is an error there, exactly as Python's `break` would be.
    source = (
        "agent f()\n"
        "  wake\n"
        "flatline\n"
        "construct n = 0\n"
        "dejavu n < 3\n"
        "  f()\n"
        "  n = n + 1\n"
        "flatline\n"
    )
    error = fails(source)
    assert error.message == "'wake' outside a loop"
    # Catches `_call`'s except _LoopSignal reporting expr.line/expr.column
    # (the call site, line 6) instead of signal.line/signal.column (the
    # `wake` itself, line 2). The brief is explicit that the position
    # must come from the signal, not the call site.
    assert error.line == 2


def test_glitch_inside_an_agent_does_not_reach_the_callers_loop():
    source = (
        "agent f()\n"
        "  glitch\n"
        "flatline\n"
        "construct n = 0\n"
        "dejavu n < 3\n"
        "  f()\n"
        "  n = n + 1\n"
        "flatline\n"
    )
    error = fails(source)
    assert error.message == "'glitch' outside a loop"


def test_a_loop_inside_an_agent_still_works():
    # The other half of the agent boundary: a loop INSIDE an agent
    # catches its own wake normally.
    source = (
        "agent f()\n"
        "  construct n = 0\n"
        "  dejavu n < 10\n"
        "    redpill n == 2\n"
        "      wake\n"
        "    flatline\n"
        "    n = n + 1\n"
        "  flatline\n"
        "  jackout n\n"
        "flatline\n"
        "trace f()\n"
    )
    assert run(source) == "2\n"


def test_jackout_beats_a_loop():
    # A jackout inside a loop inside an agent unwinds PAST the loop to
    # the call site. If the loop caught it, this would print nothing or
    # loop forever.
    source = (
        "agent f()\n"
        "  construct n = 0\n"
        "  dejavu n < 10\n"
        "    redpill n == 4\n"
        "      jackout n\n"
        "    flatline\n"
        "    n = n + 1\n"
        "  flatline\n"
        "  jackout 99\n"
        "flatline\n"
        "trace f()\n"
    )
    assert run(source) == "4\n"


def test_glitch_still_counts_against_the_step_limit():
    # Steps count executed statements, so `glitch` cannot be used to loop
    # without being counted. A loop that glitches forever must hit the
    # limit rather than hang.
    source = "dejavu true\n  glitch\nflatline\n"
    out = io.StringIO()
    with pytest.raises(RuntimeErrorML) as caught:
        Interpreter(out=out, max_steps=50).run(parse(lex(source)))
    assert "step limit" in caught.value.message


def test_wake_still_counts_against_the_step_limit():
    # `wake` can't be tested the same way as `glitch` above: the `While`
    # branch in interpreter.py catches `_Wake` with `break`, not
    # `continue`, so a loop that wakes immediately leaves rather than
    # coming back around. There is no source that makes `wake` alone
    # produce a runaway loop -- the scenario the sibling test above
    # covers for `glitch` cannot happen for `wake` at all, by
    # construction of the mechanism, not by absence of a test for it.
    #
    # What genuinely is `wake`'s relationship to the step limit, and
    # is worth pinning down: reaching `wake` still spends a step like
    # any other statement. It is not a free, uncounted control
    # transfer. A `dejavu true` loop that wakes on its very first
    # statement costs exactly two steps -- the `dejavu` line itself,
    # then `wake` -- and never a third, because `wake` truly leaves.
    # max_steps=1 must fail while executing `wake` (proving `wake` is
    # counted, not skipped); max_steps=2 must be enough to finish
    # (proving it costs no more than that, unlike `glitch`).
    source = "dejavu true\n  wake\nflatline\n"

    out = io.StringIO()
    with pytest.raises(RuntimeErrorML) as caught:
        Interpreter(out=out, max_steps=1).run(parse(lex(source)))
    assert "step limit" in caught.value.message
    assert caught.value.line == 2  # the `wake` statement itself

    out = io.StringIO()
    Interpreter(out=out, max_steps=2).run(parse(lex(source)))  # does not raise
