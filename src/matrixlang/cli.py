"""Command-line entry point for the MatrixLang toolchain."""

import argparse
import sys
from pathlib import Path

from matrixlang.errors import MatrixLangError
from matrixlang.lexer import lex

_PENDING: dict[str, str] = {
    "run": "Stage 3",
    "repl": "Stage 3",
    "render": "Stage 4",
}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="matrixlang", description="The MatrixLang toolchain."
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    lex_parser = subcommands.add_parser(
        "lex", help="Print the token stream for a source file."
    )
    lex_parser.add_argument("path", help="Path to a .rain source file.")

    subcommands.add_parser("run", help="Execute a source file. (Stage 3)")
    subcommands.add_parser("repl", help="Start an interactive session. (Stage 3)")
    subcommands.add_parser(
        "render", help="Convert between the ASCII and glyph faces. (Stage 4)"
    )

    args = parser.parse_args(argv)

    if args.command == "lex":
        return _command_lex(args.path)

    stage = _PENDING[args.command]
    print(
        f"matrixlang: '{args.command}' arrives in {stage}", file=sys.stderr
    )
    return 2


def _command_lex(path: str) -> int:
    try:
        source = Path(path).read_text(encoding="utf-8")
    except OSError as error:
        print(f"matrixlang: {error}", file=sys.stderr)
        return 2

    try:
        tokens = lex(source)
    except MatrixLangError as error:
        print(f"matrixlang: {error}", file=sys.stderr)
        return 1

    for token in tokens:
        print(f"{token.line}:{token.column}\t{token.type.name}\t{token.lexeme!r}")
    return 0
