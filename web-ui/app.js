/* Operator, in a browser. Talks only to the server that served this page.

   No framework, no build step, no CDN — the same reason the server is
   stdlib only. Everything here is wiring: post a request, post a program,
   read the event stream, hand the events to the cascade. Nothing about
   the language is implemented here, which is the lesson of the deleted
   web/interpreter.js: a second implementation drifts from the first. */

import { Cascade } from "/cascade.js";

const el = (id) => document.getElementById(id);

const source = el("source");
const chat = el("chat");
const cascade = new Cascade(el("cascade"));

/* Which face the falling source is drawn in. The server sends both — the
   browser never untransliterates, because owning a copy of the table is
   how the old web layer drifted. */
let face = "source";
let stream = null;

// ---- running -------------------------------------------------------------

async function run() {
  const text = source.value;
  if (!text.trim()) return;

  if (stream) stream.close();
  cascade.clear();
  status("program-status", "running…");
  status("cascade-status", "running");

  let started;
  try {
    started = await post("/api/run", { source: text });
  } catch (error) {
    status("program-status", String(error), "bad");
    return;
  }

  stream = new EventSource(`/api/events?run=${encodeURIComponent(started.run)}`);
  let outputs = 0;

  stream.onmessage = (message) => {
    const event = JSON.parse(message.data);
    if (event.kind === "statement") {
      cascade.add(event[face], "source");
    } else if (event.kind === "output") {
      outputs += 1;
      cascade.add(event.glyphs, "output");
      status("cascade-status", `${outputs} output line${outputs === 1 ? "" : "s"}`);
    } else if (event.kind === "error") {
      // Diagnostics are never transliterated. An error is the moment a
      // reader's fluency has failed, and glyphs are the worst possible
      // response to that — so it goes in the status strip as plain text.
      status("program-status", event.message, "bad");
    } else if (event.kind === "done") {
      stream.close();
      stream = null;
      if (!el("program-status").classList.contains("bad")) {
        status("program-status", "finished", "good");
      }
      status("cascade-status", `${outputs} output lines · looping`);
    }
  };

  stream.onerror = () => {
    if (stream) { stream.close(); stream = null; }
    status("program-status", "the connection to the server dropped", "bad");
  };
}

// ---- asking --------------------------------------------------------------

async function ask(request) {
  say("you", escape(request));
  el("operator-state").textContent = "thinking";
  el("operator-state").classList.add("busy");

  let reply;
  try {
    reply = await post("/api/chat", { request, engine: el("engine").value });
  } catch (error) {
    say("operator", escape(String(error)));
    idle();
    return;
  }

  // The retry loop, shown rather than hidden. It is the most important
  // decision in this design — Operator never gets to declare its own
  // output valid — and concealing it would waste that.
  for (const attempt of reply.attempts || []) {
    if (attempt.diagnostic) {
      say(
        null,
        `<div class="attempt"><b>attempt ${attempt.number} rejected</b> — ` +
          `${escape(attempt.diagnostic)}</div>`,
        true,
      );
    }
  }

  if (reply.ok) {
    source.value = reply.source;
    say("operator", `<span class="ok">parsed ✓</span> — running it.`, true);
    idle();
    run();
  } else {
    // Escape ONCE, at the end. Hints contain angle brackets ("add <a> and
    // <b>"), so escaping the hint and then escaping the whole message again
    // renders a literal "&lt;a&gt;" in the panel.
    let message = reply.error || "no program";
    if (reply.hint) {
      message += ` — try: ${reply.hint}`;
    }
    if (reply.try_operator) {
      message += " (or switch the engine to Operator)";
    }
    say("operator", escape(message));
    idle();
  }
}

function idle() {
  el("operator-state").textContent = "idle";
  el("operator-state").classList.remove("busy");
}

// ---- plumbing ------------------------------------------------------------

async function post(path, body) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error || `HTTP ${response.status}`);
  return payload;
}

function say(who, html, raw = false) {
  const node = document.createElement("div");
  if (who === null) {
    node.innerHTML = html;
  } else {
    node.className = `msg ${who === "you" ? "you" : "op"}`;
    node.innerHTML = `<div class="who">${who}</div><div class="body">${html}</div>`;
  }
  chat.append(node);
  chat.scrollTop = chat.scrollHeight;
  return node;
}

function status(id, text, kind) {
  const node = el(id);
  node.textContent = text;
  node.classList.remove("bad", "good");
  if (kind) node.classList.add(kind);
}

/* Everything from the server is text, and some of it is a model's output.
   It goes through here before it reaches innerHTML. */
function escape(text) {
  const node = document.createElement("div");
  node.textContent = text;
  return node.innerHTML;
}

// ---- wiring --------------------------------------------------------------

el("run").addEventListener("click", run);

el("ask").addEventListener("submit", (event) => {
  event.preventDefault();
  const input = el("request");
  const request = input.value.trim();
  if (!request) return;
  input.value = "";
  ask(request);
});

for (const [id, value] of [["face-glyph", "source"], ["face-latin", "latin"]]) {
  el(id).addEventListener("click", () => {
    face = value;
    el("face-glyph").classList.toggle("on", value === "source");
    el("face-latin").classList.toggle("on", value === "latin");
  });
}

run();
