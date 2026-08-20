// A DOM small enough to read in one sitting, and a loader for playground.js.
//
// Deliberately not jsdom. The plan's constraint is "no new dependencies, no
// build step", and the faults this harness exists to catch — a face that
// outlives its source, an error that outlives its cause, a control left live
// after a failed boot — are all `hidden`, `disabled`, `textContent` and
// `value` on a handful of elements. A full DOM would buy nothing they need
// and cost a second dependency tree in a repo that currently has none.
//
// What this cannot see: anything past the JavaScript. `glue` is stubbed, so
// a wrong key in the payload shape, a Pyodide API change, or a real
// transliteration bug all pass here. Those belong to the Python suite and to
// booting the assembled site for real.

import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const HERE = dirname(fileURLToPath(import.meta.url));

// Overridable so the harness can be pointed at an older revision of the file
// and made to fail — the check that these tests detect what they claim to.
export const PLAYGROUND =
  process.env.PLAYGROUND_JS ?? join(HERE, "..", "playground.js");

class StubElement {
  constructor(id) {
    this.id = id;
    this.hidden = false;
    this.disabled = false;
    this.textContent = "";
    this.value = "";
    this.previousElementSibling = null;
    this._listeners = new Map();
  }

  addEventListener(type, handler) {
    if (!this._listeners.has(type)) this._listeners.set(type, []);
    this._listeners.get(type).push(handler);
  }

  dispatchEvent(event) {
    for (const handler of this._listeners.get(event.type) ?? []) handler(event);
  }

  click() {
    this.dispatchEvent({ type: "click" });
  }
}

// Every id playground.js reaches for, with the state site/index.html gives
// it before any script runs. Listed rather than created on demand, so a typo
// in the source shows up as a null here instead of silently working against
// an element the page does not have.
//
// The initial state is not decoration. A stub where everything starts visible
// lets a test pass for a reason the page does not have: `#live` begins
// hidden, so "a failed boot reveals it" is only a claim if it was hidden to
// begin with. `index-html.test.mjs` is what keeps this table honest.
export const INITIAL = {
  "boot": { text: "Load the interpreter and try it" },
  "live": { hidden: true },
  "miss": { hidden: true },
  "request": {},
  "write": { text: "Write it" },
  "editor": {},
  "editor-face": { text: "Show glyphs" },
  "editor-glyph": { hidden: true },
  "program-input": {},
  "run": { text: "Run it" },
  "answer-row": { hidden: true },
  "answer-prompt": {},
  "answer": {},
  "answer-send": { text: "Answer" },
  "cascade": {},
  "cascade-face": { text: "Latin" },
  "api-key": {},
  "ask-operator": { text: "Ask Operator" },
  "translit-latin": { disabled: true },
  "translit-glyphs": { disabled: true },
  "translit-boot": { text: "Load the interpreter and try it" },
  "translit-table": {},
};

/**
 * Load playground.js into a fresh context with a stub DOM.
 *
 * `glue` is a script-scoped `let` in playground.js, so nothing outside can
 * reach it — but a second script run in the same context shares that scope,
 * which is what `setGlue` uses. The alternative, going through `boot()`,
 * would drag in Pyodide, micropip, fetch and a dynamic import of cascade.js
 * for tests that are about none of those.
 */
export function loadPlayground({ faceToggles = 0 } = {}) {
  const elements = new Map(
    Object.entries(INITIAL).map(([id, start]) => {
      const element = new StubElement(id);
      element.hidden = start.hidden ?? false;
      element.disabled = start.disabled ?? false;
      element.textContent = start.text ?? "";
      return [id, element];
    }),
  );

  // Each example is a <pre> the toggle hides and shows, followed by its
  // button — the sibling relationship toggleExampleFace() relies on.
  const examples = [];
  for (let i = 0; i < faceToggles; i += 1) {
    const pre = new StubElement(`example-glyph-${i}`);
    pre.hidden = true;
    const button = new StubElement(`face-toggle-${i}`);
    button.textContent = "Show glyphs";
    button.previousElementSibling = pre;
    examples.push({ pre, button });
  }

  const document = {
    getElementById: (id) => elements.get(id) ?? null,
    querySelectorAll: (selector) =>
      selector === ".face-toggle" ? examples.map((e) => e.button) : [],
  };

  const sandbox = { document, console };
  sandbox.window = sandbox;
  const context = vm.createContext(sandbox);
  vm.runInContext(readFileSync(PLAYGROUND, "utf8"), context, {
    filename: PLAYGROUND,
  });

  // `cascade` is only ever constructed inside load(), which this harness
  // never runs — so it starts out null, same as it does on the real page
  // before Pyodide finishes booting. Any test that clicks #run walks
  // straight into runProgram()'s unconditional `cascade.clear()`, which
  // has nothing to do with what such a test is actually checking. A no-op
  // stand-in, assigned the same way setGlue() reaches the module-scoped
  // `glue`, keeps that a non-issue here.
  vm.runInContext("cascade = { clear() {}, add() {} };", context);

  return {
    el: (id) => elements.get(id),
    examples,
    playground: sandbox.__playground,

    /** Type into an element the way a reader does: value, then the event. */
    type(id, value) {
      const element = elements.get(id);
      element.value = value;
      element.dispatchEvent({ type: "input" });
    },

    /** Stand in for the Python half. Values are whatever the test needs. */
    setGlue(stub) {
      sandbox.__stubGlue = {};
      for (const [name, fn] of Object.entries(stub)) {
        // Real calls return a PyProxy the caller converts with .toJs() —
        // but only for dicts and lists. Pyodide converts str/int/float/bool
        // straight to their JS equivalents with no PyProxy and no .toJs()
        // to call, which is what transliterate_text() and friends return.
        // Wrapping every stub the same way would make playground.js's
        // correct, .toJs()-free call to those look broken here while
        // breaking for real the moment it grew one.
        sandbox.__stubGlue[name] = (...args) => {
          const result = fn(...args);
          return result !== null && typeof result === "object"
            ? { toJs: () => result }
            : result;
        };
      }
      vm.runInContext("glue = __stubGlue", context);
    },

    /** Replace the global playground.js reaches for during load(). */
    setGlobal(name, value) {
      sandbox[name] = value;
    },
  };
}
