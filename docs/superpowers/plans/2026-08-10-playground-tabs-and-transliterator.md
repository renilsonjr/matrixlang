# Playground Tabs and Transliterator Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Retitle the front page's hero, move its explanation behind four tabs (Overview / Two Faces / How It Works / Transliterator) so only one section renders at once, enlarge the playground, and add a live bidirectional Latin ⇄ glyph translator powered by the real `translit.py` through Pyodide.

**Architecture:** A new `site/tabs.js` (vanilla, IIFE-wrapped like `intro.js`, no build step) wires `role="tablist"/"tab"/"tabpanel"` markup with click and arrow-key switching, no persistence. The three existing prose sections and the example band move, verbatim, into the first three tab panels. The Transliterator tab is a fourth panel with two synced `<textarea>` boxes; it is powered by two new thin wrappers in `site/glue.py` (`transliterate_text`, `untransliterate_text`, plus `readers_table` for a "full table" disclosure) called through Pyodide exactly as `write()`/`run()` already are — never a JavaScript copy of the table, which `site/checks/no_semantics.py` forbids.

**Tech Stack:** Python 3.11+ stdlib, pytest, plain HTML/CSS/JS, Node's built-in `node --test`. No new dependencies, no build step beyond the existing assembly in `.github/workflows/pages.yml`.

## Global Constraints

- `src/matrixlang/` and `server/sse.py` are **untouched** (TT-11). No new wire field.
- `site/checks/no_semantics.py` stays passing, **unmodified**: no `.js` file in `site/` calls `transliterate`/`untransliterate`, holds a glyph-table literal, or declares a table constant. The Transliterator's browser side only calls into `glue.py`.
- `site/checks/key_handling.py` stays passing, **unmodified**: neither `tabs.js` nor the Transliterator wiring in `playground.js` touches `localStorage`/`sessionStorage`/`document.cookie`/etc.
- Tab state is **not persisted** (TT-5) — every page load opens on Overview.
- The example band moves inside the **How It Works** tab panel (TT-4); the prose itself is reorganized, not rewritten.
- The playground stays outside every tab, always visible (TT-2).
- Canvas base resolution **640×360 → 960×540**; editor `<textarea>` **10 rows → 16** (TT-7). The `aspect-ratio: 16 / 9` mechanism that stops the `ResizeObserver` feedback loop is untouched.
- Classic `<script>` tags in `site/` share one global lexical scope — `site/tabs.js` must be IIFE-wrapped (matching `intro.js`) so its top-level names cannot collide with `layout.js` or `playground.js`.
- The full test suite stays green: `python -m pytest -q` and `node --test site/tests/*.test.mjs`.
- Any new `.js` file in `site/` must be added to the `cp` step in `.github/workflows/pages.yml` and to the `ORDER` array in `site/tests/scripts-coexist.test.mjs`, or it ships locally and 404s in production / never gets the redeclaration check.

---

### Task 1: `site/glue.py` — the Transliterator's Python side

**Files:**
- Modify: `site/glue.py`
- Modify: `tests/test_site_glue.py`

**Interfaces:**
- Consumes: `matrixlang.translit.transliterate`, `matrixlang.translit.untransliterate`, `matrixlang.translit.table_for_readers` (all already exist).
- Produces: `glue.transliterate_text(text: str) -> str`, `glue.untransliterate_text(glyphs: str) -> str`, `glue.readers_table() -> str` — plain strings, so the JS side uses them directly with no `.toJs()` (same as the existing `glue.operator_prompt()`).

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_site_glue.py`, after `test_glyph_of_invalid_source_is_an_error`:

```python
def test_transliterate_text_round_trips():
    original = "Neo woke up"
    glyphs = glue.transliterate_text(original)
    assert glyphs != original
    assert glue.untransliterate_text(glyphs) == original


def test_transliterate_text_matches_the_real_table():
    from matrixlang.translit import transliterate

    assert glue.transliterate_text("hello") == transliterate("hello")


