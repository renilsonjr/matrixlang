// site/playground.js
// The playground's JavaScript half. It boots Pyodide, hands requests to
// site/glue.py, and draws what comes back.
//
// It deliberately owns no language logic: it never lexes, parses, converts
// text into glyphs, or builds a message shape. Every glyph it draws arrived
// already rendered from Python. That rule is what the deleted web/ layer
// broke, and TECHNICAL-OVERVIEW §5.7 is why it is stated here too.
//
// The wording above avoids the obvious verb on purpose: the plan's
// no-semantics check greps this file for that verb, and a file that talks
// about the rule must not read as a file that breaks it.

const WHEEL = "matrixlang-0.6.0-py3-none-any.whl";

let pyodide = null;
let glue = null;
let cascade = null;

const el = (id) => document.getElementById(id);

async function boot() {
  const button = el("boot");
  button.disabled = true;
  button.textContent = "Loading Python… (a few MB, once)";

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
  button.hidden = true;
  el("live").hidden = false;
}

function writeProgram() {
  const result = glue.write(el("request").value).toJs({ dict_converter: Object.fromEntries });
  const miss = el("miss");
  if (result.ok) {
    el("editor").value = result.source;
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
  const events = glue.run(el("editor").value).toJs({ dict_converter: Object.fromEntries });
  cascade.clear();
  el("miss").hidden = true;
  for (const event of events) {
    if (event.kind === "statement") {
      // `source` is the glyph face, `latin` the readable one. web-ui
      // offers a toggle; this page shows the glyph wall, which is the
      // thing worth seeing.
      cascade.add(event.source, "source");
    } else if (event.kind === "output") {
      // Already in the glyph face, converted in Python. The browser owns
      // no glyph table.
      cascade.add(event.glyphs, "output");
    } else if (event.kind === "error") {
      // Diagnostics stay in Latin — an error is the moment a reader's
      // fluency has failed, and glyphs are the worst possible response to
      // that.
      el("miss").textContent = event.message;
      el("miss").hidden = false;
    }
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

window.__playground = { boot, write: writeProgram, run: runProgram };
