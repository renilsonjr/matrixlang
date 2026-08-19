import io

from matrixlang.repl import Repl, repl


def feed_streams(lines: list[str]) -> tuple[str, str]:
    """Feed lines to a Repl and return (stdout, stderr) separately."""
    out, err = io.StringIO(), io.StringIO()
    session = Repl(out=out, err=err)
    for line in lines:
        session.feed(line)
    return out.getvalue(), err.getvalue()


def feed_all(lines: list[str]) -> str:
    """Feed lines to a Repl and return both streams, interleaved.

    Kept for the tests that only care that something was reported. The
    ones that care *which* stream it went to use `feed_streams`.
    """
    out, err = feed_streams(lines)
    return out + err


def test_diagnostics_go_to_stderr_not_stdout():
    """README: diagnostics "appear as plain text ... on stderr".

    The CLI honours that in every one of its eight error paths; the REPL
    sent them to stdout, so `matrixlang repl > session.txt` swallowed the
    errors into the file and left the terminal silent about them.
    """
    out, err = feed_streams(["trace nope"])
    assert "not declared" in err
    assert "not declared" not in out


def test_program_output_stays_on_stdout():
    """The split must not send ordinary output to stderr along with it."""
    out, err = feed_streams(["trace 1"])
    assert out == "1\n"
    assert err == ""


def test_output_and_diagnostics_are_separable_in_one_session():
    """A failing line then a working one: each stream carries only its own."""
    out, err = feed_streams(["trace nope", "trace 2"])
    assert out == "2\n"
    assert "not declared" in err


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
    out, err = feed_streams(["construct = 5", "trace 1"])
    assert "line 1" in err
    assert out == "1\n"


def test_a_runtime_error_is_reported_and_the_session_continues():
    out, err = feed_streams(["trace nope", "trace 2"])
    assert "not declared" in err
    assert out == "2\n"


def test_an_error_inside_a_block_clears_the_buffer():
    # After a failed block the next line must be treated as fresh input,
    # not appended to the wreckage.
    out, err = feed_streams(["redpill 1", "  trace 1", "flatline", "trace 7"])
    assert "must be a boolean" in err
    assert out == "7\n"


def test_blank_lines_and_comments_are_harmless():
    assert feed_all(["", "# nothing", "trace 1"]) == "1\n"


def test_a_bare_expression_is_a_syntax_error_not_a_crash():
    # The grammar has no expression statement; the REPL must report that
    # cleanly rather than raise.
    out, err = feed_streams(["1 + 1", "trace 2"])
    assert "line 1" in err
    assert out == "2\n"


def test_repl_reads_until_eof_and_returns_zero():
    source = io.StringIO("construct x = 2\ntrace x\n")
    out = io.StringIO()
    assert repl(in_=source, out=out) == 0
    assert "2\n" in out.getvalue()


def test_the_glyph_command_turns_on_glyph_echo():
    # ﾄ=trace ｧ=1 ﾀ=+ ｨ=2 — the echo is the statement re-rendered in the
    # operator view, printed before the execution output.
    buffer = io.StringIO()
    session = Repl(out=buffer)
    assert session.feed(":glyph") is False
    session.feed("trace 1 + 2")
    assert buffer.getvalue() == "ﾄ ｧ ﾀ ｨ\n3\n"


def test_the_ascii_command_turns_echo_back_off():
    assert feed_all([":glyph", ":ascii", "trace 1"]) == "1\n"


def test_glyph_echo_covers_a_whole_block():
    # ﾃ=dejavu ｷ=false ﾗ=flatline. The echo appears once, after the block
    # completes, in canonical block form.
    output = feed_all([":glyph", "dejavu false", "  trace 1", "flatline"])
    assert output == "ﾃ ｷ\n  ﾄ ｧ\nﾗ\n"


def test_glyph_input_runs_without_any_mode():
    # §6.3: one lexer, no mode flag — the REPL accepts glyph source
    # as-is, even in the default ascii face. ﾄ ｩ == trace 3.
    assert feed_all(["ﾄ ｩ"]) == "3\n"


def test_a_face_command_mid_block_is_just_source():
    # Meta-commands exist only at a fresh prompt. Mid-block, ':glyph' is
    # source text, and ':' is not a MatrixLang character.
    output = feed_all(["dejavu false", ":glyph", "flatline"])
    assert "unexpected character" in output


def test_echo_still_prints_when_execution_fails():
    # The echo shows what was ABOUT to run; a runtime error follows it.
    out, err = feed_streams([":glyph", "trace nope"])
    assert out.startswith("ﾄ nope\n")
    assert "not declared" in err


# --- I-1: RecursionError must not kill the session -------------------------


def test_a_deeply_nested_expression_is_reported_and_the_session_continues():
    # ~90-100 nested parens overflow Python's recursion limit inside the
    # recursive-descent parser today — a raw RecursionError, which
    # `feed`'s `except MatrixLangError` does not catch, ending the whole
    # REPL session. Built programmatically: the exact threshold is a
    # measured implementation detail, not something to hand-pick a
    # literal for.
    line = "trace " + "(" * 120 + "1" + ")" * 120
    out, err = feed_streams([line, "trace 2"])
    assert "matrixlang:" in err
    assert out == "2\n"


def test_a_deeply_nested_render_echo_is_reported_and_the_session_continues():
    # The glyph echo (render_glyph) is a second, independent recursive
    # walk over the tree, reachable even when parsing sailed through: a
    # long same-precedence chain parses ITERATIVELY (one stack frame per
    # chain, not per element) but renders recursively, so it can blow
    # render's stack in cases the parser never even notices.
    line = "trace " + " + ".join(["1"] * 2000)
    out, err = feed_streams([":glyph", line, "trace 2"])
    assert "matrixlang:" in err
    assert out.endswith("2\n")


def test_jackin_at_the_prompt_reads_the_next_line_of_the_session():
    # The REPL shares one stream between source and input, so the line
    # after the `jackin` statement is what the statement reads. Repl
    # used to hardcode StdinSource() and ignore `in_` entirely, which
    # made this untestable -- feeding a StringIO drove the prompt while
    # `jackin` blocked on the real stdin, raising OSError out of feed()
    # and killing the session.
    source = io.StringIO('construct name = jackin\nNeo\ntrace "Hello, " + name\n')
    out, err = io.StringIO(), io.StringIO()

    assert repl(in_=source, out=out, err=err) == 0

    assert "Hello, Neo" in out.getvalue()
    assert err.getvalue() == ""
