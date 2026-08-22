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


def test_an_unsupported_statement_reports_itself_not_what_it_contains():
    # `class` is unsupported whatever is inside it. Naming the comprehension
    # would send the reader to rewrite working code and change nothing.
    refusal = translate("class A:\n    xs = [f(x) for x in ys]\n").items[0]
    assert "class" in refusal.reason
    assert refusal.line == 1


def test_a_try_statement_also_reports_itself_not_what_it_contains():
    refusal = translate("try:\n    xs = [f(x) for x in ys]\nexcept Exception:\n    pass\n").items[0]
    assert "try" in refusal.reason
    assert refusal.line == 1


def test_a_lone_surrogate_is_a_refusal_not_an_exception():
    # Exactly what a JS string with an unpaired surrogate becomes crossing
    # into Python under Pyodide -- a plain browser <textarea> can hold one.
    # ast.parse() fails encoding it as UnicodeEncodeError, not SyntaxError.
    result = translate("print('\udcff')")
    assert isinstance(result, Refusals)
    assert result.items[0].line == 1


def test_a_deeply_nested_expression_is_a_refusal_not_a_stack_overflow():
    # 500 levels of `1 + 1 + ...` is well within what a reader could paste,
    # and the walker's recursive descent has no depth guard of its own.
    source = "x = " + "1 + " * 500 + "1\n"
    result = translate(source)
    assert isinstance(result, Refusals)
    assert result.items[0].line == 1


def test_a_deeply_nested_expression_alongside_valid_statements_still_refuses_cleanly():
    # translate() only reaches the render step -- the one the nesting
    # actually defeats -- once every statement has walked clean, so when the
    # nesting is the only problem this is the only refusal, however many
    # ordinary statements sit around it and however many of them come after
    # the deep one.
    source = "z = 1\n" + "y = " + "1 + " * 500 + "1\n" + "w = 2\n"
    result = translate(source)
    assert isinstance(result, Refusals)
    assert len(result.items) == 1
    assert "nested too deeply" in result.items[0].reason


def test_an_unsupported_statement_before_a_deep_one_is_still_collected():
    # If a statement refuses on its own terms, translate() never reaches the
    # render step at all -- the deep statement after it walks clean and
    # simply never gets rendered, so this refuses for the ordinary reason,
    # not the nesting.
    source = "import os\n" + "y = " + "1 + " * 500 + "1\n"
    result = translate(source)
    assert isinstance(result, Refusals)
    assert len(result.items) == 1
    assert "import" in result.items[0].reason
    assert result.items[0].line == 1
