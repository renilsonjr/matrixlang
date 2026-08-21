import string

from matrixlang.glyphs import BLOCK_END, BLOCK_START, GLYPHS, REVERSE
from matrixlang.tokens import KEYWORDS


def test_the_table_covers_exactly_the_49_slots():
    # Language spec §3.1, plus Stage 6: 11 keywords (agent and jackout
    # join, length in Stage 7) + 11 operators + 2 parens + a comma +
    # 2 brackets + 10 digits + the '#' comment marker + Stage 9: 3 logical
    # operators (splice, fork, unplug) + input: jackin and decode
    # + encode.
    # + dictionaries: keymaker and oracle, and { } : for the literal.
    # Nothing more (identifiers and string contents stay ASCII, per D-03),
    # nothing less.
    expected = (
        set(KEYWORDS)
        | {"+", "-", "*", "/", "=", "==", "!=", "<", ">", "<=", ">="}
        | {"(", ")", ","}
        | {"[", "]"}
        | {"{", "}", ":"}
        | set(string.digits)
        | {"#"}
    )
    assert set(GLYPHS) == expected
    assert len(expected) == 49


def test_the_glyph_budget_is_tracked_not_discovered():
    # Stage 6 design §1: 24 free before, 3 spent, 21 left. Stage 7
    # spends 3 more for lists: 21 - 3 = 18 left. Stage 9 spends 3 more
    # for logical operators: 18 - 3 = 15 left. Input spends 2 for jackin
    # and decode: 15 - 2 = 13 left. encode spends 1: 13 - 1 = 12 left.
    # Dictionaries spend 5 -- keymaker, oracle, and the three punctuation
    # slots { } : -- so 12 - 5 = 7 left. Finite, and worth knowing.
    free = sum(
        1
        for code in range(BLOCK_START, BLOCK_END + 1)
        if chr(code) not in set(GLYPHS.values())
    )
    assert free == 7


def test_the_mapping_is_bijective():
    # §6.2 requires a bijection: two slots sharing a glyph would make the
    # glyph face ambiguous to lex.
    assert len(set(GLYPHS.values())) == len(GLYPHS)


def test_reverse_is_the_exact_inverse():
    assert REVERSE == {glyph: slot for slot, glyph in GLYPHS.items()}


def test_every_glyph_is_one_halfwidth_katakana_char():
    # Single chars from the halfwidth block (U+FF66–FF9D): they render in
    # any terminal today with zero font work, and single-char glyphs keep
    # column arithmetic trivial.
    for glyph in GLYPHS.values():
        assert len(glyph) == 1
        assert 0xFF66 <= ord(glyph) <= 0xFF9D


def test_construct_is_the_spec_s_own_fragment():
    # The parent spec's only code example is 'ｱ x = 5'. Honour it.
    assert GLYPHS["construct"] == "ｱ"


def test_glyphs_are_disjoint_from_every_ascii_alphabet():
    # §6.3's disjoint-alphabet property is what lets one lexer serve both
    # faces without a mode flag. If a glyph ever collided with ASCII, the
    # whole architecture would silently break.
    for glyph in GLYPHS.values():
        assert not glyph.isascii()


def test_every_language_glyph_is_inside_the_declared_block():
    # Was expressed against RAIN_ALPHABET, which existed to be sampled at
    # random. Nothing samples any more — the cascade carries the program —
    # so the containment rule is asserted against the block directly, which
    # is what it always actually meant.
    for glyph in GLYPHS.values():
        assert BLOCK_START <= ord(glyph) <= BLOCK_END


def test_every_glyph_is_a_single_character():
    assert all(len(glyph) == 1 for glyph in GLYPHS.values())
