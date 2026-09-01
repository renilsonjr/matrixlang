# Learning MatrixLang

Everything the language can do, in the order that makes it easiest to pick
up. You do not need to have read anything else in this repository.

MatrixLang has thirty keywords, five types, and two ways of writing
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
keywords — see §19.

Save it as `hello.rain` and run it:

```bash
.venv/bin/matrixlang run --no-window hello.rain
```

```
wake up, Neo
```

`--no-window` prints to the terminal. Without it, a window opens and the
program falls through it as glyphs — see §14.

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

## 3. Types — there are five

| Type | Examples |
| --- | --- |
| number | `0`, `42`, `-7`, `3.5`, `-0.25` |
| boolean | `true`, `false` |
| string | `"Neo"`, `""`, `"wake up"` |
| list | `[1, 2, 3]`, `[]`, `["Neo", true]` |
| dictionary | `{"id": 1}`, `{}` |

One number type, not two — there is no separate integer type to spill
into or out of. `3` and `3.0` are the same value; more on what that
means below. No sets, and **no null**. If you are used to a language
where a missing value is `null` or `None`, there is nothing here that
corresponds — a name either holds a value or does not exist. Lists and
dictionaries each get their own section (§7, §8) once agents have been
introduced: lists because the interesting thing about them — that they
are shared, not copied — is easiest to show with one; dictionaries
because they build on what lists already teach about indexing and
mutation.

### Arithmetic

```
trace 7 + 3        # 10
trace 7 - 3        # 4
trace 7 * 3        # 21
trace 7 / 2        # 3.5
```

`/` is **true division**, the same operation Python's `/` performs —
`7 / 2` is `3.5`, not `3`. A division that does not come out even keeps
going to 28 significant digits rather than stopping short or rounding to
something misleadingly tidy:

```
trace 7 / 3
```

```
2.333333333333333333333333333
```

### `%` is the remainder

```
trace 7 % 2         # 1
trace -7 % 2        # 1
trace 7 % -2        # -1
trace -7 % -2       # -1
```

`%` follows **the sign of the right operand**, the same rule Python's `%`
uses — not the sign of the left operand, which is what some other
languages give you. That is why `-7 % 2` is `1`, not `-1`: the result
takes the divisor's sign, not the dividend's. Even and odd are
`n % 2 == 0` and `n % 2 != 0`, and that holds for negative `n` too,
precisely because of this rule.

### One number type, more precisely

`3` and `3.0` compare equal:

```
trace 3 == 3.0
```

```
true
```

A whole-number *result* of arithmetic prints without a point — `6 / 2`
is `3`, not `3.0` — but a value that is written or computed with a
fractional part keeps it, trailing zero and all:

```
trace 6 / 2
trace 1.5 + 1.5
trace 2.50
```

```
3
3.0
2.50
```

That last line is not a typo: `2.50` and `2.5` are the same value
(`2.50 == 2.5` is `true`), but the language does not quietly drop the
zero you wrote. Trailing zeros are significant to *how a value prints*,
even though they make no difference to *what it equals*.

This exactness is also why `0.1 + 0.2` behaves the way you would hope,
not the way binary floating point makes it behave in most languages:

```
trace 0.1 + 0.2
```

```
0.3
```

The language stores `0.1` as the decimal digits `0.1`, not as the
nearest binary fraction, so arithmetic on it never picks up the rounding
error that gives other languages `0.30000000000000004`.

### An index must be whole

`xs[i]` requires `i` to be a whole number. `2` and `2.0` both work,
because they are the same value; `2.5` does not, because there is no
list element halfway between two positions:

```
construct xs = ["a", "b", "c"]
trace xs[2.0]
```

```
c
```

```
construct xs = ["a", "b", "c"]
trace xs[2.5]
```

```
matrixlang: [line 2, column 9] an index must be a whole number, got 2.5
```

### `+` joins strings too

```
trace "wake up, " + "Neo"     # wake up, Neo
```

But never both at once:

```
trace "n = " + 5              # error: cannot add string and number
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
matrixlang: [line 1, column 13] cannot order string with number
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
redpill 1          # error: condition must be a boolean, got number
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

There is no `for`. A counter and a condition are how loops are written
here — but `wake` and `glitch`, below, give you the two escapes a `for`
loop's `break` and `continue` would.

> **A loop that never ends** is stopped after 200,000 statements with a
> diagnostic rather than running forever. Raise or remove the limit with
> `--max-steps N`, where `0` means no limit.

### `wake` and `glitch`

A `dejavu` normally runs until its condition goes false. Two keywords let
you leave early.

```
construct n = 0
dejavu n < 10
  n = n + 1
  redpill n == 3
    glitch
  flatline
  redpill n == 6
    wake
  flatline
  trace n
flatline
```

```
1
2
4
5
```

`wake` leaves the loop entirely — you wake up, and the loop is over.
`glitch` skips the rest of this turn and goes back to the condition. The
name is the film's own: a déjà vu *is* a glitch in the Matrix, and the
loop keyword is `dejavu`.

Both are bare words on a line of their own, like a bare `jackout`. Both
belong to the **innermost** loop they sit in, so a `wake` inside a loop
inside another loop leaves only the inner one.

Two rules worth knowing:

- Outside a loop, either one is an error. That includes inside an agent
  called from a loop — the agent's body is not in a loop, so it cannot
  reach out and stop the caller's.
- `jackout` beats both. A `jackout` inside a loop inside an agent returns
  from the agent, loop and all.

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
matrixlang: [line 2, column 8] cannot index number
```

```
trace [1] + 2
```

```
matrixlang: [line 1, column 11] cannot add list and number
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

## 8. Dictionaries

A list gets you a sequence, but a student is more than one fact. Kept
as two lists — `ids` and `grades`, in step by position — nothing in
the language stops them drifting apart: an edit to one and not the
other, and `ids[2]` and `grades[2]` are quietly no longer the same
student. A dictionary keeps facts about one thing together, under
names instead of positions:

```
construct aluno = {"id": 1, "grade": "A"}
trace aluno
```

```
{"id": 1, "grade": "A"}
```

A dictionary literal is `{`, comma-separated `key: value` pairs, `}`.
**Keys are strings or numbers only**, and like a list literal (§7),
the whole thing is **one line, with no trailing comma**.

### Reading a value — `d["key"]`

```
construct aluno = {"id": 1, "grade": "A"}
trace aluno["grade"]
```

```
A
```

### A missing key is an error, not null

```
construct aluno = {"id": 1, "grade": "A"}
trace aluno["turma"]
```

```
matrixlang: [line 2, column 13] no key "turma" in this dictionary
```

There is no null anywhere in this language (§3) — there is nothing it
could hand back for a key that was never written. Check first with
`oracle`, below, the same discipline the bounded-search idiom (§10)
already teaches for a list index that might be past the end.

### Writing — insert or update — `d["key"] = v`

```
construct aluno = {"id": 1, "grade": "A"}
aluno["grade"] = "B"
aluno["turma"] = "3B"
trace aluno
```

```
{"id": 1, "grade": "B", "turma": "3B"}
```

The same syntax does both jobs. A key already in the dictionary updates
in place, without moving; a key that was not there is inserted at the
end. Keys keep the order they were first written in — a dictionary
never reorders itself.

### `length` and `keymaker`

```
construct aluno = {"id": 1, "grade": "B", "turma": "3B"}
trace length aluno
trace keymaker aluno
```

```
3
["id", "grade", "turma"]
```

`length` already worked on lists and strings (§7); on a dictionary it
counts entries. `keymaker` is new — a prefix keyword like `length`, not
a function call — and returns a dictionary's keys as a list, in that
same insertion order.

### `fold`, `trim` and `cleave`

Three things you will want to do to a string.

```
construct name = "  Mouse  "
trace trim name
trace fold "MOUSE"
trace "a,b,c" cleave ","
```

```
Mouse
mouse
["a", "b", "c"]
```

`fold` lower-cases and `trim` takes the whitespace off both ends. Both are
prefix keywords like `length`, so they bind tightly: `fold a + b` is
`(fold a) + b`.

`cleave` is infix, like `oracle`. It splits a string on a separator and
gives back a list. It binds looser than `+` and tighter than `==`, which
is what makes both of these read the way they look:

```
trace a + b cleave ","       # concatenate, THEN split
trace s cleave "," == parts  # split, THEN compare the lists
```

Reaching for `length` on the result needs parentheses, the same way
`length keymaker d` does — a prefix keyword binds tightest of all:

```
trace length (s cleave ",")
```

Three rules worth knowing:

- All three take strings. `fold 1` is an error, not a `1`.
- An empty separator is an error. `"abc" cleave ""` does not give you the
  letters; there is no operation in MatrixLang that does.
- Empty pieces are kept: `"a,,b" cleave ","` is `["a", "", "b"]`, and
  `"" cleave ","` is a list holding one empty string, not an empty list.

There is no upper-casing operator. To compare two strings ignoring case,
`fold` both sides:

```
construct typed = "MOUSE"
construct stored = "Mouse"
redpill fold typed == fold stored
  trace "match"
