# Interactive Input Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a program in the browser playground ask a question and wait for an answer, without changing the language or the interpreter.

**Architecture:** When `jackin` runs out of answers, `site/glue.py` returns the events collected so far plus a terminal `needs_input` marker instead of an error. `site/playground.js` shows the program's last output line with an answer box, appends what the reader types, and **re-runs the program from the start** with the longer answer list. Because MatrixLang is deterministic with `trace` as its only effect, each re-run reproduces the previous output exactly, so the cascade is fed only the newly-appeared suffix and never replayed.

**Tech Stack:** Python 3.11+ stdlib, pytest, plain HTML/CSS/JS, Node's built-in `node --test`. No new dependencies, no build step.

## Global Constraints

- **No language change.** `jackin` is untouched; a program's own `trace` is its prompt (IX-3).
- **The interpreter, `server/`, `cli.py` and `repl.py` are untouched** — they already block on real stdin (IX-9).
- **`glue.run()` must never raise.** That contract has been broken three times by unguarded integer conversions; `_NeedsInput` is caught in the same `try` as `MatrixLangError` (§5).
- **Non-interactive `run()` behaviour is unchanged** for callers that do not opt in — exhaustion is still the familiar error, so existing tests and the tutorial's §17 both stand.
- **Exhaustion is detected by a sentinel exception, never by matching a diagnostic's wording** (IX-7).
- **The cascade is cleared once per Run, not once per round**, and fed only `events.slice(drawn)` each round (IX-6, §3).
- **The existing `#program-input` box stays**, front-loading the first answers (IX-4).
- **Round cap: 100** (IX-8).
- `site/checks/no_semantics.py` and `key_handling.py` must pass **unmodified** — the JS gains a loop and a text field, no language logic.
- Run tests from the repo root. Python: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest ... -q` (the `:$PWD` is needed because `server` is deliberately not installed). JavaScript: `node --test site/tests/*.test.mjs`. Use `python3`, not `python`.

## File Structure

| Path | Responsibility |
| --- | --- |
| `site/glue.py` | `_NeedsInput`, `_InteractiveSource`, and an `interactive` mode on `run()`. The browser's Python half — the only place this can live without putting language behaviour in JavaScript. |
| `site/index.html` | The answer row markup. |
| `site/style.css` | Its styling. |
| `site/playground.js` | The round loop, suffix-only cascade feeding, the cap. |
| `tests/test_site_glue.py` | Interactive-mode tests, and the determinism property the whole design rests on. |
| `site/tests/dom.mjs`, `index-html.test.mjs`, `playground.test.mjs` | The new ids and the round loop. |

**Note on a neighbouring change:** PR #113 merged a spec for reordering this same editor pane (editor first, Scribe second) but its implementation has not been written. This plan places the answer row after `#run`, which stays correct under either ordering.

---

### Task 1: The determinism property, pinned first

**Files:**
- Modify: `tests/test_site_glue.py`

**Interfaces:**
- Consumes: the existing `glue.run(source, stdin="", max_steps=…)`.
- Produces: nothing later tasks import.

**Why this task is first.** The entire design rests on MatrixLang being deterministic with `trace` as its only effect. If that ever stops holding, re-running shows the reader a history that never happened — and the failure is silent. This test exists to fail on that day. Writing it before the feature means the feature is never built on an unverified assumption.

- [ ] **Step 1: Write the test**

Append to `tests/test_site_glue.py`:

```python
def test_running_the_same_program_twice_gives_the_same_events():
    # THE load-bearing property. Interactive input re-runs a program once per
    # prompt and shows the reader a continuous history, which is only honest
    # because a re-run reproduces the previous run exactly. If MatrixLang ever
    # gains randomness, a clock, or any effect beyond `trace`, this fails --
    # and it should, because the interactive design breaks silently otherwise.
    source = 'construct a = jackin\ntrace "got " + a\ntrace 1 + 1\n'

    def stream(stdin):
        return [(e["kind"], e.get("text") or e.get("message") or "") for e in glue.run(source, stdin=stdin)]

    assert stream("ana") == stream("ana")


def test_fewer_answers_produce_a_prefix_of_the_output():
    # The other half of the property: round n+1 must reproduce everything
    # round n showed, in order, before adding anything new. That is what lets
    # playground.js feed the cascade only the new suffix instead of replaying
    # the whole animation on every answer.
    source = 'trace "first"\nconstruct a = jackin\ntrace "then " + a\n'

    def outputs(stdin):
        return [e["text"] for e in glue.run(source, stdin=stdin) if e["kind"] == "output"]

    short = outputs("")
    long = outputs("ana")
    assert short == ["first"]
    assert long == ["first", "then ana"]
    assert long[: len(short)] == short, "a longer answer list changed earlier output"
```

- [ ] **Step 2: Run them**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_site_glue.py -q -k "same_events or prefix"`
Expected: PASS. These pin behaviour that already holds — they are a regression guard, not a red-green cycle. Say so plainly in your report rather than implying a TDD cycle you did not perform.

- [ ] **Step 3: Commit**

```bash
git add tests/test_site_glue.py
git commit -m "test: pin the determinism interactive input will rest on"
```

---

### Task 2: `glue.py` — the sentinel and interactive mode

**Files:**
- Modify: `site/glue.py`
- Modify: `tests/test_site_glue.py`

**Interfaces:**
- Consumes: `matrixlang.input.InputSource` protocol — `next_line(self) -> str | None`, where `None` means exhausted.
- Produces:
  - `glue.run(source: str, stdin: str = "", interactive: bool = False, max_steps: int = BROWSER_MAX_STEPS) -> list[dict]`
  - **`interactive` comes before `max_steps`, deliberately.** The JavaScript side calls this positionally, and JS `undefined` arrives in Python as `None` — which `interpreter.py`'s `if self._max_steps is not None` treats as *no step limit at all*, silently removing the browser's runaway-loop protection. Putting `interactive` third means `glue.run(src, stdin, true)` never has to skip over `max_steps`. Every existing caller passes `max_steps` by keyword, so the reorder breaks nothing — verified against `tests/test_site_glue.py` and `site/playground.js`.
  - When `interactive=True` and the program asks past the end of `stdin`, the returned list ends with `{"kind": "needs_input"}` after every event produced so far.
  - When `interactive=False`, behaviour is **exactly as today**.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_site_glue.py`:

```python
def test_interactive_run_asks_instead_of_failing():
    events = glue.run("trace jackin\n", stdin="", interactive=True)
    assert events[-1]["kind"] == "needs_input"


def test_interactive_run_keeps_the_output_produced_before_it_asked():
    # The prompt a reader sees IS this output -- the program's own trace.
    source = 'trace "Digite a matricula ou nome: "\nconstruct a = jackin\n'
    events = glue.run(source, stdin="", interactive=True)
    outputs = [e["text"] for e in events if e["kind"] == "output"]
    assert outputs == ["Digite a matricula ou nome: "]
    assert events[-1]["kind"] == "needs_input"


def test_interactive_run_finishes_when_the_answers_suffice():
    source = 'construct a = jackin\ntrace "got " + a\n'
    events = glue.run(source, stdin="ana", interactive=True)
    assert [e["kind"] for e in events].count("needs_input") == 0
    assert [e["text"] for e in events if e["kind"] == "output"] == ["got ana"]


def test_interactive_run_still_reports_a_real_error_as_an_error():
    # A type error is not a request for input. Confusing the two would leave
    # the page asking a question the program never asked.
    events = glue.run('trace "id " + 1\n', stdin="", interactive=True)
    assert events[-1]["kind"] == "error"
    assert "cannot add" in events[-1]["message"]


def test_non_interactive_run_is_unchanged():
    # Existing callers, and the tutorial's description, must keep working.
    events = glue.run("trace jackin\n", stdin="")
    assert events[-1]["kind"] == "error"
    assert "no input left to read" in events[-1]["message"]
```

- [ ] **Step 2: Run them to verify they fail**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_site_glue.py -q -k interactive`
Expected: FAIL — `run() got an unexpected keyword argument 'interactive'`. The last test (`test_non_interactive_run_is_unchanged`) passes already; it is a regression guard.

- [ ] **Step 3: Add the sentinel and the source**

In `site/glue.py`, after the `_Collector` class:

```python
class _NeedsInput(Exception):
    """The program asked for a line the reader has not given yet.

    Not a MatrixLangError, and deliberately not the interpreter's own "no
    input left to read" diagnostic: control flow that depended on the
    wording of an error message would change behaviour the day somebody
    reworded it. Same shape as values.CyclicValue and values.Incomparable
    -- a signal raised low and caught high -- except this one passes
    THROUGH the interpreter rather than being caught by it, which is safe
    because the interpreter has no cleanup and `recursion_guard` exits
    correctly on any exception.
    """


class _InteractiveSource:
    """Answers so far. Asking past the end suspends rather than fails.

    The browser cannot block, so a program that wants a fourth answer is
    stopped, the reader is asked, and the whole program is re-run with
    four answers. That is honest only because MatrixLang is deterministic
    with `trace` as its only effect -- see tests/test_site_glue.py's
    determinism tests, which fail if that ever stops being true.
    """

    def __init__(self, text: str) -> None:
        self._lines = text.splitlines()
        self._index = 0

    def next_line(self) -> str | None:
        if self._index >= len(self._lines):
            raise _NeedsInput
        line = self._lines[self._index]
        self._index += 1
        return line
```

- [ ] **Step 4: Add the `interactive` parameter**

Change `run`'s signature and docstring opening:

```python
def run(
    source: str,
    stdin: str = "",
    interactive: bool = False,
    max_steps: int = BROWSER_MAX_STEPS,
) -> list[dict]:
    """Execute `source`, returning every event in wire shape. Never raises.

    A failure is the last event rather than an exception, so the JS side
    has one list to walk and no error path of its own.

    `stdin` is whatever the reader typed into the input box, supplied up
    front. The browser cannot block -- JavaScript is single-threaded, so a
    read that waited would freeze the tab and the cascade drawing in it --
    so input is buffered rather than prompted for.

    `interactive=True` changes only what happens when those answers run
    out: instead of the "no input left to read" error, the events so far
    come back with a terminal {"kind": "needs_input"}, and the caller is
    expected to ask the reader and re-run with one more answer. Callers
    that do not opt in see exactly the old behaviour.
    """
```

- [ ] **Step 5: Use the source and catch the sentinel**

Replace the execution block:

```python
    source_for_run = _InteractiveSource(stdin) if interactive else BufferSource(stdin)
    try:
        Interpreter(
            sink=sink, max_steps=max_steps, source=source_for_run
        ).run(program)
    except _NeedsInput:
        # Caught in the same try that catches MatrixLangError: run() promises
        # never to raise, and that promise has been broken three times before
        # by exceptions nobody expected to reach here.
        sink.events.append({"kind": "needs_input"})
    except MatrixLangError as error:
        message = f"[line {error.line}, column {error.column}] {error.message}"
        sink.events.append({"kind": "error", "message": message + _input_hint(error, stdin)})
    return sink.events
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest tests/test_site_glue.py -q`
Expected: PASS.

- [ ] **Step 7: Run the full Python suite and both site checks**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest -q`
Expected: PASS.

Run: `python3 site/checks/no_semantics.py && python3 site/checks/key_handling.py`
Expected: both print their success line, unmodified.

- [ ] **Step 8: Commit**

```bash
git add site/glue.py tests/test_site_glue.py
git commit -m "feat: let glue.run ask for input instead of failing"
```

---

### Task 3: The answer row

**Files:**
- Modify: `site/index.html`
- Modify: `site/style.css`
- Modify: `site/tests/dom.mjs`
- Modify: `site/tests/index-html.test.mjs`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: three ids Task 4 wires — `#answer-row` (a `<div>`, starts `hidden`), `#answer-prompt` (a `<p>` holding the program's last output line as readable text), `#answer` (a text `<input>`), and `#answer-send` (a `<button>` labelled `Answer`).

- [ ] **Step 1: Add the markup**

In `site/index.html`, inside `.editor-pane`, immediately **after** the `<button id="run">Run it</button>` line:

```html
          <!-- Shown only while a running program is waiting for a line. The
               prompt is the program's own most recent output, repeated here
               in readable Latin: the cascade shows glyphs, which is a poor
               place to read a question. -->
          <div id="answer-row" hidden>
            <p id="answer-prompt"></p>
            <input id="answer" placeholder="your answer" autocomplete="off">
            <button id="answer-send">Answer</button>
          </div>
```

- [ ] **Step 2: Style it**

In `site/style.css`, after the `#program-input` rule:

```css
/* The interactive answer row. Present only while a program is waiting, so
   it must read as part of the run rather than as another form field the
   reader was supposed to fill in beforehand. */
