/**
 * Matrix Digital Rain Canvas Engine (.rain)
 * Renders Katakana digital rain cascade and custom code output streams.
 */
import { convertToGlyphs } from './interpreter.js';

const RAIN_ALPHABET = [];
for (let code = 0xff66; code <= 0xff9e; code++) {
  RAIN_ALPHABET.push(String.fromCharCode(code));
}

class Column {
  constructor(col, speed, length, numRows, customGlyphs = null) {
    this.col = col;
    this.speed = speed;
    this.length = length;
    this.numRows = numRows;
    this.head = 0;
    this.glyphs = {};
    this.customGlyphs = customGlyphs; // Optional string of Katakana output glyphs
    this.isOutput = customGlyphs !== null;
  }

  advance() {
    const prevRow = Math.floor(this.head);
    this.head += this.speed;
    const currRow = Math.floor(this.head);

    for (let r = prevRow + 1; r <= currRow; r++) {
      if (this.isOutput && this.customGlyphs.length > 0) {
        // Pick characters sequentially from the custom Katakana output
        const glyphIdx = (r >= 0 ? r : 0) % this.customGlyphs.length;
        this.glyphs[r] = this.customGlyphs[glyphIdx];
      } else {
        this.glyphs[r] = RAIN_ALPHABET[Math.floor(Math.random() * RAIN_ALPHABET.length)];
      }
    }

    // Shimmer mutation (background rain only)
    if (!this.isOutput && Math.random() < 0.15 && Object.keys(this.glyphs).length > 0) {
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
    this.fontSize = 20;
    this.cols = 0;
    this.rows = 0;
    this.columns = [];
    this.freeCols = [];
    this.animId = null;

    this.resize();
    window.addEventListener('resize', () => this.resize());
  }

  resize() {
    const dpr = window.devicePixelRatio || 1;
    const rect = this.canvas.parentElement ? this.canvas.parentElement.getBoundingClientRect() : this.canvas.getBoundingClientRect();
    
    if (rect.width === 0 || rect.height === 0) return;

    this.canvas.width = rect.width * dpr;
    this.canvas.height = rect.height * dpr;
    this.canvas.style.width = `${rect.width}px`;
    this.canvas.style.height = `${rect.height}px`;
    
    this.ctx.scale(dpr, dpr);

    this.cols = Math.floor(rect.width / this.fontSize);
    this.rows = Math.floor(rect.height / this.fontSize);

    this.freeCols = Array.from({ length: this.cols }, (_, i) => i);
    this.shuffle(this.freeCols);
  }

  shuffle(arr) {
    for (let i = arr.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [arr[i], arr[j]] = [arr[j], arr[i]];
    }
  }

  spawnColumn(customText = null) {
    if (this.cols <= 0 || this.rows <= 0) return;

    if (this.freeCols.length === 0) {
      this.freeCols = Array.from({ length: this.cols }, (_, i) => i);
      this.shuffle(this.freeCols);
    }

    const colIdx = this.freeCols.pop();
    const speed = customText ? 0.45 : 0.25 + Math.random() * 0.45;
    
    let katakanaText = null;
    let length = Math.floor(6 + Math.random() * 12);

    if (customText) {
      // Convert code output text into Katakana glyphs for the digital cascade
      katakanaText = convertToGlyphs(customText);
      if (!katakanaText || katakanaText.length === 0) {
        katakanaText = customText;
      }
      length = Math.max(8, katakanaText.length + 4);
    }

    this.columns.push(new Column(colIdx, speed, length, this.rows, katakanaText));
  }

  spawnOutputStream(outputText) {
    // Spawn multiple adjacent streams carrying the Katakana output
    const str = String(outputText);
    const glyphStr = convertToGlyphs(str);

    for (let i = 0; i < 3; i++) {
      this.spawnColumn(glyphStr);
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
    // Maintain steady ambient digital rain
    if (this.columns.length < Math.floor(this.cols * 0.6) && Math.random() < 0.4) {
      this.spawnColumn();
    }

    const width = this.canvas.width / (window.devicePixelRatio || 1);
    const height = this.canvas.height / (window.devicePixelRatio || 1);

    // Clear with dark fade
    this.ctx.fillStyle = 'rgba(4, 10, 6, 0.22)';
    this.ctx.fillRect(0, 0, width, height);

    this.ctx.font = `bold ${this.fontSize}px 'Courier New', monospace`;

    for (let i = this.columns.length - 1; i >= 0; i--) {
      const col = this.columns[i];
      col.advance();

      const headRow = Math.floor(col.head);
      for (let offset = 0; offset < col.length; offset++) {
        const r = headRow - offset;
        if (r >= 0 && r < this.rows && col.glyphs[r]) {
          const x = col.col * this.fontSize;
          const y = r * this.fontSize;

          if (col.isOutput) {
            // Output Katakana glyphs glow bright cyan/gold-green
            if (offset === 0) {
              this.ctx.fillStyle = '#ffffff';
              this.ctx.shadowColor = '#00ffff';
              this.ctx.shadowBlur = 12;
            } else {
              const alpha = 1.0 - (offset / col.length);
              this.ctx.fillStyle = `rgba(0, 255, 204, ${alpha})`;
              this.ctx.shadowColor = '#00ff66';
              this.ctx.shadowBlur = 6;
            }
          } else {
            // Ambient digital rain
            if (offset === 0) {
              this.ctx.fillStyle = '#ffffff';
              this.ctx.shadowColor = '#00ff66';
              this.ctx.shadowBlur = 10;
            } else {
              const alpha = 1.0 - (offset / col.length);
              this.ctx.fillStyle = `rgba(0, 255, 102, ${alpha * 0.9})`;
              this.ctx.shadowBlur = 0;
            }
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
