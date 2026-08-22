"""Translate, run both, compare.

The only tests here that can catch an output which parses, runs, and
means something other than the Python did.
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
