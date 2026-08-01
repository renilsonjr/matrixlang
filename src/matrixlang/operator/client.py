"""The call to the model. The only impure module in the operator package.

Everything interesting about Operator — what the model is told, and
whether its output is acceptable — lives in `prompt.py` and `validate.py`
and is tested without a network. What is left here is the API call, kept
deliberately small.

`anthropic` is imported inside the function that calls it, never at
module scope. `import matrixlang.operator` must work on a machine with no
SDK installed and no key configured — the same rule `window.py` follows
for `tkinter`, for the same reason: a missing optional extra must not
become a missing package.
"""

from typing import Protocol

# Claude Opus 5 — the current Opus. Not downgraded for cost: that is the
# operator's decision to make, not this module's, and the model is a
# constructor argument.
DEFAULT_MODEL = "claude-opus-5"

# Room for a real program plus the model's thinking. Thinking is on by
# default on this model, and max_tokens caps thinking and response text
# together, so a tight budget truncates the program rather than the
# reasoning.
DEFAULT_MAX_TOKENS = 8192

_MISSING_SDK = (
    "the anthropic SDK is not installed — run: pip install 'matrixlang[bot]'"
)


class Client(Protocol):
    """What `loop.py` needs. A stub satisfying this is what the tests use."""

    def generate(self, prompt: str) -> str: ...


class AnthropicClient:
    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        api_key: str | None = None,
    ) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self._api_key = api_key

    def generate(self, prompt: str) -> str:
        anthropic = self._sdk()
        client = (
            anthropic.Anthropic(api_key=self._api_key)
            if self._api_key
            else anthropic.Anthropic()
        )
        response = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        return self._read(response)

    @staticmethod
    def _sdk(importer=None):
        """Import the SDK, turning its absence into a message a person can act on."""
        try:
            if importer is not None:
                return importer()
            import anthropic

            return anthropic
        except ImportError as error:
            raise RuntimeError(_MISSING_SDK) from error

    @staticmethod
    def _read(response) -> str:
        """Pull the source out of a response, refusing the cases that are not one.

        `stop_reason` is checked **before** `content` is touched. A safety
        decline comes back as an ordinary successful response with an
        empty content list, so code that indexes `content[0]` crashes on
        exactly the case it most needs to report.
        """
        if getattr(response, "stop_reason", None) == "refusal":
            raise RuntimeError("the model declined this request")
        if getattr(response, "stop_reason", None) == "max_tokens":
            raise RuntimeError(
                "the reply was cut off at max_tokens — the program is incomplete"
            )
        text = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        )
        if not text:
            raise RuntimeError("the model returned no text")
        return text
