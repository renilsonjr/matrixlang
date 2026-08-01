"""Executing a program and handing its events to an HTTP response.

The same shape `window.py` uses: the interpreter runs on a worker thread
and pushes events into a `queue.Queue`; the consumer drains it. There the
consumer was Tk's `after()` loop, here it is an SSE response — which is
the argument for SSE over a framework in one sentence, since the pattern
ports rather than being redesigned.

Two independent guards, because they catch different things:

* the **step limit** (OP-A) bounds work *inside* the interpreter, and is
  deterministic — a test asserts the exact boundary;
* the **deadline** here bounds the *request*, and catches anything the
  step counter cannot see. Neither substitutes for the other.

**Known limit.** The stream is faithful: one statement event per executed
statement. A runaway program therefore emits thousands of frames before
either guard trips, and the cascade can only ever display 200 lines of
them. Throttling belongs with the client that has to render it (OP-E),
not here — this module's job is to report what actually executed.
"""

import json
import queue
import threading
import time
import uuid

from matrixlang.errors import MatrixLangError, recursion_guard
from matrixlang.events import Error, Event, Output, Statement
from matrixlang.interpreter import Interpreter
from matrixlang.lexer import lex
from matrixlang.operator.validate import DRY_RUN_MAX_STEPS
from matrixlang.parser import parse

# Generous for anything a person runs interactively, short enough that a
# wedged request cannot hold a connection open indefinitely.
DEADLINE_SECONDS = 30.0

_DONE = {"kind": "done"}


class Run:
    """One execution, and the queue its events arrive on."""

    def __init__(self, run_id: str) -> None:
        self.id = run_id
        self._queue: "queue.Queue[dict]" = queue.Queue()
        self._finished = False

    # --- producer side ---------------------------------------------------

    def emit(self, event: Event) -> None:
        """Called from the interpreter's thread. Queue only."""
        if isinstance(event, Output):
            self._queue.put({"kind": "output", "text": event.text, "line": event.line})
        elif isinstance(event, Statement):
            self._queue.put(
                {"kind": "statement", "line": event.line, "node": event.node}
            )
        elif isinstance(event, Error):
            self._queue.put({"kind": "error", "message": event.message})

    def fail(self, message: str) -> None:
        self._queue.put({"kind": "error", "message": message})

    def finish(self) -> None:
        self._queue.put(dict(_DONE))

    # --- consumer side ---------------------------------------------------

    def next(self, timeout: float = 1.0) -> dict:
        """The next event, or `done` once the run has ended.

        A finished run keeps answering `done` rather than blocking: a
        client that reconnects after the end should be told so, not left
        holding a socket open until the timeout.
        """
        if self._finished:
            return dict(_DONE)
        try:
            event = self._queue.get(timeout=timeout)
        except queue.Empty:
            return dict(_DONE)
        if event["kind"] in ("done", "error"):
            self._finished = True
        return event


class Runs:
    """Every run this process knows about, by id."""

    def __init__(
        self,
        deadline: float = DEADLINE_SECONDS,
        max_steps: int = DRY_RUN_MAX_STEPS,
    ) -> None:
        self._runs: dict[str, Run] = {}
        self._deadline = deadline
        self._max_steps = max_steps

    def get(self, run_id: str) -> Run | None:
        return self._runs.get(run_id)

    def start(self, source: str) -> Run:
        run = Run(uuid.uuid4().hex)
        self._runs[run.id] = run

        # Parsed on this thread, before any worker exists: a program that
        # cannot parse should report that immediately rather than through
        # a stream the client has to open first.
        try:
            with recursion_guard():
                program = parse(lex(source))
        except MatrixLangError as error:
            run.fail(str(error))
            return run

        threading.Thread(target=self._execute, args=(run, program), daemon=True).start()
        return run

    def _execute(self, run: Run, program) -> None:
        deadline = time.monotonic() + self._deadline

        class Guarded:
            """Emits to the run, and trips the wall clock from inside the loop.

            Checking the clock where events are already flowing means the
            deadline is enforced without a second thread watching a first
            one — the same reason the step counter lives in `_execute`.
            """

            def emit(self, event: Event) -> None:
                if time.monotonic() > deadline:
                    raise TimeoutError
                run.emit(event)

        try:
            Interpreter(sink=Guarded(), max_steps=self._max_steps).run(program)
        except TimeoutError:
            run.fail("the program took too long and was stopped")
        except MatrixLangError as error:
            run.fail(str(error))
        except Exception as error:  # pragma: no cover - belt and braces
            run.fail(f"unexpected failure: {error}")
        else:
            run.finish()
