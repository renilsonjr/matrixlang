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
