"""The 32-slot glyph table — D-03's fixed bijective mapping.

Pure data; imports nothing. Keys are the ASCII slot spellings from the
language spec §3.1; values are single half-width katakana (U+FF66–FF9D),
which render in any terminal with zero font work. The set is swappable:
if a real film-glyph font ever exists, only this table changes (§6.2).

Assignments are loosely mnemonic where a sound offered itself (ﾄ "to" for
trace, ﾚ "re" for redpill, ﾃ "te" for dejavu) and arbitrary elsewhere;
the tests pin bijectivity and coverage, not the choices.
"""

GLYPHS: dict[str, str] = {
    # keywords
    "construct": "ｱ",  # the spec's own fragment: ｱ x = 5
    "trace": "ﾄ",
    "redpill": "红",
    "bluepill": "蓝",
    # "redpill": "ﾚ",
    # "bluepill": "ﾌ",
    "dejavu": "ﾃ",
    "flatline": "ﾗ",
    "true": "ｼ",
    "false": "ｷ",
    # operators
    "+": "加",
    "-": "减",
    # "+": "ﾀ",
    # "-": "ﾋ",
    "*": "ｶ",
    "/": "ﾜ",
    "=": "ﾅ",
    "==": "ﾆ",
    "!=": "ﾇ",
    "<": "ｻ",
    ">": "ｿ",
    "<=": "ｾ",
    ">=": "ｽ",
    # punctuation
    "(": "ｸ",
    ")": "ｹ",
    # digits, per-digit (§6.2: 10 renders as two glyphs)
    "0": "ｦ",
    "1": "ｧ",
    "2": "ｨ",
    "3": "ｩ",
    "4": "ｪ",
    "5": "ｫ",
    "6": "ｬ",
    "7": "ｭ",
    "8": "ｮ",
    "9": "ｯ",
    # comment marker
    "#": "ﾒ",
}

REVERSE: dict[str, str] = {glyph: slot for slot, glyph in GLYPHS.items()}

# The rain alphabet (Stage 5). The whole half-width katakana block, of
# which the 32 language slots above are a subset: a field built from 32
# repeating characters reads as a pattern, not as rain. Built from
# codepoints rather than literals, so the block stays greppable and this
# file remains the only place a glyph is chosen.
RAIN_ALPHABET: tuple[str, ...] = tuple(chr(code) for code in range(0xFF66, 0xFF9E))
