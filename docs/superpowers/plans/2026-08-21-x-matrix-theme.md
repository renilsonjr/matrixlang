# X Matrix Theme Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship a Manifest V3 browser extension that themes X.com's timeline in Full Matrix — palette + Mono + glyph toggle + faint rain — as an isolated side-project that never touches `main`.

**Architecture:** Layered extension in `extensions/x-matrix-theme/` — `theme.css` (paint), `rain.js` (fixed canvas fork of `web-ui/cascade.js`), `glyph.js` (copied half-width katakana table + DOM walk), and `content.js` (glue: inject, mount one global `[Glyph ◐ Latin]` toggle, persist via `chrome.storage.local` + `data-ml-face`, observe timeline with `MutationObserver`). Each layer fails open.

**Tech Stack:** Plain HTML/CSS/JS, Chrome Manifest V3, no build step, no new dependencies. Copy, don't import.

## Global Constraints

- `extensions/x-matrix-theme/` is the **only** folder this feature touches. `src/matrixlang/`, `server/sse.py`, `site/`, `tests/`, `.github/workflows/pages.yml`, `pyproject.toml` are untouched. No imports from `src/` or `server/` — glyph table and cascade loop are copied with a `// copied from <path> @ <commit>` comment.
- `manifest.json` is Manifest V3, `permissions: ["storage"]` only, `host_permissions` and `content_scripts.matches` are exactly `["*://x.com/*", "*://twitter.com/*"]` — no `webRequest`, `cookies`, `<all_urls>`, or `api.x.com`.
- Palette is verbatim from `site/style.css:10-20` (`--bg #05070a`, `--panel #0b0f14`, `--edge #16202a`, `--green #00ff41`, etc.). Typography is `JetBrains Mono` first.
- Rain is a `position:fixed; inset:0; opacity:0.12; pointer-events:none; background:#000` canvas behind the feed (`primaryColumn` at `z-index:1`). It never depends on `canvas.width` for layout, pauses on `visibilitychange` and `prefers-reduced-motion: reduce`, uses 33ms `requestAnimationFrame` timestep.
- Glyph transliteration is visual only, fully reversible, original kept in `dataset.mlOriginal` + `↳ original:` helper. Only `glyph.js` knows `CHAR_MAP`.
- Global toggle only — one `#ml-face-toggle` in X's top bar, `aria-pressed` + `sync()` like `site/layout.js`, persisted in `chrome.storage.local` key `ml-x-theme-face` default `"latin"`, applied as `html[data-ml-face]` before first paint where possible.
- Fail-open per layer; no layer throws into X's JS. No tweet text is stored or sent. Extension never fetches `api.twitter.com`.
- `extensions/` is not in `pythonpath`, not collected by `pytest`, not copied by Pages assemble. Main suite stays 1399 green without running extension code.

---

### Task 1: Scaffold + `manifest.json` + `theme.css` — the paint layer

**Files:**
- Create: `extensions/x-matrix-theme/manifest.json`
- Create: `extensions/x-matrix-theme/theme.css`
- Create: `extensions/x-matrix-theme/README.md` (scaffold section only — full checklist in Task 5)
- Create: `extensions/x-matrix-theme/icons/` (placeholder — 128px PNG, can be 1x1 green square for v1)

**Interfaces:**
- Consumes: `site/style.css` palette (copied verbatim).
- Produces: `theme.css` injected by manifest `content_scripts.css` at `document_start`; `manifest.json` with exact hosts/permissions. Later tasks depend on `html[data-ml-face="glyph"]` selector already being paint-ready.

- [ ] **Step 1: Create the folder and `manifest.json` verbatim**

Create `extensions/x-matrix-theme/manifest.json`:

```json
{
  "manifest_version": 3,
  "name": "MatrixLang — X Theme",
  "version": "0.1.0",
  "description": "Full Matrix theme for X.com timeline — palette, Mono, glyph toggle, faint rain.",
  "permissions": ["storage"],
  "host_permissions": ["*://x.com/*", "*://twitter.com/*"],
  "content_scripts": [
    {
      "matches": ["*://x.com/*", "*://twitter.com/*"],
      "run_at": "document_start",
      "js": ["rain.js", "glyph.js", "content.js"],
      "css": ["theme.css"]
    }
  ]
}
```

