# Learning MatrixLang

Everything the language can do, in the order that makes it easiest to pick
up. You do not need to have read anything else in this repository.

MatrixLang has sixteen keywords, four types, and two ways of writing
every program: **ASCII**, which you type, and **glyphs**, which you
read. They are the same program — the toolchain converts between them
without loss.

```bash
.venv/bin/matrixlang run examples/hello.rain
```

---

## 1. Your first program

```
trace "wake up, Neo"
```

`trace` prints. That is the only way a program produces output; there is
no `print` and no `return` to a console. Reading input has its own two
keywords — see §17.

Save it as `hello.rain` and run it:

```bash
.venv/bin/matrixlang run --no-window hello.rain
```

```
wake up, Neo
```

`--no-window` prints to the terminal. Without it, a window opens and the
program falls through it as glyphs — see §12.

---

## 2. Names

```
construct name = "Neo"
trace name
```

`construct` **declares** a name. Plain `=` **assigns** to a name that
already exists:

```
construct n = 0
n = n + 1        # fine: n was declared
```

Two rules that will catch you once each, and then never again:

```
construct n = 1
construct n = 2    # error: 'n' is already declared
```

```
total = 10         # error: 'total' is not declared — use 'construct' first
```

This is deliberate. `construct` means something rather than being
decoration: seeing it tells you a name is *new* here, and its absence
tells you the name already exists somewhere above.

---

## 3. Types — there are four

| Type | Examples |
| --- | --- |
| integer | `0`, `42`, `-7` |
| boolean | `true`, `false` |
| string | `"Neo"`, `""`, `"wake up"` |
| list | `[1, 2, 3]`, `[]`, `["Neo", true]` |

No floats, no dictionaries, no sets, and **no null**. If you are used to
a language where a missing value is `null` or `None`, there is nothing
here that corresponds — a name either holds a value or does not exist.
Lists get their own section (§7) once agents have been introduced,
because the interesting thing about them — that they are shared, not
copied — is easiest to show with one.

### Arithmetic

```
trace 7 + 3        # 10
trace 7 - 3        # 4
trace 7 * 3        # 21
trace 7 / 3        # 2
```

Division **truncates toward zero**, so `-7 / 2` is `-3`, not `-4`. Most
languages that floor would give you `-4`; this one rounds toward zero in
both directions, which is the behaviour most people expect when they first
meet it.

### `+` joins strings too

```
trace "wake up, " + "Neo"     # wake up, Neo
```

But never both at once:

```
trace "n = " + 5              # error: cannot add string and integer
```

There is no automatic conversion. If you want a number in a message, you
currently cannot interpolate it — this is a real limit of the language,
not a trick you are missing.

### Comparison

```
trace 3 < 5        # true
trace 3 == 3       # true
trace 3 != 3       # false
```

`<`, `>`, `<=`, `>=` order two values of the same type — see below for
which types. `==` and `!=` compare two values of the *same* type;
comparing across types is an error rather than `false`, because that
comparison is almost always a mistake.

### Ordering strings

The same four operators order two strings:

```
trace "Neo" < "Trinity"     # true
```

The order is **codepoint order**, not the alphabetical order a dictionary
uses. `"a" < "B"` is `false`, because comparison looks at each character's
underlying number, and every uppercase letter (`A`–`Z`) has a lower
number than every lowercase one (`a`–`z`):

```
trace "a" < "B"      # false
```

This is not a quirk of this language — Python, Java and C all order
strings the same way, for the same reason.

Ordering across types is an error, the same way adding them is:

```
trace "Neo" < 5
```

```
matrixlang: [line 1, column 13] cannot order string with integer
```

---

## 4. Choosing — `redpill` / `bluepill`

```
construct n = 1

redpill n == 1
  trace "the one"
bluepill
  trace "not yet"
flatline
```

`redpill` is *if*, `bluepill` is *else*, and `flatline` closes the block.
The `bluepill` is optional:

