import pytest

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


def test_unimplemented_subcommands_exit_two_naming_the_stage(capsys):
    # run and repl are implemented as of Stage 3 (see test_run_* and the REPL
    # tests); only render remains pending, for Stage 4.
    assert main(["render"]) == 2
    assert "Stage" in capsys.readouterr().err


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


def test_only_render_remains_unimplemented(capsys):
    assert main(["render"]) == 2
    assert "Stage 4" in capsys.readouterr().err
