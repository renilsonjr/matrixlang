"""Stage 6 — executing agents: scope, closures, calls, jackout, NOTHING."""

import io

import pytest

from matrixlang.errors import RuntimeErrorML
from matrixlang.interpreter import Interpreter
from matrixlang.lexer import lex
from matrixlang.parser import parse


def output(source: str) -> str:
    buffer = io.StringIO()
    Interpreter(out=buffer).run(parse(lex(source)))
    return buffer.getvalue()


def fails(source: str) -> RuntimeErrorML:
    with pytest.raises(RuntimeErrorML) as excinfo:
        output(source)
    return excinfo.value


# --- Calling ------------------------------------------------------------


def test_an_agent_returns_a_value():
    assert output("agent two()\n  jackout 2\nflatline\ntrace two()\n") == "2\n"


def test_parameters_are_bound_by_the_call():
    src = "agent double(n)\n  jackout n * 2\nflatline\ntrace double(21)\n"
    assert output(src) == "42\n"


def test_several_arguments():
    src = "agent add(a, b)\n  jackout a + b\nflatline\ntrace add(1, 2)\n"
    assert output(src) == "3\n"


def test_recursion_works():
    src = (
        "agent fib(n)\n"
        "  redpill n < 2\n"
        "    jackout n\n"
        "  flatline\n"
        "  jackout fib(n - 1) + fib(n - 2)\n"
        "flatline\n"
        "trace fib(10)\n"
    )
    assert output(src) == "55\n"


def test_an_agent_can_be_called_for_its_effect_alone():
    src = 'agent shout()\n  trace "wake up"\nflatline\nshout()\n'
    assert output(src) == "wake up\n"


# --- Scope --------------------------------------------------------------


def test_a_body_can_read_a_global():
    src = 'construct name = "Neo"\nagent hi()\n  jackout name\nflatline\ntrace hi()\n'
    assert output(src) == "Neo\n"


def test_a_local_does_not_leak_out():
    src = "agent f()\n  construct hidden = 1\n  jackout hidden\nflatline\ntrace f()\ntrace hidden\n"
    assert "not declared" in str(fails(src))


def test_a_local_may_shadow_a_global():
    src = (
        "construct n = 1\n"
        "agent f()\n"
        "  construct n = 99\n"
        "  jackout n\n"
        "flatline\n"
        "trace f()\n"
        "trace n\n"
    )
    assert output(src) == "99\n1\n"


def test_assignment_finds_the_nearest_existing_binding():
    src = (
        "construct n = 1\n"
        "agent bump()\n"
        "  n = n + 1\n"
        "  jackout n\n"
        "flatline\n"
        "trace bump()\n"
        "trace n\n"
    )
    assert output(src) == "2\n2\n"


def test_redeclaring_in_the_same_scope_is_still_an_error():
    src = "agent f()\n  construct x = 1\n  construct x = 2\n  jackout x\nflatline\ntrace f()\n"
    assert "already declared" in str(fails(src))


def test_each_call_gets_its_own_environment():
    src = (
        "agent count(n)\n"
        "  construct seen = n\n"
        "  jackout seen\n"
        "flatline\n"
        "trace count(1)\n"
        "trace count(2)\n"
    )
    assert output(src) == "1\n2\n"


# --- Closures -----------------------------------------------------------


def test_an_inner_agent_captures_its_defining_scope():
    src = (
        "agent adder(n)\n"
        "  agent add(m)\n"
        "    jackout n + m\n"
        "  flatline\n"
        "  jackout add\n"
        "flatline\n"
        "construct add5 = adder(5)\n"
        "trace add5(3)\n"
    )
    assert output(src) == "8\n"


def test_a_captured_environment_outlives_the_call_that_made_it():
    src = (
        "agent make()\n"
        "  construct secret = 7\n"
        "  agent reveal()\n"
        "    jackout secret\n"
        "  flatline\n"
        "  jackout reveal\n"
        "flatline\n"
        "construct r = make()\n"
        "trace r()\n"
    )
    assert output(src) == "7\n"


def test_two_closures_do_not_share_state():
    src = (
        "agent adder(n)\n"
        "  agent add(m)\n"
        "    jackout n + m\n"
        "  flatline\n"
        "  jackout add\n"
        "flatline\n"
        "construct a = adder(1)\n"
        "construct b = adder(100)\n"
        "trace a(0)\n"
        "trace b(0)\n"
    )
    assert output(src) == "1\n100\n"


