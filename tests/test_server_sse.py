"""OP-D — the wire format, and the run lifecycle.

Split so the parts that decide *what* the browser receives are pure and
testable without a socket. Only `test_server_http.py` starts a server.
"""

import json

from matrixlang.cascade import _header
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


def test_an_output_event_encodes_both_the_text_and_the_glyphs():
    # The cascade draws `glyphs`; `text` is for a status line or a log.
    # Sending only `text` put Latin in the cascade with the glyph wall
    # selected, and no test caught it because none asked what the cascade
    # was handed — only the browser did.
    from matrixlang.translit import untransliterate

    payload = json.loads(encode(Output(text="wake up, Neo", line=2))[6:])
    assert payload["text"] == "wake up, Neo"
    assert payload["line"] == 2
    assert not any(ch.isascii() and ch.isalnum() for ch in payload["glyphs"])
    assert untransliterate(payload["glyphs"]) == "wake up, Neo"


def test_a_statement_event_encodes_its_glyph_face():
    program = parse(lex('construct name = "Neo"\n'))
    payload = json.loads(encode(Statement(node=program.statements[0], line=1))[6:])
    assert payload["kind"] == "statement"
    assert payload["line"] == 1
    assert payload["source"]


def test_a_statement_event_carries_both_faces():
    # The toggle in layout D switches between a pure glyph wall and the
    # glyph face with Latin identifiers. Both come from the server:
    # untransliterating in the browser would need a copy of the table in
    # JavaScript, which is exactly the duplication that made
    # web/interpreter.js drift from the language it claimed to implement.
    program = parse(lex('construct name = "Neo"\n'))
    payload = json.loads(encode(Statement(node=program.statements[0], line=1))[6:])
    assert "name" in payload["latin"]
    assert not any(ch.isascii() and ch.isalnum() for ch in payload["source"])


def test_the_two_backends_draw_the_same_source_text():
    # The Tk cascade and the browser build their source lines through
    # different code (`cascade._header` and `sse.payload`), and the two
    # have drifted once already — `encode` grew a transliterated output
    # field and the queue did not, so the browser drew Latin while every
    # test of `encode` passed.
    #
    # This nearly happened a second time in the opposite direction. The
    # escape marker was added to `transliterate` for reversibility, and
    # `cascade._header` opted out with `escape_glyphs=False` because a
    # source line is already full of the language's glyphs and escaping
    # each one doubles its height. `sse.payload` did not opt out, so the
    # browser drew an escape marker before every glyph — twice the height
    # of the same line in the window. Asserting the two agree is cheaper
    # than remembering to change both.
    for text in ('construct name = "Neo"\n', "dejavu n > 0\n  trace n\nflatline\n"):
        program = parse(lex(text))
        node = program.statements[0]
        payload = json.loads(encode(Statement(node=node, line=1))[6:])
        assert payload["source"] == _header(node), text


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
