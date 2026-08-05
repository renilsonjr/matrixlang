"""The key gate: a reader's API key is memory-only and goes to one host.

§4 of the design says the key lives in a variable, never in storage, and
travels only to Anthropic. This is what enforces it, so the rule is a
build failure rather than a review note.

Comments are stripped before checking, for the same reason
`no_semantics.py` strips them: an earlier version grepped the raw file, so
the comment explaining "never localStorage" tripped the check that exists
to enforce it, and the only way to pass was to write around the name. A
guard that forces bad prose is a guard someone eventually deletes.
"""

import pathlib
import re
import sys

SOURCE = pathlib.Path(__file__).parent.parent / "playground.js"

# Persisting a key is one XSS away from it being someone else's.
FORBIDDEN_SINKS = [
    "localStorage",
    "sessionStorage",
    "indexedDB",
    "document.cookie",
    "history.pushState",
    "history.replaceState",
]

ALLOWED_HOST = "api.anthropic.com"


def strip_comments(js: str) -> str:
    js = re.sub(r"/\*.*?\*/", "", js, flags=re.S)
    js = re.sub(r"^\s*//.*$", "", js, flags=re.M)
    return re.sub(r"(?<![:/])//.*$", "", js, flags=re.M)


def main() -> int:
    code = strip_comments(SOURCE.read_text())
    failures = []

    for sink in FORBIDDEN_SINKS:
        if re.search(rf"\b{re.escape(sink)}\b", code):
            failures.append(f"the key could be persisted via {sink}")

    # Every absolute URL the file fetches must be Anthropic's.
    for url in re.findall(r"""fetch\(\s*["'`](https?://[^"'`]+)""", code):
        if ALLOWED_HOST not in url:
            failures.append(f"sends a request to {url}, not {ALLOWED_HOST}")

    # The header without which a browser cannot call the API at all.
    if "anthropic-dangerous-direct-browser-access" not in code:
        failures.append(
            "missing the anthropic-dangerous-direct-browser-access header — "
            "the request will fail CORS"
        )

    if failures:
        print("key handling is unsafe:")
        for failure in failures:
            print("  -", failure)
        return 1

    print("key is memory-only, and goes to exactly one host")
    return 0


if __name__ == "__main__":
    sys.exit(main())
