"""Generate, validate, retry — the cycle that makes Operator's output safe.

Operator is never the authority on whether its own output is valid
MatrixLang. The parser is. This module is the thin orchestration between
the two, and it is deliberately separate from `client.py` so that the
interesting half can be tested with a stub and no API key.

Three attempts, then stop (OP-4). Looping until success sounds generous
and is not: a model that cannot satisfy a request will not start to on
the fourth try, and every attempt is a paid call.
"""

from dataclasses import dataclass, field

from matrixlang.nodes import Program
from matrixlang.operator.prompt import build
from matrixlang.operator.validate import DRY_RUN_MAX_STEPS, Invalid, Stage, Valid, check

MAX_ATTEMPTS = 3


@dataclass(frozen=True)
class Attempt:
    """One generate-and-validate round. Recorded whether it passed or not.

    Kept even on success because every attempt is a paid API call, and a
    session that quietly took three tries should be visible before anyone
    builds a spend cap on top of it.
    """

    number: int
    source: str
    failure: Invalid | None


@dataclass(frozen=True)
class Outcome:
    attempts: list[Attempt] = field(default_factory=list)
    program: Program | None = None
    source: str | None = None
    failure: Invalid | None = None

    @property
    def succeeded(self) -> bool:
        return self.program is not None

    @property
    def calls(self) -> int:
        return len(self.attempts)


def run(
    request: str,
    client,
    max_attempts: int = MAX_ATTEMPTS,
    max_steps: int = DRY_RUN_MAX_STEPS,
) -> Outcome:
    """Ask, check, and ask again with the diagnostic. Never raises.

    A failure anywhere — a refusal, a dead network, a model that returns
    an empty string — becomes an `Invalid` on the outcome rather than an
    exception. The caller is a server handling a chat message; it needs a
    result to show, not a traceback.
    """
    attempts: list[Attempt] = []
    previous: str | None = None
    failure: Invalid | None = None

    for number in range(1, max_attempts + 1):
        context = build(request, previous=previous, failure=failure)
        try:
            candidate = _unfence(client.generate(context))
        except Exception as error:
            # The client is the only impure thing here, and it can fail in
            # ways this loop cannot enumerate — network, auth, a refusal.
            failure = Invalid(Stage.RUN, str(error), 0, 0)
            attempts.append(Attempt(number, "", failure))
            previous = None
            continue

        if not candidate.strip():
            # An empty program is *valid* MatrixLang — zero statements
            # parse and run fine — so validate.check accepts it, correctly.
            # It is still not an answer to a request, and that judgement
            # belongs here rather than in the parser's ground truth.
            failure = Invalid(Stage.RUN, "the reply contained no program", 0, 0)
            attempts.append(Attempt(number, candidate, failure))
            previous = None
            continue

        result = check(candidate, max_steps=max_steps)
        if isinstance(result, Valid):
            attempts.append(Attempt(number, candidate, None))
            return Outcome(attempts, result.program, candidate, None)

        failure = result
        previous = candidate
        attempts.append(Attempt(number, candidate, failure))

    return Outcome(attempts, None, None, failure)


def _unfence(reply: str) -> str:
    """Strip a Markdown code fence if the model added one.

    The prompt says to reply with source only, and models wrap it in
    fences anyway. Failing on that would burn a paid retry on a formatting
    habit rather than on anything about the program.
    """
    text = reply.strip()
    if not text.startswith("```"):
        return reply
    lines = text.splitlines()
    if lines and lines[0].startswith("```"):
        lines = lines[1:]
    if lines and lines[-1].strip() == "```":
        lines = lines[:-1]
    return "\n".join(lines) + "\n"
