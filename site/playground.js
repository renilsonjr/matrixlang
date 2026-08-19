// site/playground.js
// The playground's JavaScript half. It boots Pyodide, hands requests to
// site/glue.py, and draws what comes back.
//
// It deliberately owns no language logic: it never lexes, parses,
// transliterates, or builds a message shape. Every glyph it draws arrived
// already rendered from Python. That rule is what the deleted web/ layer
// broke, and TECHNICAL-OVERVIEW §5.7 is why it is stated here too.

const WHEEL = "matrixlang-0.6.0-py3-none-any.whl";

let pyodide = null;
let glue = null;
let cascade = null;
let face = "glyph"; // "glyph" | "latin" — the cascade's face for both source and output

const el = (id) => document.getElementById(id);

const BOOT_LABEL = "Load the interpreter and try it";
const BOOT_BUTTON_IDS = ["boot", "translit-boot"];
// Every control that is dead until Pyodide has booted successfully. A failed
// boot disables all of these; a successful one — first try or a retry after
// a failure — has to re-enable all of them, or a fail-then-retry-then-succeed
// reader is left with a page that looks alive but has dead buttons on it.
const GATED_CONTROL_IDS = [
  "write", "run", "ask-operator", "editor-face", "cascade-face",
  "translit-latin", "translit-glyphs", "program-input",
];

async function boot() {
  const buttons = BOOT_BUTTON_IDS.map(el);
  for (const button of buttons) {
    button.disabled = true;
    button.textContent = "Loading Python… (a few MB, once)";
  }
  try {
    await load();
  } catch (error) {
    // Without this the rejection surfaces only as "Uncaught (in promise)"
    // in a console the reader is not looking at, and the buttons sit on
    // "Loading Python…" forever. A CDN that is blocked, an offline tab,
    // and a wheel that failed to publish all look like that. The narrative
    // above is unaffected — that is the point of loading none of this
    // until asked.
    for (const button of buttons) {
      button.disabled = false;
      button.textContent = BOOT_LABEL;
    }
    const miss = el("miss");
    miss.textContent =
      `The interpreter could not load: ${error.message}. ` +
      "Everything above still reads without it, and the examples were run " +
      "before the page shipped. You can also clone the repository and run " +
      "the same interpreter locally.";
    miss.hidden = false;
    // `#miss` lives inside `#live`, so saying anything at all means
    // revealing that block — which would also expose an editor and a Run
    // button wired to a `glue` and a `cascade` that are still null.
    // Showing the controls dead is worse than not showing them, so they
    // are disabled rather than merely present.
    el("live").hidden = false;
    for (const id of GATED_CONTROL_IDS) {
      const control = el(id);
      if (control) control.disabled = true;
    }
    return;
  }
  for (const button of buttons) button.hidden = true;
  finishBoot();
}

// Runs once load() has resolved, whether this is the first attempt or a
// retry after an earlier failure. The failure branch above disables every
// gated control and leaves its message in #miss; both have to be undone
// here, or a fail-then-retry-then-succeed reader is left with a page that
// looks alive but has dead buttons and a stale error on it. Pulled out as
// its own function — rather than left inline in boot() — so this half of
// the contract can be exercised without going through load()'s Pyodide/
// fetch/dynamic-import pipeline, which the test harness cannot stub.
function finishBoot() {
  el("live").hidden = false;
  for (const id of GATED_CONTROL_IDS) {
    const control = el(id);
    if (control) control.disabled = false;
  }
  el("miss").hidden = true;
  el("translit-table").textContent = glue.readers_table();
}

async function load() {
  pyodide = await loadPyodide();
  await pyodide.loadPackage("micropip");
  const micropip = pyodide.pyimport("micropip");
  await micropip.install(WHEEL);

  // server/ is not in the wheel — it is deliberately not packaged. Mount
  // the one module the page needs so `sse.payload` is reused rather than
  // reimplemented in JavaScript.
  const sse = await (await fetch("sse.py")).text();
  pyodide.FS.mkdir("/server");
  pyodide.FS.writeFile("/server/__init__.py", "");
  pyodide.FS.writeFile("/server/sse.py", sse);
  const glueSource = await (await fetch("glue.py")).text();
  pyodide.FS.writeFile("/glue.py", glueSource);
  pyodide.runPython("import sys; sys.path.insert(0, '/')");
  glue = pyodide.pyimport("glue");

  // Dynamic, not static: cascade.js is absent until the workflow copies
  // it, and a static import would break the page for everyone.
  const { Cascade } = await import("./cascade.js");
  cascade = new Cascade(el("cascade"));
}

function writeProgram() {
  const result = glue.write(el("request").value).toJs({ dict_converter: Object.fromEntries });
  const miss = el("miss");
  if (result.ok) {
    el("editor").value = result.source;
    withdrawEditorFace();
    miss.hidden = true;
  } else {
    // Escape once, at the end. Hints contain angle brackets, so escaping
    // the hint and then the message renders a literal &lt;a&gt;.
    let text = result.error;
    if (result.hint) text += ` — try: ${result.hint}`;
    miss.textContent = text;
    miss.hidden = false;
  }
}

function runProgram() {
  const events = glue
    .run(el("editor").value, el("program-input").value)
    .toJs({ dict_converter: Object.fromEntries });
  cascade.clear();
  el("miss").hidden = true;
  for (const event of events) {
    if (event.kind === "statement") {
      // `source` is the pure glyph wall, `latin` keeps identifiers readable.
      // One toggle governs both faces — output too — per FL-7.
      cascade.add(face === "glyph" ? event.source : event.latin, "source");
    } else if (event.kind === "output") {
      cascade.add(face === "glyph" ? event.glyphs : event.text, "output");
    } else if (event.kind === "error") {
      // Diagnostics are never transliterated — an error is the moment a
      // reader's fluency has failed, and glyphs are the worst possible
      // response to that.
      el("miss").textContent = event.message;
      el("miss").hidden = false;
    }
  }
}

