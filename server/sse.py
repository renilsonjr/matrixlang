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
    """An execution event as a frame the browser can render."""
    return frame(json.dumps(payload(event)))


def payload(event: Event) -> dict:
    """The wire shape of one execution event. **The only place it is built.**

    `runs.py` queues what this returns and the HTTP layer serialises it,
    so there is exactly one definition of what the browser receives. An
    earlier version built the payload in both places, and the two drifted
    immediately: `encode` gained a transliterated `glyphs` field for
    output and the queue did not, so the cascade drew Latin with the
    glyph wall selected while every test of `encode` passed.
    """
    if isinstance(event, Output):
        return {
            "kind": "output",
            # `text` is the readable value, for a status line or a log.
            # `glyphs` is what falls. Sending only `text` put Latin in the
            # cascade with the glyph wall selected — OP-12 broken in the
            # browser while every test passed, because no test looked at
            # what the cascade was actually handed.
            "text": event.text,
            "glyphs": transliterate(event.text),
            "line": event.line,
        }
    elif isinstance(event, Statement):
        glyph = _face(event.node)
        return {
            "kind": "statement",
            "line": event.line,
            # Both faces, because the UI toggles between them and the
            # browser must not own a copy of the transliteration table.
            # A second copy is how web/interpreter.js drifted from the
            # language it claimed to implement.
            "source": transliterate(glyph),
            "latin": glyph,
        }
    elif isinstance(event, Error):
        return {"kind": "error", "message": event.message}
    else:
        return {"kind": "unknown"}
    return data


def _face(node) -> str:
    """A statement's own first line in the glyph face.

    Never `repr(node)`: that would put a Python class name and a memory
    address on the wire, which §6 records this project as not doing.
    """
    if node is None:
        return ""
    rendered = render_glyph(Program([node]))
    lines = [line.strip() for line in rendered.splitlines() if line.strip()]
    return lines[0] if lines else ""


def header(node) -> str:
    """The pure glyph wall form, for callers that only want one face."""
    return transliterate(_face(node))
