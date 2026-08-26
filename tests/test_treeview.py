import dataclasses
import types
import typing
from decimal import Decimal

import pytest

from matrixlang import nodes as nodes_module
from matrixlang.lexer import lex
from matrixlang.nodes import Expr, NumberLiteral, Program, Stmt, Trace
from matrixlang.parser import parse
from matrixlang.tokens import TokenType
from matrixlang.treeview import format_tree


def test_if_else_and_comments_render():
    source = (
        "# intro\n"
        "redpill true\n"
        "  trace 1  # then side\n"
        "bluepill\n"
        "  trace 2\n"
        "flatline\n"
    )
    assert format_tree(parse(lex(source))) == (
        "Program\n"
        "  # intro\n"
        "  If\n"
        "    condition:\n"
        "      BoolLiteral true\n"
        "    then:\n"
        "      Trace  # then side\n"
        "        NumberLiteral 1\n"
        "    else:\n"
        "      Trace\n"
        "        NumberLiteral 2\n"
    )


def test_while_unary_and_dangling_comments_render():
    # Covers the branches the If/Trace fixture never reaches: Declare, While,
    # Unary, Name, body_trailing, and Program.trailing_comments.
    source = (
        "construct total = -1\n"
        "dejavu total <= 10\n"
        "  total = total - 1\n"
        "  # loop tail\n"
        "flatline\n"
        "# program tail\n"
    )
    assert format_tree(parse(lex(source))) == (
        "Program\n"
        "  Declare 'total'\n"
        "    Unary -\n"
        "      NumberLiteral 1\n"
        "  While\n"
        "    condition:\n"
        "      Binary <=\n"
        "        Name 'total'\n"
        "        NumberLiteral 10\n"
        "    body:\n"
        "      Assign 'total'\n"
        "        Binary -\n"
        "          Name 'total'\n"
        "          NumberLiteral 1\n"
        "      # loop tail\n"
        "  # program tail\n"
    )


def test_block_body_dangling_comments_render_on_both_branches():
    source = (
        "redpill true\n"
        "  trace \"Neo\"\n"
        "  # then tail\n"
        "bluepill\n"
        "  trace false\n"
        "  # else tail\n"
        "flatline\n"
    )
    assert format_tree(parse(lex(source))) == (
        "Program\n"
        "  If\n"
        "    condition:\n"
        "      BoolLiteral true\n"
        "    then:\n"
        "      Trace\n"
        "        StringLiteral 'Neo'\n"
        "      # then tail\n"
        "    else:\n"
        "      Trace\n"
        "        BoolLiteral false\n"
        "      # else tail\n"
    )


@pytest.mark.parametrize(
    ("expression", "symbol"),
    [
        ("1 + 2", "+"),
        ("1 - 2", "-"),
        ("1 * 2", "*"),
        ("1 / 2", "/"),
        ("1 == 2", "=="),
        ("1 != 2", "!="),
        ("1 < 2", "<"),
        ("1 > 2", ">"),
        ("1 <= 2", "<="),
        ("1 >= 2", ">="),
    ],
)
def test_every_operator_in_the_table_renders(expression, symbol):
    # _OPS is a lookup: a missing entry is a KeyError on valid input, and a
    # wrong entry renders a lie. Ten cases, one per table row.
    text = format_tree(parse(lex(f"trace {expression}\n")))
    assert f"Binary {symbol}" in text


def test_an_empty_bluepill_block_still_prints_an_else_header():
    # else_body=[] (a bluepill with no statements) and else_body=None (no
    # bluepill at all) are DIFFERENT trees, and treeview's `is not None`
    # check is what keeps them distinguishable. Under a truthiness check
    # the empty else would vanish. Stage 4's renderer relies on the same
    # distinction, so this pins the AST contract behaviourally.
    from matrixlang.lexer import lex
    from matrixlang.parser import parse

    with_empty_else = format_tree(parse(lex("redpill true\nbluepill\nflatline\n")))
    assert "else:" in with_empty_else

    without_else = format_tree(parse(lex("redpill true\nflatline\n")))
    assert "else:" not in without_else


def test_a_list_literal_has_a_treeview_case():
    # treeview.py had no case for the Stage 6 nodes and `matrixlang parse`
    # crashed on an agent while 878 tests passed. One test per new node.
    out = format_tree(parse(lex("construct xs = [1, 2]\n")))
    assert "ListLiteral (2)" in out
    assert "NumberLiteral 1" in out


def test_an_index_has_a_treeview_case():
    out = format_tree(parse(lex("construct a = xs[0]\n")))
    assert "Index" in out
    assert "Name 'xs'" in out


def test_index_assignment_has_a_treeview_case():
    out = format_tree(parse(lex("xs[0] = 9\n")))
    assert "IndexAssign" in out


