// What playground.js is supposed to DO.
//
// site/checks/ already pins what it must not do — own a glyph table, persist
// a key, talk to a second host. Those are prohibitions, and a static scan can
// enforce them. Nothing enforced the other half, and all three faults found
// auditing #82 lived there: not in any single line, but in the relationship
// between lines across time. Every test below failed against the revision
// that shipped those faults.
//
// The glyph strings are placeholders. This file knows no more about the
// language than playground.js is allowed to — what is under test is which
// face is showing and whether it still belongs to the source above it.

import assert from "node:assert/strict";
import test from "node:test";

import { loadPlayground } from "./dom.mjs";

/** A glue whose glyph() succeeds, tagging its output with what it was given. */
const rendering = {
  glyph: (source) => ({ ok: true, glyph: `GLYPH(${source})` }),
  write: (request) => ({ ok: true, source: `SOURCE(${request})` }),
};

test("the glyph face is withdrawn when the reader edits the source", () => {
  const page = loadPlayground();
  page.setGlue(rendering);

  page.type("editor", "trace 1");
  page.el("editor-face").click();
  assert.equal(page.el("editor-glyph").textContent, "GLYPH(trace 1)");
  assert.equal(page.el("editor-glyph").hidden, false);
  assert.equal(page.el("editor-face").textContent, "Hide glyphs");

  page.type("editor", "trace 2");

  // The fault: the face stayed, so the page showed GLYPH(trace 1) directly
  // beneath `trace 2` and called them two faces of one program.
  assert.equal(
    page.el("editor-glyph").hidden,
    true,
    "a face of the previous program is still showing",
  );
  assert.equal(page.el("editor-face").textContent, "Show glyphs");

  // Asking again renders the face of what is actually there now.
  page.el("editor-face").click();
  assert.equal(page.el("editor-glyph").textContent, "GLYPH(trace 2)");
});

test("the glyph face is withdrawn when Scribe writes into the editor", () => {
  const page = loadPlayground();
  page.setGlue(rendering);

  page.type("editor", "trace 1");
  page.el("editor-face").click();
  assert.equal(page.el("editor-glyph").hidden, false);

  page.el("request").value = "count from 1 to 5";
  page.el("write").click();

  // Assigning .value fires no input event, so this path has to withdraw the
  // face itself. Operator's reply lands in the editor the same way.
  assert.equal(page.el("editor").value, "SOURCE(count from 1 to 5)");
  assert.equal(
    page.el("editor-glyph").hidden,
    true,
    "the face survived a program the reader did not type",
  );
});

test("a face that will not render leaves its diagnostic in the miss slot", () => {
  const page = loadPlayground();
  page.setGlue({ glyph: () => ({ ok: false, error: "[line 1] broken" }) });

  page.type("editor", "trace )(");
  page.el("editor-face").click();

  assert.equal(page.el("miss").hidden, false);
  assert.equal(page.el("miss").textContent, "[line 1] broken");
  assert.equal(page.el("editor-glyph").hidden, true);
  assert.equal(page.el("editor-face").textContent, "Show glyphs");
});

test("a face that renders clears the diagnostic left by one that did not", () => {
  const page = loadPlayground();
  let broken = true;
  page.setGlue({
    glyph: (source) =>
      broken ? { ok: false, error: "[line 1] broken" } : { ok: true, glyph: `GLYPH(${source})` },
  });

  page.type("editor", "trace )(");
  page.el("editor-face").click();
  assert.equal(page.el("miss").hidden, false);

  broken = false;
  page.type("editor", "trace 3");
  page.el("editor-face").click();

  assert.equal(page.el("editor-glyph").textContent, "GLYPH(trace 3)");
  // The fault: the slot is shared, so the reader fixed the program, got the
  // glyphs, and kept the old error sitting above them.
  assert.equal(
    page.el("miss").hidden,
    true,
    "a stale diagnostic outlived the failure that caused it",
  );
});

test("translating Python sets the editor's source on success", () => {
  const page = loadPlayground();
  page.setGlue({
    translate_python: (source) => ({ ok: true, source: `SOURCE(${source})` }),
    glyph: (source) => ({ ok: true, glyph: `GLYPH(${source})` }),
  });

  page.type("editor", "trace 1");
  page.el("editor-face").click();
  page.el("python-source").value = "print(1)";
  page.el("translate").click();

  assert.equal(page.el("editor").value, "SOURCE(print(1))");
  assert.equal(page.el("miss").hidden, true);
  // Setting .value fires no input event, so this path has to withdraw the
  // face itself -- same contract writeProgram() already keeps.
  assert.equal(
    page.el("editor-glyph").hidden,
    true,
    "the face survived a program the reader did not type",
  );
});

