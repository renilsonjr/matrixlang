"""C4 — the reversible display table.

This is what makes the cascade *output* rather than decoration: a person,
a program or a model holding the table can recover the text exactly.

Not the language's glyph face. This table's output is never lexed, so it
owes nothing to bijectivity with the lexer or to the round-trip
criterion — which is precisely what lets it cover the Latin alphabet at
all. The language's face cannot: it has taken 35 of the block's 56
glyphs, leaving 21 free where 26 letters are needed.
"""

import random
import string

import pytest

from matrixlang.glyphs import GLYPHS
from matrixlang.translit import (
    ESCAPE,
    REVERSE,
    SHIFT,
    TABLE,
    table_for_readers,
    transliterate,
    untransliterate,
)

# --- The property the whole design rests on -----------------------------


@pytest.mark.parametrize(
    "text",
    [
        "wake up, Neo",
        "Neo",
        "neo",
        "NEO",
        "0123456789",
        "",
        " ",
        "hello world",
        "-7",
        "a.b,c!d?e",
        "MiXeD CaSe 123",
    ],
)
def test_transliteration_round_trips(text):
    assert untransliterate(transliterate(text)) == text


def test_round_trip_holds_over_fuzzed_strings():
    # The old alphabet was `string.printable + "áçñ日本語"` — which contains
    # no glyphs, so the fuzz could not reach the one case that broke the
    # invariant. A test that cannot fail proves nothing; the glyphs and
    # the markers are in the alphabet now.
    rng = random.Random(7)
    alphabet = (
        string.printable + "áçñ日本語" + "".join(REVERSE) + SHIFT + ESCAPE
    )
    for _ in range(4000):
        text = "".join(rng.choice(alphabet) for _ in range(rng.randint(0, 40)))
        assert untransliterate(transliterate(text)) == text, repr(text)


# --- The case the old fuzz could not reach ------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "ｱ",                      # a language glyph in a string literal
        "aｱb",
        "ｱｲｳ",
        "wake up, ｱ",
    ],
)
def test_a_glyph_in_the_input_still_round_trips(text):
    # Reachable from a .rain file: `trace "ｱ"` prints a glyph, the cascade
    # shows it, and before this a reader decoding with the published table
    # got 'g'. Passthrough characters that are already glyphs decoded as
    # though they had been encoded.
    assert untransliterate(transliterate(text)) == text


def test_the_markers_themselves_round_trip():
    # SHIFT decoded to nothing at all: it was consumed as a marker.
    for marker in (SHIFT, ESCAPE):
        assert untransliterate(transliterate(marker)) == marker
    assert untransliterate(transliterate(SHIFT + ESCAPE + "a")) == SHIFT + ESCAPE + "a"


def test_the_escape_marker_is_not_also_an_encoded_glyph():
    assert ESCAPE not in REVERSE
    assert ESCAPE != SHIFT


# --- The three decisions that make reversibility hold -------------------


def test_case_survives_because_uppercase_uses_a_shift_glyph():
    # Case-folding is shorter and is what a first attempt reaches for.
    # It would render 'Neo' and 'neo' identically and lose the difference.
    assert transliterate("Neo") != transliterate("neo")


def test_the_shift_glyph_precedes_the_letter_it_marks():
    assert transliterate("N") == SHIFT + TABLE["n"]


def test_uncovered_characters_pass_through_unchanged():
    # Reversible without escapes because the glyph alphabet is disjoint
    # from ASCII: a decoder always knows which is which.
    assert transliterate("日") == "日"


def test_space_stays_a_space():
    # Encoding it gains nothing and destroys the word boundaries that make
    # the result legible as structure even when the characters are not.
    assert " " in transliterate("wake up")


# --- Table integrity ----------------------------------------------------


def test_the_table_is_bijective():
    assert len(REVERSE) == len(TABLE)


def test_the_shift_marker_is_not_also_an_encoded_glyph():
    assert SHIFT not in REVERSE


def test_every_lowercase_letter_is_covered():
    assert set(string.ascii_lowercase) <= set(TABLE)


def test_every_digit_is_covered():
    assert set(string.digits) <= set(TABLE)


def test_digits_reuse_the_languages_own_glyphs():
    # So a number looks identical in program text and in output.
    for digit in string.digits:
        assert TABLE[digit] == GLYPHS[digit]


def test_every_glyph_is_a_single_column_character():
    # Full-width katakana would give ~90 slots but occupy two terminal
    # columns, which would break every cell calculation in the cascade.
    for glyph in TABLE.values():
        assert len(glyph) == 1


# --- The table is publishable -------------------------------------------


def test_the_reader_table_documents_the_shift_glyph():
    assert SHIFT in table_for_readers()


def test_the_reader_table_documents_passthrough():
    assert "pass through unchanged" in table_for_readers()