// The key is a local, never stored. Not localStorage, not a cookie, not a
// URL parameter: a persisted key is one XSS away from being someone
// else's, and this page cannot offer the isolation that would make
// storing it reasonable. site/checks/key_handling.py enforces that, and
// enforces that this file talks to exactly one host.
//
// `anthropic-dangerous-direct-browser-access` is what makes the API answer
// a browser at all — it opts the request into CORS. The header is named
// the way it is on purpose: sending a key from a page is a real risk, and
// the only reason it is defensible here is that the key is the reader's
// own and Scribe already works without one.
async function askOperator() {
  const key = el("api-key").value.trim();
  const miss = el("miss");
  if (!key) {
    miss.textContent = "Operator needs your own Anthropic API key. Scribe needs nothing.";
    miss.hidden = false;
    return;
  }

  const button = el("ask-operator");
  button.disabled = true;
  button.textContent = "Asking…";
  try {
    const response = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
        "anthropic-dangerous-direct-browser-access": "true",
      },
      body: JSON.stringify({
        model: "claude-opus-5",
        max_tokens: 4096,
        // `build()` returns the whole context with the request already in
        // it — role, keyword list, rules, worked example. There is no
        // separate system prompt to send, and nothing here assembles one.
        messages: [{ role: "user", content: glue.operator_prompt(el("request").value) }],
      }),
    });
    if (!response.ok) {
      const detail = await response.json().catch(() => ({}));
      throw new Error(detail?.error?.message || `HTTP ${response.status}`);
    }
    const body = await response.json();
    const text = body.content.filter((b) => b.type === "text").map((b) => b.text).join("");
    el("editor").value = text.trim();
    withdrawEditorFace();
    miss.hidden = true;
  } catch (error) {
    miss.textContent = `Operator failed: ${error.message}`;
    miss.hidden = false;
  } finally {
    button.disabled = false;
    button.textContent = "Ask Operator";
  }
}

// No start() call: Cascade begins its own requestAnimationFrame loop in
// its constructor and runs a fixed 33ms timestep, so speed is a property
// of the design rather than of the viewer's refresh rate (§5.7).

el("boot").addEventListener("click", boot);
el("write").addEventListener("click", writeProgram);
el("run").addEventListener("click", runProgram);
el("request").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); writeProgram(); }
});
el("ask-operator").addEventListener("click", askOperator);

function toggleCascadeFace() {
  face = face === "glyph" ? "latin" : "glyph";
  const button = el("cascade-face");
  button.textContent = face === "glyph" ? "Latin" : "Glyph wall";
  // Applies to the next run: the wall is cleared per run by design, and
  // toggling mid-fall would need cascade.js to re-render its history —
  // presentation, not worth touching the copied file for.
}

// The glyph face is a face *of the source it was rendered from*. The moment
// the editor changes it stops being one, so it is withdrawn rather than left
// sitting under a program it no longer describes — which on a page whose
// whole claim is "one program, two faces, the conversion loses nothing"
// would be the most damaging thing on the screen.
//
// Withdrawn, not re-rendered: re-rendering would mean a parse per keystroke,
// and a diagnostic for every half-typed line. Pressing the button again is
// how the reader asks for the face of what is now there.
function withdrawEditorFace() {
  const pre = el("editor-glyph");
  if (pre.hidden) return;
  pre.hidden = true;
  pre.textContent = "";
  el("editor-face").textContent = "Show glyphs";
}

function toggleEditorFace() {
  const pre = el("editor-glyph");
  const button = el("editor-face");
  if (pre.hidden === false) {
    pre.hidden = true;
    button.textContent = "Show glyphs";
    return;
  }
  // Ask Python, never transliterate here. A parse failure shows the real
  // diagnostic in the shared miss slot rather than a broken face.
  const result = glue.glyph(el("editor").value).toJs({ dict_converter: Object.fromEntries });
  if (result.ok) {
    pre.textContent = result.glyph;
    pre.hidden = false;
    button.textContent = "Hide glyphs";
    // The slot is shared, so a face that renders has to clear the failure
    // that a previous one left there — otherwise the reader fixes their
    // program, gets the glyphs, and the old syntax error is still accusing
    // them. `writeProgram` and `runProgram` both clear it on success.
    el("miss").hidden = true;
  } else {
    el("miss").textContent = result.error;
    el("miss").hidden = false;
  }
}

function toggleExampleFace(button) {
  const pre = button.previousElementSibling;
  pre.hidden = pre.hidden === false;
  button.textContent = pre.hidden ? "Show glyphs" : "Hide glyphs";
}

function transliterateLatin() {
  el("translit-glyphs").value = glue.transliterate_text(el("translit-latin").value);
}

function untransliterateGlyphs() {
  el("translit-latin").value = glue.untransliterate_text(el("translit-glyphs").value);
}

el("cascade-face").addEventListener("click", toggleCascadeFace);
el("editor-face").addEventListener("click", toggleEditorFace);
// Typing is only one of the ways the editor changes; Scribe and Operator
// both write into it, and assigning `.value` fires no input event, so they
// withdraw the face themselves.
el("editor").addEventListener("input", withdrawEditorFace);
document.querySelectorAll(".face-toggle").forEach((button) => {
  button.addEventListener("click", () => toggleExampleFace(button));
});
el("translit-boot").addEventListener("click", boot);
el("translit-latin").addEventListener("input", transliterateLatin);
el("translit-glyphs").addEventListener("input", untransliterateGlyphs);

window.__playground = { boot, write: writeProgram, run: runProgram, finishBoot };