def test_readers_table_documents_the_markers():
    table = glue.readers_table()
    assert "marks the next glyph as uppercase" in table
    assert "marks the next character as literal" in table
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests/test_site_glue.py -v -k "transliterate_text or readers_table"`
Expected: FAIL with `AttributeError: module 'glue' has no attribute 'transliterate_text'` (and similarly for the other two).

- [ ] **Step 3: Add the three wrappers to `site/glue.py`**

Add `table_for_readers`, `transliterate`, `untransliterate` to the import block at the top (alphabetized, matching the existing style):

```python
from matrixlang.interpreter import Interpreter
from matrixlang.lexer import lex
from matrixlang.parser import parse
from matrixlang.render import render_glyph
from matrixlang.scribe import ScribeProgram, scribe
from matrixlang.translit import table_for_readers, transliterate, untransliterate

from server.sse import payload
```

Add the three functions after `glyph()` and before `operator_prompt()`:

```python
def transliterate_text(text: str) -> str:
    """The glyph face of arbitrary text, for the Transliterator tab.

    Calls the real table rather than a JS copy of it — a JS copy is the
    exact shape of thing site/checks/no_semantics.py exists to block (see
    the playground-tabs-and-transliterator design doc, TT-9).
    """
    return transliterate(text)


def untransliterate_text(glyphs: str) -> str:
    """The inverse of transliterate_text()."""
    return untransliterate(glyphs)


def readers_table() -> str:
    """The full reversible table, for the Transliterator's disclosure panel."""
    return table_for_readers()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `python -m pytest tests/test_site_glue.py -v`
Expected: PASS, all tests including the three new ones.

- [ ] **Step 5: Run the two site checks to confirm they still pass unmodified**

Run: `python site/checks/no_semantics.py && python site/checks/key_handling.py`
Expected: both print their success line (`glue.py` is Python, not scanned by either check — this just confirms nothing else broke).

- [ ] **Step 6: Commit**

```bash
git add site/glue.py tests/test_site_glue.py
git commit -m "feat: add glue.py wrappers for the Transliterator tab"
```

---

### Task 2: `site/tabs.js` — the tab-switching engine

**Files:**
- Create: `site/tabs.js`
- Create: `site/tests/tabs.test.mjs`
- Modify: `.github/workflows/pages.yml`
- Modify: `site/tests/scripts-coexist.test.mjs`

**Interfaces:**
- Consumes: nothing from other tasks — this is pure DOM wiring against `role="tab"`/`aria-controls` markup that Task 3 will add. It degrades safely (does nothing) if that markup isn't present yet, which is what makes it buildable and testable first.
- Produces: click-to-switch and Left/Right-arrow-to-switch behavior over any `[role="tab"]` elements found on the page, each with an `aria-controls` attribute naming the panel `id` it shows.

- [ ] **Step 1: Write the failing tests**

Create `site/tests/tabs.test.mjs`:

```javascript
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
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `node --test site/tests/tabs.test.mjs`
Expected: FAIL — `site/tabs.js` does not exist yet (`Cannot find module`).

- [ ] **Step 3: Write `site/tabs.js`**

```javascript
// site/tabs.js
// The "About MatrixLang" tab strip: four tabs, one panel visible at a time.
// No persistence (design TT-5) — every page load opens on the first tab.
//
// Wrapped in an IIFE for the reason intro.js's own comment gives: layout.js,
// intro.js, tabs.js and playground.js are classic scripts sharing one global
// lexical scope, and a top-level name here would collide with theirs.
(function () {
"use strict";

function activate(tabs, panels, index) {
  tabs.forEach((tab, i) => tab.setAttribute("aria-selected", String(i === index)));
  panels.forEach((panel, i) => { panel.hidden = i !== index; });
}

function wire(tabs, panels) {
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => activate(tabs, panels, index));
    tab.addEventListener("keydown", (event) => {
      if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
      event.preventDefault();
      const delta = event.key === "ArrowRight" ? 1 : -1;
      const next = (index + delta + tabs.length) % tabs.length;
      tabs[next].focus();
      activate(tabs, panels, next);
    });
  });
}

