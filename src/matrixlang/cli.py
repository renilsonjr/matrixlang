"""Command-line entry point for the MatrixLang toolchain."""

import argparse
import os
import shutil
import sys
from pathlib import Path

from matrixlang.curtain import play_if_supported
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
    run_parser.add_argument(
        "--no-rain",
        action="store_true",
        help="Skip the digital rain and execute immediately.",
    )

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
        return _command_run(args.path, rain=not args.no_rain)
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


def _command_run(path: str, rain: bool = True) -> int:
    source = _read_source(path)
    if source is None:
        return 2

    try:
        with recursion_guard():
            tree = parse(lex(source))
    except MatrixLangError as error:
        print(f"matrixlang: {error}", file=sys.stderr)
        return 1

    # After the parse, before execution: a program that cannot run should
    # say so immediately rather than after a second of decoration. The
    # curtain declines itself on a non-TTY, so redirected output is clean
    # without this call site knowing anything about terminals.
    if rain:
        try:
            play_if_supported(sys.stdout, os.environ, shutil.get_terminal_size())
        except KeyboardInterrupt:
            # play() has already restored the terminal in its finally.
            # This must stay first: KeyboardInterrupt is a BaseException,
            # so a later `except Exception` cannot catch it here.
            return 130
        except Exception:
            # Decoration must never be the reason a run fails: an
            # unencodable glyph or a dropped terminal loses the rain,
            # not the program.
            pass

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
