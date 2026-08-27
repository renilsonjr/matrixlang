import ast

from matrixlang.pytrans.names import dict_names


def proven(source):
    """The names this program proves hold dictionaries."""
    return sorted(dict_names(ast.parse(source)))


def test_a_name_bound_to_a_dict_literal_is_proven():
    assert proven('d = {"a": 1}\n') == ["d"]


def test_an_empty_dict_literal_still_proves_it():
    assert proven("d = {}\n") == ["d"]


def test_subscript_assignment_is_not_a_binding():
    # `d = {}` then `d["a"] = 1` is how a reader builds a dictionary. The
    # subscript names `d` in Load context, so it is not a rebinding and
    # must not disqualify it.
    assert proven('d = {}\nd["a"] = 1\n') == ["d"]


def test_a_name_also_bound_to_a_list_is_not_proven():
    assert proven('d = {"a": 1}\nd = [1]\n') == []


def test_a_parameter_of_that_name_disqualifies_it():
    # No scope sensitivity, deliberately: a parameter named `d` anywhere
    # means some `d` can hold anything, and being wrong here emits
    # `keymaker` on a list.
    assert proven('d = {"a": 1}\ndef f(d):\n    return d\n') == []


def test_a_loop_target_of_that_name_disqualifies_it():
    assert proven('d = {"a": 1}\nfor d in xs:\n    print(d)\n') == []


def test_a_tuple_target_never_proves_a_name():
    # The right-hand side must be a dict LITERAL, or this never reaches
    # the `isinstance(target, ast.Name)` guard it exists to pin -- it
    # would fail on the value check instead and the guard could be
    # deleted with every test still green. Unpacking a dict binds its
    # KEYS, so here `d` is the string "a", not a dictionary.
    assert proven('d, e = {"a": 1, "b": 2}\n') == []


def test_a_type_parameter_never_proves_a_name():
    # PEP 695. `def f[d](x)` binds `d` as a TypeVar, and the name lives
    # in a plain string field exactly as MatchAs's does. Skipped below
    # 3.12, where the syntax does not parse.
    import sys

    if sys.version_info < (3, 12):
        return
    assert proven('d = {"a": 1}\ndef f[d](x):\n    return x\n') == []
    assert proven('d = {"a": 1}\ntype d = int\n') == []


def test_the_backstop_denies_what_a_blind_walk_would_prove():
    # The backstop exists for binding forms the walk does not know about
    # -- which, the walk being complete for Python as it stands, cannot
    # be reached through dict_names at all. So it is called directly with
    # a proof the walk would never actually make.
    from matrixlang.pytrans.names import _still_bound_without_their_proofs

    tree = ast.parse('d = {"a": 1}\nmatch xs:\n    case d:\n        pass\n')
    assert _still_bound_without_their_proofs(tree, {"d"}) == {"d"}


def test_a_dict_alone_in_a_block_is_still_proven():
    # Stripping the proof must not empty the block: an empty `class C:`
    # or `def f():` does not unparse, symtable refuses the program, and
    # the failure path denies everything -- including names elsewhere.
    assert proven('class C:\n    d = {"a": 1}\n') == ["d"]
    assert proven('def f():\n    d = {"a": 1}\n') == ["d"]
    assert proven('if c:\n    d = {"a": 1}\n') == ["d"]


def test_one_collapsed_block_does_not_deny_unrelated_names():
    assert proven('class C:\n    d = {"a": 1}\ne = {"b": 2}\n') == ["d", "e"]


def test_a_star_import_proves_nothing():
    # `from m import *` brings in names nobody can enumerate. symtable
    # does not know them either, so it would report every proven name as
    # unbound and wave them all through.
    assert proven('d = {"a": 1}\nfrom m import *\n') == []


def test_an_attribute_assignment_is_not_a_binding():
    # `o.d = 1` names `d` but binds nothing. Guards the Assign-target
    # walk restricting to ast.Name, and would also fail if "attr" were
    # ever added to _NAME_FIELDS. Passes with the backstop disabled --
    # it is not a backstop test.
    assert proven('d = {"a": 1}\no.d = 1\n') == ["d"]


def test_a_dotted_import_denies_the_name_it_actually_binds():
    # `import d.b.c` binds only `d`. The alias node carries the whole
    # dotted path as its name, so denying the raw field value would deny
    # "d.b.c" -- which nobody wrote -- and leave `d` proven.
    assert proven('d = {"a": 1}\nimport d.b.c\n') == []
    assert proven('d = {"a": 1}\nimport x.y as d\n') == []


def test_a_call_keyword_argument_is_not_a_binding():
    # `f(d=1)` names `d` in an ast.keyword, which binds nothing. Denying
    # on the field alone would lose this fix for no safety.
    assert proven('d = {"a": 1}\nf(d=1)\n') == ["d"]


def test_a_match_capture_never_proves_a_name():
    # `case d:` binds `d` through MatchAs, which carries the name as a
    # string and has no ast.Name node to find.
    assert proven(
        'd = {"a": 1}\nmatch xs:\n    case d:\n        print(d)\n'
    ) == []


def test_a_value_from_a_call_is_not_proven():
    assert proven("d = f()\n") == []


def test_several_dictionaries_are_each_proven():
    assert proven('d = {"a": 1}\ne = {"b": 2}\nxs = [1]\n') == ["d", "e"]
