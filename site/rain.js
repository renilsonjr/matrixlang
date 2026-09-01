// The page's background wall.
//
// It owns no language logic and no table of its own. Every character it
// drops is read from examples.json — the same file the narrative quotes,
// produced at build time by site/generate_examples.py running the real
// renderer over programs that really ran. That is not indirection for its
// own sake: this page states, in so many words, that nothing on a falling
// screen is generated at random and every character came from a program.
// A decorative wall of invented symbols would make that sentence false
// while it was on screen. Reading the examples keeps it true, and costs a
// fetch of a file the page already ships.
//
// Everything here is presentation. If the fetch fails the wall simply
// never starts, which is the right failure for scenery: the page is a
// document first, and it reads identically without it.
(function () {
  "use strict";

  var canvas = document.getElementById("page-rain");
  if (!canvas || !canvas.getContext) return;

  // Scenery is the first thing to drop for a reader who asked for less
  // motion. The intro already honours this; the wall must not be the one
  // moving thing left on the page after it.
  var still = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)");
  if (still && still.matches) return;

  var ctx = canvas.getContext("2d");
  var SIZE = 17;          // px per cell
  var BRIGHT = 0.11;      // chosen against the real page, not guessed
  var SPEED = 0.10;       // cells per 60Hz frame, before per-column variance
  var alphabet = "";
  var columns = [];
  var last = 0;

  function fit() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
    var wide = Math.ceil(canvas.width / SIZE);
    columns = new Array(wide);
    for (var i = 0; i < wide; i++) {
      // A fractional start and a per-column rate, so the wall drifts
      // rather than pulsing in lockstep.
      columns[i] = { y: Math.random() * -60, rate: 0.55 + Math.random() * 0.9 };
    }
  }

  function pick() {
    return alphabet.charAt((Math.random() * alphabet.length) | 0);
  }

  function frame(now) {
    var step = Math.min(64, now - last);
    last = now;
    // A low alpha leaves long trails, which is what reads as smooth. A
    // higher one blinks each character off and looks like a strobe.
    ctx.fillStyle = "rgba(5, 7, 10, 0.045)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.font = SIZE + "px " + getComputedStyle(document.body).fontFamily;
    for (var i = 0; i < columns.length; i++) {
      var column = columns[i];
      var y = column.y * SIZE;
      ctx.fillStyle = "rgba(190, 255, 205, " + 0.55 * BRIGHT + ")";
      ctx.fillText(pick(), i * SIZE, y);
      ctx.fillStyle = "rgba(0, 255, 65, " + 0.30 * BRIGHT + ")";
      ctx.fillText(pick(), i * SIZE, y - SIZE);
      if (y > canvas.height + SIZE * 6) column.y = -Math.random() * 40;
      // Time-based, so the wall does not run at double speed on a 120Hz
      // display the way a per-frame increment would.
      column.y += SPEED * column.rate * (step / 16.7);
    }
    window.requestAnimationFrame(frame);
  }

  fetch("examples.json").then(function (response) {
    return response.ok ? response.json() : null;
  }).then(function (examples) {
    if (!examples) return;
    var seen = {};
    var letters = [];
    Object.keys(examples).forEach(function (request) {
      var face = examples[request].glyph || "";
      for (var i = 0; i < face.length; i++) {
        var ch = face.charAt(i);
        // Spaces and newlines are layout in a rendered face, not marks.
        if (ch.trim() && !seen[ch]) { seen[ch] = true; letters.push(ch); }
      }
    });
    if (!letters.length) return;
    alphabet = letters.join("");
    fit();
    window.addEventListener("resize", fit);
    last = performance.now();
    window.requestAnimationFrame(frame);
  }).catch(function () {
    // Scenery that cannot load is simply absent.
  });
})();
