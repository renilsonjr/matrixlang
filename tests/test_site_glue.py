"""The playground's Python half, exercised under CPython.

site/glue.py is what the browser calls once Pyodide is up. Keeping it
Python rather than JavaScript is what lets the existing suite cover the
playground's logic — the project does not acquire a browser-automation
rig, and a refactor of server/sse.py that would break the page fails
here instead of silently in production.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "site"))

import glue  # noqa: E402


def test_write_turns_a_request_into_source():
    result = glue.write("add 5 and 3")
    assert result["ok"] is True
    assert result["source"].strip() == "trace 5 + 3"


def test_write_reports_a_miss_with_a_hint():
    result = glue.write("sort a list")
    assert result["ok"] is False
    assert result["error"]
    assert result["hint"] == "make a list of <values>"


def test_write_on_an_empty_request_is_a_miss():
    result = glue.write("")
    assert result["ok"] is False


def test_run_returns_wire_shaped_output_events():
    events = glue.run('trace "wake up"\n')
    outputs = [e for e in events if e["kind"] == "output"]
    assert len(outputs) == 1
    assert outputs[0]["text"] == "wake up"
    # `glyphs` is what the cascade draws. Its presence here is the point:
    # the page never transliterates in JavaScript.
    assert outputs[0]["glyphs"]
    assert "wake up" not in outputs[0]["glyphs"]


def test_run_reports_a_parse_error_rather_than_raising():
    events = glue.run("construct = 5\n")
    assert events[-1]["kind"] == "error"
    assert "line 1" in events[-1]["message"]


def test_run_reports_the_step_limit_rather_than_hanging():
    source = "construct i = 1\ndejavu true\n  i = i + 1\nflatline\n"
    events = glue.run(source, max_steps=500)
    assert events[-1]["kind"] == "error"
    assert "step limit" in events[-1]["message"]


def test_operator_prompt_comes_from_the_package():
    prompt = glue.operator_prompt("count from 1 to 10")
    # The request is embedded, not appended by the caller.
    assert "count from 1 to 10" in prompt
    # Keywords are read from tokens.py, not retyped — spot-check two that
    # arrived in different stages.
    assert "jackout" in prompt and "splice" in prompt


def test_operator_prompt_pulls_in_no_sdk():
    """The page must stay usable without the optional `anthropic` extra."""
    import subprocess
    import sys

    code = (
        "import sys; sys.path.insert(0, 'site');"
        "import glue; glue.operator_prompt('add 1 and 2');"
        "print('anthropic' in sys.modules)"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "False"


def test_glyph_renders_the_glyph_face_of_arbitrary_source():
    from matrixlang.lexer import lex
    from matrixlang.parser import parse

    result = glue.glyph("trace 5 + 3")
    assert result["ok"] is True
    assert parse(lex(result["glyph"])) == parse(lex("trace 5 + 3"))
    assert result["glyph"] != "trace 5 + 3"  # really the glyph face


def test_glyph_of_invalid_source_is_an_error():
    result = glue.glyph("trace )(")
    assert result["ok"] is False
    assert "error" in result


def test_transliterate_text_round_trips():
    original = "Neo woke up"
    glyphs = glue.transliterate_text(original)
    assert glyphs != original
    assert glue.untransliterate_text(glyphs) == original


def test_transliterate_text_matches_the_real_table():
    from matrixlang.translit import transliterate

    assert glue.transliterate_text("hello") == transliterate("hello")


def test_readers_table_documents_the_markers():
    table = glue.readers_table()
    assert "marks the next glyph as uppercase" in table
    assert "marks the next character as literal" in table


def test_run_reads_supplied_input():
    events = glue.run('construct name = jackin\ntrace "Hello, " + name\n', stdin="Neo\n")
    outputs = [e for e in events if e["kind"] == "output"]
    assert [o["text"] for o in outputs] == ["Hello, Neo"]


def test_run_without_input_reports_the_shortfall_rather_than_raising():
    # Never raises -- the JS side walks one list and has no error path.
    events = glue.run("trace jackin\n")
    assert events[-1]["kind"] == "error"
    assert "no input left to read" in events[-1]["message"]


def test_run_reports_an_over_long_decode_display_rather_than_raising():
    # `run` promises never to raise and the JS caller has no error path.
    # Was a raw ValueError out of int() -- now Decimal(stripped) never
    # raises for a long digit string, so `decode` itself succeeds; it is
    # `trace` trying to SHOW the huge result that reaches values.py's
    # digit cap. Still reachable with no input at all, straight from the
    # editor, and still an error event rather than a raised exception --
    # just from displaying, not decoding.
    too_long = "9" * (sys.int_info.default_max_str_digits + 1)
    events = glue.run(f'trace decode "{too_long}"\n')
    assert events[-1]["kind"] == "error"
    assert "cannot display a number longer than" in events[-1]["message"]


def test_run_reports_an_over_long_number_rather_than_raising():
    # The mirror of the decode case above, and the one a program reaches
    # with no input at all: CPython refuses str(int) past 4300 digits, so
    # a number built by squaring breaks `trace` and `encode` alike. `run`
    # catches MatrixLangError and nothing else, so a bare ValueError out
    # of values.py would leave the playground with an unhandled exception
    # instead of an error event.
    squared = "construct n = 10\nconstruct i = 0\ndejavu i < 13\n  n = n * n\n  i = i + 1\nflatline\n"

    traced = glue.run(squared + "trace n\n")
    assert traced[-1]["kind"] == "error"
    assert "cannot display a number longer than" in traced[-1]["message"]

    encoded = glue.run(squared + "trace encode n\n")
    assert encoded[-1]["kind"] == "error"
    assert "encode" in encoded[-1]["message"]


def test_run_reports_an_over_long_number_literal_rather_than_raising():
    # The third door to the same CPython ceiling, and the one that needs
    # no arithmetic at all: a long enough run of digits typed -- or
    # pasted -- straight into the editor. The digit cap moved out of the
    # lexer (#135): lexing and parsing a literal this long now succeed,
    # and it is `trace` trying to display the result that reaches
    # values.py's cap -- see
    # tests/test_numbers_lex.py::test_an_oversized_literal_fails_at_trace_not_at_lex_or_parse
    # for the same chain pinned closer to the source. `run` catches
    # MatrixLangError and nothing else, so a bare exception anywhere in
    # that chain would leave the playground with an unhandled exception
    # rather than an error event.
    events = glue.run("trace " + "1" * (sys.int_info.default_max_str_digits + 1) + "\n")
    assert events[-1]["kind"] == "error"
    assert "cannot display a number longer than" in events[-1]["message"]


# --- Fix-review regression: an over-long INDEX, not just an over-long
# number, escaping run() as a bare Python exception. -------------------
#
# Review on this task's first pass found two Criticals sitting in the
# same eight lines of interpreter.py's _check_index: `position` -- a
# full-size Python int by the time the "past the end" message was built
# -- was interpolated straight into an f-string, and the "not is_whole"
# branch's own to_display(index) call was unguarded, unlike every other
# to_display call site in that file. Both are the same class of bug as
# test_run_reports_an_over_long_number_literal_rather_than_raising
# above, and the same class Task 2's
# test_an_oversized_literal_fails_at_trace_not_at_lex_or_parse exists to
# catch for `trace` -- proven here for indexing instead, end to end
# through glue.run() exactly as that promise requires, and through both
# routes that can hand `_check_index` an oversized value: a literal
# typed straight into the editor, and `decode` reading external input
# (this task removed decode's own digit cap, so nothing upstream stops
# either route from reaching the index check with a huge value).


def test_run_reports_an_over_long_literal_index_rather_than_raising():
    # Critical 1, the literal route. No input needed -- reachable by
    # pasting straight into the editor.
    too_long = "9" * (sys.int_info.default_max_str_digits + 1)
    events = glue.run(f'construct xs = ["a", "b"]\ntrace xs[{too_long}]\n')
    assert events[-1]["kind"] == "error"
    assert "cannot display a number longer than" in events[-1]["message"]


def test_run_reports_an_over_long_decoded_index_rather_than_raising():
    # Critical 1, the decode route -- reached differently from the
    # literal case above: through external input rather than the lexer,
    # with nothing but `_check_index` itself standing between a caller
    # and a bare Python exception now that decode's own cap is gone.
    too_long = "9" * (sys.int_info.default_max_str_digits + 1)
    events = glue.run(
        f'construct xs = ["a", "b"]\ntrace xs[decode "{too_long}"]\n'
    )
    assert events[-1]["kind"] == "error"
    assert "cannot display a number longer than" in events[-1]["message"]


def test_run_reports_an_over_long_non_whole_index_rather_than_raising():
    # Critical 2: the "not is_whole" branch's to_display(index) call,
    # reached before position even exists -- a long, fractional index
    # never gets as far as the "past the end" message Critical 1 covers.
    too_long = "9" * (sys.int_info.default_max_str_digits + 1)
    events = glue.run(f'construct xs = ["a"]\ntrace xs[{too_long}.5]\n')
    assert events[-1]["kind"] == "error"
    assert "cannot display a number longer than" in events[-1]["message"]


def test_run_reports_an_over_long_index_on_assignment_rather_than_raising():
    # _check_index is shared between the Index-read branch of _evaluate
    # and the IndexAssign branch of _execute -- a fix in one and not the
    # other would leave this route still raising bare.
    too_long = "9" * (sys.int_info.default_max_str_digits + 1)
    events = glue.run(f'construct xs = ["a", "b"]\nxs[{too_long}] = "z"\n')
    assert events[-1]["kind"] == "error"
    assert "cannot display a number longer than" in events[-1]["message"]


def test_run_reports_an_over_long_string_index_rather_than_raising():
    # _element serves strings and lists through the same _check_index,
    # so the guard must hold for a string target too, not just a list.
    too_long = "9" * (sys.int_info.default_max_str_digits + 1)
    events = glue.run(f'construct s = "ab"\ntrace s[{too_long}]\n')
    assert events[-1]["kind"] == "error"
    assert "cannot display a number longer than" in events[-1]["message"]


def test_an_empty_input_box_is_named_when_a_program_runs_out_of_input():
    # "no input left to read" is correct and stays surface-neutral -- the CLI
    # and the REPL share it. But glue.py IS the browser, so it can say which
    # box is empty. Without this the reader is told what happened and not
    # where to fix it, which is what actually happened on the live page.
    events = glue.run("trace jackin\n", stdin="")
    assert events[-1]["kind"] == "error"
    message = events[-1]["message"]
    assert "no input left to read" in message
    assert "Input box" in message


def test_a_part_filled_input_box_says_it_ran_short_not_that_it_is_empty():
    # Supplying one line to a program that reads two is a different mistake,
    # and "the box is empty" would be a lie.
    events = glue.run("trace jackin\ntrace jackin\n", stdin="Neo\n")
    message = events[-1]["message"]
    assert "no input left to read" in message
    assert "Input box" in message
    assert "empty" not in message


def test_an_unrelated_runtime_error_gains_no_input_guidance():
    # The guidance must be narrow. A type error has nothing to do with input.
    events = glue.run('trace "id " + 1\n')
    message = events[-1]["message"]
    assert "cannot add" in message
    assert "Input box" not in message


def test_running_the_same_program_twice_gives_the_same_events():
    # THE load-bearing property. Interactive input re-runs a program once per
    # prompt and shows the reader a continuous history, which is only honest
    # because a re-run reproduces the previous run exactly. If MatrixLang ever
    # gains randomness, a clock, or any effect beyond `trace`, this fails --
    # and it should, because the interactive design breaks silently otherwise.
    #
    # Whole dicts, not a projection: `source`, `latin` and `glyphs` are what
    # playground.js hands the cascade, so a projection that dropped them would
    # stay green while the wall diverged -- the day `render_glyph` or
    # `transliterate` became order- or identity-dependent.
    source = 'construct a = jackin\ntrace "got " + a\ntrace 1 + 1\n'

    assert glue.run(source, stdin="ana") == glue.run(source, stdin="ana")


def test_fewer_answers_produce_a_prefix_of_the_full_event_stream():
    # The other half of the property: round n+1 must reproduce everything
    # round n showed, in order, before adding anything new. That is what lets
    # playground.js feed the cascade only the new suffix instead of replaying
    # the whole animation on every answer.
    #
    # Over the FULL event list, because `drawnCount` indexes the full list.
    # Comparing only outputs would miss an extra or reordered statement event
    # on re-run, which misaligns the slice and duplicates or swallows lines.
    source = 'trace "first"\nconstruct a = jackin\ntrace "then " + a\n'

    short = glue.run(source, stdin="", interactive=True)
    long = glue.run(source, stdin="ana", interactive=True)

    # The marker is the suspension itself, not something the cascade draws;
    # playground.js excludes it from `drawnCount` for exactly this reason.
    assert short[-1] == {"kind": "needs_input"}
    drawn = short[:-1]
    assert [e["text"] for e in drawn if e["kind"] == "output"] == ["first"]
    assert [e["text"] for e in long if e["kind"] == "output"] == ["first", "then ana"]
    assert long[: len(drawn)] == drawn, "a longer answer list changed earlier events"


def test_interactive_run_asks_instead_of_failing():
    events = glue.run("trace jackin\n", stdin="", interactive=True)
    assert events[-1]["kind"] == "needs_input"


def test_interactive_run_keeps_the_output_produced_before_it_asked():
    # The prompt a reader sees IS this output -- the program's own trace.
    source = 'trace "Digite a matricula ou nome: "\nconstruct a = jackin\n'
    events = glue.run(source, stdin="", interactive=True)
    outputs = [e["text"] for e in events if e["kind"] == "output"]
    assert outputs == ["Digite a matricula ou nome: "]
    assert events[-1]["kind"] == "needs_input"


def test_interactive_run_finishes_when_the_answers_suffice():
    source = 'construct a = jackin\ntrace "got " + a\n'
    events = glue.run(source, stdin="ana", interactive=True)
    assert [e["kind"] for e in events].count("needs_input") == 0
    assert [e["text"] for e in events if e["kind"] == "output"] == ["got ana"]


def test_interactive_run_still_reports_a_real_error_as_an_error():
    # A type error is not a request for input. Confusing the two would leave
    # the page asking a question the program never asked.
    events = glue.run('trace "id " + 1\n', stdin="", interactive=True)
    assert events[-1]["kind"] == "error"
    assert "cannot add" in events[-1]["message"]


def test_non_interactive_run_is_unchanged():
    # Existing callers, and the tutorial's description, must keep working.
    events = glue.run("trace jackin\n", stdin="")
    assert events[-1]["kind"] == "error"
    assert "no input left to read" in events[-1]["message"]


def test_a_trailing_newline_in_the_box_does_not_shift_later_answers():
    # The box is a <textarea> and readers press Enter, so a trailing newline
    # is the common case rather than the odd one. When the answers rode in the
    # same string as the box, `"\n".join(["ana\n", "bob"])` split back into
    # ["ana", "", "bob"] and the second question silently received "" -- the
    # typed answer discarded, a phantom blank consumed in its place, and
    # nothing on screen to say so. Two channels, so there is nothing to shift.
    source = 'construct a = jackin\nconstruct b = jackin\ntrace "a=" + a\ntrace "b=" + b\n'
    events = glue.run(source, "ana\n", True, ["bob"])
    assert [e["text"] for e in events if e["kind"] == "output"] == ["a=ana", "b=bob"]


def test_a_blank_answer_is_one_real_line():
    # Pressing Answer on an empty field is a reader saying "nothing", and a
    # blank line is real input -- `input.py` returns None for exhausted rather
    # than "" for precisely this reason. Flattened, [""] joined to "" and split
    # back to zero lines: the same needs_input stream came back, so the row
    # reappeared with the same prompt and the button looked broken.
    source = 'construct a = jackin\ntrace "[" + a + "]"\n'
    events = glue.run(source, "", True, [""])
    assert [e["text"] for e in events if e["kind"] == "output"] == ["[]"]
    assert events[-1]["kind"] != "needs_input"


def test_an_answer_is_yielded_verbatim_rather_than_re_split():
    # The contract that keeps the two channels apart: the box is text and gets
    # BufferSource's splitting, an answer is already one line and gets none.
    # The answer row is an <input>, so a reader cannot type this today -- what
    # is pinned is that answers never go back through a splitter, which is the
    # single step that caused both faults above.
    source = 'construct a = jackin\ntrace "[" + a + "]"\n'
    events = glue.run(source, "", True, ["one\ntwo"])
    assert [e["text"] for e in events if e["kind"] == "output"] == ["[one\ntwo]"]


def test_run_takes_interactive_and_answers_positionally_in_that_order():
    # The browser calls `run` positionally, and until this test the parameter
    # order was guarded by a comment alone. Verified by mutation: dropping the
    # `true` from playground.js's call reverted the whole feature to the old
    # "no input left to read" error with every Python and JavaScript test still
    # green. `interactive` and `answers` both sit before `max_steps` so the
    # page never passes a placeholder past it -- a JS `undefined` arrives as
    # Python None, and None means no step limit at all.
    events = glue.run("trace jackin\ntrace jackin\n", "", True, ["ana"])
    assert [e["text"] for e in events if e["kind"] == "output"] == ["ana"]
    assert events[-1]["kind"] == "needs_input"


def test_answers_are_ignored_when_the_caller_did_not_opt_in():
    # Non-interactive behaviour must not move: the CLI-shaped path reads the
    # box and nothing else, and still reports the shortfall as an error.
    events = glue.run("trace jackin\n", "", False, ["ana"])
    assert events[-1]["kind"] == "error"
    assert "no input left to read" in events[-1]["message"]


def test_interactive_source_splits_lines_exactly_like_non_interactive():
    # str.splitlines() also breaks on \x0b (vertical tab), which BufferSource
    # -- and therefore readline() and the CLI -- treats as an ordinary
    # character inside a line. The same Input box text must not be read
    # differently just because interactive mode is on; _InteractiveSource
    # must delegate to BufferSource's splitting rather than have its own.
    from matrixlang.input import BufferSource

    text = "a\x0bb\nc"

    buffer_source = BufferSource(text)
    buffer_lines = []
    while (line := buffer_source.next_line()) is not None:
        buffer_lines.append(line)

    interactive_source = glue._InteractiveSource(text)
    interactive_lines = []
    while True:
        try:
            interactive_lines.append(interactive_source.next_line())
        except glue._NeedsInput:
            break

    assert interactive_lines == buffer_lines == ["a\x0bb", "c"]


def test_translate_python_returns_a_program():
    result = glue.translate_python("print(1)\n")
    assert result == {"ok": True, "source": "trace 1\n"}


def test_translate_python_returns_refusals_with_positions():
    result = glue.translate_python("import os\n")
    assert result["ok"] is False
    assert result["refusals"][0]["line"] == 1


def test_translate_python_never_raises_on_invalid_python():
    result = glue.translate_python("def (:\n")
    assert result["ok"] is False


def test_translate_python_never_raises_on_a_lone_surrogate():
    # A JS string with an unpaired surrogate crosses into Python under
    # Pyodide as exactly this -- a plain browser <textarea> can hold one,
    # and ast.parse() used to fail encoding it with an uncaught
    # UnicodeEncodeError rather than a refusal.
    result = glue.translate_python("print('\udcff')")
    assert result["ok"] is False


def test_translate_python_never_raises_on_deep_nesting():
    # 500 levels of `1 + 1 + ...` is well within what a reader could paste,
    # and used to blow the walker's recursive descent with an uncaught
    # RecursionError rather than a refusal.
    result = glue.translate_python("x = " + "1 + " * 500 + "1\n")
    assert result["ok"] is False


def test_encoding_a_cyclic_value_returns_an_error_event_rather_than_raising():
    # `encode` accepts any value now, which makes a self-containing one
    # reachable inside it for the first time. run() promises never to
    # raise; that promise has been broken five times here, so a new
    # reachable exception type gets its own guard at this layer too.
    events = glue.run('construct xs = [1]\nxs[0] = xs\ntrace encode xs\n')
    assert events[-1]["kind"] == "error"
    assert "contains a cycle" in events[-1]["message"]


def test_wake_and_glitch_run_without_raising():
    # run() promises never to raise; that promise has been broken five
    # times before. `interpreter.py._execute` emits a `Statement` event
    # for EVERY statement before its isinstance dispatch, and that event
    # is rendered by `server.sse.payload` -> `render_glyph` before this
    # program's own control flow even matters. Until render.py grew
    # branches for Wake and Glitch, a program containing either raised a
    # bare AssertionError ("unhandled statement node: Wake") straight
    # out of run() -- not caught, not turned into an {"kind": "error"}
    # event, an uncaught crash of the whole call.
    #
    # `glitch` skips the `trace i` below on i == 2; `wake` breaks the
    # loop on i == 4 before its `trace i` runs. So the loop's own output
    # is "1" and "3" only, followed by "done" once the loop exits.
    source = (
        "construct i = 0\n"
        "dejavu true\n"
        "  i = i + 1\n"
        "  redpill i == 2\n"
        "    glitch\n"
        "  flatline\n"
        "  redpill i == 4\n"
        "    wake\n"
        "  flatline\n"
        "  trace i\n"
        "flatline\n"
        "trace \"done\"\n"
    )

    events = glue.run(source)

    assert [e["kind"] for e in events].count("error") == 0
    assert [e["text"] for e in events if e["kind"] == "output"] == ["1", "3", "done"]