flatline
```

### `oracle` — is it in there?

```
construct aluno = {"id": 1, "grade": "B"}
trace aluno oracle "grade"
trace aluno oracle "turma"
```

```
true
false
```

`oracle` is infix, like `splice` and `fork` (§10) — it sits between the
dictionary and the key being asked about, and answers with a boolean.
Guard a lookup with it before indexing a key you are not sure is there:

```
construct aluno = {"id": 1, "grade": "A"}
redpill aluno oracle "turma"
  trace aluno["turma"]
bluepill
  trace "no turma yet"
flatline
```

```
no turma yet
```

`oracle` is not only for dictionaries. It asks any container the same
question — *do you hold this?*

```
trace ["neo", "trinity"] oracle "neo"
trace "matrix" oracle "rix"
trace {"a": 1} oracle "a"
```

```
true
true
true
```

A list is asked about its elements, a dictionary about its keys, and a
string about the text inside it — so `"matrix" oracle "rix"` is true even
though `"rix"` is not one of its characters.

One rule worth knowing: an element a list cannot compare is simply not a
match. `["a"] oracle 1` is `false`, not an error, even though `"a" == 1`
*is* an error. Asking whether a list contains the number 1 has a truthful
answer — it does not, it holds a string — while asking whether a string
equals a number does not.

A second rule, for the string arm specifically: the right side must be a
string. `"matrix" oracle 1` is an error, not `false` — a list quietly
skips what it cannot compare, but a string does not, since "does this
text contain the number 1?" has no substring to look for at all.

---

## 9. Python, translated

Section 8 motivated dictionaries with a scenario, not a program: two
parallel lists — `ids` and `grades` — quietly drifting apart, so keep
facts together instead. That scenario is not hypothetical — it is close
to what a beginner actually writes, in Python, already reaching for a
dictionary. `matrixlang.pytrans.translate` takes real Python source like
that and turns it into real MatrixLang source, for a stated subset of the
language.

```python
from matrixlang.pytrans import translate

result = translate("x = 2\nprint(x * 3 + 1)\n")
print(result.source)
```

```
construct x = 2
trace x * 3 + 1
```

Run that and you get `7`, same as running the Python. In the browser
playground, the same tool sits behind **Or paste Python** → **Translate
it**, next to the editor — paste, translate, then run it like any other
program.

`translate` never raises. Python that does not parse, or Python that
parses but uses something MatrixLang has no answer for, comes back as
`Refusals` instead of an exception — a list of reasons, each with a line
and column, and, where one exists, the MatrixLang idiom to write instead.
A program with five problems shows you all five in one pass, not one per
attempt.

**The subset:** `+`, `-`, `*`, `/`, `%` and comparisons, `print`,
assignment (`=` and `+=`), `if`/`elif`/`else`, `while`, `for` over a list
or `range(...)`, `def`/`return`, lists, dictionaries, `input()`,
f-strings, and list comprehensions with a single `for` and a plain
variable target (`[f(x) for x in xs if c]`). **Refused, always:** `class`,
`try`/`except`, `import`, set and dict comprehensions, generator
expressions, a list comprehension with more than one `for` clause or a
tuple target, `lambda`, slicing, `//`, and anything else MatrixLang
genuinely cannot express — not a temporary gap, but the same "no sets,
no null" boundary the rest of this guide draws around MatrixLang itself.

