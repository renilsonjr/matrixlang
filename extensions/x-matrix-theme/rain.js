// copied from web-ui/cascade.js @ 10b6ef1d63482dee8752b500f7b1b2caad70aa3c — fork for fixed background use
// extensions/x-matrix-theme/rain.js
// Rain behind the timeline. Fork of web-ui/cascade.js — copied, not imported.
// Source: web-ui/cascade.js @ 10b6ef1d63482dee8752b500f7b1b2caad70aa3c
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
      // theme.css already styles #ml-rain fixed 0.22 opacity; inline fallback:
      canvas.style.position = "fixed";
      canvas.style.inset = "0";
      canvas.style.width = "100vw";
      canvas.style.height = "100vh";
      canvas.style.zIndex = "0";
      canvas.style.opacity = "0.22";
      canvas.style.pointerEvents = "none";
      canvas.style.background = "#000";
      (document.body || document.documentElement).prepend(canvas);
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
