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
- Types are number, boolean, string, list and dictionary. A number is
  exact decimal, not floating point -- `2.5`, `-7`, and `0.001` are all
  the same type, with no separate integer type. No null.
- A list literal is `[a, b, c]`. Read an element with `xs[i]`, write one
  with `xs[i] = v`, and measure one with `length xs` (also works on a
  string, and on a dictionary, where it gives the number of entries).
  Indexing is 0-based and out of range is an error.
- A string can be indexed too: `s[i]` reads a one-character string. It
  cannot be written — `s[i] = v` is an error, because a string can never
  change once made. Build a different one with `+` instead.
- Three string operations. `fold s` lower-cases, `trim s` removes
  whitespace from both ends, and the infix `s cleave sep` splits on a
  separator and gives a list — `"a,b" cleave ","` is `["a", "b"]`. All
  three take strings and nothing else. There is no upper-casing
  operator: to compare two strings ignoring case, `fold` both sides. A
  separator with nothing in it is an error, not a character-by-character
  split.
- A dictionary literal is `{"a": 1}`; keys must be strings or numbers.
  Reading a key that is not there is an error, so check first with
  `oracle`. `keymaker` takes a dictionary and gives the list of its keys,
  in insertion order.
- `oracle` is infix and gives a boolean: it asks whether a container holds
  something. `d oracle "a"` asks a dictionary for a key, `xs oracle 3` asks
  a list whether it holds that element, and `s oracle "ab"` asks a string
  whether that text appears in it. An element a list cannot compare is
  simply not a match, so `["a"] oracle 1` is false rather than an error —
  but the right side of a string `oracle` must itself be a string;
  `"matrix" oracle 1` is an error, not false.
- `<`, `>`, `<=`, `>=` order two numbers or two strings — never a mix,
  and never any other type.
- `+` adds numbers, joins strings, or concatenates lists — never a mix
  of different types.
- `/` is true division: `7 / 2` is `3.5`, not `3`. `%` is the remainder:
  `7 % 2` is 1. It follows the sign of the right operand, as Python does,
  so `-7 % 2` is 1 rather than -1. Even and odd are `n % 2 == 0` and
  `n % 2 != 0`.
- An index (`xs[i]`) must be a whole number — `2` and `2.0` both work,
  `2.5` is an error — even though `/` can produce one.
- `agent` defines; `jackout` returns. An agent that never jacks out
  produces nothing, and using that nothing as a value is an error.
- The only way to produce output is `trace`. To read input, use `jackin`,
  which reads a line of text, and `decode`, which converts that text to a
  number (or fails). `encode` is `decode`'s counterpart, not its exact
  mirror: it gives the text form of any value — the same text `trace`
  would print — not just a number.
- `splice` is and, `fork` is or, `unplug` is not. Operands must be
  boolean — `1 splice true` is an error, the same rule that makes
  `redpill 1` an error. `splice` and `fork` short-circuit: the right
  side of `a splice b` runs only if `a` is true, and the right side of
  `a fork b` runs only if `a` is false, so a side that is never
  evaluated is never type-checked (`false splice 1` is `false`, but
  `true splice 1` is an error). `unplug` binds looser than comparison,
  so `unplug n == 1` means `unplug (n == 1)`, not `(unplug n) == 1`.
  - Bitwise operators work on integers only: `mask` is &, `merge` is |,
    `flip` is ^, and `invert` is ~. `uplink` and `downlink` shift left
    and right; their shift count must not be negative."""
- `wake` leaves the innermost `dejavu` immediately; `glitch` skips to that
  loop's next iteration. Both are bare keywords on their own line, like a
  bare `jackout`, and both are an error outside a loop. A `jackout` inside
  a loop still returns from the agent — it is not stopped by the loop."""


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
