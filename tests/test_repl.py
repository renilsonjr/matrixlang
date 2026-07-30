import io

from matrixlang.repl import Repl, repl


def feed_all(lines: list[str]) -> str:
    """Feed lines to a Repl and return everything it printed."""
    buffer = io.StringIO()
    session = Repl(out=buffer)
    for line in lines:
        session.feed(line)
    return buffer.getvalue()


def test_a_single_statement_executes_immediately():
    assert feed_all(["trace 1"]) == "1\n"


def test_state_persists_between_lines():
    assert feed_all(["construct x = 5", "trace x"]) == "5\n"


def test_a_block_waits_for_flatline():
    buffer = io.StringIO()
    session = Repl(out=buffer)
    assert session.feed("dejavu false") is True
    assert session.feed("  trace 1") is True
    assert session.feed("flatline") is False
    assert buffer.getvalue() == ""


def test_a_loop_typed_at_the_prompt_runs():
    printed = feed_all(
        ["construct n = 1", "dejavu n <= 3", "  trace n", "  n = n + 1", "flatline"]
    )
    assert printed == "1\n2\n3\n"


def test_nested_blocks_need_both_flatlines():
    buffer = io.StringIO()
    session = Repl(out=buffer)
    session.feed("redpill true")
    session.feed("  redpill true")
    session.feed("    trace 9")
    assert session.feed("  flatline") is True
    assert session.feed("flatline") is False
    assert buffer.getvalue() == "9\n"


def test_a_syntax_error_is_reported_and_the_session_continues():
    printed = feed_all(["construct = 5", "trace 1"])
    assert "line 1" in printed
    assert printed.endswith("1\n")


def test_a_runtime_error_is_reported_and_the_session_continues():
    printed = feed_all(["trace nope", "trace 2"])
    assert "not declared" in printed
    assert printed.endswith("2\n")


def test_an_error_inside_a_block_clears_the_buffer():
    # After a failed block the next line must be treated as fresh input,
    # not appended to the wreckage.
    printed = feed_all(["redpill 1", "  trace 1", "flatline", "trace 7"])
    assert "must be a boolean" in printed
    assert printed.endswith("7\n")


def test_blank_lines_and_comments_are_harmless():
    assert feed_all(["", "# nothing", "trace 1"]) == "1\n"


def test_a_bare_expression_is_a_syntax_error_not_a_crash():
    # The grammar has no expression statement; the REPL must report that
    # cleanly rather than raise.
    printed = feed_all(["1 + 1", "trace 2"])
    assert "line 1" in printed
    assert printed.endswith("2\n")


def test_repl_reads_until_eof_and_returns_zero():
    source = io.StringIO("construct x = 2\ntrace x\n")
    out = io.StringIO()
    assert repl(in_=source, out=out) == 0
    assert "2\n" in out.getvalue()
