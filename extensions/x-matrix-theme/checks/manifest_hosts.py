"""Manifest hosts must be exactly x.com + twitter.com, no extra."""
import json, pathlib, sys

data = json.loads(pathlib.Path("extensions/x-matrix-theme/manifest.json").read_text())
allowed = {"*://x.com/*", "*://twitter.com/*"}
hosts = set(data.get("host_permissions", []))
matches = set()
for cs in data.get("content_scripts", []):
    matches.update(cs.get("matches", []))

if hosts != allowed or matches != allowed:
    print(f"hosts={hosts} matches={matches} want {allowed}")
    sys.exit(1)
if "storage" not in data.get("permissions", []):
    print("missing storage permission")
    sys.exit(1)
for bad in ["webRequest", "cookies", "<all_urls>", "api.x.com", "api.twitter.com"]:
    blob = json.dumps(data)
    if bad in blob:
        print(f"manifest contains forbidden {bad!r}")
        sys.exit(1)
print("manifest hosts — OK")
