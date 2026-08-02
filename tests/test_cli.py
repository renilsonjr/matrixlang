import io

import pytest

from matrixlang import cli
from matrixlang.cli import main


@pytest.fixture
def source_file(tmp_path):
    def write(text: str):
        path = tmp_path / "program.rain"
        path.write_text(text, encoding="utf-8")
        return str(path)

    return write


def test_lex_prints_tokens_and_exits_zero(source_file, capsys):
    exit_code = main(["lex", source_file("x = 1\n")])
    output = capsys.readouterr().out
    assert exit_code == 0
    assert "IDENT" in output
    assert "ASSIGN" in output
    assert "NUMBER" in output
    assert "EOF" in output


def test_lex_reports_source_errors_on_stderr_and_exits_one(source_file, capsys):
    exit_code = main(["lex", source_file('trace "unterminated\n')])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "line 1" in captured.err
    assert "column 7" in captured.err


def test_missing_file_exits_two(capsys, tmp_path):
    exit_code = main(["lex", str(tmp_path / "nope.rain")])
    assert exit_code == 2
    assert "nope.rain" in capsys.readouterr().err


def test_no_subcommand_is_a_usage_error():
    with pytest.raises(SystemExit) as excinfo:
        main([])
    assert excinfo.value.code == 2


def test_non_utf8_file_exits_two_without_traceback(capsys, tmp_path):
    path = tmp_path / "binary.rain"
    path.write_bytes(b"\xff\xfe invalid utf-8")
    exit_code = main(["lex", str(path)])
    captured = capsys.readouterr()
    assert exit_code == 2
    assert captured.out == ""
    assert "matrixlang:" in captured.err


def test_parse_prints_the_tree(source_file, capsys):
    exit_code = main(["parse", source_file("x = 2 + 3 * 4\n")])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == (
        "Program\n"
        "  Assign 'x'\n"
        "    Binary +\n"
        "      NumberLiteral 2\n"
        "      Binary *\n"
        "        NumberLiteral 3\n"
        "        NumberLiteral 4\n"
    )


def test_parse_reports_errors_and_exits_one(source_file, capsys):
    exit_code = main(["parse", source_file("construct = 5\n")])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "line 1" in captured.err


def test_parse_missing_file_exits_two(capsys, tmp_path):
    assert main(["parse", str(tmp_path / "nope.rain")]) == 2


def test_lex_still_works_after_the_read_refactor(source_file, capsys):
    assert main(["lex", source_file("x = 1\n")]) == 0


def test_run_executes_a_program(source_file, capsys):
    exit_code = main(["run", source_file("construct x = 2\ntrace x + 3\n")])
    assert exit_code == 0
    assert capsys.readouterr().out == "5\n"


def test_run_reports_a_runtime_error_and_exits_one(source_file, capsys):
    exit_code = main(["run", source_file("trace 1 / 0\n")])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert "divide by zero" in captured.err
    assert "line 1" in captured.err


def test_run_reports_a_parse_error_and_exits_one(source_file, capsys):
    exit_code = main(["run", source_file("construct = 5\n")])
    assert exit_code == 1
    assert "line 1" in capsys.readouterr().err


def test_run_emits_output_produced_before_a_runtime_error(source_file, capsys):
    # Unlike lex and parse, run has side effects as it goes. Output already
    # printed is real and must not be swallowed.
    exit_code = main(["run", source_file("trace 1\ntrace 2 / 0\n")])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == "1\n"
    assert "divide by zero" in captured.err


def test_run_missing_file_exits_two(capsys, tmp_path):
    assert main(["run", str(tmp_path / "nope.rain")]) == 2


def test_render_glyph_prints_the_glyph_face(source_file, capsys):
    exit_code = main(["render", "--face", "glyph", source_file("trace 1 + 2\n")])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "ﾄ ｧ ﾀ ｨ\n"


