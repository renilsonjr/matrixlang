"""Stage 8 — running dictionary programs end to end."""

import io

import pytest

from matrixlang.errors import RuntimeErrorML
from matrixlang.interpreter import Interpreter
from matrixlang.lexer import lex
from matrixlang.parser import parse


def run(source):
    out = io.StringIO()
    Interpreter(out=out).run(parse(lex(source)))
    return out.getvalue()


def fails(source):
    with pytest.raises(RuntimeErrorML) as caught:
        run(source)
    return caught.value


def test_a_dictionary_literal_evaluates():
    assert run('construct d = {"a": 1}\ntrace d["a"]\n') == "1\n"


def test_lookup_of_a_missing_key_is_an_error():
    error = fails('construct d = {"a": 1}\ntrace d["b"]\n')
    assert 'no key "b" in this dictionary' in error.message


def test_assignment_inserts_a_new_key():
    assert run('construct d = {"a": 1}\nd["b"] = 2\ntrace d["b"]\n') == "2\n"


def test_assignment_updates_an_existing_key_without_moving_it():
    source = 'construct d = {"a": 1, "b": 2}\nd["a"] = 9\ntrace keymaker d\n'
    assert run(source) == '["a", "b"]\n'


def test_length_of_a_dictionary_is_its_entry_count():
    assert run('trace length {"a": 1, "b": 2}\n') == "2\n"


def test_keymaker_returns_keys_in_insertion_order():
    # Insertion order is a REQUIREMENT, not an accident of CPython. The
    # playground re-runs a program from the start when it needs input and
    # draws only the events it has not drawn yet, which is honest only
    # because a re-run reproduces the one before it exactly. A keymaker
    # whose order varied would make the second run diverge from the first
    # and the reader would watch their own output change underneath them.
    source = 'construct d = {"z": 1, "a": 2}\nd["m"] = 3\ntrace keymaker d\n'
    assert run(source) == '["z", "a", "m"]\n'


def test_oracle_finds_a_present_key():
    assert run('trace {"a": 1} oracle "a"\n') == "true\n"


def test_oracle_rejects_an_absent_key():
    assert run('trace {"a": 1} oracle "b"\n') == "false\n"


def test_a_boolean_key_is_refused_with_a_position():
    error = fails("construct d = {true: 1}\n")
    assert "boolean" in error.message
    assert error.line == 1


def test_a_list_key_is_refused():
    assert "list" in fails("construct d = {[1]: 2}\n").message


def test_a_key_assigned_later_is_also_checked():
    assert "boolean" in fails('construct d = {}\nd[true] = 1\n').message


# A key reaches the checker through four doors -- a literal's entry, an
# index assignment, an index read, and `oracle`. The two above fence the
# first pair; these fence the second. Both were unfenced: deleting either
# check left the whole suite green, and the `oracle` one is not cosmetic
# -- without it `d oracle [1]` raises `TypeError: unhashable type: 'list'`
# straight out of the interpreter, a Python exception reaching the reader.


def test_a_list_key_is_refused_when_reading():
    error = fails('construct d = {"a": 1}\ntrace d[[1]]\n')
    assert "a dictionary key must be a string or a number, got list" in error.message
    assert error.line == 2


def test_a_list_key_is_refused_by_oracle():
    error = fails('construct d = {"a": 1}\ntrace d oracle [1]\n')
    assert "a dictionary key must be a string or a number, got list" in error.message
    assert error.line == 2


def test_keymaker_of_a_non_dictionary_is_an_error():
    error = fails("trace keymaker [1, 2]\n")
    assert "'keymaker' takes a dictionary, got list" in error.message


def test_oracle_on_a_non_container_is_an_error():
    # Was `[1, 2] oracle "a"`, back when a list was the example of "not a
    # dictionary". Issue #134 made a list a perfectly good left operand,
    # so the example moved to something that genuinely holds nothing.
    error = fails('trace 1 oracle "a"\n')
    assert (
        "'oracle' takes a list, a string or a dictionary, got integer"
        in error.message
    )


def test_tracing_a_cyclic_dictionary_does_not_call_it_a_list():
    # There is no list in this program. The diagnostic reaches the
    # browser verbatim in the SSE error payload, so naming the wrong
    # container is a lie a reader can see.
    error = fails('construct d = {}\nd["me"] = d\ntrace d\n')
    assert "cycle" in error.message.lower()
    assert "list" not in error.message
    assert error.line == 3


def test_a_later_duplicate_key_wins():
    assert run('trace {"a": 1, "a": 2}["a"]\n') == "2\n"


def test_nested_dictionaries_index_through():
    source = 'construct xs = [{"g": "A"}, {"g": "B"}]\ntrace xs[1]["g"]\n'
    assert run(source) == "B\n"


def test_the_students_search_program_runs():
    # This is the program that motivated the feature: a reader's Python
    # translated to MatrixLang. `alunos[n]` is indexed directly inside
    # the loop rather than bound with `construct aluno = alunos[n]`,
    # because `construct` inside a loop body fails on the second
    # iteration with "already declared" — it runs once per program, not
    # once per pass through the loop.
    source = (
        'construct alunos = [{"id": 1, "grade": "A"}, {"id": 2, "grade": "B"}, '
        '{"id": 3, "grade": "A"}]\n'
        "agent find_students(alunos, busca)\n"
        "  construct encontrados = []\n"
        "  construct n = 0\n"
        "  dejavu n < length alunos\n"
        '    redpill busca == encode alunos[n]["id"] fork busca == alunos[n]["grade"]\n'
        '      encontrados = encontrados + [alunos[n]["id"]]\n'
        "    flatline\n"
        "    n = n + 1\n"
        "  flatline\n"
        "  jackout encontrados\n"
        "flatline\n"
        'trace find_students(alunos, "A")\n'
    )
    assert run(source) == "[1, 3]\n"


# A key with more digits than CPython will render. Squaring is what makes
# it reachable: fourteen doublings of the exponent from 10 is 16385
# digits, and costs about 45 steps of a 200,000-step budget.
_OVER_LONG = """construct n = 10
construct i = 0
dejavu i < 14
  n = n * n
  i = i + 1
flatline
construct d = {}
"""


def test_a_missing_key_too_long_to_render_is_a_language_error():
    # The third door onto values.py's digit ceiling, after `trace` and
    # `encode`. The missing-key diagnostic names the key, and naming it
    # renders it -- so an unguarded render here puts a raw Python
    # TooManyDigits through Interpreter.run(), the CLI's diagnostic and
    # site/glue.py's run(), which promises never to emit one at all.
    error = fails(_OVER_LONG + "trace d[n]\n")
    assert "cannot display a number longer than 4300 digits" in error.message
    assert error.line == 8
