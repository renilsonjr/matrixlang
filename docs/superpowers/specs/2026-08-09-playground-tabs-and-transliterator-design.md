# Playground Tabs and Transliterator Design — a shorter front page, and a live translator

Status: **Approved as a design. Nothing is implemented.**
Inputs: `2026-08-05-playground-faces-and-layout-design.md` (the layout this
builds on), `TECHNICAL-OVERVIEW.md` §5.7 (the browser may re-implement
presentation, never semantics — the rule this design has to satisfy),
`src/matrixlang/translit.py` (the reversible table the new tab exposes),
`site/glue.py` and `site/checks/no_semantics.py` (the sanctioned boundary
between the two halves), GitHub #103 (this feature).

The front page currently stacks three prose sections and a 4-example band,
all rendered at once, before a visitor reaches the live playground. This
retitles the hero, moves that explanation behind tabs so only one section is
on screen at a time, enlarges the playground, and adds a fourth tab: a live,
bidirectional Latin ⇄ glyph translator built on the interpreter the page
already loads.

## Decisions

| # | Question | Decision |
| --- | --- | --- |
| TT-1 | The new hero | `<h1>` becomes **"Explore MatrixLang"**, eyebrow unchanged (`MATRIXLANG`), subtitle shortened to one line. The current headline/thesis text is not deleted — it moves into the Overview tab. |
| TT-2 | Page order | **Welcome → Tabs → Playground**, in that order. The playground stays outside every tab — always visible, not itself a tab. |
| TT-3 | Tab set and default | Four tabs, in order: **Overview · Two Faces · How It Works · Transliterator**. Overview is selected on load. |
| TT-4 | What "reduce the text" means here | Reorganizing what is already written so one section renders at a time, not rewriting the prose. The 4-example band moves inside **How It Works**, since that is the section that introduces Scribe and the examples illustrate it. |
| TT-5 | Tab persistence | **None.** Every page load starts on Overview. No `localStorage`, no URL hash. |
| TT-6 | Tab implementation | New `site/tabs.js`, same vanilla/no-build pattern as `site/layout.js`. Real `role="tablist"/"tab"/"tabpanel"` and arrow-key navigation — this is new interactive chrome, unlike the examples' existing `hidden` toggling, so it needs real accessibility semantics from the start. |
| TT-7 | Playground size | Canvas base resolution **640×360 → 960×540**; editor `<textarea>` **10 rows → 16**. The wide desktop band (FL-1) already stretches both to fill the column; this raises the floor below that breakpoint. |
| TT-8 | Transliterator direction | **Bidirectional.** Two boxes, Latin and Glyphs; typing in either updates the other. No mode switch. |
| TT-9 | Transliterator engine | **Not a JS port.** `site/glue.py` gains two thin wrappers around the real `translit.transliterate`/`untransliterate`, called through Pyodide exactly like `write()`/`run()` already are. See §3 for why a JS table was rejected. |
| TT-10 | Transliterator availability before boot | The tab's two boxes are disabled until Pyodide has loaded, with its own copy of the **"Load the interpreter and try it"** button wired to the same boot handler the playground uses. Booting from either button unlocks both. |
| TT-11 | Scope creep guard | No change to `src/matrixlang/`, `server/sse.py`, or the wire format. No new payload fields. |

## 1. The hero and tab structure (TT-1 – TT-4)

The current page reads top-to-bottom: "Nothing in the film runs" → "Two
faces" → "What it looks like" (with the example band immediately after, not
inside it) → "Now run one yourself" → the playground. All of it renders at
once, so a visitor scrolls past everything to reach the interactive part.

The hero shrinks to a title and one line — "Explore MatrixLang" plus a short
subtitle — and the three prose sections become three tabs, keeping their
existing paragraphs verbatim. The example band, which today lives between the
third section and the playground with no section of its own, moves inside the
**How It Works** tab: it is Scribe's output, and "What it looks like" is the
section that introduces Scribe, so folding it in both gives the examples a
home and removes an always-rendered block from the default view.

The **Transliterator** tab is new (§3). The "Now run one yourself" paragraph
and the playground itself stay outside all tabs, per TT-2 — they're the
destination, not explanation, and should be reachable regardless of which tab
a visitor was last on.

## 2. Tabs (TT-5, TT-6)

