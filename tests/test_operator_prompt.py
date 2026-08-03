"""OP-B — building the context Operator is given.

Pure. No network, no SDK, no key. The whole point of separating this from
`client.py` is that what the model is told can be tested.
"""

from matrixlang.operator.prompt import _EXAMPLE, _RULES, build
from matrixlang.operator.validate import Invalid, Stage, check
from matrixlang.tokens import KEYWORDS
from matrixlang.values import Function, type_name


def test_the_request_appears_in_the_prompt():
    assert "count down from three" in build("count down from three")


def test_every_keyword_is_explained_or_demonstrated():
    # NOT build(): build() always appends a derived "Keywords: ..." line
    # from tokens.KEYWORDS, so any test that checks `keyword in build(...)`
    # is satisfied by construction regardless of what _RULES or _EXAMPLE
    # actually say. That is why the previous guard (test_every_keyword_is_
    # described, now removed) stayed green when Stage 9 added three
    # keywords with no rule or example covering them. Asserting against
    # _RULES + _EXAMPLE directly is the only way this can go red.
    body = _RULES + _EXAMPLE
    missing = sorted(k for k in KEYWORDS if k not in body)
    assert not missing, f"never explained or shown: {missing}"


def test_every_type_name_is_mentioned():
    # This gap has been missed in two consecutive stage plans: Stage 7
    # shipped a prompt that said "no lists" after lists existed, and this
    # stage shipped one silent about strings being indexable and
    # orderable. Derive the type names from `type_name` itself — one
    # representative value per type — rather than retyping the list, for
    # the same reason the keyword line above is derived and not retyped:
    # a hardcoded copy can drift from the thing it is supposed to track.
    sample_values = [1, True, "x", [], Function("f", [], [], None)]
    type_names = {type_name(value) for value in sample_values}
    assert type_names == {"integer", "boolean", "string", "list", "agent"}

    prompt = build("anything").lower()
    missing = sorted(name for name in type_names if name not in prompt)
    assert not missing, (
        f"the prompt never mentions the type name(s) {missing} — "
        "a model told to write MatrixLang has no signal that this type "
        "exists. Add it to _RULES in src/matrixlang/operator/prompt.py."
    )


def test_the_prompt_carries_a_worked_example():
    # Assert that _EXAMPLE's own text is embedded in build()'s output --
    # not just that some keyword like "flatline" or "trace" occurs
    # somewhere in it. Both of those are entries in KEYWORDS and would
    # appear via build()'s derived "Keywords: ..." line even if the
    # "A complete example:\n\n" + _EXAMPLE line were deleted from build()
    # entirely, which is exactly the mutation this test exists to catch.
    assert _EXAMPLE in build("anything")


def test_the_worked_example_is_a_valid_program():
    # _EXAMPLE is never parsed by anything else. A prompt that ships a
    # broken example teaches the model to write broken programs.
    result = check(_EXAMPLE + "\n")
    assert not isinstance(result, Invalid), result


def test_the_rules_a_model_gets_wrong_are_stated():
    # Assert against _RULES directly, not build(): build()'s derived
    # "Keywords: ..." line already contains "construct" and "flatline"
    # regardless of what _RULES says, so checking `x in build(...)` for a
    # keyword proves nothing about whether the RULE explaining it exists.
    # "boolean" is not a keyword, so it is the one part of the original
    # test that was not already tautological.
    lowered = _RULES.lower()
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
