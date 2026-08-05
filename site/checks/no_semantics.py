"""The no-semantics gate: playground.js may draw, but must not know the language.

Comments are stripped before checking. The rule is about what the code
DOES, not what its prose is allowed to name — an earlier version grepped
the raw file, so a comment explaining the rule tripped it, and the only
way to pass was to write around the obvious verb.
"""
import pathlib, re, sys

src = pathlib.Path("site/playground.js").read_text()
code = re.sub(r"/\*.*?\*/", "", src, flags=re.S)          # block comments
code = re.sub(r"^\s*//.*$", "", code, flags=re.M)          # line comments
code = re.sub(r"(?<![:/])//.*$", "", code, flags=re.M)     # trailing comments

failures = []
if re.search(r"[ｦ-ﾝ]", code):
    failures.append("contains a half-width katakana literal (a glyph table)")
for name in ["transliterate", "untransliterate"]:
    if re.search(rf"\b{name}\s*\(", code):
        failures.append(f"calls {name}()")
for pattern, what in [(r"\bfunction\s+lex\b", "defines lex()"),
                      (r"\bfunction\s+parse\b", "defines parse()"),
                      (r"\bconst\s+GLYPHS?\b", "declares a glyph table")]:
    if re.search(pattern, code):
        failures.append(what)

if failures:
    print("playground.js owns language logic:")
    for f in failures: print("  -", f)
    sys.exit(1)
print("no semantics in the browser half")