#answer-row {
  margin-top: 0.75rem;
  padding: 0.75rem;
  background: var(--panel);
  border-left: 2px solid var(--green);
  border-radius: 0 4px 4px 0;
}

#answer-prompt {
  margin: 0 0 0.5rem;
  color: var(--white);
  font: 13px/1.5 var(--mono);
  white-space: pre-wrap;
}
```

- [ ] **Step 3: Register the ids in the stub DOM**

In `site/tests/dom.mjs`, add to `INITIAL` after the `"program-input"` entry:

```javascript
  "answer-row": { hidden: true },
  "answer-prompt": {},
  "answer": {},
  "answer-send": { text: "Answer" },
```

- [ ] **Step 4: Run the JS suite**

Run: `node --test site/tests/*.test.mjs`
Expected: PASS. `index-html.test.mjs` checks the stub's assumptions against the real page — every id present, `#answer-row` hidden, `#answer-send` labelled `Answer` — so it passing is the evidence the two agree.

- [ ] **Step 5: Run both site checks**

Run: `python3 site/checks/no_semantics.py && python3 site/checks/key_handling.py`
Expected: both pass, unmodified.

- [ ] **Step 6: Commit**

```bash
git add site/index.html site/style.css site/tests/dom.mjs
git commit -m "feat: add the answer row markup"
```

---

### Task 4: The round loop

**Files:**
- Modify: `site/playground.js`
- Modify: `site/tests/playground.test.mjs`

**Interfaces:**
- Consumes: `glue.run(source, stdin, max_steps, interactive)` returning a terminal `{"kind": "needs_input"}` (Task 2); `#answer-row`, `#answer-prompt`, `#answer`, `#answer-send` (Task 3).
- Produces: nothing later tasks import.

**The two rules that matter.** The cascade is cleared **once**, when Run is pressed — not once per round; and each round feeds it only the events it has not already drawn. Feeding everything every round would replay the whole falling-glyph animation on every answer and lose the reader's place in their own output.

- [ ] **Step 1: Write the failing tests**

Append to `site/tests/playground.test.mjs`:

```javascript
test("a program that wants input shows the answer row with its last output", () => {
  const page = loadPlayground();
  page.setGlue({
    run: () => [
      { kind: "output", text: "Digite a matricula ou nome: ", glyphs: "G" },
      { kind: "needs_input" },
    ],
  });

  page.el("editor").value = "trace jackin";
  page.el("run").click();

  assert.equal(page.el("answer-row").hidden, false);
  assert.equal(page.el("answer-prompt").textContent, "Digite a matricula ou nome: ");
});

test("answering re-runs and feeds the cascade only the new events", () => {
  // The cascade must not replay. Round two repeats round one's output --
  // that is what makes re-running honest -- so drawing it again would show
  // the reader their own history twice and restart the animation.
  const page = loadPlayground();
  const drawn = [];
  page.setCascade({
    clear: () => drawn.push("CLEAR"),
    add: (text) => drawn.push(text),
  });
  let round = 0;
  page.setGlue({
    run: () => {
      round += 1;
      return round === 1
        ? [{ kind: "output", text: "ask", glyphs: "ask" }, { kind: "needs_input" }]
        : [
            { kind: "output", text: "ask", glyphs: "ask" },
            { kind: "output", text: "done", glyphs: "done" },
          ];
    },
  });

  page.el("editor").value = "trace jackin";
  page.el("run").click();
  page.el("answer").value = "ana";
  page.el("answer-send").click();

  assert.deepEqual(drawn, ["CLEAR", "ask", "done"], "the cascade replayed or cleared twice");
  assert.equal(page.el("answer-row").hidden, true, "the row stayed open after finishing");
});

test("the answer is passed to the next run, appended to the box's contents", () => {
  const page = loadPlayground();
  const seen = [];
  page.setGlue({
    run: (source, stdin) => {
      seen.push(stdin);
      return seen.length === 1
        ? [{ kind: "needs_input" }]
        : [{ kind: "output", text: "ok", glyphs: "ok" }];
    },
  });

  page.el("editor").value = "trace jackin";
  page.el("program-input").value = "first";
  page.el("run").click();
  page.el("answer").value = "second";
  page.el("answer-send").click();

  assert.deepEqual(seen, ["first", "first\nsecond"]);
});
```

`page.setCascade` does not exist yet — add it to `site/tests/dom.mjs` alongside `setGlue`, in the same style:

```javascript
    /** Stand in for the cascade, so a test can watch what gets drawn. */
    setCascade(stub) {
      sandbox.__stubCascade = stub;
      vm.runInContext("cascade = __stubCascade", context);
    },