```
redpill n > 100
  trace "large"
flatline
```

**Conditions must be boolean.** There is no truthiness:

```
redpill 1          # error: condition must be a boolean, got integer
```

There is no `else if`. Nest instead:

```
redpill n == 1
  trace "one"
bluepill
  redpill n == 2
    trace "two"
  bluepill
    trace "many"
  flatline
flatline
```

---

## 5. Repeating — `dejavu`

```
construct n = 3
dejavu n > 0
  trace n
  n = n - 1
flatline
```

```
3
2
1
```

`dejavu` is *while*. Same rules: the condition must be boolean, and
`flatline` closes it.

There is no `for`, no `break`, and no `continue`. A counter and a
condition are how loops are written here.

> **A loop that never ends** is stopped after 200,000 statements with a
> diagnostic rather than running forever. Raise or remove the limit with
> `--max-steps N`, where `0` means no limit.

---

## 6. Agents — naming a computation

```
agent double(n)
  jackout n * 2
flatline

trace double(21)      # 42
```

`agent` defines; `jackout` returns. An Agent in the films is a callable,
reusable program, which is what this is.

Parameters are named in parentheses and separated by commas:

```
agent add(a, b)
  jackout a + b
flatline

trace add(1, 2)       # 3
```

### Agents can call themselves

```
agent fib(n)
  redpill n < 2
    jackout n
  flatline
  jackout fib(n - 1) + fib(n - 2)
flatline

trace fib(10)         # 55
```

### An agent that returns nothing

`jackout` with no value exits early:

```
agent log(message)
  redpill message == ""
    jackout
  flatline
  trace message
flatline

log("")               # returns immediately, prints nothing
log("wake up")        # wake up
```

An agent that never reaches a `jackout` with a value produces **nothing**
— and *nothing* is not a value you can hold:

```
log("hi")             # fine: called as a statement
trace log("hi")       # error: agent 'log' did not jack out a value
```

That error is the language telling you it has no null to give you.

---

## 7. Lists

```
trace ["Neo", "Trinity", "Morpheus"]
```

```
["Neo", "Trinity", "Morpheus"]
```

A list is a sequence of values inside `[` and `]`, comma-separated.
Elements can be any type, mixed freely:

```
trace [1, true, "Neo"]      # [1, true, "Neo"]
```

Notice the strings are quoted *inside* the list but not at the top level
(compare `trace "Neo"`, which prints `Neo`). Without the quotes there
would be no way to tell a string from a name in the printed form — the
top level keeps its old, unquoted behaviour so it does not change what
every earlier program in this file prints.

### Reading an element — `xs[0]`

Indexing is zero-based:

```
construct crew = ["Neo", "Trinity", "Morpheus"]
trace crew[0]                # Neo
```

### A string indexes the same way — `name[0]`

```
construct name = "Neo"
trace name[0]                # N
```

There is no separate character type. Indexing a string returns another
**string, one character long** — so it can be indexed again:

```
construct name = "Neo"
trace name[0][0]             # N
```

`name[0][0]` does not drill down into something smaller. Asking a
one-character string for its own first character just returns itself —
the regress stops because you stop asking, not because there is a
character type underneath waiting to be reached.

### Writing an element — `xs[0] = v`

```
construct crew = ["Neo", "Trinity", "Morpheus"]
crew[0] = "Mr. Anderson"
trace crew
```

```
["Mr. Anderson", "Trinity", "Morpheus"]
```

This **mutates** the list — there is no new list produced. Keep that in
mind for the "shared" section below.

### `length`

`length` is a keyword, not a function call — no parentheses. It works on
lists and strings alike:

```
trace length ["Neo", "Trinity", "Morpheus"]     # 3
trace length "Neo"                              # 3
trace length []                                 # 0
```

### `+` concatenates, and copies

