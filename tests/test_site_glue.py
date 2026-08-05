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
