# Playground Faces and Layout Design — a desktop layout, and both faces on demand

Status: **Approved as a design. Nothing is implemented.**
Inputs: `2026-08-05-web-playground-design.md` (the playground this adjusts),
`TECHNICAL-OVERVIEW.md` §5.7 (presentation may be re-implemented; semantics may
not), `README.md` (the cascade is a glyph wall; the two faces round-trip),
GitHub #80 (this feature).

Three adjustments to the live playground. Two are wiring over data the page
already receives; one fixes a layout that never had a desktop form.

## Decisions

| # | Question | Decision |
| --- | --- | --- |
| FL-1 | What the desktop layout does | Prose stays 34rem at every width. The **playground** breaks out wide: editor left, cascade right. Examples go two-up in the same band. |
| FL-2 | Where the layout changes | One breakpoint at **60rem (960px)**. Below it, everything stacks exactly as today — the mobile layout is untouched. |
| FL-3 | The layout switch | Three states: **Auto · Desktop · Mobile**. Auto is the default. The other two override the viewport in both directions. |
| FL-4 | How the switch is expressed | `data-layout` on `<html>`. CSS keys off `[data-layout="…"]` and falls back to the media query when absent — one set of rules, not two. |
| FL-5 | Whether the layout choice persists | **Yes, in `localStorage`** — from `site/layout.js`, never from `playground.js`. |
| FL-6 | Which "Latin" the cascade shows | The existing `latin` face: glyph keywords, **your identifiers readable**. No new payload field. |
| FL-7 | Whether the cascade toggle covers output | **Yes.** One control switches statements `source ⇄ latin` and output `glyphs ⇄ text`. |
| FL-8 | The source toggle's effect on the editor | Shows the glyph face **beside** the ASCII. Never replaces what was typed. |
| FL-9 | Where example glyph faces come from | `render_glyph` at build time, into `examples.json`. Never typed by hand. |
| FL-10 | Scope creep guard | No change to `src/matrixlang/` or `server/sse.py`. No new faces on the wire. |

## 1. The layout, and why prose does not get wider

At 1440px the page currently uses **38% of the screen** — 544px of content
against 896px of empty space. Everything caps at 34rem, at every width, because
the original CSS applied a mobile reading measure globally and no desktop form
was ever written.

The fix is not to widen the text. A 34rem measure is correct: long lines are
harder to read, and the page's first job is being read. What should use the
space is the **playground**, where the editor and the cascade currently stack —
so the cascade sits below the fold and a reader scrolls away from the editor to
watch their own program run.

So: prose stays centred and narrow; the playground band goes full width with
editor and cascade side by side, and the five examples go two-up.

**The cascade keeps its explicit `aspect-ratio: 16 / 9`.** This is not
cosmetic. `Cascade.resize()` writes `canvas.width`/`canvas.height` from
`getBoundingClientRect()`, so any CSS height derived from those attributes feeds
its own output back through the `ResizeObserver` — which is exactly how the box
crept from 16:9 to a square before. Any new rule for the wide layout must give
the canvas a height that does not depend on its attributes.

## 2. The switch (FL-3, FL-4, FL-5)

Three states rather than two, because "Auto" has to remain expressible: a
visitor who never touches the control should get the breakpoint's answer, and a
two-state switch would force a wrong default on somebody.

```
[ Auto | Desktop | Mobile ]     →  <html data-layout="auto|desktop|mobile">
```

CSS reads the attribute first and the viewport second:

```css
/* the wide band, when the viewport says so and nothing overrides it */
@media (min-width: 60rem) {
  :root:not([data-layout="mobile"]) #playground { /* wide */ }
}
/* …and when the reader asks for it regardless of width */
:root[data-layout="desktop"] #playground { /* wide */ }
```

The two rules must produce the same layout. Stating the wide band once in a
shared place and referencing it from both selectors is the point — a second copy
is how the two drift.

### The `localStorage` exception, stated deliberately

`site/checks/key_handling.py` fails the build if `playground.js` mentions
`localStorage`, `sessionStorage`, `document.cookie`, or any other persistence
sink. That rule exists because `playground.js` handles the reader's API key.

A layout preference is not sensitive, and forgetting it on every visit would be
a worse page. So it persists — **from a separate `site/layout.js`**, which
touches no credential. The check stays scoped to `playground.js` and is not
loosened. The file that handles the key still cannot persist anything, which is
the property that was worth having.

`layout.js` must also apply the stored preference **before first paint** —
otherwise a reader who chose Desktop sees the mobile layout flash first.

## 3. The cascade toggle (FL-6, FL-7)

`sse.payload()` already sends every face this needs:

| event | glyph face | Latin face |
| --- | --- | --- |
| `statement` | `source` — `ｱ ｾｹｾ｡ｶ ﾅ ｫ` | `latin` — `ｱ total ﾅ ｫ` |
| `output` | `glyphs` — `ﾊﾁ｡ｵ･` | `text` — `wake up` |