```
trace [1, 2] + [3]      # [1, 2, 3]
```

`+` always builds a **new** list. It never mutates either side:

```
construct xs = [1]
construct ys = xs + [2]
xs[0] = 99
trace xs
trace ys
```

```
[99]
[1, 2]
```

`ys` does not see the change to `xs` — concatenation copied, so the two
lists are independent from the moment `+` ran.

### Walking one with `dejavu`

```
construct crew = ["Neo", "Trinity", "Morpheus"]
construct n = 0
dejavu n < length crew
  trace crew[n]
  n = n + 1
flatline
```

```
Neo
Trinity
Morpheus
```

There is still no `for`. A counter, `length`, and `dejavu` are how you
walk a list here.

### Walking a string the same way

```
construct name = "Neo"
construct n = 0
dejavu n < length name
  trace name[n]
  n = n + 1
flatline
```

```
N
e
o
```

Same pattern as walking a list, because `length` already worked on
strings (see §3) and now indexing does too.

### Lists are shared, not copied

Assigning a list to another name, or passing it as an argument, does not
copy it — both names refer to the same list, so a mutation through one
is visible through the other. This is the one place in the language with
reference semantics; every other type is a value.

```
agent bump(zs)
  zs[0] = zs[0] + 1
flatline

construct xs = [1]
bump(xs)
trace xs[0]      # 2
```

`bump` did not receive a copy of `xs`. It received the same list `xs`
points at, and `zs[0] = zs[0] + 1` mutated that list in place — which is
why the change is visible back at the call site through `xs`.

### Strings cannot be written to

`xs[0] = v` works on a list, as above. The same syntax on a string is
refused:

```
construct name = "Neo"
name[0] = "X"
```

```
matrixlang: [line 2, column 6] a string cannot be changed — build a new one with +
```

This is not a missing feature — it is the other half of a trade. A list
handed to an agent can come back changed, because that is exactly what
`bump` just did. A **string** handed to an agent is guaranteed to come
back exactly as it went in, because nothing in the language can write
through it, no matter how many agents it gets passed to. Lists gave that
guarantee up in exchange for in-place mutation; strings kept it. When you
need a different string, `+` (§3) builds a new one — it does not change
the old one.

### Four more new errors

Four more, on top of the "a string cannot be changed" refusal already
shown above:

```
construct xs = [1, 2]
trace xs[5]
```

```
matrixlang: [line 2, column 9] index 5 is past the end of a list of length 2
```

```
construct xs = [1]
trace xs[-1]
```

```
matrixlang: [line 2, column 9] an index cannot be negative — use xs[length xs - 1]
```

```
construct n = 1
trace n[0]
```

```
matrixlang: [line 2, column 8] cannot index integer
```

```
trace [1] + 2
```

```
matrixlang: [line 1, column 11] cannot add list and integer
```

Indexing a string out of bounds gives the same message as a list, with
the noun changed:

```
construct name = "Neo"
trace name[5]
```

```
matrixlang: [line 2, column 11] index 5 is past the end of a string of length 3
```

A negative string index gives a related message, but not by swapping a
noun — the fix-it example changes its placeholder from `xs` to `s`:

```
construct name = "Neo"
trace name[-1]
```

```
matrixlang: [line 2, column 11] an index cannot be negative — use s[length s - 1]
```

---

## 8. Logical operators — `splice`, `fork`, `unplug`

```
trace true splice false     # false
trace true fork false       # true
trace unplug true           # false
```

`splice` is *and*, `fork` is *or*, `unplug` is *not*. The truth table:

| `a` | `b` | `a splice b` | `a fork b` |
| --- | --- | --- | --- |
| `true` | `true` | `true` | `true` |
| `true` | `false` | `false` | `true` |
| `false` | `true` | `false` | `true` |
| `false` | `false` | `false` | `false` |

**Operands must be boolean.** Same rule as `redpill` — there is no
truthiness anywhere in this language:

