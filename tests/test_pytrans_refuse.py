"""The translator's refusal machinery, and its promise never to raise."""

from matrixlang.pytrans import Refusals, Translated, translate


def test_invalid_python_is_a_refusal_not_an_exception():
    result = translate("def (:\n")
    assert isinstance(result, Refusals)
    assert result.items[0].line == 1


def test_an_empty_program_translates_to_an_empty_program():
    result = translate("")
    assert isinstance(result, Translated)
    assert result.source == ""


def test_an_unsupported_statement_is_refused_with_its_line():
    result = translate("import os\n")
    assert isinstance(result, Refusals)
    assert result.items[0].line == 1
    assert "import" in result.items[0].reason


def test_every_refusal_is_collected_not_just_the_first():
    result = translate("import os\nimport sys\nclass A: pass\n")
    assert isinstance(result, Refusals)
    assert [r.line for r in result.items] == [1, 2, 3]


def test_refusals_are_in_line_order():
    result = translate("class A: pass\nimport os\n")
    assert [r.line for r in translate("class A: pass\nimport os\n").items] == [1, 2]


def test_a_refusal_names_an_idiom_when_one_exists():
    refusal = translate("xs = [f(x) for x in ys]\n").items[0]
    assert refusal.idiom is not None
    assert "dejavu" in refusal.idiom
