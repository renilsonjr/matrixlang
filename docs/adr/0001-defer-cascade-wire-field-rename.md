# Defer renaming `sse.payload()`'s `source`/`latin` fields

`server/sse.py`'s wire format calls its two statement fields `source` and
`latin`. Neither matches the Face/Transliteration distinction in
`CONTEXT.md`: `source` is the glyph face transliterated a second time (fully
glyph, no Latin at all), and `latin` is the glyph face *un*-transliterated
(keywords glyph, identifiers stay Latin) — the field named "latin" is the one
least deserving the name. The playground's cascade toggle
(`site/playground.js`) inherited the same naming and has never actually shown
the ASCII face.

We are not renaming it now. `server/sse.py` is consumed by both `web-ui/` and
the published playground, so this is a breaking wire-format change with two
live call sites, and it deserves its own spec rather than riding in on a
glossary session. The mismatch is recorded here so nobody "fixes" the naming
inline without accounting for both consumers, and so the eventual rename has
a clear starting citation.
