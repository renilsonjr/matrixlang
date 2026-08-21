"""Command-line entry point for the MatrixLang toolchain."""

import argparse
import os
import sys
import threading
from pathlib import Path

from matrixlang.display import Backend, TextDisplay, choose_backend, tk_is_available
from matrixlang.errors import MatrixLangError, recursion_guard
from matrixlang.events import Error
from matrixlang.input import StdinSource
from matrixlang.interpreter import DEFAULT_MAX_STEPS, Interpreter, reads_input
from matrixlang.window import CascadeWindow
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
        "--max-steps",
        type=int,
        default=DEFAULT_MAX_STEPS,
        metavar="N",
        help=(
            "Stop after N statements, to catch runaway loops. "
            "0 removes the limit entirely."
        ),
    )
    run_parser.add_argument(
        "--no-window",
        action="store_true",
        help="Print output as text instead of opening the cascade window.",
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
        return _command_run(
            args.path,
            want_window=not args.no_window,
            max_steps=args.max_steps or None,
        )
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


def _command_run(
    path: str,
    want_window: bool = True,
    max_steps: int | None = DEFAULT_MAX_STEPS,
) -> int:
    source = _read_source(path)
    if source is None:
        return 2

    try:
        with recursion_guard():
            tree = parse(lex(source))
    except MatrixLangError as error:
        print(f"matrixlang: {error}", file=sys.stderr)
        return 1

    # Chosen after the parse: a program that cannot run must say so
    # immediately, not from behind a window someone has to dismiss first.
    #
    # The AST is consulted here, which looks arbitrary until you try it: a
    # program containing `jackin` reads from stdin, and the cascade window
    # has no input field. Windowed, the worker thread blocks on stdin with
    # nothing on screen saying why, and the reader has to type blind into
    # the terminal underneath an empty window. Text keeps the prompt and
    # the program in one place, which is what LEARNING-MATRIXLANG §18
    # promises the terminal does. Only the DISPLAY is chosen this way —
    # the program runs identically either side of the decision.
    backend = choose_backend(
        isatty=sys.stdout.isatty(),
        env=os.environ,
        want_window=want_window and not reads_input(tree),
        tk_available=tk_is_available(),
    )
    if backend is Backend.WINDOW:
        window = CascadeWindow()
        try:
            window.open()
        except Exception as error:
            # A failure of the display is never a failure of the program.
            print(f"matrixlang: could not open a window ({error}); "
                  f"printing instead", file=sys.stderr)
        else:
            return _run_in_window(tree, window, max_steps)

    return _run_as_text(tree, max_steps)


def _run_as_text(tree, max_steps: int | None) -> int:
    """Execute to stdout. Byte-identical to every version before displays."""
    # Outside the parse try-block on purpose: a program that fails partway
    # has already printed real output, and that output stays.
    try:
        Interpreter(
            sink=TextDisplay(sys.stdout), max_steps=max_steps, source=StdinSource()
        ).run(tree)
    except MatrixLangError as error:
        print(f"matrixlang: {error}", file=sys.stderr)
        return 1
    return 0


# Injectable so the abandoned-run path is testable without a real wait.
_join_timeout = 1.0


def _run_in_window(tree, window, max_steps: int | None) -> int:
    """Execute on a worker thread, drawing on the UI thread.

    Tk is not thread-safe, so the interpreter never touches it: it emits
    into the window's queue, and the window drains that queue under
    `after()`. The mainloop returns when the viewer closes the window,
    which is deliberately later than when the program finishes — a program
    that runs in 200ms would otherwise flash and vanish unread.
    """
    outcome: list[int] = []

    def execute() -> None:
        try:
            Interpreter(
                sink=window, max_steps=max_steps, source=StdinSource()
            ).run(tree)
        except MatrixLangError as error:
            message = f"matrixlang: {error}"
            print(message, file=sys.stderr)
            window.emit(Error(message=message))
            outcome.append(1)
        else:
            outcome.append(0)
        finally:
            window.close()

    worker = threading.Thread(target=execute, daemon=True)
    worker.start()
    try:
        window.mainloop()
    except KeyboardInterrupt:
        return 130
    worker.join(timeout=_join_timeout)
    if outcome:
        return outcome[0]
    # The viewer closed the window before the program finished. Reporting
    # success would be a lie — the run was abandoned, and a failing
    # program would have exited 0. Closing the window is the GUI
    # equivalent of Ctrl-C, so it reports what Ctrl-C reports.
    return 130


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