Division is worth a sentence, because MatrixLang has `/` and Python has
two of them. Python's `/` is true division, and so is MatrixLang's — the
two agree everywhere, `7 / 2` is `3.5` in both — so `/` translates
straight across:

```python
print(translate('a = 7\nb = 2\nprint(a / b)\n').source)
```

```
construct a = 7
construct b = 2
trace a / b
```

`//` is the one Python operator this document's title claims and cannot
deliver. Python's `//` floors (`-7 // 2` is `-4`); MatrixLang has no
floor operator to translate it to, and the glyph table that would carry
one is full — 56 slots used, 0 free (§13) — so there is no slot left to
buy. This is not a translation gap the way truthiness (below) is; it is
permanent, the same way `class` and `lambda` are permanent, and the
refusal says so:

```python
result = translate('a = 7\nb = 2\nprint(a // b)\n')
print(result.items[0].idiom)
```

```
MatrixLang has no floor operator, and no free glyph slot is left to add one. `//` floors (`-7 // 2` is `-4` in Python) while MatrixLang's `/` is true division (`-7 / 2` here is `-3.5`); work out the floor yourself once you know the sign
```

### The governing rule: syntax, not types

The translator never evaluates anything. It looks at the *shape* of a line
— an `if`, a `+`, a call — and produces the matching MatrixLang shape,
without ever asking what kind of value will be there when the line
actually runs. That is the only way it can work, since it runs once,
before the program does, and Python's own types are not visible to it.

```python
print(translate('a = 2\nb = 3\nprint(a + b)\n').source)
print(translate('a = "wake"\nb = " up"\nprint(a + b)\n').source)
```

```
construct a = 2
construct b = 3
trace a + b

construct a = "wake"
construct b = " up"
trace a + b
```

Both become `a + b`, unchanged, whether `a` and `b` turn out to be numbers
or strings — because MatrixLang's own `+` already does both jobs (§3), the
translator does not need to pick one. Run the second and you get
`wake up`. This is also why a Python program the translator refuses is a
program it is *unwilling* to guess about, not one it read wrong: type
inference would be a second copy of the interpreter's own rules, living in
a tool that runs before any value exists to check them against.

### Why truthiness is refused

Python lets any value stand in for a condition — an empty list is
false-ish, a non-empty one is true-ish. MatrixLang has no such rule (§4):
`redpill` needs an actual boolean, or it is a type error. Since the
translator does not evaluate anything (previous section), it cannot know
at translation time whether `xs` will hold a list, a number, or something
else — so it cannot silently decide which comparison Python meant, and
refuses instead of guessing:

```python
result = translate("xs = [1, 2, 3]\nif xs:\n    print('has items')\n")
print(result.items[0].reason)
print(result.items[0].idiom)
```

```
`xs` relies on truthiness, which MatrixLang does not have — a condition must already be a boolean
a list or string →  len(xs) > 0
a number        →  xs != 0
```

Apply the idiom and it translates clean:

```python
print(translate("xs = [1, 2, 3]\nif len(xs) > 0:\n    print('has items')\n").source)
```

```
construct xs = [1, 2, 3]
redpill length xs > 0
  trace "has items"
