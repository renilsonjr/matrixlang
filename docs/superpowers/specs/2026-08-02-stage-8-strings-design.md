# Stage 8 Design — strings stop being opaque

Status: Approved (brainstorm 2026-08-02)
Inputs: GitHub #44 (the f10 umbrella), language-surface spec §9 (deferred features),
Stage 7 design §10 (which deferred this, on reasoning corrected below), technical
overview §6 (a `.rain` program has no route into Python), D-05 (vocabulary reads well
or it does not ship), §4.3 (the round-trip criterion).

The language-surface spec §9 defers *"String indexing, slicing, length, or any string
method."* Stage 7 took `length`. This takes indexing and ordering. Slicing stays
deferred.

Until now a string is an atom: you can build one, join two, compare two for equality,
and ask its length — but you cannot look inside it, and you cannot put two in order.
Sorting a list of names, the most natural program to write after Stage 7, is
impossible.

Stage 8 is **indexing and ordering**. Slicing, string methods, and mutable strings are
each out of scope.

## Decisions made in this brainstorm

| # | Question | Decision |
| --- | --- | --- |
| S8-1 | Are strings mutable, as lists are | **No.** `s[i] = v` is an error. Matches Python, Java, JS, Go and C#, and keeps the guarantee that a string handed to an agent cannot change underneath the caller. §3 records the asymmetry this creates and why it is accepted rather than hidden. |
| S8-2 | What does `s[i]` return, with no character type | **A one-character string.** The regress is real and harmless — see §2. |
| S8-3 | Does this stage also make `"a" < "b"` work | **Yes.** Sorting a list of names is the program Stage 7 makes people want to write, and it is impossible today. The change is four lines in one method. |
| S8-4 | Slicing | **Deferred.** It needs a colon token, a two-operand expression form, and a matching decision for lists — a bigger stage than this one, and its own conversation. |
| S8-5 | Any string method (`split`, `upper`, …) | **Deferred, indefinitely.** The language has zero built-in functions and that stays true. `length` is a keyword precisely so it did not become the first one. |

## 1. The surface

```
construct name = "Neo"
trace name[0]                    # N
trace length name                # 3   (already works, Stage 7)

trace "Neo" < "Trinity"          # true
trace "Trinity" < "Neo"          # false

name[0] = "X"                    # error — strings are immutable
```

Walking a string is now possible, and is the program this stage exists for:

```
construct name = "Neo"
construct n = 0
dejavu n < length name
  trace name[n]
  n = n + 1
flatline
```

## 2. This stage changes no syntax

Verified rather than assumed: `"Neo"[0]` and `s[0] = "x"` **parse today** and fail at
runtime with `cannot index string`. Indexing syntax arrived with Stage 7 and was never
restricted to lists at the grammar level.

So there is:

- no new token and no new keyword
- **no new glyph slot** — the table stays at 38
- no new AST node and no parser change
- **no change to the round-trip criterion, and none to `tests/treegen.py`**

Stage 8 is the first purely semantic stage in the project. Every previous one moved
the grammar. That is worth stating because it changes what the risk profile is: §4.3
cannot break here, and the whole of the work is in `interpreter.py`.

### What `s[i]` returns, and the regress

`s[i]` is a one-character string. `"Neo"[0]` is `"N"`, and `"N"[0]` is `"N"` — a string
is therefore a sequence of strings, each of which is a sequence of strings, without
end.

**This is a property, not a blocker.** It terminates because a reader stops asking, and
Python and JavaScript have both shipped it for decades without anyone being harmed. The
alternative — a fifth type for characters — costs a type, a literal syntax, a glyph
slot, and a conversion story in both directions, to buy a distinction no program in this
language needs.

#### A correction to the Stage 7 spec

`2026-08-01-stage-7-lists-design.md:267` deferred this feature on the grounds that it

> makes a string a list of strings each of which is a list of strings, without end.
> That is a real design position and it deserves its own stage

The regress is accurately described. Framing it as the reason to defer was
**overstated**: it reads as a blocking objection and it is not one. The feature deserved
its own stage because it is separable work, not because the regress is dangerous.
Recorded here rather than quietly dropped, because a reason given for a decision is part
of the record.

## 3. Immutability, and the asymmetry it creates

S8-1 makes `xs[0] = 9` legal and `s[0] = "X"` an error. That is a real inconsistency in a
language that otherwise treats indexing uniformly, and it must be **taught rather than
hidden**: the diagnostic explains that a string cannot be changed and points at `+`,
instead of refusing bare.

Mutable strings were considered and rejected on two counts:

- **Cost.** Python strings are immutable, so every element assignment would rebuild the
  whole string. A character-by-character loop — the exact program §1 shows — would be
  quietly O(n²).
- **Identity.** It would give strings identity, reopening the aliasing question Stage 7
  answered for lists only. `construct a = b` on a string currently cannot surprise
  anyone; it would start to.

The compensating property is worth naming: a string passed to an agent **stays put**.
That is a guarantee lists deliberately gave up, and having one type of each is more
useful than having two of the same.

## 4. Ordering

