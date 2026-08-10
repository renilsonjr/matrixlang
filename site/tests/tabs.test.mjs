// The tab engine, tested against a stub tablist -- three tabs, three panels.
// Deliberately not the real index.html: Task 3 wires the real markup, and
// this file only has to prove tabs.js does what it claims to any markup
// shaped like role="tab" / aria-controls.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const TABS = join(dirname(fileURLToPath(import.meta.url)), "..", "tabs.js");

class StubTab {
  constructor(controls) {
    this._attrs = { "aria-controls": controls, "aria-selected": "false" };
    this._listeners = new Map();
    this.focused = false;
  }
  getAttribute(name) { return this._attrs[name] ?? null; }
  setAttribute(name, value) { this._attrs[name] = String(value); }
  addEventListener(type, handler) {
    if (!this._listeners.has(type)) this._listeners.set(type, []);
    this._listeners.get(type).push(handler);
  }
  dispatchEvent(event) {
    for (const handler of this._listeners.get(event.type) ?? []) handler(event);
  }
  click() { this.dispatchEvent({ type: "click" }); }
  keydown(key) {
    let prevented = false;
    this.dispatchEvent({ type: "keydown", key, preventDefault: () => { prevented = true; } });
    return prevented;
  }
  focus() { this.focused = true; }
}

class StubPanel {
  constructor(id) { this.id = id; this.hidden = true; }
}

/** Load tabs.js into a fresh context wired to `count` stub tabs/panels. */
function loadTabs(count) {
  const panels = Array.from({ length: count }, (_, i) => new StubPanel(`panel-${i}`));
  const tabs = panels.map((panel) => new StubTab(panel.id));
  const byId = new Map(panels.map((p) => [p.id, p]));

  const document = {
    readyState: "complete",
    querySelectorAll: (selector) => (selector === '[role="tab"]' ? tabs : []),
    getElementById: (id) => byId.get(id) ?? null,
    addEventListener() {},
  };
  const sandbox = { document, console };
  sandbox.window = sandbox;
  const context = vm.createContext(sandbox);
  vm.runInContext(readFileSync(TABS, "utf8"), context, { filename: TABS });

  return { tabs, panels };
}

test("wiring activates the first tab and panel, and only those", () => {
  const { tabs, panels } = loadTabs(3);
  assert.equal(panels[0].hidden, false);
  assert.equal(panels[1].hidden, true);
  assert.equal(panels[2].hidden, true);
  assert.equal(tabs[0].getAttribute("aria-selected"), "true");
  assert.equal(tabs[1].getAttribute("aria-selected"), "false");
});

test("clicking a tab activates its panel and deactivates the others", () => {
  const { tabs, panels } = loadTabs(3);
  tabs[2].click();
  assert.equal(panels[2].hidden, false);
  assert.equal(panels[0].hidden, true);
  assert.equal(tabs[2].getAttribute("aria-selected"), "true");
  assert.equal(tabs[0].getAttribute("aria-selected"), "false");
});

test("ArrowRight moves to the next tab and wraps past the last", () => {
  const { tabs, panels } = loadTabs(3);
  tabs[2].click(); // start on the last tab
  const prevented = tabs[2].keydown("ArrowRight");
  assert.equal(prevented, true, "ArrowRight must not scroll the page");
  assert.equal(tabs[0].focused, true);
  assert.equal(panels[0].hidden, false);
});

test("ArrowLeft moves to the previous tab and wraps before the first", () => {
  const { tabs, panels } = loadTabs(3);
  tabs[0].keydown("ArrowLeft");
  assert.equal(tabs[2].focused, true);
  assert.equal(panels[2].hidden, false);
});

test("a key other than the arrows does nothing", () => {
  const { tabs, panels } = loadTabs(3);
  const prevented = tabs[0].keydown("Enter");
  assert.equal(prevented, false);
  assert.equal(panels[0].hidden, false); // unchanged
});

test("a page with no tablist does not throw", () => {
  assert.doesNotThrow(() => loadTabs(0));
});
