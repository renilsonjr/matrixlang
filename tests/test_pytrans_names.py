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
    assert proven('d, e = {"a": 1}, 2\n') == []


def test_a_value_from_a_call_is_not_proven():
    assert proven("d = f()\n") == []


def test_several_dictionaries_are_each_proven():
    assert proven('d = {"a": 1}\ne = {"b": 2}\nxs = [1]\n') == ["d", "e"]
