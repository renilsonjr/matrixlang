"""`python -m server` — run it from a clone."""

import sys

from server.app import DEFAULT_PORT, HOST, serve


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