```html
<div class="tabs" role="tablist" aria-label="About MatrixLang">
  <button role="tab" aria-selected="true"  aria-controls="tab-overview" id="tab-overview-btn">Overview</button>
  <button role="tab" aria-selected="false" aria-controls="tab-faces"    id="tab-faces-btn">Two Faces</button>
  <button role="tab" aria-selected="false" aria-controls="tab-how"      id="tab-how-btn">How It Works</button>
  <button role="tab" aria-selected="false" aria-controls="tab-translit" id="tab-translit-btn">Transliterator</button>
</div>
<div role="tabpanel" id="tab-overview" aria-labelledby="tab-overview-btn">…</div>
<div role="tabpanel" id="tab-faces"    aria-labelledby="tab-faces-btn"    hidden>…</div>
<div role="tabpanel" id="tab-how"      aria-labelledby="tab-how-btn"      hidden>…</div>
<div role="tabpanel" id="tab-translit" aria-labelledby="tab-translit-btn" hidden>…</div>
```

`site/tabs.js` toggles `aria-selected` and `hidden`, and handles Left/Right
(or Up/Down) arrow keys moving focus between tab buttons per the standard
tabs pattern — this is new interactive UI, not a toggle over existing markup,
so it gets real keyboard support rather than click-only handling.

No persistence (TT-5): unlike the layout switch, which is a standing
preference worth remembering, which tab was open is transient — a returning
visitor re-reading the page is not worse off starting at Overview again, and
skipping `localStorage` here keeps `tabs.js` simple and keeps the
`localStorage` exception carved out for `layout.js` (FL-5) from spreading to
a second file.

## 3. The Transliterator, and why it is not a JS port (TT-8 – TT-10)

`src/matrixlang/translit.py` is a small, pure, deterministic table — letters,
digits, and punctuation mapped to half-width katakana, plus a SHIFT marker
for case and an ESCAPE marker for literal glyphs, both documented in the
module's own docstring as required for the encoding to be reversible for
*all* text. A JS reimplementation of that table looked, at first, like the
obvious choice: instant on load, no boot wait, and if generated from Python
into a JSON file rather than hand-copied, no risk of the two falling out of
sync.

That reasoning does not survive contact with `site/checks/no_semantics.py`,
which fails the build if any file in `site/*.js` calls
`transliterate`/`untransliterate` by name, declares a glyph-table constant,
or contains a half-width katakana literal — and `TECHNICAL-OVERVIEW.md` §5.7
explains why the gate exists: a hand-written `web/interpreter.js` once
drifted from the real interpreter until the two disagreed about the
language, and it was deleted rather than patched. The rule that came out of
it, stated plainly: **the browser may re-implement presentation, never
semantics.** Owning a copy of the translit table — even one generated from
Python, even shipped as data rather than code — is the exact shape of thing
that produced the original defect. Pre-rendering into a JSON file the way
`site/generate_intro.py` does for the intro's two fixed lines does not apply
either: that pattern only works for a known, finite set of strings decided
at build time, and a translator has to handle whatever a visitor types.

So the Transliterator calls the real thing. Two additions to `site/glue.py`:

```python
def transliterate_text(text: str) -> str:
    return translit.transliterate(text)

def untransliterate_text(glyphs: str) -> str:
    return translit.untransliterate(glyphs)
```

Thin wrappers, in the same spirit `glue.py`'s docstring already states for
`write()`/`run()`: it owns no language logic, it only sequences calls into
the real package. `playground.js` calls these through Pyodide exactly as it
already calls `write()` for Scribe.

**Cost:** the tab cannot work until Pyodide has booted — the same one-time,
cached 13 MB fetch the rest of the playground already gates behind "Load the
interpreter and try it." TT-10 makes that boundary visible rather than
surprising: the tab's two boxes render disabled, with its own copy of that
same button and label, wired to the same boot handler as the playground's.
Clicking either button boots once and unlocks both — there is one boot
state, not two.

**UI:** two `<textarea>` boxes side by side, labelled Latin and Glyphs. Input
in either fires the corresponding wrapper and writes the result into the
other box (setting `.value` directly, not dispatching a synthetic `input`
event, so the two handlers cannot re-trigger each other). A short caption
below the boxes explains the SHIFT and ESCAPE marker glyphs that can appear
in output, so they read as intentional rather than as mangled text.

## 4. The playground (TT-7)

