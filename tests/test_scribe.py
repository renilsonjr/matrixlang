"""SC-B — Scribe, the keyless generator.

Scribe is pure: it builds nodes.* ASTs from plain-language requests and
never touches the network, an SDK, or a key. The server owns the validate
gate; scribe only produces. The full language surface is covered here,
pattern by pattern.
"""

import pytest

from matrixlang.scribe import (
    _MAX_LOOP_ITERATIONS,
    ScribeMiss,
    ScribeProgram,
    normalize,
    scribe,
)
from matrixlang.tokens import KEYWORDS


def test_normalize_collapses_whitespace_but_never_inside_quotes():
    assert normalize('print  hello   world') == "trace hello world"
    assert normalize('trace "Hello  World"') == 'trace "Hello  World"'
    assert normalize('print "  padded  "') == 'trace "  padded  "'


def test_an_empty_request_is_a_miss():
    result = scribe("")
    assert isinstance(result, ScribeMiss)
    assert result.reason


def test_unrecognized_request_is_a_miss_with_a_hint():
    result = scribe("make soup")
    assert isinstance(result, ScribeMiss)
    assert result.closest


def test_a_known_request_produces_source_that_parses():
    result = scribe("print hello")
    assert isinstance(result, ScribeProgram)
    assert "trace" in result.source


def test_scribe_never_touches_a_key():
    # The pure contract: no exception, no network, deterministic result.
    import subprocess
    import sys

    code = "from matrixlang.scribe import scribe; r = scribe('print hi'); print(type(r).__name__)"
    out = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True,
        text=True,
        check=True,
    )
    assert out.stdout.strip() == "ScribeProgram"


from matrixlang.scribe import ScribeProgram, scribe
from matrixlang.tokens import TokenType


def _binary_of(request):
    result = scribe(request)
    assert isinstance(result, ScribeProgram)
    from matrixlang.lexer import lex
    from matrixlang.parser import parse
    tree = parse(lex(result.source))
    assert tree.statements
    return tree.statements[0]


def test_add_two_numbers():
    stmt = _binary_of("add 5 and 3")
    from matrixlang.nodes import Trace
    assert isinstance(stmt, Trace)
    from matrixlang.nodes import Binary, NumberLiteral
    assert isinstance(stmt.value, Binary)
    assert stmt.value.op is TokenType.PLUS
    assert stmt.value.left.value == 5
    assert stmt.value.right.value == 3


def test_subtract():
    stmt = _binary_of("subtract 7 minus 2")
    from matrixlang.nodes import Binary, NumberLiteral
    assert stmt.value.op is TokenType.MINUS
    assert stmt.value.left.value == 7
    assert stmt.value.right.value == 2


def test_subtract_from_swaps_operands():
    stmt = _binary_of("subtract 7 from 2")
    from matrixlang.nodes import Binary, NumberLiteral
    assert stmt.value.op is TokenType.MINUS
    assert stmt.value.left.value == 2
    assert stmt.value.right.value == 7


def test_multiply():
    stmt = _binary_of("multiply 4 times 6")
    from matrixlang.nodes import Binary
    assert stmt.value.op is TokenType.STAR


def test_divide_is_true_division():
    # Was named test_divide_truncates_toward_zero, which stated the
    # opposite of what `/` does now: `divide 10 by 3` is 3.333..., and
    # `half of 9` is 4.5, not 4. The assertion never checked truncation --
    # only that the operator is SLASH -- so the name outlived the rule.
    stmt = _binary_of("divide 10 by 3")
    from matrixlang.nodes import Binary
    assert stmt.value.op is TokenType.SLASH


def test_double():
    stmt = _binary_of("double 4")
    from matrixlang.nodes import Binary, NumberLiteral
    assert stmt.value.op is TokenType.STAR
    assert stmt.value.right.value == 2


def test_half():
    stmt = _binary_of("half of 9")
    from matrixlang.nodes import Binary, NumberLiteral
    assert stmt.value.op is TokenType.SLASH
    assert stmt.value.right.value == 2


def test_add_rejects_word_operands():
    # A Scribe program can never declare "five", so a word operand must be
    # a miss — never a program check() rejects for 'five' is not declared.
    result = scribe("add five and three")
    assert isinstance(result, ScribeMiss)


def test_double_rejects_word_operands():
    result = scribe("double five")
    assert isinstance(result, ScribeMiss)