So this is wiring. `playground.js` currently hardcodes `event.source` and
`event.glyphs`; it gains a `face` variable and picks the other pair when set.

**The Latin face is not plain ASCII, and that is the intended reading.** It is
`render_glyph` output: keywords, operators and digits stay glyphs, and only
identifiers and string contents come through readable. This is the same
`glyph_source=False` mode the README describes as putting "Latin identifiers
back", and it is what keeps the wall a glyph wall. A fully readable
`construct total = 5` would need a new field in `server/sse.py`, would
contradict the README's "pure glyph wall with no Latin in it", and is **out of
scope** (FL-10).

**Output toggles too — a deliberate divergence from `web-ui`.** The local UI
switches only the falling source and always draws output as glyphs. Here one
control governs both, because output is the half a reader most wants to read
back, and a "Latin" mode that left the answers unreadable would not be worth
having. Anyone comparing the two surfaces should read this as intended, not as
a bug.

## 4. The source toggle (FL-8, FL-9)

Each of the five examples, and the editor, can show the glyph face alongside the
ASCII.

**It never replaces what the reader typed.** Re-rendering normalizes whitespace
and drops comments, so a toggle that rewrote the editor would quietly eat work
mid-edit. The REPL's `:glyph` already resolved this the same way — it echoes
rather than replaces — and the same reasoning applies to a textarea somebody is
part-way through.

Example glyph faces are generated by `render_glyph` in
`site/generate_examples.py` and land in `examples.json` as a new field per
example. They are never hand-typed, for the reason every other example on the
page is generated: `tests/test_site_examples.py` regenerates the file and fails
if the committed copy differs, so a stale glyph face is a red build.

## 5. Module boundaries

| Path | Change | Why |
| --- | --- | --- |
| `site/layout.js` | **New.** The switch, `data-layout`, and its `localStorage` persistence. | Keeps persistence out of the file that handles the key. |
| `site/playground.js` | Add a `face` variable; pick `source`/`latin` and `glyphs`/`text`. | The cascade toggle. |
| `site/index.html` | The switch, the two toggles, the wide-band markup. | |
| `site/style.css` | The 60rem band, `data-layout` overrides, two-up examples. | |
| `site/generate_examples.py` | Emit a glyph face per example. | |
| `site/examples.json` | Regenerated. | Never hand-edited. |
| `tests/test_site_examples.py` | Assert the glyph face is present and round-trips. | |
| `src/matrixlang/`, `server/` | **Untouched.** | Both faces already exist on the wire. |

**Load-bearing assertions:**

- `site/checks/no_semantics.py` still passes: no toggle untransliterates in
  JavaScript. Every face is a string Python already rendered.
- `site/checks/key_handling.py` still passes **unmodified**: `playground.js`
  gains no persistence sink.

## 6. Testing

| Layer | Approach |
| --- | --- |
| Example glyph faces | The existing freshness test covers the new field for free — `committed == fresh` compares the whole structure. Add one assertion that each glyph face re-parses to the same tree as its ASCII, which is the round-trip property applied to what the page actually ships. |
| The two CI checks | Unchanged and still passing. That `key_handling.py` needs no edit is itself the assertion that the exception was taken safely. |
| Layout and toggles | DOM wiring with no Python surface. Verified in a real browser at both widths and in all three switch states. |

Not building a browser-automation rig for this. The playground's logic lives in
`glue.py` precisely so the suite covers it under CPython; the remainder is
presentation, and the one bug that mattered here — the canvas feedback loop —
was found by looking at the page, which is the check §10 of the cascade spec
already records as the one that works.

## 7. Deliberately out of scope

- **A fully-ASCII cascade face** — FL-6. Needs a new payload field and
  contradicts a documented decision.
- **Changing `web-ui/`** to match the output-toggle behaviour. The two may
  differ; §3 records why.
- **Widening the prose.** FL-1. The measure is correct.
- **Persisting anything else**, especially anything from `playground.js`.

## 8. Known risks

- **Two paths to one layout.** FL-4 has the media query and the attribute
  override producing the same wide band. If they are written twice they will
  drift. Stating it once and referencing it twice is the mitigation, and a
  visual check in all three switch states at both widths is how a drift is
  caught.
- **The canvas feedback loop can return.** Any new height rule for the wide
  layout that derives from the canvas attributes reintroduces it. §1 names it;
  the visual check at both widths is what would catch it.
- **Flash of the wrong layout** if `layout.js` applies the stored preference
  after first paint. §2 requires it before.
- **The `localStorage` exception could be read as permission.** It is not: the
  scope of `key_handling.py` is unchanged, and a future file that handles
  credentials gets no new latitude from this.
- **Nothing here is implemented.** Verify against the code, not against this
  file.
