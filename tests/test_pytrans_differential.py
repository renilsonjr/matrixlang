"""Translate, run both, compare.

The only tests here that can catch an output which parses, runs, and
means something other than the Python did.

Three rows of the subset cannot be judged by comparing stdout, and all
three are structural rather than gaps waiting to be filled: `input()`'s
prompt newline (see `both` below), anything whose result is a boolean,
which Python prints as `True` and MatrixLang as `true`, and a container
that holds a string, which Python quotes with `'` and MatrixLang with
`"` (see `matrixlang_prints` for all three). Those rows are covered
against a literal expectation instead, so the absence of an `agree()`
case for them is deliberate and visible.
"""

import io
from contextlib import redirect_stdout

from matrixlang.input import ListSource
from matrixlang.interpreter import Interpreter
from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.pytrans import Translated, translate


def both(python_source, stdin_lines=()):
    """(what Python printed, what the MatrixLang printed)."""
    python_out = io.StringIO()
    supply = iter(stdin_lines)
    # Python's input(prompt) prints the prompt with NO trailing newline;
    # MatrixLang has no such primitive. The translation of `input(...)` is
    # `trace <prompt>` followed by `jackin`, and `trace` -- like every
    # other output MatrixLang can produce -- always ends in a newline
    # (events.py's TextSink prints every Output with `print()`, and Trace
    # is the only statement that produces one). There is no MatrixLang
    # construct that prints without a newline, so there is no way to
    # match Python's prompt behaviour exactly. This shim prints the
    # prompt WITH a trailing newline (`print(p)`, not `print(p, end="")`)
    # so both sides are compared against the same, achievable target:
    # Python-with-a-newline-after-the-prompt, because MatrixLang cannot
    # do otherwise.
    def fake_input(p=""):
        print(p)
        return next(supply)

    namespace = {"input": fake_input}
    with redirect_stdout(python_out):
        exec(compile(python_source, "<differential>", "exec"), namespace)

    result = translate(python_source)
    assert isinstance(result, Translated), result.items
    ml_out = io.StringIO()
    Interpreter(out=ml_out, source=ListSource(list(stdin_lines))).run(
        parse(lex(result.source))
    )
    return python_out.getvalue(), ml_out.getvalue()


def agree(python_source, stdin_lines=()):
    left, right = both(python_source, stdin_lines)
    assert left == right, f"python={left!r} matrixlang={right!r}"


def test_arithmetic_and_printing_agree():
    agree("x = 2\nprint(x * 3 + 1)\n")


def test_a_while_loop_agrees():
    agree("n = 0\nwhile n < 3:\n    print(n)\n    n += 1\n")


def test_a_for_loop_over_a_list_agrees():
    agree("xs = [1, 2, 3]\nfor x in xs:\n    print(x)\n")


def test_a_for_loop_over_range_agrees():
    agree("for i in range(3):\n    print(i)\n")


def test_an_agent_agrees():
    agree("def double(x):\n    return x * 2\n\nprint(double(21))\n")


def test_if_elif_else_agrees():
    agree(
        "g = 'B'\n"
        "if g == 'A':\n    print('top')\n"
        "elif g == 'B':\n    print('middle')\n"
        "else:\n    print('other')\n"
    )


def test_a_dictionary_agrees():
    agree('d = {"a": 1, "b": 2}\nprint(d["a"])\nprint(len(d))\n')


def test_building_a_list_in_a_loop_agrees():
    agree(
        "out = []\n"
        "for i in range(4):\n"
        "    out = out + [i * 2]\n"
        "print(len(out))\n"
        "for v in out:\n    print(v)\n"
    )


def test_a_prompted_program_agrees():
    # The simplest program that exercises input(), verified first per the
    # brief's instruction, before trusting the rest of this file.
    agree('name = input("Name: ")\nprint("Hi " + name)\n', stdin_lines=["Ada"])


