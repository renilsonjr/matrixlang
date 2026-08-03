"""SC-B — Scribe, the keyless generator.

Scribe is pure: it builds nodes.* ASTs from plain-language requests and
never touches the network, an SDK, or a key. The server owns the validate
gate; scribe only produces. The full language surface is covered here,
pattern by pattern.
"""

import pytest

from matrixlang.scribe import ScribeMiss, ScribeProgram, normalize, scribe


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


def test_divide_truncates_toward_zero():
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
    # Longest-match-wins degrades it to a bare, valid `trace "bigger"` instead.
    from matrixlang.operator.validate import Valid, check
    result = scribe("if five is greater than three trace bigger")
    assert isinstance(check(result.source), Valid)


def test_if_not_word_operand_is_a_miss():
    from matrixlang.operator.validate import Valid, check
    result = scribe("if not five is less than three trace smaller")
    assert isinstance(check(result.source), Valid)


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
    # Same root cause: `xs` is the list's own name, not an element. The
    # numbers still match; the trailing name is simply not part of the
    # element list. Whatever the match produces must pass check().
    result = scribe("make a list of 1 2 xs")
    assert isinstance(result, ScribeProgram)
    assert isinstance(check(result.source), Valid)


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