function start() {
  const tabs = Array.from(document.querySelectorAll('[role="tab"]'));
  if (!tabs.length) return; // presentation only; nothing to wire on a page without tabs
  const panels = tabs.map((tab) => document.getElementById(tab.getAttribute("aria-controls")));
  wire(tabs, panels);
  activate(tabs, panels, 0); // authoritative: correct even if the static markup drifts
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", start);
} else {
  start();
}

})();
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `node --test site/tests/tabs.test.mjs`
Expected: PASS, all 6 tests.

- [ ] **Step 5: Register the new file with the workflow and the coexistence test**

In `.github/workflows/pages.yml`, add `site/tabs.js` to the `cp` line in the "Assemble the site" step:

```yaml
      - name: Assemble the site
        run: |
          mkdir -p _site
          cp site/index.html site/style.css site/layout.js site/intro.js site/tabs.js site/playground.js site/glue.py site/examples.json site/intro.json _site/
```

In `site/tests/scripts-coexist.test.mjs`, add `"tabs.js"` to `ORDER`, in the position it will load in `index.html` (after the two `<head>` scripts, before the deferred `playground.js` at the end of body — Task 3 places its `<script>` tag there):

```javascript
const ORDER = ["layout.js", "intro.js", "tabs.js", "playground.js"];
```

- [ ] **Step 6: Run the full JS suite to confirm nothing broke**

Run: `node --test site/tests/*.test.mjs`
Expected: PASS. In particular `scripts-coexist.test.mjs`'s "every script the page ships is actually shipped by the workflow" and "the scripts load together without a redeclaration" tests must pass — the second one proves the IIFE wrapping actually works, in the same synthetic shared-scope context that caught the original `STORAGE_KEY` collision.

- [ ] **Step 7: Commit**

```bash
git add site/tabs.js site/tests/tabs.test.mjs .github/workflows/pages.yml site/tests/scripts-coexist.test.mjs
git commit -m "feat: add site/tabs.js, the tab-switching engine"
```

---

### Task 3: `site/index.html` + `site/style.css` — hero, tabs, content moves, Transliterator markup, bigger playground

**Files:**
- Modify: `site/index.html`
- Modify: `site/style.css`

**Interfaces:**
- Consumes: `site/tabs.js` (Task 2) — the `[role="tab"]`/`aria-controls`/`[role="tabpanel"]` contract it wires against.
- Produces: the real markup Task 4's `playground.js` changes will reach for by id: `translit-latin`, `translit-glyphs`, `translit-boot`, `translit-table`.

This task has no Python or Node test of its own — it's markup and styling, verified the same way the faces-and-layout spec's layout/toggle work was: by looking at the real page in a browser (Task 5). Steps here are "write this exact markup/CSS", not red/green.

- [ ] **Step 1: Rewrite the hero**

In `site/index.html`, replace the `<header class="masthead">` block:

```html
<header class="masthead">
  <p class="eyebrow">MATRIXLANG</p>
  <h1>Explore MatrixLang</h1>
  <p class="premise">A real programming language, invented for a film that
  never had one.</p>

  <div id="layout-switch" role="group" aria-label="Layout">
    <button data-layout-choice="auto" aria-pressed="true">Auto</button>
    <button data-layout-choice="desktop" aria-pressed="false">Desktop</button>
    <button data-layout-choice="mobile" aria-pressed="false">Mobile</button>
  </div>
</header>
```

(Only the `<h1>` and `.premise` text changed — the eyebrow and layout switch are untouched.)

- [ ] **Step 2: Replace the three prose sections and the example band with tabs**

Replace everything from `<section class="prose">` (the "Nothing in the film runs" section) through the closing `</div>` of `<div class="examples band">` with:

```html
<div class="tabs" role="tablist" aria-label="About MatrixLang">
  <button class="tab" role="tab" aria-selected="true"  aria-controls="tab-overview" id="tab-overview-btn">Overview</button>
  <button class="tab" role="tab" aria-selected="false" aria-controls="tab-faces"    id="tab-faces-btn">Two Faces</button>
  <button class="tab" role="tab" aria-selected="false" aria-controls="tab-how"      id="tab-how-btn">How It Works</button>
  <button class="tab" role="tab" aria-selected="false" aria-controls="tab-translit" id="tab-translit-btn">Transliterator</button>
</div>

<div role="tabpanel" id="tab-overview" aria-labelledby="tab-overview-btn" class="prose">
  <p><b>The code in <i>The Matrix</i> was never a programming language.</b>
  This is the one it pretended to have — invented, written down, and made to
  run.</p>

  <h2>Nothing in the film runs</h2>

  <p>The falling green characters are a visual effect. They have no grammar, no
  meaning attached to any symbol, and no way to be executed. Nobody could type
  them into a computer and get an answer back, because there is nothing behind
  them to answer.</p>

  <p>So this project is not "recreate the Matrix language." There is nothing to
  recreate. It is the other thing:</p>

  <p class="thesis">Invent the language the film pretended to have.</p>

  <p>A real one, with rules a program either follows or is rejected for breaking.
  It stores values, makes decisions, repeats work, defines functions that
  remember where they were written, and handles numbers, text, true and false,
  and lists. It is Turing-complete, which is the technical way of saying there
  is no arbitrary ceiling on what you can express in it. Programs live in files
  ending in <code>.rain</code>, and there is an interpreter that runs them, an
  interactive prompt for trying things a line at a time, and a test suite that
  has to stay green before any of this changes.</p>

  <p>When a program runs, its own source and its own output fall through a
  window as glyphs. Nothing on that screen is generated at random. Every
  character that falls came from the program you ran.</p>
</div>

<div role="tabpanel" id="tab-faces" aria-labelledby="tab-faces-btn" class="prose" hidden>
  <h2>Two faces</h2>

  <p>Every program can be written and read two ways. Here is one program, twice:</p>

  <div class="faces">
    <figure>
      <figcaption>The face you type</figcaption>
      <pre>construct i = 1
dejavu i <= 5
  trace i
  i = i + 1
flatline</pre>
    </figure>
    <figure>
      <figcaption>The face it wears</figcaption>
      <pre class="glyph">ｱ i ﾅ ｧ
ﾃ i ｾ ｫ
  ﾄ i
  i ﾅ i ﾀ ｧ
ﾗ</pre>
    </figure>
  </div>

  <p>Neither of those is a translation of the other. The program is read once,
  into a single structure, and that structure can be printed in either face —
  which is why the conversion loses nothing and can be run in both directions
  without drift. Feed the glyphs back in and the text comes out again — spacing
  normalized to the canonical form, and otherwise the program you started with.
  Run either face and the same thing happens.</p>

  <p>Names you chose and text you quoted stay as you wrote them here, because
  this is source you are meant to keep editing. The cascade window is stricter:
  it transliterates everything, so what falls is a wall with no Latin in it, and
  the table is reversible, so it can be read back rather than merely watched.</p>

  <p>The glyphs are ordinary Unicode half-width katakana. They are not the
  film's own glyph designs, and nothing here uses them.</p>
</div>

<div role="tabpanel" id="tab-how" aria-labelledby="tab-how-btn" class="prose" hidden>
  <h2>What it looks like</h2>

  <p>You do not need to know any of those keywords to get a program out of this.
  <b>Scribe</b> takes a plain-English request and writes the MatrixLang for it.
  It is not an AI: it is a fixed catalogue of phrasings it was taught in
  advance, matched exactly, so the same request always produces the same
  program — and a request outside the catalogue is refused with the closest
  phrasing it does know, rather than answered with a guess.</p>

  <p>Below is every example on this page: what was asked for, what Scribe wrote,
  and what that program printed. None of it was typed here by hand. It was
  produced by running the real interpreter, and a test compares this page
  against a fresh run, so an example cannot quietly go stale.</p>

  <p><code>construct</code> names a value, <code>trace</code> prints one,
  <code>dejavu</code> loops, <code>redpill</code> is <i>if</i>,
  <code>agent</code> defines a function, <code>jackout</code> returns from one,
  and <code>flatline</code> closes whichever of those you opened. There are
  fourteen keywords in total.</p>

  <div class="examples">
    <div class="example">
      <p class="request">add 5 and 3</p>
      <pre class="source">trace 5 + 3</pre>
      <pre class="example-glyph glyph" hidden>ﾄ ｫ ﾀ ｩ</pre>
      <button class="face-toggle">Show glyphs</button>
      <pre class="output">8</pre>
    </div>
    <div class="example">
      <p class="request">count from 1 to 5</p>
      <pre class="source">construct i = 1
dejavu i <= 5
  trace i
  i = i + 1
flatline</pre>
      <pre class="example-glyph glyph" hidden>ｱ i ﾅ ｧ
ﾃ i ｾ ｫ
  ﾄ i
  i ﾅ i ﾀ ｧ
ﾗ</pre>
      <button class="face-toggle">Show glyphs</button>
      <pre class="output">1
2
3
4
5</pre>
    </div>
    <div class="example">
      <p class="request">make a list of 1 2 3</p>
      <pre class="source">construct xs = [1, 2, 3]</pre>
      <pre class="example-glyph glyph" hidden>ｱ xs ﾅ ﾍｧﾈ ｨﾈ ｩﾎ</pre>
      <button class="face-toggle">Show glyphs</button>
      <p class="declares">This one declares rather than prints: it binds a list to
      the name <code>xs</code>, and printing is what <code>trace</code> does.</p>
    </div>
    <div class="example">
      <p class="request">if 5 is greater than 3 trace bigger</p>
      <pre class="source">redpill 5 > 3
  trace "bigger"
flatline</pre>
      <pre class="example-glyph glyph" hidden>ﾚ ｫ ｿ ｩ
  ﾄ "bigger"
ﾗ</pre>
      <button class="face-toggle">Show glyphs</button>
      <pre class="output">bigger</pre>
    </div>
    <div class="example">
      <p class="request">define a function that doubles</p>
      <pre class="source">agent double(n)
  jackout n * 2
flatline</pre>
      <pre class="example-glyph glyph" hidden>ｴ doubleｸnｹ
  ﾖ n ｶ ｨ
ﾗ</pre>
      <button class="face-toggle">Show glyphs</button>
      <p class="declares">This one declares too: <code>double</code> now exists,
      but nothing has called it yet, and a function that is never called has
      nothing to say.</p>
    </div>
  </div>
</div>

<div role="tabpanel" id="tab-translit" aria-labelledby="tab-translit-btn" class="prose" hidden>
  <h2>Transliterator</h2>

  <p>Type in either box — the other updates as you type. Both directions run
  the same reversible table the falling cascade decodes from, through the
  real interpreter this page loads, not a copy guessed at in the browser.</p>

  <div class="translit-grid">
    <div>
      <label for="translit-latin">Latin</label>
      <textarea id="translit-latin" rows="6" disabled placeholder="Type here…"></textarea>
    </div>
    <div>
      <label for="translit-glyphs">Glyphs</label>
      <textarea id="translit-glyphs" rows="6" class="glyph" disabled placeholder="…or type here"></textarea>
    </div>
  </div>

  <p class="translit-caption">A few glyphs in that box are not letters — one
  marks the next glyph as uppercase, another marks the next character as a
  literal passthrough rather than something encoded. The full table:</p>
  <details>
    <summary>Full table</summary>
    <pre id="translit-table" class="glyph"></pre>
  </details>

  <button id="translit-boot">Load the interpreter and try it</button>
</div>
```