test("every refusal is rendered into the miss slot, not just the first", () => {
  const page = loadPlayground();
  page.setGlue({
    translate_python: () => ({
      ok: false,
      refusals: [
        { reason: "no import statements", line: 1, column: 1, idiom: "" },
        { reason: "no while/else", line: 4, column: 3, idiom: "for-else" },
      ],
    }),
  });

  page.el("python-source").value = "import os\n";
  page.el("translate").click();

  assert.equal(page.el("miss").hidden, false);
  assert.equal(
    page.el("miss").textContent,
    "line 1: no import statements\nline 4: no while/else — for-else",
  );
});

test("a failed boot leaves no control looking usable", async () => {
  const page = loadPlayground();
  page.setGlobal("loadPyodide", () => Promise.reject(new Error("blocked")));

  await page.playground.boot();

  // #miss lives inside #live, so saying anything means revealing the block —
  // which is why every control in it has to be dead, not merely present.
  assert.equal(page.el("live").hidden, false);
  assert.equal(page.el("miss").hidden, false);
  assert.match(page.el("miss").textContent, /could not load/);

  for (const id of [
    "write", "run", "ask-operator", "editor-face", "cascade-face",
    "translit-latin", "translit-glyphs", "program-input",
  ]) {
    assert.equal(page.el(id).disabled, true, `${id} is still live after a failed boot`);
  }

  // Both boot buttons must come back: the reader can retry from either tab.
  assert.equal(page.el("boot").disabled, false);
  assert.equal(page.el("translit-boot").disabled, false);
});

// A full fail-then-retry-then-succeed run would need load() to actually
// resolve, which drags in pyodide.loadPackage, micropip.install, two
// fetch() calls and a dynamic import("./cascade.js") — none of which this
// harness's stub DOM provides (no `fetch`, no importModuleDynamically
// hook in the vm context), and no existing test in this suite attempts a
// full successful boot for exactly that reason. What playground.js exposes
// instead is finishBoot(), the function boot() calls once load() resolves —
// pulled out for this reason — so this test drives a failed boot for real
// (proving the gated controls start disabled and #miss starts populated),
// then calls finishBoot() directly to exercise the "undo the failure"
// contract in isolation, without needing a working load() pipeline.
test("boot() fails then succeeds re-enables every gated control", async () => {
  const page = loadPlayground();
  page.setGlue({ readers_table: () => "TABLE" });
  page.setGlobal("loadPyodide", () => Promise.reject(new Error("blocked")));

  await page.playground.boot();

  const gated = [
    "write", "run", "ask-operator", "editor-face", "cascade-face",
    "translit-latin", "translit-glyphs", "program-input",
  ];
  for (const id of gated) {
    assert.equal(page.el(id).disabled, true, `${id} is still live after a failed boot`);
  }
  assert.equal(page.el("miss").hidden, false);

  // The retry succeeds: playground.js's boot() would reach this point once
  // load() stops throwing, and calls finishBoot() itself.
  page.playground.finishBoot();

  for (const id of gated) {
    assert.equal(page.el(id).disabled, false, `${id} is still disabled after a successful retry`);
  }
  assert.equal(
    page.el("miss").hidden,
    true,
    "the failed boot's message is still showing after a successful retry",
  );
  assert.equal(page.el("live").hidden, false);
  assert.equal(page.el("translit-table").textContent, "TABLE");
});

test("typing Latin fills the Glyphs box, and back again", () => {
  const page = loadPlayground();
  page.setGlue({
    transliterate_text: (text) => `GLYPHS(${text})`,
    untransliterate_text: (glyphs) => `LATIN(${glyphs})`,
  });

  page.type("translit-latin", "hello");
  assert.equal(page.el("translit-glyphs").value, "GLYPHS(hello)");

  page.type("translit-glyphs", "abc");
  assert.equal(page.el("translit-latin").value, "LATIN(abc)");
});

test("running passes the input box's contents to the Python half", () => {
  const page = loadPlayground();
  let seen = null;
  page.setGlue({
    run: (source, stdin) => {
      seen = { source, stdin };
      return [];
    },
  });

  page.el("editor").value = "trace jackin";
  page.el("program-input").value = "Neo";
  page.el("run").click();

  assert.equal(seen.stdin, "Neo", "the input box never reached glue.run");
});