flatline
```

Run it: `has items`.

### `in` becomes `oracle`, and the one case that still fails loudly

The translator refuses where a difference would be silent (above). Where
it instead translates and lets MatrixLang answer, that answer can still
arrive as a runtime error — MatrixLang will *say* what went wrong, with a
line and a column you can act on. One case in this subset lands on that
side of the line. A second used to as well, and no longer does; both are
worth knowing.

**`in` always becomes `oracle`.** MatrixLang's `oracle` asks any
container whether it holds something (§8) — which is why the translator
can map `in` onto it without knowing which container it has:

```python
print(translate('d = {"a": 1}\nprint("a" in d)\n').source)
```

```
construct d = {"a": 1}
trace d oracle "a"
```

Run it: `true`. Python's `in` also works on lists and strings, and the
translator cannot tell which you meant — `k in d` and `2 in xs` are the
same syntax, and only the value at run time says which is which. Guessing
would be type inference, the one thing the translator will not do (above),
so it translates every `in` the same way and lets MatrixLang answer:

```python
print(translate("xs = [1, 2]\nprint(2 in xs)\n").source)
```

```
construct xs = [1, 2]
trace xs oracle 2
```

Run *that* and, today, you get `true` — the same answer Python gives.
That was not always so: before `oracle` learned to ask a list for an
element, this translation looked fine and died on `Run` with `'oracle'
takes a dictionary, got list`. Nothing about the translator changed to
fix that; `oracle` itself was widened, so every program this rule had
already produced started working. (`not in` still has no MatrixLang
form, so it is refused outright, and the refusal names
`unplug (container oracle value)`.)

**One case still disagrees with Python, and silently.** `True in [1]` is
`true` in Python, because `True == 1` there. `[1] oracle true` is `false`
here, because MatrixLang's `==` never equates a boolean with a number —
the same rule that keeps `{true: "a", 1: "b"}` as two separate keys
instead of collapsing into one (§8). The translator cannot catch this:
`True in [1]` and `"a" in xs` are the same syntax, and telling them apart
is exactly the type inference the translator refuses to do (above). This
is deliberate, not a bug — do not "fix" it by making `oracle` treat
`true` and `1` as the same element, since that would break dictionary
keys the same way.

**`for k in d:` walks a dictionary's keys, using `keymaker` (§8).** Rule 1
below turns a `for` into a counter and `length`, which is exactly right
for a list and wrong for a dictionary — the translator recognises a
dictionary syntactically and reaches for `keymaker` instead:

```python
print(translate('d = {"a": 1, "b": 2}\nfor k in d:\n    print(k)\n').source)
```

```
construct d = {"a": 1, "b": 2}
construct ks = keymaker d
construct n = 0
dejavu n < length ks
  trace ks[n]
  n = n + 1
flatline
```

Run it: `a` then `b`, same as Python — the loop walks the keys, in the
order they were first written.

This depends on the translator being able to *see* that `d` is a
dictionary, and it only looks at the syntax that builds and assigns
`d`, never at a value. A dictionary that arrives as a function parameter
or as the result of a call cannot be proven that way, so a loop over one
is still translated as if it were a list — the same shape shown above
with `d` in place of `ks`, wrong for the same reason. Write `.keys()`
explicitly when you mean it and the translator cannot see it:

```python
print(translate(
    "def totals(d):\n    for k in d.keys():\n        print(k)\n"
).source)
```

```
agent totals(d)
  construct ks = keymaker d
  construct n = 0
  dejavu n < length ks
    trace ks[n]
    n = n + 1
  flatline
flatline
```

`.keys()` is supported only as the thing a `for` walks, not as a value —
Python prints `d.keys()` as `dict_keys(['a'])`, where a MatrixLang list
prints `["a"]`, so returning it from `keymaker` and calling that
"the same" would trade one silent difference for another.

### The three rewrites, and the hoisted `construct`

A Python `for` loop has no MatrixLang equivalent — this language only has
`dejavu` (§5). Translating one means writing an equivalent `dejavu` by
hand, and three rules keep it equivalent rather than merely similar:

1. **The iterable is evaluated once.** If it is already a plain name, the
   loop indexes that name directly. Anything else — a literal, a call — is
   hoisted into a generated name *before* the loop, so the loop indexes
   that instead of re-evaluating the expression on every pass. Substituted
   inline, `for s in find_students(a, b):` would call `find_students`
   again on every iteration — a different program from the one written.
   The bound of a `range(...)` is read once the same way, because Python
   builds the range when the loop *starts*: `for i in range(n)` with a
   body that counts `n` down still runs the original number of times.
2. **The loop variable is substituted, not declared.** Every use of the
   Python loop variable becomes an index into the hoisted list — `xs[n]` —
   rather than a `construct` inside the body. That is also why a loop
   variable that is *already* a name in your program is refused: Python
   leaves the variable bound after the loop, and there is no such name
   here to leave anything in.
3. **A name first bound inside the loop — or inside one branch of an
   `if` — has its `construct` hoisted above it, initialised to `0`.**
   `construct` a second time on the same name fails with `'x' is already
   declared` (§2), and a loop body runs more than once. An `if` branch has
   the mirror-image problem: its `construct` runs only when that branch is
   taken, so the *other* branch's assignment — and every read after the
   `if` — would fail with `'x' is not declared`. Both are a declaration
   sitting somewhere that does not run exactly once, and both are fixed
   the same way: declared once, above, and merely assigned from then on.

```python
print(translate(
    "total = 0\n"
    "for n in [10, 20, 30]:\n"
    "    doubled = n * 2\n"
    "    total = total + doubled\n"
    "print(total)\n"
).source)
```

```
construct total = 0
construct xs = [10, 20, 30]
construct n1 = 0
construct doubled = 0
dejavu n1 < length xs
  doubled = xs[n1] * 2
  total = total + doubled
  n1 = n1 + 1