def test_compare_rejects_word_operands():
    result = scribe("is five greater than three")
    assert isinstance(result, ScribeMiss)


def test_subtract_rejects_word_operands():
    # A miss, never the wrong program `trace five - three`.
    result = scribe("subtract five from three")
    assert isinstance(result, ScribeMiss)


def test_negative_operand_is_unary_minus_over_positive_literal():
    stmt = _binary_of("add -5 and 3")
    from matrixlang.nodes import Binary, NumberLiteral, Unary
    assert stmt.value.op is TokenType.PLUS
    left = stmt.value.left
    assert isinstance(left, Unary)
    assert left.op is TokenType.MINUS
    assert isinstance(left.operand, NumberLiteral)
    assert left.operand.value == 5


def test_multi_minus_values_never_raise_and_pass_check():
    # Regression: "--5" crashed int() with a ValueError, violating scribe's
    # never-raises contract. In value contexts it becomes a string literal
    # the dry run accepts, instead of a crash that kills the request.
    from matrixlang.lexer import lex
    from matrixlang.operator.validate import Valid, check
    from matrixlang.parser import parse

    result = scribe("trace --5")
    assert isinstance(result, ScribeProgram)
    from matrixlang.nodes import StringLiteral
    assert isinstance(parse(lex(result.source)).statements[0].value, StringLiteral)
    assert isinstance(check(result.source), Valid)

    for request in ["store --5 as total", "if 5 is greater than 3 trace --5"]:
        result = scribe(request)
        assert isinstance(result, ScribeProgram), request
        assert isinstance(check(result.source), Valid), request


def test_comparison_greater_than():
    stmt = _binary_of("is 5 greater than 3")
    from matrixlang.nodes import Binary
    assert stmt.value.op is TokenType.GT


def test_comparison_less_than_or_equal():
    stmt = _binary_of("is 3 less than or equal to 4")
    from matrixlang.nodes import Binary
    assert stmt.value.op is TokenType.LTE


from matrixlang.lexer import lex
from matrixlang.nodes import Declare, Name, NumberLiteral, StringLiteral, Trace
from matrixlang.parser import parse


def test_trace_a_string_literal():
    result = scribe("trace hello")
    assert isinstance(result, ScribeProgram)
    tree = parse(lex(result.source))
    stmt = tree.statements[0]
    assert isinstance(stmt, Trace)
    assert isinstance(stmt.value, StringLiteral)
    assert stmt.value.value == "hello"


def test_trace_a_quoted_string():
    result = scribe('trace "wake up"')
    assert isinstance(result, ScribeProgram)
    tree = parse(lex(result.source))
    assert isinstance(tree.statements[0].value, StringLiteral)


def test_trace_a_number():
    result = scribe("trace 42")
    assert isinstance(result, ScribeProgram)
    tree = parse(lex(result.source))
    assert isinstance(tree.statements[0].value, NumberLiteral)


def test_declare_and_trace_a_name():
    # "store as total" binds a name, then traces it.
    result = scribe("store 5 as total")
    assert isinstance(result, ScribeProgram)
    tree = parse(lex(result.source))
    stmt = tree.statements[0]
    assert isinstance(stmt, Declare)
    assert stmt.name == "total"
    assert stmt.value.value == 5


from matrixlang.nodes import Assign, Declare, Name, NumberLiteral, Trace, While


def test_count_from_one_to_ten():
    result = scribe("count from 1 to 10")
    assert isinstance(result, ScribeProgram)
    tree = parse(lex(result.source))
    assert isinstance(tree.statements[0], Declare)  # i = 1
    loop = tree.statements[1]
    assert isinstance(loop, While)
    from matrixlang.nodes import Binary
    assert loop.condition.left.ident == "i"
    assert loop.condition.op is TokenType.LTE
    assert loop.condition.right.value == 10
    assert isinstance(loop.body[0], Trace)
    assert isinstance(loop.body[1], Assign)
    assert loop.body[1].name == "i"


def test_count_down():
    result = scribe("count down from 5 to 1")
    assert isinstance(result, ScribeProgram)
    tree = parse(lex(result.source))
    loop = tree.statements[1]
    assert isinstance(loop, While)
    from matrixlang.nodes import Binary
    assert loop.condition.op is TokenType.GTE
    assert loop.body[1].value.right.value == 1  # i = i - 1


from matrixlang.nodes import If, Unary


