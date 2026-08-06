// site/intro.js
// The terminal intro: a typed line that turns into its own glyph face.
//
// It owns no language logic. The lines and their glyph faces are fetched
// from intro.json, which site/generate_intro.py produced with the package's
// `transliterate`. This file never transliterates and holds no glyph table —
// the same rule playground.js follows, enforced by site/checks/no_semantics.py.
//
// Structured so that FAILING MEANS NO INTRO, never a stuck black screen:
// the overlay is invisible until this script sets `data-intro` on <html>, and
// every path that cannot finish clears the attribute again. A blocked fetch,
// a thrown error, or this file not loading at all all end with the ordinary
// page, which is the only acceptable way for decoration to fail.

// Wrapped, and it has to be. The page loads layout.js, intro.js and
// playground.js as classic scripts, which SHARE one global lexical scope —
// so a `const STORAGE_KEY` here collided with layout.js's and threw
// "already been declared" before this file did anything at all. The intro
// silently never played. Nothing escapes this closure but window.__intro,
// which is the only thing outside needs.
(function () {
"use strict";

const CHAR_MS = 65; // the steady cadence; punctuation rests on top of it
const GLYPH_MS = 22; // the turn is faster than the typing — it is a reveal

// This file remembers NOTHING. It stores no flag, reads no flag, and touches
// neither localStorage nor sessionStorage — every page load gets the intro.
//
// That is a deliberate reversal of two earlier attempts. Once-per-browser
// meant a reader returning later saw nothing. Once-per-tab meant a refresh
// saw nothing, because sessionStorage survives a reload. Both were chosen to
// spare a returning reader, and both mostly succeeded in hiding the intro
// from everyone including its author.
//
// The cost is real and accepted: someone who reloads to re-read a paragraph
// gets it again. Skipping is one key or one click, and the page underneath
// is never blocked, which is what makes that cost affordable.
//
// It also deletes a whole class of bug. With nothing recorded, a failed
// fetch cannot mark a reader as having watched an intro they never saw —
// the next load simply tries again.

// `?intro` remains for one narrow purpose: it overrides the reduced-motion
// decline, so a reader who has asked their OS for less motion can still
// choose, explicitly, to see this once.
function forced() {
  return new URLSearchParams(location.search).has("intro");
}

function shouldPlay() {
  if (forced()) return true;
  // A reader who asked the OS for less motion is not asking for a typewriter.
  return !window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

// Before first paint, for the same reason layout.js runs in <head>: the CSS
// keys the overlay off this attribute, so setting it here means the intro is
// either there from the first frame or not at all. Never a flash of page
// followed by a black screen dropping over it.
const playing = shouldPlay();
if (playing) document.documentElement.dataset.intro = "playing";

const wait = (ms) => new Promise((resolve) => setTimeout(resolve, ms));

let run = 0; // bumped to cancel an in-flight sequence

// One exit for every path. Skipping, finishing and failing were three cases
// only because something had to be recorded; with nothing recorded they are
// the same act — take the overlay away and give the reader the page.
function stop() {
  run += 1;
  const root = document.documentElement;
  const overlay = document.getElementById("intro");
  if (!overlay) {
    root.removeAttribute("data-intro");
    return;
  }
  overlay.classList.add("gone");
  // Drop the attribute only after the fade, or the overlay vanishes instantly
  // and body scrolling returns mid-transition.
  setTimeout(() => root.removeAttribute("data-intro"), 900);
}

/* A machine of that era typed at a steady rate, but it rested at punctuation,
   and that pause is most of what makes a line feel written rather than
   pasted. */
function delayFor(character) {
  const jitter = 0.85 + Math.random() * 0.3;
  if (character === ".") return CHAR_MS * 5 * jitter;
  if (character === "," || character === ":") return CHAR_MS * 4 * jitter;
  if (character === " ") return CHAR_MS * 0.7 * jitter;
  return CHAR_MS * jitter;
}

async function type(body, text, token) {
  for (const character of text) {
    if (token !== run) return false;
    body.textContent += character;
    await wait(delayFor(character));
  }
  return token === run;
}

/* The line re-rendered into its other face, revealed left to right. No
   scramble and no invented characters: the page's claim is that nothing on
   screen was generated at random, and the intro is the worst possible place
   to start breaking it. */
async function turnToGlyphs(body, glyph, token) {
  body.classList.add("glyphed");
  for (let i = 1; i <= glyph.length; i += 1) {
    if (token !== run) return false;
    body.textContent = glyph.slice(0, i);
    await wait(GLYPH_MS);
  }
  return token === run;
}

async function play(lines) {
  const token = run;
  const terminal = document.getElementById("intro-terminal");
  // The overlay is showing but its terminal is missing — nothing can be typed
  // into it, so this is a failure, not a viewing.
  if (!terminal) return stop();

  for (const [index, line] of lines.entries()) {
    const row = document.createElement("span");
    row.className = "intro-line";
    const body = document.createElement("span");
    const cursor = document.createElement("span");
    cursor.className = "intro-cursor";
    row.append(body, cursor);
    terminal.appendChild(row);

    // A beat of cursor alone before the first character. The screen is
    // waiting, and the waiting is the whole effect.
    await wait(index === 0 ? 700 : 450);
    if (token !== run) return;

    if (!(await type(body, line.latin, token))) return;
    await wait(index === lines.length - 1 ? 850 : 550);
    if (token !== run) return;

    if (!(await turnToGlyphs(body, line.glyph, token))) return;
    await wait(500);
    if (token !== run) return;

    cursor.remove();
  }

  await wait(700);
  if (token === run) stop();
}

async function start() {
  const skip = document.getElementById("intro-skip");
  const overlay = document.getElementById("intro");
  if (skip) skip.addEventListener("click", stop);
  if (overlay) overlay.addEventListener("click", stop);
  window.addEventListener("keydown", () => {
    if (document.documentElement.dataset.intro === "playing") stop();
  });

  try {
    const response = await fetch("intro.json");
    if (!response.ok) throw new Error(String(response.status));
    const { lines } = await response.json();
    if (!Array.isArray(lines) || !lines.length) throw new Error("no lines");
    await play(lines);
  } catch {
    // No intro is a fine outcome. A black screen is not. Nothing is recorded
    // either way, so a reader who hit a blocked fetch gets the intro on their
    // next load without anything having to notice.
    stop();
  }
}

if (playing) {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
}

window.__intro = { shouldPlay, stop, playing };

})();