`<`, `>`, `<=`, `>=` accept two integers or two strings. Mixed operands stay an error.

The existing message is verified as: `left operand must be an integer, got string`. That
sentence **becomes false** the moment this stage ships — an integer is no longer what is
required — so rewording it is part of the change, not a polish item. The rule is now
about the pair rather than about either operand alone, and the message should say so:

```
cannot order string with integer
```

which mirrors the existing `cannot compare X with Y` from equality and `cannot add X and
Y` from `+`, so the three binary-operator failures read as one family. Naming the exact
string here rather than leaving it to the implementation is deliberate: in Stage 7 a
message and the test asserting it were specified separately and contradicted each other.

String ordering is **codepoint order**, which is what Python, Java and C do.

### The gotcha, documented rather than hidden

```
"a" < "B"   ->  false
```

Every uppercase letter sorts before every lowercase one. This surprises people, and it
belongs in the tutorial in one sentence rather than being discovered while sorting
names.

The alternative — case-insensitive comparison — is worse, and precisely because of a
rule this language already has: it would make `==` and `<` disagree about whether two
strings are the same. `"a" == "A"` is false; under case-insensitive ordering
`"a" < "A"` and `"A" < "a"` would both be false too, which reads as equality. Two
operators giving contradictory answers about sameness is the kind of trap this language
exists to avoid.

## 5. What it touches

Four changes, all in `interpreter.py`.

| Where | Change |
| --- | --- |
| `_element` (:340) | `is_list(target)` → list **or** string. `target[index]` on a Python `str` already returns a one-character string, so the read generalises for free |
| `_check_index` (:360) | The bounds message says *"past the end of a **list** of length N"*. It becomes `type_name(target)`, so a string says "string". `len()` already works on both |
| `IndexAssign` (:227) | **Must not generalise** — see §6 |
| `_comparison` (:446) | `_require_int` on both operands → both integers **or** both strings |

No new predicate in `values.py`. `is_list(v) or is_str(v)` inline is clearer than
inventing `is_indexable` for two call sites, and `values.py` continues to import
nothing.

Sharing `_check_index` between the read path and the (now rejecting) write path is what
keeps the bounds rules from drifting — the same argument that put it there in Stage 7.

## 6. The hazard, measured

Three of the four changes in §5 are "relax an `is_list` check." The fourth looks
identical and is a trap.

If `IndexAssign`'s guard is relaxed the same way `_element`'s is, `s[0] = "X"` reaches
Python's own item assignment:

```
TypeError: 'str' object does not support item assignment
```

That is an uncaught Python exception escaping into a `.rain` program — precisely what
technical overview §6 claims cannot happen, and the claim is load-bearing for the
project's security posture. **The careless version of this stage is a posture
regression, and it looks like the careful version.**

So `IndexAssign` needs a **three-way** branch rather than a two-way one:

- a list → assign
- a string → the explanatory immutability error from §3
- anything else → `cannot index {type_name}`

This is the one place in Stage 8 where the obvious edit is wrong, and it is the reason
§7 makes a teeth-check mandatory rather than optional.

## 7. Testing

1. **The trap gets a teeth-check.** Relax `IndexAssign`'s guard, confirm a `TypeError`
   escapes as a Python exception, revert. That is what proves the guard is load-bearing
   rather than decorative. A test that has never failed proves nothing.
2. **Read errors match lists word for word**, except the type noun — asserted by
   comparing the two messages in one test, because they come from the shared
   `_check_index` and a future edit could silently fork them.
3. **The codepoint gotcha is pinned, not merely documented:** `"a" < "B"` is `false`.
   Documentation drifts; a test does not.
4. **`length` and `[]` compose** — the character walk from §1, end to end.
5. **A guard that no syntax changed:** the glyph table stays at 38 and `treegen.py` is
   untouched. `tests/test_glyphs.py` already pins the count, so accidental syntax creep
   fails loudly without a new test.
6. **The mixed-operand message is asserted by exact text**, not by substring. `"a" < 1`
   must produce `cannot order string with integer` — the §4 wording. A substring check
   like `"string" in message and "integer" in message` would pass against the old,
   now-false message too; that exact failure shipped in Stage 7 and was caught only by
   the final review.
7. **`[1] < [2]` stays an error**, verified today as `left operand must be an integer,
   got list`. It will need the §4 rewording too, and must not become orderable by
   accident when the both-strings case is added.
8. The existing suite is the regression proof that nothing else moved: **1,138 tests
   pass before this stage begins**, verified on `main` at the time of writing.

## 8. Deliberately out of scope

- **Slicing** (`s[1:3]`) — see S8-4.
- **String methods** — see S8-5.
- **Mutable strings** — see §3.
- **Ordering for lists.** `[1] < [2]` stays an error. Element-wise ordering needs a
  rule for unequal lengths and for mixed element types, and §6.1 of the Stage 7 design
  shows how easily comparison rules go wrong here. It is not needed for anything.
- **`and` / `or` / `not`** — still absent, still their own stage, and now the largest
  remaining gap in the language.
- **Case-insensitive comparison or any collation** — see §4.