def test_if_greater_than_traces():
    result = scribe("if 5 is greater than 3 trace bigger")
    assert isinstance(result, ScribeProgram)
    tree = parse(lex(result.source))
    stmt = tree.statements[0]
    assert isinstance(stmt, If)
    from matrixlang.nodes import Binary, StringLiteral
    assert isinstance(stmt.condition, Binary)
    assert stmt.condition.op is TokenType.GT
    assert isinstance(stmt.then_body[0], Trace)
    assert stmt.else_body is None


def test_if_not_unplug():
    result = scribe("if not 5 is equal to 6 trace no")
    assert isinstance(result, ScribeProgram)
    tree = parse(lex(result.source))
    stmt = tree.statements[0]
    assert isinstance(stmt, If)
    assert isinstance(stmt.condition, Unary)
    assert stmt.condition.op is TokenType.UNPLUG


def test_if_greater_than_or_equal_to_traces():
    # Without GTE in the conditional pattern this degrades, via longest
    # match wins, to a bare `trace "bigger"` — the condition silently
    # disappears and the action runs unconditionally.
    result = scribe("if 5 is greater than or equal to 3 trace bigger")
    assert isinstance(result, ScribeProgram)
    tree = parse(lex(result.source))
    stmt = tree.statements[0]
    assert isinstance(stmt, If)
    from matrixlang.nodes import Binary
    assert stmt.condition.op is TokenType.GTE
    assert isinstance(stmt.then_body[0], Trace)
    from matrixlang.operator.validate import Valid, check
    assert isinstance(check(result.source), Valid)


def test_if_less_than_or_equal_to_traces():
    result = scribe("if 3 is less than or equal to 4 trace small")
    assert isinstance(result, ScribeProgram)
    tree = parse(lex(result.source))
    stmt = tree.statements[0]
    assert isinstance(stmt, If)
    assert stmt.condition.op is TokenType.LTE
    assert isinstance(stmt.then_body[0], Trace)
    from matrixlang.operator.validate import Valid, check
    assert isinstance(check(result.source), Valid)


def test_if_not_greater_than_or_equal_to_traces():
    result = scribe("if not 5 is greater than or equal to 3 trace big")
    assert isinstance(result, ScribeProgram)
    tree = parse(lex(result.source))
    stmt = tree.statements[0]
    assert isinstance(stmt, If)
    assert isinstance(stmt.condition, Unary)
    assert stmt.condition.op is TokenType.UNPLUG
    from matrixlang.nodes import Binary
    assert stmt.condition.operand.op is TokenType.GTE


def test_if_word_operand_is_a_miss():
    # A word operand could never resolve — no such name is declared — so the
    # conditional must not build `redpill five > three` (check() rejects it).
    # Nor may it degrade to a bare unconditional `trace "bigger"`: a request
    # that opens with a conditional prefix is a miss, never a silent trace.
    result = scribe("if five is greater than three trace bigger")
    assert isinstance(result, ScribeMiss)
    assert result.reason


def test_if_not_word_operand_is_a_miss():
    # Same guard for the negated form: unmatched `if not ...` is a miss, not
    # a silent unconditional `trace "smaller"`.
    result = scribe("if not five is less than three trace smaller")
    assert isinstance(result, ScribeMiss)
    assert result.reason


def test_if_numeric_condition_still_builds_if():
    # The guard only fires when the conditional regexes failed. A numeric
    # condition still produces the real `If` program.
    result = scribe("if 5 is greater than 3 trace bigger")
    assert isinstance(result, ScribeProgram)
    tree = parse(lex(result.source))
    assert isinstance(tree.statements[0], If)
    from matrixlang.nodes import Binary
    assert isinstance(tree.statements[0].condition, Binary)


def test_if_not_numeric_condition_still_builds_if():
    result = scribe("if not 3 is less than 4 trace smaller")
    assert isinstance(result, ScribeProgram)
    tree = parse(lex(result.source))
    stmt = tree.statements[0]
    assert isinstance(stmt, If)
    assert isinstance(stmt.condition, Unary)
    assert stmt.condition.op is TokenType.UNPLUG


def test_bare_trace_still_works():
    # The guard must not fire for a plain trace request — no `if` prefix.
    result = scribe("trace x")
    assert isinstance(result, ScribeProgram)
    tree = parse(lex(result.source))
    assert isinstance(tree.statements[0], Trace)


