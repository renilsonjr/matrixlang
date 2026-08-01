"""Server-Sent Events: the wire format, and nothing else.

Pure. No socket, no thread, no server — which is what makes the format
testable, and the format is the part a browser is unforgiving about.
"""

import json

from matrixlang.events import Error, Event, Output, Statement
from matrixlang.nodes import Program
from matrixlang.render import render_glyph
from matrixlang.translit import transliterate


def frame(payload: str) -> str:
    """One SSE event.

    Two rules the browser enforces and a hand-rolled writer gets wrong:
    every line needs its own `data: ` prefix, and the event is terminated
    by a **blank line**. Miss the blank line and the browser buffers
    forever — the stream looks connected and nothing ever arrives.
    """
    body = "\n".join(f"data: {line}" for line in payload.split("\n"))
    return body + "\n\n"


DONE = frame(json.dumps({"kind": "done"}))


def encode(event: Event) -> str:
    """An execution event as a frame the browser can render.

    Source is sent in the glyph face and transliterated, matching what the
    Tk window shows — the browser is a third backend behind the same
    decisions, not a second set of them.
    """
    if isinstance(event, Output):
        payload = {
            "kind": "output",
            "text": event.text,
            "line": event.line,
        }
    elif isinstance(event, Statement):
        payload = {
            "kind": "statement",
            "line": event.line,
            "source": _header(event.node),
        }
    elif isinstance(event, Error):
        payload = {"kind": "error", "message": event.message}
    else:
        payload = {"kind": "unknown"}
    return frame(json.dumps(payload))


def _header(node) -> str:
    """A statement's own first line, glyph face, transliterated.

    Never `repr(node)`: that would put a Python class name and a memory
    address on the wire, which §6 records this project as not doing.
    """
    if node is None:
        return ""
    rendered = render_glyph(Program([node]))
    lines = [line.strip() for line in rendered.splitlines() if line.strip()]
    return transliterate(lines[0]) if lines else ""