def test_the_students_search_program_agrees():
    # The program that motivated dictionaries, with the one line the
    # translator's own truthiness refusal instructs the reader to change.
    agree(
        'students_data = [\n'
        '    {"id": 1, "grade": "A"},\n'
        '    {"id": 2, "grade": "B"},\n'
        '    {"id": 3, "grade": "A"},\n'
        ']\n'
        'user_search = input("Digite a nota(A, B, C): ")\n'
        '\n'
        'def find_students(students_data, search_student):\n'
        '    found = []\n'
        '    for students in students_data:\n'
        '        if search_student == str(students["id"]) '
        'or search_student == students["grade"]:\n'
        '            found = found + [students]\n'
        '    return found\n'
        '\n'
        'result = find_students(students_data, user_search)\n'
        'if len(result) > 0:\n'
        '    print("Encontrado esses ID que dao match:")\n'
        '    for student in result:\n'
        '        print("-ID: " + str(student["id"]))\n'
        'else:\n'
        '    print("match nao valido")\n',
        stdin_lines=["A"],
    )


def matrixlang_prints(python_source, expected):
    """Run only the translation, against a literal expectation.

    For the handful of rows where `agree()` is structurally impossible.
    Python prints `True`/`False` and MatrixLang prints `true`/`false`
    (render.py and events.py both spell booleans the language's own way),
    so every row whose result IS a boolean -- `and`/`or`/`not`, `k in d`,
    the boolean literals themselves -- can never match Python's stdout no
    matter how correct the translation is. That is inherent to comparing
    two languages' output, the same way the `input()` prompt newline
    documented at the top of this file is, and it is recorded here rather
    than left as an unexplained gap in the table's coverage.
    """
    result = translate(python_source)
    assert isinstance(result, Translated), result.items
    out = io.StringIO()
    Interpreter(out=out).run(parse(lex(result.source)))
    assert out.getvalue() == expected, out.getvalue()


def test_element_assignment_agrees():
    agree("xs = [1, 2, 3]\nxs[1] = 9\nprint(xs)\nprint(xs[1])\n")


def test_dictionary_key_assignment_agrees():
    agree('d = {"a": 1}\nd["b"] = 2\nprint(d["b"])\nprint(len(d))\n')


def test_int_and_str_agree():
    agree('n = int("42")\nprint(n + 1)\nprint("n=" + str(n))\n')


def test_append_agrees():
    agree("xs = []\nxs.append(1)\nxs.append(2)\nprint(xs)\nprint(len(xs))\n")


def test_an_fstring_agrees():
    agree('x = 3\ny = 4\nprint(f"x={x} y={y}")\n')


def test_a_bare_return_agrees():
    agree(
        "def report(x):\n"
        "    if x > 0:\n"
        "        print('positive')\n"
        "        return\n"
        "    print('not positive')\n"
        "report(1)\n"
        "report(-1)\n"
    )


def test_a_name_first_bound_inside_a_loop_agrees():
    # The hoisted `construct` rewrite itself -- the one piece of invented
    # output the reader did not write, and until now the only rewrite with
    # no differential case at all, because both list-building cases bind
    # their accumulator BEFORE the loop.
    agree(
        "for i in range(4):\n"
        "    doubled = i * 2\n"
        "    print(doubled)\n"
        "print(doubled)\n"
    )


def test_a_name_first_bound_in_an_if_branch_agrees():
    agree(
        "x = -1\n"
        "if x > 0:\n"
        "    s = 'up'\n"
        "else:\n"
        "    s = 'down'\n"
        "print(s)\n"
    )


def test_a_nested_loop_over_a_list_of_lists_agrees():
    agree(
        "rows = [[1, 2], [3], []]\n"
        "for row in rows:\n"
        "    for v in row:\n"
        "        print(v)\n"
    )


def test_a_range_bound_is_read_once_and_agrees():
    agree("n = 5\nfor i in range(n):\n    n = n - 1\n    print(i)\n")