from matrixlang.nodes import Declare, Index, ListLiteral, NumberLiteral, Trace, Unary


def test_make_a_list():
    result = scribe("make a list of 1 2 3")
    assert isinstance(result, ScribeProgram)
    tree = parse(lex(result.source))
    stmt = tree.statements[0]
    assert isinstance(stmt, Declare)
    assert stmt.name == "xs"
    assert isinstance(stmt.value, ListLiteral)
    assert [e.value for e in stmt.value.elements] == [1, 2, 3]


def test_get_element():
    result = scribe("get element 0 of xs")
    assert isinstance(result, ScribeProgram)
    tree = parse(lex(result.source))
    # The list is declared first — a program that only reads `xs` is
    # rejected by check() for naming an undeclared variable.
    assert isinstance(tree.statements[0], Declare)
    stmt = tree.statements[1]
    assert isinstance(stmt, Trace)
    assert isinstance(stmt.value, Index)
    assert stmt.value.index.value == 0


def test_length_of_list():
    result = scribe("length of xs")
    assert isinstance(result, ScribeProgram)
    tree = parse(lex(result.source))
    assert isinstance(tree.statements[0], Declare)
    stmt = tree.statements[1]
    assert isinstance(stmt, Trace)
    assert isinstance(stmt.value, Unary)
    assert stmt.value.op is TokenType.LENGTH


from matrixlang.operator.validate import Valid, check


def test_make_a_list_rejects_word_elements():
    # A word element could never resolve — the only declared name is the
    # list's own `xs` — so such a request must not produce a program that
    # check() would reject.
    result = scribe("make a list of a b c")
    assert isinstance(result, ScribeMiss)


def test_make_a_list_rejects_trailing_undeclared_name():
    # This used to assert a ScribeProgram, on the reading that `xs` was the
    # list's own name rather than an element. It wasn't: the name `xs` is a
    # hardcoded default, so "make a list of 1 2 foo" produced the identical
    # `construct xs = [1, 2]` and dropped `foo` on the floor. The old
    # assertion only looked right because the example word and the default
    # name happened to be the same string.
    #
    # A trailing word the pattern cannot place is discarded content, which
    # is the same defect as a pasted program matching on its last line.
    result = scribe("make a list of 1 2 xs")
    assert isinstance(result, ScribeMiss)


def test_make_a_list_discards_nothing_silently():
    # The generalization of the case above, with a word that cannot be
    # confused with the default list name.
    result = scribe("make a list of 1 2 banana")
    assert isinstance(result, ScribeMiss), "dropped 'banana' and built a list anyway"


def test_get_element_rejects_negative_index():
    result = scribe("get element -1 of xs")
    assert isinstance(result, ScribeMiss)


def test_get_element_index_bound_matches_demo_list():
    # The demo list is fixed at 3 elements, so only indices 0-2 survive
    # the check() dry-run. An index at or past the length must be a miss —
    # never a program check() would reject at runtime.
    for i in range(3):
        result = scribe(f"get element {i} of xs")
        assert isinstance(result, ScribeProgram)
        assert isinstance(check(result.source), Valid)
    for i in (3, 5, 100):
        result = scribe(f"get element {i} of xs")
        assert isinstance(result, ScribeMiss)


def test_list_intents_pass_check_gate():
    for request in [
        "make a list of 1 2 3",
        "make a list of -1 2 3",
        "get element 0 of xs",
        "get element 2 of xs",
        "length of xs",
    ]:
        result = scribe(request)
        assert isinstance(result, ScribeProgram)
        assert isinstance(check(result.source), Valid)


from matrixlang.nodes import Declare, StringLiteral, Index


def test_make_a_string():
    result = scribe("make a string hello")
    assert isinstance(result, ScribeProgram)
    tree = parse(lex(result.source))
    stmt = tree.statements[0]
    assert isinstance(stmt, Declare)
    assert stmt.name == "s"
    assert isinstance(stmt.value, StringLiteral)
    assert stmt.value.value == "hello"


def test_get_character():
    result = scribe("get character 0 of name")
    assert isinstance(result, ScribeProgram)
    tree = parse(lex(result.source))
    assert isinstance(tree.statements[0], Declare)
    stmt = tree.statements[1]
    assert isinstance(stmt, Trace)
    assert isinstance(stmt.value, Index)
    assert stmt.value.target.ident == "name"


def test_get_character_rejects_negative_index():
    result = scribe("get character -1 of name")
    assert isinstance(result, ScribeMiss)


