# Eval instructions — what is expected, and how to write it

The contract for this directory. `README.md` says what exists; this says **what you owe when you
change the graph, and how to discharge it**.

---

## The rule

> **A graph change is not finished until it adds or updates the eval that would have caught its
> absence.**

Not "should". The graph's whole claim is that its behaviour is mechanical rather than narrative — a
change that only exists as prose has no mechanism behind it and will be re-litigated by the next
reader. Concretely:

| You changed | You owe |
|---|---|
| A new **edge** | a walk fixture that traverses it. *(Enforced for you — `graph_walk.py` fails on any untraversed edge.)* |
| A new **node** | a walk that enters it. *(Also enforced.)* |
| A **guard** on an existing edge | a walk step exercising the new condition — **not enforced**, the coverage gate only knows the edge was taken. This is the one that slips through. |
| A new or changed **human stop** | a fixture where it fires, **a fixture where it must not**, and a planted violation in a negative control. |
| A new **invariant** on state | a check in `spec/spec_consistency.py`, plus a planted violation. |
| A new **field** in the schema | a check that it is declared where it is read, and its presence asserted in the walker's invariants. |
| A **count** published anywhere | nothing — `published-counts-match-reality` already covers it. |
| A rule an orchestrator must **obey** — a stop it must not invent, a bound it must not spend, a pass it must not fake | an **executing** case: a `runs/scenarios/*.md`, a `real/tests/*.md`, or a `behavioural/evals.json` entry. **Author it; do not drive it.** |

**A change that leaves the suite green without touching it has probably added something untested.**
Assume that before assuming the suite was already sufficient.

> **Write the executing case, and leave it undriven.** That tier needs a model and real minutes per
> test, so it is run **on demand by a human** — never by a hook, and never as a condition of pushing.
> The cost of authoring a case is a few minutes of writing; the cost of driving it is money. Those
> are different decisions and they do not have to be made at the same time.
>
> A case you wrote and did not drive lists as `NO RECEIPT` in
> `python3 .claude/hooks/eval-receipts.py --list`, which is the honest state: it exists, it is
> registered, it is addressable by name, and nobody has paid for it yet. **A case nobody wrote can
> never be driven at all** — that is the failure this rule prevents, and it is the one that actually
> happens, because the moment to think of the case is the moment you are changing the rule.

---

## The three kinds, and when each applies

| Kind | File | Answers | Needs a model? |
|---|---|---|---|
| **Spec check** | `spec/spec_consistency.py` | Do the files describing the graph contradict each other? | no |
| **Walk fixture** | `walks/fixtures/*.json` | Is a run through the graph legal, and does the set cover it? | no |
| **Behavioural** | `behavioural/evals.json` | Does an orchestrator *obey* the spec under pressure? | yes |

The first two run on every edit. The third is prompt/expected-output and is run deliberately, because
the failures it catches — halting at `IMPLEMENT` with nothing wrong, faking a green to get past a
bound — are failures of obedience, and no static check reaches them.

---

## Writing a spec check

```python
@check("has-ui-null-is-blocked-before-routing",
       "NOT has_ui is true for null, so a null would erase E2E for a whole run with no ledger entry")
def _(spec):
    ...
    return None            # pass
    return "what is wrong" # fail — a sentence a reader can act on
```

- **Name the check for the defect, not the property.** `has-ui-null-is-blocked-before-routing`, not
  `check-guards`. The name is what appears in a red run, and it should read as a diagnosis.
- **The `why` string is the real defect it was written for**, in the past tense. Every check in this
  file has one because every check here was paid for by a real run. If you cannot write that
  sentence, you may be guarding a hypothetical — which is how a suite grows noisy and gets ignored.
