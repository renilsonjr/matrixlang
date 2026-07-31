"""The execution event stream: what the interpreter emits while it runs.

Before this module the interpreter printed. Printing is a decision about
*where* output goes, made at the point that knows least about it, and it
forces every consumer to be a file. A cascade window is not a file.

So the interpreter emits events instead, and a sink decides what they
mean. The default sink prints, byte for byte, exactly what printing used
to print — which is what makes this a refactor rather than a behaviour
change, and what lets the existing suite serve as its proof.

The vocabulary is deliberately three items. `Statement` is what a display
needs to show *what is running*; `Output` is what a program produced;
`Error` is the one thing that must never be transliterated (design §5).
Pure data, like `tokens.py` and `nodes.py`.
"""

from dataclasses import dataclass
from typing import Protocol, TextIO

from matrixlang.nodes import Stmt


@dataclass(frozen=True)
class Statement:
    """A statement began executing.

    Carries the node rather than rendered text: the display chooses a face,
    and the interpreter has no business knowing that faces exist.
    """

    node: Stmt | None
    line: int


@dataclass(frozen=True)
class Output:
    """A `trace` produced a value, already converted for display.

    Display-ready by design. A sink that had to call `values.to_display`
    would be a second place where display rules live.
    """

    text: str
    line: int


@dataclass(frozen=True)
class Error:
    """Execution failed. Always plain text, never transliterated."""

    message: str


Event = Statement | Output | Error


class EventSink(Protocol):
    """Anything that can receive execution events."""

    def emit(self, event: Event) -> None: ...


class TextSink:
    """The default sink: stdout, exactly as it behaved before events existed.

    Only `Output` reaches the stream. `Statement` is display scaffolding and
    would add a line per statement to every program's output; `Error` travels
    its own path to stderr, and must not contaminate stdout — a program whose
    output is being captured should not gain a diagnostic in the middle of it.
    """

    def __init__(self, out: TextIO) -> None:
        self._out = out

    def emit(self, event: Event) -> None:
        if isinstance(event, Output):
            print(event.text, file=self._out)