def test_get_character_index_bound_matches_demo_string():
    # The demo string is fixed at 3 characters, so only indices 0-2 survive
    # the check() dry-run. An index at or past the length must be a miss —
    # never a program check() would reject at runtime.
    for i in range(3):
        result = scribe(f"get character {i} of name")
        assert isinstance(result, ScribeProgram)
        assert isinstance(check(result.source), Valid)
    for i in (3, 5, 100):
        result = scribe(f"get character {i} of name")
        assert isinstance(result, ScribeMiss)


def test_string_intents_pass_check_gate():
    for request in [
        "make a string hello",
        "get character 0 of name",
        "get character 2 of name",
    ]:
        result = scribe(request)
        assert isinstance(result, ScribeProgram)
        assert isinstance(check(result.source), Valid)


from matrixlang.nodes import FunctionDef, Return, Call, Declare, Trace


def test_define_a_double_function():
    result = scribe("define a function that doubles")
    assert isinstance(result, ScribeProgram)
    tree = parse(lex(result.source))
    fn = tree.statements[0]
    assert isinstance(fn, FunctionDef)
    assert fn.name == "double"
    assert fn.params == ["n"]
    assert isinstance(fn.body[0], Return)
    from matrixlang.nodes import Binary
    assert isinstance(fn.body[0].value, Binary)
    assert fn.body[0].value.op is TokenType.STAR


def test_adder_factory_returns_a_function():
    result = scribe("define an adder factory")
    assert isinstance(result, ScribeProgram)
    tree = parse(lex(result.source))
    outer = tree.statements[0]
    assert isinstance(outer, FunctionDef)
    assert isinstance(outer.body[0], FunctionDef)  # inner agent
    assert isinstance(outer.body[1], Return)        # jackout inner


# Every request in the §3 catalogue. Both tests below iterate this, because
# the two properties are independent and a program can have one without the
# other.
CATALOGUE = [
    "add 5 and 3",
    "subtract 7 minus 2",
    "multiply 4 times 6",
    "divide 10 by 3",
    "double 4",
    "half of 9",
    "is 5 greater than 3",
    "trace hello",
    "store 5 as total",
    "count from 1 to 10",
    "count down from 5 to 1",
    "make a list of 1 2 3",
    "get element 0 of xs",
    "length of xs",
    "make a string hello",
    "get character 0 of name",
    "define a function that doubles",
    "define an adder factory",
    "if 5 is greater than 3 trace bigger",
    "if not 5 is equal to 6 trace no",
]


@pytest.mark.parametrize("request_text", CATALOGUE)
def test_generated_programs_round_trip(request_text):
    """parse(render_ascii(program)) == program for every Scribe program."""
    from matrixlang.lexer import lex
    from matrixlang.parser import parse
    from matrixlang.render import render_ascii

    result = scribe(request_text)
    assert isinstance(result, ScribeProgram)
    assert parse(lex(render_ascii(result.program))) == result.program


@pytest.mark.parametrize("request_text", CATALOGUE)
def test_every_catalogued_request_survives_the_validate_gate(request_text):
    """Round-tripping is not enough — the program has to actually run.

    This is the assertion that catches an intent which reads a variable it
    never declared: `trace xs[0]` parses, renders, and round-trips
    perfectly, then fails at runtime with "'xs' is not declared" — so the
    server returns an error and the intent is dead on arrival. Only the
    dry run sees it.
    """
    from matrixlang.operator.validate import Valid, check

    result = scribe(request_text)
    assert isinstance(result, ScribeProgram)
    outcome = check(result.source)
    assert isinstance(outcome, Valid), f"{request_text!r} -> {outcome.as_diagnostic()}"


# --- The invariant, and the three ways it was breakable ---------------------
#
# "Every accepted input produces a program check() dry-runs as valid" is the
# rule the list and string index bounds already existed to protect. These
# pin the cases where it did not hold: a reserved word used as a variable
# name, and a loop span larger than the dry run's budget. Both returned a
# ScribeProgram whose source failed check(), so the browser showed a raw
# compiler diagnostic where it should have shown a program or a hint.


