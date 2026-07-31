"""C3 — the window backend, tested everywhere it is not Tk.

Honesty first: **no test here opens a window or asserts a pixel.** What
is tested is everything that decides what a viewer would see — the queue
that carries events across the thread boundary, the routing that keeps
diagnostics out of the cascade, and the degradation path.

That is the same admission the project already makes about the curtain:
the frame math is verified, the look is a human judgment.
"""

import ast
import queue
import threading
from random import Random

from matrixlang.cascade import CascadeField
from matrixlang.events import Error, Output, Statement
from matrixlang.window import CascadeWindow, drain


def a_field():
    return CascadeField(20, 10, Random(7))


# --- The thread boundary ------------------------------------------------


def test_emitting_puts_the_event_on_the_queue_without_touching_tk():
    # emit() is called from the interpreter's worker thread. If it did
    # anything to a widget, Tk would corrupt or crash — it is not
    # thread-safe, and this is the whole reason a queue exists.
    window = CascadeWindow(width=20, height=10)
    window.emit(Output(text="wake up", line=1))
    assert window.pending() == 1


def test_events_emitted_from_another_thread_arrive():
    window = CascadeWindow(width=20, height=10)

    def worker():
        for i in range(50):
            window.emit(Output(text=str(i), line=1))

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()
    assert window.pending() == 50


# --- Draining -----------------------------------------------------------


def test_draining_moves_output_events_into_the_field():
    q, field, errors = queue.Queue(), a_field(), []
    q.put(Output(text="wake up", line=1))
    drain(q, field, errors)
    assert not field.is_empty()


def test_draining_empties_the_queue():
    q, field, errors = queue.Queue(), a_field(), []
    for i in range(5):
        q.put(Output(text=str(i), line=1))
    drain(q, field, errors)
    assert q.empty()


def test_errors_go_to_the_status_strip_and_never_into_the_cascade():
    # The one rule the spike proved empirically: a transliterated
    # diagnostic hides the line number, the misspelled name and the
    # remedy at once, and breaks D-03's guarantee.
    q, field, errors = queue.Queue(), a_field(), []
    q.put(Error(message="[line 2, column 21] 'nme' is not declared"))
    drain(q, field, errors)
    assert field.is_empty()
    assert errors == ["[line 2, column 21] 'nme' is not declared"]


def test_a_statement_event_reaches_the_field():
    from matrixlang.lexer import lex
    from matrixlang.parser import parse

    q, field, errors = queue.Queue(), a_field(), []
    program = parse(lex("construct n = 0\n"))
    q.put(Statement(node=program.statements[0], line=1))
    drain(q, field, errors)
    assert not field.is_empty()


def test_draining_an_empty_queue_is_harmless():
    q, field, errors = queue.Queue(), a_field(), []
    drain(q, field, errors)
    assert field.is_empty()
    assert errors == []


# --- Degradation --------------------------------------------------------


def test_tkinter_is_not_imported_at_module_scope():
    # A top-level `import tkinter` would make the entire package fail to
    # import on a machine without Tk, turning a missing window into a
    # missing language.
    source = (
        __import__("pathlib").Path(
            __import__("matrixlang.window", fromlist=["window"]).__file__
        )
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = []
    for node in top_level:
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif node.module:
            names.append(node.module)
    assert not any(n.split(".")[0] == "tkinter" for n in names)


def test_close_before_open_is_safe():
    # The CLI calls close() in a finally. It must not require that open()
    # succeeded, or a failed window becomes a failed program.
    window = CascadeWindow(width=20, height=10)
    window.close()
    window.close()


def test_the_window_satisfies_the_display_protocol():
    window = CascadeWindow(width=20, height=10)
    assert callable(window.open)
    assert callable(window.emit)
    assert callable(window.close)