flatline
trace total
```

Run it: `120`.

Most of this is the shape any `for`-to-`dejavu` rewrite has: a hoisted
`xs` for the list, a counter `n1` counting up to `length xs`, `dejavu` and
`flatline` around the body. Once you know that shape, none of it
surprises you. **`construct doubled = 0`** is different — it sits above
the loop, and nothing in the Python program declared `doubled` before the
loop started; the reader's own program creates it fresh on the first
pass, inside the body. It is rule 3's insertion, and it is the one line
here that no amount of familiarity with the rewrite would have told you
to expect — the reason it exists is `construct`'s own "already declared"
rule (§2), not anything about `for` loops.

---

## 10. Logical operators — `splice`, `fork`, `unplug`

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
matrixlang: [line 1, column 7] 'splice' takes booleans, got number
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
matrixlang: [line 2, column 8] 'unplug' takes a boolean, got number
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
matrixlang: [line 1, column 19] 'splice' takes booleans, got number
```

Same shape, same `1` on the right — one runs, one errors, because the
left side decided whether the right side was ever looked at. This is not
a quirk of this language: Python, Java and C all behave the same way.

### The bounded search

If all you need is a yes-or-no answer to "is this element in the list?",
`oracle` (§8) already does that in one step — `crew oracle "Cypher"`. The
loop below is for when you need more than yes-or-no: the *position* of a
match, or a search on some condition other than equality. It is also the
reason the short-circuit operators above exist, which is worth seeing
even where `oracle` alone would do. Indexing past the end of a list
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

## 10. Bitwise operators — `mask`, `merge`, `flip`, `invert`, `uplink`, `downlink`

Bitwise operators work on integers and manipulate their individual bits:

```
trace 6 mask 3       # 2   (&)
trace 6 merge 3      # 7   (|)
trace 6 flip 3       # 5   (^)
trace invert 5       # -6  (~)
trace 3 uplink 2     # 12  (<<)
trace 13 downlink 2  # 3   (>>)
```

`uplink` shifts left and `downlink` shifts right. A shift count cannot be
negative. These operators have the conventional precedence order: merge,
flip, mask, shifts, arithmetic; `invert` is a unary operator.

---

## 11. Scope, and agents that remember

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

## 12. Comments

```
# this is a comment
trace 1    # so is this
```

Comments survive the conversion between faces — turn a file into glyphs
and back and your comments are still there, in place.

---

## 13. The two faces

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


Thirty keywords, seventeen operators (`%` among them), parentheses, a
comma, two brackets, a pair of braces, a colon, a decimal point, ten
digits, and the comment marker — 56 slots in all. The table is full:
0 slots free, and every one of those 56 is spoken for.

