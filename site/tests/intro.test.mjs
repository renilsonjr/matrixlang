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
  storage = {},
  search = "",
  blockStorage = false,
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

  const sandbox = {
    console,
    setTimeout,
    clearTimeout,
    location: { search },
    URLSearchParams,
    fetch,
    // The session is the unit now. A localStorage stub is deliberately NOT
    // provided: if intro.js reaches for it again this throws rather than
    // quietly going back to remembering forever.
    sessionStorage: {
      getItem: (k) => { if (blockStorage) throw new Error("blocked"); return k in storage ? storage[k] : null; },
      setItem: (k, v) => { if (blockStorage) throw new Error("blocked"); storage[k] = v; },
    },
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

  return { root, storage, sandbox, fire: (type) => listeners.get(type)?.() };
}

test("a first-time reader gets the intro", () => {
  const { root } = load();
  assert.equal(root.dataset.intro, "playing");
});

test("a reader who has seen it this session does not get it again", () => {
  const { root } = load({ storage: { "matrixlang-intro-seen": "1" } });
  assert.equal(root.dataset.intro, undefined, "the intro replayed within one session");
});

test("a new session gets the intro again", () => {
  // sessionStorage starts empty in a new tab, which is the whole difference
  // from the localStorage version: coming back later is a fresh arrival.
  const { root } = load({ storage: {} });
  assert.equal(root.dataset.intro, "playing");
});

test("reduced motion means no intro at all", () => {
  const { root } = load({ reducedMotion: true });
  assert.equal(
    root.dataset.intro,
    undefined,
    "a reader who asked for less motion got a typewriter",
  );
});

test("?intro replays it even for a reader who has seen it", () => {
  const { root } = load({ storage: { "matrixlang-intro-seen": "1" }, search: "?intro" });
  assert.equal(root.dataset.intro, "playing");
});

test("?intro overrides reduced motion, because it was asked for explicitly", () => {
  const { root } = load({ reducedMotion: true, search: "?intro" });
  assert.equal(root.dataset.intro, "playing");
});

test("blocked storage plays the intro rather than throwing", () => {
  // Private mode. Reading and writing both throw; neither may escape.
  const { root } = load({ blockStorage: true });
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

test("stopping records that it was seen", () => {
  const { storage, sandbox } = load();
  sandbox.window.__intro.stop();
  assert.equal(storage["matrixlang-intro-seen"], "1");
});

test("a failed fetch does NOT record a viewing that never happened", async () => {
  // One transient network blip used to cost the reader the intro for the
  // whole session, having shown them nothing.
  const { root, storage, fire } = load({
    fetch: () => Promise.reject(new Error("offline")),
  });
  assert.equal(root.dataset.intro, "playing");

  await fire("DOMContentLoaded");

  assert.equal(
    storage["matrixlang-intro-seen"],
    undefined,
    "a reader who saw nothing was recorded as having watched it",
  );
});

test("a non-ok response for intro.json is treated the same way", async () => {
  const { storage, fire } = load({
    fetch: () => Promise.resolve({ ok: false, status: 404 }),
  });
  await fire("DOMContentLoaded");
  assert.equal(storage["matrixlang-intro-seen"], undefined);
});

test("an empty line list is a failure, not a viewing", async () => {
  const { storage, fire } = load({
    fetch: () => Promise.resolve({ ok: true, json: () => Promise.resolve({ lines: [] }) }),
  });
  await fire("DOMContentLoaded");
  assert.equal(storage["matrixlang-intro-seen"], undefined);
});

test("the browser half still owns no glyph table", () => {
  // The same rule site/checks/no_semantics.py enforces, asserted here too
  // because intro.js is the file most tempted to break it: it is the one
  // that puts glyphs on screen.
  const code = SOURCE.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, "");
  assert.doesNotMatch(code, /[ｦ-ﾝ]/, "intro.js contains a katakana literal");
  assert.doesNotMatch(code, /\btransliterate\s*\(/, "intro.js transliterates");
});
