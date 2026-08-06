// What intro.js decides, and how it fails.
//
// The animation is not what can hurt anyone — a mistimed cursor is a shrug.
// What can hurt is the intro appearing when it should not, or failing in a
// way that leaves a reader staring at a black rectangle with the page behind
// it. Every test here is about one of those two.
//
// The typing itself is left alone deliberately: asserting on wall-clock
// animation buys flakiness and pins nothing anyone would notice breaking.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import vm from "node:vm";

const INTRO = join(dirname(fileURLToPath(import.meta.url)), "..", "intro.js");
const SOURCE = readFileSync(INTRO, "utf8");

/** The smallest environment intro.js can decide in. */
function load({
  reducedMotion = false,
  search = "",
  fetch = () => Promise.reject(new Error("not used in this test")),
} = {}) {
  const root = { dataset: {}, removeAttribute(name) { delete this.dataset[name.replace("data-", "")]; } };
  const elements = new Map();
  const listeners = new Map();
  const stub = () => ({
    className: "", textContent: "", hidden: false,
    classList: { add() {}, remove() {} },
    append() {}, appendChild() {}, remove() {}, addEventListener() {},
  });
  for (const id of ["intro", "intro-terminal", "intro-skip"]) elements.set(id, stub());

  // Neither storage is provided. The intro is supposed to remember nothing,
  // so any attempt to read or write a flag is a ReferenceError here rather
  // than a quiet return to hiding itself from people.
  const sandbox = {
    console,
    setTimeout,
    clearTimeout,
    location: { search },
    URLSearchParams,
    fetch,
    document: {
      documentElement: root,
      readyState: "loading",
      getElementById: (id) => elements.get(id) ?? null,
      addEventListener: (type, fn) => listeners.set(type, fn),
      createElement: stub,
    },
    matchMedia: (query) => ({ matches: reducedMotion && query.includes("reduce") }),
  };
  sandbox.window = sandbox;
  sandbox.window.addEventListener = () => {};
  const context = vm.createContext(sandbox);
  vm.runInContext(SOURCE, context, { filename: INTRO });

  return { root, sandbox, fire: (type) => listeners.get(type)?.() };
}

test("every page load gets the intro", () => {
  const { root } = load();
  assert.equal(root.dataset.intro, "playing");
});

test("a reload gets it again — nothing is remembered between loads", () => {
  // Two independent loads stand in for a refresh. Both must play: the
  // once-per-browser and once-per-tab versions each failed this, and each
  // one hid the intro from almost everybody.
  for (const attempt of [1, 2, 3]) {
    const { root } = load();
    assert.equal(root.dataset.intro, "playing", `load ${attempt} did not play`);
  }
});

test("intro.js touches no storage at all", () => {
  // The sandbox above provides neither, so a reach for one would already
  // throw — but this says why, and catches it even if a stub reappears.
  const code = SOURCE.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
  assert.doesNotMatch(code, /localStorage\s*\./, "intro.js reads or writes localStorage");
  assert.doesNotMatch(code, /sessionStorage\s*\./, "intro.js reads or writes sessionStorage");
});

test("reduced motion means no intro at all", () => {
  const { root } = load({ reducedMotion: true });
  assert.equal(
    root.dataset.intro,
    undefined,
    "a reader who asked for less motion got a typewriter",
  );
});

test("?intro overrides reduced motion, because it was asked for explicitly", () => {
  const { root } = load({ reducedMotion: true, search: "?intro" });
  assert.equal(root.dataset.intro, "playing");
});

test("stopping clears the attribute, so the page is never left covered", async () => {
  const { root, sandbox } = load();
  assert.equal(root.dataset.intro, "playing");
  sandbox.window.__intro.stop();
  // The attribute drops after the fade rather than during it.
  await new Promise((resolve) => setTimeout(resolve, 1000));
  assert.equal(root.dataset.intro, undefined, "the overlay attribute outlived the intro");
});

test("a failed fetch leaves the reader the page, not a black screen", async () => {
  const { root, fire } = load({ fetch: () => Promise.reject(new Error("offline")) });
  assert.equal(root.dataset.intro, "playing");
  await fire("DOMContentLoaded");
  await new Promise((resolve) => setTimeout(resolve, 1000));
  assert.equal(root.dataset.intro, undefined, "a failed fetch left the overlay up");
});

test("a non-ok response for intro.json is treated the same way", async () => {
  const { root, fire } = load({ fetch: () => Promise.resolve({ ok: false, status: 404 }) });
  await fire("DOMContentLoaded");
  await new Promise((resolve) => setTimeout(resolve, 1000));
  assert.equal(root.dataset.intro, undefined);
});

test("an empty line list leaves the reader the page", async () => {
  const { root, fire } = load({
    fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve({ lines: [] }) }),
  });
  await fire("DOMContentLoaded");
  await new Promise((resolve) => setTimeout(resolve, 1000));
  assert.equal(root.dataset.intro, undefined);
});

test("the browser half still owns no glyph table", () => {
  // The same rule site/checks/no_semantics.py enforces, asserted here too
  // because intro.js is the file most tempted to break it: it is the one
  // that puts glyphs on screen.
  const code = SOURCE.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
  assert.doesNotMatch(code, /[ｦ-ﾝ]/, "intro.js contains a katakana literal");
  assert.doesNotMatch(code, /\btransliterate\s*\(/, "intro.js transliterates");
});