```
trace 1 splice true
```

```
matrixlang: [line 1, column 7] 'splice' takes booleans, got integer
```

### `unplug` binds looser than comparison

```
construct n = 1
trace unplug n == 1
```

```
false
```

`unplug n == 1` means `unplug (n == 1)`, not `(unplug n) == 1` — the
tight reading would compare a boolean to `1`, which is an error for
every possible `n`:

```
construct n = 1
trace (unplug n) == 1
```

```
matrixlang: [line 2, column 8] 'unplug' takes a boolean, got integer
```

### `splice` and `fork` short-circuit

`a splice b` skips `b` entirely once `a` is already `false`. `a fork b`
skips `b` once `a` is already `true`. This has a consequence worth
stating plainly, because it holds nowhere else in the language:
**whether the right side is even type-checked depends on the value of
the left side.**

```
trace false splice 1
```

```
false
```

```
trace true splice 1
```

```
matrixlang: [line 1, column 19] 'splice' takes booleans, got integer
```

Same shape, same `1` on the right — one runs, one errors, because the
left side decided whether the right side was ever looked at. This is not
a quirk of this language: Python, Java and C all behave the same way.

### The bounded search

This is the reason the operators exist. Indexing past the end of a list
is an error:

```
construct crew = ["Neo", "Trinity", "Tank"]
trace crew[3]
```

```
matrixlang: [line 2, column 11] index 3 is past the end of a list of length 3
```

So a loop that searches a list for something that might not be there has
to stop checking the length **before** it ever reads an element at that
length — and short-circuit is what lets one condition do both jobs
safely:

```
construct crew = ["Neo", "Trinity", "Tank"]
construct n = 0
dejavu n < length crew splice crew[n] != "Cypher"
  n = n + 1
flatline
trace n

redpill unplug (n == length crew)
  trace "found at"
  trace n
bluepill
  trace "not found"
flatline
```

```
3
not found
```

`"Cypher"` is not in `crew`, so the loop keeps going until `n` reaches
`3` — `length crew`. At that point `n < length crew` is `false`,
`splice` never evaluates `crew[n]`, and the loop exits without indexing
past the end. `unplug (n == length crew)` then reads as "the search did
not run off the end without finding it" — true when the target is
missing, which is exactly what happened here.

---

## 9. Scope, and agents that remember

A name declared inside an agent is local to it:

```
agent f()
  construct hidden = 1
  jackout hidden
flatline

trace f()             # 1
trace hidden          # error: 'hidden' is not declared
```

An agent can read names from outside itself, and assignment finds the
nearest one:

```
construct total = 0

agent bump()
  total = total + 1
  jackout total
flatline

trace bump()          # 1
trace bump()          # 2
```

### Closures

An agent defined **inside** another remembers where it was defined, even
after the outer call has finished:

```
agent adder(n)
  agent add(m)
    jackout n + m
  flatline
  jackout add
flatline

construct add5 = adder(5)
trace add5(37)        # 42
```

`add5` still knows that `n` was `5`, long after `adder` returned. Agents
are values: they can be stored in names, passed to other agents, and
returned.

```
agent twice(f, x)
  jackout f(f(x))
flatline

agent inc(k)
  jackout k + 1
flatline

trace twice(inc, 5)   # 7
```

Printing an agent shows its name rather than its contents:

```
trace inc             # <agent inc>
```

---

## 10. Comments

```
# this is a comment
trace 1    # so is this
```

Comments survive the conversion between faces — turn a file into glyphs
and back and your comments are still there, in place.

---

## 11. The two faces

Every program can be written and read two ways. This:

```
construct n = 3
dejavu n > 0
  trace n
  n = n - 1
flatline
```

is the same program as this:

```
ｱ n ﾅ ｩ
ﾃ n ｿ ｦ
  ﾄ n
  n ﾅ n ﾋ ｧ
ﾗ
```

