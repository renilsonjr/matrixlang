"""Display-only transliteration: arbitrary text to glyphs.

EXPERIMENT. Not part of the shipped package, not imported by anything in
src/matrixlang/, and deliberately outside it so the architecture guard and
the katakana-containment guard do not apply.

This is NOT the language's glyph face. The distinction is the whole point:

  glyphs.GLYPHS   the LANGUAGE's face. 32 slots, bijective, round-trips
                  through the lexer. Governed by D-03 and spec section 4.3.
  this module     a DISPLAY transliteration. Its output is never lexed, so
                  it owes nothing to bijectivity or the round trip. It may
                  reuse glyphs the language already assigns, because no
                  parser ever has to tell them apart.

That freedom is what makes rendering arbitrary output possible at all: the
language's 32 slots cannot cover the Latin alphabet (24 free glyphs against
26 letters needed), but a display map is under no such constraint.
"""

from matrixlang.glyphs import GLYPHS

# The full half-width katakana block. 56 characters, one terminal column
# each -- full-width katakana would be two columns and would break every
# cursor calculation in curtain.py.
_BLOCK = [chr(code) for code in range(0xFF66, 0xFF9E)]

_LETTERS = "abcdefghijklmnopqrstuvwxyz"

# Letters map positionally into the block. Case-folded: distinguishing case
# would need 52 glyphs and buys nothing for a display face.
_LETTER_MAP = {letter: _BLOCK[i] for i, letter in enumerate(_LETTERS)}

# Digits reuse the LANGUAGE's assignments, so a number looks the same in
# program text and in transliterated output. Consistency is free here.
_DIGIT_MAP = {d: GLYPHS[d] for d in "0123456789"}

TABLE: dict[str, str] = {**_LETTER_MAP, **_DIGIT_MAP}


def transliterate(text: str) -> str:
    """Render text in glyphs. Unmapped characters pass through unchanged.

    Spaces and punctuation are deliberately preserved: dropping them would
    destroy word boundaries and make the result unreadable even to someone
    fluent in the glyph alphabet, which would prejudge the very question
    this experiment exists to answer.
    """
    return "".join(TABLE.get(char.lower(), char) for char in text)