- [ ] **Step 3: Resize the playground**

In the (unchanged) `#playground` section, change two attributes:

```html
        <label for="editor">MatrixLang</label>
        <textarea id="editor" rows="16" spellcheck="false"></textarea>
```

```html
      <div class="cascade-pane">
        <button id="cascade-face">Latin</button>
        <canvas id="cascade" width="960" height="540"></canvas>
      </div>
```

- [ ] **Step 4: Load `tabs.js`**

In `<body>`, add the script tag right before `playground.js`'s, at the very end of the file (after the SRI-pinned Pyodide `<script>`):

```html
<script src="tabs.js"></script>
<script src="playground.js"></script>
```

- [ ] **Step 5: Add the tab bar and Transliterator styling to `site/style.css`**

Add `.tabs` to the two places the file already shares one width token (search for `.masthead,\n.prose,\n.band {` — there are two occurrences, the base rule and the one inside `@container style(--layout: desktop)`):

```css
.masthead,
.prose,
.band,
.tabs {
  max-width: var(--measure);
  margin: 0 auto;
}
```

```css
@container style(--layout: desktop) {
  .masthead,
  .prose,
  .band,
  .tabs { max-width: var(--page); }
```

Then add two new sections, after "---- the examples ----" and before "---- the playground ----":

```css
/* ---- the tabs ---- */

.tabs {
  display: flex;
  gap: 2px;
  margin: 0 0 1.5rem;
  padding: 2px;
  background: var(--panel);
  border: 1px solid var(--edge);
  border-radius: 4px;
  overflow-x: auto;
}

.tab {
  margin: 0;
  padding: 0.5rem 0.9rem;
  border: none;
  border-radius: 3px;
  background: transparent;
  color: var(--muted);
  font: 11px/1.2 var(--mono);
  letter-spacing: 0.06em;
  white-space: nowrap;
  cursor: pointer;
}
.tab:hover { color: var(--head); background: #08120c; }
.tab[aria-selected="true"] {
  color: var(--green);
  background: #0a1a0f;
}

/* ---- the transliterator ---- */

.translit-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.75rem;
  margin: 1rem 0;
}
.translit-grid textarea { min-height: 8rem; }

@media (min-width: 40rem) {
  .translit-grid { grid-template-columns: 1fr 1fr; }
}

.translit-caption {
  margin: 0.5rem 0 0;
  color: var(--muted);
  font-size: 0.9rem;
}

#translit-table {
  margin-top: 0.5rem;
  max-height: 16rem;
  overflow-y: auto;
  white-space: pre-wrap;
}
```