@pytest.mark.parametrize("keyword", sorted(KEYWORDS))
@pytest.mark.parametrize(
    "template",
    ["store 5 as {}", "length of {}", "get element 0 of {}", "get character 0 of {}"],
)
def test_a_reserved_word_is_never_bound_as_a_name(keyword, template):
    """`construct trace = 5` is a parse error, so it must never be built.

    The name groups read from tokens.KEYWORDS rather than a retyped list,
    so adding a keyword to the language cannot leave this stale.
    """
    result = scribe(template.format(keyword))
    assert isinstance(result, ScribeMiss), f"{template.format(keyword)!r} built a program"


def test_an_ordinary_name_still_binds():
    # The keyword guard must not swallow legitimate names.
    result = scribe("store 5 as total")
    assert isinstance(result, ScribeProgram)
    assert "construct total = 5" in result.source


@pytest.mark.parametrize(
    "request_text",
    [
        "count from 1 to 10000",
        "count from 1 to 999999999",
        "count down from 999999 to 1",
        "count from -999999 to 999999",
    ],
)
def test_a_loop_past_the_dry_run_budget_is_a_miss(request_text):
    """Unbounded in the request, bounded in the dry run — so refuse it here.

    Without this the user typed "count from 1 to 10000" and got
    "[line 3, column 3] program exceeded the step limit", which reads as a
    bug in their request rather than a limit of the preview.
    """
    result = scribe(request_text)
    assert isinstance(result, ScribeMiss)
    assert "dry run" in result.reason


def test_a_loop_inside_the_budget_still_builds():
    result = scribe(f"count from 1 to {_MAX_LOOP_ITERATIONS}")
    assert isinstance(result, ScribeProgram)
    from matrixlang.operator.validate import Valid, check

    assert isinstance(check(result.source), Valid)


def test_the_loop_ceiling_is_actually_what_the_dry_run_affords():
    """Pins the constant to the real budget rather than to a comment.

    _MAX_LOOP_ITERATIONS is hardcoded because scribe may not import
    operator (SC-5). This is the test that catches the two drifting apart.
    """
    from matrixlang.operator.validate import Valid, check

    result = scribe(f"count from 1 to {_MAX_LOOP_ITERATIONS}")
    assert isinstance(result, ScribeProgram)
    assert isinstance(check(result.source), Valid), (
        f"_MAX_LOOP_ITERATIONS={_MAX_LOOP_ITERATIONS} no longer fits the dry run"
    )


@pytest.mark.parametrize(
    "request_text,expected",
    [
        ("get element 9 of xs", "get element <i> of <list>"),
        ("get character 9 of name", "get character <i> of <name>"),
        ("make soup", "make a list of <values>"),
    ],
)
def test_a_miss_suggests_the_pattern_it_nearly_matched(request_text, expected):
    """Hints scored on identifying words, not on "a" and "of".

    Matching any hint token made "render a 3d scene" suggest "make a list
    of <values>" because both contain the letter a, and sent someone who
    asked for element 9 to "half of <a>".
    """
    result = scribe(request_text)
    assert isinstance(result, ScribeMiss)
    assert result.closest == expected


def test_no_accepted_request_is_ever_check_invalid():
    """The invariant itself, fuzzed over the catalogue's own vocabulary."""
    import random

    from matrixlang.operator.validate import Valid, check

    vocabulary = [
        "add", "trace", "store", "count", "down", "from", "to", "of", "get",
        "element", "length", "make", "list", "string", "character", "if",
        "not", "is", "greater", "than", "less", "equal", "double", "half",
        "define", "function", "adder", "factory", "as", "and", "agent",
        "flatline", "construct", "xs", "name", "total", "5", "0", "-2", "10000",
    ]
    random.seed(20260803)
    for _ in range(2000):
        text = " ".join(random.choices(vocabulary, k=random.randint(1, 8)))
        result = scribe(text)
        if isinstance(result, ScribeProgram):
            outcome = check(result.source)
            assert isinstance(outcome, Valid), (
                f"{text!r} produced {result.source!r} -> {outcome.as_diagnostic()}"
            )


# --- Partial matches are misses, not guesses ----------------------------
#
# The catalogue is searched with .search(), so a pattern can match a
# fragment buried in a much larger request and the rest is silently
# discarded. That is how a whole Python program pasted into the request
# box came back as `trace "(result)"` — the tail `print (result)` matched
# and the fifty lines above it were dropped. A request Scribe only
# partly understood is a miss: guessing is the one thing this module
# exists not to do.


