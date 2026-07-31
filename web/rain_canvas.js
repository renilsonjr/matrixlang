/**
 * Matrix Digital Rain Canvas Engine (.rain)
 * Based on matrixlang.rain & matrixlang.glyphs
 */

// Full half-width Katakana alphabet U+FF66..U+FF9D matching matrixlang RAIN_ALPHABET
const RAIN_ALPHABET = [];
for (let code = 0xff66; code <= 0xff9e; code++) {
  RAIN_ALPHABET.push(String.fromCharCode(code));
}

class Column {
  constructor(col, speed, length, numRows) {
    this.col = col;
    this.speed = speed;
    this.length = length;
    this.numRows = numRows;
    this.head = 0;
    this.glyphs = {};
  }

  advance() {
    const prevRow = Math.floor(this.head);
    this.head += this.speed;
    const currRow = Math.floor(this.head);

    for (let r = prevRow + 1; r <= currRow; r++) {
      this.glyphs[r] = RAIN_ALPHABET[Math.floor(Math.random() * RAIN_ALPHABET.length)];
    }

    // Shimmer mutation
    if (Math.random() < 0.15 && Object.keys(this.glyphs).length > 0) {
      const keys = Object.keys(this.glyphs);
      const randomRow = keys[Math.floor(Math.random() * keys.length)];
      this.glyphs[randomRow] = RAIN_ALPHABET[Math.floor(Math.random() * RAIN_ALPHABET.length)];
    }
  }

  isFinished() {
    return (this.head - this.length) > this.numRows;
  }
}

export class MatrixRainEngine {
  constructor(canvas) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.fontSize = 18;
    this.cols = 0;
    this.rows = 0;
    this.columns = [];
    this.freeCols = [];
    this.animId = null;
    this.intensity = 1.0;
    this.speedMultiplier = 1.0;

    this.resize();
    window.addEventListener('resize', () => this.resize());
  }

  resize() {
    const dpr = window.devicePixelRatio || 1;
    const rect = this.canvas.getBoundingClientRect();
    this.canvas.width = rect.width * dpr;
    this.canvas.height = rect.height * dpr;
    this.ctx.scale(dpr, dpr);

    this.cols = Math.floor(rect.width / this.fontSize);
    this.rows = Math.floor(rect.height / this.fontSize);

    this.freeCols = Array.from({ length: this.cols }, (_, i) => i);
    this.shuffle(this.freeCols);
    this.columns = [];
  }

  shuffle(arr) {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
  }

  spawnColumn() {
    if (this.freeCols.length === 0) {
      this.freeCols = Array.from({ length: this.cols }, (_, i) => i);
      this.shuffle(this.freeCols);
    }
    const colIdx = this.freeCols.pop();
    const speed = (0.2 + Math.random() * 0.6) * this.speedMultiplier;
    const length = Math.floor(4 + Math.random() * 12);
    this.columns.push(new Column(colIdx, speed, length, this.rows));
  }

  pulse(amount = 5) {
    for (let i = 0; i < amount; i++) {
      this.spawnColumn();
    }
  }

  start() {
    if (this.animId) return;
    let lastTime = performance.now();

    const loop = (now) => {
      const delta = now - lastTime;
      if (delta > 30) { // ~30 FPS tick matching MatrixLang curtain
        lastTime = now;
        this.tick();
      }
      this.animId = requestAnimationFrame(loop);
    };
    this.animId = requestAnimationFrame(loop);
  }

  stop() {
    if (this.animId) {
      cancelAnimationFrame(this.animId);
      this.animId = null;
    }
  }

  tick() {
    // Spawn new rain drops based on density
    if (Math.random() < 0.3 * this.intensity) {
      this.spawnColumn();
    }

    // Clear background with translucent dark fill for motion blur trail
    const rect = this.canvas.getBoundingClientRect();
    this.ctx.fillStyle = 'rgba(5, 12, 8, 0.2)';
    this.ctx.fillRect(0, 0, rect.width, rect.height);

    this.ctx.font = `${this.fontSize}px 'Courier New', monospace`;

    for (let i = this.columns.length - 1; i >= 0; i--) {
      const col = this.columns[i];
      col.advance();

      const headRow = Math.floor(col.head);
      for (let offset = 0; offset < col.length; offset++) {
        const r = headRow - offset;
        if (r >= 0 && r < this.rows && col.glyphs[r]) {
          const x = col.col * this.fontSize;
          const y = r * this.fontSize;

          if (offset === 0) {
            // Bright white head glyph
            this.ctx.fillStyle = '#ffffff';
            this.ctx.shadowColor = '#00ff66';
            this.ctx.shadowBlur = 10;
          } else {
            // Fading neon green trail
            const alpha = 1.0 - (offset / col.length);
            this.ctx.fillStyle = `rgba(0, 255, 102, ${alpha * 0.95})`;
            this.ctx.shadowBlur = 0;
          }

          this.ctx.fillText(col.glyphs[r], x, y);
        }
      }

      if (col.isFinished()) {
        this.columns.splice(i, 1);
      }
    }
  }
}