- **Return a sentence, not a boolean.** The failure text is the whole value of the check.
- **Beware matching your own prose.** Fixes explain what they replaced, so the wrong wording appears
  in the file as a *quotation*, and the paragraph explaining a rule necessarily contains the rule's
  own words. **This is the single most common way a check here turns out to be inert** — eight in
  one session, every one found by writing its control: a `touch` check that the paragraph about
  `touch` satisfied; an owner cell whose prose said "the agent" while the owner was `inline`; a
  three-way alternation where deleting the invariant left a synonym matching; a mutation that renamed
  its own source line. **Scope the assertion to the thing that carries the rule** — the table row,
  the command, the shape — never the file.
- **Asserting the ABSENCE of a phrasing is the worst case of that**, and it is why four checks were
  retired rather than fixed: a rewrite of the paragraph explaining a removal reads, to a regex,
  exactly like the removal coming back.

`spec` holds `nodes`, `edges`, `state`, `skill`, `e2e`, `published` (every countable surface in
the plugin, keyed by relative path) and **`plugin_files`** (every readable file in the plugin, same
keying).

**Pick the narrower one that answers your question.** `published` is a curated glob and is right for
a *claim* — only a published surface can publish a stale count. `plugin_files` is right for a
question about what the plugin may **contain**, and it exists because `published` reaches neither
`evals/walks/fixtures/*.json` nor most of `nodes/`, which is where two of the eight unpublished
plugin names survived a hand sweep that had found the other six.

> **A check over `plugin_files` matches its own explanation.** `no-unpublished-plugin-name-ships-in-this-plugin`
> scans the file it is written in, so its patterns spell the forbidden names with a bracketed hyphen
> — `nestjs-backend[-]standards` — and its controls build them by concatenation. If you ever explain
> that removal in prose, describe it; do not spell it. The same goes for a commit message a reader
> will grep.

---

## Writing a walk fixture

A fixture is one scripted run with **every node body mocked** — nothing is built, no agent spawned,
no branch created. It exercises control flow only.

```jsonc
{
  "name": "…",              // what shape this walk is
  "why": "…",               // what it proves that no other fixture does
  "expect": {
    "final_status": "DONE", // or BLOCKED / HANDOFF
    "reaches": ["…"],       // nodes this walk claims to exercise
    "stops": ["SPEC:approval-after", "…"]   // the EXACT ordered stop sequence
  },
  "initial_state": { … },   // a full state file; may start mid-run
  "steps": [ … ]
}
```

Each step:

```jsonc
{
  "from": "GATE_A", "to": "E2E",
  "edge": "12",             // the edge id from edges.md — NOT the guard text
  "milestone": 1,
  "observation": "…",       // required, and it should say something
  "set":  { "attempts.GATE_A:1": 1 },        // dotted paths; index == length appends
  "skipped_gates": [ { "node": …, "reason": …, "at_milestone": … } ],
  "stops": [ { "type": "approval-after", "answer": "approved" } ],
  "halt":  { "guards_tested": [ … ], "tried": [ … ] },  // only on a transition to BLOCKED, which
                                                       // has no `edge`: an `on failure` exit is not
                                                       // a guarded transition and no row declares it
  "e2e_specs": "authored" | "regression-only" | "ledgered",  // only on steps leaving E2E

  // --- milestone-sourced steps: the milestone loop runs in an agent -------------------------
  "agent": { "bundle": true, "verified": ["R6"] },         // what the RETURN GATE checked, per node
  "evidence": { "commits": ["a1b2c3d"], "run_id": null },  // required on IMPLEMENT steps
  "agent_stop": "on-exception"                             // the agent returned early, mode-stop pending
}
```

> **The key names above are the ones `graph_walk.py` actually reads.** They were documented as
> `"milestone agent"` and `"milestone agent_stop"` for a release — the output of a blind rename — and
> one fixture was written from the docs. The walker never saw that fixture's `agent_stop`, so the
> only fixture exercising the on-exception early return proved nothing; it passed on its
> `skipped_gates` instead. **A step key the walker does not read is silently inert**, which is why
> `unknown-step-keys` now rejects any key not in the documented set.

