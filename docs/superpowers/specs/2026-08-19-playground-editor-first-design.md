# Playground Layout — the editor leads, Scribe follows

Status: **Approved as a design. Nothing is implemented.**
Inputs: `site/index.html` (the editor pane this rearranges), `site/playground.js`
(untouched, and the reason the id set is fixed), `site/tests/playground.test.mjs`
(the shared-diagnostic tests that decide §3), GitHub #112 (this feature), and
the two fixes that treated the symptom rather than the cause — #107 (Scribe
refuses pasted code) and #111 (and stops suggesting an unrelated phrasing when
it does).

The playground's editor pane stacks **Describe a program** → **MatrixLang** →
**Input** → **Run it**. Scribe's plain-English box is step one, with its own
button, before the editor. People with code in hand paste it into Scribe.

This happened twice to the language's own author. #107 and #111 fixed what
happens next; neither touched why it happens. This does.

## Decisions

| # | Question | Decision |
| --- | --- | --- |
| EF-1 | What leads | The **editor**, its input box and **Run it** — one primary cluster at the top of the pane. |
| EF-2 | What happens to Scribe | Moves **below** that cluster, **still fully visible**, introduced by a rule reading "or have it written for you". Not collapsed. |
| EF-3 | Why not collapsed | Deterministic natural-language-to-code with no account and no key is the page's most unusual feature. A newcomer who does not know the syntax is exactly who it exists for, and a `<details>` hides it from them. |
| EF-4 | Labels | Parallel and imperative: **"Write a program"** for the editor, **"Or describe one"** for Scribe. The word *or* carries the demotion in the label itself. |
| EF-5 | The diagnostic slot | `#miss` moves to **directly below Run it**. |
| EF-6 | One slot or two | **One**, unchanged. Splitting it would duplicate clearing logic that existing tests already pin. |
| EF-7 | Scribe writing upward | **Accepted, not mitigated.** No auto-scroll. See §4. |
| EF-8 | The introduction | Rewritten to lead with typing MatrixLang and mention Scribe second. |
| EF-9 | Scope guard | Markup, styling and prose only. **No `playground.js` changes** — same ids, same handlers, same `#miss` element. Operator's `<details>` and the cascade pane are untouched. |

## 1. The order (EF-1, EF-2)

```
Write a program   [ 16-row editor ]
  Show glyphs
Input             [ 3 rows ]
                  ( Run it )
  ⟨#miss⟩
──────────── or have it written for you ────────────
Or describe one   [ count from 1 to 10 ]  ( Write it )
──────────── Operator (unchanged, collapsed) ───────
```

The `playground-grid` split between `editor-pane` and `cascade-pane` is
unchanged, as is everything in the cascade pane.

## 2. Why the labels matter as much as the order (EF-4)

The current pair is lopsided in a way that is easy to miss and hard to
un-see once noticed:

- "Describe a program" — a verb. It tells you to do something.
- "MatrixLang" — a noun. It names a thing.

Only one of them is an instruction, and it is not the one attached to the
box most visitors want. Reordering alone would leave that asymmetry in
place, so both labels become imperative. Making the second read "**Or**
describe one" also means the demotion survives a future restyle of the
separator rule, because it no longer depends on visual treatment alone.

## 3. The diagnostic slot (EF-5, EF-6)

`#miss` is one shared element serving five producers: a Scribe miss, a parse
error from *Show glyphs*, a parse or runtime error from *Run it*, an Operator
failure, and a boot failure.

Today it sits **above** the editor. That is already wrong for the most common
case — a run error appears above a 16-row textarea, far from the button that
produced it. Moving it directly below **Run it** puts it at the end of the
primary cluster and immediately adjacent to the Scribe block that follows, so
it is close to both things that most often write into it.

**It stays a single slot.** `playground.js` clears it carefully across
producers, and `site/tests/playground.test.mjs` pins that behaviour — including
*"a face that renders clears the diagnostic left by one that did not"*, which
exists because a stale diagnostic once outlived the failure that caused it.
Two slots would mean two copies of that logic and two copies of those tests,
to solve a problem nobody has reported.