- [ ] **Step 6: Run the JS test suite**

Run: `node --test site/tests/*.test.mjs`
Expected: PASS. (`index-html.test.mjs` only checks ids that `dom.mjs` lists, which does not yet include the Transliterator ids — Task 4 extends it. `assets.test.mjs` and `scripts-coexist.test.mjs` are unaffected by markup content.)

- [ ] **Step 7: Commit**

```bash
git add site/index.html site/style.css
git commit -m "feat: retitle the hero, tab the explanation, add the Transliterator markup"
```

---

### Task 4: `site/playground.js` — wire the Transliterator and share the boot button

**Files:**
- Modify: `site/playground.js`
- Modify: `site/tests/dom.mjs`
- Modify: `site/tests/index-html.test.mjs`
- Modify: `site/tests/playground.test.mjs`

**Interfaces:**
- Consumes: `glue.transliterate_text`, `glue.untransliterate_text`, `glue.readers_table` (Task 1); the real `#translit-latin`/`#translit-glyphs`/`#translit-boot`/`#translit-table` markup (Task 3).
- Produces: nothing further consumed elsewhere — this is the last task with test-visible behavior. Task 5 is verification only.

- [ ] **Step 1: Extend `dom.mjs`'s stub so it can track `disabled` as an initial state, and add the four new ids**

In `site/tests/dom.mjs`, `INITIAL` gains four entries (added after `"ask-operator"`):

```javascript
export const INITIAL = {
  "boot": { text: "Load the interpreter and try it" },
  "live": { hidden: true },
  "miss": { hidden: true },
  "request": {},
  "write": { text: "Write it" },
  "editor": {},
  "editor-face": { text: "Show glyphs" },
  "editor-glyph": { hidden: true },
  "run": { text: "Run it" },
  "cascade": {},
  "cascade-face": { text: "Latin" },
  "api-key": {},
  "ask-operator": { text: "Ask Operator" },
  "translit-latin": { disabled: true },
  "translit-glyphs": { disabled: true },
  "translit-boot": { text: "Load the interpreter and try it" },
  "translit-table": {},
};
```

