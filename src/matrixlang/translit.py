"""A complete, reversible text-to-glyph dictionary.

This is NOT the language's glyph face. The distinction matters:

  glyphs.GLYPHS   the LANGUAGE's face. 44 slots, bijective, round-trips
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

2. UNCOVERED CHARACTERS PASS THROUGH UNCHANGED, AND AN ESCAPE MARKER
   KEEPS THAT REVERSIBLE. The reasoning used to be that the glyph alphabet
   is disjoint from ASCII, so a decoder can always tell an encoded
   character from a passed-through one, and no escape was needed.

   That was wrong for one case, and the case is reachable: a string
   literal may itself contain a glyph. A program that traces a glyph
   printed it, the glyph passed through unencoded, and a reader decoding
   with this table got back a letter — because the decoder cannot
   distinguish a glyph that was ENCODED from one that was merely PASSED
   THROUGH. The two markers had the same problem: SHIFT decoded to
   nothing at all.

   A glyph in the input is therefore prefixed with ESCAPE, meaning "the
   next character is literal". The invariant is total again, and the fuzz
   that is supposed to prove it now includes glyphs in its alphabet —
   before, it drew from `string.printable` plus a few accents, so it could
   not reach the failing case at all.

   `escape_glyphs=False` opts out, and exactly one caller does: the
   cascade's SOURCE lines. Those are already documented as not decodable
   — the language's own glyphs and this table overlap, so a naive decode
   garbles keywords either way — and escaping each of them would double
   the height of every line on screen for a property that line does not
   have. OUTPUT keeps the guarantee, and output is the half anyone would
   want to read back.

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

# Marks the NEXT character as literal — used when the input already
# contains a glyph or a marker. Without it, such a character decodes as
# though it had been encoded.
ESCAPE = _available.pop(0)

TABLE: dict[str, str] = {**_letter_map, **_DIGITS, **_punct_map}
REVERSE: dict[str, str] = {glyph: char for char, glyph in TABLE.items()}

assert len(REVERSE) == len(TABLE), "glyph collision — the table is not bijective"
assert SHIFT not in REVERSE, "the shift marker collides with an encoded glyph"
assert ESCAPE not in REVERSE, "the escape marker collides with an encoded glyph"
assert ESCAPE != SHIFT, "the two markers must be distinguishable"

_LITERAL = frozenset(REVERSE) | {SHIFT, ESCAPE}


def transliterate(text: str, escape_glyphs: bool = True) -> str:
    """Render text in glyphs. Reversible via untransliterate(), for all text.

    `escape_glyphs=False` drops the guarantee for input that already
    contains glyphs, in exchange for not growing the line. See the module
    docstring: only the cascade's source lines use it.
    """
    out = []
    for char in text:
        lowered = char.lower()
        if escape_glyphs and char in _LITERAL:
            # Already a glyph or a marker: say so, or the decoder will
            # read it as something this function encoded.
            out.append(ESCAPE)
            out.append(char)
        elif lowered in TABLE:
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
    literal = False
    for char in glyphs:
        if literal:
            out.append(char)
            literal = False
            continue
        if char == ESCAPE:
            literal = True
            continue
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
    rows.append(f"  {ESCAPE} marks the next character as literal")
    rows.append("  space and any unlisted character pass through unchanged")
    return "\n".join(rows)
