/* The cascade, in a canvas — the browser backend of the same display the
   Tk window implements.

   Every decision here mirrors src/matrixlang/cascade.py rather than being
   invented again: one reserved column per falling line, source faster,
   output slower and brighter, characters read top-to-bottom, and the
   program's own material looping forever once it has all fallen. Nothing
   random is generated; every glyph on screen came from the program.

   The two bugs that field found the hard way are avoided by construction
   here too: a column is reserved for a stream's whole life (sharing one
   corrupts a line of your program), and character 0 sits highest so a
   column reads downward in natural order (the obvious layout renders
   every line backwards). */

/* Halved from the original pair, which crossed the field in well under a
   second and read as a wipe rather than as rain. */
const SPEED = { source: 0.45, output: 0.22 };

/* Every stream draws its own multiplier. Without it the field held
   exactly two speeds, so every source line sat on the identical row as
   every other one and the whole thing read as a block of plain text
   sliding down. The range is chosen so the source and output bands do not
   overlap: "output falls slower than source" stays a guarantee. */
const JITTER = [0.7, 1.3];

/* How many lines may start falling on one frame. Releasing every queued
   line at once was the other half of the lockstep. */
const SPAWNS_PER_FRAME = 2;

/* A fixed ramp, not a fraction of the line: scaling it to the line meant
   a 3-glyph line faded over 3 cells and a 20-glyph line over 20, so the
   head falloff depended on the content. FLOOR keeps the oldest glyphs
   readable, because the cascade is carrying the program. */
const TRAIL = 6;
const FLOOR = 0.28;

/* The simulation's tick, in milliseconds. requestAnimationFrame fires at
   the display's refresh rate, so stepping once per callback ran the
   cascade at 60 rows/second on a 60Hz panel and 108 on a 120Hz one —
   twice the Tk window's speed, and different on different machines.
   Accumulating real time and stepping at a fixed rate makes the two
   backends agree and makes the speed a property of the design rather
   than of the monitor. */
const TICK_MS = 33;

/* Two screens' worth, matching cascade.MAX_HISTORY. The server's stream is
   faithful — one statement event per executed statement — so a recursive
   or runaway program sends thousands of frames. The display can never show
   more than this, and OP-D deliberately left the throttling to whoever has
   to render it. This is that. */
const MAX_HISTORY = 200;

const CELL_W = 12;
const CELL_H = 17;

class Stream {
  constructor(col, text, kind, speed) {
    this.col = col;
    this.text = text;
    this.kind = kind;
    this.speed = speed;
    this.head = -1;
  }

  advance() { this.head += this.speed; }

  /* Character 0 highest, last character leading the fall, so reading the
     column downward gives the line in natural order. */
  cells(rows) {
    const head = Math.floor(this.head);
    const out = [];
    for (let i = 0; i < this.text.length; i++) {
      const offset = this.text.length - 1 - i;
      const row = head - offset;
      if (row >= 0 && row < rows) {
        out.push({
          row,
          col: this.col,
          glyph: this.text[i],
          level: Math.max(FLOOR, 1 - offset / TRAIL),
          kind: this.kind,
        });
      }
    }
    return out;
  }

  finished(rows) {
    return Math.floor(this.head) - (this.text.length - 1) >= rows;
  }
}

export class Cascade {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext("2d");
    this.streams = [];
    this.waiting = [];
    this.history = [];
    this.cols = 0;
    this.rows = 0;

    this.carry = 0;
    this.last = performance.now();

    new ResizeObserver(() => this.resize()).observe(canvas);
    this.resize();
    requestAnimationFrame((now) => this.frame(now));
  }

  resize() {
    const ratio = window.devicePixelRatio || 1;
    const rect = this.canvas.getBoundingClientRect();
    this.canvas.width = Math.max(1, Math.floor(rect.width * ratio));
    this.canvas.height = Math.max(1, Math.floor(rect.height * ratio));
    this.ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    this.cols = Math.max(1, Math.floor(rect.width / CELL_W));
    this.rows = Math.max(1, Math.floor(rect.height / CELL_H));
  }

  add(text, kind) {
    if (!text) return;
    this.waiting.push({ text, kind });
    this.history.push({ text, kind });
    if (this.history.length > MAX_HISTORY) {
      this.history.splice(0, this.history.length - MAX_HISTORY);
    }
  }

  clear() {
    this.streams = [];
    this.waiting = [];
    this.history = [];
  }

  /* Order matters and the obvious order is wrong: retiring before moving
     uses last frame's positions, so the frame on which a stream leaves the
     screen draws nothing and blanks for one frame. Move, retire on what
     just happened, then refill. */
  step() {
    for (const s of this.streams) s.advance();
    this.streams = this.streams.filter((s) => !s.finished(this.rows));

    if (!this.streams.length && !this.waiting.length && this.history.length) {
      this.waiting.push(...this.history);
    }

    const taken = new Set(this.streams.map((s) => s.col));
    const free = [];
    for (let c = 0; c < this.cols; c++) if (!taken.has(c)) free.push(c);
    shuffle(free);
    let started = 0;
    while (this.waiting.length && free.length && started < SPAWNS_PER_FRAME) {
      started += 1;
      const { text, kind } = this.waiting.shift();
      const speed = SPEED[kind] * (JITTER[0] + Math.random() * (JITTER[1] - JITTER[0]));
      const stream = new Stream(free.pop(), text, kind, speed);
      // New streams advance immediately, or they contribute nothing to the
      // frame that created them and the blank frame comes back.
      stream.advance();
      this.streams.push(stream);
    }

    return this.streams.flatMap((s) => s.cells(this.rows));
  }

  frame(now) {
    /* Fixed timestep. Catch up at most a few ticks so a backgrounded tab
       does not fast-forward the whole program when it returns. */
    this.carry += Math.min(now - this.last, TICK_MS * 4);
    this.last = now;
    while (this.carry >= TICK_MS) {
      this.carry -= TICK_MS;
      this.cells = this.step();
    }

    const cells = this.cells || [];
    const { ctx } = this;
    const rect = this.canvas.getBoundingClientRect();
    ctx.fillStyle = "#000";
    ctx.fillRect(0, 0, rect.width, rect.height);
    ctx.font = `13px ${getComputedStyle(document.body).fontFamily}`;
    ctx.textBaseline = "top";
    for (const cell of cells) {
      ctx.fillStyle = colour(cell);
      ctx.fillText(cell.glyph, cell.col * CELL_W, cell.row * CELL_H);
    }
    requestAnimationFrame((next) => this.frame(next));
  }
}

/* Output is brighter and white-headed so a value stands out from the
   source scrolling past it. */
function colour(cell) {
  if (cell.kind === "output") {
    if (cell.level > 0.95) return "#ffffff";
    if (cell.level > 0.4) return "#ccffcc";
    return "#2a8f3f";
  }
  if (cell.level > 0.95) return "#ccffcc";
  if (cell.level > 0.4) return "#00ff41";
  return "#0d7a2a";
}

function shuffle(list) {
  for (let i = list.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [list[i], list[j]] = [list[j], list[i]];
  }
}