In `loadPlayground()`, apply the new `disabled` field when building each stub element:

```javascript
  const elements = new Map(
    Object.entries(INITIAL).map(([id, start]) => {
      const element = new StubElement(id);
      element.hidden = start.hidden ?? false;
      element.disabled = start.disabled ?? false;
      element.textContent = start.text ?? "";
      return [id, element];
    }),
  );
```

- [ ] **Step 2: Write the failing harness-drift test for `disabled`**

In `site/tests/index-html.test.mjs`, add a third test after "the harness starts each element hidden exactly when the page does":

```javascript
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
```

- [ ] **Step 3: Run the JS suite to verify the new test passes (Task 3's markup already matches) and confirm the id-existence tests pass too**

Run: `node --test site/tests/index-html.test.mjs`
Expected: PASS — Task 3 already wrote `disabled` on `#translit-latin`/`#translit-glyphs` and not on `#translit-boot`/`#translit-table`, and all four ids exist. If anything fails here, it means Step 1's `INITIAL` entries don't match Task 3's actual markup — fix the mismatch before continuing.

- [ ] **Step 4: Write the failing behavior tests**

In `site/tests/playground.test.mjs`, replace the existing `"a failed boot leaves no control looking usable"` test with an extended version, and add a new test after it:

```javascript
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
```

- [ ] **Step 5: Run the tests to verify they fail**

Run: `node --test site/tests/playground.test.mjs`
Expected: FAIL — `playground.js` doesn't yet reference `translit-latin`/`translit-glyphs`/`translit-boot`, so `page.el("translit-latin")` is a valid stub element but nothing listens on it (the sync test fails: value stays `""`), and the failed-boot test fails because `translit-latin`/`translit-glyphs` are never disabled and `translit-boot` is never re-enabled (boot() doesn't know it exists yet).

- [ ] **Step 6: Update `boot()` in `site/playground.js` to drive both boot buttons**

Replace the `boot()` function:

```javascript
const BOOT_LABEL = "Load the interpreter and try it";
const BOOT_BUTTON_IDS = ["boot", "translit-boot"];

async function boot() {
  const buttons = BOOT_BUTTON_IDS.map(el);
  for (const button of buttons) {
    button.disabled = true;
    button.textContent = "Loading Python… (a few MB, once)";
  }
  try {
    await load();
  } catch (error) {
    // Without this the rejection surfaces only as "Uncaught (in promise)"
    // in a console the reader is not looking at, and the buttons sit on
    // "Loading Python…" forever. A CDN that is blocked, an offline tab,
    // and a wheel that failed to publish all look like that. The narrative
    // above is unaffected — that is the point of loading none of this
    // until asked.
    for (const button of buttons) {
      button.disabled = false;
      button.textContent = BOOT_LABEL;
    }
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
    for (const id of [
      "write", "run", "ask-operator", "editor-face", "cascade-face",
      "translit-latin", "translit-glyphs",
    ]) {
      const control = el(id);
      if (control) control.disabled = true;
    }
    return;
  }
  for (const button of buttons) button.hidden = true;
  el("live").hidden = false;
  el("translit-latin").disabled = false;
  el("translit-glyphs").disabled = false;
  el("translit-table").textContent = glue.readers_table();
}
```

- [ ] **Step 7: Add the Transliterator wiring functions and event listeners**

Add these two functions after `toggleExampleFace` (near the end of the functional section):

```javascript
function transliterateLatin() {
  el("translit-glyphs").value = glue.transliterate_text(el("translit-latin").value);
}

function untransliterateGlyphs() {
  el("translit-latin").value = glue.untransliterate_text(el("translit-glyphs").value);
}
```

Add the listeners in the wiring section at the bottom, alongside the other `addEventListener` calls:

```javascript
el("translit-boot").addEventListener("click", boot);
el("translit-latin").addEventListener("input", transliterateLatin);
el("translit-glyphs").addEventListener("input", untransliterateGlyphs);
```

