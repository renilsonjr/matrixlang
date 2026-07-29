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
    for command in ("run", "repl", "render"):
        assert main([command]) == 2
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