| | | | | | | |
| --- | --- | --- | --- | --- | --- | --- |
| `construct` `ｱ` | `trace` `ﾄ` | `redpill` `ﾚ` | `bluepill` `ﾌ` | `dejavu` `ﾃ` | `flatline` `ﾗ` | `#` `ﾒ` |
| `agent` `ｴ` | `jackout` `ﾖ` | `length` `ﾙ` | `true` `ｼ` | `false` `ｷ` | `(` `ｸ` | `)` `ｹ` |
| `,` `ﾈ` | `[` `ﾍ` | `]` `ﾎ` | `+` `ﾀ` | `-` `ﾋ` | `*` `ｶ` | `/` `ﾜ` |
| `=` `ﾅ` | `==` `ﾆ` | `!=` `ﾇ` | `<` `ｻ` | `>` `ｿ` | `<=` `ｾ` | `>=` `ｽ` |
| `splice` `ﾁ` | `fork` `ﾂ` | `unplug` `ｳ` | `jackin` `ｲ` | `decode` `ｺ` | `encode` `ﾏ` | `oracle` `ｵ` |
| `keymaker` `ﾔ` | `{` `ﾐ` | `}` `ﾑ` | `:` `ﾓ` | | | |
| `keymaker` `ﾔ` | `{` `ﾐ` | `}` `ﾑ` | `:` `ﾓ` | `fold` `ﾊ` | `trim` `ﾘ` | `cleave` `ﾛ` |
| `mask` `ｷｬ` | `merge` `ｷｭ` | `flip` `ｷｮ` | `invert` `ｷﾞｬ` | `uplink` `ｷﾞｭ` | `downlink` `ｷﾞｮ` | |
| `wake` `ﾉ` | `glitch` `ﾕ` | `.` `ｰ` | `%` `ﾝ` | | | |
| `0` `ｦ` | `1` `ｧ` | `2` `ｨ` | `3` `ｩ` | `4` `ｪ` | `5` `ｫ` | `6` `ｬ` | `7` `ｭ` | `8` `ｮ` | `9` `ｯ` |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

Numbers are written one glyph per digit: `10` is `ｧｦ`.

**Your own names stay in Latin.** `construct name = "Neo"` becomes
`ｱ name ﾅ "Neo"`, not a wall of glyphs — so in a screen full of green,
the only readable text is the part you wrote. That is deliberate, and it
is what makes the glyph face usable rather than decorative.

---

## 14. Watching a program run

```bash
.venv/bin/matrixlang run program.rain
```

A window opens and the program falls through it: source lines in green,
the values it produced brighter and slower, looping for as long as the
window is open. Nothing on screen is random — every glyph came from your
program.

Output in the cascade is **decodable**, not decoration. `ﾁ｡ｵ･ ｿｺﾆ ﾛｸ･ｹ`
is `wake up, Neo`, and the table that decodes it is printable.

Three things worth knowing:

- **Redirect and you get plain text.** `matrixlang run p.rain > out.txt`
  writes exactly the bytes it always did, with no window and no escapes.
- **`--no-window`** does the same in the terminal while you iterate.
- **Diagnostics are never glyphs.** An error is the moment you have lost
  the thread; it appears as plain text, in the window's status strip and
  on stderr.

---

## 15. When something goes wrong

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
| `condition must be a boolean, got number` | `redpill 1` — there is no truthiness |
| `'splice' takes booleans, got number` | An operand of `splice` or `fork` was not a boolean — same rule as `redpill` |
| `cannot add string and number` | `"n = " + 5`. There is no automatic conversion |
| `cannot compare string with number` | `==` across two types |
| `agent 'f' takes 2 arguments, got 1` | Wrong number of arguments |
| `agent 'f' did not jack out a value` | Used the result of an agent that returns nothing |
| `program exceeded the step limit — likely an infinite loop` | A loop that does not end — or a genuinely long program; see `--max-steps` |
| `expression is nested too deeply` | Runaway *recursion*, which hits a depth limit rather than the step limit |
| `expected 'flatline' to close 'dejavu', found end of input` | An unclosed block |

---

## 16. Seeing the shape of a program

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

## 17. A whole program

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

## 18. Having it written for you — Scribe

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
| `define an adder factory` | the nested closure from §11 |

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
it runs. What it does **not** cover yet: `splice` and `fork` (§10), writing
to a list element (§7), calling a function you just defined, and the whole
of input — `jackin`, `decode` and `encode` (§19). Write those by hand —
which, having read this far, you can.

