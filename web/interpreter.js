/**
 * MatrixLang Client-Side Interpreter Engine (JavaScript Implementation)
 * Full parser, lexer, and interpreter matching MatrixLang v0.5.0 spec.
 */

// 32-Slot Katakana Bijective Glyph Table (§3.1)
export const GLYPH_MAP = {
  "construct": "ｱ",
  "trace": "ﾄ",
  "redpill": "ﾚ",
  "bluepill": "ﾌ",
  "dejavu": "ﾃ",
  "flatline": "ﾗ",
  "true": "ｼ",
  "false": "ｷ",
  "+": "ﾀ",
  "-": "ﾋ",
  "*": "ｶ",
  "/": "ﾜ",
  "=": "ﾅ",
  "==": "ﾆ",
  "!=": "ﾇ",
  "<": "ｻ",
  ">": "ｿ",
  "<=": "ｾ",
  ">=": "ｽ",
  "(": "ｸ",
  ")": "ｹ",
  "0": "ｦ", "1": "ｧ", "2": "ｨ", "3": "ｩ", "4": "ｪ",
  "5": "ｫ", "6": "ｬ", "7": "ｭ", "8": "ｮ", "9": "ｯ",
  "#": "ﾒ"
};

const REVERSE_GLYPH_MAP = {};
for (const [k, v] of Object.entries(GLYPH_MAP)) {
  REVERSE_GLYPH_MAP[v] = k;
}

export function convertToGlyphs(code) {
  // Replace keywords, operators, and digits with Katakana glyphs
  let result = "";
  let i = 0;
  while (i < code.length) {
    if (code[i] === '"') {
      let str = '"';
      i++;
      while (i < code.length && code[i] !== '"') {
        str += code[i];
        i++;
      }
      if (i < code.length) str += '"';
      result += str;
      i++;
      continue;
    }

    // Check operators
    let matched = false;
    for (const op of ["==", "!=", "<=", ">="]) {
      if (code.startsWith(op, i)) {
        result += GLYPH_MAP[op];
        i += op.length;
        matched = true;
        break;
      }
    }
    if (matched) continue;

    for (const op of ["+", "-", "*", "/", "=", "<", ">", "(", ")", "#"]) {
      if (code[i] === op) {
        result += GLYPH_MAP[op];
        i++;
        matched = true;
        break;
      }
    }
    if (matched) continue;

    // Check words/keywords
    if (/[a-zA-Z_]/.test(code[i])) {
      let word = "";
      while (i < code.length && /[a-zA-Z0-9_]/.test(code[i])) {
        word += code[i];
        i++;
      }
      if (GLYPH_MAP[word]) {
        result += GLYPH_MAP[word];
      } else {
        result += word;
      }
      continue;
    }

    // Check digits
    if (/[0-9]/.test(code[i])) {
      result += GLYPH_MAP[code[i]] || code[i];
      i++;
      continue;
    }

    result += code[i];
    i++;
  }
  return result;
}

export function convertFromGlyphs(code) {
  let result = "";
  for (const char of code) {
    result += REVERSE_GLYPH_MAP[char] !== undefined ? REVERSE_GLYPH_MAP[char] : char;
  }
  return result;
}

export class Lexer {
  constructor(source) {
    // Standardize glyphs to ASCII keywords first if glyphs are used
    this.source = convertFromGlyphs(source);
    this.pos = 0;
    this.line = 1;
    this.col = 1;
    this.tokens = [];
  }

  tokenize() {
    while (this.pos < this.source.length) {
      const ch = this.source[this.pos];

      if (ch === '\n') {
        this.line++;
        this.col = 1;
        this.pos++;
        continue;
      }

      if (/\s/.test(ch)) {
        this.pos++;
        this.col++;
        continue;
      }

      if (ch === '#') {
        while (this.pos < this.source.length && this.source[this.pos] !== '\n') {
          this.pos++;
        }
        continue;
      }

      if (ch === '"') {
        this.readString();
        continue;
      }

      if (/[0-9]/.test(ch)) {
        this.readNumber();
        continue;
      }

      if (/[a-zA-Z_]/.test(ch)) {
        this.readIdentifierOrKeyword();
        continue;
      }

      this.readOperatorOrPunctuation();
    }

    this.tokens.push({ type: 'EOF', lexeme: '', line: this.line, col: this.col });
    return this.tokens;
  }

  readString() {
    const startLine = this.line;
    const startCol = this.col;
    this.pos++; // skip open quote
    this.col++;
    let val = "";
    while (this.pos < this.source.length && this.source[this.pos] !== '"') {
      if (this.source[this.pos] === '\n') {
        throw new Error(`Unterminated string at line ${startLine}, col ${startCol}`);
      }
      val += this.source[this.pos];
      this.pos++;
      this.col++;
    }
    if (this.pos >= this.source.length) {
      throw new Error(`Unterminated string at line ${startLine}, col ${startCol}`);
    }
    this.pos++; // skip close quote
    this.col++;
    this.tokens.push({ type: 'STRING', value: val, line: startLine, col: startCol });
  }

