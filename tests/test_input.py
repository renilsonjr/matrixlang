"""The input providers, exercised directly.

`events.py` has TextSink and the cascade; this is the same split for the
other direction. Each provider is tested here so the interpreter tests can
use ListSource without wondering whether the source itself is correct.
"""

import io

from matrixlang.input import (
    BufferSource,
    ConstantSource,
    EmptySource,
    ListSource,
    StdinSource,
)


def test_empty_source_is_exhausted_immediately():
    assert EmptySource().next_line() is None


def test_list_source_yields_each_line_then_none():
    source = ListSource(["Neo", "Trinity"])
    assert source.next_line() == "Neo"
    assert source.next_line() == "Trinity"
    assert source.next_line() is None
    # Still exhausted on a second ask -- no wrapping around.
    assert source.next_line() is None


def test_buffer_source_splits_text_into_lines():
    source = BufferSource("Neo\nTrinity\n")
    assert source.next_line() == "Neo"
    assert source.next_line() == "Trinity"
    assert source.next_line() is None


def test_buffer_source_of_empty_text_has_no_lines():
    assert BufferSource("").next_line() is None


def test_stdin_source_strips_only_the_newline():
    # Trailing spaces are content. Python's input() keeps them and so does
    # this -- a program reading "  " should see two spaces, not "".
    source = StdinSource(io.StringIO("Neo  \nTrinity\n"))
    assert source.next_line() == "Neo  "
    assert source.next_line() == "Trinity"
    assert source.next_line() is None


def test_stdin_source_handles_a_final_line_without_a_newline():
    source = StdinSource(io.StringIO("Neo"))
    assert source.next_line() == "Neo"
    assert source.next_line() is None


def test_stdin_source_distinguishes_a_blank_line_from_the_end():
    # readline() returns "\n" for a blank line and "" at EOF. Collapsing
    # the two would make a blank line look like exhaustion.
    source = StdinSource(io.StringIO("\nNeo\n"))
    assert source.next_line() == ""
    assert source.next_line() == "Neo"
    assert source.next_line() is None


def test_constant_source_never_runs_out():
    source = ConstantSource("1")
    assert [source.next_line() for _ in range(3)] == ["1", "1", "1"]
