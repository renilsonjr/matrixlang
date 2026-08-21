// extensions/x-matrix-theme/glyph.js
// Visual transliteration for tweet bodies. Copied table, not imported.
// Source: src/matrixlang/render.py CHAR_MAP @ 5d4c278bfab58a418836458a30575aba6c25aef3 — fork for X timeline use.
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
