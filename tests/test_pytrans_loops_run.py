"""Running translated `for` loops through the real interpreter and
diffing them against the Python they came from.

`tests/test_pytrans_loops.py` only checks the rendered *text*. That is
not the same guarantee as running the program: a nested-`if` hoisting
bug (a name first bound inside an `if` inside a `for` body was never
hoisted, so its `construct` landed inside the `dejavu` body and crashed
with "already declared" on the loop's second pass) shipped past every
text-shape test in that file, because none of them ran the emitted
program. These tests do -- same shape as tests/test_lists_run.py and its
siblings, but comparing against the actual Python instead of a literal
string, since the point is agreement between the two languages.
"""

import contextlib
import io

from matrixlang.interpreter import Interpreter
from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.pytrans import Translated, translate


def _run_python(source: str) -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        exec(compile(source, "<python>", "exec"), {})
    return buf.getvalue()


def _run_matrixlang(source: str) -> str:
    buf = io.StringIO()
    Interpreter(out=buf).run(parse(lex(source)))
    return buf.getvalue()


def _translated_output(python_source: str) -> str:
    """Translate `python_source` and run the result. Fails loudly on refusal."""
    result = translate(python_source)
    assert isinstance(result, Translated), getattr(result, "items", result)
    return _run_matrixlang(result.source)


def test_a_name_first_bound_inside_an_if_inside_a_loop_runs():
    source = (
        "xs = [1, 2, 3]\n"
        "for x in xs:\n"
        "    if x > 0:\n"
        "        y = x\n"
        "    print(y)\n"
    )
    assert _translated_output(source) == _run_python(source)


def test_nested_loops_reset_the_inner_counter_each_outer_pass():
    source = (
        "xs = [1, 2]\n"
        "for a in xs:\n"
        "    for b in xs:\n"
        "        print(a * 10 + b)\n"
    )
    assert _translated_output(source) == _run_python(source)


def test_a_loop_builds_up_a_list():
    source = (
        "xs = [1, 2, 3]\n"
        "ys = []\n"
        "for x in xs:\n"
        "    ys.append(x * 2)\n"
        "print(ys)\n"
    )
    assert _translated_output(source) == _run_python(source)