# --- Exhaustiveness guard ------------------------------------------------
#
# Twice now a new node has shipped with treeview.py untouched, and twice
# `matrixlang parse` crashed on it while the whole suite stayed green --
# because treeview is the only consumer that reaches its nodes through an
# isinstance chain ending in `raise AssertionError`. The named tests above
# are one-per-node and depend on somebody remembering. What follows does
# not: it walks every concrete node class the package defines, builds a
# minimal instance of each, and renders it. Add a node without a treeview
# case and this fails on the next run.
#
# There are deliberately NO silent skips. A node that cannot be built from
# the table below raises with the field that stumped it, because a guard
# that quietly passes over the node nobody handled is the very bug it is
# here to prevent.

_ABSTRACT = {nodes_module.Node, Expr, Stmt}


def _concrete_node_classes(base: type) -> set[type]:
    """Every concrete descendant of `base`, however deeply nested."""
    found: set[type] = set()
    for subclass in base.__subclasses__():
        if subclass not in _ABSTRACT:
            found.add(subclass)
        found |= _concrete_node_classes(subclass)
    return found


def _minimal(annotation):
    """The smallest value satisfying one field's declared type."""
    origin = typing.get_origin(annotation)
    if origin in (types.UnionType, typing.Union):
        # `Expr | None`, `list[Stmt] | None`: fill the real arm, never
        # None -- the None case is the branch treeview already skips, so
        # filling it would test nothing.
        arms = [a for a in typing.get_args(annotation) if a is not type(None)]
        return _minimal(arms[0])
    if origin is list:
        (item,) = typing.get_args(annotation)
        return [_minimal(item)]
    if origin is tuple:
        # DictLiteral.entries is list[tuple[Expr, Expr]] -- a fixed-shape
        # pair, not a homogeneous sequence, so it gets its own branch
        # rather than reusing the list one.
        return tuple(_minimal(arg) for arg in typing.get_args(annotation))
    if annotation is bool:
        return True
    if annotation is int:
        return 1
    if annotation is Decimal:
        # NumberLiteral.value -- must be a Decimal, not a bare int; see
        # nodes.py. A plain int would slip past this generic helper the
        # same way it slipped past render.py before that was caught.
        return Decimal(1)
    if annotation is str:
        return "x"
    if annotation is TokenType:
        # Any row of treeview._OPS will do; the parametrized operator test
        # above is what covers the rows individually.
        return TokenType.MINUS
    if isinstance(annotation, type) and issubclass(annotation, Expr):
        return NumberLiteral(Decimal(1))
    if isinstance(annotation, type) and issubclass(annotation, Stmt):
        return Trace(NumberLiteral(Decimal(1)))
    raise AssertionError(
        f"no minimal value for field type {annotation!r} -- teach _minimal "
        f"about it rather than skipping the node that uses it"
    )


def _build(node_class: type):
    hints = typing.get_type_hints(node_class)
    args, kwargs = [], {}
    for field in dataclasses.fields(node_class):
        if not field.init:
            continue
        value = _minimal(hints[field.name])
        if field.kw_only:
            kwargs[field.name] = value
        else:
            args.append(value)
    return node_class(*args, **kwargs)


_NODE_CLASSES = sorted(
    _concrete_node_classes(Expr) | _concrete_node_classes(Stmt),
    key=lambda cls: cls.__name__,
)


def test_the_walk_finds_every_node_class_the_module_declares():
    # The parametrized guard below is worthless if the walk comes back
    # empty or misses a class, and an empty parametrize list passes
    # silently. This pins the walk itself against nodes.py's namespace.
    declared = {
        obj
        for obj in vars(nodes_module).values()
        if isinstance(obj, type)
        and issubclass(obj, (Expr, Stmt))
        and obj not in _ABSTRACT
    }
    assert set(_NODE_CLASSES) == declared
    assert len(declared) >= 19


@pytest.mark.parametrize("node_class", _NODE_CLASSES, ids=lambda c: c.__name__)
def test_treeview_renders_every_node_class(node_class):
    node = _build(node_class)
    statement = node if isinstance(node, Stmt) else Trace(node)
    out = format_tree(Program([statement]))
    # Every treeview branch prints its node's class name, so this catches
    # a branch that renders nothing as well as one that raises.
    assert node_class.__name__ in out


def test_the_treeview_and_render_operator_tables_cover_the_same_operators():
    # `decode` reached render._OPS and not treeview._OPS, which is exactly
    # how `parse` came to KeyError on a program `render` handled fine. The
    # two tables answer the same question -- which TokenTypes are printed
    # as operators -- so they must agree on the keys.
    from matrixlang import render, treeview

    assert set(treeview._OPS) == set(render._OPS)