Convert either way:

```bash
.venv/bin/matrixlang render --face glyph program.rain
```

```bash
.venv/bin/matrixlang render --face ascii glyphs.rain
```

Both faces run. You can mix them in one file — glyphs and ASCII names use
different alphabets, so nothing is ambiguous.

### The table

Sixteen keywords, eleven operators, parentheses, a comma, two brackets,
ten digits, and the comment marker — 43 slots in all.

| | | | | | | |
| --- | --- | --- | --- | --- | --- | --- |
| `construct` `ｱ` | `trace` `ﾄ` | `redpill` `ﾚ` | `bluepill` `ﾌ` | `dejavu` `ﾃ` | `flatline` `ﾗ` | `#` `ﾒ` |
| `agent` `ｴ` | `jackout` `ﾖ` | `length` `ﾙ` | `true` `ｼ` | `false` `ｷ` | `(` `ｸ` | `)` `ｹ` |
| `,` `ﾈ` | `[` `ﾍ` | `]` `ﾎ` | `+` `ﾀ` | `-` `ﾋ` | `*` `ｶ` | `/` `ﾜ` |
| `=` `ﾅ` | `==` `ﾆ` | `!=` `ﾇ` | `<` `ｻ` | `>` `ｿ` | `<=` `ｾ` | `>=` `ｽ` |
| `splice` `ﾁ` | `fork` `ﾂ` | `unplug` `ｳ` | `jackin` `ｲ` | `decode` `ｺ` | | |

| `0` `ｦ` | `1` `ｧ` | `2` `ｨ` | `3` `ｩ` | `4` `ｪ` | `5` `ｫ` | `6` `ｬ` | `7` `ｭ` | `8` `ｮ` | `9` `ｯ` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

Numbers are written one glyph per digit: `10` is `ｧｦ`.

**Your own names stay in Latin.** `construct name = "Neo"` becomes
`ｱ name ﾅ "Neo"`, not a wall of glyphs — so in a screen full of green,
the only readable text is the part you wrote. That is deliberate, and it
is what makes the glyph face usable rather than decorative.

---

## 12. Watching a program run

```bash
.venv/bin/matrixlang run program.rain
```

A window opens and the program falls through it: source lines in green,
the values it produced brighter and slower, looping for as long as the
window is open. Nothing on screen is random — every glyph came from your
program.

Output in the cascade is **decodable**, not decoration. `ﾁ｡ｵ･ ｿｺﾆ ﾙｸ･ｹ`
is `wake up, Neo`, and the table that decodes it is printable.

Three things worth knowing:

- **Redirect and you get plain text.** `matrixlang run p.rain > out.txt`
  writes exactly the bytes it always did, with no window and no escapes.
- **`--no-window`** does the same in the terminal while you iterate.
- **Diagnostics are never glyphs.** An error is the moment you have lost
  the thread; it appears as plain text, in the window's status strip and
  on stderr.

---

## 13. When something goes wrong

Every error carries a line and a column:

```
construct name = "Neo"
trace "wake up, " + nme
```

```
matrixlang: [line 2, column 21] 'nme' is not declared — use 'construct' first
```

Column 21 is where `nme` starts, not where the statement does.

The ones you will meet first:

| Message | What happened |
| --- | --- |
| `'x' is already declared` | A second `construct` for the same name in the same scope |
| `'x' is not declared — use 'construct' first` | Assigning or reading a name that does not exist. Often a typo |
| `condition must be a boolean, got integer` | `redpill 1` — there is no truthiness |
| `'splice' takes booleans, got integer` | An operand of `splice` or `fork` was not a boolean — same rule as `redpill` |
| `cannot add string and integer` | `"n = " + 5`. There is no automatic conversion |
| `cannot compare string with integer` | `==` across two types |
| `agent 'f' takes 2 arguments, got 1` | Wrong number of arguments |
| `agent 'f' did not jack out a value` | Used the result of an agent that returns nothing |
| `program exceeded the step limit — likely an infinite loop` | A loop that does not end — or a genuinely long program; see `--max-steps` |
| `expression is nested too deeply` | Runaway *recursion*, which hits a depth limit rather than the step limit |
| `expected 'flatline' to close 'dejavu', found end of input` | An unclosed block |