## 4. The cost this change introduces (EF-7)

Scribe writes its result into the editor, which is now **above** its own
button. Press **Write it** and the thing that changed is behind you.

On a desktop both are in view and it does not matter. On a narrow screen it
could be missed. The decision is to accept it:

- The editor is 16 rows and sits directly above the Scribe block, so its
  lower edge is almost certainly still on screen.
- Auto-scrolling the page underneath someone is its own annoyance, and a
  worse one — it moves content the reader did not ask to move.
- If it proves to bite in practice, the remedy is one `scrollIntoView` call,
  reversible and cheap.

Recorded because it is the single respect in which this rearrangement makes
something worse rather than better, and a future reader should find the
reasoning rather than assume it was an oversight.

## 5. The introduction (EF-8)

The paragraph above the playground currently reads:

> Describe a program and Scribe writes it, needing no account and no key.
> Edit what it wrote, or ignore it and type MatrixLang directly. Then run it,
> and watch it fall.

It describes the old order and would contradict the layout the moment this
ships. That is the same class of defect the input work hit four separate
times — prose asserting something the code had stopped doing — so it is a
required step here, not a polish item.

It gets rewritten to lead with typing MatrixLang and to introduce Scribe
second, keeping the "no account and no key" claim, which remains true and is
worth saying.

## 6. Module boundaries

| Path | Change | Why |
| --- | --- | --- |
| `site/index.html` | Reorder the editor pane, retitle two labels, move `#miss`, add the Scribe separator, rewrite the intro paragraph. | The whole feature. |
| `site/style.css` | The separator rule, and any spacing the new order needs. | |
| `site/tests/dom.mjs`, `site/tests/index-html.test.mjs` | Only if the drift checks need it — the id set does not change, so they may need nothing. | |
| `site/playground.js` | **Untouched.** | EF-9. Same ids, same handlers, same single `#miss`. If this file needs editing, the change has gone wrong. |
| `src/matrixlang/`, `server/` | **Untouched.** | Nothing here is language behaviour. |

**Load-bearing assertions:**

- `site/checks/no_semantics.py` passes unmodified — no JavaScript changes at all.
- `site/checks/key_handling.py` passes unmodified — same reason.
- `tests/test_site_examples.py` passes — the examples live in the How It Works
  tab, not the playground, and are not touched.

## 7. Testing

| Layer | Approach |
| --- | --- |
| The id contract | The existing `index-html.test.mjs` drift checks already assert every id in the stub DOM exists on the page with the right starting state. Since no id changes, these passing unmodified is itself the evidence that `playground.js` still finds everything it reaches for. |
| Everything else | A real browser. This is a layout change: reading the diff cannot tell you whether the editor now reads as the primary way in. Check at both the **Desktop** and **Mobile** switch states, confirm the diagnostic appears near Run for a run error and is still reachable for a Scribe miss, and confirm Scribe still writes into the editor above it. |

No browser-automation rig, for the reason the earlier playground specs gave:
the logic that can drift lives in `glue.py` where the suite reaches it under
CPython, and the rest is presentation checked by looking at the page.

## 8. Deliberately out of scope

- **Collapsing Scribe into a `<details>`.** EF-3 — it would hide the feature
  from the people it exists for.
- **Any `playground.js` change.** EF-9.
- **Splitting `#miss`.** EF-6.
- **Auto-scrolling after Scribe writes.** EF-7 — named, considered, declined.
- **Touching Operator or the cascade pane.** Neither is implicated.

## 9. Known risks

- **The wrong-box problem might not actually be fixed.** Ordering and labels
  are the two plausible causes, but the only real test is a person meeting the
  page cold. If it recurs, the next lever is EF-3 — collapsing Scribe — and
  that decision should be revisited rather than re-derived.
- **Scribe's result lands off-screen on a narrow viewport.** §4, accepted with
  a stated remedy.
- **The separator could be restyled into meaninglessness later.** Mitigated by
  EF-4 putting "Or" in the label text, so the demotion does not rest on the
  rule alone.
- **Nothing here is implemented.** Verify against the page, not against this
  file.
