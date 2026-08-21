"""What Operator is told, and nothing about how it is asked.

Pure: no network, no SDK, no key. Splitting this from `client.py` is what
makes the interesting half testable — the instructions a model receives
are as much a part of this system's behaviour as any function in it, and
they should not only be observable by paying for an API call.

The keyword list is read from `tokens.KEYWORDS` rather than retyped. That
is a deliberate deviation from the design's module table, which said this
module imports nothing: a hardcoded grammar is exactly how the deleted
`web/interpreter.js` drifted from the language it claimed to implement,
and a prompt that lies about the grammar is worse than one that is merely
stale. Importing pure data costs nothing and cannot drift.
"""

from matrixlang.operator.validate import Invalid, Stage
from matrixlang.tokens import KEYWORDS

_ROLE = """\
You are Operator. You write programs in MatrixLang, a small language with
a full grammar and no standard library. Reply with source code only — no
prose, no explanation, no code fences."""

_EXAMPLE = """\
construct n = 3
dejavu n > 0
  trace n
  n = n - 1
flatline

agent double(x)
  jackout x * 2
flatline

trace double(21)

construct xs = [1, 2, 3]
xs[0] = xs[0] + 1
trace xs[0]
trace length xs

construct name = "Neo"
trace name < "Trinity"
trace name[0]

construct crew = ["Neo", "Trinity", "Tank"]
construct i = 0
dejavu i < length crew splice crew[i] != "Trinity"
  i = i + 1
flatline
redpill unplug (i == length crew)
  trace i
flatline"""

# The ways MatrixLang differs from what a model assumes by default. Each
# line here exists because getting it wrong produces a candidate that
# looks plausible and fails.
_RULES = """\
Rules that differ from most languages:
- Blocks are opened by a keyword and closed by `flatline`. A block is
  never wrapped in braces, never introduced by a colon, and indentation is
  never significant. Braces and colons are real punctuation, but only
  inside a dictionary literal.
- `construct` declares a name. Plain `=` assigns and requires the name to
  have been declared already. Re-declaring in the same scope is an error.
- Conditions must be a boolean. `redpill 1` is an error, not a taken
  branch. There is no truthiness. `redpill` may be followed by an
  optional `bluepill` block, which runs when the condition is false —
  MatrixLang's else.
- Types are integer, boolean, string, list and dictionary. No floats, no
  null.
- A list literal is `[a, b, c]`. Read an element with `xs[i]`, write one
  with `xs[i] = v`, and measure one with `length xs` (also works on a
  string, and on a dictionary, where it gives the number of entries).
  Indexing is 0-based and out of range is an error.
- A string can be indexed too: `s[i]` reads a one-character string. It
  cannot be written — `s[i] = v` is an error, because a string can never
  change once made. Build a different one with `+` instead.
- A dictionary literal is `{"a": 1}`; keys must be strings or numbers.
  Reading a key that is not there is an error, so check first with
  `oracle`, which is infix and gives a boolean: `d oracle "a"`.
  `keymaker` takes a dictionary and gives the list of its keys, in
  insertion order.
- `<`, `>`, `<=`, `>=` order two integers or two strings — never a mix,
  and never any other type.
- `+` adds integers, joins strings, or concatenates lists — never a mix
  of different types.
- Integer division truncates toward zero.
- `agent` defines; `jackout` returns. An agent that never jacks out
  produces nothing, and using that nothing as a value is an error.
- The only way to produce output is `trace`. To read input, use `jackin`,
  which reads a line of text, and `decode`, which converts that text to a
  number (or fails). The inverse, `encode`, converts a number to text,
  and takes only a number — text is already text and is refused.
- `splice` is and, `fork` is or, `unplug` is not. Operands must be
  boolean — `1 splice true` is an error, the same rule that makes
  `redpill 1` an error. `splice` and `fork` short-circuit: the right
  side of `a splice b` runs only if `a` is true, and the right side of
  `a fork b` runs only if `a` is false, so a side that is never
  evaluated is never type-checked (`false splice 1` is `false`, but
  `true splice 1` is an error). `unplug` binds looser than comparison,
  so `unplug n == 1` means `unplug (n == 1)`, not `(unplug n) == 1`."""


def _keywords() -> str:
    return ", ".join(sorted(KEYWORDS))


def build(
    request: str,
    previous: str | None = None,
    failure: Invalid | None = None,
) -> str:
    """The full context for one attempt.

    `previous` and `failure` turn it into a retry. The diagnostic goes in
    verbatim: it is the real one from the real parser, and softening it
    would hide the exact thing that has to change.
    """
    parts = [
        _ROLE,
        f"Keywords: {_keywords()}.",
        _RULES,
        "A complete example:\n\n" + _EXAMPLE,
        f"Write a MatrixLang program that does this:\n\n{request}",
    ]

    if previous is not None and failure is not None:
        parts.append(
            "Your previous attempt was rejected.\n\n"
            f"{previous.rstrip()}\n\n"
            f"{_explain(failure)}\n"
            f"{failure.as_diagnostic()}\n\n"
            "Fix that specific problem and reply with the whole program again."
        )
    return "\n\n".join(parts)


def _explain(failure: Invalid) -> str:
    """Name the stage, so a retry is informed rather than merely repeated.

    A model told only "that was wrong" will often return the same syntax.
    Knowing the program parsed and then failed is what redirects it.
    """
    if failure.stage is Stage.PARSE:
        return "It did not parse:"
    if failure.stage is Stage.RUN:
        return "It parsed, but failed while running:"
    return "It parsed, but did not finish — it may contain an endless loop:"