Note: `rain.js` / `glyph.js` / `content.js` don't exist yet — manifest listing them now is intentional; Chrome ignores missing content scripts at install time until they appear, and the plan lands them in Tasks 2-4. No `webRequest`, no `cookies`.

- [ ] **Step 2: Create `theme.css` — palette + timeline selectors verbatim**

Create `extensions/x-matrix-theme/theme.css`:

```css
/* X Matrix Theme — paint only. No JS. */
/* Palette verbatim from site/style.css:10-20 */
:root {
  --ml-bg: #05070a;
  --ml-panel: #0b0f14;
  --ml-edge: #16202a;
  --ml-green: #00ff41;
  --ml-dim: #0d7a2a;
  --ml-head: #ccffcc;
  --ml-text: #c8d4cd;
  --ml-muted: #5d6f66;
  --ml-white: #e8f0ea;
  --ml-amber: #d68a2a;
  --ml-mono: "JetBrains Mono", "SF Mono", Menlo, monospace;
}

/* Timeline column — the reading column */
body,
[data-testid="primaryColumn"] {
  background: var(--ml-bg) !important;
}

/* Tweet cards */
article[data-testid="tweet"] {
  background: var(--ml-panel) !important;
  border: 1px solid var(--ml-edge) !important;
  border-radius: 4px !important;
}

/* Tweet text — Latin face */
div[data-testid="tweetText"] {
  font-family: var(--ml-mono) !important;
  color: var(--ml-text) !important;
}

/* Glyph face — green + glow, driven by html[data-ml-face="glyph"] */
html[data-ml-face="glyph"] div[data-testid="tweetText"] {
  color: var(--ml-green) !important;
  text-shadow: 0 0 6px rgba(0, 255, 65, 0.35);
}

/* Preserve original helper underneath glyph tweet */
.ml-original {
  margin-top: 4px;
  color: var(--ml-muted);
  font: 10px/1.4 var(--ml-mono);
  white-space: pre-wrap;
}

/* Column header glyph swap — keep DOM header for a11y, hide visually when needed */
html[data-ml-face="glyph"] [data-testid="primaryColumn"] h2 {
  /* optional: add glyph pseudo if header exists — left empty for v1, ready for B chrome later */
}

/* Promoted posts — amber warning like site .warning */
[data-testid="tweet"] [data-testid="placementTracking"] {
  background: #120d06 !important;
  border-left: 3px solid var(--ml-amber) !important;
}

/* Top bar toggle — injected by content.js, styled here so CSS owns paint */
#ml-face-toggle {
  margin: 0 0 0 12px;
  padding: 0.3rem 0.7rem;
  border: 1px solid var(--ml-dim);
  border-radius: 3px;
  font: 11px/1.2 var(--ml-mono);
  color: var(--ml-muted);
  background: transparent;
  cursor: pointer;
}
#ml-face-toggle:hover { color: var(--ml-head); background: #08120c; }
#ml-face-toggle[aria-pressed="true"] { color: var(--ml-green); background: #0a1a0f; }

/* Rain canvas sits behind feed — feed paints over it */
#ml-rain {
  position: fixed;
  inset: 0;
  width: 100vw;
  height: 100vh;
  z-index: 0;
  opacity: 0.12;
  pointer-events: none;
  background: #000;
}
[data-testid="primaryColumn"] { position: relative; z-index: 1; }

/* Reduced motion — no glow animation */
@media (prefers-reduced-motion: reduce) {
  html[data-ml-face="glyph"] div[data-testid="tweetText"] { text-shadow: none; }
}
```

- [ ] **Step 3: Create a minimal `README.md` scaffold (full checklist lands in Task 5)**

Create `extensions/x-matrix-theme/README.md` with at least:

