"""Render the narrative's examples by running the real interpreter.

Run it directly to refresh `examples.json`:

    PYTHONPATH=.:src python site/generate_examples.py

The prefix is needed because `server/` is deliberately not packaged (see
pyproject: a top-level `server` on PyPI would collide with half the
ecosystem). Tests import it via pytest's `pythonpath = ["."]`; a plain
script run gets `sys.path[0] = site/` and never sees it.

`tests/test_site_examples.py` fails if the committed file and a fresh run
disagree, so a stale example is a red build rather than a wrong page.
"""

import json
from pathlib import Path

import glue

# The narrative's examples. Each must be a request Scribe knows — the
# freshness test asserts every one produced source and output.
EXAMPLES = [
    "add 5 and 3",
    "count from 1 to 5",
    "make a list of 1 2 3",
    "if 5 is greater than 3 trace bigger",
    "define a function that doubles",
]

_OUT = Path(__file__).parent / "examples.json"


def build() -> dict:
    """Every example, with the source Scribe wrote, its glyph face, and the
    output it printed."""
    built = {}
    for request in EXAMPLES:
        written = glue.write(request)
        assert written["ok"], f"{request!r} is no longer a request Scribe knows"
        source = written["source"]
        events = glue.run(source)
        built[request] = {
            "source": source,
            "glyph": glue.glyph(source)["glyph"],
            "output": [e["text"] for e in events if e["kind"] == "output"],
        }
    return built


if __name__ == "__main__":
    _OUT.write_text(json.dumps(build(), indent=2) + "\n")
    print(f"wrote {_OUT}")
