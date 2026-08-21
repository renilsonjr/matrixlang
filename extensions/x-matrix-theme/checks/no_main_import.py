"""Extension must not import matrixlang main — table/cascade are copied."""
import pathlib, re, sys

root = pathlib.Path("extensions/x-matrix-theme")
fails = []
for path in root.rglob("*.js"):
    if "checks" in path.parts: continue
    text = path.read_text()
    if re.search(r"from\s+matrixlang|import\s+matrixlang|server/sse|from\s+server", text):
        fails.append(str(path))

if fails:
    print("extension imports main:")
    for f in fails: print(" ", f)
    sys.exit(1)
print("no main import in extension — OK")