  readNumber() {
    const startLine = this.line;
    const startCol = this.col;
    let numStr = "";
    while (this.pos < this.source.length && /[0-9]/.test(this.source[this.pos])) {
      numStr += this.source[this.pos];
      this.pos++;
      this.col++;
    }
    this.tokens.push({ type: 'NUMBER', value: parseInt(numStr, 10), line: startLine, col: startCol });
  }

  readIdentifierOrKeyword() {
    const startLine = this.line;
    const startCol = this.col;
    let word = "";
    while (this.pos < this.source.length && /[a-zA-Z0-9_]/.test(this.source[this.pos])) {
      word += this.source[this.pos];
      this.pos++;
      this.col++;
    }

    const keywords = ['construct', 'trace', 'redpill', 'bluepill', 'dejavu', 'flatline', 'true', 'false'];
    if (keywords.includes(word)) {
      if (word === 'true' || word === 'false') {
        this.tokens.push({ type: 'BOOL', value: word === 'true', line: startLine, col: startCol });
      } else {
        this.tokens.push({ type: word.toUpperCase(), lexeme: word, line: startLine, col: startCol });
      }
    } else {
      this.tokens.push({ type: 'IDENT', value: word, line: startLine, col: startCol });
    }
  }

  readOperatorOrPunctuation() {
    const startLine = this.line;
    const startCol = this.col;
    const two = this.source.slice(this.pos, this.pos + 2);

    if (['==', '!=', '<=', '>='].includes(two)) {
      this.tokens.push({ type: two, lexeme: two, line: startLine, col: startCol });
      this.pos += 2;
      this.col += 2;
      return;
    }

    const ch = this.source[this.pos];
    if (['+', '-', '*', '/', '=', '<', '>', '(', ')'].includes(ch)) {
      this.tokens.push({ type: ch, lexeme: ch, line: startLine, col: startCol });
      this.pos++;
      this.col++;
      return;
    }

    throw new Error(`Unexpected character '${ch}' at line ${startLine}, col ${startCol}`);
  }
}

export class Parser {
  constructor(tokens) {
    this.tokens = tokens;
    this.idx = 0;
  }

  peek() {
    return this.tokens[this.idx];
  }

  consume(type) {
    const tok = this.peek();
    if (tok.type !== type) {
      throw new Error(`Expected ${type} but got ${tok.type} ('${tok.lexeme || tok.value}') at line ${tok.line}, col ${tok.col}`);
    }
    this.idx++;
    return tok;
  }

  match(type) {
    if (this.peek().type === type) {
      this.idx++;
      return true;
    }
    return false;
  }

  parse() {
    const statements = [];
    while (this.peek().type !== 'EOF') {
      statements.push(this.statement());
    }
    return { type: 'Program', statements };
  }

  statement() {
    const tok = this.peek();

    if (this.match('CONSTRUCT')) {
      const name = this.consume('IDENT').value;
      this.consume('=');
      const value = this.expression();
      return { type: 'Declare', name, value, line: tok.line, col: tok.col };
    }

    if (this.match('TRACE')) {
      const expr = this.expression();
      return { type: 'Trace', value: expr, line: tok.line, col: tok.col };
    }

    if (this.match('REDPILL')) {
      const cond = this.expression();
      const thenBody = [];
      while (this.peek().type !== 'BLUEPILL' && this.peek().type !== 'FLATLINE' && this.peek().type !== 'EOF') {
        thenBody.push(this.statement());
      }
      let elseBody = null;
      if (this.match('BLUEPILL')) {
        elseBody = [];
        while (this.peek().type !== 'FLATLINE' && this.peek().type !== 'EOF') {
          elseBody.push(this.statement());
        }
      }
      this.consume('FLATLINE');
      return { type: 'If', condition: cond, thenBody, elseBody, line: tok.line, col: tok.col };
    }

    if (this.match('DEJAVU')) {
      const cond = this.expression();
      const body = [];
      while (this.peek().type !== 'FLATLINE' && this.peek().type !== 'EOF') {
        body.push(this.statement());
      }
      this.consume('FLATLINE');
      return { type: 'While', condition: cond, body, line: tok.line, col: tok.col };
    }

    if (tok.type === 'IDENT') {
      const name = this.consume('IDENT').value;
      this.consume('=');
      const val = this.expression();
      return { type: 'Assign', name, value: val, line: tok.line, col: tok.col };
    }

    throw new Error(`Unexpected token '${tok.lexeme || tok.value}' at line ${tok.line}, col ${tok.col}`);
  }

  expression() {
    return this.equality();
  }

