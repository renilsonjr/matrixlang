"""C3 — the content-carrying field.

Pure and seeded, exactly as rain.py was. The difference is what falls:
random glyphs all look alike, so the decorative rain could tolerate bugs
this cannot. Both regressions below were real defects in the spike, and
both were invisible until the columns carried a program.

Nothing here touches Tk. Everything a viewer would actually see is
decided in this module, which is what keeps the window a thin edge.
"""

from random import Random

import pytest

from matrixlang.cascade import CascadeField, Kind
from matrixlang.glyphs import GLYPHS
from matrixlang.events import Error, Output, Statement
from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.translit import untransliterate


def field(width=40, height=20, seed=7):
    return CascadeField(width, height, Random(seed))


def only_column_levels(cells):
    """Levels of the single occupied column, ordered top to bottom."""
    columns = {c.col for c in cells}
    assert len(columns) <= 1, f"expected one column, got {columns}"
    return [lvl for _, lvl in sorted((c.row, c.level) for c in cells)]


def only_column(cells):
    """Glyphs of the single occupied column, ordered top to bottom.

    Columns are assigned at random, so a test with one stream must not
    assume column 0 — an earlier version did, and failed for that reason
    rather than for the property it was checking.
    """
    columns = {c.col for c in cells}
    assert len(columns) <= 1, f"expected one column, got {columns}"
    return [g for _, g in sorted((c.row, c.glyph) for c in cells)]


# --- Regression: lines must read top-to-bottom --------------------------


def test_a_line_reads_downward_in_natural_order():
    # The obvious layout puts the first character at the head, which renders
    # every line backwards. Harmless when nobody reads the glyphs; fatal
    # when the columns ARE the program.
    f = field()
    f.add("abc", Kind.SOURCE)
    for _ in range(6):
        cells = f.advance()
    painted = "".join(only_column(cells))
    assert painted and "abc".endswith(painted)


def test_the_full_line_appears_in_order_once_it_is_all_on_screen():
    f = field(height=20)
    f.add("wake", Kind.SOURCE)
    seen = []
    for _ in range(40):
        painted = only_column(f.advance())
        if len(painted) == 4:
            seen.append("".join(painted))
    assert seen and all(s == "wake" for s in seen)


# --- Regression: no two streams may share a column ----------------------


@pytest.mark.parametrize("seed", range(30))
def test_no_two_cells_ever_occupy_the_same_position(seed):
    # The first version returned a column to the free pool as soon as a
    # stream spawned, so two streams could share it and overwrite each
    # other — silently corrupting a line of the program.
    f = field(width=10, height=12, seed=seed)
    for i in range(40):
        f.add(f"line{i}", Kind.SOURCE if i % 2 else Kind.OUTPUT)
    for _ in range(80):
        cells = f.advance()
        positions = [(c.row, c.col) for c in cells]
        assert len(positions) == len(set(positions))


# --- Field invariants ---------------------------------------------------


@pytest.mark.parametrize("seed", range(10))
def test_every_painted_cell_is_in_bounds(seed):
    f = field(width=8, height=10, seed=seed)
    for i in range(20):
        f.add("abcdefgh", Kind.SOURCE)
    for _ in range(60):
        for cell in f.advance():
            assert 0 <= cell.row < 10
            assert 0 <= cell.col < 8


def test_the_head_is_strictly_the_brightest_cell():
    # A previous version of this assertion used max() over a list whose
    # insertion order already guaranteed the property, so it passed with
    # every level tied. Strict ordering is what has teeth.
    f = field()
    f.add("abcd", Kind.SOURCE)
    for _ in range(8):
        cells = f.advance()
    levels = only_column_levels(cells)
    # No `if len(...) > 1` guard: an empty column would satisfy that and
    # the test would prove nothing. Assert the trail is really there.
    assert len(levels) > 1
    assert levels == sorted(levels)
    assert levels[-1] > levels[0]


def test_the_field_empties_once_every_stream_has_fallen_off():
    f = field(height=6)
    f.add("ab", Kind.SOURCE)
    for _ in range(200):
        cells = f.advance()
        if f.is_empty():
            break
    assert f.is_empty()
    assert f.advance() == ()


def test_the_same_seed_produces_the_same_stream():
    a, b = field(seed=3), field(seed=3)
    for f in (a, b):
        f.add("hello", Kind.SOURCE)
        f.add("world", Kind.OUTPUT)
    for _ in range(20):
        assert a.advance() == b.advance()


def test_output_falls_slower_than_source_so_results_linger():
    fast = field(seed=1)
    fast.add("abcd", Kind.SOURCE)
    slow = field(seed=1)
    slow.add("abcd", Kind.OUTPUT)
    for _ in range(10):
        fast_cells, slow_cells = fast.advance(), slow.advance()
    assert max(c.row for c in fast_cells) > max(c.row for c in slow_cells)


def test_more_lines_than_columns_are_queued_not_dropped():
    f = field(width=3, height=10)
    for i in range(9):
        f.add(f"l{i}", Kind.SOURCE)
    total = 0
    for _ in range(200):
        total += len(f.advance())
    assert total > 0
    assert f.is_empty()


# --- Looping: the program's own material never stops falling ----------


