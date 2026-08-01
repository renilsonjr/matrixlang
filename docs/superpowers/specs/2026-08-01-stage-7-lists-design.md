# Stage 7 Design — collections, as one list type

Status: Approved (brainstorm 2026-08-01)
Inputs: GitHub #40 (the f09 umbrella), language-surface spec §9 (deferred features),
technical overview §5.5 (`bool` is a subclass of `int`) and §6 (no route into Python),
D-03 (the glyph face is a view), D-05 (vocabulary reads well or it does not ship),
§4.3 (the round-trip criterion).

The language-surface spec §9 defers **"Collections of any kind"** alongside functions
and LLM authoring support. Both of those have since shipped — Stage 6 and Operator —
and this lifts the third. Like Stage 6, it reverses a deliberate decision rather than
completing an unfinished one.

Until now a program cannot hold more than one value. Every `.rain` file is capped at
scalars, and so is everything the teaching series can demonstrate with it.

Stage 7 is **one list type**. Dictionaries, sets, tuples, `for`, and string indexing
are each their own stage.

## Decisions made in this brainstorm

| # | Question | Decision |
| --- | --- | --- |
| S7-1 | Are lists mutable | **Mutable, with element assignment.** `xs[0] = 9` changes the list in place; passing a list to an agent shares it. §3 records the cost, which is real and is paid in §6. |
| S7-2 | How does a program ask a list its length | **A `length` keyword with its own glyph**, not a built-in function. The language still has *zero* standard library, and the entire language surface stays glyphs — see §1. |
| S7-3 | How does a list grow | **`+` concatenation only.** No `push`. `+` is already overloaded for integer and string; lists are the third case of one idea rather than a fourth mechanism. |
| S7-4 | What is `[1, 2] == [1, 2]` | **True — structural equality**, recursively. `==` then means one thing across integers, booleans, strings and lists. Agents remain the identity-compared exception, because nothing can meaningfully compare two agents. |
| S7-5 | Does `length` work on strings | **Yes.** `length "Neo"` is 3. String *indexing* stays deferred: `"Neo"[0]` needs a character type, and the language has three types and no char. |

## 1. Vocabulary and the glyph budget

Three new slots, drawn from the 21 free. The table goes 35 → 38, leaving 18.

| Slot | Glyph | Note |
| --- | --- | --- |
| `[` | `ﾍ` | An adjacent pair, mirroring `(`→`ｸ` `)`→`ｹ` |
| `]` | `ﾎ` | |
| `length` | `ﾙ` | |

Arbitrary rather than mnemonic. `glyphs.py` already sanctions this: *"Assignments are
loosely mnemonic where a sound offered itself and arbitrary elsewhere; the tests pin
bijectivity and coverage, not the choices."* `length` has no katakana mora that fits —
レ is the closest and belongs to `redpill`.

**Why `length` is a keyword and not `length(xs)`.** A built-in function would reuse the
call syntax that already exists and cost no new grammar. It would also be the first
piece of the language surface rendered in **Latin** in the glyph face, because built-in
names are identifiers. D-03's whole claim is that in a wall of green the only readable
text is the thing you wrote; a Latin `length` sitting among the glyphs breaks that for
a construct the programmer did not write. It would also raise a question with no good
answer — may a program define its own agent named `length`? As a keyword, it cannot,
and that is a rule rather than a special case.

The second-order benefit: the language still has **no built-in functions at all**, so
"MatrixLang has no standard library" stays true rather than becoming "almost none."

## 2. The surface

```
construct crew = ["Neo", "Trinity", "Morpheus"]

trace crew[0]              # Neo
crew[1] = "Tank"
trace length crew          # 3

construct all = crew + ["Cypher"]
trace length all           # 4

construct n = 0
dejavu n < length crew
  trace crew[n]
  n = n + 1
flatline
```

Everything above is existing machinery reused:

| Piece | Reuses |
| --- | --- |
| `xs[i]` and `xs[i] = v` | `parser._call()` is already a postfix loop, so `f()()` works. Indexing joins that loop rather than changing precedence |
| `xs + ys` | `+` is already overloaded for integer addition and string concatenation |
| `length xs` | Binds at unary level exactly like `-x`, so `length xs + 1` is `(length xs) + 1`, matching `-x + 1` |
| The `length` AST node | **None needed.** It is `Unary(op=TokenType.LENGTH, operand=...)`, the node `-x` already uses |

