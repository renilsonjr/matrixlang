"""Command-line entry point for the MatrixLang toolchain."""

import argparse
import sys
from pathlib import Path

from matrixlang.errors import MatrixLangError, recursion_guard
from matrixlang.interpreter import run as run_program
from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.render import render_ascii, render_glyph
from matrixlang.repl import repl as run_repl
from matrixlang.treeview import format_tree


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="matrixlang", description="The MatrixLang toolchain."
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    lex_parser = subcommands.add_parser(
        "lex", help="Print the token stream for a source file."
    )
    lex_parser.add_argument("path", help="Path to a .rain source file.")

    parse_parser = subcommands.add_parser(
        "parse", help="Print the syntax tree for a source file."
    )
    parse_parser.add_argument("path", help="Path to a .rain source file.")

    run_parser = subcommands.add_parser("run", help="Execute a source file.")
    run_parser.add_argument("path", help="Path to a .rain source file.")

    subcommands.add_parser("repl", help="Start an interactive session.")
    render_parser = subcommands.add_parser(
        "render", help="Print a source file in the ASCII or glyph face."
    )
    render_parser.add_argument("path", help="Path to a .rain source file.")
    render_parser.add_argument(
        "--face",
        choices=("ascii", "glyph"),
        required=True,
        help="Which face to print. Rendering is canonical: whitespace normalizes.",
    )

    args = parser.parse_args(argv)

    if args.command == "lex":
        return _command_lex(args.path)
    if args.command == "parse":
        return _command_parse(args.path)
    if args.command == "run":
        return _command_run(args.path)
    if args.command == "repl":
        return run_repl()
    if args.command == "render":
        return _command_render(args.path, args.face)
    raise AssertionError(f"unhandled command: {args.command}")


def _read_source(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        print(f"matrixlang: {error}", file=sys.stderr)
        return None


def _command_parse(path: str) -> int:
    source = _read_source(path)
    if source is None:
        return 2
    try:
        with recursion_guard():
            tree = parse(lex(source))
    except MatrixLangError as error:
        print(f"matrixlang: {error}", file=sys.stderr)
        return 1
    print(format_tree(tree), end="")
    return 0


def _command_lex(path: str) -> int:
    source = _read_source(path)
    if source is None:
        return 2

    try:
        tokens = lex(source)
    except MatrixLangError as error:
        print(f"matrixlang: {error}", file=sys.stderr)
        return 1

    for token in tokens:
        print(f"{token.line}:{token.column}\t{token.type.name}\t{token.lexeme!r}")
    return 0


def _command_run(path: str) -> int:
    source = _read_source(path)
    if source is None:
        return 2

    try:
        with recursion_guard():
            tree = parse(lex(source))
    except MatrixLangError as error:
        print(f"matrixlang: {error}", file=sys.stderr)
        return 1

    # Execution is deliberately outside the parse try-block: a program that
    # fails partway has already printed real output, and that output stays.
    try:
        run_program(tree)
    except MatrixLangError as error:
        print(f"matrixlang: {error}", file=sys.stderr)
        return 1
    return 0


def _command_render(path: str, face: str) -> int:
    source = _read_source(path)
    if source is None:
        return 2
    try:
        with recursion_guard():
            tree = parse(lex(source))
            text = render_glyph(tree) if face == "glyph" else render_ascii(tree)
    except MatrixLangError as error:
        print(f"matrixlang: {error}", file=sys.stderr)
        return 1
    print(text, end="")
    return 0
