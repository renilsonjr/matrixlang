from matrixlang.values import is_bool, is_int, is_str, to_display, type_name


def test_bool_is_not_an_integer():
    # In Python, bool subclasses int: isinstance(True, int) is True and
    # True + 1 is 2. Spec §5 forbids coercion, so the interpreter must be
    # able to tell them apart. This is THE rule this module exists for.
    assert is_int(True) is False
    assert is_int(False) is False
    assert is_bool(True) is True
    assert is_int(7) is True
    assert is_bool(7) is False


def test_string_predicate():
    assert is_str("Neo") is True
    assert is_str(7) is False
    assert is_str(True) is False


def test_type_names_are_the_language_s_words():
    assert type_name(7) == "integer"
    assert type_name(True) == "boolean"
    assert type_name("Neo") == "string"


def test_display_prints_strings_without_quotes():
    assert to_display("wake up") == "wake up"


def test_display_prints_booleans_in_the_language_s_spelling():
    # Python renders these "True"/"False"; MatrixLang spells them lowercase.
    assert to_display(True) == "true"
    assert to_display(False) == "false"


def test_display_prints_integers():
    assert to_display(0) == "0"
    assert to_display(-7) == "-7"
