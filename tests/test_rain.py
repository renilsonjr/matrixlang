"""Field invariants under a fixed seed.

The field is a pure function of its seed, which is the only reason an
animation can be asserted on at all: RainField(w, h, Random(7)) advanced
N times produces the same cells on every machine, every run.
"""

from random import Random

from matrixlang.glyphs import RAIN_ALPHABET
from matrixlang.rain import MAX_TICKS, MAX_TRAIL, SPAWN_END_TICK, RainField


def frames(seed: int, ticks: int, width: int = 40, height: int = 12):
    field = RainField(width, height, Random(seed))
    return [field.advance() for _ in range(ticks)]


def test_the_field_is_deterministic_for_a_seed():
    # No shrinking, no reruns: a seed reproduces its animation exactly.
    assert frames(7, 20) == frames(7, 20)


def test_different_seeds_produce_different_fields():
    assert frames(1, 20) != frames(2, 20)


def test_every_painted_cell_is_on_screen():
    # A cell outside the buffer is a cursor move into someone else's
    # terminal. The alternate screen contains the damage but not the bug.
    for frame in frames(3, MAX_TICKS, width=40, height=12):
        for cell in frame.paint:
            assert 0 <= cell.row < 12
            assert 0 <= cell.col < 40


def test_every_erased_cell_is_on_screen():
    for frame in frames(3, MAX_TICKS, width=40, height=12):
        for row, col in frame.erase:
            assert 0 <= row < 12
            assert 0 <= col < 40


def test_every_glyph_comes_from_the_rain_alphabet():
    alphabet = set(RAIN_ALPHABET)
    for frame in frames(4, MAX_TICKS):
        for cell in frame.paint:
            assert cell.glyph in alphabet


def test_levels_stay_in_range():
    for frame in frames(5, MAX_TICKS):
        for cell in frame.paint:
            assert 0.0 < cell.level <= 1.0


def test_brightness_falls_off_strictly_down_each_column():
    # The gradient IS the effect. Asserted strictly, so tied levels fail:
    # an earlier version compared with max(), which breaks ties by
    # insertion order and passed happily when every level was 1.0.
    # Note what is NOT asserted: that the top cell is 1.0. Once a column's
    # head falls past the bottom edge its visible trail is all dimmer than
    # full, and pinning 1.0 here is what drove a false head onto the
    # screen edge.
    for frame in frames(6, 30):
        by_column: dict[int, list] = {}
        for cell in frame.paint:
            by_column.setdefault(cell.col, []).append(cell)
        for cells in by_column.values():
            ordered = sorted(cells, key=lambda c: c.row, reverse=True)
            levels = [cell.level for cell in ordered]
            assert levels == sorted(levels, reverse=True)
            assert len(set(levels)) == len(levels), "levels must be strictly ordered"


def test_a_visible_head_is_exactly_full_brightness():
    # The other half: 1.0 must still occur, and must mean the head is on
    # screen. Together with the test above this pins both directions.
    seen_full = False
    for frame in frames(6, 30):
        for cell in frame.paint:
            assert cell.level <= 1.0
            if cell.level == 1.0:
                seen_full = True
    assert seen_full, "no column ever showed its head on screen"


def test_columns_are_born_staggered_not_all_at_once():
    # Density waves (design S5-4). If every column existed at tick 1 the
    # field would appear as a single slab.
    field = RainField(40, 12, Random(8))
    field.advance()
    early = field.active
    for _ in range(11):
        field.advance()
    assert early < field.active


def test_no_two_cells_ever_collide_in_a_frame():
    # Two columns sharing an x would erase each other's cells, and the
    # erase list carries no identity, so the corruption would be silent.
    # Asserted on the observable output rather than on the column list:
    # a duplicate (row, col) in one frame IS the bug.
    for frame in frames(9, MAX_TICKS):
        positions = [(cell.row, cell.col) for cell in frame.paint]
        assert len(positions) == len(set(positions))


def test_the_field_stops_spawning_and_then_drains():
    # The drain phase IS the dissolve: after spawning ends the screen
    # empties on its own before the player restores the terminal.
    field = RainField(40, 12, Random(10))
    for _ in range(SPAWN_END_TICK):
        field.advance()
    assert field.active > 0
    while not field.is_done():
        field.advance()
    assert field.active == 0


def test_the_field_always_terminates():
    # is_done must go true within MAX_TICKS whatever the seed, or the
    # curtain hangs the terminal it is drawing on.
    for seed in range(20):
        field = RainField(40, 12, Random(seed))
        ticks = 0
        while not field.is_done():
            field.advance()
            ticks += 1
            assert ticks <= MAX_TICKS, f"seed {seed} never finished"


def test_a_frame_is_bounded_by_its_columns_not_by_the_screen():
    # Sparse by construction: work is O(active columns x trail), never
    # O(screen area). A frame bigger than that means something started
    # repainting the whole field.
    field = RainField(80, 24, Random(11))
    for _ in range(MAX_TICKS):
        before = field.active
        frame = field.advance()
        assert len(frame.paint) <= max(before, field.active) * MAX_TRAIL


def test_the_curtain_clears_a_tall_terminal_too():
    # The drain must close on any supported height, not just the 12-row
    # field the other tests use. Column speed scales with height for
    # exactly this reason; a fixed speed would strand a 50-row screen
    # full of rain when MAX_TICKS expired.
    for height in (8, 12, 24, 50):
        field = RainField(80, height, Random(12))
        while not field.is_done():
            field.advance()
        assert field.active == 0, f"height {height} still had columns"
