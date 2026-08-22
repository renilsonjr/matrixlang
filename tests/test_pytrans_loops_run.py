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


def test_a_name_first_bound_inside_a_standalone_while_runs():
    # The `for` fix hoists via _hoist_declares, and that function already
    # recurses into a nested `while`'s body -- but only when something
    # else's walk reaches it. A `while` that is not inside a `for` sits at
    # the top level of statement(), where nothing was calling the hoist at
    # all: `construct doubled = n * 2` landed inside the `dejavu` body and
    # crashed with "already declared" on the second iteration, for an
    # entirely ordinary Python loop.
    source = (
        "n = 0\n"
        "while n < 3:\n"
        "    doubled = n * 2\n"
        "    print(doubled)\n"
        "    n += 1\n"
    )
    assert _translated_output(source) == _run_python(source)



def test_a_module_level_function_called_from_a_loop_runs():
    # A `def` written directly in a loop body is refused (see
    # tests/test_pytrans_loops.py) -- but a `def` outside any loop, then
    # called from one, is unaffected by that refusal and must keep
    # working.
    source = (
        "def helper(v):\n"
        "    return v * 2\n"
        "xs = [1, 2, 3]\n"
        "for x in xs:\n"
        "    print(helper(x))\n"
    )
    assert _translated_output(source) == _run_python(source)


def test_a_range_bound_is_read_once_at_loop_entry():
    # Python builds the range object when the loop STARTS, so a body that
    # changes the bound's name still runs the original number of times.
    # Inlined into the `dejavu` condition the name was re-read every
    # iteration, and this printed 0 1 2 instead of 0 1 2 3 4 -- clean run,
    # wrong answer.
    source = (
        "n = 5\n"
        "for i in range(n):\n"
        "    n = n - 1\n"
        "    print(i)\n"
    )
    assert _translated_output(source) == _run_python(source)


def test_a_range_bound_that_is_a_call_is_read_once_too():
    source = (
        "def size():\n"
        "    return 3\n"
        "for i in range(size()):\n"
        "    print(i)\n"
    )
    assert _translated_output(source) == _run_python(source)


def test_a_nested_loop_over_a_list_of_lists_runs():
    # The inner loop's iterable is the OUTER loop's variable, which has no
    # name in the output at all -- it is substituted. Read straight off the
    # Python ast, the inner loop emitted `length row` for a `row` that was
    # never declared, and the most ordinary nested loop there is died with
    # "'row' is not declared".
    source = (
        "xs = [[1, 2], [3]]\n"
        "for row in xs:\n"
        "    for v in row:\n"
        "        print(v)\n"
    )
    assert _translated_output(source) == _run_python(source)


def test_appending_to_the_loop_variable_runs():
    # `.append` read its receiver straight off the Python ast, so inside a
    # loop it emitted `r = r + [9]` for a loop variable that has no name in
    # the output. With an outer `r` in scope that assigned the OUTER name
    # and left the list of lists untouched: a clean run and a different
    # answer. Substituted, it becomes `rs[n] = rs[n] + [9]`.
    source = (
        "rs = [[1], [2]]\n"
        "for r in rs:\n"
        "    r.append(9)\n"
        "print(rs)\n"
    )
    assert _translated_output(source) == _run_python(source)


def test_a_name_first_bound_in_one_branch_of_an_if_runs():
    # The fourth site of the declaration quirk, and the branch variant of
    # it: bindings were recorded in one flat set per scope, so the second
    # branch to bind `s` was treated as already declared and emitted a bare
    # assignment -- and `construct` only runs on the branch taken, so this
    # died with "'s' is not declared" whichever way it went.
    source = (
        "x = -1\n"
        "if x > 0:\n"
        "    s = 1\n"
        "else:\n"
        "    s = 0\n"
        "print(s)\n"
    )
    assert _translated_output(source) == _run_python(source)


def test_a_name_first_bound_in_an_elif_chain_runs():
    source = (
        "g = 2\n"
        "if g == 1:\n"
        "    s = 'a'\n"
        "elif g == 2:\n"
        "    s = 'b'\n"
        "else:\n"
        "    s = 'c'\n"
        "print(s)\n"
    )
    assert _translated_output(source) == _run_python(source)


def test_a_name_first_bound_in_a_branch_then_reassigned_after_it_runs():
    # Same cause, different shape: the branch's `construct` may not run,
    # and the assignment after the `if` always does.
    source = "c = 0\nif c > 0:\n    s = 1\ns = 2\nprint(s)\n"
    assert _translated_output(source) == _run_python(source)


def test_a_branch_binding_inside_a_def_runs():
    # An agent body is its own MatrixLang scope, so the same hoist has to
    # happen there and not be confused with the module's names.
    source = (
        "def f(c):\n"
        "    if c > 0:\n"
        "        s = 1\n"
        "    else:\n"
        "        s = 2\n"
        "    return s\n"
        "print(f(1))\n"
        "print(f(-1))\n"
    )
    assert _translated_output(source) == _run_python(source)


def test_a_branch_bound_name_is_not_reset_each_pass_of_an_enclosing_loop():
    # Two hoists nest here: the `if` hoists `s` to just above itself, and
    # then the loop hoists that placeholder out again. The placeholder has
    # to MOVE rather than be rewritten in place -- left behind as `s = 0`
    # at the top of the loop body it would reset, on every pass, a name the
    # Python expects to survive from the iteration that set it.
    source = (
        "for i in range(4):\n"
        "    if i == 0:\n"
        "        s = 1\n"
        "    print(s)\n"
    )
    assert _translated_output(source) == _run_python(source)