`#cascade`'s base `width`/`height` attributes move from 640×360 to 960×540;
the `aspect-ratio: 16 / 9` rule that exists specifically to stop the
`ResizeObserver` feedback loop (§1 of the faces-and-layout spec) is untouched
— only the base resolution changes, not the sizing mechanism. `#editor`'s
`rows` attribute moves from 10 to 16. Both changes are floor-raising: the
wide desktop band already stretches the canvas to `max-width: none` and the
grid gives the editor pane real width, so the visible effect is largest on
the layouts that don't yet have that band (mobile, and desktop pinned to the
Mobile switch state).

## 5. Module boundaries

| Path | Change | Why |
| --- | --- | --- |
| `site/tabs.js` | **New.** Tab switching, ARIA wiring, arrow-key navigation. | Keeps tab logic out of `layout.js` and `playground.js`, matching the one-concern-per-file pattern those two already set. |
| `site/glue.py` | Add `transliterate_text`, `untransliterate_text`. | The sanctioned Python-side surface for anything the JS half needs from the package — see its own docstring. |
| `site/playground.js` | Wire the Transliterator boxes to the two new `glue.py` calls; share the boot handler with the existing `#boot` button. | |
| `site/index.html` | New hero copy, tab markup, Transliterator tab markup, resized canvas/textarea attributes. | |
| `site/style.css` | Tab bar and panel styling, Transliterator box layout. | |
| `src/matrixlang/`, `server/` | **Untouched.** `translit.py` already has everything this needs. | |

**Load-bearing assertions:**

- `site/checks/no_semantics.py` still passes, unmodified: no new `.js` file
  calls `transliterate`/`untransliterate`, holds a glyph literal, or declares
  a table. The Transliterator's JS side only calls into `glue.py`.
- `site/checks/key_handling.py` still passes, unmodified: neither `tabs.js`
  nor the Transliterator wiring in `playground.js` touches `localStorage` or
  any other persistence sink (TT-5 rules out the one place that temptation
  could have entered).

## 6. Testing

| Layer | Approach |
| --- | --- |
| `transliterate_text`/`untransliterate_text` | Covered by the existing `tests/test_site_glue.py` pattern — imported and called directly under CPython, same as `write()`/`run()` today. Assert round-trip (`untransliterate_text(transliterate_text(s)) == s`) for a few representative strings, mirroring `translit.py`'s own fuzz property. |
| `no_semantics.py`, `key_handling.py` | Unchanged and still passing — the assertion that no exception was taken. |
| Tabs, ARIA, keyboard nav, sizing | DOM wiring with no Python surface. Verified in a real browser: all four tabs reachable by click and by arrow key, default tab on load, disabled Transliterator boxes before boot and enabled after, at both the Mobile and Desktop layout switch states. |

Not building a browser-automation rig for this, for the same reason the
faces-and-layout spec gave: the logic that can drift lives in `glue.py`,
where the suite already reaches it under CPython, and the rest is
presentation checked by looking at the page.

## 7. Deliberately out of scope

- **Rewriting the prose.** TT-4 — this reorganizes existing paragraphs, it
  does not shorten or rewrite them.
- **Persisting the active tab.** TT-5.
- **A JS-side transliteration table in any form**, generated or hand-written.
  §3 — this is the one option considered and rejected, not merely unstated.
- **Changing `server/sse.py` or any wire field.** TT-11 — the Transliterator
  needs no new payload; it calls the package directly through Pyodide.

## 8. Known risks

- **The Transliterator looks broken before boot.** Disabled boxes with no
  explanation would read as a bug rather than a gate. TT-10's own copy of the
  boot button and label is the mitigation; if it is dropped for space, some
  other explicit cue must take its place.
- **Two boot buttons could drift into two boot *paths*.** If the
  Transliterator's button ever gets its own click handler instead of calling
  the playground's existing one, the "one boot state, not two" property in
  §3 breaks silently. The mitigation is structural — share the handler, not
  just the label — and worth a comment at the call site saying so.
- **Tab keyboard support is easy to half-implement.** Click-only tabs would
  work for a mouse user and silently fail an arrow-key/screen-reader check.
  TT-6 calls this out explicitly so it isn't dropped as "just a details.md
  toggle" during implementation.
- **Nothing here is implemented.** Verify against the code, not against this
  file.