> **A step names its EDGE, and the guard is looked up.** Fixtures used to carry the guard text
> verbatim: 170 copies of 39 distinct strings, the most-copied appearing 17 times, so rewording one
> guard in `edges.md` was a seventeen-file JSON edit. An id is also stricter — it names one
> transition, where a guard string was matched by substring and could match two. `history[].guard` is
> still written verbatim from `edges.md`, so what `state.md` requires is better served, not weakened.
> A fixture carrying `guard` is now rejected outright: two accepted spellings is the drift this removed.

> **The two DEBUG rules are one table row each, and a fixture names the EXPANDED id.** Edge 19 is
> written once — *any of `TEST` · `E2E` · `GATE_A` · `GATE_B` · `CI` · `CONSOLIDATE` → `DEBUG`* —
> and edge 20 is its return, keyed on `debug_return_to`. Twelve transitions, two rows,
> because writing them out twelve times is twelve places for one rule to drift. `graph_walk.py` expands
> them per caller, so a step into `DEBUG` from `GATE_A` carries `"edge": "19·GATE_A"` and its
> return carries `"20·GATE_A"` — a bare `"19"` in a fixture names no transition and is rejected.
> In *prose* a bare `19` is correct and stays correct, because it names the row; that is the half
> of `eval-prose-cites-edges-that-exist` the expanded ids cannot reach on their own.

### Milestone blocks

A step carries `agent` when its facts came from a milestone bundle rather than from a node the
orchestrator ran itself. Those steps form a **block**: it opens on a step leaving `BRANCH`, runs
over the seven nodes a milestone agent owns (`BRANCH IMPLEMENT TEST GATE_A E2E GATE_B DEBUG`), and
closes on the step leaving `GATE_B` — or on a halt.

- **`agent.verified` names the world-sourced checks that were run before the transition was
  written**, and the walker requires the ones that node owes: `R4` for `BRANCH`, `R4`+`R5` for
  `IMPLEMENT`, `R6` for `TEST` and `GATE_B`, `R7`+`R8` for `GATE_A`, `R9` for `E2E`, `R4` for
  `DEBUG`. A milestone step naming none of them is a transition written on an agent's word, which is
  the failure delegation introduces — see `workflow-dispatch.md` § The return gate.
- **Not every DEBUG round-trip is the agent's.** When `debug_return_to` is `CI` or `CONSOLIDATE` the
  round-trip belongs to the orchestrator, because those callers do. Marking it `agent` is wrong and
  the walker says so.
- **The integration `GATE_B` pass (after `CONSOLIDATE`) has no agent at all** — every milestone agent
  has already returned by then.
- **No orchestrator step may interleave inside an open block.** The replay is serial: transitions
  are written in the milestone agent's order, so one of the orchestrator's own cannot appear among
  transitions that have not been written yet.

### Five rules that matter more than the rest

1. **Guards verbatim.** Copy from `edges.md`, do not paraphrase. A trail that does not match the table
   cannot be checked against it, and paraphrase is itself a reported defect. (Backticks, bold and
   whitespace are normalised; wording is not.)
2. **A stop belongs to the step LEAVING its node.** The stop happens *inside* the node, before it
   emits a transition, so `SPEC`'s approval sits on `SPEC → PLAN`. `expect.stops` then fails both when
   a declared stop is missing and when an undeclared one appears.
3. **Conditional stops need a fixture in each direction.** `PR`'s `confirm-before` fires only when
   `auto_open_mr == false`; `VERDICT`'s `escalation` only once `attempts.QA` hits its bound. **The
   fixture where the stop must NOT fire is the one nobody writes, and it is the one that regresses**
   — a stop taken where the user said continue costs what an invented stop costs and reads as
   diligence. `strategy-a-happy` fires both; `strategy-b-backend-no-e2e` proves neither does.
4. **Every step's `observation` is written for a human reading the trail later.** "SIMULATED" is
   acceptable on a step that is genuinely just plumbing; on the step the fixture exists for, say what
   is being proved and why it once went wrong.
5. **A walk may start mid-run.** `verdict-escalation-on-exception` opens at `CLOSE_OUT` with both
   reopens already spent, because reaching that state legitimately would have cost thirty steps of
   plumbing to exercise two stops. Set `initial_state` to the resumed state and say so in `why`.

