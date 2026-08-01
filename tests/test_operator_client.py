"""OP-C — the LLM client.

**No test here makes an API call.** What is tested is everything around
the call: that the SDK is not imported until it is needed, that a refusal
is handled rather than crashing, and that the model is the one the
project chose.
"""

import ast
import pathlib

import pytest

from matrixlang.operator import client as client_module
from matrixlang.operator.client import DEFAULT_MAX_TOKENS, DEFAULT_MODEL, AnthropicClient


# --- The dependency stays optional --------------------------------------


def test_the_sdk_is_not_imported_at_module_scope():
    # OP-5. `import matrixlang.operator` must work on a machine with no
    # SDK installed — the same rule window.py follows for tkinter, and
    # for the same reason: a missing extra must not become a missing
    # package.
    source = pathlib.Path(client_module.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    top_level = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = []
    for node in top_level:
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif node.module:
            names.append(node.module)
    assert not any(n.split(".")[0] == "anthropic" for n in names)


def test_constructing_a_client_does_not_import_the_sdk():
    import sys

    before = "anthropic" in sys.modules
    AnthropicClient()
    assert ("anthropic" in sys.modules) == before


def test_a_missing_sdk_is_a_clear_message_not_an_import_error():
    c = AnthropicClient()
    with pytest.raises(RuntimeError) as excinfo:
        c._sdk(lambda: (_ for _ in ()).throw(ImportError("no module")))
    assert "matrixlang[bot]" in str(excinfo.value)


# --- The model ----------------------------------------------------------


def test_the_default_model_is_the_current_opus():
    assert DEFAULT_MODEL == "claude-opus-5"


def test_the_model_is_overridable():
    assert AnthropicClient(model="claude-sonnet-5").model == "claude-sonnet-5"


def test_max_tokens_leaves_room_for_a_real_program():
    assert DEFAULT_MAX_TOKENS >= 4096


# --- Reading a response -------------------------------------------------


class FakeBlock:
    def __init__(self, text):
        self.type = "text"
        self.text = text


class FakeResponse:
    def __init__(self, blocks, stop_reason="end_turn"):
        self.content = blocks
        self.stop_reason = stop_reason
        self.stop_details = None


def test_text_blocks_are_joined():
    c = AnthropicClient()
    assert c._read(FakeResponse([FakeBlock("trace 1\n")])) == "trace 1\n"


def test_a_refusal_is_raised_before_the_content_is_read():
    # A refusal returns HTTP 200 with empty content. Code that indexes
    # content[0] unconditionally crashes on it; the stop_reason must be
    # checked first.
    c = AnthropicClient()
    with pytest.raises(RuntimeError) as excinfo:
        c._read(FakeResponse([], stop_reason="refusal"))
    assert "declined" in str(excinfo.value).lower()


def test_a_truncated_response_says_so():
    c = AnthropicClient()
    with pytest.raises(RuntimeError) as excinfo:
        c._read(FakeResponse([FakeBlock("agent f(")], stop_reason="max_tokens"))
    assert "max_tokens" in str(excinfo.value)


def test_non_text_blocks_are_ignored():
    class Thinking:
        type = "thinking"
        thinking = "..."

    c = AnthropicClient()
    assert c._read(FakeResponse([Thinking(), FakeBlock("trace 1\n")])) == "trace 1\n"


def test_a_response_with_no_text_is_an_error_not_an_empty_string():
    c = AnthropicClient()
    with pytest.raises(RuntimeError):
        c._read(FakeResponse([]))


# --- It satisfies what the loop needs -----------------------------------


def test_the_client_satisfies_the_protocol_the_loop_expects():
    assert callable(AnthropicClient().generate)