### Iteration, and the loop this does not add

There is no `for`. A counter and `dejavu` is how you walk a list, which is the same
answer the language already gives for every other loop. `length` is what makes that
possible at all — without it the bound cannot be written, which is why S7-2 is the
decision the rest of the stage rests on.

### Growth, and its honest cost

`xs = xs + [item]` in a loop is O(n²): each concatenation copies. At teaching scale
this is invisible, and the documentation will say so rather than leaving a reader to
discover it. A `push` keyword would make it O(1) and would also give every "add to a
list" task two correct answers — the kind of choice this language has consistently
refused. There is no `for`, no `else if`, no truthiness, and now no second way to
append.

## 3. Mutability, and what it costs

S7-1 chose reference semantics, which is what almost every language does and what
nobody will be surprised by. It has one consequence the language has never had before:
**a value with identity**.

Until Stage 7 every MatrixLang value was compared by content and copied by assignment.
`Function` was the sole exception, and it was safe precisely because nothing in the
language can inspect an agent. A list can be inspected, mutated, and aliased.

Two things follow, and §6 is where they are paid:

- Structural equality (S7-4) coexists with reference identity. `[1,2] == [1,2]` is
  true while the two lists are distinct objects. This is Python's model and is not
  novel, but it is new *here*.
- **Cycles become reachable.** `xs[0] = xs` is legal and builds a list containing
  itself. Measured: `+` alone cannot do this — `ys = ys + [ys]` leaves `ys[0] is ys`
  false, because concatenation copies. Element assignment is the only door to a cycle,
  which means this entire hazard class is the price of S7-1. The immutable design had
  no cycles by construction.

Recorded because it is a real cost of a decision taken with open eyes, not a defect
discovered later.

## 4. What a list is at runtime

A plain Python `list`, matching how integers, booleans and strings are plain Python
values. `values.py` gains `is_list` using `type(value) is list` — **never
`isinstance`**, for the same reason every other predicate in that module does, and with
sharper stakes here because §6 shows the `bool`/`int` trap re-entering through lists.

| Function | Addition |
| --- | --- |
| `is_list` | `type(value) is list` |
| `type_name` | `"list"` |
| `to_display` | `[1, 2]`, and see below |

**`trace` quotes strings inside a list.** `trace ["hi", 1]` prints `["hi", 1]`, while
bare `trace "hi"` still prints `hi` unquoted. The inconsistency is deliberate: without
quotes, `[hi, 1]` gives a reader no way to tell a string from a name, and a list of
strings becomes unreadable. The top-level case keeps its existing behaviour because
changing it would alter output every existing program produces.

`values.py` must still import nothing. Lists hold arbitrary values including other
lists and agents, and none of that requires a new dependency.

## 5. Errors

| Case | Result |
| --- | --- |
| `xs[5]` on a 3-element list | Runtime error. **Forced, not chosen** — there is no null to return |
| `xs[-1]` | Runtime error. `xs[length xs - 1]` is explicit and works. Consistent with a language that refuses to guess |
| `xs["a"]` | Runtime error: an index must be an integer |
| `[1] + 2` | Runtime error, the existing "cannot add" family |
| `length 5` | Runtime error: `length` takes a list or a string |
| `[1, "a", true]` | **Legal.** Refusing mixed types needs a type system this language does not have |
| `[[1, 2], [3]]` | **Legal**, and free — lists hold any value |

Every message carries a line and column, like every other diagnostic.

## 6. The two hazards, measured

Both were asserted from reading the code and then **tested before this spec was
written**. One of the two initial assessments was wrong, and the correction is recorded
because it changed what the implementation must do.

### 6.1 The `bool`-is-an-`int` trap returns, one level down

`interpreter.py:368` guards operand types with `type_name` and then delegates to
Python's `==`. That guard is top-level only. Measured against the real code path:

```
1 == true          (top level, existing guard)  -> error: cannot compare   ✓
[1] == [true]      (one level down)             -> True                    ✗
[0] == [false]                                  -> True                    ✗
[[1]] == [[true]]  (two levels down)            -> True                    ✗
[1,2] == [1,2]     (the case we want)           -> True                    ✓
```

