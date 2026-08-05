"""The narrative's examples ship executed — enforced, not promised.

README already claims every example was run before it shipped. For the
page, this test is what makes that true: it regenerates examples.json and
fails if the committed copy differs, so an example cannot go stale
without CI saying so.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "site"))

import generate_examples  # noqa: E402

_COMMITTED = Path(__file__).parent.parent / "site" / "examples.json"


def test_committed_examples_match_a_fresh_run():
    fresh = generate_examples.build()
    committed = json.loads(_COMMITTED.read_text())
    assert committed == fresh, (
        "site/examples.json is stale — run "
        "`PYTHONPATH=.:src python site/generate_examples.py`"
    )


def test_every_example_generated_source():
    """Source, not output — some examples correctly print nothing.

    `make a list of 1 2 3` renders `construct xs = [1, 2, 3]` and
    `define a function that doubles` renders an `agent` that nobody calls;
    both are declarations, and a declaration traces nothing. Scribe has no
    define-and-call intent, so the function example *cannot* produce
    output — and it is the one example that shows `agent`/`jackout`, which
    the page should not lose.

    Asserting output here would only restate what the freshness test
    already pins: `committed == fresh` compares source and output exactly,
    so an example that started or stopped printing fails there, with a
    better message. What is genuinely invariant is that every request
    still resolves to a program.
    """
    committed = json.loads(_COMMITTED.read_text())
    for request, example in committed.items():
        assert example["source"].strip(), f"{request!r} generated no source"