def test_boolean_literals_and_operators_translate_to_matrixlang_booleans():
    # See matrixlang_prints: Python spells these True/False, MatrixLang
    # spells them true/false, so agree() cannot be the judge.
    matrixlang_prints("print(True)\nprint(False)\n", "true\nfalse\n")
    matrixlang_prints(
        "a = 1\nb = 2\nprint(a == 1 and b == 2)\n"
        "print(a == 9 or b == 2)\nprint(not a == 1)\n",
        "true\ntrue\nfalse\n",
    )


def test_in_over_a_dictionary_translates_to_oracle():
    matrixlang_prints(
        'd = {"a": 1}\nprint("a" in d)\nprint("z" in d)\n', "true\nfalse\n"
    )


def test_an_fstring_interpolating_a_string_agrees():
    # The case that prompted widening `encode`. The translator emits
    # `encode` for every interpolation; while that took numbers only, this
    # program translated cleanly and then died on Run.
    agree(
        'name = "clean code"\n'
        'book_id = 1\n'
        'print(f"Match found! Name: {name}, ID: {book_id}")\n'
    )


def test_an_fstring_interpolating_a_dictionary_field_agrees():
    agree(
        'book = {"id": 2, "name": "refactoring"}\n'
        'print(f"Name: {book[\'name\']}, ID: {book[\'id\']}")\n'
    )


def test_an_fstring_interpolating_a_list_of_strings_translates_to_oracle():
    # `encode` widened to take any value, so this hole now translates and
    # runs instead of dying at Run -- but it does not agree with Python.
    # `encode` shares `to_display` with `trace`, and a nested string was
    # already quoted MatrixLang's way (`"`) rather than Python's (`'`)
    # before this branch; an f-string hole is just one more way to reach
    # that same pre-existing divergence.
    matrixlang_prints('print(f"{[\'a\']}")\n', '["a"]\n')


def test_the_products_search_agrees():
    # The program that put string methods first in the register. Prices
    # are strings because MatrixLang has no decimals yet (register item 4,
    # #135); everything else is the reader's own program, `.lower()`
    # included.
    source = (
        "products = [\n"
        '    {"code": "A1", "name": "Mouse", "price": "49"},\n'
        '    {"code": "B2", "name": "Teclado", "price": "120"},\n'
        "]\n"
        "\n"
        'term = input("Search: ")\n'
        "found = 0\n"
        "for product in products:\n"
        '    if term.lower() == product["code"].lower() or '
        'term.lower() == product["name"].lower():\n'
        '        print(product["name"] + " costs " + product["price"])\n'
        "        found = found + 1\n"
        "if found == 0:\n"
        '    print("Nothing found.")\n'
    )
    agree(source, ["mouse"])
    agree(source, ["B2"])
    agree(source, ["nothing at all"])


def test_trim_and_cleave_agree():
    agree('s = "  a,b,c  "\nfor part in s.strip().split(","):\n    print(part)\n')


def test_a_continue_nested_two_ifs_deep_agrees():
    # Catches the walk not descending far enough.
    agree(
        "xs = [1, 2, 3, 4]\n"
        "for x in xs:\n"
        "    if x > 1:\n"
        "        if x < 4:\n"
        "            continue\n"
        "    print(x)\n"
    )


def test_a_continue_in_a_while_nested_in_a_for_agrees():
    # Catches the walk descending too far and double-incrementing the
    # OUTER counter for a `glitch` that belongs to the inner while.
    agree(
        "xs = [1, 2]\n"
        "for x in xs:\n"
        "    n = 0\n"
        "    while n < 3:\n"
        "        n = n + 1\n"
        "        if n == 2:\n"
        "            continue\n"
        "        print(n)\n"
        "    print(x)\n"
    )


def test_a_continue_in_a_nested_for_agrees():
    # Catches the wrong counter being incremented.
    agree(
        "rows = [[1, 2], [3, 4]]\n"
        "for row in rows:\n"
        "    for cell in row:\n"
        "        if cell == 2:\n"
        "            continue\n"
        "        print(cell)\n"
    )


def test_a_break_in_a_for_agrees():
    agree(
        "xs = [1, 2, 3, 4]\n"
        "for x in xs:\n"
        "    if x == 3:\n"
        "        break\n"
        "    print(x)\n"
    )


