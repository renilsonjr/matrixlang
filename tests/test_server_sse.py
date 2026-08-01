"""OP-D — the wire format, and the run lifecycle.

Split so the parts that decide *what* the browser receives are pure and
testable without a socket. Only `test_server_http.py` starts a server.
"""

import json

from matrixlang.events import Error, Output, Statement
from matrixlang.lexer import lex
from matrixlang.parser import parse
from server.sse import DONE, encode, frame


# --- Frames -------------------------------------------------------------


def test_a_frame_ends_with_a_blank_line():
    # The blank line IS the delimiter. Without it the browser buffers
    # forever and the cascade never moves.
    assert frame("hello").endswith("\n\n")


def test_a_frame_is_prefixed_with_data():
    assert frame("hello").startswith("data: ")


def test_a_multiline_payload_gets_one_data_prefix_per_line():
    # A raw newline inside a frame would end the event early and the
    # browser would parse half a payload.
    out = frame("one\ntwo")
    assert out == "data: one\ndata: two\n\n"


def test_the_done_sentinel_is_a_frame():
    assert DONE.endswith("\n\n")


# --- Encoding execution events -----------------------------------------


def test_an_output_event_encodes_its_text():
    payload = json.loads(encode(Output(text="wake up, Neo", line=2))[6:])
    assert payload == {"kind": "output", "text": "wake up, Neo", "line": 2}


def test_a_statement_event_encodes_its_glyph_face():
    program = parse(lex('construct name = "Neo"\n'))
    payload = json.loads(encode(Statement(node=program.statements[0], line=1))[6:])
    assert payload["kind"] == "statement"
    assert payload["line"] == 1
    assert payload["source"]


def test_a_statement_event_carries_no_python_repr():
    program = parse(lex("construct n = 0\n"))
    encoded = encode(Statement(node=program.statements[0], line=1))
    assert "matrixlang" not in encoded
    assert "0x" not in encoded


def test_an_error_event_encodes_its_message_verbatim():
    payload = json.loads(encode(Error(message="[line 1] boom"))[6:])
    assert payload == {"kind": "error", "message": "[line 1] boom"}


def test_every_encoded_event_is_a_single_frame():
    program = parse(lex('trace "a\\nb"\n'))
    for event in (
        Output(text="a\nb", line=1),
        Statement(node=program.statements[0], line=1),
        Error(message="a\nb"),
    ):
        encoded = encode(event)
        assert encoded.endswith("\n\n")
        # JSON escapes the newline, so the payload is one line.
        assert encoded.count("data: ") == 1
