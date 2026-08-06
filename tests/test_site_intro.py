"""The intro's glyph faces are generated, and they decode back.

site/intro.json is the only definition of what the intro says — intro.js
fetches it, and the page carries no second copy — so the two things worth
pinning are that the committed file matches a fresh generation, and that
every face on it is reversible. The page claims the table round-trips;
this is the intro's share of making that true.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "site"))

import generate_intro  # noqa: E402

from matrixlang.translit import untransliterate  # noqa: E402

_COMMITTED = Path(__file__).parent.parent / "site" / "intro.json"


def test_committed_intro_matches_a_fresh_run():
    fresh = generate_intro.build()
    committed = json.loads(_COMMITTED.read_text())
    assert committed == fresh, (
        "site/intro.json is stale — run "
        "`PYTHONPATH=.:src python site/generate_intro.py`"
    )


def test_every_intro_line_decodes_back_to_what_it_says():
    committed = json.loads(_COMMITTED.read_text())
    for line in committed["lines"]:
        assert untransliterate(line["glyph"]) == line["latin"], (
            f"{line['latin']!r} does not survive its own glyph face"
        )


def test_the_intro_has_lines_and_none_are_empty():
    """intro.js treats an empty list as a failure and skips the intro.

    That is the right behaviour there, but it would turn a generator bug
    into a silently missing intro rather than a red build.
    """
    committed = json.loads(_COMMITTED.read_text())
    assert committed["lines"], "intro.json ships no lines"
    for line in committed["lines"]:
        assert line["latin"].strip(), "an intro line is empty"
        assert line["glyph"].strip(), f"{line['latin']!r} has no glyph face"
