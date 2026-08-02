# Learning MatrixLang

Everything the language can do, in the order that makes it easiest to pick
up. You do not need to have read anything else in this repository.

MatrixLang has eleven keywords, four types, and two ways of writing every
program: **ASCII**, which you type, and **glyphs**, which you read. They
are the same program — the toolchain converts between them without loss.

```bash
.venv/bin/matrixlang run examples/hello.rain
```

---

## 1. Your first program

```
trace "wake up, Neo"
```

`trace` prints. That is the only way a program produces output; there is
no `print`, no `return` to a console, and no input.

Save it as `hello.rain` and run it:

```bash
.venv/bin/matrixlang run --no-window hello.rain
```

```
wake up, Neo
```

`--no-window` prints to the terminal. Without it, a window opens and the
program falls through it as glyphs — see §11.

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

`<`, `>`, `<=`, `>=` compare integers. `==` and `!=` compare two values of
the *same* type; comparing across types is an error rather than `false`,
because that comparison is almost always a mistake.

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

### Four new errors

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

---

## 8. Scope, and agents that remember

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

## 9. Comments

```
# this is a comment
trace 1    # so is this
```

Comments survive the conversion between faces — turn a file into glyphs
and back and your comments are still there, in place.

---

## 10. The two faces

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

Eleven keywords, eleven operators, parentheses, a comma, two brackets,
ten digits, and the comment marker — 38 slots in all.

| | | | | | | |
| --- | --- | --- | --- | --- | --- | --- |
| `construct` `ｱ` | `trace` `ﾄ` | `redpill` `ﾚ` | `bluepill` `ﾌ` | `dejavu` `ﾃ` | `flatline` `ﾗ` | `#` `ﾒ` |
| `agent` `ｴ` | `jackout` `ﾖ` | `length` `ﾙ` | `true` `ｼ` | `false` `ｷ` | `(` `ｸ` | `)` `ｹ` |
| `,` `ﾈ` | `[` `ﾍ` | `]` `ﾎ` | `+` `ﾀ` | `-` `ﾋ` | `*` `ｶ` | `/` `ﾜ` |
| `=` `ﾅ` | `==` `ﾆ` | `!=` `ﾇ` | `<` `ｻ` | `>` `ｿ` | `<=` `ｾ` | `>=` `ｽ` |

| `0` `ｦ` | `1` `ｧ` | `2` `ｨ` | `3` `ｩ` | `4` `ｪ` | `5` `ｫ` | `6` `ｬ` | `7` `ｭ` | `8` `ｮ` | `9` `ｯ` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

Numbers are written one glyph per digit: `10` is `ｧｦ`.

**Your own names stay in Latin.** `construct name = "Neo"` becomes
`ｱ name ﾅ "Neo"`, not a wall of glyphs — so in a screen full of green,
the only readable text is the part you wrote. That is deliberate, and it
is what makes the glyph face usable rather than decorative.

---

## 11. Watching a program run

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

## 12. When something goes wrong

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
| `cannot add string and integer` | `"n = " + 5`. There is no automatic conversion |
| `cannot compare string with integer` | `==` across two types |
| `agent 'f' takes 2 arguments, got 1` | Wrong number of arguments |
| `agent 'f' did not jack out a value` | Used the result of an agent that returns nothing |
| `program exceeded the step limit — likely an infinite loop` | A loop that does not end — or a genuinely long program; see `--max-steps` |
| `expression is nested too deeply` | Runaway *recursion*, which hits a depth limit rather than the step limit |
| `expected 'flatline' to close 'dejavu', found end of input` | An unclosed block |

---

## 13. Seeing the shape of a program

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

## 14. A whole program

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

## What the language does not have

Being clear about this saves more time than any feature list:

- no floats, dictionaries, sets, or null
- no indexing into a string — `"Neo"[0]` is an error; only lists index
- no `for`, `break`, `continue`, or `else if`
- no `and`, `or`, or `not`
- no input — a program's only channel out is `trace`
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
