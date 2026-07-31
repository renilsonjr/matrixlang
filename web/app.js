import { MatrixRainEngine } from './rain_canvas.js';
import { Lexer, Parser, Interpreter, convertToGlyphs, convertFromGlyphs } from './interpreter.js';

const SAMPLES = {
  hello: `# The Stage 3 demo: hello.rain
construct n = 0
construct name = "World!"

dejavu n < 3
  redpill n == 1
    trace "Hello, " + name
  bluepill
    trace n
  flatline
  n = n + 1
flatline`,

  counter: `# Loop & Conditional Counter
construct count = 1
construct max = 5

dejavu count <= max
  redpill count == 3
    trace "Glitch in the Matrix!"
  bluepill
    trace "Processing frame: " + count
  flatline
  count = count + 1
flatline`,

  fibonacci: `# Fibonacci Sequence Stream
construct a = 0
construct b = 1
construct temp = 0
construct step = 0

dejavu step < 7
  trace "Fib: " + a
  temp = a + b
  a = b
  b = temp
  step = step + 1
flatline`,

  glyphs: `# Katakana Glyphs Demonstration
ｱ n = 0
ｱ name = "Morpheus"

ﾃ n < 3
  ﾚ n == 1
    ﾄ "Follow the white rabbit, " + name
  ﾌ
    ﾄ n
  ﾗ
  n = n + 1
ﾗ`
};

document.addEventListener('DOMContentLoaded', () => {
  const canvas = document.getElementById('matrix-rain-canvas');
  const rainEngine = new MatrixRainEngine(canvas);
  rainEngine.start();

  const codeInput = document.getElementById('code-input');
  const consoleOutput = document.getElementById('console-output');
  const runBtn = document.getElementById('run-btn');
  const resetBtn = document.getElementById('reset-btn');
  const toggleGlyphBtn = document.getElementById('toggle-glyph-btn');
  const sampleSelect = document.getElementById('sample-select');
  const charCount = document.getElementById('char-count');
  const execStatus = document.getElementById('exec-status');
  const stepCount = document.getElementById('step-count');
  const editorStatus = document.getElementById('editor-status');

  let isGlyphView = false;

  // Set default sample
  codeInput.value = SAMPLES.hello;
  updateCharCount();

  sampleSelect.addEventListener('change', (e) => {
    const key = e.target.value;
    if (SAMPLES[key]) {
      codeInput.value = isGlyphView ? convertToGlyphs(SAMPLES[key]) : SAMPLES[key];
      updateCharCount();
    }
  });

  codeInput.addEventListener('input', updateCharCount);

  function updateCharCount() {
    charCount.textContent = `${codeInput.value.length} chars`;
  }

  toggleGlyphBtn.addEventListener('click', () => {
    isGlyphView = !isGlyphView;
    toggleGlyphBtn.textContent = `Glyph View: ${isGlyphView ? 'On (Katakana)' : 'Off'}`;
    if (isGlyphView) {
      codeInput.value = convertToGlyphs(codeInput.value);
    } else {
      codeInput.value = convertFromGlyphs(codeInput.value);
    }
    updateCharCount();
  });

  resetBtn.addEventListener('click', () => {
    consoleOutput.innerHTML = `
      <div class="console-line">
        <span class="console-prompt">&gt;</span>
        <span class="console-text">Console reset. Engine ready.</span>
      </div>
    `;
    execStatus.textContent = 'IDLE';
    stepCount.textContent = 'Steps: 0';
  });

  runBtn.addEventListener('click', async () => {
    const code = codeInput.value;
    consoleOutput.innerHTML = '';
    execStatus.textContent = 'RUNNING...';
    editorStatus.textContent = 'Executing';

    // Trigger initial rain burst
    rainEngine.spawnColumn();
    rainEngine.spawnColumn();

    try {
      const lexer = new Lexer(code);
      const tokens = lexer.tokenize();

      const parser = new Parser(tokens);
      const ast = parser.parse();

      let steps = 0;
      const interpreter = new Interpreter(async (val) => {
        steps++;
        stepCount.textContent = `Steps: ${steps}`;

        // 1. Output line to bottom-left Terminal Output Stream
        const lineEl = document.createElement('div');
        lineEl.className = 'console-line';
        lineEl.innerHTML = `<span class="console-prompt">&gt;</span><span class="console-text">${escapeHtml(val)}</span>`;
        consoleOutput.appendChild(lineEl);
        consoleOutput.scrollTop = consoleOutput.scrollHeight;

        // 2. Spawn corresponding Katakana output streams down the right Rain Cascade Screen!
        rainEngine.spawnOutputStream(val);

        await new Promise((r) => setTimeout(r, 180)); // smooth step delay
      });

      await interpreter.run(ast);

      execStatus.textContent = 'FINISHED';
      editorStatus.textContent = 'Ready';

      const doneEl = document.createElement('div');
      doneEl.className = 'console-line';
      doneEl.innerHTML = `<span class="console-prompt">&gt;</span><span class="console-text" style="color: #00ff66; opacity: 0.7;">--- Program completed successfully ---</span>`;
      consoleOutput.appendChild(doneEl);
      consoleOutput.scrollTop = consoleOutput.scrollHeight;

    } catch (err) {
      execStatus.textContent = 'ERROR';
      editorStatus.textContent = 'Error';
      const errEl = document.createElement('div');
      errEl.className = 'console-line';
      errEl.innerHTML = `<span class="console-prompt">&gt;</span><span class="console-error">Runtime Error: ${escapeHtml(err.message)}</span>`;
      consoleOutput.appendChild(errEl);
      consoleOutput.scrollTop = consoleOutput.scrollHeight;
    }
  });

  function escapeHtml(str) {
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }
});
