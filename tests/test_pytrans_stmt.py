"""Binding: assignment, `+=`, element assignment, and `.append()` -- and
the `construct` versus plain-assignment distinction Python doesn't make."""

from matrixlang.pytrans import translate, Translated, Refusals


def ml(python_source):
    """The MatrixLang a Python snippet translates to. Fails loudly on refusal."""
    result = translate(python_source)
    assert isinstance(result, Translated), getattr(result, "items", result)
    return result.source


def refused(python_source):
    """The refusals a Python snippet produces. Fails loudly if it translated."""
    result = translate(python_source)
    assert isinstance(result, Refusals), result
    return result.items


def test_a_first_binding_uses_construct():
    assert ml("x = 1\n") == "construct x = 1\n"


def test_a_later_binding_is_a_plain_assignment():
    assert ml("x = 1\nx = 2\n") == "construct x = 1\nx = 2\n"


def test_augmented_assignment_expands():
    assert ml("x = 1\nx += 2\n") == "construct x = 1\nx = x + 2\n"


def test_augmented_assignment_before_any_binding_is_refused():
    assert "before changing it" in refused("x += 1\n")[0].idiom


def test_index_assignment():
    assert ml("xs = [1]\nxs[0] = 9\n") == "construct xs = [1]\nxs[0] = 9\n"


def test_dictionary_key_assignment():
    assert ml('d = {}\nd["a"] = 1\n') == 'construct d = {}\nd["a"] = 1\n'


def test_append_becomes_concatenation():
    assert ml("xs = []\nxs.append(1)\n") == "construct xs = []\nxs = xs + [1]\n"


def test_append_inside_an_expression_is_refused():
    assert refused("xs = []\ny = xs.append(1)\n")[0].reason != ""


def test_an_unknown_method_call_is_refused():
    refusal = refused("xs = []\nxs.sort()\n")[0]
    assert "sort" in refusal.reason or "method" in refusal.reason


def test_multiple_assignment_is_refused():
    assert refused("a = b = 0\n")[0].idiom is not None


def test_tuple_unpacking_is_refused():
    assert refused("a, b = 1, 2\n")[0].idiom is not None
