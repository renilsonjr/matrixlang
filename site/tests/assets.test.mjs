// The page's non-code assets, and the two rules that keep them working.
//
// Both invariants here look like tidy-up bait. The `--mono` fallback chain
// reads as redundant belt-and-braces until you know the shipped subset has no
// katakana in it, and `font-src` reads as boilerplate until you know the CSP
// denies by default. Shortening either is a one-line change that breaks the
// page in a way no other test would notice.

import assert from "node:assert/strict";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const SITE = join(dirname(fileURLToPath(import.meta.url)), "..");
const CSS = readFileSync(join(SITE, "style.css"), "utf8");
const HTML = readFileSync(join(SITE, "index.html"), "utf8");
const WORKFLOW = readFileSync(
  join(SITE, "..", ".github", "workflows", "pages.yml"), "utf8",
);

test("every font the stylesheet asks for is actually in the repo", () => {
  const referenced = [...CSS.matchAll(/url\("(fonts\/[^"]+)"\)/g)].map((m) => m[1]);
  assert.ok(referenced.length, "no @font-face src found — did the paths change?");
  for (const path of referenced) {
    assert.ok(existsSync(join(SITE, path)), `style.css asks for ${path}, which does not exist`);
  }
});

test("no font file is shipped that nothing asks for", () => {
  // A face nobody references is weight in the repo and in the deploy that no
  // browser will ever fetch — the 400 italic was exactly that.
  const referenced = new Set(
    [...CSS.matchAll(/url\("fonts\/([^"]+)"\)/g)].map((m) => m[1]),
  );
  for (const file of readdirSync(join(SITE, "fonts")).filter((f) => f.endsWith(".woff2"))) {
    assert.ok(referenced.has(file), `fonts/${file} is shipped but never referenced`);
  }
});

test("the mono stack keeps a fallback past JetBrains Mono", () => {
  // The shipped subset is basic latin: 229 codepoints, none of them the
  // half-width katakana this page prints in every example. Those characters
  // reach the reader only because Menlo and SF Mono are still in the chain.
  const declaration = CSS.match(/--mono:\s*([^;]+);/);
  assert.ok(declaration, "--mono is gone");
  const families = declaration[1].split(",").map((f) => f.trim().replace(/^["']|["']$/g, ""));
  assert.equal(families[0], "JetBrains Mono");
  assert.ok(
    families.length >= 3,
    `--mono fell back to ${families.length} families; the katakana in every ` +
      `example would render as tofu. Keep Menlo/SF Mono after JetBrains Mono.`,
  );
});

test("the licence ships with the fonts, as the OFL requires", () => {
  // Serving a font on the web is redistribution, and the OFL requires the
  // notice travel with it.
  assert.ok(existsSync(join(SITE, "fonts", "OFL.txt")), "fonts/OFL.txt is missing");
  assert.match(readFileSync(join(SITE, "fonts", "OFL.txt"), "utf8"), /SIL Open Font License/);
});

test("the fonts directory is copied into the deploy", () => {
  assert.match(
    WORKFLOW, /cp -R site\/fonts/,
    "pages.yml never copies site/fonts — the page would 404 every face in production",
  );
});

test("the CSP allows same-origin fonts", () => {
  // default-src is 'none', so without an explicit font-src every @font-face
  // is blocked and the page silently falls back to Menlo.
  const csp = HTML.match(/Content-Security-Policy"\s+content="([^"]+)"/s);
  assert.ok(csp, "the CSP meta tag is gone");
  assert.match(
    csp[1], /font-src\s+'self'/,
    "the CSP has no font-src; default-src 'none' would block every face",
  );
});