```markdown
# MatrixLang — X Theme

Full Matrix theme for X.com timeline. Isolated extension — Load unpacked.

## Install

1. Open `chrome://extensions` → Developer mode ON → Load unpacked → `extensions/x-matrix-theme`
2. Same for Firefox `about:debugging`

## Checks (extension-only)

- `python extensions/x-matrix-theme/checks/no_main_import.py` — no import of src/
- `python extensions/x-matrix-theme/checks/manifest_hosts.py` — hosts == x.com + twitter.com

## Manual acceptance (timeline-first)

See Task 5 checklist.
```

- [ ] **Step 4: Verify `extensions/` does not affect main**

Run:

```bash
git status --short | grep -E "src/|server/|site/|tests/|\.github/" && echo "FAIL — main touched" || echo "main untouched — OK"
PYTHONPATH=src .venv/bin/python -m pytest tests/test_site_examples.py tests/test_site_glue.py -q
python site/checks/no_semantics.py
python site/checks/key_handling.py
```

Expected: no `src/`/`site/`/`tests/` in status; site tests pass; both checks pass.

- [ ] **Step 5: Validate manifest JSON**

Run:

```bash
python -m json.tool extensions/x-matrix-theme/manifest.json > /dev/null && echo "manifest JSON valid"
```

Expected: `manifest JSON valid`.

- [ ] **Step 6: Commit**

```bash
git add extensions/x-matrix-theme/manifest.json extensions/x-matrix-theme/theme.css extensions/x-matrix-theme/README.md
git commit -m "feat(x-theme): scaffold manifest and palette — paint layer"
```

---

### Task 2: Rain canvas layer — `rain.js` (fork of `web-ui/cascade.js`)

**Files:**
- Create: `extensions/x-matrix-theme/rain.js`

**Interfaces:**
- Consumes: `web-ui/cascade.js` draw loop (copied, not imported).
- Produces: `window.MLRain = { start, stop, isRunning }` used by Task 4's `content.js`. `theme.css` already provides `#ml-rain` + column `z-index`.

- [ ] **Step 1: Create `rain.js` verbatim**

Create `extensions/x-matrix-theme/rain.js`:

```javascript
// extensions/x-matrix-theme/rain.js
// Rain behind the timeline. Fork of web-ui/cascade.js — copied, not imported.
// Source: web-ui/cascade.js @ 80c56a6 (or current main at copy time)
// Isolation: this file never reads storage, never touches glyphs, never throws into host.

(function () {
  const CANVAS_ID = "ml-rain";
  let canvas = null;
  let ctx = null;
  let raf = 0;
  let last = 0;
  let cols = 0;
  let drops = [];
  const FONT_SIZE = 13;
  const CHARS = "ｦｧｨｩｪｫｬｭｮｯｰｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝﾞﾟ".split("");

  function ensureCanvas() {
    if (canvas) return canvas;
    canvas = document.getElementById(CANVAS_ID);
    if (!canvas) {
      canvas = document.createElement("canvas");
      canvas.id = CANVAS_ID;
      // theme.css already styles #ml-rain fixed 0.12 opacity; inline fallback:
      canvas.style.position = "fixed";
      canvas.style.inset = "0";
      canvas.style.width = "100vw";
      canvas.style.height = "100vh";
      canvas.style.zIndex = "0";
      canvas.style.opacity = "0.12";
      canvas.style.pointerEvents = "none";
      canvas.style.background = "#000";
      document.body.prepend(canvas);
    }
    ctx = canvas.getContext("2d");
    return canvas;
  }

  function resize() {
    if (!canvas || !ctx) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = window.innerWidth * dpr;
    canvas.height = window.innerHeight * dpr;
    canvas.style.width = window.innerWidth + "px";
    canvas.style.height = window.innerHeight + "px";
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    cols = Math.floor(window.innerWidth / FONT_SIZE);
    drops = Array.from({ length: cols }, () => Math.floor(Math.random() * -40));
  }

  function draw(now) {
    if (last === 0) last = now;
    const dt = now - last;
    if (dt < 33) { raf = requestAnimationFrame(draw); return; }
    last = now;
    if (!ctx || !canvas) return;
    ctx.fillStyle = "rgba(0, 0, 0, 0.08)";
    ctx.fillRect(0, 0, window.innerWidth, window.innerHeight);
    ctx.fillStyle = "#00ff41";
    ctx.font = FONT_SIZE + "px 'JetBrains Mono', monospace";
    for (let i = 0; i < cols; i++) {
      const ch = CHARS[Math.floor(Math.random() * CHARS.length)];
      ctx.fillText(ch, i * FONT_SIZE, drops[i] * FONT_SIZE);
      if (drops[i] * FONT_SIZE > window.innerHeight && Math.random() > 0.975) drops[i] = 0;
      else drops[i]++;
    }
    raf = requestAnimationFrame(draw);
  }

  function shouldRun() {
    if (window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches) return false;
    if (document.hidden) return false;
    return true;
  }

  function start() {
    try {
      if (!shouldRun()) return;
      ensureCanvas();
      resize();
      window.addEventListener("resize", resize);
      document.addEventListener("visibilitychange", () => {
        if (document.hidden) stop();
        else if (shouldRun() && !raf) { last = 0; raf = requestAnimationFrame(draw); }
      });
      const mql = window.matchMedia("(prefers-reduced-motion: reduce)");
      if (mql && mql.addEventListener) mql.addEventListener("change", () => { if (mql.matches) stop(); else start(); });
      if (!raf) { last = 0; raf = requestAnimationFrame(draw); }
    } catch {}
  }

  function stop() {
    if (raf) cancelAnimationFrame(raf);
    raf = 0;
  }

  function isRunning() { return !!raf; }

  window.MLRain = { start, stop, isRunning };
})();
```

