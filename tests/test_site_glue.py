"""The playground's Python half, exercised under CPython.

site/glue.py is what the browser calls once Pyodide is up. Keeping it
Python rather than JavaScript is what lets the existing suite cover the
playground's logic — the project does not acquire a browser-automation
rig, and a refactor of server/sse.py that would break the page fails
here instead of silently in production.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "site"))

import glue  # noqa: E402


def test_write_turns_a_request_into_source():
    result = glue.write("add 5 and 3")
    assert result["ok"] is True
    assert result["source"].strip() == "trace 5 + 3"


def test_write_reports_a_miss_with_a_hint():
    result = glue.write("sort a list")
    assert result["ok"] is False
    assert result["error"]
    assert result["hint"] == "make a list of <values>"


def test_write_on_an_empty_request_is_a_miss():
    result = glue.write("")
    assert result["ok"] is False


def test_run_returns_wire_shaped_output_events():
    events = glue.run('trace "wake up"\n')
    outputs = [e for e in events if e["kind"] == "output"]
    assert len(outputs) == 1
    assert outputs[0]["text"] == "wake up"
    # `glyphs` is what the cascade draws. Its presence here is the point:
    # the page never transliterates in JavaScript.
    assert outputs[0]["glyphs"]
    assert "wake up" not in outputs[0]["glyphs"]


def test_run_reports_a_parse_error_rather_than_raising():
    events = glue.run("construct = 5\n")
    assert events[-1]["kind"] == "error"
    assert "line 1" in events[-1]["message"]


def test_run_reports_the_step_limit_rather_than_hanging():
    source = "construct i = 1\ndejavu true\n  i = i + 1\nflatline\n"
    events = glue.run(source, max_steps=500)
    assert events[-1]["kind"] == "error"
    assert "step limit" in events[-1]["message"]


def test_operator_prompt_comes_from_the_package():
    prompt = glue.operator_prompt("count from 1 to 10")
    # The request is embedded, not appended by the caller.
    assert "count from 1 to 10" in prompt
    # Keywords are read from tokens.py, not retyped — spot-check two that
    # arrived in different stages.
    assert "jackout" in prompt and "splice" in prompt


def test_operator_prompt_pulls_in_no_sdk():
    """The page must stay usable without the optional `anthropic` extra."""
    import subprocess
    import sys

    code = (
        "import sys; sys.path.insert(0, 'site');"
        "import glue; glue.operator_prompt('add 1 and 2');"
        "print('anthropic' in sys.modules)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "False"


def test_glyph_renders_the_glyph_face_of_arbitrary_source():
    from matrixlang.lexer import lex
    from matrixlang.parser import parse

    result = glue.glyph("trace 5 + 3")
    assert result["ok"] is True
    assert parse(lex(result["glyph"])) == parse(lex("trace 5 + 3"))
    assert result["glyph"] != "trace 5 + 3"  # really the glyph face


def test_glyph_of_invalid_source_is_an_error():
    result = glue.glyph("trace )(")
    assert result["ok"] is False
    assert "error" in result


def test_transliterate_text_round_trips():
    original = "Neo woke up"
    glyphs = glue.transliterate_text(original)
    assert glyphs != original
    assert glue.untransliterate_text(glyphs) == original


def test_transliterate_text_matches_the_real_table():
    from matrixlang.translit import transliterate

    assert glue.transliterate_text("hello") == transliterate("hello")


def test_readers_table_documents_the_markers():
    table = glue.readers_table()
    assert "marks the next glyph as uppercase" in table
    assert "marks the next character as literal" in table


def test_run_reads_supplied_input():
    events = glue.run('construct name = jackin\ntrace "Hello, " + name\n', stdin="Neo\n")
    outputs = [e for e in events if e["kind"] == "output"]
    assert [o["text"] for o in outputs] == ["Hello, Neo"]


def test_run_without_input_reports_the_shortfall_rather_than_raising():
    # Never raises -- the JS side walks one list and has no error path.
    events = glue.run("trace jackin\n")
    assert events[-1]["kind"] == "error"
    assert "no input left to read" in events[-1]["message"]


def test_run_reports_an_over_long_decode_rather_than_raising():
    # `run` promises never to raise and the JS caller has no error path,
    # so a raw ValueError out of int() breaks the playground rather than
    # showing a diagnostic. Reachable with no input at all, straight from
    # the editor -- CPython refuses int(str) past 4300 digits.
    too_long = "9" * (sys.int_info.default_max_str_digits + 1)
    events = glue.run(f'trace decode "{too_long}"\n')
    assert events[-1]["kind"] == "error"
    assert "decode" in events[-1]["message"]


def test_run_reports_an_over_long_number_rather_than_raising():
    # The mirror of the decode case above, and the one a program reaches
    # with no input at all: CPython refuses str(int) past 4300 digits, so
    # a number built by squaring breaks `trace` and `encode` alike. `run`
    # catches MatrixLangError and nothing else, so a bare ValueError out
    # of values.py would leave the playground with an unhandled exception
    # instead of an error event.
    squared = "construct n = 10\nconstruct i = 0\ndejavu i < 13\n  n = n * n\n  i = i + 1\nflatline\n"

    traced = glue.run(squared + "trace n\n")
    assert traced[-1]["kind"] == "error"
    assert "cannot display a number longer than" in traced[-1]["message"]

    encoded = glue.run(squared + "trace encode n\n")
    assert encoded[-1]["kind"] == "error"
    assert "encode" in encoded[-1]["message"]


def test_run_reports_an_over_long_number_literal_rather_than_raising():
    # The third door to the same CPython ceiling, and the one that needs
    # no arithmetic at all: a long enough run of digits typed -- or
    # pasted -- straight into the editor. `run` catches MatrixLangError
    # and nothing else, so the bare ValueError out of the lexer's int()
    # left the playground with an unhandled exception rather than an
    # error event, exactly as the two above did.
    events = glue.run("trace " + "1" * (sys.int_info.default_max_str_digits + 1) + "\n")
    assert events[-1]["kind"] == "error"
    assert "number too long to read" in events[-1]["message"]


def test_an_empty_input_box_is_named_when_a_program_runs_out_of_input():
    # "no input left to read" is correct and stays surface-neutral -- the CLI
    # and the REPL share it. But glue.py IS the browser, so it can say which
    # box is empty. Without this the reader is told what happened and not
    # where to fix it, which is what actually happened on the live page.
    events = glue.run("trace jackin\n", stdin="")
    assert events[-1]["kind"] == "error"
    message = events[-1]["message"]
    assert "no input left to read" in message
    assert "Input box" in message


def test_a_part_filled_input_box_says_it_ran_short_not_that_it_is_empty():
    # Supplying one line to a program that reads two is a different mistake,
    # and "the box is empty" would be a lie.
    events = glue.run("trace jackin\ntrace jackin\n", stdin="Neo\n")
    message = events[-1]["message"]
    assert "no input left to read" in message
    assert "Input box" in message
    assert "empty" not in message


def test_an_unrelated_runtime_error_gains_no_input_guidance():
    # The guidance must be narrow. A type error has nothing to do with input.
    events = glue.run('trace "id " + 1\n')
    message = events[-1]["message"]
    assert "cannot add" in message
    assert "Input box" not in message


def test_running_the_same_program_twice_gives_the_same_events():
    # THE load-bearing property. Interactive input re-runs a program once per
    # prompt and shows the reader a continuous history, which is only honest
    # because a re-run reproduces the previous run exactly. If MatrixLang ever
    # gains randomness, a clock, or any effect beyond `trace`, this fails --
    # and it should, because the interactive design breaks silently otherwise.
    source = 'construct a = jackin\ntrace "got " + a\ntrace 1 + 1\n'

    def stream(stdin):
        return [(e["kind"], e.get("text") or e.get("message") or "") for e in glue.run(source, stdin=stdin)]

    assert stream("ana") == stream("ana")


def test_fewer_answers_produce_a_prefix_of_the_output():
    # The other half of the property: round n+1 must reproduce everything
    # round n showed, in order, before adding anything new. That is what lets
    # playground.js feed the cascade only the new suffix instead of replaying
    # the whole animation on every answer.
    source = 'trace "first"\nconstruct a = jackin\ntrace "then " + a\n'

    def outputs(stdin):
        return [e["text"] for e in glue.run(source, stdin=stdin) if e["kind"] == "output"]

    short = outputs("")
    long = outputs("ana")
    assert short == ["first"]
    assert long == ["first", "then ana"]
    assert long[: len(short)] == short, "a longer answer list changed earlier output"
