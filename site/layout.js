// site/layout.js
// The layout switch. Lives apart from playground.js on purpose: it touches
// localStorage, and playground.js handles the reader's API key, which must
// never be persisted. site/checks/key_handling.py stays scoped to
// playground.js and is not loosened.

const STORAGE_KEY = "matrixlang-layout";
const VALID = ["auto", "desktop", "mobile"];

function readPref() {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return VALID.includes(stored) ? stored : "auto";
  } catch {
    return "auto"; // storage blocked (private mode) — fall back, never crash
  }
}

function writePref(value) {
  try {
    localStorage.setItem(STORAGE_KEY, value);
  } catch {
    /* storage blocked — the in-memory attribute still applies for this visit */
  }
}

// Before first paint: the stored preference decides, so a Desktop reader
// never sees the mobile layout flash. Runs synchronously because this file
// is loaded in <head> ahead of the stylesheet.
document.documentElement.dataset.layout = readPref();

// The buttons live in the body, which is not parsed yet — wire them when it
// is. Until then the attribute above is already doing the work.
document.addEventListener("DOMContentLoaded", () => {
  const buttons = document.querySelectorAll("[data-layout-choice]");
  for (const button of buttons) {
    button.addEventListener("click", () => {
      document.documentElement.dataset.layout = button.dataset.layoutChoice;
      writePref(button.dataset.layoutChoice);
      sync();
    });
  }
  sync();

  function sync() {
    const current = document.documentElement.dataset.layout;
    for (const button of buttons) {
      const active = button.dataset.layoutChoice === current;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    }
  }
});
