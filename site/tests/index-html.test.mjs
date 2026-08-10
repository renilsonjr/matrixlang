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

/**
 * Every opening tag carrying a given boolean/valueless-or-valued attribute
 * pattern — e.g. `role="tab"`. Returns each match's full attribute string,
 * the same shape findElement() returns a single one of. A minimal
 * regex sweep rather than a real parser, in keeping with the rest of this
 * file: the markup here is simple enough that "strip to opening tags, match
 * attributes" holds.
 */
function findAllWithAttribute(attributePattern) {
  const tagPattern = new RegExp(`<[a-z]+\\s[^>]*${attributePattern}[^>]*>`, "gi");
  return HTML.match(tagPattern) ?? [];
}

/** Pull one attribute's value out of a raw opening tag string. */
function attr(tag, name) {
  const match = tag.match(new RegExp(`${name}="([^"]*)"`, "i"));
  return match ? match[1] : null;
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

// tabs.js maps aria-controls through document.getElementById() and then
// unconditionally writes panel.hidden on the result. If a tab's
// aria-controls ever pointed at a missing or renamed panel id, that throws a
// TypeError at DOMContentLoaded and silently breaks tab switching for every
// visitor — and neither tabs.test.mjs (synthetic stubs) nor the rest of this
// file (walks INITIAL's ids, which has none of the tab markup in it) would
// notice. These tests pin the contract directly against the real markup.
test("every tab's aria-controls points at a real tabpanel", () => {
  const tabs = findAllWithAttribute('role="tab"');
  assert.ok(tabs.length > 0, "found no role=\"tab\" elements in index.html");

  for (const tab of tabs) {
    const controls = attr(tab, "aria-controls");
    assert.ok(controls, `a role="tab" element has no aria-controls: ${tab}`);

    const panel = findElement(controls);
    assert.ok(panel, `aria-controls="${controls}" points at no element with that id`);
    assert.equal(
      attr(`<div ${panel.attributes}>`, "role"),
      "tabpanel",
      `id="${controls}" is not role="tabpanel"`,
    );
  }
});

test("exactly one tabpanel is visible by default, and it agrees with the selected tab", () => {
  const tabs = findAllWithAttribute('role="tab"');
  const panels = findAllWithAttribute('role="tabpanel"');

  const visiblePanels = panels.filter((panel) => !/\shidden(\s|>|=)/.test(panel));
  assert.equal(visiblePanels.length, 1, `expected exactly one visible tabpanel, found ${visiblePanels.length}`);
  const visiblePanelId = attr(visiblePanels[0], "id");

  const selectedTabs = tabs.filter((tab) => attr(tab, "aria-selected") === "true");
  assert.equal(selectedTabs.length, 1, `expected exactly one tab with aria-selected="true", found ${selectedTabs.length}`);
  const selectedTab = selectedTabs[0];

  assert.equal(
    attr(selectedTab, "aria-controls"),
    visiblePanelId,
    "the selected tab's aria-controls does not point at the one visible panel",
  );
});