def test_looping_is_off_by_default():
    f = field()
    f.add("ab", Kind.SOURCE)
    for _ in range(200):
        f.advance()
        if f.is_empty():
            break
    assert f.is_empty()


def test_a_looping_field_never_empties():
    f = CascadeField(20, 10, Random(7), loop=True)
    f.add("ab", Kind.SOURCE)
    for _ in range(500):
        f.advance()
    assert not f.is_empty()


def test_a_looping_field_always_has_something_on_screen():
    f = CascadeField(20, 10, Random(7), loop=True)
    f.add("wake up", Kind.OUTPUT)
    f.add("construct n", Kind.SOURCE)
    blanks = [i for i in range(500) if not f.advance()]
    assert blanks == []


def test_looping_replays_every_line_not_only_the_last():
    f = CascadeField(30, 12, Random(3), loop=True)
    f.add("aaa", Kind.SOURCE)
    f.add("bbb", Kind.OUTPUT)
    seen = set()
    for _ in range(600):
        for cell in f.advance():
            seen.add(cell.glyph)
    assert {"a", "b"} <= seen


def test_looping_still_reserves_one_column_per_stream():
    f = CascadeField(6, 10, Random(5), loop=True)
    for i in range(4):
        f.add(f"line{i}", Kind.SOURCE)
    for _ in range(400):
        positions = [(c.row, c.col) for c in f.advance()]
        assert len(positions) == len(set(positions))


def test_a_looping_field_with_no_material_stays_empty():
    # A program that produced nothing has nothing to replay. Looping must
    # not spin on an empty history.
    f = CascadeField(20, 10, Random(7), loop=True)
    for _ in range(50):
        assert f.advance() == ()


# --- Turning events into falling text -----------------------------------


def test_an_output_event_becomes_a_transliterated_stream():
    f = field()
    f.consume(Output(text="wake up", line=1))
    for _ in range(12):
        cells = f.advance()
    glyphs = "".join(only_column(cells))
    # Empty would decode to "" and satisfy `in`, proving nothing.
    assert glyphs
    assert untransliterate(glyphs) in "wake up"


def test_a_statement_event_becomes_its_glyph_face():
    f = field()
    program = parse(lex("construct n = 0\n"))
    f.consume(Statement(node=program.statements[0], line=1))
    assert not f.is_empty()


def test_a_block_statement_contributes_only_its_own_header_line():
    # Rendering a While yields its whole body, and every body statement
    # emits its own event. Taking the header alone is what stops each
    # loop body line from appearing twice.
    f = field()
    program = parse(lex("construct n = 0\ndejavu n < 3\n  n = n + 1\nflatline\n"))
    while_stmt = program.statements[1]
    f.consume(Statement(node=while_stmt, line=2))
    for _ in range(30):
        cells = f.advance()
        if cells:
            assert len({c.col for c in cells}) == 1


def test_source_falls_as_pure_glyphs_by_default():
    # D-03 keeps identifiers Latin in the glyph FACE, because in the editor
    # "the only Latin text is the thing you need to find". The cascade is
    # not the editor — the editor pane shows the real source — so the
    # cascade is a pure glyph wall.
    f = field()
    program = parse(lex('construct name = "Neo"\n'))
    f.consume(Statement(node=program.statements[0], line=1))
    (text, _kind) = f._waiting[0]
    assert not any(ch.isascii() and ch.isalnum() for ch in text)


def test_the_language_glyphs_survive_transliteration():
    # Option 1, not option 2: transliterate ON TOP of the glyph face, so
    # `construct` stays the single glyph the language assigns it rather
    # than becoming nine glyphs of spelled-out Latin.
    f = field()
    program = parse(lex("construct n = 0\n"))
    f.consume(Statement(node=program.statements[0], line=1))
    (text, _kind) = f._waiting[0]
    assert GLYPHS["construct"] in text
    assert GLYPHS["="] in text


def test_a_transliterated_source_line_is_no_taller_than_the_glyph_face():
    # The whole reason option 1 beat option 2. The cascade renders a line
    # vertically, so height is length: option 2 doubled it and a 30-row
    # field stopped fitting whole statements.
    program = parse(lex('construct name = "Neo"\n'))
    plain = field(); plain._glyph_source = False
    plain.consume(Statement(node=program.statements[0], line=1))
    pure = field()
    pure.consume(Statement(node=program.statements[0], line=1))
    assert len(pure._waiting[0][0]) <= len(plain._waiting[0][0]) + 2


def test_latin_source_can_be_turned_back_on():
    f = CascadeField(40, 20, Random(7), glyph_source=False)
    program = parse(lex('construct name = "Neo"\n'))
    f.consume(Statement(node=program.statements[0], line=1))
    (text, _kind) = f._waiting[0]
    assert "name" in text


def test_output_is_unaffected_by_the_source_face():
    on = field()
    off = CascadeField(40, 20, Random(7), glyph_source=False)
    for f in (on, off):
        f.consume(Output(text="wake up, Neo", line=1))
    assert on._waiting[0][0] == off._waiting[0][0]


def test_an_error_event_never_reaches_the_cascade():
    # Diagnostics go to the status strip in plain text. A transliterated
    # error is unreadable, and the spike proved it breaks D-03.
    f = field()
    f.consume(Error(message="boom"))
    assert f.is_empty()