def test_an_agent_is_a_value_that_can_be_passed():
    src = (
        "agent twice(f, x)\n"
        "  jackout f(f(x))\n"
        "flatline\n"
        "agent inc(n)\n"
        "  jackout n + 1\n"
        "flatline\n"
        "trace twice(inc, 5)\n"
    )
    assert output(src) == "7\n"


# --- Errors -------------------------------------------------------------


def test_too_few_arguments():
    error = fails("agent add(a, b)\n  jackout a\nflatline\ntrace add(1)\n")
    assert "takes 2" in str(error)
    assert error.line > 0


def test_too_many_arguments():
    error = fails("agent one(a)\n  jackout a\nflatline\ntrace one(1, 2)\n")
    assert "takes 1" in str(error)


def test_calling_something_that_is_not_an_agent():
    error = fails("construct n = 1\ntrace n(1)\n")
    assert "not an agent" in str(error)


def test_jackout_outside_an_agent():
    assert "outside" in str(fails("jackout 1\n"))


# --- NOTHING ------------------------------------------------------------


def test_an_agent_that_never_jacks_out_may_be_called_as_a_statement():
    assert output('agent log()\n  trace "hi"\nflatline\nlog()\n') == "hi\n"


def test_using_a_nothing_as_a_value_is_an_error():
    error = fails('agent log()\n  trace "hi"\nflatline\ntrace log()\n')
    assert "did not jack out" in str(error)
    assert error.line > 0


def test_a_bare_jackout_produces_nothing():
    src = 'agent f()\n  jackout\n  trace "unreachable"\nflatline\nf()\n'
    assert output(src) == ""


def test_nothing_can_never_be_stored():
    error = fails('agent log()\n  trace "hi"\nflatline\nconstruct x = log()\n')
    assert "did not jack out" in str(error)


def test_nothing_as_a_redpill_condition_says_did_not_jack_out():
    # _condition used to call _evaluate rather than _value_of, so NOTHING
    # survived into type_name's fallback and the error read "condition
    # must be a boolean, got _Nothing" — a Python class name in a
    # user-facing diagnostic. It must read the same as every other place
    # NOTHING is used as a value.
    src = "agent f()\n  jackout\nflatline\nredpill f()\n  trace 1\nflatline\n"
    error = fails(src)
    assert "did not jack out" in str(error)
    assert "_Nothing" not in str(error)


def test_nothing_as_a_dejavu_condition_says_did_not_jack_out():
    src = "agent f()\n  jackout\nflatline\ndejavu f()\n  trace 1\nflatline\n"
    error = fails(src)
    assert "did not jack out" in str(error)
    assert "_Nothing" not in str(error)


# --- Display ------------------------------------------------------------


def test_an_agent_displays_with_its_own_name():
    out = output("agent fib(n)\n  jackout n\nflatline\ntrace fib\n")
    assert out == "<agent fib>\n"
    assert "matrixlang" not in out
    assert "0x" not in out


def test_an_agent_in_a_type_error_reads_as_agent():
    error = fails("agent f()\n  jackout 1\nflatline\ntrace f + 1\n")
    assert "agent" in str(error)
    assert "Function" not in str(error)


def test_a_nested_jackout_outside_an_agent_reports_the_keywords_position():
    # Catches run()'s `except _Jackout` reporting statement.line/column --
    # the outer, top-level `redpill` on line 2 -- instead of the `jackout`
    # the reader typed on line 4. A bare top-level `jackout` cannot tell the
    # two apart, because its own position and the enclosing statement's
    # coincide; this nests it two `redpill`s deep so they don't.
    #
    # `wake` in this identical shape already reports line 4, because
    # _LoopSignal carries its own position and _Jackout does not. Two
    # control-flow signals in one interpreter, one reporting the keyword and
    # one reporting its enclosing block, reads as an accident rather than a
    # decision. See test_loops_run.py::
    # test_the_position_is_the_keywords_not_an_enclosing_statements.
    source = (
        "trace 0\n"
        "redpill true\n"
        "  redpill true\n"
        "    jackout 1\n"
        "  flatline\n"
        "flatline\n"
    )
    error = fails(source)
    assert error.message == "'jackout' outside an agent"
    assert error.line == 4
    assert error.column == 5