- [ ] **Step 8: Run the tests to verify they pass**

Run: `node --test site/tests/*.test.mjs`
Expected: PASS, the full JS suite.

- [ ] **Step 9: Run the full Python suite and the two site checks once more**

Run: `python -m pytest -q && python site/checks/no_semantics.py && python site/checks/key_handling.py`
Expected: all pass. Nothing in this task touched `src/matrixlang/`, `server/`, or the checks themselves — this confirms it.

- [ ] **Step 10: Commit**

```bash
git add site/playground.js site/tests/dom.mjs site/tests/index-html.test.mjs site/tests/playground.test.mjs
git commit -m "feat: wire the Transliterator tab and share the boot button"
```

---

### Task 5: Full verification and a real browser check

**Files:** none (verification only).

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest -q`
Expected: PASS, same count as `main` plus the new tests from Task 1 and Task 4.

- [ ] **Step 2: Run the full JS suite**

Run: `node --test site/tests/*.test.mjs`
Expected: PASS, all files.

- [ ] **Step 3: Run both site checks**

Run: `python site/checks/no_semantics.py && python site/checks/key_handling.py`
Expected: both print their success line, unmodified by this feature (Global Constraints).

- [ ] **Step 4: Serve the assembled site locally and check it in a real browser**

The page needs to run from an HTTP origin (the CSP and `fetch("intro.json")`/`fetch("sse.py")` calls don't work from `file://`). Assemble it the same way the workflow does, using a locally built wheel:

```bash
python -m pip install build
python -m build --wheel --outdir dist/
mkdir -p /tmp/matrixlang-site-check
cp site/index.html site/style.css site/layout.js site/intro.js site/tabs.js site/playground.js site/glue.py site/examples.json site/intro.json /tmp/matrixlang-site-check/
cp -R site/fonts /tmp/matrixlang-site-check/fonts
cp web-ui/cascade.js /tmp/matrixlang-site-check/
cp server/sse.py /tmp/matrixlang-site-check/
cp dist/*.whl /tmp/matrixlang-site-check/
cd /tmp/matrixlang-site-check && python -m http.server 8123
```

Then, using the browser tool, open `http://localhost:8123/?intro=0` (or click "Skip" on the intro) and check:

1. The hero reads "Explore MatrixLang" with the shortened subtitle.
2. Four tabs are visible: Overview, Two Faces, How It Works, Transliterator. Overview is active on load, and its content includes the relocated "The code in *The Matrix* was never a programming language" sentence.
3. Clicking each tab shows only that tab's content; the example band appears inside How It Works.
4. Arrow-key navigation works: focus a tab, press Right/Left, the selection and panel follow, including wrap-around at both ends.
5. Open the Transliterator tab: both boxes are visibly disabled, with a "Load the interpreter and try it" button.
6. Press "Load the interpreter and try it" (either copy of the button). After it loads: both Transliterator boxes become usable, typing in Latin fills Glyphs and vice versa, and the "Full table" `<details>` has real content when expanded.
7. The playground below the tabs is visibly bigger than before (compare against `main` if unsure) and still works: write a request, run it, watch the cascade.
8. Resize to a narrow viewport (mobile) and confirm the tab bar scrolls horizontally rather than wrapping the page, and the Transliterator boxes stack to one column.

Report what was checked and any deviation found — this step is what actually confirms the feature works, not just that unit tests pass against stubs.

- [ ] **Step 5: Stop the local server**

Run: `pkill -f "http.server 8123"` (or close the terminal running it).

- [ ] **Step 6: Push and open the PR**

```bash
git push -u origin playground-tabs-transliterator
gh pr create --title "feat: playground tabs, a shorter hero, and a live Transliterator" --body "Implements the design in docs/superpowers/specs/2026-08-09-playground-tabs-and-transliterator-design.md.

Closes #103." --base main --head playground-tabs-transliterator
```

(Use `--body-file` with a prepared file instead of an inline `--body` string if the message needs any backticks or code spans — inline double-quoted strings can mangle them.)
