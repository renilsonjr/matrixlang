"""String methods — rendering fold, trim and cleave in both faces."""

from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.render import render_ascii, render_glyph


def ascii_face(source):
    return render_ascii(parse(lex(source)))


def glyph_face(source):
    return render_glyph(parse(lex(source)))


def test_fold_renders_with_a_separating_space():
    # `fold s` must never come back as `folds` -- that re-lexes as one
    # identifier, a silent change of meaning. Same rule as `length`,
    # `decode`, `encode` and `keymaker`.
    assert ascii_face("trace fold s\n") == "trace fold s\n"


def test_trim_renders_with_a_separating_space():
    assert ascii_face("trace trim s\n") == "trace trim s\n"


def test_cleave_renders_infix():
    assert ascii_face('trace s cleave ","\n') == 'trace s cleave ","\n'


def test_the_three_render_in_the_glyph_face():
    assert glyph_face("trace fold s\n") == "ﾄ ﾊ s\n"
    assert glyph_face("trace trim s\n") == "ﾄ ﾘ s\n"
    assert glyph_face('trace s cleave "x"\n') == 'ﾄ s ﾛ "x"\n'


def test_a_unary_word_over_a_cleave_keeps_its_parens():
    # cleave binds looser than the unary rung, so these parens are load
    # bearing: `length s cleave ","` would be `(length s) cleave ","`.
    source = 'trace length (s cleave ",")\n'
    assert ascii_face(source) == source


def test_a_cleave_under_a_comparison_needs_no_parens():
    source = 'trace s cleave "," == xs\n'
    assert ascii_face(source) == source


def test_a_plus_under_a_cleave_needs_no_parens():
    source = 'trace a + b cleave ","\n'
    assert ascii_face(source) == source


def test_a_cleave_on_the_right_of_a_cleave_gets_parens():
    # Left-associative: `a cleave (b cleave c)` is NOT what
    # `a cleave b cleave c` parses as, so the render must put them back.
    source = "trace a cleave (b cleave c)\n"
    assert ascii_face(source) == source


def test_a_comparison_under_a_cleave_gets_parens():
    source = 'trace (a == b) cleave ","\n'
    assert ascii_face(source) == source


def test_a_lt_under_a_cleave_gets_parens():
    # `==`/`!=` sit at level 4, but `<`/`>`/`<=`/`>=` sit at level 5 -- one
    # rung above. If CLEAVE were misnumbered at 5 (merged with
    # comparison) or lower, these parens would be dropped and the source
    # would come back as `trace a < b cleave ","`, a different tree. This
    # is the case the `==` comparison test above cannot catch, because it
    # only discriminates CLEAVE <= 4.
    source = 'trace (a < b) cleave ","\n'
    assert ascii_face(source) == source


def test_a_cleave_under_a_plus_gets_parens():
    # If CLEAVE were misnumbered at 7 (merged with term, the level PLUS
    # and MINUS sit at), these parens would be dropped and the source
    # would come back as `trace a cleave b + c`, parsing as
    # `a cleave (b + c)` instead of `(a cleave b) + c`.
    source = "trace (a cleave b) + c\n"
    assert ascii_face(source) == source


def test_fold_over_a_plus_gets_parens():
    source = "trace fold (a + b)\n"
    assert ascii_face(source) == source


def test_fold_over_a_star_gets_parens():
    # If _UNARY_LEVEL were left at 8 (its pre-cleave value) instead of
    # moving to 9, a `*`/`/` operand (level 8) would appear to bind as
    # tight as the unary rung and lose its parens, misrendering as
    # `trace fold a * b` -- a different tree than `fold (a * b)`.
    source = "trace fold (a * b)\n"
    assert ascii_face(source) == source


def test_the_tree_view_names_all_three():
    from matrixlang.treeview import format_tree

    tree = format_tree(parse(lex('trace fold trim s cleave ","\n')))
    assert "fold" in tree and "trim" in tree and "cleave" in tree