def test_break_and_continue_together_agree():
    agree(
        "xs = [1, 2, 3, 4, 5]\n"
        "for x in xs:\n"
        "    if x == 2:\n"
        "        continue\n"
        "    if x == 4:\n"
        "        break\n"
        "    print(x)\n"
    )


def test_a_continue_in_an_else_branch_agrees():
    # The `else_body` arm of `_increment_before_glitches` is the one
    # branch of that helper with no guard at all -- all five differential
    # cases the brief gave put `continue` in a `then` branch, so a
    # regression that dropped the `else_body` rewrite entirely (e.g. an
    # `and False` tacked onto its `if`) would pass the whole suite while
    # sending a reader's ordinary `continue`-in-an-`else` into a loop that
    # spins to the step limit.
    agree(
        "xs = [1, 2, 3, 4]\n"
        "for x in xs:\n"
        "    if x == 2:\n"
        "        print(x)\n"
        "    else:\n"
        "        continue\n"
        "    print(x * 10)\n"
    )


def test_in_over_a_list_agrees():
    # Printing the `in` result directly can never agree() -- Python spells
    # it True/False, MatrixLang true/false (see this file's own docstring,
    # and matrixlang_prints below). So, like test_a_membership_search_loop_
    # agrees, the boolean is routed through if/else into a non-boolean
    # sentinel that still depends entirely on oracle's answer.
    agree(
        'names = ["neo", "trinity", "morpheus"]\n'
        'for name in names:\n'
        '    if name in names:\n'
        '        print("yes")\n'
        '    else:\n'
        '        print("no")\n'
        'if "smith" in names:\n'
        '    print("yes")\n'
        'else:\n'
        '    print("no")\n'
    )


def test_in_over_a_string_agrees():
    # Substring, not character -- "rix" is not one of "matrix"'s
    # characters, and both sides must still say the same thing.
    agree(
        's = "matrix"\n'
        'for needle in ["rix", "m", "zion", ""]:\n'
        '    if needle in s:\n'
        '        print("yes")\n'
        '    else:\n'
        '        print("no")\n'
    )


def test_in_over_a_mixed_list_agrees_in_both_orders():
    # The skip decision, and the reason it was chosen. Both orders must
    # give the same answers, and both must match Python.
    agree(
        'a = ["a", 1]\n'
        'b = [1, "a"]\n'
        'if 1 in a:\n    print("yes")\nelse:\n    print("no")\n'
        'if 1 in b:\n    print("yes")\nelse:\n    print("no")\n'
        'if "a" in a:\n    print("yes")\nelse:\n    print("no")\n'
        'if "a" in b:\n    print("yes")\nelse:\n    print("no")\n'
        'if 2 in a:\n    print("yes")\nelse:\n    print("no")\n'
    )


def test_in_over_a_dictionary_still_agrees():
    agree(
        'd = {"a": 1, "b": 2}\n'
        'for key in ["a", "z"]:\n'
        '    if key in d:\n'
        '        print("yes")\n'
        '    else:\n'
        '        print("no")\n'
    )


def test_a_membership_search_loop_agrees():
    # The shape the register was actually about: a search that stops
    # early, now that both `in` and `wake` exist.
    agree(
        'names = ["neo", "trinity"]\n'
        'wanted = "trinity"\n'
        'found = 0\n'
        'for name in names:\n'
        '    if wanted in name:\n'
        '        found = 1\n'
        '        break\n'
        'print(found)\n'
    )


def test_decimal_arithmetic_agrees():
    agree("print(49.90 + 120.00)\nprint(2.5 * 4)\nprint(1.5 - 0.5)\n")


def test_division_agrees():
    agree("print(7 / 2)\nprint(-7 / 2)\nprint(49.90 / 2)\n")


def test_remainder_agrees():
    agree("print(7 % 2)\nprint(-7 % 2)\nprint(7 % -2)\nprint(7.5 % 2)\n")


def test_an_even_odd_loop_agrees():
    agree("for n in range(6):\n    if n % 2 == 0:\n        print(n)\n")


