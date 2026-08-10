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
  tabs.forEach((tab, i) => {
    tab.setAttribute("aria-selected", String(i === index));
    // Roving tabindex: only the active tab sits in the page's Tab order, so
    // Tab from the tablist moves straight into the panel content rather than
    // walking all four tab buttons first — the standard ARIA tabs pattern.
    tab.setAttribute("tabindex", i === index ? "0" : "-1");
  });
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