def test_a_pattern_buried_in_unrelated_text_is_a_miss():
    result = scribe("blah blah blah print (result)")
    assert isinstance(result, ScribeMiss), "matched a fragment and discarded the rest"


def test_a_pasted_program_is_a_miss_rather_than_its_last_line():
    request = (
        "user_input = input('What book do you want?') "
        'books = ["Clean Code", "Refactoring"] '
        "def find_item(books, target): for item in books: "
        "if item == target: return item "
        "result = find_item(books, user_input) print (result)"
    )
    result = scribe(request)
    assert isinstance(result, ScribeMiss), "a pasted program became a one-line guess"


def test_politeness_and_punctuation_still_match():
    # The fix must not make the catalogue brittle: filler around a request
    # is not content Scribe failed to understand.
    for request in ["please print hello", "count from 1 to 5.", "can you print hello"]:
        result = scribe(request)
        assert isinstance(result, ScribeProgram), f"{request!r} became a miss"


def test_a_pasted_program_offers_no_phrasing_suggestion():
    # The "closest phrasing" hint is for someone who asked in words Scribe
    # not quite know. Someone who pasted code did not mishrase a request —
    # they used the wrong input entirely, and suggesting
    # `if not <a> is greater than <b> trace <value>` sends them further from
    # what they wanted. The reason already tells them what went wrong.
    result = scribe("construct xs = [1, 2, 3]\ntrace xs\n")
    assert isinstance(result, ScribeMiss)
    assert result.closest is None, f"offered a phrasing hint: {result.closest!r}"


def test_a_pasted_program_is_told_to_run_it_instead():
    result = scribe("construct xs = [1, 2, 3]\ntrace xs\n")
    assert isinstance(result, ScribeMiss)
    assert "run it" in result.reason


def test_an_ordinary_miss_still_offers_the_closest_phrasing():
    # The suppression above must be narrow: a real phrasing miss still gets
    # the help it always did.
    result = scribe("make soup")
    assert isinstance(result, ScribeMiss)
    assert result.closest


def test_a_decimal_is_a_number_not_a_string():
    # `trace 2.5` produced `trace "2.5"` -- a StringLiteral. Every numeric
    # gate in this module was `-?\\d+`, written before `.` was in the number
    # grammar, so a decimal fell straight through _value's "a bare word is
    # a string literal" fallback: no miss, no error, the wrong type,
    # silently, from a front end the web UI is served from.
    from decimal import Decimal

    from matrixlang.nodes import NumberLiteral

    result = scribe("trace 2.5")
    assert isinstance(result, ScribeProgram)
    stmt = result.program.statements[0]
    assert isinstance(stmt.value, NumberLiteral)
    assert stmt.value.value == Decimal("2.5")
    assert result.source == "trace 2.5\n"


def test_a_negative_decimal_is_a_unary_minus_over_a_positive_literal():
    from decimal import Decimal

    from matrixlang.nodes import NumberLiteral, Unary

    result = scribe("trace -2.5")
    assert isinstance(result, ScribeProgram)
    stmt = result.program.statements[0]
    assert isinstance(stmt.value, Unary)
    assert stmt.value.op is TokenType.MINUS
    assert isinstance(stmt.value.operand, NumberLiteral)
    assert stmt.value.operand.value == Decimal("2.5")


def test_store_binds_a_decimal_as_a_number():
    from decimal import Decimal

    from matrixlang.nodes import NumberLiteral

    result = scribe("store 49.90 as price")
    assert isinstance(result, ScribeProgram)
    # Trailing zeros are significant: 49.90, not 49.9.
    assert result.source == "construct price = 49.90\n"
    assert result.program.statements[0].value.value == Decimal("49.90")


def test_a_token_that_only_looks_numeric_is_still_a_string():
    # The gate is the lexer's grammar exactly -- digits required on BOTH
    # sides of the point -- not "anything with a dot in it". `2.` is not a
    # number this language can write, so the string fallback is right.
    from matrixlang.nodes import StringLiteral

    result = scribe("trace 2.")
    assert isinstance(result, ScribeProgram)
    assert isinstance(result.program.statements[0].value, StringLiteral)


def test_arithmetic_intents_still_miss_cleanly_on_a_decimal():
    # The arithmetic patterns keep capturing `-?\\d+`. A miss is a correct
    # answer -- it says "I did not understand" rather than building a
    # program from a pattern that never expected a decimal.
    assert isinstance(scribe("add 2.5 and 1"), ScribeMiss)
