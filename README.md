# MatrixLang

The code shown in *The Matrix* is not a programming language. It has no grammar, no
semantics, and no execution model. Nothing in the film runs.

This project is not "recreate the Matrix language." There is nothing to recreate. It is:

> **Invent the language the film pretended to have.**

A real, executable, Turing-complete language whose source can be written and read in
Matrix-style glyphs, with a working interpreter, a REPL, and a test suite.

Source files use the `.rain` extension.

MatrixLang is an independent, non-commercial project made by a fan, for
learning. It is not affiliated with, sponsored by, or endorsed by Warner
Bros. Entertainment Inc. or any other rights holder connected to *The
Matrix*. "The Matrix" and related marks belong to their respective owners;
nothing here uses their trademarks, logos, footage, or the film's own glyph
designs — the falling text is ordinary Unicode katakana, explained in
[The glyphs](#the-glyphs) below. Code is [MIT licensed](LICENSE); that
license covers this repository's code and nothing beyond it.

**Four ways in, depending on what you want:**

| | |
| --- | --- |
| **[Open it in a browser](https://renilsonjr.github.io/matrixlang/)** | Read what it is, then run the real interpreter in your own tab. Nothing to install |
| **[docs/LEARNING-MATRIXLANG.md](docs/LEARNING-MATRIXLANG.md)** | Learn to read and write the language. Start here if you want to *use* it |
| **[docs/NON_TECHNICAL_EXPLANATION.md](docs/NON_TECHNICAL_EXPLANATION.md)** | Explain the project to someone who does not know programming |
| **[docs/TECHNICAL-OVERVIEW.md](docs/TECHNICAL-OVERVIEW.md)** | How the implementation works — the pipeline, the module map, the problems that took real effort |
| **[Clone it and run it](#clone-it-and-run-it)** | A handful of commands and a window full of falling glyphs |
| **[X Theme for X.com](extensions/x-matrix-theme/README.md)** | Bring the glyph wall to your timeline — faint rain, Mono, and a glyph toggle for X.com |

## Status

**The language runs, and its output falls.** The cascade is the output
device: running a program opens a window in which the program's own
source and output fall as glyphs, on a loop, for as long as the window
is open. Nothing random is ever generated — every glyph on screen came
from material the program produced.

Working today: lexer, parser, tree-walking interpreter, REPL, CLI, the
two interchangeable source faces with a lossless round trip, the cascade
window, a step limit that stops runaway loops, **functions with
closures**, **lists** — literals, indexing, element assignment, `+`
concatenation, and `length` — **strings that are indexable and orderable**
— `name[0]` reads a character, and `<`/`>`/`<=`/`>=` order two strings by
codepoint, while `name[0] = "X"` is refused because strings, unlike
lists, cannot be written to — **logical operators** — `splice` (and),
`fork` (or) and `unplug` (not), boolean operands only, with `splice` and
`fork` short-circuiting so a bounded search like `n < length xs splice
xs[n] != target` never reads past the end of `xs` — **dictionaries** —
`{"a": 1}` literals keyed by strings or integers, `d["a"]` to read and
`d["a"] = v` to write or insert, `length` for the entry count, `keymaker`
for the keys in insertion order, and the infix `oracle` to ask whether a
key is there before reading it, since reading a missing one is an error —
**bitwise operators** — `mask`, `merge`, `flip`, `invert`, `uplink` and
`downlink` operate on integers, with non-negative shift counts — **Operator**,
an assistive companion that writes MatrixLang from
plain language, in the terminal or in a browser, and **Scribe**, a
keyless, deterministic companion that does the same without a key, an
SDK, or the network.

1,627 tests pass on Python 3.11 through 3.14 in CI. Zero third-party
runtime dependencies.

```
agent adder(n)
  agent add(m)
    jackout n + m
  flatline
  jackout add
flatline

construct add5 = adder(5)
trace add5(37)          # 42
```

`agent` defines, `jackout` returns. An agent captures the scope it was
*defined* in, so `add5` still knows what `n` was long after `adder`
finished.

## Clone it and run it

Anyone can clone this and run it on their own machine. It is not hosted
anywhere and does not need to be.

**Requirements:** Python 3.11 or newer, and nothing else. There are no
third-party runtime dependencies — the interpreter, the CLI and the local
server are standard library only. `pytest` is the development dependency,
and the Anthropic SDK is an optional extra that only [Operator](#operator)
needs. The cascade window uses `tkinter`, which ships with Python; if it is
missing, everything still works and output prints as text.

```bash
git clone https://github.com/renilsonjr/matrixlang.git
cd matrixlang
```

```bash
python3 -m venv .venv
```

```bash
.venv/bin/pip install -e ".[dev]"
```

Check it works — you should see the full suite pass:

```bash
.venv/bin/python -m pytest
```

Then run your first program:

```bash
.venv/bin/matrixlang run examples/hello.rain
```

A window opens, and the program's source and its output fall through it as
glyphs while it runs. Redirect instead and you get plain text:

```
0
wake up, Neo
2
```

To skip the `.venv/bin/` prefix, activate the environment first
(`source .venv/bin/activate`), after which plain `matrixlang` works.

Now go write something: **[docs/LEARNING-MATRIXLANG.md](docs/LEARNING-MATRIXLANG.md)**
teaches the whole language — twenty-five keywords, five types, and both faces —
and every example in it was executed before it shipped.

### Seeing the cascade

The window opens when you run a program from an interactive shell. It
deliberately declines whenever output is being captured rather than
displayed — a pipe, a redirect, a CI job — which is the same guarantee
that keeps `matrixlang run prog.rain > out.txt` byte-clean. Seeing no
window in those contexts is correct behaviour, not a fault.

What falls is your program, and nothing else. Source lines and output
are both transliterated, so the cascade is a **pure glyph wall** with no
Latin in it. It is decodable rather than decorative: the table is
reversible, so `ﾁ｡ｵ･ ｿｺﾆ ﾛｸ･ｹ` reads back as `wake up, Neo`.

Source falls faster; output falls slower and brighter, so results linger.
When everything has fallen off the bottom it starts again — a screen that
stops is not a cascade.

`glyph_source=False` on `CascadeField` or `CascadeWindow` puts Latin
identifiers back, if you would rather read the source as you wrote it.

If you expected a window and got text, this prints the actual decision
using the same code the runner uses:

```bash
.venv/bin/python -c "import os,sys;from matrixlang.display import choose_backend,tk_is_available;print(f'isatty={sys.stdout.isatty()} NO_COLOR={\"NO_COLOR\" in os.environ} tk={tk_is_available()} -> {choose_backend(isatty=sys.stdout.isatty(),env=os.environ,want_window=True,tk_available=tk_is_available()).name}')"
```

`TEXT` is explained by whichever condition failed: no TTY, `NO_COLOR`
set, or no working `tkinter`.

### If the import fails

If anything reports `ModuleNotFoundError: No module named 'matrixlang'`
right after a successful install, run:

```bash
chflags -R nohidden .venv
```

Some macOS systems intermittently set a hidden flag on venv files, which
Python ≥3.14 silently skips when processing `.pth` files. This is a
platform quirk, not a project one.

## Usage

```bash
.venv/bin/matrixlang lex examples/hello.rain
```

Prints one `line:column<TAB>TOKEN_TYPE<TAB>lexeme` row per token.
`render --face glyph` prints the same
program in half-width katakana; `render --face ascii` converts it back
(and doubles as a formatter — whitespace normalizes to canonical form).

```bash
.venv/bin/matrixlang render --face glyph examples/hello.rain
```

In the REPL, `:glyph` echoes each statement in the operator view as you
type ASCII; `:ascii` turns it back off. Glyph and mixed-face source are
accepted everywhere with no mode flag — glyphs and ASCII identifiers
occupy disjoint alphabets, so one lexer reads both.

```bash
.venv/bin/matrixlang parse examples/hello.rain
```

Prints the syntax tree as indented text — the tree's shape is the precedence lesson.

```bash
.venv/bin/matrixlang run examples/hello.rain
.venv/bin/matrixlang repl
```

`run` executes a program into the cascade window. `repl` starts an
interactive session — blocks span multiple lines, so a `dejavu` loop can
be typed at the prompt. The REPL never cascades: motion and legibility
are adversaries, so the display belongs to the runner and not to the
editing surface.

The window declines itself whenever it would be unwelcome — a redirected
or piped stdout, `NO_COLOR`, or no working `tkinter`. `matrixlang run
prog.rain > out.txt` writes exactly the bytes it always did.

Diagnostics are never transliterated. They appear as plain text in the
window's status strip and on stderr, because an error is the moment a
reader's fluency has failed and glyphs are the worst possible response
to that.

```bash
.venv/bin/matrixlang run --no-window examples/hello.rain
```

`--no-window` prints as text instead, which is what you want while iterating.

### Runaway programs

`run` stops after 200,000 statements and reports it as an ordinary
diagnostic with a line and column:

```
matrixlang: [line 3, column 3] program exceeded the step limit — likely an infinite loop
```

The limit counts **statements executed**, not stack depth, so a
`dejavu true` loop is caught even though it never grows the stack. Raise
it, lower it, or remove it entirely:

```bash
.venv/bin/matrixlang run --max-steps 0 examples/hello.rain
```

`0` means no limit.

## Operator

Operator writes MatrixLang from plain language. It is optional, it is the
only part of the project with a dependency, and it costs money to use —
everything above runs on the standard library alone.

```bash
.venv/bin/pip install -e ".[bot]"
```

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

**Operator is never the authority on whether its own output is valid.**
Every candidate program is parsed and dry-run before you see it. If
either fails, the real diagnostic — line, column and all — goes back to
the model and it tries again, at most three times. Nothing unvalidated
reaches your editor, and the attempts it took are shown rather than
hidden, because that gate is the whole design.

### In a browser

```bash
.venv/bin/python -m server
```

Then open <http://127.0.0.1:8420>. The program is top-left, Operator is
bottom-left, and the cascade fills the right-hand side at full height —
the same cascade as the native window, carrying the same material, with
a button to switch the falling source between glyphs and Latin.

The server is `http.server` and Server-Sent Events, no framework and no
build step, for the same reason the package has no dependencies. It
binds `127.0.0.1` and nothing else. It has no accounts, no rate limits
and no abuse handling, so **do not expose it to a network** — hosting
this as a product would mean designing all of that first, and that is
deliberately out of scope.

`server/` is not part of the installed package on purpose: a top-level
`server` module would collide with half of PyPI. It runs from a clone,
which is the model this project chose.

## Scribe

Scribe writes MatrixLang from plain language too, and it needs none of
what Operator needs: no API key, no SDK, no network. It is a finite
catalogue of intent patterns, matched deterministically — the same
request always produces the same program, because nothing is asked of a
model. It is optional, it has no dependency, and it runs on the standard
library alone.

Every program Scribe produces is parsed and dry-run before it is shown,
through the same gate Operator answers to. Nothing unvalidated reaches
you, and a request that matches nothing is refused with a hint at the
closest phrasing it knows rather than a guess. When an API key is
configured, the server also flags that Operator could take the request —
and the browser offers the switch.

A few requests Scribe understands:

```
add 5 and 3                          trace 5 + 3
count from 1 to 10                   construct i = 1
                                     dejavu i <= 10
                                       trace i
                                       i = i + 1
                                     flatline
make a list of 1 2 3                 construct xs = [1, 2, 3]
if 5 is greater than 3 trace bigger  redpill 5 > 3
                                       trace "bigger"
                                     flatline
```

### In a browser

The same chat surface, with an engine toggle. Scribe is the server's
default: `/api/chat` answers as Scribe unless asked for `operator`, so
the page works with no key installed. A miss shows the hint in the chat
and, when a key is present, offers the switch to Operator.

## In a browser, with nothing installed

<https://renilsonjr.github.io/matrixlang/>

The page explains what the project is, and then runs the language in your
own browser tab. There is no server on the other end of it: it fetches
Python compiled to WebAssembly along with this project's wheel, built by
CI from the same commit the page is published from, and executes
`src/matrixlang/` locally. Whatever you type stays on your machine,
because the page has nowhere to send it.

That is also why hosting this needed no login, no rate limiting, and no
answer to running strangers' code — the property that made clone-and-run
acceptable is unchanged. **Nobody's code runs on anybody else's computer.**

Reading it costs about 24&nbsp;KB. Pressing the button costs roughly
13&nbsp;MB — Pyodide's WebAssembly build is 10 of that, the Python
standard library another 2, and this project's wheel 66&nbsp;KB — fetched
once, then cached, and about three seconds to a working editor on a fast
connection. Nothing loads until you ask, so a reader who only wants the
explanation pays none of it.

[Scribe](#scribe) works there with no key. [Operator](#operator) is
present but needs an Anthropic API key you supply yourself; it is held in
the tab's memory, never stored, and sent nowhere but Anthropic. Pasting an
API key into a web page is a habit worth being suspicious of, which is
why the page says so plainly and links to the file that makes the call.

There is one thing the browser cannot do: `tkinter` is not there, so the
native cascade window has no equivalent. The page draws the same cascade
on a canvas from the same events, which is what `web-ui/` already did for
the local server.

## X Theme for X.com

A browser extension that brings MatrixLang to your timeline — the same palette, Mono, faint rain behind the feed, and a global **Glyph ◐ Latin** toggle.

[![X Theme — Download](https://img.shields.io/badge/X%20Theme-%2300ff41?style=for-the-badge&logo=x&logoColor=white)](https://github.com/renilsonjr/matrixlang/releases/latest/download/x-matrix-theme.zip)

**Click to install:**

1. Click the badge above to download `x-matrix-theme.zip` — or get it from the [latest release](https://github.com/renilsonjr/matrixlang/releases) or [Actions artifact](../../actions/workflows/x-theme.yml)
2. Unzip it
3. Open `chrome://extensions` (or `brave://extensions`, `edge://extensions`) → **Developer mode** ON → **Load unpacked** → pick the `x-matrix-theme` folder
4. Open `https://x.com/home` → faint rain behind the timeline, toggle says **Glyph ◐ Latin** — click to flip

Firefox: `about:debugging` → **This Firefox** → **Load Temporary Add-on** → pick `manifest.json`. See `extensions/x-matrix-theme/README.md` for checks and the 6-step manual acceptance.

> Chrome blocks true one-click installs outside the Web Store — this is the closest click-to-install before publishing. When it’s published, this badge will become **Add to Chrome** (one click, auto-updates).

## The glyphs

The falling characters are Unicode half-width katakana (U+FF66–FF9D), not
the film's own glyphs.

The real ones were reverse-engineered by
[Rezmason/matrix](https://github.com/Rezmason/matrix) from an archived
promotional asset: mirrored katakana scanned out of a Japanese cookbook,
plus characters from Susan Kare's Chicago typeface and the expanded set
from *Resurrections*. That work is the reference for what the film's code
actually looks like, and this project is indebted to it.

That project now ships `Matrix-Code.ttf` and `Matrix-Resurrected.ttf`, so
the film's glyphs *are* available as fonts — an earlier version of this
README said they were not, which was true when the glyphs existed only as
WebGL data and is no longer. Swapping them in is a change to `glyphs.py`
and nothing else, which is what the swappability guard exists to protect.
Half-width katakana are kept for now because they render anywhere with
zero font work.

Digital rain is solved work with many good implementations (TMatrix,
green_rain, RGB-digital-rain, Rezmason's). None of them are what this is:
those animate noise, and this animates a running program. The cells carry
your source and your output, and the transliteration is reversible, so
what falls can be read back rather than merely watched.

## Development

Setup is the same as [Clone it and run it](#clone-it-and-run-it). To run
the suite:

```bash
.venv/bin/python -m pytest
```

It runs on every pull request against Python 3.11, 3.12, 3.13 and 3.14.

[docs/TECHNICAL-OVERVIEW.md](docs/TECHNICAL-OVERVIEW.md) is the fastest way
in: the compilation pipeline, what each module owns, and the eight design
problems that took real work — reconstructing parentheses from a tree that
does not store them, the round-trip property, why testing an animation
required splitting the code on a purity gradient, and how the browser gets
the same cascade without a second implementation of the language.

Specs and implementation plans live under `docs/superpowers/`, written
before the code and kept as the record of why the thing is shaped the way
it is. Stages 1–5 each have a design spec and a plan; the cascade window,
Stage 6 and Operator have specs. The cascade window's spec has a §10
worth reading on its own — it records two wrong answers that passed a
full test suite and were only caught by a human opening the window.

### A note on untrusted `.rain` files

The interpreter is deliberately small: a MatrixLang program has no file
access, no network, no process spawning, and no route into Python — there
is no `eval`, no `exec`, and no deserialization anywhere in the package.

Raw terminal control characters are refused by the lexer, in string literals
and comments alike, so a `.rain` file cannot drive your terminal with escape
sequences — whether you run it or merely inspect it with `parse` or `render`.
The refusal happens at the lexer rather than by escaping output, because
`render` has to reproduce source exactly; the reasoning is in the
language-surface spec §3.4.

That is not a sandbox, and this is not a security product. Two things it
deliberately does not cover: an AST built directly in Python rather than
parsed from source is not subject to the control-character rule, and
`--max-steps 0` removes the runaway-loop guard on request.

A program **can** still express an unbounded loop — that is what
Turing-completeness means — but by default it will be stopped after
200,000 statements rather than running until you kill it.