```

- [ ] **Step 2: Run them to verify they fail**

Run: `node --test site/tests/playground.test.mjs`
Expected: FAIL — `runProgram` does not know about `needs_input`, so the answer row never appears and the second round never happens.

- [ ] **Step 3: Add the round state and the cap**

In `site/playground.js`, near the other module-level constants:

```javascript
// A program can read input inside a loop that never ends. Each answer costs
// a full re-run, so without a cap the page would prompt forever and get
// slower every round. Bounded the way the interpreter bounds a runaway loop.
const MAX_ANSWER_ROUNDS = 100;

// The interactive session: answers collected so far, and how many events the
// cascade has already been given. Both reset when Run is pressed.
let answers = [];
let drawnCount = 0;
let rounds = 0;
```

- [ ] **Step 4: Rewrite `runProgram` into a start and a round**

Replace `runProgram` entirely:

```javascript
function runProgram() {
  // Cleared once per Run, never per round: rounds repeat earlier output by
  // design, and re-clearing would restart the animation on every answer.
  cascade.clear();
  el("miss").hidden = true;
  answers = el("program-input").value ? [el("program-input").value] : [];
  drawnCount = 0;
  rounds = 0;
  runRound();
}

function runRound() {
  // Three positional args, no placeholder: `interactive` sits before
  // `max_steps` precisely so nothing has to pass `undefined` past it. A JS
  // `undefined` becomes Python None, and None means "no step limit" -- the
  // browser would lose its runaway-loop protection without a word.
  const events = glue
    .run(el("editor").value, answers.join("\n"), true)
    .toJs({ dict_converter: Object.fromEntries });

  // Only what has not been drawn yet. The re-run reproduces every earlier
  // event exactly -- see tests/test_site_glue.py's determinism tests -- so
  // anything before drawnCount is already on screen.
  for (const event of events.slice(drawnCount)) {
    if (event.kind === "statement") {
      cascade.add(face === "glyph" ? event.source : event.latin, "source");
    } else if (event.kind === "output") {
      cascade.add(face === "glyph" ? event.glyphs : event.text, "output");
    } else if (event.kind === "error") {
      el("miss").textContent = event.message;
      el("miss").hidden = false;
    }
  }

  const wants = events.length > 0 && events[events.length - 1].kind === "needs_input";
  // A needs_input marker is not something to draw, so it is excluded from the
  // count -- the next round re-sends the events before it and stops there.
  drawnCount = wants ? events.length - 1 : events.length;

  if (!wants) {
    hideAnswerRow();
    return;
  }
  if (rounds >= MAX_ANSWER_ROUNDS) {
    hideAnswerRow();
    el("miss").textContent =
      `this program asked for more than ${MAX_ANSWER_ROUNDS} answers — stopped`;
    el("miss").hidden = false;
    return;
  }
  showAnswerRow(lastOutput(events));
}

