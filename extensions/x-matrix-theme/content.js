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
      const anchor = document.querySelector('header [role="navigation"]') || document.querySelector("header") || document.body || document.documentElement;
      anchor.appendChild(btn);
      sync();
      return true;
    };
    if (tryMount()) return;
    const target = document.body || document.documentElement;
    const obs = new MutationObserver(() => { if (tryMount()) obs.disconnect(); });
    obs.observe(target, { childList: true, subtree: true });
  }

  function observeTimeline() {
    const col = document.querySelector('[data-testid="primaryColumn"]');
    if (!col) {
      const target2 = document.body || document.documentElement;
      const bodyObs = new MutationObserver(() => {
        const c = document.querySelector('[data-testid="primaryColumn"]');
        if (c) { bodyObs.disconnect(); observeTimeline(); }
      });
      bodyObs.observe(target2, { childList: true, subtree: true });
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