---

## 19. Input — `jackin`, `decode`, and `encode`

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

`decode` is strict, but it accepts exactly what the language's own number
grammar accepts — which now includes a decimal point:

```
trace decode "5.5" + 1
```

```
6.5
```

It refuses text that is not a number at all — no digits, more than one
point, a point with nothing on one side of it — and refuses a value that
is already a number, the same way `splice` refuses anything that is not
a boolean rather than guessing what you meant:

```
trace decode "hi"
```

```
matrixlang: [line 1, column 7] 'decode' needs a number, got "hi"
```

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

### `encode` is `decode`'s counterpart

`encode` is `decode`'s counterpart, not its exact mirror. `decode` is
narrow — it turns text into a number, and refuses text that is not one,
because there is no sensible number for `"hi"`. `encode` is not narrow the
same way: it gives the text form of *any* value — the same text `trace`
would print.

```
construct id = 7
trace "ID: " + encode id
```

```bash
.venv/bin/matrixlang run --no-window id.rain
```

```
ID: 7
```

Give it something other than a number and it still works, because it
routes through the same display rules `trace` uses. A string prints bare
at the top level; a string nested inside a list or dictionary prints
quoted, the same rule `trace` follows:

```
trace encode "5"
trace encode true
trace encode ["a", "b"]
```

```
5
true
["a", "b"]
```

`encode` refuses two things outright, both about the value's shape
rather than its type: a value that contains itself (a list or dictionary
that holds itself, directly or indirectly, has no finite text form), and
a number past the same digit ceiling described below. A value nested
too many levels deep also comes back refused, the same host recursion
limit `trace` runs into rather than a rule `encode` itself enforces.
Everything else comes back as text.

`encode` sits at the same precedence as `decode` — tighter than arithmetic,
for the same reason: both produce a value that the arithmetic around them
then consumes. `encode n + 1` means `(encode n) + 1`, not `encode (n + 1)`,
and since `encode` produces text, adding the `1` to it fails with the same
error `+` gives any other mismatched pair:

```
construct n = 7
trace encode n + 1
```

```
matrixlang: [line 2, column 16] cannot add string and number
```

`decode encode n == n` holds for every number the language can write out —
encoding and then decoding gets you back where you started:

```
construct n = 7
trace decode encode n == n
```

```
true
```

"The language can write out" is the whole of the exception, and it takes
some doing to find: past 4,300 digits a number has no text form, and
`encode` says so rather than producing one. `trace` refuses the same
number for the same reason — both write a number out the same way, so
there is one ceiling and not two.

The reverse does not hold. `decode` tolerates whitespace either side and a
leading `-`; `encode` never produces either, so a value that made the trip
through `decode` first can come out shorter than it went in:

```
construct raw = " 3 "
construct n = decode raw
trace encode n
```

```
3
```

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
way. Every other program still gets the window described in §14.

In the browser you can answer either way. Fill the input box beside the editor
before you press Run and `jackin` reads it one line at a time, or leave it
empty and the page will ask you: when a program wants a line it does not have,
an answer box appears under the editor showing whatever the program printed
last — its question — and typing a line and pressing Answer carries on.

A web page still cannot stop and wait for you without freezing the tab, so the
page does not wait. It runs your program again from the beginning with your
answer added, and shows you only the part that is new. You see one continuous
run because that is what it is: MatrixLang programs do nothing but compute and
`trace`, so running one twice with the same input gives exactly the same
output, every time. The playground is built on that.

---

## What the language does not have

Being clear about this saves more time than any feature list:

- no sets, or null
- no `//` — MatrixLang's `/` is true division, and there is no floor
  operator to spell alongside it; the glyph table is full (§13)
- no slicing (`name[0:2]`) and no string methods — indexing one character
  at a time (§7) is as far as string access goes
- no removing a key from a dictionary (§8) — only reading, inserting, and
  updating one
- no `for` or `else if` — but a `dejavu` loop can leave early with `wake`
  and skip to its next turn with `glitch` (§5)
- no way to *prompt* for input and wait — `jackin` (§19) reads lines that
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
