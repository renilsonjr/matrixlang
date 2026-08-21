# X Matrix Theme — Design

**Date:** 2026-08-21
**Status:** Draft — brainstormed, awaiting plan
**Scope:** Timeline-first Full Matrix theme for X.com (Twitter), as a browser extension. Side-project inside `matrixlang`, zero touches to `src/`, `server/`, `site/`, `tests/`, or CI on `main`.

## 1. Goal

Give X.com's **timeline** the MatrixLang look — the same palette, typography, panel chrome, glyph face, and falling cascade that the language's own site uses — without touching any line of X's code and without touching any line of `matrixlang`'s main.

A reader who knows `site/style.css` should recognize X's timeline immediately: black/green, JetBrains Mono, panel borders, phosphor glow, half-width katakana headers, faint rain behind the feed, and a single global toggle that flips every visible tweet between its Latin face and its glyph wall.

v1 is **timeline only**. Profile, DMs, search, etc. are out of scope but the architecture must not make them hard later.

## 2. Non-goals

- No X API usage, no `webRequest`, no credential handling, no data persistence beyond one string (`glyph`|`latin`).
- No publish to Chrome Web Store in v1 — Load unpacked is the distribution.
- No mutation of tweet semantics — transliteration is purely visual, fully reversible, original is always kept.
- No changes to `matrixlang`'s interpreter, Scribe, Operators, `site/`, `web-ui/`, or test suite. The extension is additive.

## 3. Architecture — Layered extension

Three visual layers plus one glue layer, each isolated so any one can fail without breaking X or the others. Mirrors how `site/layout.js` (persisted switch), `site/playground.js` (orchestration), and `site/glue.py` (rendering) are separated on the narrative page.

```
matrixlang/
  extensions/
    x-matrix-theme/          ← only folder this feature touches
      manifest.json          Manifest V3, document_start, x.com + twitter.com
      theme.css              paint only — palette, Mono, borders, glow
      rain.js                canvas + draw loop (fork of web-ui/cascade.js)
      glyph.js               CHAR_MAP + walk + apply/restore
      content.js             glue: inject CSS, start rain, mount toggle,
                             persist pref, observe timeline
      checks/
        no_main_import.py    no import of src/matrixlang
        manifest_hosts.py    hosts == x.com + twitter.com only
      icons/                 optional
      README.md              Load unpacked + acceptance checklist
```

**Isolation guarantees:**

- No `import matrixlang`, no `from server.sse`, no `fetch("glue.py")`. The glyph table and cascade loop are **copied** into `glyph.js` / `rain.js` with a `// copied from <path> @ <commit>` comment, the same way `web-ui/cascade.js` is copied to `_site/` in `.github/workflows/pages.yml`. `site/checks/no_semantics.py` stays green because `site/` never sees the copy.
- `extensions/` is not in `pyproject.toml` `pythonpath`, not collected by `pytest`, not copied by the Pages assemble step. `main` CI stays blind to the extension; full suite stays 1399 green without running extension code.

## 4. Components

### 4.1 `theme.css` — Paint

Palette is a verbatim copy of `site/style.css:10-20`:

```
--bg: #05070a; --panel: #0b0f14; --edge: #16202a;
--green: #00ff41; --dim: #0d7a2a; --head: #ccffcc;
--text: #c8d4cd; --muted: #5d6f66; --white: #e8f0ea; --amber: #d68a2a;
--mono: "JetBrains Mono", "SF Mono", Menlo, monospace;
```

Timeline-first selectors (stable `data-testid` anchors):

- `body, [data-testid="primaryColumn"]` → `background: var(--bg)`
- `article[data-testid="tweet"]` → `background: var(--panel); border: 1px solid var(--edge); border-radius: 4px` (same as `.example` / `pre`)
- `div[data-testid="tweetText"]` → `font-family: var(--mono); color: var(--text)` in Latin mode; `color: var(--green); text-shadow: 0 0 6px rgba(0,255,65,0.35)` in glyph mode via `html[data-ml-face="glyph"]`
- Column header → glyph label via CSS content swap (e.g. `Home → ﾎﾑﾒ`), DOM header text kept hidden for accessibility
- Promoted posts → `background: #120d06; border-left: 3px solid var(--amber)` (same `site/style.css:384-391` `.warning`)

Injected at `document_start` as `<link rel="stylesheet">` so X's stylesheet doesn't flash first (same rationale as `site/layout.js` before `style.css`). `!important` only where X inline styles force it, documented per rule. All transitions are `prefers-reduced-motion` gated.

### 4.2 `rain.js` — Cascade canvas

