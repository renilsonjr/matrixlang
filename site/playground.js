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

const el = (id) => document.getElementById(id);

async function boot() {
  const button = el("boot");
  button.disabled = true;
  button.textContent = "Loading Python… (a few MB, once)";
  try {
    await load();
  } catch (error) {
    // Without this the rejection surfaces only as "Uncaught (in promise)"
    // in a console the reader is not looking at, and the button sits on
    // "Loading Python…" forever. A CDN that is blocked, an offline tab,
    // and a wheel that failed to publish all look like that. The narrative
    // above is unaffected — that is the point of loading none of this
    // until asked.
    button.disabled = false;
    button.textContent = "Load the interpreter and try it";
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
    for (const id of ["write", "run", "ask-operator"]) {
      const control = el(id);
      if (control) control.disabled = true;
    }
    return;
  }
  button.hidden = true;
  el("live").hidden = false;
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
      // Already transliterated in Python. The browser owns no glyph table.
      cascade.add(event.glyphs, "output");
    } else if (event.kind === "error") {
      // Diagnostics are never transliterated — an error is the moment a
      // reader's fluency has failed, and glyphs are the worst possible
      // response to that.
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