Add top comment `// copied from web-ui/cascade.js @ <commit> — fork for fixed background use` and replace `<commit>` with the actual current HEAD commit hash at copy time (`git rev-parse HEAD`).

- [ ] **Step 2: Run main checks — rain must not affect them**

Run:

```bash
python site/checks/no_semantics.py
python site/checks/key_handling.py
PYTHONPATH=src .venv/bin/python -m pytest tests/test_site_examples.py tests/test_site_glue.py -q
```

Expected: both checks pass; site tests pass. Rain file is not checked by these — it's isolated.

- [ ] **Step 3: Syntax check**

Run:

```bash
node --check extensions/x-matrix-theme/rain.js && echo "rain.js syntax OK"
```

Expected: `rain.js syntax OK`.

- [ ] **Step 4: Commit**

```bash
git add extensions/x-matrix-theme/rain.js
git commit -m "feat(x-theme): rain canvas behind feed — fork of cascade"
```

---

### Task 3: Glyph layer — `glyph.js` (copied table + DOM walk)

**Files:**
- Create: `extensions/x-matrix-theme/glyph.js`

**Interfaces:**
- Consumes: `src/matrixlang/render.py` CHAR_MAP (copied, not imported).
- Produces: `window.MLGlyph = { transliterate, applyToTweet, restoreTweet, enableAll, disableAll }` used by Task 4. Only this file knows `CHAR_MAP`.

- [ ] **Step 1: Create `glyph.js` verbatim**

Create `extensions/x-matrix-theme/glyph.js`:

```javascript
// extensions/x-matrix-theme/glyph.js
// Visual transliteration for tweet bodies. Copied table, not imported.
// Source: src/matrixlang/render.py CHAR_MAP @ <commit> — fork for X timeline use.
// Isolation: only this file knows CHAR_MAP; content.js/theme.css never do.

(function () {
  // Minimal latin → half-width katakana map for tweet bodies.
  // Copied from src/matrixlang/render.py — keep the mapping for A-Z, a-z, 0-9.
  // If render.py uses a dict, flatten it here as a literal object.
  const CHAR_MAP = {
    A: "ﾊ", B: "ﾐ", C: "ﾋ", D: "ﾌ", E: "ﾑ", F: "ﾒ", G: "ﾓ", H: "ﾔ", I: "ﾕ", J: "ﾖ", K: "ﾗ", L: "ﾘ", M: "ﾙ",
    N: "ﾚ", O: "ﾛ", P: "ﾜ", Q: "ﾝ", R: "ﾜ", S: "ｦ", T: "ﾄ", U: "ﾝ", V: "ﾌ", W: "ﾜ", X: "ﾒ", Y: "ﾔ", Z: "ｿ",
    a: "ﾊ", b: "ﾐ", c: "ﾋ", d: "ﾌ", e: "ﾑ", f: "ﾒ", g: "ﾓ", h: "ﾔ", i: "ﾕ", j: "ﾖ", k: "ﾗ", l: "ﾘ", m: "ﾙ",
    n: "ﾚ", o: "ﾛ", p: "ﾜ", q: "ﾝ", r: "ﾜ", s: "ｦ", t: "ﾄ", u: "ﾝ", v: "ﾌ", w: "ﾜ", x: "ﾒ", y: "ﾔ", z: "ｿ",
    "0": "ｧ", "1": "ｨ", "2": "ｩ", "3": "ｪ", "4": "ｫ", "5": "ｬ", "6": "ｭ", "7": "ｮ", "8": "ｯ", "9": "ﾟ",
    trace: "ﾄ", construct: "ｱ", dejavu: "ﾃ", flatline: "ﾗ", redpill: "ﾚ", agent: "ｴ", jackout: "ﾖ",
  };

  function transliterate(str) {
    // Single-char map first, then word-level fallback for matrix keywords (already covered char-wise).
    // Keep emoji, existing katakana, spaces, punctuation as-is.
    let out = "";
    for (const ch of str) {
      out += CHAR_MAP[ch] || ch;
    }
    return out;
  }

  function applyToTweet(articleEl) {
    try {
      const textEl = articleEl.querySelector('div[data-testid="tweetText"]');
      if (!textEl) return;
      if (textEl.dataset.mlOriginal !== undefined) return; // already in glyph face
      // Save original text (innerText, not innerHTML — links stay DOM)
      const original = textEl.innerText;
      textEl.dataset.mlOriginal = original;
      textEl.innerText = transliterate(original);
      // Append helper line once
      if (!articleEl.querySelector(".ml-original")) {
        const helper = document.createElement("div");
        helper.className = "ml-original";
        helper.textContent = "↳ original: " + original;
        textEl.after(helper);
      }
    } catch {}
  }

  function restoreTweet(articleEl) {
    try {
      const textEl = articleEl.querySelector('div[data-testid="tweetText"]');
      if (!textEl || textEl.dataset.mlOriginal === undefined) return;
      textEl.innerText = textEl.dataset.mlOriginal;
      delete textEl.dataset.mlOriginal;
      const helper = articleEl.querySelector(".ml-original");
      if (helper) helper.remove();
    } catch {}
  }

  function enableAll() {
    for (const a of document.querySelectorAll('article[data-testid="tweet"]')) applyToTweet(a);
  }

  function disableAll() {
    for (const a of document.querySelectorAll('article[data-testid="tweet"]')) restoreTweet(a);
  }

  window.MLGlyph = { transliterate, applyToTweet, restoreTweet, enableAll, disableAll };
})();
```

Replace `<commit>` with actual `git rev-parse HEAD` at copy time. Keep `a[href]` out of the walk — only `tweetText` text nodes are swapped, so links stay clickable.

- [ ] **Step 2: Syntax + main checks**

Run:

```bash
node --check extensions/x-matrix-theme/glyph.js && echo "glyph.js syntax OK"
python site/checks/no_semantics.py
python site/checks/key_handling.py
PYTHONPATH=src .venv/bin/python -m pytest tests/test_site_examples.py tests/test_site_glue.py -q
```

Expected: syntax OK; both checks pass; site tests pass.

- [ ] **Step 3: Manual smoke — table is a literal copy, not an import**

Run:

```bash
grep -R "from matrixlang\|import matrixlang\|server/sse" extensions/x-matrix-theme/glyph.js && echo "FAIL — imported main" || echo "no main import — OK"
grep -n "CHAR_MAP" extensions/x-matrix-theme/glyph.js | head -1 && echo "CHAR_MAP present"
```

Expected: `no main import — OK`; `CHAR_MAP present`.

- [ ] **Step 4: Commit**

```bash
git add extensions/x-matrix-theme/glyph.js
git commit -m "feat(x-theme): glyph table and tweet walk — visual, reversible"
```

---

### Task 4: Glue — `content.js` (toggle + observer + persistence)

**Files:**
- Create: `extensions/x-matrix-theme/content.js`

**Interfaces:**
- Consumes: `window.MLRain` from Task 2, `window.MLGlyph` from Task 3, `theme.css` already injected by manifest.
- Produces: one `#ml-face-toggle` button, `html[data-ml-face]` attribute, `chrome.storage.local` persistence, `MutationObserver` on timeline + SPA nav handling. This is the only file that reads storage and mounts UI.

- [ ] **Step 1: Create `content.js` verbatim**

Create `extensions/x-matrix-theme/content.js`:

```javascript
// extensions/x-matrix-theme/content.js
// Glue for the X Matrix theme — mount toggle, persist face, observe timeline.
// Mirrors site/layout.js (persisted data-* on html, sync, aria-pressed).

(function () {
  const STORAGE_KEY = "ml-x-theme-face";
  const VALID = ["glyph", "latin"];

  async function readPref() {
    try {
      const out = await chrome.storage.local.get(STORAGE_KEY);
      const v = out[STORAGE_KEY];
      return VALID.includes(v) ? v : "latin";
    } catch { return "latin"; }
  }

  async function writePref(v) {
    try { await chrome.storage.local.set({ [STORAGE_KEY]: v }); } catch {}
  }

  function applyFace(face) {
    document.documentElement.dataset.mlFace = face;
    if (face === "glyph" && window.MLGlyph) window.MLGlyph.enableAll();
    else if (window.MLGlyph) window.MLGlyph.disableAll();
    sync();
  }

  function sync() {
    const btn = document.getElementById("ml-face-toggle");
    if (!btn) return;
    const cur = document.documentElement.dataset.mlFace || "latin";
    const isGlyph = cur === "glyph";
    btn.setAttribute("aria-pressed", String(isGlyph));
    btn.textContent = isGlyph ? "Latin ◑ Glyph" : "Glyph ◐ Latin";
  }

  async function mountToggle() {
    // X header may not exist yet — observe body until it does
    const tryMount = () => {
      if (document.getElementById("ml-face-toggle")) return true;
      const header = document.querySelector('header [role="navigation"], header nav, [data-testid="primaryColumn"]');
      if (!header) return false;
      const btn = document.createElement("button");
      btn.id = "ml-face-toggle";
      btn.setAttribute("aria-pressed", "false");
      btn.textContent = "Glyph ◐ Latin";
      btn.addEventListener("click", async () => {
        const cur = document.documentElement.dataset.mlFace || "latin";
        const next = cur === "glyph" ? "latin" : "glyph";
        document.documentElement.dataset.mlFace = next;
        await writePref(next);
        if (next === "glyph" && window.MLGlyph) window.MLGlyph.enableAll();
        else if (window.MLGlyph) window.MLGlyph.disableAll();
        sync();
      });
      // Place near top bar — fallback to body if header not found
      const anchor = document.querySelector('header [role="navigation"]') || document.querySelector("header") || document.body;
      anchor.appendChild(btn);
      sync();
      return true;
    };
    if (tryMount()) return;
    const obs = new MutationObserver(() => { if (tryMount()) obs.disconnect(); });
    obs.observe(document.body, { childList: true, subtree: true });
  }

  function observeTimeline() {
    const col = document.querySelector('[data-testid="primaryColumn"]');
    if (!col) {
      const bodyObs = new MutationObserver(() => {
        const c = document.querySelector('[data-testid="primaryColumn"]');
        if (c) { bodyObs.disconnect(); observeTimeline(); }
      });
      bodyObs.observe(document.body, { childList: true, subtree: true });
      return;
    }
    const applyIfGlyph = (article) => {
      const cur = document.documentElement.dataset.mlFace || "latin";
      if (cur === "glyph" && window.MLGlyph) window.MLGlyph.applyToTweet(article);
    };
    // Apply to existing tweets
    for (const a of col.querySelectorAll('article[data-testid="tweet"]')) applyIfGlyph(a);
    const obs = new MutationObserver((muts) => {
      for (const m of muts) for (const n of m.addedNodes) {
        if (!(n instanceof HTMLElement)) continue;
        if (n.matches && n.matches('article[data-testid="tweet"]')) applyIfGlyph(n);
        for (const a of n.querySelectorAll ? n.querySelectorAll('article[data-testid="tweet"]') : []) applyIfGlyph(a);
      }
    });
    obs.observe(col, { childList: true, subtree: true });
    // SPA nav — re-apply when column changes
    let lastHref = location.href;
    setInterval(() => {
      if (location.href !== lastHref) {
        lastHref = location.href;
        const cur = document.documentElement.dataset.mlFace || "latin";
        if (cur === "glyph") setTimeout(() => window.MLGlyph && window.MLGlyph.enableAll(), 300);
      }
    }, 500);
  }

  (async function init() {
    try {
      const face = await readPref();
      document.documentElement.dataset.mlFace = face;
      // Rain is already loaded (rain.js runs before content.js); start it
      if (window.MLRain) window.MLRain.start();
      mountToggle();
      observeTimeline();
      // If initial face is glyph, enable after toggle/observer are ready
      if (face === "glyph") setTimeout(() => window.MLGlyph && window.MLGlyph.enableAll(), 500);
    } catch {}
  })();
})();
```

