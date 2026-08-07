# JetBrains Mono

The face the page is set in — headline, labels, and every code block.

## Where these files came from

Unmodified basic-latin `woff2` subsets, exactly as Google Fonts serves them.
Nothing here has been re-subset or otherwise edited by hand: they are byte
copies of upstream, so anyone can reproduce them and the licence applies to a
file the licensor actually published.

```sh
curl -s -A "$(modern browser UA)" \
  "https://fonts.googleapis.com/css2?family=JetBrains+Mono:ital,wght@0,400;0,700;1,700&display=swap"
```

That returns one `@font-face` block per weight per unicode-range. Keep the
blocks whose `unicode-range` contains `U+0000-00FF` — the basic-latin subset —
and download the `woff2` each one points at.

The user-agent matters: without a modern one, Google Fonts serves `ttf`
instead of `woff2`, which is roughly four times the size.

## Why three faces and not six

| file | used by |
|---|---|
| `jetbrains-mono-400.woff2` | code blocks, labels, eyebrows, the examples |
| `jetbrains-mono-700.woff2` | the headline |
| `jetbrains-mono-700-italic.woff2` | `<i>The Matrix</i>`, inside the headline |

A 400 italic was fetched first and then dropped: nothing on the page renders
italic inside a monospace element except that one headline phrase, so no
browser ever requested the file. If one is ever needed, the browser
synthesises an oblique from the 400 upright.

## What these fonts do not contain

Half-width katakana. The basic-latin subset stops at `U+00FF`, and every
glyph the page prints lives at `U+FF61`–`U+FF9D`. Those characters fall
through to the next family in `--mono` (Menlo, SF Mono), which do carry them.
**That fallback chain in `site/style.css` is load-bearing** — shorten it to
`"JetBrains Mono", monospace` and every example renders as tofu.

## Licence

SIL Open Font License 1.1. `OFL.txt` is the licence text and must travel with
the fonts; the OFL permits bundling and redistribution, and requires the
notice be kept. Copyright 2020 The JetBrains Mono Project Authors.

## Cost

About 84 KB for the three faces, against roughly 18 KB for the rest of the
page before the interpreter loads. The page states its own weight in the
"Now run one yourself" section — if these files change, that number changes
with them.
