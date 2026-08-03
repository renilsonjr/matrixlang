"""`python -m server` — run it from a clone.

`server/` is deliberately not packaged (see pyproject: a top-level
`server` on PyPI would collide with half the ecosystem), so it is only
ever run from a checkout. But `server.runs` imports `matrixlang`, and a
bare clone has no way to find it — `python -m server` died with
`ModuleNotFoundError: No module named 'matrixlang'` unless the package
had been installed first. Putting `src/` on the path here makes the
clone-and-run model the README promises literally true, with no install
step and nothing added to the environment.

Prepended, not appended, and that is the intended precedence: this
module only ever runs from a clone, so the clone's own source is the
copy that should win over anything installed elsewhere. Appending would
silently run a different `matrixlang` than the one you are editing.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

# Imported after the path is set, not at the top, because this import is
# what triggers the matrixlang lookup that the block above exists to fix.
from server.app import DEFAULT_PORT, HOST, serve  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    port = int(argv[0]) if argv else DEFAULT_PORT
    httpd = serve(port)
    print(f"operator listening on http://{HOST}:{httpd.server_address[1]}")
    print("POST /api/chat · POST /api/run · GET /api/events?run=<id>")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        httpd.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