- [ ] **Step 2: Syntax + main checks**

Run:

```bash
node --check extensions/x-matrix-theme/content.js && echo "content.js syntax OK"
python site/checks/no_semantics.py
python site/checks/key_handling.py
PYTHONPATH=src .venv/bin/python -m pytest tests/test_site_examples.py tests/test_site_glue.py -q
```

Expected: syntax OK; checks pass; site tests pass.

- [ ] **Step 3: Verify no main import and rain/glyph globals are used correctly**

Run:

```bash
grep -R "from matrixlang\|import matrixlang\|server/sse" extensions/x-matrix-theme/content.js && echo "FAIL" || echo "no main import — OK"
grep -n "MLRain\|MLGlyph\|ml-face-toggle\|mlOriginal" extensions/x-matrix-theme/content.js | head -5
```

Expected: `no main import — OK`; symbols present.

- [ ] **Step 4: Commit**

```bash
git add extensions/x-matrix-theme/content.js
git commit -m "feat(x-theme): global glyph toggle and timeline observer"
```

---

### Task 5: Checks, README, and verification — keep `main` green

**Files:**
- Create: `extensions/x-matrix-theme/checks/no_main_import.py`
- Create: `extensions/x-matrix-theme/checks/manifest_hosts.py`
- Modify: `extensions/x-matrix-theme/README.md` (complete the checklist)

**Interfaces:**
- Consumes: all prior tasks' files.
- Produces: two tiny checks (like `site/checks/`) and a complete manual acceptance checklist. No changes to `main` CI.

- [ ] **Step 1: Create `checks/no_main_import.py`**

Create `extensions/x-matrix-theme/checks/no_main_import.py`:

```python
"""Extension must not import matrixlang main — table/cascade are copied."""
import pathlib, re, sys

root = pathlib.Path("extensions/x-matrix-theme")
fails = []
for path in root.rglob("*.js"):
    if "checks" in path.parts: continue
    text = path.read_text()
    if re.search(r"from\s+matrixlang|import\s+matrixlang|server/sse|from\s+server", text):
        fails.append(str(path))

if fails:
    print("extension imports main:")
    for f in fails: print(" ", f)
    sys.exit(1)
print("no main import in extension — OK")
```

- [ ] **Step 2: Create `checks/manifest_hosts.py`**

