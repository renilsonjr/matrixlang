"""Where execution events go, and how that is decided.

The interpreter emits events (`events.py`); a display consumes them. Text
is one display, the cascade window is another, a browser would be a third.
Keeping the choice behind a protocol is what stops the window from being
wired into the runner the way the curtain was — and what lets the import
graph forbid the core from knowing any backend exists.

Selection is a pure function so it is table-testable without a terminal or
a window, the same reason `ansi.detect_color_mode` takes the environment
as a parameter instead of reading it.

The first rule is the one everything else defers to: **not a TTY means no
window and unchanged bytes.** Redirected output is a property of this
project, not a default to be overridden.
"""

from collections.abc import Mapping
from enum import Enum, auto
from typing import Protocol, TextIO

from matrixlang.events import Event, TextSink


class Backend(Enum):
    TEXT = auto()
    WINDOW = auto()


class Display(Protocol):
    """An event consumer with a lifecycle.

    `open` and `close` exist for backends that own a resource. Text owns
    nothing and implements them as no-ops, so the CLI can call them
    unconditionally rather than branching on which backend it got.
    """

    def open(self) -> None: ...
    def emit(self, event: Event) -> None: ...
    def close(self) -> None: ...


def choose_backend(
    *,
    isatty: bool,
    env: Mapping[str, str],
    want_window: bool,
    tk_available: bool,
) -> Backend:
    """Which backend the environment calls for.

    Deliberately not routed through `detect_color_mode`, which also vetoes
    on `TERM`. TERM describes a terminal's capabilities, and a window is
    not a terminal: a program run from a dumb terminal can still open one.
    The curtain lived in the terminal and was right to care; this does not.
    """
    if not isatty:
        return Backend.TEXT
    if not want_window:
        return Backend.TEXT
    # Presence, not truthiness: NO_COLOR="" still means no.
    if "NO_COLOR" in env:
        return Backend.TEXT
    if not tk_available:
        return Backend.TEXT
    return Backend.WINDOW


def tk_is_available() -> bool:
    """Whether a Tk window can be built at all.

    Import failure is the cheap half. Whether a *display* exists is not
    knowable without trying, so `window.py` degrades on construction too;
    this only avoids the obvious case.
    """
    try:
        import tkinter  # noqa: F401
    except Exception:
        return False
    return True


class TextDisplay:
    """Stdout, behaving exactly as it did before displays existed."""

    def __init__(self, out: TextIO) -> None:
        self._sink = TextSink(out)

    def open(self) -> None:
        pass

    def emit(self, event: Event) -> None:
        self._sink.emit(event)

    def close(self) -> None:
        pass