---

## 14. Seeing the shape of a program

```bash
.venv/bin/matrixlang parse program.rain
```

prints the syntax tree. It is the fastest way to understand precedence:

```
Program
  Trace
    Binary +
      NumberLiteral 2
      Binary *
        NumberLiteral 3
        NumberLiteral 4
```

`2 + 3 * 4` groups as `2 + (3 * 4)`, and the tree's shape says so.

```bash
.venv/bin/matrixlang lex program.rain
```

prints the token stream, one per line, if you want to see how the text was
split up before it was shaped.

```bash
.venv/bin/matrixlang repl
```

starts an interactive session. Blocks span several lines, so a whole
`dejavu` loop can be typed at the prompt. `:glyph` echoes what you type in
the glyph face; `:ascii` turns that off.

---

## 15. A whole program

```
# Count down, then greet — using an agent and a closure.

agent greeter(name)
  agent greet()
    jackout "wake up, " + name
  flatline
  jackout greet
flatline

construct wake = greeter("Neo")

construct n = 3
dejavu n > 0
  trace n
  n = n - 1
flatline

trace wake()
```

```
3
2
1
wake up, Neo
```

---

## 16. Having it written for you — Scribe

Everything above teaches you to write MatrixLang. **Scribe** goes the other
way: you describe what you want in English and get MatrixLang back. It
needs no API key and no network — it is a fixed catalogue of phrasings, so
the same request always produces the same program.

