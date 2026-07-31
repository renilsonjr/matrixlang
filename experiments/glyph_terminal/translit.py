"""A complete, reversible text-to-glyph dictionary.

EXPERIMENT. Not part of the shipped package, not imported by anything in
src/matrixlang/, and deliberately outside it so the architecture guard and
the katakana-containment guard do not apply.

This is NOT the language's glyph face. The distinction matters:

  glyphs.GLYPHS   the LANGUAGE's face. 32 slots, bijective, round-trips
                  through the lexer. Governed by D-03 and spec section 4.3.
  this module     a DISPLAY dictionary. Its output is never lexed, so it
                  owes nothing to D-03 and may reuse glyphs the language
                  assigns -- no parser ever has to tell them apart.

**Reversibility is the point.** The goal is glyph-only output that a
person, a program or a model can still decode given the table:

    untransliterate(transliterate(text)) == text      for ALL text

Three design decisions make that hold.

1. UPPERCASE USES A SHIFT GLYPH. Case-folding would be shorter and is what
   a first attempt reaches for, but it destroys information: 'Neo' and
   'neo' would render identically and no reader could recover which was
   meant. One marker glyph before a letter costs a character and keeps the
   text decodable.

2. UNCOVERED CHARACTERS PASS THROUGH UNCHANGED, AND THAT IS STILL
   REVERSIBLE. The glyph alphabet is disjoint from ASCII, so a decoder can
   always tell an encoded character from a passed-through one. There is no
   ambiguity to resolve and no escape sequence to get wrong.

3. SPACE STAYS A SPACE. Encoding it would gain nothing and destroy word
   boundaries, which are most of what makes the result legible as
   structure even when the characters are not.

The alphabet is the half-width forms block (U+FF61-FF9D, 61 single-column
characters). Full-width katakana would give ~90, but they occupy two
terminal columns and would break every cursor calculation in the cascade.
"""

from matrixlang.glyphs import GLYPHS

# 61 single-column glyphs: half-width punctuation (FF61-FF65) then katakana
# (FF66-FF9D). Single-column is a hard requirement -- see the module docstring.
_POOL = [chr(code) for code in range(0xFF61, 0xFF9E)]

_LETTERS = "abcdefghijklmnopqrstuvwxyz"

# The 20 punctuation marks that actually appear in MatrixLang output:
# string contents, the minus sign on negative integers, and ordinary prose.
_PUNCTUATION = ".,!?'\"-:;()[]/+*=_@#"

# Digits reuse the LANGUAGE's own glyphs, so a number looks identical in
# program text and in transliterated output. Consistency costs nothing.
_DIGITS = {digit: GLYPHS[digit] for digit in "0123456789"}

_taken = set(_DIGITS.values())
_available = [glyph for glyph in _POOL if glyph not in _taken]

_letter_map = {}
_punct_map = {}
for _char in _LETTERS:
    _letter_map[_char] = _available.pop(0)
for _char in _PUNCTUATION:
    _punct_map[_char] = _available.pop(0)

# Marks the NEXT glyph as uppercase. This is what makes case survive.
SHIFT = _available.pop(0)

TABLE: dict[str, str] = {**_letter_map, **_DIGITS, **_punct_map}
REVERSE: dict[str, str] = {glyph: char for char, glyph in TABLE.items()}

assert len(REVERSE) == len(TABLE), "glyph collision — the table is not bijective"
assert SHIFT not in REVERSE, "the shift marker collides with an encoded glyph"


def transliterate(text: str) -> str:
    """Render text in glyphs. Reversible via untransliterate()."""
    out = []
    for char in text:
        lowered = char.lower()
        if lowered in TABLE:
            if char.isupper():
                out.append(SHIFT)
            out.append(TABLE[lowered])
        else:
            out.append(char)          # passthrough; still decodable
    return "".join(out)


def untransliterate(glyphs: str) -> str:
    """Recover the original text. The inverse of transliterate()."""
    out = []
    shifted = False
    for char in glyphs:
        if char == SHIFT:
            shifted = True
            continue
        decoded = REVERSE.get(char, char)
        out.append(decoded.upper() if shifted else decoded)
        shifted = False
    return "".join(out)


def table_for_readers() -> str:
    """The dictionary, printable — so a person or a model can decode output.

    An LLM handed this table and a line of glyphs can recover the text
    without any other context, which is the point of keeping the mapping
    reversible rather than merely pretty.
    """
    rows = [f"  {char} {glyph}" for char, glyph in TABLE.items()]
    rows.append(f"  {SHIFT} marks the next glyph as uppercase")
    rows.append("  space and any unlisted character pass through unchanged")
    return "\n".join(rows)
