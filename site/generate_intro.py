"""The intro's two lines, and the glyph face of each.

Generated, never typed. The browser must not own the transliteration table
(TECHNICAL-OVERVIEW §5.7, site/checks/no_semantics.py), so the glyph face
of every line is produced here by the package's own `transliterate` and
shipped as data — the same arrangement site/generate_examples.py uses for
the examples.

Unlike the examples, this file is the *only* definition: `site/intro.js`
fetches intro.json at runtime rather than the page carrying a second copy
inline, so there is no paste step and nothing to drift.

Run: PYTHONPATH=.:src python site/generate_intro.py
"""

import json
from pathlib import Path

from matrixlang.translit import transliterate, untransliterate

# The first line is four words of on-screen text from the film, which the
# page's colophon already covers: this is a fan project, unaffiliated, and
# it uses none of the film's trademarks, logos, footage or glyph designs.
# The second line is the project's own, and it is what the intro is FOR —
# it states the page's argument before a word of prose has been read.
LINES = [
    "The Matrix has you...",
    "But the code never did.",
]

_OUT = Path(__file__).parent / "intro.json"


def build() -> dict:
    """Every intro line with its glyph face, checked reversible on the way out."""
    lines = []
    for latin in LINES:
        glyph = transliterate(latin)
        # The page claims the table is reversible. An intro that shipped a
        # face which did not decode back would be the first counterexample,
        # on the way in, before anyone read the claim.
        assert untransliterate(glyph) == latin, f"{latin!r} does not round-trip"
        lines.append({"latin": latin, "glyph": glyph})
    return {"lines": lines}


if __name__ == "__main__":
    _OUT.write_text(json.dumps(build(), ensure_ascii=False, indent=2) + "\n")
    print(f"wrote {_OUT}")
