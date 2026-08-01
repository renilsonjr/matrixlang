"""OP-B — building the context Operator is given.

Pure. No network, no SDK, no key. The whole point of separating this from
`client.py` is that what the model is told can be tested.
"""

from matrixlang.operator.prompt import build
from matrixlang.operator.validate import Invalid, Stage
from matrixlang.tokens import KEYWORDS


def test_the_request_appears_in_the_prompt():
    assert "count down from three" in build("count down from three")


def test_every_keyword_is_described():
    # Read from KEYWORDS rather than retyped. A hardcoded list is how the
    # deleted web/interpreter.js drifted from the language it claimed to
    # implement, and a prompt that lies about the grammar is worse than
    # one that is merely stale.
    prompt = build("anything")
    for keyword in KEYWORDS:
        assert keyword in prompt


def test_the_stage_6_keywords_are_present_without_being_retyped():
    prompt = build("anything")
    assert "agent" in prompt
    assert "jackout" in prompt


def test_the_prompt_carries_a_worked_example():
    prompt = build("anything")
    assert "flatline" in prompt
    assert "trace" in prompt


def test_the_rules_a_model_gets_wrong_are_stated():
    prompt = build("anything")
    lowered = prompt.lower()
    # Each of these is a real way MatrixLang differs from what a model
    # will assume by default.
    assert "boolean" in lowered          # conditions are not truthy
    assert "construct" in lowered        # declare before assign
    assert "flatline" in lowered         # blocks are keyword-delimited


# --- Retry feedback -----------------------------------------------------


def test_a_retry_includes_the_previous_attempt():
    failure = Invalid(Stage.PARSE, "expected a name", 1, 9)
    prompt = build("x", previous="construct = 5\n", failure=failure)
    assert "construct = 5" in prompt


def test_a_retry_includes_the_real_diagnostic():
    failure = Invalid(Stage.PARSE, "expected a name", 1, 9)
    prompt = build("x", previous="construct = 5\n", failure=failure)
    assert "expected a name" in prompt
    assert "line 1" in prompt


def test_a_run_failure_says_it_parsed_but_did_not_run():
    # A model told only "that was wrong" will often retry the same syntax.
    # Naming the stage is what makes the retry informed.
    failure = Invalid(Stage.RUN, "agent 'add' takes 2 arguments, got 1", 4, 7)
    prompt = build("x", previous="...", failure=failure)
    assert "parsed" in prompt.lower()


def test_a_limit_failure_says_it_did_not_finish():
    failure = Invalid(Stage.LIMIT, "program exceeded the step limit", 2, 1)
    prompt = build("x", previous="...", failure=failure)
    assert "finish" in prompt.lower() or "loop" in prompt.lower()


def test_a_first_attempt_has_no_retry_section():
    assert "attempt" not in build("x").lower()


# --- Purity -------------------------------------------------------------


def test_building_a_prompt_touches_no_network_and_no_sdk():
    import sys

    before = set(sys.modules)
    build("anything")
    new = set(sys.modules) - before
    assert not any(m.split(".")[0] in {"anthropic", "httpx", "socket"} for m in new)


def test_the_prompt_is_deterministic():
    assert build("same request") == build("same request")