def test_render_ascii_is_a_formatter(source_file, capsys):
    # Whitespace normalizes (design S4-1): the blank line goes, the
    # indent becomes canonical. render --face ascii doubles as fmt.
    exit_code = main(
        ["render", "--face", "ascii", source_file("\n\ntrace      1\n")]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "trace 1\n"


def test_render_round_trips_through_a_file(source_file, capsys, tmp_path):
    # The toggle demo end-to-end: ascii -> glyph -> ascii, byte-identical.
    source = 'construct n = 0\ndejavu n < 2\n  trace "go"\nflatline\n'
    exit_code = main(["render", "--face", "glyph", source_file(source)])
    glyph_text = capsys.readouterr().out
    assert exit_code == 0

    glyph_path = tmp_path / "glyph.rain"
    glyph_path.write_text(glyph_text, encoding="utf-8")
    exit_code = main(["render", "--face", "ascii", str(glyph_path)])
    assert exit_code == 0
    assert capsys.readouterr().out == source


def test_render_reports_parse_errors_and_exits_one(source_file, capsys):
    exit_code = main(["render", "--face", "glyph", source_file("redpill true\n")])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert "flatline" in captured.err


def test_render_requires_a_face():
    with pytest.raises(SystemExit) as excinfo:
        main(["render", "some.rain"])
    assert excinfo.value.code == 2


def test_render_missing_file_exits_two(capsys, tmp_path):
    exit_code = main(["render", "--face", "ascii", str(tmp_path / "nope.rain")])
    assert exit_code == 2
    assert "nope.rain" in capsys.readouterr().err


# --- I-1: RecursionError must become a clean CLI error, not a traceback ----


def _deeply_nested_source() -> str:
    # ~90-100 nested parens overflow Python's recursion limit inside the
    # recursive-descent parser today — a raw RecursionError, uncaught by
    # `except MatrixLangError`, which dumps a traceback instead of the
    # `matrixlang: ...` / exit-1 contract every other error follows.
    return "trace " + "(" * 120 + "1" + ")" * 120 + "\n"


def test_parse_reports_deep_nesting_cleanly_and_exits_one(source_file, capsys):
    exit_code = main(["parse", source_file(_deeply_nested_source())])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err.startswith("matrixlang:")


def test_render_reports_deep_nesting_cleanly_and_exits_one(source_file, capsys):
    exit_code = main(
        ["render", "--face", "glyph", source_file(_deeply_nested_source())]
    )
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err.startswith("matrixlang:")


def test_render_reports_a_render_only_recursion_limit_cleanly(source_file, capsys):
    # A long same-precedence chain parses ITERATIVELY (one stack frame per
    # chain, not per element) but the renderer walks it recursively, so
    # this stresses render's own guard independently of parse's.
    source = "trace " + " + ".join(["1"] * 2000) + "\n"
    exit_code = main(["render", "--face", "ascii", source_file(source)])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.out == ""
    assert captured.err.startswith("matrixlang:")


def test_run_reports_deep_nesting_cleanly_and_exits_one(source_file, capsys):
    exit_code = main(["run", source_file(_deeply_nested_source())])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err.startswith("matrixlang:")


def test_repl_subcommand_reads_until_eof(capsys, monkeypatch):
    # The other half of this task's wiring. `repl` takes no path argument and
    # reads stdin, so drive it with a finite stream — an interactive run
    # blocks until EOF. Prompts also land on stdout, hence the `in` check.
    monkeypatch.setattr("sys.stdin", io.StringIO("construct x = 2\ntrace x\n"))
    assert main(["repl"]) == 0
    assert "2\n" in capsys.readouterr().out


def test_run_writes_no_escape_bytes_under_capture(source_file, capsys):
    # THE debuggability contract, end to end. pytest's captured stdout is
    # not a TTY, which is exactly the situation of `run prog.rain > out`.
    exit_code = main(["run", source_file("trace 1\ntrace 2\n")])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert captured.out == "1\n2\n"
    assert "\x1b" not in captured.out
    assert "\x1b" not in captured.err


class _FakeWindow:
    """Stands in for CascadeWindow so tests never open one."""

    opened = 0

    def __init__(self, *args, **kwargs):
        self.events: list[object] = []
        type(self).opened += 1

    def open(self):
        pass

    def emit(self, event):
        self.events.append(event)

    def close(self):
        pass

    def mainloop(self):
        pass


@pytest.fixture
def no_real_window(monkeypatch):
    _FakeWindow.opened = 0
    monkeypatch.setattr(cli, "CascadeWindow", _FakeWindow)
    return _FakeWindow


def test_run_uses_text_when_stdout_is_not_a_tty(source_file, capsys, no_real_window):
    # capsys makes stdout a non-TTY, which is exactly the redirected case.
    # This is the property everything else defers to.
    assert main(["run", source_file("trace 1\n")]) == 0
    assert capsys.readouterr().out == "1\n"
    assert no_real_window.opened == 0


def test_no_window_skips_the_window_entirely(source_file, capsys, no_real_window):
    assert main(["run", "--no-window", source_file("trace 1\n")]) == 0
    assert capsys.readouterr().out == "1\n"
    assert no_real_window.opened == 0


def test_run_opens_a_window_on_a_tty(source_file, capsys, monkeypatch, no_real_window):
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(cli, "tk_is_available", lambda: True)
    assert main(["run", source_file("trace 1\n")]) == 0
    assert no_real_window.opened == 1


def test_a_parse_error_never_opens_a_window(
    source_file, capsys, monkeypatch, no_real_window
):
    # A program that cannot run must say so immediately, not behind a
    # window that has to be dismissed first.
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(cli, "tk_is_available", lambda: True)
    assert main(["run", source_file("construct = 5\n")]) == 1
    assert no_real_window.opened == 0


def test_a_runtime_error_in_the_window_still_exits_one(
    source_file, capsys, monkeypatch, no_real_window
):
    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(cli, "tk_is_available", lambda: True)
    assert main(["run", source_file("trace nope\n")]) == 1
    assert "not declared" in capsys.readouterr().err


def test_a_window_that_fails_to_open_falls_back_to_text(
    source_file, capsys, monkeypatch
):
    # A failure of the display must never be the reason a program fails.
    class Broken(_FakeWindow):
        def open(self):
            raise RuntimeError("no display")

    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(cli, "tk_is_available", lambda: True)
    monkeypatch.setattr(cli, "CascadeWindow", Broken)
    assert main(["run", source_file("trace 1\n")]) == 0
    captured = capsys.readouterr()
    assert captured.out == "1\n"
    assert "window" in captured.err.lower()


def test_the_rain_flag_is_gone(source_file):
    # The curtain is superseded by the window. --no-rain must not linger
    # as an accepted no-op, which would be worse than removing it.
    with pytest.raises(SystemExit) as excinfo:
        main(["run", "--no-rain", source_file("trace 1\n")])
    assert excinfo.value.code == 2


def test_ctrl_c_while_the_window_is_open_exits_130(
    source_file, capsys, monkeypatch, no_real_window
):
    class Interrupting(_FakeWindow):
        def mainloop(self):
            raise KeyboardInterrupt

    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(cli, "tk_is_available", lambda: True)
    monkeypatch.setattr(cli, "CascadeWindow", Interrupting)
    assert main(["run", source_file("trace 1\n")]) == 130


def test_the_program_output_reaches_the_window_as_events(
    source_file, capsys, monkeypatch, no_real_window
):
    # The seam between the tested half and the half no automated test can
    # exercise: what a viewer sees is decided by these events.
    from matrixlang.events import Output

    created: list[_FakeWindow] = []

    class Recording(_FakeWindow):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            created.append(self)

    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(cli, "tk_is_available", lambda: True)
    monkeypatch.setattr(cli, "CascadeWindow", Recording)
    main(["run", source_file('trace "wake up, Neo"\n')])
    texts = [e.text for e in created[0].events if isinstance(e, Output)]
    assert texts == ["wake up, Neo"]


def test_a_run_abandoned_by_closing_the_window_does_not_report_success(
    source_file, capsys, monkeypatch, no_real_window
):
    # `return outcome[0] if outcome else 0` reported success for a run the
    # viewer walked away from — including one that would have failed. A
    # closed window is the GUI equivalent of Ctrl-C, so it exits 130.
    class ClosedEarly(_FakeWindow):
        def mainloop(self):
            pass  # viewer closed it; the worker never recorded an outcome

    monkeypatch.setattr(cli.sys.stdout, "isatty", lambda: True, raising=False)
    monkeypatch.setattr(cli, "tk_is_available", lambda: True)
    monkeypatch.setattr(cli, "CascadeWindow", ClosedEarly)
    monkeypatch.setattr(cli, "_join_timeout", 0.0)
    path = source_file("construct n = 0\ndejavu true\n  n = n + 1\nflatline\n")
    assert main(["run", path]) == 130


def test_only_run_takes_the_window_flag(source_file):
    # R-03's successor: the display belongs to the runner, never the
    # editor. The flag exists on run and nowhere else.
    with pytest.raises(SystemExit) as excinfo:
        main(["render", "--face", "ascii", "--no-window", source_file("trace 1\n")])
    assert excinfo.value.code == 2


def test_parse_does_not_crash_on_a_list_program(tmp_path, capsys):
    # treeview.py had no case for the Stage 6 nodes and this command
    # crashed while 878 tests passed. One test per stage, forever.
    path = tmp_path / "lists.rain"
    path.write_text("construct xs = [1, 2]\nxs[0] = length xs\n", encoding="utf-8")
    assert main(["parse", str(path)]) == 0
    out = capsys.readouterr().out
    assert "ListLiteral" in out
    assert "IndexAssign" in out