Technical overview §5.5 is entirely about this trap, and lists reintroduce it through a
back door: the rule holds exactly at the surface and breaks at every level beneath it.

**Requirement: equality recurses using `type_name` and never delegates to Python's
`==` for a list.** A dedicated `equal(a, b)` in `values.py`, so the rule stays
auditable in one place — the same argument that put `type(v) is int` there originally.

### 6.2 Cycles: the diagnostic lies, and equality recurses

`construct xs = [1]` then `xs[0] = xs`.

**Initial assessment, which was wrong:** that this lets a Python `RecursionError`
traceback escape a `.rain` program, holing the §6 claim that a program has no route
into Python. It does not. `Interpreter.run` already wraps `_execute` in
`except RecursionError` (`interpreter.py:161`) and converts it.

**The actual defect** is that `trace xs` then reports:

> `expression is nested too deeply`

which is false. Nothing is nested; it is a one-element list. The requirement is an
**honest diagnostic**, not a crash fix — considerably cheaper than what was first
proposed.

Equality is a separate case and needed its own measurement. Python's per-element
identity shortcut rescues the easy shapes but not all of them:

```
a == a              -> True            identity shortcut, no recursion
a == [1]            -> False           element 0 is list vs int
b == c  (mutual)    -> RecursionError  b[0] is c, c[0] is b
d == e  (both self) -> RecursionError  distinct self-referential lists
```

**Requirement: `equal` carries a seen-set.** Display needs the truthful message,
equality needs cycle detection. Two different fixes — the initial design assumed one,
and that assumption was wrong.

## 7. The two faces must survive

§4.3 is unchanged and non-negotiable:

```
parse(render_glyph(t)) == parse(render_ascii(t)) == t
```

Three render levels, all existing:

| Node | Level |
| --- | --- |
| `ListLiteral` | `_ATOM_LEVEL` — a bracketed literal never needs parens |
| `Index` | `_CALL_LEVEL` — same as a call, and for the same reason |
| `Unary(LENGTH)` | `_UNARY_LEVEL` — identical treatment to `-x` |

**`tests/treegen.py` must generate `ListLiteral` and `Index` nodes.** Without that the
property test keeps passing while silently covering none of the new syntax — the exact
failure §5.2 of the technical overview describes, where a generator that stops
producing hard shapes degrades the property into testing nothing. Its meta-test needs a
list case for the same reason.

## 8. The cascade

Nothing to implement. The cascade renders whatever `render_glyph` produces, and a list
literal is just a longer line.

One thing to look at rather than test: **a line falls vertically, so its length is its
height on screen.** `construct crew = ["Neo", "Trinity", "Morpheus"]` is a much taller
stream than anything Stages 1–6 produce. This is the same constraint that decided
against spelling keywords out in `cascade._header`. It may be fine; it will be looked
at before the stage ships, because the cascade's visual quality has never been caught
by a test and has been wrong twice.

## 9. Testing

1. **The nesting cases go in first**, before any implementation, and are teeth-checked
   against the naive `left == right`. The spike that produced §6.1's table becomes a
   real test rather than a scratchpad file.
2. **`treegen.py` extended**, per §7, along with its meta-test.
3. **`matrixlang parse` run against a real list program.** `treeview.py` had no case
   for the Stage 6 nodes and crashed on the CLI while 878 tests passed. A test per new
   node type, plus running the actual command.
4. **A list program watched in the cascade**, per §8.
5. The existing suite is the regression proof that nothing else moved: 1,023 tests
   pass before this stage begins.

## 10. Deliberately out of scope

- **String indexing and slicing.** `"Neo"[0]` must return a one-character string, which
  makes a string a list of strings each of which is a list of strings, without end.
  That is a real design position and it deserves its own stage rather than riding
  along here.
- **`push`, or any second way to grow a list.** See §2.
- **Dictionaries, sets, tuples.** A dictionary needs a key-equality story that §6.1
  makes non-trivial.
- **`for`, `break`, `continue`.** A counter and `dejavu` is the answer, as it is for
  every existing loop.
- **A `map`/`filter`/`reduce` layer.** Agents are values already, so this is reachable
  in the language rather than needing to be built into it — which is a better
  demonstration of Stage 6 than a built-in would be.
