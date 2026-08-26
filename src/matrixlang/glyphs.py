"""The 56-slot glyph table — D-03's fixed bijective mapping.

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
    "redpill": "ﾚ",
    "bluepill": "ﾌ",
    "dejavu": "ﾃ",
    "flatline": "ﾗ",
    "true": "ｼ",
    "false": "ｷ",
    # Stage 6. An Agent is a callable, reusable program in the films;
    # jackout is leaving the construct and coming back with something.
    "agent": "ｴ",
    "jackout": "ﾖ",
    # Stage 7. A keyword rather than a built-in `length(xs)`: a built-in
    # name is an identifier, so it would be the first piece of the
    # language surface rendered in Latin in the glyph face, and D-03's
    # claim is that the only readable text in a wall of green is the
    # thing you wrote.
    "length": "ﾙ",
    # Stage 9. `and`, `or` and `not` as crew vocabulary: splice joins two
    # signals, fork is a branch in the path, unplug cuts it. The films
    # have no concept of logical conjunction, so these are metaphors of
    # connection rather than film concepts — recorded in the Stage 9
    # design §1 rather than pretended otherwise.
    "splice": "ﾁ",
    "fork": "ﾂ",
    "unplug": "ｳ",
    # Input. `jackin` takes ｲ for the "i" of "in", pairing with jackout's
    # ﾖ: one carries a value out of a function, the other brings one in
    # from the world. `decode` takes ｺ for the "co" in the middle of it.
    "jackin": "ｲ",
    "decode": "ｺ",
    # `encode` takes ﾏ ("ma") — arbitrary, like most of the table. It is
    # decode's mirror in meaning, not in sound; ｺ's neighbours were taken.
    "encode": "ﾏ",
    # Dictionaries. `oracle` takes ｵ for the "o" it starts with, the same
    # kind of mnemonic as ｲ for jackin. `keymaker` takes ﾔ arbitrarily --
    # the Keymaker's own sounds were long gone by this point in the table.
    "keymaker": "ﾔ",
    "oracle": "ｵ",
    # String methods. `trim` takes ﾘ, the "ri" of its own katakana
    # spelling ﾄﾘﾑ -- ﾄ and ﾑ were long gone, so the middle sound is what
    # was left. `fold` and `cleave` take ﾊ and ﾛ arbitrarily: almost every
    # sound in ﾌｫｰﾙﾄﾞ and ｸﾘｰﾌﾞ was already spent by this point in the
    # table. The one that wasn't -- ｰ, the prolonged-sound mark shared by
    # both spellings -- was passed over on purpose: it reads as
    # punctuation stretching the syllable before it, not as a word of its
    # own, which is what every other mnemonic assignment here rests on.
    "fold": "ﾊ",
    "trim": "ﾘ",
    "cleave": "ﾛ",
    # Loop control. Both arbitrary -- ｳｪｲｸ and ｸﾞﾘｯﾁ have no sound left
    # unspent. The two slots deliberately NOT taken are ｰ (U+FF70) and
    # ﾝ (U+FF9D): neither is a syllable, both read as punctuation, and
    # the next item in the register needs exactly two punctuation slots.
    "wake": "ﾉ",
    "glitch": "ﾕ",
    # Numbers. The point takes ｰ, the prolonged-sound mark. The
    # string-methods branch passed this slot over precisely because it
    # "reads as punctuation rather than a word" -- which is what a decimal
    # point is.
    ".": "ｰ",
    # operators
    "+": "ﾀ",
    "-": "ﾋ",
    "*": "ｶ",
    "/": "ﾜ",
    # The last slot. ﾝ was held back from loop control precisely because
    # it "reads as punctuation rather than a word" -- which is what a
    # remainder operator borrowed from arithmetic notation is. 56 used,
    # 0 free: the table is closed.
    "%": "ﾝ",
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
    ",": "ﾈ",
    # Adjacent, mirroring ( and ) which are adjacent too.
    "[": "ﾍ",
    "]": "ﾎ",
    # Adjacent, for the same reason ( ) and [ ] are adjacent.
    "{": "ﾐ",
    "}": "ﾑ",
    ":": "ﾓ",
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

# The block the language's glyphs are drawn from.
BLOCK_START = 0xFF66
BLOCK_END = 0xFF9D
