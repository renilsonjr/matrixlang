import pytest

from matrixlang.errors import LexError
from matrixlang.glyphs import BLOCK_END, BLOCK_START, GLYPHS
from matrixlang.lexer import lex
from matrixlang.tokens import KEYWORDS, TokenType


def kinds(source: str) -> list[TokenType]:
    """Token types only — keeps assertions readable."""
    return [t.type for t in lex(source)]


def pairs(source: str) -> list[tuple[TokenType, str]]:
    """(type, lexeme) pairs."""
    return [(t.type, t.lexeme) for t in lex(source)]


def test_single_character_operators():
    assert kinds("+ - * / ( )") == [
        TokenType.PLUS,
        TokenType.MINUS,
        TokenType.STAR,
        TokenType.SLASH,
        TokenType.LPAREN,
        TokenType.RPAREN,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_whitespace_is_skipped_but_newlines_are_not():
    assert kinds("+\t+\r+") == [
        TokenType.PLUS,
        TokenType.PLUS,
        TokenType.PLUS,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_trailing_newline_is_synthesised_exactly_once():
    with_newline = kinds("+\n")
    without_newline = kinds("+")
    assert with_newline == without_newline
    assert with_newline == [TokenType.PLUS, TokenType.NEWLINE, TokenType.EOF]


def test_empty_source_yields_only_eof():
    assert kinds("") == [TokenType.EOF]


def test_blank_lines_produce_newlines_and_nothing_else():
    # Acceptance case 7.
    assert kinds("\n\n\n+") == [
        TokenType.NEWLINE,
        TokenType.NEWLINE,
        TokenType.NEWLINE,
        TokenType.PLUS,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_line_and_column_are_one_indexed_and_track_newlines():
    tokens = lex("+\n  +")
    assert (tokens[0].line, tokens[0].column) == (1, 1)
    assert (tokens[2].line, tokens[2].column) == (2, 3)


def test_unknown_character_reports_line_and_column():
    # Acceptance case 9.
    with pytest.raises(LexError) as excinfo:
        lex("+ +\n+ @")
    error = excinfo.value
    assert error.line == 2
    assert error.column == 3
    assert "@" in str(error)


def test_two_character_operators_win_over_single():
    # Acceptance case 4.
    assert kinds("<= >= == !=") == [
        TokenType.LTE,
        TokenType.GTE,
        TokenType.EQ,
        TokenType.NEQ,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_single_character_comparisons_still_work():
    assert kinds("< > =") == [
        TokenType.LT,
        TokenType.GT,
        TokenType.ASSIGN,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_two_character_operator_advances_column_by_two():
    tokens = lex("<= <=")
    assert tokens[0].column == 1
    assert tokens[1].column == 4


def test_bare_bang_is_an_error():
    with pytest.raises(LexError) as excinfo:
        lex("! ")
    assert excinfo.value.column == 1


def test_multi_digit_number_is_one_token_with_int_value():
    tokens = lex("1024")
    assert tokens[0].type is TokenType.NUMBER
    assert tokens[0].lexeme == "1024"
    assert tokens[0].value == 1024


def test_numbers_and_operators_interleave():
    assert pairs("2+3") == [
        (TokenType.NUMBER, "2"),
        (TokenType.PLUS, "+"),
        (TokenType.NUMBER, "3"),
        (TokenType.NEWLINE, ""),
        (TokenType.EOF, ""),
    ]


def test_number_column_points_at_first_digit():
    tokens = lex("  42")
    assert tokens[0].column == 3


def test_non_ascii_digits_are_rejected():
    # str.isdigit() would accept these. See Global Constraints.
    with pytest.raises(LexError):
        lex("４")


def test_identifier_is_scanned():
    tokens = lex("counter")
    assert tokens[0].type is TokenType.IDENT
    assert tokens[0].lexeme == "counter"
    assert tokens[0].value is None


def test_keyword_is_recognised():
    # Acceptance case 2.
    assert kinds("construct") == [
        TokenType.CONSTRUCT,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_keyword_matching_does_not_fire_on_a_prefix():
    # Acceptance case 3. 'constructor' starts with 'construct'.
    tokens = lex("constructor = 1")
    assert tokens[0].type is TokenType.IDENT
    assert tokens[0].lexeme == "constructor"


def test_booleans_carry_python_bool_values():
    tokens = lex("true false")
    assert (tokens[0].type, tokens[0].value) == (TokenType.TRUE, True)
    assert (tokens[1].type, tokens[1].value) == (TokenType.FALSE, False)


def test_identifiers_may_contain_digits_and_underscores():
    tokens = lex("_x1 count_2")
    assert [t.lexeme for t in tokens[:2]] == ["_x1", "count_2"]


def test_identifiers_may_not_start_with_a_digit():
    assert kinds("1x") == [
        TokenType.NUMBER,
        TokenType.IDENT,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]




def test_assignment_statement_lexes_as_specified():
    # Acceptance case 1 — the parent spec's opening commit.
    assert kinds("x = 2 + 3") == [
        TokenType.IDENT,
        TokenType.ASSIGN,
        TokenType.NUMBER,
        TokenType.PLUS,
        TokenType.NUMBER,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_string_keeps_raw_lexeme_and_decoded_value():
    # Acceptance case 5.
    tokens = lex('"wake up, "')
    assert tokens[0].type is TokenType.STRING
    assert tokens[0].lexeme == '"wake up, "'
    assert tokens[0].value == "wake up, "


def test_string_escapes_are_decoded():
    tokens = lex(r'"a\"b\\c\nd"')
    assert tokens[0].value == 'a"b\\c\nd'


def test_string_concatenation_expression_lexes():
    assert kinds('"wake up, " + name') == [
        TokenType.STRING,
        TokenType.PLUS,
        TokenType.IDENT,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_unterminated_string_reports_the_opening_quote():
    # Acceptance case 8.
    with pytest.raises(LexError) as excinfo:
        lex('trace "unterminated')
    error = excinfo.value
    assert error.line == 1
    assert error.column == 7
    assert "unterminated" in str(error)


def test_newline_inside_string_is_unterminated():
    with pytest.raises(LexError) as excinfo:
        lex('"broken\n"')
    assert excinfo.value.line == 1


def test_unknown_escape_is_an_error():
    with pytest.raises(LexError) as excinfo:
        lex(r'"\q"')
    assert "\\q" in str(excinfo.value)
    assert excinfo.value.column == 2


def test_empty_string_is_valid():
    tokens = lex('""')
    assert tokens[0].value == ""


def test_comment_is_emitted_not_discarded():
    # Acceptance case 6.
    tokens = lex("trace x  # wake up")
    assert [t.type for t in tokens] == [
        TokenType.TRACE,
        TokenType.IDENT,
        TokenType.COMMENT,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]
    assert tokens[2].lexeme == "# wake up"


def test_comment_stops_at_the_newline():
    assert kinds("# one\n# two\n") == [
        TokenType.COMMENT,
        TokenType.NEWLINE,
        TokenType.COMMENT,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]


def test_hash_inside_a_string_is_not_a_comment():
    tokens = lex('"# not a comment"')
    assert tokens[0].type is TokenType.STRING
    assert tokens[0].value == "# not a comment"


def test_comment_column_points_at_the_hash():
    tokens = lex("x # here")
    assert tokens[1].column == 3


def test_whitespace_only_source_yields_only_eof():
    # No tokens were produced, so there is no statement to terminate:
    # the synthesised NEWLINE keys on "produced no tokens", not "source empty".
    assert kinds("   ") == [TokenType.EOF]


def test_glyph_keywords_lex_as_keywords():
    # ｱ x ﾅ ｫ  ==  construct x = 5. One lexer, no mode flag (§6.3).
    tokens = lex("ｱ x ﾅ ｫ\n")
    assert [t.type for t in tokens] == [
        TokenType.CONSTRUCT,
        TokenType.IDENT,
        TokenType.ASSIGN,
        TokenType.NUMBER,
        TokenType.NEWLINE,
        TokenType.EOF,
    ]
    assert tokens[3].value == 5


def test_the_spec_s_own_fragment_means_what_the_spec_says():
    # Parent spec §1's only code example, mixed-face: glyph keyword, ASCII
    # everything else. Mixed-face source is legal — D-03's free win.
    assert [t.type for t in lex("ｱ x = 5\n")] == [
        t.type for t in lex("construct x = 5\n")
    ]


def test_glyph_operators_lex_as_operators():
    # ｧ ﾆ ｧ  ==  1 == 1. A glyph operator is ONE char even when its ASCII
    # spelling is two.
    tokens = lex("ｧ ﾆ ｧ\n")
    assert [t.type for t in tokens[:3]] == [
        TokenType.NUMBER,
        TokenType.EQ,
        TokenType.NUMBER,
    ]


def test_glyph_booleans_carry_their_values():
    # The parser reads token.value for BoolLiteral; a glyph ｼ that lexes
    # as TRUE with value=None would build BoolLiteral(None).
    tokens = lex("ｼ ｷ\n")
    assert tokens[0].type is TokenType.TRUE
    assert tokens[0].value is True
    assert tokens[1].type is TokenType.FALSE
    assert tokens[1].value is False


def test_glyph_digit_runs_decode_positionally():
    # §6.2: digits map per-digit. ｧｦ is 10, not two tokens.
    tokens = lex("ﾄ ｧｦ\n")
    assert tokens[1].type is TokenType.NUMBER
    assert tokens[1].value == 10


def test_a_number_may_mix_faces_within_one_run():
    # 1ｦｦ is 100. Without this, adjacent NUMBER NUMBER tokens would parse
    # into a baffling error two stages away from the actual cause.
    tokens = lex("ﾄ 1ｦｦ\n")
    assert tokens[1].type is TokenType.NUMBER
    assert tokens[1].value == 100


def test_glyph_comments_normalize_to_canonical_trivia():
    # §6.1 invariant: trivia starts with ASCII '#'. A glyph-marked comment
    # must store '#…' or parse(render_glyph(t)) carries different trivia
    # than t and the §4.3 equality fails.
    tokens = lex("ﾄ x ﾒ note\n")
    comment = tokens[2]
    assert comment.type is TokenType.COMMENT
    assert comment.lexeme == "# note"


def test_a_block_character_outside_the_table_is_still_an_error():
    # Was test_katakana_outside_the_table_is_still_an_error, which named ﾝ
    # (U+FF9D) as its specimen of an unmapped glyph. Task 7 spent ﾝ on `%`,
    # the last free slot, and this test broke — its premise had been true
    # only by accident of which slots happened to be unclaimed that week.
    # It had already drifted once besides: the comment said "the 32 mapped
    # glyphs" long after the table passed 32.
    #
    # First fix derived the specimen from range(0xFF61, 0xFF9E) instead —
    # wider than glyphs.py's own BLOCK_START (0xFF66), by five code
    # points (U+FF61-FF65: halfwidth ideographic full stop, both corner
    # brackets, comma, and the middle dot — punctuation, not katakana).
    # Nothing in glyphs.py ever assigns a code point below BLOCK_START,
    # so those five can NEVER enter GLYPHS — which meant the non-vacuity
    # assertion below could never fire again no matter how full the
    # table's REAL, assignable range got. That hid exactly the scenario
    # it existed to catch, which is what happened the moment this task
    # filled the table to 56/56.
    #
    # Second fix (this one): scan glyphs.py's own BLOCK_START..BLOCK_END,
    # not a hand-picked bound and not the wider Unicode "Halfwidth and
    # Fullwidth Forms" block. That range is now, by this task's own
    # ledger (56 used, 0 free), genuinely and permanently fully claimed —
    # `unclaimed` below is expected to be empty from this commit forward,
    # not by accident of which slots happen to be free this week, but
    # because there are no more slots, ever. The loop stays rather than
    # getting deleted: if a later change ever widens BLOCK_END or frees a
    # slot, this starts testing the freed code point again with no edit
    # needed here — the assertion is capable of firing on that, unlike
    # the range it replaces. What the assertion checks flipped along with
    # it: it no longer demands a free slot exist (impossible to promise
    # once the table is closed), it demands the table's real range and
    # the ledger's "0 free" claim agree.
    unclaimed = [
        chr(cp)
        for cp in range(BLOCK_START, BLOCK_END + 1)
        if chr(cp) not in set(GLYPHS.values())
    ]
    assert not unclaimed, (
        f"the ledger says 56 used / 0 free but {unclaimed!r} is still "
        "unclaimed in glyphs.py's own BLOCK_START..BLOCK_END range — "
        "update this test's expectation or fix the ledger"
    )

    for glyph in unclaimed:
        with pytest.raises(LexError) as excinfo:
            lex(f"construct {glyph} = 1\n")
        assert excinfo.value.column == 11, glyph


def test_every_slot_lexes_to_the_same_type_as_its_ascii_spelling():
    # The whole-table property, so a future glyph-set swap stays honest.
    # Two slots are excluded because they never stand alone as a token:
    # '#' opens a comment, checked above, and '.' (#135) is consumed
    # inside a NUMBER -- which is exactly what makes '.5' and '1.' lex
    # errors without a rule of their own.
    for slot, glyph in GLYPHS.items():
        if slot in ("#", "."):
            continue
        assert lex(glyph + "\n")[0].type is lex(slot + "\n")[0].type, slot


# --- control characters (security: terminal escape injection) -------------
#
# The lexer preserves raw source bytes verbatim, which is right for
# round-tripping and wrong for safety: an ESC byte in a string or a comment
# reached the terminal unescaped through `trace`, `parse`, `render` and the
# REPL echo. Escaping at those output sites would break the §4.3 round trip
# (render would emit '\x1b' as four characters, which re-lexes as four
# characters), so the byte is refused here instead — where the existing
# "a newline inside a string is an error" rule already lives.


def test_an_escape_byte_in_a_string_is_rejected():
    with pytest.raises(LexError) as excinfo:
        lex('trace "\x1b[31mred"\n')
    assert "control character" in str(excinfo.value)
    assert "U+001B" in str(excinfo.value)
    assert excinfo.value.line == 1
    assert excinfo.value.column == 8


def test_an_escape_byte_in_a_comment_is_rejected():
    # Comments need no quoting, so they are the easier carrier of the two.
    with pytest.raises(LexError) as excinfo:
        lex("construct x = 1  #\x1b[8mhidden\n")
    assert "control character" in str(excinfo.value)
    assert excinfo.value.line == 1
    assert excinfo.value.column == 19


def test_the_whole_rejected_range_is_refused():
    # C0, DEL and C1. Tab and newline are carved out and tested separately.
    for codepoint in (0x00, 0x07, 0x1B, 0x1F, 0x7F, 0x80, 0x9F):
        with pytest.raises(LexError):
            lex(f'trace "a{chr(codepoint)}b"\n')
        with pytest.raises(LexError):
            lex(f"# a{chr(codepoint)}b\n")


def test_a_tab_is_still_legal_inside_a_string():
    # Carve-out: tab cannot drive a terminal, and refusing it would break
    # working programs for no security gain.
    tokens = lex('trace "a\tb"\n')
    assert tokens[1].value == "a\tb"


def test_printable_text_either_side_of_the_range_is_untouched():
    assert lex('trace " ~"\n')[1].value == " ~"
    assert lex('trace " ÿ"\n')[1].value == " ÿ"


def test_no_output_path_can_emit_a_control_byte_from_source():
    # THE security property, stated once. Every path that writes source-derived
    # text to a terminal — trace, parse, render, the REPL echo — is fed from
    # lex(), so refusing the byte here closes all of them at once. If this ever
    # fails, one of those paths has grown a way to reach the terminal that does
    # not go through the lexer.
    hostile = 'construct x = "\x1b[31m"  #\x1b[8m\ntrace x\n'
    with pytest.raises(LexError):
        lex(hostile)


# --- Stage 6: agent, jackout, comma -------------------------------------


def test_agent_lexes_as_a_keyword():
    from matrixlang.tokens import TokenType

    types = [t.type for t in lex("agent f\n")]
    assert types[0] is TokenType.AGENT


def test_jackout_lexes_as_a_keyword():
    from matrixlang.tokens import TokenType

    types = [t.type for t in lex("jackout 1\n")]
    assert types[0] is TokenType.JACKOUT


def test_a_comma_lexes():
    from matrixlang.tokens import TokenType

    types = [t.type for t in lex("f(a, b)\n")]
    assert TokenType.COMMA in types


def test_the_new_slots_lex_in_the_glyph_face_too():
    from matrixlang.glyphs import GLYPHS
    from matrixlang.tokens import TokenType

    source = f"{GLYPHS['agent']} f{GLYPHS['(']}a{GLYPHS[',']}b{GLYPHS[')']}\n"
    types = [t.type for t in lex(source)]
    assert types[0] is TokenType.AGENT
    assert TokenType.COMMA in types


def test_jackout_lexes_in_the_glyph_face():
    from matrixlang.glyphs import GLYPHS
    from matrixlang.tokens import TokenType

    types = [t.type for t in lex(f"{GLYPHS['jackout']} 1\n")]
    assert types[0] is TokenType.JACKOUT


def test_the_input_keywords_lex_in_both_faces():
    from matrixlang.glyphs import GLYPHS

    for ascii_word in ("jackin", "decode"):
        (token, _eof) = [t for t in lex(ascii_word) if t.type is not TokenType.NEWLINE]
        assert token.type is KEYWORDS[ascii_word], f"{ascii_word} did not lex"
        (glyph_token, _) = [
            t for t in lex(GLYPHS[ascii_word]) if t.type is not TokenType.NEWLINE
        ]
        assert glyph_token.type is token.type, f"{ascii_word}'s glyph face did not lex"


def test_encode_lexes_in_both_faces():
    from matrixlang.glyphs import GLYPHS

    (token, _eof) = [t for t in lex("encode") if t.type is not TokenType.NEWLINE]
    assert token.type is KEYWORDS["encode"]
    (glyph_token, _) = [
        t for t in lex(GLYPHS["encode"]) if t.type is not TokenType.NEWLINE
    ]
    assert glyph_token.type is token.type


def test_a_number_literal_past_the_old_digit_ceiling_now_lexes():
    # Before #135, CPython's int(str) refused past
    # sys.get_int_max_str_digits() with a bare ValueError, and this test
    # pinned the LexError this module converted that into. decimal.Decimal
    # has no such ceiling -- Decimal(digits) is exact regardless of length
    # -- so the literal now lexes cleanly. The cap did not vanish, it moved
    # to display: tests/test_values.py::
    # test_a_number_too_long_to_render_raises_a_named_signal pins it there
    # now, and interpreter.py's Trace handler converts that into a
    # positioned RuntimeErrorML (see
    # test_an_oversized_literal_fails_at_trace_not_at_lex_or_parse below).
    import sys
    from decimal import Decimal

    limit = sys.get_int_max_str_digits()
    digits = "1" * (limit + 1)
    tokens = [t for t in lex("trace " + digits + "\n") if t.type is TokenType.NUMBER]
    assert tokens[0].value == Decimal(digits)


def test_a_number_literal_at_the_digit_ceiling_still_lexes():
    # The boundary from below. A guard that refused every long literal
    # would pass the test above and break nothing a test noticed.
    import sys

    limit = sys.get_int_max_str_digits()
    (token, *_rest) = lex("1" * limit)
    assert token.type is TokenType.NUMBER
    assert token.value == int("1" * limit)


def test_a_glyph_number_past_the_old_ceiling_now_lexes_too():
    # The digits are transliterated back through REVERSE before Decimal()
    # sees them, so the glyph face has no ceiling for the same reason the
    # ASCII face above does not: both faces are the same language or
    # neither is. Kept as its own test (rather than folded into the ASCII
    # one) because it is the proof that per-digit mapping still works at
    # this length, which the ASCII test cannot show.
    import sys
    from decimal import Decimal

    limit = sys.get_int_max_str_digits()
    digits = "1" * (limit + 1)
    tokens = [t for t in lex(GLYPHS["1"] * (limit + 1)) if t.type is TokenType.NUMBER]
    assert tokens[0].value == Decimal(digits)
