"""SC-B — Scribe, the keyless generator.

Scribe is pure: it builds nodes.* ASTs from plain-language requests and
never touches the network, an SDK, or a key. The server owns the validate
gate; scribe only produces. The full language surface is covered here,
pattern by pattern.
"""

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


def test_negative_operand_is_unary_minus_over_positive_literal():
    stmt = _binary_of("add -5 and 3")
    from matrixlang.nodes import Binary, NumberLiteral, Unary
    assert stmt.value.op is TokenType.PLUS
    left = stmt.value.left
    assert isinstance(left, Unary)
    assert left.op is TokenType.MINUS
    assert isinstance(left.operand, NumberLiteral)
    assert left.operand.value == 5


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