Open the browser UI (`python -m server`, then
<http://127.0.0.1:8420>) and type into the chat panel with the engine set
to **Scribe**. Or call it directly:

```python
from matrixlang.scribe import scribe

print(scribe("count down from 3 to 1").source)
```

```
construct i = 3
dejavu i >= 1
  trace i
  i = i - 1
flatline
```

Some of what it knows, and what each one produces:

| You type | You get |
| --- | --- |
| `add 5 and 3` | `trace 5 + 3` |
| `double 7` | `trace 7 * 2` |
| `divide 10 by 3` | `trace 10 / 3` |
| `is 4 less than 9` | `trace 4 < 9` |
| `store 42 as answer` | `construct answer = 42` |
| `make a list of 1 2 3` | `construct xs = [1, 2, 3]` |
| `get element 1 of xs` | a three-element list, then `trace xs[1]` |
| `get character 0 of name` | `construct name = "neo"`, then `trace name[0]` |
| `define a function that doubles` | `agent double(n)` … `jackout n * 2` |
| `define an adder factory` | the nested closure from §9 |

`print`, `show` and `display` all mean `trace`, so "print 42" works as well
as "trace 42".

### It says no rather than guessing

Scribe recognises a fixed set of phrasings. Anything outside it comes back
as a **miss** with the nearest pattern it does know, rather than a program
that might not be what you meant:

```python
>>> scribe("sort a list").closest
'make a list of <values>'
>>> scribe("add five and three").closest
'add <a> and <b>'
```

That second one is the rule worth remembering: **numbers must be digits.**
"add five and three" is a miss; "add 5 and 3" is a program.

Two more refusals are deliberate. A loop longer than 5,000 iterations is
declined, because every generated program is dry-run before you see it and
a longer one would blow the preview's step budget. And a reserved word
cannot be a variable name — `store 5 as trace` is a miss, because
`construct trace = 5` would not parse.

Everything Scribe hands you has already been parsed and executed once, so
it runs. What it does **not** cover yet: `splice` and `fork` (§8), writing
to a list element (§6), and calling a function you just defined. Write
those by hand — which, having read this far, you can.

---

## 17. Input — `jackin` and `decode`

`jackin` reads one line and gives you the text of it.

```
construct name = jackin
trace "Hello, " + name
```

Save it as `greet.rain` and run it, piping in what it should read:

```bash
echo "Neo" | .venv/bin/matrixlang run --no-window greet.rain
```

```
Hello, Neo
```

It is always text, never a number, even when the line looks like one. That
is deliberate: a value whose type depended on what somebody typed would send
the same program down different branches on different runs.

So `decode` turns text into a number when you want one:

```
construct n = decode jackin
trace n + 1
```

```bash
echo "41" | .venv/bin/matrixlang run --no-window add.rain
```

```
42
```

`decode` is strict. It refuses text that is not a whole number, refuses a
decimal point (this language has integers only), and refuses a value that is
already a number — the same way `splice` refuses anything that is not a
boolean rather than guessing what you meant.

Spaces and tabs either side of the number are forgiven, and so is a leading
`-`: `decode` reads ` -3 ` as `-3`. A leading `+` is not. The asymmetry is
deliberate rather than an oversight — `-3` is how the language itself writes
that number, and `+3` is a spelling it never produces, so accepting it would
mean `decode` reading a wider set of numbers than the language can write.

### `decode` binds tighter than arithmetic

`decode jackin + 1` means `(decode jackin) + 1`, not `decode (jackin + 1)`.
This is the same level `length` sits at, and for the same reason: both
produce a number that the arithmetic around them then consumes.

Note that `unplug` goes the other way — `unplug n == 1` means
`unplug (n == 1)`. The two are not inconsistent by accident. `unplug`
*consumes* a boolean that comparison *produces*, so it has to reach across
the comparison; `decode` *produces* a number that arithmetic *consumes*, so
reaching across the `+` would only ever produce an error.

### Running out of input

Asking for a line that is not there stops the program. Run this with
`echo "Neo"` piped in — one line for the first `jackin`, none for the
second:

```
construct name = jackin
trace name
construct age = jackin
```

```
Neo
matrixlang: [line 3, column 17] no input left to read
```

Not an empty string. A loop reading input would otherwise spin forever on
blanks while the real mistake stayed invisible.

### Where input comes from

At the terminal, `jackin` reads what you type, and `echo "Neo" | matrixlang
run greet.rain` works the way you would expect.

A program that uses `jackin` prints to the terminal rather than opening the
cascade window, even without `--no-window`. The window has no input box, so
a windowed run would sit there waiting for a line you had no way to see it
wanting. Only the display changes; the program itself runs the same either
way. Every other program still gets the window described in §12.

In the browser `jackin` reads the input box beside the editor, one line per
`jackin`, supplied before you press Run — a web page cannot stop and wait for
you without freezing the tab.

---

## What the language does not have

Being clear about this saves more time than any feature list:

- no floats, dictionaries, sets, or null
- no slicing (`name[0:2]`) and no string methods — indexing one character
  at a time (§7) is as far as string access goes
- no `for`, `break`, `continue`, or `else if`
- no way to *prompt* for input and wait — `jackin` (§17) reads lines that
  were already supplied, from the terminal or from the box beside the
  editor, and a program cannot stop mid-run to ask a question
- no modules, imports, or standard library
- no file or network access, and no way to reach the host language

The last one is a property rather than an omission: a `.rain` file cannot
touch your filesystem, your network, or Python. Running one you did not
write is about as safe as reading it.

---

## Where to go next

- [`README.md`](../README.md) — installing it, and what else is in the box
- [`docs/TECHNICAL-OVERVIEW.md`](TECHNICAL-OVERVIEW.md) — how the
  implementation works, and the design problems that took real effort
- `docs/superpowers/specs/` — the design record: what was decided, what
  was rejected, and, in a couple of places, what turned out to be wrong
