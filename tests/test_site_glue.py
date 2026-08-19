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
