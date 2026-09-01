// The page's scripts have to survive being loaded together.
//
// This test exists because of a concrete bug. intro.js declared
// `const STORAGE_KEY`, layout.js already had one, and classic scripts share
// a single global lexical scope — so the browser threw "Identifier
// 'STORAGE_KEY' has already been declared", intro.js died before its first
// statement, and the intro simply never appeared. Nothing failed loudly:
// no test went red, the page looked fine, and the feature was just absent.
//
// Every other test in this directory loads one file into its own context,
// which is precisely the arrangement that cannot see this class of bug.
// Here the files are loaded into ONE context, in the order index.html loads
// them, because that is what the browser does.

import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..");

// The order index.html loads them: the two head scripts, then the deferred
// playground at the end of body.
const ORDER = ["layout.js", "intro.js", "tabs.js", "rain.js", "playground.js"];

/** Enough of a browser for three scripts to reach the end of themselves. */
function browser() {
  const made = new Map();
  const element = (id) => {
    if (!made.has(id)) {
      made.set(id, {
        id, hidden: false, disabled: false, textContent: "", value: "",
        dataset: {}, previousElementSibling: null,
        classList: { add() {}, remove() {}, toggle() {} },
        addEventListener() {}, setAttribute() {}, append() {}, appendChild() {},
        remove() {}, insertBefore() {},
      });
    }
    return made.get(id);
  };

  const sandbox = {
    console, setTimeout, clearTimeout, URLSearchParams,
    location: { search: "" },
    localStorage: { getItem: () => null, setItem() {} },
    matchMedia: () => ({ matches: false }),
    fetch: () => Promise.reject(new Error("no network in tests")),
    document: {
      documentElement: { dataset: {}, removeAttribute() {} },
      readyState: "loading",
      getElementById: element,
      querySelectorAll: () => [],
      addEventListener() {},
      createElement: () => element(Symbol()),
    },
  };
  sandbox.window = sandbox;
  sandbox.window.addEventListener = () => {};
  return vm.createContext(sandbox);
}

test("every script the page ships is actually shipped by the workflow", () => {
  // A file that exists but is never copied into _site is a file that works
  // locally and 404s in production.
  const workflow = readFileSync(join(SITE, "..", ".github", "workflows", "pages.yml"), "utf8");
  for (const name of readdirSync(SITE).filter((f) => f.endsWith(".js"))) {
    assert.ok(
      workflow.includes(`site/${name}`),
      `site/${name} is never copied into _site by pages.yml`,
    );
  }
});

test("the scripts load together without a redeclaration", () => {
  const context = browser();
  for (const name of ORDER) {
    const source = readFileSync(join(SITE, name), "utf8");
    assert.doesNotThrow(
      () => vm.runInContext(source, context, { filename: name }),
      `${name} threw when loaded after ${ORDER.slice(0, ORDER.indexOf(name)).join(", ") || "nothing"}`,
    );
  }
});

test("loading them together leaves both features wired", () => {
  // Not just "did not throw": the bug's symptom was a feature going missing
  // while everything around it kept working.
  const context = browser();
  for (const name of ORDER) {
    vm.runInContext(readFileSync(join(SITE, name), "utf8"), context, { filename: name });
  }
  const globals = vm.runInContext(
    "JSON.stringify({ intro: typeof window.__intro, playground: typeof window.__playground })",
    context,
  );
  assert.deepEqual(JSON.parse(globals), { intro: "object", playground: "object" });
});