Create `extensions/x-matrix-theme/checks/manifest_hosts.py`:

```python
"""Manifest hosts must be exactly x.com + twitter.com, no extra."""
import json, pathlib, sys

data = json.loads(pathlib.Path("extensions/x-matrix-theme/manifest.json").read_text())
allowed = {"*://x.com/*", "*://twitter.com/*"}
hosts = set(data.get("host_permissions", []))
matches = set()
for cs in data.get("content_scripts", []):
    matches.update(cs.get("matches", []))

if hosts != allowed or matches != allowed:
    print(f"hosts={hosts} matches={matches} want {allowed}")
    sys.exit(1)
if "storage" not in data.get("permissions", []):
    print("missing storage permission")
    sys.exit(1)
for bad in ["webRequest", "cookies", "<all_urls>", "api.x.com", "api.twitter.com"]:
    blob = json.dumps(data)
    if bad in blob:
        print(f"manifest contains forbidden {bad!r}")
        sys.exit(1)
print("manifest hosts — OK")
```

- [ ] **Step 3: Complete `README.md` with full checklist**

Append to `extensions/x-matrix-theme/README.md` (keep install section from Task 1):

```markdown
## Manual acceptance (timeline-first, Load unpacked)

1. Install: Load unpacked → open `x.com/home` → faint rain behind feed, toggle says `Glyph ◐ Latin`
2. Click toggle → every visible tweet flips to glyph with `↳ original:` underneath; button flips to `Latin ◑ Glyph`
3. Scroll — new tweets appear in glyph face automatically; toggle back → all revert, including new ones
4. SPA: `Home` → profile → `Home` → timeline still in chosen face, rain still behind
5. `prefers-reduced-motion: reduce` (DevTools → Rendering → Emulate) → rain canvas absent, toggle still works
6. Block `theme.css` in DevTools → tweets still toggle (layers isolated)

## Layer isolation

- `theme.css` — paint only
- `rain.js` — canvas only, pauses on `visibilitychange` / reduced-motion
- `glyph.js` — table + walk only, `MLGlyph` global
- `content.js` — glue only, `chrome.storage.local` + observer
```

- [ ] **Step 4: Run all checks exactly as CI would**

Run:

```bash
python extensions/x-matrix-theme/checks/no_main_import.py
python extensions/x-matrix-theme/checks/manifest_hosts.py
python -m json.tool extensions/x-matrix-theme/manifest.json > /dev/null && echo "manifest JSON valid"
node --check extensions/x-matrix-theme/rain.js && node --check extensions/x-matrix-theme/glyph.js && node --check extensions/x-matrix-theme/content.js && echo "all JS syntax OK"
python site/checks/no_semantics.py
python site/checks/key_handling.py
PYTHONPATH=src .venv/bin/python -m pytest -q
```

Expected: all checks print OK; manifest valid; JS syntax OK; main suite 1399 passed; `src/matrixlang/` and `server/sse.py` untouched:

```bash
git diff --stat main -- src/matrixlang server/sse.py 2>&1 | grep . && echo "FAIL — main touched" || echo "src/server untouched — OK"
git status --short | grep -E "^.. extensions/x-matrix-theme" | head -10
```

Only `extensions/x-matrix-theme/` should appear.

- [ ] **Step 5: Commit**

```bash
git add extensions/x-matrix-theme/checks/ extensions/x-matrix-theme/README.md
git commit -m "feat(x-theme): checks and checklist — keep main green"
```

---

## Verification Gates (run before PR)

```bash
python extensions/x-matrix-theme/checks/no_main_import.py
python extensions/x-matrix-theme/checks/manifest_hosts.py
python site/checks/no_semantics.py
python site/checks/key_handling.py
PYTHONPATH=src .venv/bin/python -m pytest -q
git diff --stat main -- src/matrixlang server/sse.py  # expect empty
git diff --stat main                                    # expect only extensions/x-matrix-theme/ + docs/
```

Expected: all green; nothing under `src/matrixlang/` or `server/sse.py` changed.
