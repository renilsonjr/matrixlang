"""OP-C — the generate → validate → retry cycle.

**No test in this file makes an API call.** The loop takes a client, and
every test passes a stub. That is the whole reason `client.py` and
`loop.py` are separate modules: the orchestration is the part worth
testing, and it must be testable without a key, a network, or a bill.
"""

import pytest

from matrixlang.operator.loop import MAX_ATTEMPTS, Outcome, run
from matrixlang.operator.validate import Stage

GOOD = 'trace "wake up, Neo"\n'
BAD_SYNTAX = "construct = 5\n"
BAD_RUNTIME = "agent add(a, b)\n  jackout a\nflatline\ntrace add(1)\n"
ENDLESS = "construct n = 0\ndejavu true\n  n = n + 1\nflatline\n"


class Stub:
    """A client that replays a fixed script and records what it was asked."""

    def __init__(self, *responses):
        self.responses = list(responses)
        self.prompts: list[str] = []

    def generate(self, prompt: str) -> str:
        self.prompts.append(prompt)
        return self.responses[min(len(self.prompts) - 1, len(self.responses) - 1)]


# --- Succeeding ---------------------------------------------------------


def test_a_good_first_attempt_stops_immediately():
    client = Stub(GOOD)
    outcome = run("say hello", client)
    assert outcome.succeeded
    assert len(outcome.attempts) == 1
    assert len(client.prompts) == 1


def test_the_program_comes_back_parsed():
    outcome = run("say hello", Stub(GOOD))
    assert outcome.program is not None
    assert outcome.source == GOOD


def test_a_retry_can_succeed():
    outcome = run("say hello", Stub(BAD_SYNTAX, GOOD))
    assert outcome.succeeded
    assert len(outcome.attempts) == 2


# --- Retrying -----------------------------------------------------------


def test_the_diagnostic_is_fed_back_into_the_next_prompt():
    # The whole point of the cycle. Without this the retry is a coin flip.
    client = Stub(BAD_SYNTAX, GOOD)
    run("say hello", client)
    assert "expected a name" in client.prompts[1]
    assert BAD_SYNTAX.strip() in client.prompts[1]


def test_the_first_prompt_carries_no_retry_context():
    client = Stub(GOOD)
    run("say hello", client)
    assert "rejected" not in client.prompts[0].lower()


def test_a_runtime_failure_is_retried_too():
    # Not just syntax. Stage 6 made "parses" and "runs" diverge.
    client = Stub(BAD_RUNTIME, GOOD)
    outcome = run("add two numbers", client)
    assert outcome.succeeded
    assert outcome.attempts[0].failure.stage is Stage.RUN


def test_an_endless_program_is_retried_as_a_limit_failure():
    client = Stub(ENDLESS, GOOD)
    outcome = run("count", client)
    assert outcome.attempts[0].failure.stage is Stage.LIMIT
    assert outcome.succeeded


# --- The ceiling --------------------------------------------------------


def test_the_retry_ceiling_is_three():
    # OP-4. Three attempts, then stop — not a silent infinite loop.
    assert MAX_ATTEMPTS == 3


def test_it_stops_after_the_ceiling():
    client = Stub(BAD_SYNTAX)
    outcome = run("say hello", client)
    assert not outcome.succeeded
    assert len(outcome.attempts) == MAX_ATTEMPTS
    assert len(client.prompts) == MAX_ATTEMPTS


def test_the_last_diagnostic_reaches_the_caller():
    # On exhaustion the user must see what actually went wrong, not a
    # generic "Operator failed".
    outcome = run("say hello", Stub(BAD_SYNTAX))
    assert outcome.failure is not None
    assert "expected a name" in outcome.failure.message


def test_the_ceiling_is_adjustable():
    client = Stub(BAD_SYNTAX)
    outcome = run("say hello", client, max_attempts=1)
    assert len(outcome.attempts) == 1


def test_an_exhausted_outcome_has_no_program():
    outcome = run("say hello", Stub(BAD_SYNTAX))
    assert outcome.program is None
    assert outcome.source is None


# --- Every attempt is recorded ------------------------------------------


def test_every_attempt_is_recorded_with_its_source_and_failure():
    # Design §9: every retry is a paid API call. Log attempts from day
    # one, before any cap on spend exists.
    outcome = run("say hello", Stub(BAD_SYNTAX, BAD_RUNTIME, GOOD))
    assert [a.number for a in outcome.attempts] == [1, 2, 3]
    assert outcome.attempts[0].failure.stage is Stage.PARSE
    assert outcome.attempts[1].failure.stage is Stage.RUN
    assert outcome.attempts[2].failure is None
    assert outcome.attempts[0].source == BAD_SYNTAX


def test_the_outcome_reports_how_many_calls_were_made():
    outcome = run("say hello", Stub(BAD_SYNTAX))
    assert outcome.calls == MAX_ATTEMPTS


# --- Robustness against a hostile model ---------------------------------


def test_a_fenced_reply_is_unwrapped():
    # Models wrap code in fences even when told not to. Failing on that
    # would burn a paid retry on a formatting habit.
    fenced = '```\ntrace "wake up, Neo"\n```'
    assert run("say hello", Stub(fenced)).succeeded


def test_a_language_tagged_fence_is_unwrapped():
    fenced = '```matrixlang\ntrace "wake up, Neo"\n```'
    assert run("say hello", Stub(fenced)).succeeded


def test_an_empty_reply_is_a_failure_not_a_crash():
    outcome = run("say hello", Stub(""))
    assert not outcome.succeeded
    assert outcome.failure is not None


def test_a_client_that_raises_does_not_take_the_process_with_it():
    class Broken:
        def generate(self, prompt):
            raise RuntimeError("network went away")

    outcome = run("say hello", Broken())
    assert not outcome.succeeded
    assert "network went away" in outcome.failure.message
