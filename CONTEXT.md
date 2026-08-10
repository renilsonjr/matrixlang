# MatrixLang

A programming language whose two textual forms — ASCII and glyph — are both
faces of one syntax tree, plus a browser-hosted playground that runs it and a
cascade display that renders its execution as falling text.

## Language

**Face**:
One of the two textual renderings of a MatrixLang program — the ASCII face or
the glyph face — produced directly from the syntax tree by `render_ascii` or
`render_glyph`. A face is a property of the *language*, governed by D-03: it
round-trips through the lexer, `parse(lex(render_X(t))) == t`, for both faces.
_Avoid_: "Latin face" (nothing in the codebase renders one — see
Transliteration), "view", "mode".

**Transliteration**:
A reversible, *display-only* substitution — via `translit.py`'s dictionary —
applied to arbitrary text for the cascade. Its round-trip is its own,
`untransliterate(transliterate(t)) == t`, and is unrelated to a face's
lexer round-trip: transliterated text is never fed back through `parse`/`lex`.
It may reuse glyph slots the language's own glyph face already uses, because a
parser never has to tell the two apart. Applies to *any* text — English prose,
program output, or a glyph face that's had transliteration applied a second
time — not only to source.
_Avoid_: "face" (a transliteration is not one — it doesn't round-trip through
the lexer and isn't a property of the syntax tree).

**Cascade**:
The falling-text simulation and its display — `CascadeField` (Python),
`Cascade` (JS), one instance per surface (native window, local server, the
published page). Draws only transliterated text or plain output text, never a
face directly, and never generates content: everything on screen came from the
program that ran.
_Avoid_: using "face" for what the cascade shows — see
[ADR-0001](docs/adr/0001-defer-cascade-wire-field-rename.md) for a naming
mismatch in its current wire format.