```html
<canvas id="ml-rain" style="position:fixed; inset:0; width:100vw; height:100vh;
  z-index:0; opacity:0.12; pointer-events:none; background:#000;">
```

First child of `body`. Timeline column is `position:relative; z-index:1` so opaque tweet panels paint over the rain — rain is visible in gaps/margins, not through text (like the playground's `aspect-ratio: 16/9` wall behind code).

- **Loop:** fork of `web-ui/cascade.js` draw loop, 33ms timestep, `requestAnimationFrame`, `font: 13px JetBrains Mono`, `color: #00ff41` with trailing fade. No import — literal copy.
- **Sizing:** `canvas.width = innerWidth * devicePixelRatio`, same for height, on `resize` + `ResizeObserver` on `body`. No layout dependency on `canvas.width` attributes (avoids `site/style.css:348-353` feedback loop).
- **Lifecycle:** `Rain.start()` at injection; `document.visibilitychange` → pause when hidden; `matchMedia('(prefers-reduced-motion: reduce)')` → never start / remove canvas (mirrors `site/style.css:467-470` + `intro.js` guard).
- **Isolation:** no DOM reads beyond its own canvas, no network, no storage. If it throws, `content.js` catches and continues — glyph toggle still works.

Cost: ~3-5% CPU at 1080p, low opacity — same profile as the playground's wall.

### 4.3 `glyph.js` — Transliteration

- **Table:** literal `CHAR_MAP` object copied from `src/matrixlang/render.py` (half-width katakana for A-Z / 0-9 / basic Latin). Not an import. Commented with source commit. Verifiable by a smoke check in `extensions/checks/` — not in `main` suite.
- **Functions:**
  - `transliterate(str): string` — pure, maps each codepoint or leaves emoji/katakana as-is
  - `applyToTweet(articleEl)` — finds `div[data-testid="tweetText"]`, saves `el.dataset.mlOriginal = el.innerText` on first run, sets `el.innerText = transliterate(original)`, appends `<div class="ml-original">↳ original: …</div>` in muted style
  - `restoreTweet(articleEl)` — restores from `dataset.mlOriginal`, removes the helper line
  - `enableAll() / disableAll()` — walks every `article[data-testid="tweet"]` on page
- **Skips:** `a[href]`, `img`, `svg` — links stay clickable, hrefs unchanged. Hashtags are transliterated visually but link targets stay.
- **Contract:** this file is the only place that knows the table — `content.js` and `theme.css` never do (same rule as `site/glue.py` owning `render_glyph` while `site/playground.js` never calls `transliterate()` — enforced by `site/checks/no_semantics.py` on the main side).

### 4.4 `content.js` — Glue + observer + persistence

- **Injection order at `document_start`:** `theme.css` is already injected by the manifest's `content_scripts.css` — `content.js` does not re-inject it → create `#ml-rain` → `Rain.start()` → wait for `header` / `[data-testid="primaryColumn"]` via `MutationObserver` on `body` (no polling) → mount one global toggle:
  ```html
  <button id="ml-face-toggle" aria-pressed="false">Glyph ◐ Latin</button>
  ```
  Placed in X's top bar (right of Search, fallback to header `nav`). Label flips to `Latin ◑ Glyph` when active, `aria-pressed` tracks it (same `sync()` pattern as `site/layout.js:107-115`).

- **Persistence:** `chrome.storage.local` key `ml-x-theme-face` → `"glyph"|"latin"` (default `"latin"`), `try/catch` on read/write (storage blocked never crashes). Applied as `document.documentElement.dataset.mlFace = await readPref()` before first paint where possible — no flash of wrong face on reload, like `site/layout.js:92` pre-paint `dataset.layout`.

- **Timeline observer:** one `MutationObserver` on `[data-testid="primaryColumn"]` (`childList` + `subtree`) + `requestAnimationFrame` batching; for each added `article[data-testid="tweet"]`, if face is `glyph`, call `Glyph.applyToTweet(article)`.

- **SPA navigation:** listen for `history.pushState` / `popstate` — X's client-side nav (timeline → profile → home) — re-apply face to the newly visible column.

- **No X API:** never fetches `api.twitter.com` / `api.x.com`, never adds auth headers, never reads cookies — purely DOM + canvas, like `site/playground.js` never owns `transliterate()`.

### 4.5 `manifest.json`

Manifest V3, minimal permissions:

```json
{
  "manifest_version": 3,
  "name": "MatrixLang — X Theme",
  "version": "0.1.0",
  "description": "Full Matrix theme for X.com timeline — palette, Mono, glyph toggle, faint rain.",
  "permissions": ["storage"],
  "host_permissions": ["*://x.com/*", "*://twitter.com/*"],
  "content_scripts": [{
    "matches": ["*://x.com/*", "*://twitter.com/*"],
    "run_at": "document_start",
    "js": ["rain.js", "glyph.js", "content.js"],
    "css": ["theme.css"]
  }]
}
```

No `webRequest`, no `cookies`, no `<all_urls>`, CSP `script-src 'self'`.

## 5. Data flow

```
User loads x.com/home
  → manifest injects theme.css + rain.js + glyph.js + content.js at document_start
  → content.js reads chrome.storage.local (face) → sets html[data-ml-face]
  → Rain.start() → fixed canvas behind feed (or skips if reduced-motion)
  → observer watches primaryColumn
  → for each tweet already in DOM + each new tweet added by X's infinite scroll:
      if face == "glyph" → Glyph.applyToTweet() (save original, swap, append helper)
      else → leave Latin
User clicks [Glyph ◐ Latin]
  → toggle face → writePref() → set html[data-ml-face] → Glyph.enableAll() / disableAll()
  → future tweets observed in that face automatically
```

## 6. Safety & error handling

- **Fail-open per layer:** each layer is `try/catch` isolated — `theme.css` load failure doesn't kill rain/glyphs; rain throw doesn't kill toggle; glyph table gap leaves that tweet Latin. No layer throws into X's JS.
- **No persistence of X data:** storage holds only one string. No tweet text is stored or sent.
- **Reduced motion:** `prefers-reduced-motion: reduce` → rain never starts / is removed; glow animation disabled. Also `visibilitychange` → pause rain when tab hidden.
- **Host creep:** manifest allows only `x.com` + `twitter.com`. No `webRequest` / `cookies` / `api.x.com`.
- **Selector fragility:** if X renames `data-testid="tweet"`, we degrade to Latin + faint rain — not a crash. README notes the one selector to update. Observer never walks into ad iframes.
- **Main isolation:** `extensions/` not in `pythonpath`, not collected by `pytest`, not copied by Pages assemble. Main suite and `site/checks/` stay green without extension code.

## 7. Testing & verification

**Main (unchanged, must stay green):**

```
PYTHONPATH=src .venv/bin/python -m pytest -q
python site/checks/no_semantics.py
python site/checks/key_handling.py
```

`extensions/` not collected.

**Extension's own checks (like `site/checks/`):**

- `extensions/x-matrix-theme/checks/no_main_import.py` — greps for `from matrixlang` / `import matrixlang` / `server/sse` → must be empty
- `extensions/x-matrix-theme/checks/manifest_hosts.py` — parses `manifest.json` → hosts must be only `x.com` + `twitter.com`

**Manual acceptance (Load unpacked → 5-min pass, like site Task 1 Step 9):**

1. Load unpacked → `x.com/home` → faint rain behind feed, header glyph label, toggle says Latin
2. Click `[Glyph ◐ Latin]` → every visible tweet flips to glyph with `↳ original:` underneath; button flips
3. Scroll — new tweets appear in glyph face automatically; toggle back → all revert, including new ones
4. SPA: Home → Profile → Home → timeline still in chosen face, rain still behind
5. `prefers-reduced-motion: reduce` (DevTools → Rendering → Emulate) → rain canvas absent, toggle still works
6. Block `theme.css` in DevTools → tweets still toggle (layers isolated)

Checklist lives in `extensions/x-matrix-theme/README.md`.

## 8. Future

- v1 is timeline-only. DMs, profile, search are not excluded by design — the same `applyToTweet` pattern and `data-testid` anchoring extends to them without new architecture.
- If glyph table needs to match a future `render.py` change, the copy is re-copied and the `checks/no_main_import.py` + manual toggle pass re-run — no shared import is introduced.

## 9. Decisions

| FL | Decision | Rationale |
|----|----------|-----------|
| 1 | Extension lives in `extensions/x-matrix-theme/`, isolated | Side-project guarantee: no `src/`/`site/` touch, main CI blind |
| 2 | `theme.css` is paint-only | Separation of concerns; testable without JS |
| 3 | Rain is fixed canvas behind feed, always-on faint, pausable | Full Matrix without obscuring opaque tweet panels; respects motion |
| 4 | Glyph table is copied, not imported | Isolation from `src/`; same rationale as `web-ui/cascade.js` copy to `_site/` |
| 5 | Global toggle only (not per-tweet) | Timeline-first YAGNI; matches playground's one cascade toggle |
| 6 | `chrome.storage.local` for pref, `data-ml-face` attribute | Mirrors `site/layout.js` `localStorage` + `data-layout` pattern |
| 7 | `MutationObserver` on `primaryColumn` + SPA nav handling | X is SPA with infinite scroll — polling is never used |
