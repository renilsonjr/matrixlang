"""Expression translation, and `print` as the smallest statement that can
hold one end to end."""

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


def test_numbers_strings_and_booleans():
    assert ml("print(1)\n") == "trace 1\n"
    assert ml('print("hi")\n') == 'trace "hi"\n'
    assert ml("print(True)\nprint(False)\n") == "trace true\ntrace false\n"


def test_names():
    assert ml("print(x)\n") == "trace x\n"


def test_arithmetic_and_comparison():
    assert ml("print(1 + 2 * 3)\n") == "trace 1 + 2 * 3\n"
    assert ml("print((1 + 2) * 3)\n") == "trace (1 + 2) * 3\n"
    assert ml("print(a <= b)\n") == "trace a <= b\n"


def test_boolean_operators():
    assert ml("print(a and b)\n") == "trace a splice b\n"
    assert ml("print(a or b)\n") == "trace a fork b\n"
    assert ml("print(not a)\n") == "trace unplug a\n"


def test_unary_minus():
    assert ml("print(-x)\n") == "trace -x\n"


def test_list_and_dict_literals():
    assert ml("print([1, 2])\n") == "trace [1, 2]\n"
    assert ml('print({"a": 1})\n') == 'trace {"a": 1}\n'


def test_indexing():
    assert ml('print(xs[0])\n') == "trace xs[0]\n"
    assert ml('print(d["a"])\n') == 'trace d["a"]\n'


def test_len_str_and_int():
    assert ml("print(len(xs))\n") == "trace length xs\n"
    assert ml("print(str(n))\n") == "trace encode n\n"
    assert ml("print(int(s))\n") == "trace decode s\n"


def test_a_call_to_a_reader_defined_function():
    assert ml("print(f(1, 2))\n") == "trace f(1, 2)\n"


def test_in_over_a_dictionary_is_oracle():
    assert ml('print("a" in d)\n') == 'trace d oracle "a"\n'


def test_precedence_is_rebuilt_not_copied():
    # The renderer decides parentheses, so a tree that needs them gets them
    # and one that does not is left clean. This is the whole reason the
    # translator builds nodes instead of emitting text.
    assert ml("print(a * (b + c))\n") == "trace a * (b + c)\n"
    assert ml("print(a * b + c)\n") == "trace a * b + c\n"


def test_a_float_is_refused():
    refusal = refused("print(1.5)\n")[0]
    assert "float" in refusal.reason


def test_none_is_refused():
    assert "None" in refused("print(None)\n")[0].reason


def test_a_tuple_is_refused():
    assert refused("print((1, 2))\n")[0].idiom is not None


def test_a_chained_comparison_is_refused():
    assert "chain" in refused("print(a < b < c)\n")[0].reason


def test_slicing_is_refused():
    assert refused("print(xs[1:3])\n")[0].idiom is not None


def test_is_is_refused():
    assert "is" in refused("print(a is b)\n")[0].reason


def test_print_with_several_arguments_is_refused():
    refusal = refused('print("a", "b")\n')[0]
    assert refusal.idiom is not None


def test_a_bare_expression_statement_is_refused():
    # MatrixLang's grammar accepts an expression statement only when it is a
    # call: `1 + 1` alone computes and discards, which the parser treats as a
    # mistake. Python allows it, so it is refused here.
    assert refused("1 + 1\n")[0].idiom is not None


def test_true_division_is_refused():
    # MatrixLang's `/` truncates toward zero, so `print(7 / 2)` used to
    # translate clean and print `3` where Python prints `3.5` -- a program
    # that runs and quietly means something else, which is the one outcome
    # the translator exists to prevent. Even exact division diverges:
    # Python's `4 / 2` is `2.0`, MatrixLang's is `2`.
    refusal = refused("print(7 / 2)\n")[0]
    assert "`/`" in refusal.reason
    assert refusal.line == 1
    assert "truncates" in refusal.idiom


def test_floor_division_is_refused():
    # Agrees with MatrixLang's `/` for non-negative operands and disagrees
    # for negative ones, and which of the two applies depends on values
    # that do not exist at translation time.
    refusal = refused("print(a // b)\n")[0]
    assert "`//`" in refusal.reason
    assert "negatives" in refusal.idiom


def test_dividing_in_place_is_refused_naming_the_operator():
    refusal = refused("x = 8\nx /= 2\n")[0]
    assert "`/`" in refusal.reason
    assert refusal.line == 2


def test_an_operator_refusal_carries_the_expression_s_position():
    # Python's operator nodes hold no position of their own, so without
    # borrowing one from the expression around them every `%` in a file
    # reported at line 1, column 0.
    refusal = refused("x = 1\ny = 2\nprint(x % y)\n")[0]
    assert refusal.line == 3
    assert refusal.column == 6


def test_in_translates_unconditionally_over_every_container():
    # `k in d`, `2 in xs` and `"a" in s` are the same syntax, and only the
    # runtime value says which is which -- deciding would be the type
    # inference the governing rule forbids. So `in` always becomes
    # `oracle`, unconditionally.
    #
    # This test used to end by asserting that the list form then FAILED at
    # runtime, with "takes a dictionary". That was honest about a real
    # gap: the translation looked fine and died on Run, naming an operator
    # the reader never typed. Issue #134 closed it by widening `oracle`
    # rather than by teaching the translator to guess, so the second half
    # now asserts the program runs and prints the right answer.
    import io

    from matrixlang.interpreter import Interpreter
    from matrixlang.lexer import lex
    from matrixlang.parser import parse

    assert ml("xs = [1, 2]\nprint(2 in xs)\n") == (
        "construct xs = [1, 2]\ntrace xs oracle 2\n"
    )
    assert ml('print("a" in d)\n') == 'trace d oracle "a"\n'
    assert ml('s = "abc"\nprint("b" in s)\n') == (
        'construct s = "abc"\ntrace s oracle "b"\n'
    )

    out = io.StringIO()
    Interpreter(out=out).run(
        parse(lex("construct xs = [1, 2]\ntrace xs oracle 2\n"))
    )
    assert out.getvalue() == "true\n"


def test_not_in_is_still_refused():
    # Unlike `in`, this one genuinely has no MatrixLang form.
    refusal = refused("print(a not in b)\n")[0]
    assert "`not in`" in refusal.reason
    assert "unplug" in refusal.idiom


def test_lower_becomes_fold():
    assert "fold s" in ml("s = 'A'\nprint(s.lower())\n")


def test_strip_becomes_trim():
    assert "trim s" in ml("s = ' a '\nprint(s.strip())\n")


def test_split_becomes_cleave():
    assert 's cleave ","' in ml("s = 'a,b'\nprint(s.split(','))\n")


def test_a_string_method_on_an_expression_translates():
    # The receiver is an arbitrary expression, not only a name.
    assert "fold xs[0]" in ml("xs = ['A']\nprint(xs[0].lower())\n")


def test_a_case_insensitive_comparison_translates_whole():
    source = "a = 'A'\nb = 'a'\nprint(a.lower() == b.lower())\n"
    assert "fold a == fold b" in ml(source)


def test_a_chained_strip_and_split_translates():
    assert 'trim s cleave ","' in ml("s = ' a,b '\nprint(s.strip().split(','))\n")