# List comprehensions, run end to end rather than compared as text. Every
# other comprehension test in this repo compares `ast.unparse` output
# (test_pytrans_comprehensions.py) or a MatrixLang source string
# (test_pytrans_expr.py, test_pytrans_refuse.py) -- both catch a rewrite
# that produces the wrong text, neither catches one that produces text
# which parses, runs, and does the wrong thing. Integer-valued programs
# only: a boolean result can never agree() (Python prints True/False,
# MatrixLang prints true/false -- see this file's own docstring), and a
# comprehension result used directly as a condition refuses outright
# (MatrixLang has no truthiness), so neither shape belongs here.


def test_a_plain_comprehension_agrees():
    agree("xs = [1, 2, 3]\nout = [x * 2 for x in xs]\nfor v in out:\n    print(v)\n")


def test_a_filtered_comprehension_agrees():
    agree(
        "xs = [1, 2, 3, 4, 5]\n"
        "out = [x for x in xs if x > 2]\n"
        "for v in out:\n    print(v)\n"
    )


def test_a_comprehension_whose_loop_variable_shadows_an_outer_name_agrees():
    # Python 3 gives the comprehension its own scope, so `x` is untouched
    # outside it -- the same hazard test_the_loop_variable_does_not_leak
    # pins as text, run here end to end instead.
    agree(
        "x = 99\n"
        "xs = [1, 2, 3]\n"
        "out = [x for x in xs]\n"
        "for v in out:\n    print(v)\n"
        "print(x)\n"
    )


def test_a_comprehension_nested_inside_another_agrees():
    agree(
        "rows = [[1, 2], [3, 4]]\n"
        "out = [[y * 2 for y in row] for row in rows]\n"
        "for r in out:\n"
        "    for v in r:\n        print(v)\n"
    )


def test_a_comprehension_inside_a_for_body_agrees():
    agree(
        "for i in range(3):\n"
        "    doubled = [x * i for x in [1, 2]]\n"
        "    for v in doubled:\n        print(v)\n"
    )


def test_a_comprehension_inside_an_if_body_agrees():
    agree(
        "c = 1\n"
        "if c > 0:\n"
        "    out = [x for x in [1, 2, 3]]\n"
        "    for v in out:\n        print(v)\n"
    )


def test_a_comprehension_in_the_iterable_of_another_agrees():
    agree(
        "xs = [1, 2, 3]\n"
        "out = [x for x in [y * 2 for y in xs]]\n"
        "for v in out:\n    print(v)\n"
    )


def test_a_loop_else_that_breaks_agrees():
    agree(
        "xs = [1, 2, 3]\nt = 2\n"
        "for x in xs:\n    if x == t:\n        print(100)\n        break\n"
        "else:\n    print(999)\n"
    )


def test_a_loop_else_that_completes_agrees():
    agree(
        "xs = [1, 2, 3]\nt = 9\n"
        "for x in xs:\n    if x == t:\n        print(100)\n        break\n"
        "else:\n    print(999)\n"
    )


def test_a_loop_else_over_an_empty_list_agrees():
    agree("xs = []\nfor x in xs:\n    break\nelse:\n    print(7)\n")


def test_a_loop_else_with_no_break_agrees():
    agree("xs = [1, 2]\nfor x in xs:\n    print(x)\nelse:\n    print(7)\n")


def test_a_nested_loops_break_does_not_suppress_the_outer_else_agrees():
    agree(
        "A = [1, 2]\nB = [3]\n"
        "for a in A:\n    for b in B:\n        break\n"
        "else:\n    print(5)\n"
    )


def test_a_break_in_an_inner_loops_else_exits_the_outer_loop_agrees():
    agree(
        "A = [1, 2, 3]\nB = []\n"
        "for a in A:\n    for b in B:\n        print(b)\n"
        "    else:\n        print(a)\n        break\n"
        "else:\n    print(999)\n"
    )


def test_a_while_else_agrees():
    agree(
        "n = 0\nwhile n < 5:\n    if n == 2:\n        print(2)\n        break\n"
        "    n = n + 1\nelse:\n    print(99)\n"
    )