  equality() {
    let expr = this.comparison();
    while (['==', '!='].includes(this.peek().type)) {
      const op = this.consume(this.peek().type).type;
      const right = this.comparison();
      expr = { type: 'Binary', op, left: expr, right };
    }
    return expr;
  }

  comparison() {
    let expr = this.term();
    while (['<', '>', '<=', '>='].includes(this.peek().type)) {
      const op = this.consume(this.peek().type).type;
      const right = this.term();
      expr = { type: 'Binary', op, left: expr, right };
    }
    return expr;
  }

  term() {
    let expr = this.factor();
    while (['+', '-'].includes(this.peek().type)) {
      const op = this.consume(this.peek().type).type;
      const right = this.factor();
      expr = { type: 'Binary', op, left: expr, right };
    }
    return expr;
  }

  factor() {
    let expr = this.primary();
    while (['*', '/'].includes(this.peek().type)) {
      const op = this.consume(this.peek().type).type;
      const right = this.primary();
      expr = { type: 'Binary', op, left: expr, right };
    }
    return expr;
  }

  primary() {
    const tok = this.peek();

    if (this.match('NUMBER')) return { type: 'Literal', value: tok.value };
    if (this.match('STRING')) return { type: 'Literal', value: tok.value };
    if (this.match('BOOL')) return { type: 'Literal', value: tok.value };

    if (this.match('IDENT')) {
      return { type: 'Variable', name: tok.value };
    }

    if (this.match('(')) {
      const expr = this.expression();
      this.consume(')');
      return expr;
    }

    throw new Error(`Unexpected expression token '${tok.lexeme || tok.value}' at line ${tok.line}`);
  }
}

export class Interpreter {
  constructor(onTrace = null) {
    this.env = {};
    this.onTrace = onTrace;
    this.maxSteps = 10000;
    this.stepCount = 0;
  }

  async run(ast) {
    this.stepCount = 0;
    for (const stmt of ast.statements) {
      await this.execute(stmt);
    }
  }

  async execute(stmt) {
    this.stepCount++;
    if (this.stepCount > this.maxSteps) {
      throw new Error("Execution limit exceeded (infinite loop protection)");
    }

    if (stmt.type === 'Declare') {
      if (stmt.name in this.env) {
        throw new Error(`'${stmt.name}' is already declared`);
      }
      this.env[stmt.name] = this.evaluate(stmt.value);
    } else if (stmt.type === 'Assign') {
      if (!(stmt.name in this.env)) {
        throw new Error(`'${stmt.name}' is not declared — use 'construct' first`);
      }
      this.env[stmt.name] = this.evaluate(stmt.value);
    } else if (stmt.type === 'Trace') {
      const val = this.evaluate(stmt.value);
      const strVal = typeof val === 'boolean' ? (val ? 'true' : 'false') : String(val);
      if (this.onTrace) {
        await this.onTrace(strVal);
      }
    } else if (stmt.type === 'If') {
      const cond = this.evaluate(stmt.condition);
      if (typeof cond !== 'boolean') {
        throw new Error(`Condition must be a boolean, got ${typeof cond}`);
      }
      if (cond) {
        for (const s of stmt.thenBody) await this.execute(s);
      } else if (stmt.elseBody) {
        for (const s of stmt.elseBody) await this.execute(s);
      }
    } else if (stmt.type === 'While') {
      while (true) {
        const cond = this.evaluate(stmt.condition);
        if (typeof cond !== 'boolean') {
          throw new Error(`Condition must be a boolean, got ${typeof cond}`);
        }
        if (!cond) break;
        for (const s of stmt.body) await this.execute(s);
      }
    }
  }

  evaluate(expr) {
    if (expr.type === 'Literal') return expr.value;
    if (expr.type === 'Variable') {
      if (!(expr.name in this.env)) {
        throw new Error(`'${expr.name}' is not declared`);
      }
      return this.env[expr.name];
    }
    if (expr.type === 'Binary') {
      const left = this.evaluate(expr.left);
      const right = this.evaluate(expr.right);

      if (expr.op === '+') {
        if (typeof left === 'string' && typeof right === 'string') return left + right;
        if (typeof left === 'number' && typeof right === 'number') return left + right;
        throw new Error(`Cannot add ${typeof left} and ${typeof right}`);
      }
      if (expr.op === '-') return left - right;
      if (expr.op === '*') return left * right;
      if (expr.op === '/') {
        if (right === 0) throw new Error("Cannot divide by zero");
        return Math.trunc(left / right);
      }
      if (expr.op === '==') return left === right;
      if (expr.op === '!=') return left !== right;
      if (expr.op === '<') return left < right;
      if (expr.op === '>') return left > right;
      if (expr.op === '<=') return left <= right;
      if (expr.op === '>=') return left >= right;
    }
    throw new Error(`Unhandled expression node type: ${expr.type}`);
  }
}