### Coverage is a gate

Run with no arguments and the suite **fails** if the fixture set does not enter every node in
`nodes.md` and traverse every edge in `edges.md`. Naming specific fixtures on the command line skips
the gate, for iterating. An untraversed edge is an untested guard — usually the configuration variant
nobody traced.

---

## The negative control is the load-bearing fixture

`negative-control.json` and `negative-control-stops.json` are walks that **must be rejected**, each
planted violation named in `expect.because`.

> **A suite that cannot fail is not evidence.** If a negative control ever passes, the checker has
> stopped checking and every other green in this directory is worthless.

- **Add to one whenever you add a check.** The new check's first fixture is a planted violation of it.
- **Keep a legal step or two in each**, so the control cannot be satisfied by a checker that rejects
  everything.
- **`because` entries are substrings of the expected failure message.** Extra violations beyond the
  named set are fine — one planted defect often trips two checks.

---

## Where a new file goes

```
evals/
├── run_all.py              the runner — every deterministic suite, one verdict
├── EVAL-INSTRUCTIONS.md    this file
├── README.md               what each suite covers
├── lib/
│   ├── paths.py            THE LAYOUT, written down once. Nothing else counts `../`.
│   └── invariants.py       state.md's invariants — the walker and the auditor share them
├── spec/                   spec_consistency.py + spec_controls.py
├── walks/                  graph_walk.py · audit_walks.py · fixtures/*.json
├── audit/                  audit_run.py + audit_selftest.py
├── runs/                   run_scenario.py · mock_milestone.py · scenarios/NN-*.md
├── real/                   run_real_eval.py · SYSTEM.md · tests/
└── behavioural/            evals.json
```

**Resolve paths through `lib/paths.py`, never by counting `../` from your own file.** Nine scripts
here used to do the counting; the restructure invalidated every count, and three of them broke
*silently* — they globbed a directory that no longer existed, found nothing, and reported a clean
pass over an empty set. A glob that matches nothing is a check that cannot fail, arriving through
the back door of a file move.

The same hazard has a second door: `published-counts-match-reality` found the rendered HTML through
`docs/*.html`, and moving `index.html` into `docs/artifacts/` switched the check off without
changing a line of it. Its control now corrupts a count *inside* the artifact, so it goes DEAD the
moment the check stops opening the file. **When you move a file, run the controls — do not read
them.**

---

## Scope: what this suite may and may not read

The suite reads **only files inside `plugins/sdlc-graph/`**. That is the marketplace rule — a plugin
references nothing above its own root.

**`sdlc-graph-viewer` and `sdlc-graph-engineering-install` are therefore out of reach**, and both
mirror facts about the graph. That is a real gap, and it is failure mode 13: the guard fixed in
`edges.md` and not in the surface that renders it. It is covered by the rule in the root `CLAUDE.md`
and by nothing else — **not** by anything here, and no longer by an auditor agent either. When you change a guard, a count,
or a stop, open the viewer and `docs/artifacts/*.html` yourself.

---

## How it runs

```bash
python3 evals/run_all.py          # every deterministic suite, one verdict
```

**The PostToolUse hook (`.claude/hooks/run-graph-evals.py`) runs this on every edit under
`plugins/sdlc-graph/`**, and the viewer's `run_all.py` alongside it — a guard edited here is
what makes the viewer's copy stale, and the viewer is the only side allowed to look across.

A plugin was once left out of that hook on purpose — "that one is where you break things" — which
in practice meant its suites ran late and two of them were in no runner at all. The whole
deterministic set costs 3.6s, so nothing is excluded now. When you add a suite, add it to `SUITES`
in `run_all.py` —
`every-deterministic-suite-is-wired-into-run-all` reads the directory and will fail until you do.

**A red suite mid-change is expected.** Editing `graph/nodes.md` before `SKILL.md` leaves the spec
inconsistent. A red suite is the second half of the edit, not an error — the change is finished when
`run_all.py` stops saying so.
