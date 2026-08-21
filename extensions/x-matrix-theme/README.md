# MatrixLang — X Theme

Full Matrix theme for X.com timeline. Isolated extension — Load unpacked.

## Install

1. Open `chrome://extensions` → Developer mode ON → Load unpacked → `extensions/x-matrix-theme`
2. Same for Firefox `about:debugging`

## Checks (extension-only)

- `python extensions/x-matrix-theme/checks/no_main_import.py` — no import of src/
- `python extensions/x-matrix-theme/checks/manifest_hosts.py` — hosts == x.com + twitter.com

## Manual acceptance (timeline-first, Load unpacked)

1. Install: Load unpacked → open `x.com/home` → faint rain behind feed, toggle says `Glyph ◐ Latin`
2. Click toggle → every visible tweet flips to glyph with `↳ original:` underneath; button flips to `Latin ◑ Glyph`
3. Scroll — new tweets appear in glyph face automatically; toggle back → all revert, including new ones
4. SPA: `Home` → profile → `Home` → timeline still in chosen face, rain still behind
5. `prefers-reduced-motion: reduce` (DevTools → Rendering → Emulate) → rain canvas absent, toggle still works
6. Block `theme.css` in DevTools → tweets still toggle (layers isolated)

## Layer isolation

- `theme.css` — paint only
- `rain.js` — canvas only, pauses on `visibilitychange` / reduced-motion
- `glyph.js` — table + walk only, `MLGlyph` global
- `content.js` — glue only, `chrome.storage.local` + observer
