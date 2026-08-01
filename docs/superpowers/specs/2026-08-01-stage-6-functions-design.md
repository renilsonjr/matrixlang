# Stage 6 Design — functions, with closures

Status: Approved (brainstorm 2026-08-01)
Inputs: GitHub #21 (the f05 umbrella), parent spec §5 (flat environment) and §6
(deferred features), D-02 (keyword-delimited blocks), D-03 (glyph face is a view),
D-05 (vocabulary reads well or it does not ship), §4.3 (the round-trip criterion).

Stages 1–5 built a language you can teach with. This is the first stage aimed at a
language you can build something in, and #21 is right that it reverses a deliberate
decision rather than completing an unfinished one. Parent spec §5 pins the flat
environment to the absence of functions — *"with no functions there is nothing for
lexical scoping to do yet."* Adding functions is what gives scoping something to do.

Stage 6 is **functions only**. Collections, a standard library, modules and I/O are
each their own stage, per #21's sequence.

## Decisions made in this brainstorm

| # | Question | Decision |
| --- | --- | --- |
| S6-1 | Does this land in the JavaScript implementation too | **There is no longer a second implementation.** `web/` is removed (#28). It had become a full duplicate of the language — its own lexer, parser, interpreter and a hardcoded copy of the glyph table — and every language change would have had to land twice, against a side with no tests. |
| S6-2 | Closures, or plain top-level functions | **Closures, from the start.** Retrofitting capture means changing the environment model twice. |
| S6-3 | Function and return keywords | **`agent` and `jackout`.** An Agent is a callable, reusable program in the films; `jackout` is leaving the construct and coming back with something. Both pass D-05's test — they read as vocabulary, not as a joke. |
| S6-4 | Argument syntax | **Parens with a comma.** Parens already have glyphs; the comma costs one new slot. Juxtaposition (`add 1 2`) costs nothing but cannot be parsed without knowing arity. |
| S6-5 | What an `agent` that never jacks out produces | **An internal `NOTHING` sentinel**, not a language value. See §4. |
| S6-6 | The A/B/C architecture fork from #21 | **Still undecided, deliberately.** Functions are identical under all three, so the decision waits for real experience. |

## 1. Vocabulary and the glyph budget

Three new slots, drawn from the 24 free:

| Slot | Glyph |
| --- | --- |
| `agent` | `ｴ` |
| `jackout` | `ﾖ` |
| `,` | `ﾈ` |

Arbitrary, like most of the table. `glyphs.py`'s docstring already says assignments
are "loosely mnemonic where a sound offered itself and arbitrary elsewhere"; the
tests pin bijectivity and coverage, never the choices.

**21 slots remain.** Collections would want roughly five (`[ ] { } :`). The budget is
finite and worth tracking rather than discovering.

Blocks stay keyword-delimited per D-02: an `agent` definition is closed by `flatline`,
like every other block, so every boundary is a glyph rather than Latin punctuation.

```
agent fib(n)
  redpill n < 2
    jackout n
  flatline
  jackout fib(n - 1) + fib(n - 2)
flatline

trace fib(10)
```

## 2. The environment becomes a chain

`interpreter.py` currently holds `environment: dict[str, object]` as one global
namespace. It becomes an `Environment` with a `parent` link and its own `values` dict.

| Operation | Rule |
| --- | --- |
| `construct x = …` | Defines in the **current** environment. Re-declaring in the same environment is still an error; shadowing an outer one is not. |
| `x = …` | Walks the chain to the nearest existing binding and assigns there. Assigning to an undeclared name is still an error. |
| `x` (read) | Walks the chain. Not found is still an error. |
| parameters | Bound by the call into the call's environment, without `construct`. |

The root environment is the globals. Nothing about the existing rules changes — they
are simply now scoped, which is the whole point of the stage.

**A closure captures the environment it was defined in, not the one it is called
from.** This is the entire difference between S6-2's two options and the reason it
had to be decided first.

## 3. Function values and calls

Four new AST nodes:

| Node | Purpose |
| --- | --- |
| `FunctionDef(name, params, body)` | Statement. Binds a `Function` value into the current environment. |
| `Call(callee, args)` | Expression. |
| `Return(value)` | Statement. |
| `ExprStmt(expr)` | Statement. Needed so `log(1)` can stand alone — without it, a call whose value is discarded has nowhere to live. |

A runtime `Function` value carries its parameters, its body, and its captured
environment. Functions are first-class: they can be passed, returned, and stored,
which S6-2 requires.

Two new runtime errors, both `RuntimeErrorML` carrying line and column like every
other error in the language:

- arity mismatch — `agent 'add' takes 2 arguments, got 3`
- calling a non-function — `'x' is not an agent`

## 4. `NOTHING`, and why it is not a language value

The language has three types and parent spec §4 defers a fourth deliberately. So an
`agent` that never reaches a `jackout` has nothing to produce, and there is no null
to produce it with.

The resolution: an internal sentinel that is **not** reachable as a value.

- A call used as a **statement** may produce `NOTHING`. This is what makes procedures
  legal — an agent that only traces is a reasonable thing to write.
- A call used as an **expression** that produces `NOTHING` is a runtime error:
  `agent 'log' did not jack out a value`.

This keeps the type count at three, keeps `to_display` total over real values, and
means no program can ever hold or compare a null. The cost is that the error surfaces
at the use site rather than the definition — acceptable, and it carries a position.

`jackout` outside any agent is a runtime error rather than a parse error, because the
parser does not track function context and giving it that tracking costs more than the
error is worth.

## 5. Return as control flow

`Return` unwinds to the call site via an internal exception, the standard tree-walker
technique. It is caught in `Call` evaluation and nowhere else.

The exception type is private to `interpreter.py` and must not inherit from
`MatrixLangError`: a `jackout` is not a diagnostic, and a stray `except MatrixLangError`
must never swallow a return.

## 6. Recursion becomes load-bearing

`Interpreter.run` already maps `RecursionError` to `RuntimeErrorML`, and
`errors.recursion_guard()` already covers the lex/parse/render boundaries. Both were
built for hostile input. They now carry ordinary user programs, which is a change of
role rather than of code.

The one addition: the error must carry the **call site's** line and column, not the
interpreter's own position, or a deep recursion reports a location the author never
wrote.

No explicit depth limit is introduced. Python's own limit is the policy, converted at
the boundary — inventing a second limit would mean two numbers to keep in agreement.

## 7. The two faces must survive

Every new node renders in both faces and round-trips, per §4.3. `render.py`,
`treeview.py` and `tests/treegen.py` all grow.

The parenthesisation trap is specific and worth naming: `f(a + b)` and `f(a) + b` are
different trees. A call's argument list is its own precedence context, so an emitter
that reuses the enclosing context renders them identically and silently changes
meaning. Directed test per case, as in §5.1 of the technical overview.

The property test's generator must produce the new shapes, and the existing meta-test
— which asserts the generator actually emits the hard cases — extends to cover them,
or the property quietly degrades into testing nothing.

## 8. The cascade, and a real problem functions create

#21 assumed this was free, on the grounds that the rain ran at the CLI boundary and
never touched the AST. That was true of the Stage 5 curtain and is no longer true of
anything: the window consumes an execution event stream, and `cascade._header()`
renders every executed statement.

**`fib(10)` emits hundreds of `Statement` events.** `CascadeField._history` records
every line added so the loop can replay it, and it currently grows without bound. A
recursive program would balloon memory and turn the cascade into an unreadable wall
of repeats.

Stage 6 therefore caps the history at **200 lines**, keeping the most recent and
discarding the rest. 200 is chosen because the field is 80 columns wide and a line
takes several seconds to fall: more than a couple of screens' worth can never be
read before it is replaced, so a larger cap would buy memory pressure and nothing
else. The number lives as a named constant, not a literal.

Small, but it belongs in this stage rather than being discovered by the first person
who writes a recursive program.

## 9. Testing

Test-driven throughout, following the practices already established:

| Layer | Approach |
| --- | --- |
| Environment | Directed tests for define/assign/read across the chain, including shadowing and the "assign finds the nearest binding" rule |
| Closures | A returned inner agent still sees its defining scope after the outer call has finished |
| Calls | Arity, non-callable, `NOTHING` used as a value — each a `RuntimeErrorML` with position |
| Return | Unwinds through nested blocks; does not escape a call; not caught by `except MatrixLangError` |
| Round trip | Property test extended to the new nodes, plus the `f(a + b)` parenthesisation cases |
| Recursion | Deep recursion reports the call site's position |
| Cascade | History cap holds under a recursive program |
| Architecture | Stage 6 adds no modules, so the allow-table should be **unchanged**. If it needs an edit, a dependency crept in that this design did not intend, and that is the finding. |

Every load-bearing guard gets a teeth-check: inject the bug, watch the test fail,
revert.

## 10. Deliberately out of scope

- **Collections** — Stage 7 per #21, and much easier once functions exist.
- **Standard library, modules, file and network I/O** — each its own stage.
- **The A/B/C fork** — S6-6.
- **Default arguments, varargs, keyword arguments.** Fixed arity only. Each is a
  separate design with its own glyph cost, and none is needed to make the language
  usable.
- **Tail calls.** Recursion is bounded by Python's limit; changing that is a
  performance project, not a language one.