def test_a_while_else_that_completes_agrees():
    agree("n = 0\nwhile n < 3:\n    n = n + 1\nelse:\n    print(42)\n")


def test_a_while_else_whose_reachable_break_never_fires_agrees():
    # A `while` whose `break` is reachable but its condition never true
    # during the run: the flag is emitted (there is a `break` to guard
    # against) but stays false, so the else body runs -- the third leg,
    # alongside test_a_while_else_agrees (breaks) and
    # test_a_while_else_that_completes_agrees (no break at all, no flag).
    agree(
        "n = 0\nwhile n < 3:\n    if n == 99:\n        break\n"
        "    n = n + 1\nelse:\n    print(42)\n"
    )


def test_a_loop_else_inside_a_loop_agrees():
    # The flag lands inside the outer loop body, which is the
    # `construct`-in-a-loop trap this project has hit before -- it only
    # works because _hoist_declares lifts the declaration out.
    agree(
        "rows = [[1, 2], [3, 4]]\nt = 1\n"
        "for r in rows:\n    for v in r:\n        if v == t:\n            break\n"
        "    else:\n        print(r[0])\n"
    )


def test_a_loop_else_whose_flag_name_is_taken_agrees():
    agree(
        "broke = 5\nxs = [1]\n"
        "for x in xs:\n    break\nelse:\n    print(1)\n"
        "print(broke)\n"
    )


def test_iterating_a_dictionary_yields_its_keys_agrees():
    agree('d = {"a": 1, "b": 2}\nfor k in d:\n    print(k)\n')


def test_iterating_a_dictionary_with_integer_keys_agrees():
    # The case that used to run cleanly and print the VALUES where Python
    # prints the keys. A crash is at least visible; this one was not.
    agree("d = {0: 10, 1: 20}\nfor k in d:\n    print(k)\n")


def test_iterating_an_empty_dictionary_agrees():
    agree("d = {}\nfor k in d:\n    print(k)\nprint(9)\n")


def test_looking_up_values_while_iterating_a_dictionary_agrees():
    agree('d = {"a": 1, "b": 2}\nfor k in d:\n    print(d[k])\n')


def test_iterating_a_dictionary_built_by_subscript_agrees():
    agree('d = {}\nd["a"] = 1\nd["b"] = 2\nfor k in d:\n    print(k)\n')


def test_iterating_a_dict_literal_inline_agrees():
    agree('for k in {"a": 1, "b": 2}:\n    print(k)\n')


def test_a_comprehension_over_a_dictionary_agrees():
    agree('d = {"a": 1, "b": 2}\nprint(len([k for k in d]))\n')


def test_adding_a_key_during_iteration_completes_where_python_raises():
    # The one accepted difference, pinned so it stays a known quantity.
    # Python raises `RuntimeError: dictionary changed size during
    # iteration`; the translation walks the keys as they were at loop
    # entry and finishes. There is no MatrixLang output that reproduces a
    # Python runtime error, and the reader's program was already an error
    # -- so this is recorded rather than closed. Not an `agree()` case,
    # because the two deliberately do not agree.
    # io, Interpreter, ListSource, lex, parse, translate and Translated
    # are all already imported at the top of this file -- do not add them.
    source = 'd = {"a": 1}\nfor k in d:\n    d[k + "x"] = 2\n    print(k)\n'
    result = translate(source)
    assert isinstance(result, Translated), result
    out = io.StringIO()
    Interpreter(out=out, source=ListSource([])).run(parse(lex(result.source)))
    assert out.getvalue() == "a\n"


def test_rebinding_a_dictionary_inside_its_own_loop_agrees():
    # The list path REFUSES this shape, because the output indexes the
    # name and would follow the rebinding. A dictionary is hoisted into a
    # keys list instead, so rebinding cannot reach it -- which is also
    # what Python does, its `for` holding the object it was given.
    agree('d = {"a": 1, "b": 2}\nfor k in d:\n    d = {"z": 9}\n    print(k)\n')
