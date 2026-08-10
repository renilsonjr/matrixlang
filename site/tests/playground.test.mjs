// What playground.js is supposed to DO.
//
// site/checks/ already pins what it must not do — own a glyph table, persist
// a key, talk to a second host. Those are prohibitions, and a static scan can
// enforce them. Nothing enforced the other half, and all three faults found
// auditing #82 lived there: not in any single line, but in the relationship
// between lines across time. Every test below failed against the revision
// that shipped those faults.
//
// The glyph strings are placeholders. This file knows no more about the
// language than playground.js is allowed to — what is under test is which
// face is showing and whether it still belongs to the source above it.

import assert from "node:assert/strict";
import test from "node:test";

import { loadPlayground } from "./dom.mjs";

/** A glue whose glyph() succeeds, tagging its output with what it was given. */
const rendering = {
  glyph: (source) => ({ ok: true, glyph: `GLYPH(${source})` }),
  write: (request) => ({ ok: true, source: `SOURCE(${request})` }),
};

test("the glyph face is withdrawn when the reader edits the source", () => {
  const page = loadPlayground();
  page.setGlue(rendering);

  page.type("editor", "trace 1");
  page.el("editor-face").click();
  assert.equal(page.el("editor-glyph").textContent, "GLYPH(trace 1)");
  assert.equal(page.el("editor-glyph").hidden, false);
  assert.equal(page.el("editor-face").textContent, "Hide glyphs");

  page.type("editor", "trace 2");

  // The fault: the face stayed, so the page showed GLYPH(trace 1) directly
  // beneath `trace 2` and called them two faces of one program.
  assert.equal(
    page.el("editor-glyph").hidden,
    true,
    "a face of the previous program is still showing",
  );
  assert.equal(page.el("editor-face").textContent, "Show glyphs");

  // Asking again renders the face of what is actually there now.
  page.el("editor-face").click();
  assert.equal(page.el("editor-glyph").textContent, "GLYPH(trace 2)");
});

test("the glyph face is withdrawn when Scribe writes into the editor", () => {
  const page = loadPlayground();
  page.setGlue(rendering);

  page.type("editor", "trace 1");
  page.el("editor-face").click();
  assert.equal(page.el("editor-glyph").hidden, false);

  page.el("request").value = "count from 1 to 5";
  page.el("write").click();

  // Assigning .value fires no input event, so this path has to withdraw the
  // face itself. Operator's reply lands in the editor the same way.
  assert.equal(page.el("editor").value, "SOURCE(count from 1 to 5)");
  assert.equal(
    page.el("editor-glyph").hidden,
    true,
    "the face survived a program the reader did not type",
  );
});

test("a face that will not render leaves its diagnostic in the miss slot", () => {
  const page = loadPlayground();
  page.setGlue({ glyph: () => ({ ok: false, error: "[line 1] broken" }) });

  page.type("editor", "trace )(");
  page.el("editor-face").click();

  assert.equal(page.el("miss").hidden, false);
  assert.equal(page.el("miss").textContent, "[line 1] broken");
  assert.equal(page.el("editor-glyph").hidden, true);
  assert.equal(page.el("editor-face").textContent, "Show glyphs");
});

test("a face that renders clears the diagnostic left by one that did not", () => {
  const page = loadPlayground();
  let broken = true;
  page.setGlue({
    glyph: (source) =>
      broken ? { ok: false, error: "[line 1] broken" } : { ok: true, glyph: `GLYPH(${source})` },
  });

  page.type("editor", "trace )(");
  page.el("editor-face").click();
  assert.equal(page.el("miss").hidden, false);

  broken = false;
  page.type("editor", "trace 3");
  page.el("editor-face").click();

  assert.equal(page.el("editor-glyph").textContent, "GLYPH(trace 3)");
  // The fault: the slot is shared, so the reader fixed the program, got the
  // glyphs, and kept the old error sitting above them.
  assert.equal(
    page.el("miss").hidden,
    true,
    "a stale diagnostic outlived the failure that caused it",
  );
});

test("a failed boot leaves no control looking usable", async () => {
  const page = loadPlayground();
  page.setGlobal("loadPyodide", () => Promise.reject(new Error("blocked")));

  await page.playground.boot();

  // #miss lives inside #live, so saying anything means revealing the block —
  // which is why every control in it has to be dead, not merely present.
  assert.equal(page.el("live").hidden, false);
  assert.equal(page.el("miss").hidden, false);
  assert.match(page.el("miss").textContent, /could not load/);

  for (const id of [
    "write", "run", "ask-operator", "editor-face", "cascade-face",
    "translit-latin", "translit-glyphs",
  ]) {
    assert.equal(page.el(id).disabled, true, `${id} is still live after a failed boot`);
  }

  // Both boot buttons must come back: the reader can retry from either tab.
  assert.equal(page.el("boot").disabled, false);
  assert.equal(page.el("translit-boot").disabled, false);
});

test("typing Latin fills the Glyphs box, and back again", () => {
  const page = loadPlayground();
  page.setGlue({
    transliterate_text: (text) => `GLYPHS(${text})`,
    untransliterate_text: (glyphs) => `LATIN(${glyphs})`,
  });

  page.type("translit-latin", "hello");
  assert.equal(page.el("translit-glyphs").value, "GLYPHS(hello)");

  page.type("translit-glyphs", "abc");
  assert.equal(page.el("translit-latin").value, "LATIN(abc)");
});

test("an example's glyph face toggles independently of its neighbours", () => {
  const page = loadPlayground({ faceToggles: 3 });
  const [first, second] = page.examples;

  first.button.click();
  assert.equal(first.pre.hidden, false);
  assert.equal(first.button.textContent, "Hide glyphs");
  assert.equal(second.pre.hidden, true, "a neighbouring example also opened");

  first.button.click();
  assert.equal(first.pre.hidden, true);
  assert.equal(first.button.textContent, "Show glyphs");
});
