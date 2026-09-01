# esolangs.org article draft — MatrixLang

Ready to paste into a new page at `esolangs.org/wiki/MatrixLang`. Verified free
(404) at the time this was written.

**Before publishing:**
1. Create a wiki account (required to create pages; I can't do this for you —
   account creation isn't something I do on your behalf).
2. Replace `[[User:YOUR-USERNAME]]` in the infobox with your actual wiki
   username once you have one, or a plain name if you'd rather not link a
   user page.
3. Paste everything in the fenced block below as the page's wikitext.
4. Every code example here was executed against the real interpreter and the
   output pasted from that run — not predicted — the same standard the
   project's own tutorial is held to. If you add more examples, run them
   first.

Syntax verified against two real, currently-live esolangs.org articles
(`Brainfuck`, `Ook!`, fetched via `Special:Export`), not guessed.

---

```wikitext
{{infobox proglang
|name=MatrixLang
|paradigms=imperative, structured
|author=[[User:YOUR-USERNAME]]
|year=[[:Category:2026|2026]]
|class=[[:Category:Turing complete|Turing complete]]
|majorimpl=[https://github.com/renilsonjr/matrixlang Reference implementation (Python)]
|files=<code>.rain</code>
}}

'''MatrixLang''' is an imperative, dynamically-typed language whose defining
feature is that every program has two interchangeable '''faces''': an ASCII
face you type, and a face written in half-width [[katakana]] glyphs that a
program running in ''The Matrix'''s style can be read in. Both are renderings
of the same syntax tree, and the toolchain converts between them without
loss — <code>parse(render_glyph(t)) == parse(render_ascii(t)) == t</code> for
any tree <code>t</code>, verified by a property test over 300 generated
programs in both faces.

The code shown on screen in ''The Matrix'' film has no grammar, no semantics,
and nothing in it runs — it was mirrored half-width katakana scanned from an
unrelated cookbook, chosen because it looked right on camera. MatrixLang does
not attempt to reproduce that code. It invents a real, executable language
that the film's aesthetic could plausibly have been standing in for: a
program can be authored normally and then viewed — never edited — in the
glyph face, the way the film's operators are shown reading a live system
rather than writing it.

MatrixLang is not affiliated with, sponsored by, or endorsed by Warner Bros.
Entertainment Inc. or any other rights holder connected to the film. The
falling glyphs are ordinary Unicode half-width katakana (U+FF66–FF9D), not
the film's own glyph designs.

==Design==

Keywords are drawn from the film's vocabulary where the film's concept and
the language concept are the same thing — <code>dejavu</code> (while) is
literally seeing the same thing happen again; <code>redpill</code> /
<code>bluepill</code> (if / else) is the choice itself; <code>jackout</code>
(return) is leaving the construct and coming back with something. Three
logical operators — <code>splice</code> (and), <code>fork</code> (or),
<code>unplug</code> (not) — are themed rather than translated, since the film
has no equivalent concept for logical conjunction; this is stated directly in
the language's own design records rather than left for a reader to notice.

The language has five types (number, boolean, string, list, dictionary),
agents (functions) with closures, and no null — a value either exists or
the name does not. There is no <code>eval</code>, no file or network access, and no
route from a program into the host language; a <code>.rain</code> file cannot
do anything beyond compute and print.

==Computational class==

MatrixLang is [[Turing complete]]: it has named mutable variables, arbitrary
exact-decimal arithmetic, conditionals, unbounded loops (<code>dejavu</code>), and
recursive agents with closures. A step counter stops a runaway loop after
200,000 statements by default; this is a configurable safety limit for the
reference implementation, not a restriction on what the language can express
— it can be raised or removed per run.

==[[Hello, world!]] program==

 trace "wake up, Neo"

Output:

 wake up, Neo

The same program in the glyph face:

 ﾄ "wake up, Neo"

Both faces parse to the same tree and produce the same output; either can be
converted to the other losslessly by the reference implementation's
<code>render</code> command.

==Example: closures==

An agent (function) defined inside another agent captures the scope where it
was ''defined'', not where it is called from — the same rule most languages
with closures use, applied to a language whose whole premise is film
vocabulary rather than conventional keywords.

 agent adder(n)
   agent add(m)
     jackout n + m
   flatline
   jackout add
 flatline

 construct add5 = adder(5)
 trace add5(37)

Output:

 42

<code>add5</code> still knows <code>n</code> was <code>5</code> long after
<code>adder</code> returned.

==External resources==
* [https://github.com/renilsonjr/matrixlang Source repository] — interpreter, REPL, CLI, and full test suite
* [https://github.com/renilsonjr/matrixlang/blob/main/docs/LEARNING-MATRIXLANG.md Learning MatrixLang] — a from-scratch tutorial covering every keyword, both faces, and closures
* [https://github.com/renilsonjr/matrixlang/blob/main/docs/TECHNICAL-OVERVIEW.md Technical overview] — the interpreter's design, the two-face round-trip property, and the project's own record of bugs it shipped and how each was caught

[[Category:Languages]]
[[Category:2026]]
[[Category:Turing complete]]
[[Category:Implemented]]
```
