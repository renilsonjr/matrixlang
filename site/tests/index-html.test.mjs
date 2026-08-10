// The stub DOM is only worth anything if it starts where the real page does.
//
// A hand-written DOM has exactly one failure mode a dependency would not
// have: it drifts. Someone renames a button's label in index.html, the stub
// keeps the old one, and playground.test.mjs goes on passing against a page
// that no longer exists. This is the guard for that — it is a check on the
// harness, not on playground.js.

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

import { INITIAL } from "./dom.mjs";

const HTML = readFileSync(
  join(dirname(fileURLToPath(import.meta.url)), "..", "index.html"),
  "utf8",
);

/** The opening tag carrying this id, plus whatever sits inside the element. */
function findElement(id) {
  const opening = HTML.match(
    new RegExp(`<([a-z]+)((?:[^>]*\\s)?id="${id}"[^>]*)>`, "i"),
  );
  if (!opening) return null;
  const [tag, name, attributes] = opening;
  const rest = HTML.slice(HTML.indexOf(tag) + tag.length);
  const close = rest.indexOf(`</${name}>`);
  return { attributes, text: close === -1 ? "" : rest.slice(0, close) };
}

test("every element the harness stubs exists in index.html", () => {
  for (const id of Object.keys(INITIAL)) {
    assert.ok(findElement(id), `index.html has no element with id="${id}"`);
  }
});

test("the harness starts each element hidden exactly when the page does", () => {
  for (const [id, start] of Object.entries(INITIAL)) {
    const onPage = /\shidden(\s|>|=)/.test(`${findElement(id).attributes}>`);
    assert.equal(
      onPage,
      start.hidden ?? false,
      `id="${id}" is ${onPage ? "" : "not "}hidden in index.html, ` +
        `but the harness starts it ${start.hidden ? "" : "not "}hidden`,
    );
  }
});

test("the harness starts each control disabled exactly when the page does", () => {
  for (const [id, start] of Object.entries(INITIAL)) {
    const onPage = /\sdisabled(\s|>|=)/.test(`${findElement(id).attributes}>`);
    assert.equal(
      onPage,
      start.disabled ?? false,
      `id="${id}" is ${onPage ? "" : "not "}disabled in index.html, ` +
        `but the harness starts it ${start.disabled ? "" : "not "}disabled`,
    );
  }
});

test("the harness starts each control with the label the page gives it", () => {
  for (const [id, start] of Object.entries(INITIAL)) {
    if (start.text === undefined) continue;
    assert.equal(
      findElement(id).text.trim(),
      start.text,
      `id="${id}" is labelled differently in index.html than in the harness`,
    );
  }
});