test("an example's glyph face toggles independently of its neighbours", () => {
  const page = loadPlayground({ faceToggles: 3 });
  const [first, second] = page.examples;

  first.button.click();
  assert.equal(first.pre.hidden, false);
  assert.equal(first.button.textContent, "Hide glyphs");
  assert.equal(second.pre.hidden, true, "a neighbouring example also opened");

  first.button.click();
  assert.equal(first.pre.hidden, true);
  assert.equal(first.button.textContent, "Show glyphs");
});

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

/**
 * A glue that records every call and keeps asking for one more line, up to
 * `until` answers. Enough to watch what the page sends across many rounds.
 */
function recordingGlue(page, { until = Infinity } = {}) {
  const calls = [];
  page.setGlue({
    run: (source, stdin, interactive, answers) => {
      // Copied, not stored by reference: `answers` is the page's own live
      // array, pushed into between rounds, so every entry would otherwise
      // read as its final state and a test of what each round sent would
      // assert nothing. `?? []` so that a page which stops passing a fourth
      // argument fails the test that is about the argument list, rather than
      // throwing inside every test that merely needs a glue.
      calls.push({ source, stdin, interactive, answers: [...(answers ?? [])] });
      return calls.length > until
        ? [{ kind: "output", text: "done", glyphs: "done" }]
        : [{ kind: "output", text: "next?", glyphs: "next?" }, { kind: "needs_input" }];
    },
  });
  return calls;
}

test("the program receives exactly the lines the reader supplied", () => {
  // The box and the typed answers are two channels and must stay two. They
  // were once flattened into one string here and split apart again in Python,
  // which composes only by luck: this test's box ends in a newline, the way a
  // <textarea> the reader pressed Enter in does, and the join-then-split
  // handed the second question "" and threw the typed answer away. A blank
  // answer vanished outright. Both are invisible on screen, so nothing but a
  // test that looks at the arguments can catch them coming back.
  const page = loadPlayground();
  const calls = recordingGlue(page, { until: 3 });

  page.el("editor").value = "trace jackin";
  page.el("program-input").value = "ana\n";
  page.el("run").click();
  page.el("answer").value = "bob";
  page.el("answer-send").click();
  page.el("answer").value = "";
  page.el("answer-send").click();

  assert.deepEqual(
    calls.map((c) => ({ stdin: c.stdin, answers: c.answers })),
    [
      { stdin: "ana\n", answers: [] },
      { stdin: "ana\n", answers: ["bob"] },
      // The blank answer is a line the reader gave, not an absence.
      { stdin: "ana\n", answers: ["bob", ""] },
    ],
    "the box and the typed answers were merged into one channel again",
  );
});

test("glue.run is called with interactive and the answers list positionally", () => {
  // Verified by mutation: dropping the `true` reverted the whole feature to
  // the old "no input left to read" error with every test still green,
  // because the Python tests all call glue.run by keyword and this file
  // stubbed glue without looking at what it was handed. Position is the
  // contract between the two halves, so something has to assert it.
  const page = loadPlayground();
  const calls = recordingGlue(page, { until: 1 });

  page.el("editor").value = "trace jackin";
  page.el("program-input").value = "box";
  page.el("run").click();
  page.el("answer").value = "typed";
  page.el("answer-send").click();

  assert.equal(calls[0].source, "trace jackin", "argument 1 is not the program");
  assert.equal(calls[0].stdin, "box", "argument 2 is not the Input box");
  assert.equal(calls[0].interactive, true, "argument 3 is not the interactive flag");
  assert.deepEqual(calls[1].answers, ["typed"], "argument 4 is not the answers list");
});

test("a program that asks forever is stopped rather than prompting forever", () => {
  // Each answer costs a full re-run, so an unbounded ask-loop makes the page
  // slower every round and never stops. The cap is the same promise the
  // interpreter's step limit makes, and until now nothing tested it: not the
  // limit, not the message, not that the row goes away when it fires.
  const page = loadPlayground();
  const calls = recordingGlue(page); // never satisfied

  page.el("editor").value = "dejavu true\n  trace jackin\nflatline";
  page.el("run").click();
  for (let i = 0; i < 100; i += 1) {
    page.el("answer").value = `answer ${i}`;
    page.el("answer-send").click();
  }

  assert.equal(page.el("answer-row").hidden, true, "the page is still asking past the cap");
  assert.equal(page.el("miss").hidden, false);
  assert.match(page.el("miss").textContent, /more than 100 answers/);
  // The first run plus one per answer, and then it stops asking.
  assert.equal(calls.length, 101, "the cap fired at the wrong round");
});
