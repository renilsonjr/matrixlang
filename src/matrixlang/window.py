"""The Tk backend: the only module in the package that owns a window.

Everything that decides what a viewer sees lives in `cascade.py`, which is
pure and seeded. What is left here is the part that cannot be pure — a
toolkit, a clock, and a thread boundary — and it is kept as small as the
job allows.

Two decisions carry the design.

**Tk is not thread-safe.** The interpreter runs on a worker thread and may
emit an event at any moment; touching a widget from there corrupts or
crashes Tk. So `emit` only puts the event on a queue, and the UI thread
drains it under `after()`. `emit` is the method the interpreter calls, and
it deliberately does nothing else.

**The window outlives the program.** A program that finishes in 200 ms
would otherwise flash and vanish with its output unread, which would make
the output device useless for exactly the programs most people write
first. Execution ending drains the cascade; the window closes when the
viewer closes it.

`tkinter` is imported inside `open()`, never at module scope: a top-level
import would make the whole package fail on a machine without Tk, turning
a missing window into a missing language.
"""

import queue
from random import Random

from matrixlang.cascade import CascadeField, Cell, Kind
from matrixlang.display import Backend  # noqa: F401  (re-exported for callers)
from matrixlang.events import Error, Event

FRAME_MS = 33  # ~30fps

# A cell grid, not pixels. The canvas is sized from these.
CELL_WIDTH = 12
CELL_HEIGHT = 18

_HEAD = "#ccffcc"
_BODY = "#00ff41"
_DIM = "#004411"
_BACKGROUND = "#000000"


def drain(q: "queue.Queue[Event]", field: CascadeField, errors: list[str]) -> None:
    """Move every queued event into the field, or into the status strip.

    `Error` never reaches the cascade. A transliterated diagnostic hides
    the line number, the misspelled name and the remedy at once, and it
    breaks D-03's guarantee that the only Latin text in a wall of green is
    the thing you need to find.
    """
    while True:
        try:
            event = q.get_nowait()
        except queue.Empty:
            return
        if isinstance(event, Error):
            errors.append(event.message)
        else:
            field.consume(event)


class CascadeWindow:
    """A `Display` that draws the cascade in a native window."""

    def __init__(
        self, width: int = 80, height: int = 30, rng: Random | None = None
    ) -> None:
        self._queue: queue.Queue[Event] = queue.Queue()
        self._field = CascadeField(width, height, rng or Random())
        self._errors: list[str] = []
        self._width = width
        self._height = height
        self._root = None
        self._canvas = None
        self._status = None
        self._closed = False

    # --- Display protocol ------------------------------------------------

    def open(self) -> None:
        import tkinter

        self._root = tkinter.Tk()
        self._root.title("MatrixLang")
        self._root.configure(bg=_BACKGROUND)
        self._canvas = tkinter.Canvas(
            self._root,
            width=self._width * CELL_WIDTH,
            height=self._height * CELL_HEIGHT,
            bg=_BACKGROUND,
            highlightthickness=0,
        )
        self._canvas.pack()
        self._status = tkinter.Label(
            self._root,
            text="",
            anchor="w",
            fg="#ffffff",
            bg="#111111",
            font=("Menlo", 11),
        )
        self._status.pack(fill="x")
        self._root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Raise it. A Tk process launched from a terminal on macOS opens
        # behind the frontmost application, so a window that is mapped and
        # viewable is still, from the operator's side, nothing happening.
        # The topmost flag is toggled rather than left on: a window that
        # will not go behind anything is worse than one that opens behind.
        # Done with Tk alone — §6 records that this package spawns no
        # processes, and an osascript activation would break that.
        self._root.lift()
        self._root.attributes("-topmost", True)
        self._root.after_idle(self._root.attributes, "-topmost", False)

        self._root.after(FRAME_MS, self._tick)

    def emit(self, event: Event) -> None:
        """Called from the interpreter's thread. Queue only — never a widget."""
        self._queue.put(event)

    def step(self) -> tuple:
        """Advance one frame and return the cells to draw.

        Split out of `_tick` so the frame stream is testable without Tk —
        which is how the settling defect below was caught, and how it stays
        caught.

        Once execution has ended and everything has fallen, the output
        **settles**: it stops moving and stays on screen. Draining to black
        made "the window outlives the program" meaningless, because the
        thing worth outliving it is the output, not the frame.
        """
        drain(self._queue, self._field, self._errors)
        if self._closed and self._field.is_empty():
            return self._settled()
        cells = self._field.advance()
        # The frame that retires the last stream draws nothing, and the
        # settled view only takes over on the frame after. Handing over
        # here instead keeps the screen from blanking in between.
        if not cells and self._closed:
            return self._settled()
        return cells

    def _settled(self) -> tuple:
        """The transcript at rest: one output line per row, static."""
        cells = []
        for row, text in enumerate(self._field.transcript()[: self._height]):
            for col, glyph in enumerate(text[: self._width]):
                cells.append(
                    Cell(row=row, col=col, glyph=glyph, level=1.0, kind=Kind.OUTPUT)
                )
        return tuple(cells)

    def close(self) -> None:
        """Signal that execution is over. The window itself stays open.

        Safe before `open()` and safe twice: the CLI calls it in a finally,
        and a window that failed to open must not turn into a failed
        program.
        """
        self._closed = True

    # --- for tests -------------------------------------------------------

    def pending(self) -> int:
        return self._queue.qsize()

    # --- the UI thread ---------------------------------------------------

    def _tick(self) -> None:
        if self._root is None:
            return
        self._draw(self.step())
        if self._errors and self._status is not None:
            self._status.configure(text=self._errors[-1])
        self._root.after(FRAME_MS, self._tick)

    def _draw(self, cells) -> None:
        canvas = self._canvas
        if canvas is None:
            return
        canvas.delete("all")
        for cell in cells:
            canvas.create_text(
                cell.col * CELL_WIDTH + CELL_WIDTH // 2,
                cell.row * CELL_HEIGHT + CELL_HEIGHT // 2,
                text=cell.glyph,
                fill=_colour(cell.level),
                font=("Menlo", 13),
            )

    def _on_close(self) -> None:
        if self._root is not None:
            self._root.destroy()
            self._root = None

    def mainloop(self) -> None:
        """Hand control to Tk. Returns when the viewer closes the window."""
        if self._root is not None:
            self._root.mainloop()


def _colour(level: float) -> str:
    if level > 0.95:
        return _HEAD
    if level > 0.4:
        return _BODY
    return _DIM