/** The program's own most recent output, which is the question it asked. */
function lastOutput(events) {
  for (let i = events.length - 1; i >= 0; i -= 1) {
    if (events[i].kind === "output") return events[i].text;
  }
  // A program may read before it prints; a blank row would look broken.
  return "The program is waiting for a line.";
}

function showAnswerRow(prompt) {
  el("answer-prompt").textContent = prompt;
  el("answer").value = "";
  el("answer-row").hidden = false;
}

function hideAnswerRow() {
  el("answer-row").hidden = true;
}

function sendAnswer() {
  answers.push(el("answer").value);
  rounds += 1;
  hideAnswerRow();
  runRound();
}
```

- [ ] **Step 5: Wire the button and the Enter key**

In the listener section at the bottom of the file, beside the others:

```javascript
el("answer-send").addEventListener("click", sendAnswer);
el("answer").addEventListener("keydown", (e) => {
  if (e.key === "Enter") { e.preventDefault(); sendAnswer(); }
});
```

Also add `"answer"` and `"answer-send"` to `GATED_CONTROL_IDS`, so a failed boot leaves them dead like every other control.

- [ ] **Step 6: Run the JS suite**

Run: `node --test site/tests/*.test.mjs`
Expected: PASS.

- [ ] **Step 7: Run both site checks**

Run: `python3 site/checks/no_semantics.py && python3 site/checks/key_handling.py`
Expected: both pass, unmodified — the JS gained a loop and a text field, no language logic and no persistence sink.

- [ ] **Step 8: Commit**

```bash
git add site/playground.js site/tests/playground.test.mjs site/tests/dom.mjs
git commit -m "feat: ask the reader for input and re-run with the answer"
```

---

### Task 5: Verification in a real browser

**Files:** none — verification only.

- [ ] **Step 1: Run the full suites and both checks**

Run: `PYTHONPATH="$PWD/src:$PWD" python3 -m pytest -q`
Run: `node --test site/tests/*.test.mjs`
Run: `python3 site/checks/no_semantics.py && python3 site/checks/key_handling.py`
Expected: all pass.

- [ ] **Step 2: Assemble and serve the site**

```bash
python3 -m build --wheel --outdir dist/
SC=/private/tmp/claude-501/-Users-renilsonjr-Documents-GitHub-matrixlang/db7327d1-c06f-4716-989f-0e0abc100c14/scratchpad/site-ix
rm -rf "$SC"; mkdir -p "$SC"
cp site/index.html site/style.css site/layout.js site/intro.js site/tabs.js site/playground.js site/glue.py site/examples.json site/intro.json "$SC/"
cp -R site/fonts "$SC/fonts"
cp web-ui/cascade.js "$SC/"
cp server/sse.py "$SC/"
cp dist/*.whl "$SC/"
cd "$SC" && python3 -m http.server 8150
```

- [ ] **Step 3: Drive it**

Open `http://localhost:8150/?intro=0`, skip the intro, press **Load the interpreter and try it**, then paste this into the **MatrixLang** box and leave the **Input** box **empty**:

```
trace "Digite a matricula ou nome: "
construct search = jackin
trace "Voce digitou: " + search
```

Confirm, in order:

1. Pressing **Run it** shows the answer row, and `#answer-prompt` reads `Digite a matricula ou nome: `.
2. Typing `ana` and pressing **Answer** completes the program and hides the row.
3. The cascade shows `Digite a matricula ou nome: ` **once**, not twice — this is the check that the re-run did not replay.
4. Pressing Enter in the answer field works the same as the button.

Then run it again with `ana` **already in the Input box** and confirm it finishes without ever asking.

Paste what you observed. This is the check that matters — the unit tests run against a stub cascade and cannot see whether the animation actually restarted.

- [ ] **Step 4: Stop the server**

```bash
pkill -f "http.server 8150"
```

- [ ] **Step 5: Open the PR**

```bash
git push -u origin <branch>
```

Open it with `gh pr create --body-file <prepared file>`, referencing #118. Do **not** write "Closes #118" in any commit message before the feature lands, or the issue closes on the first merge.
