# How the graph plugins are tested

Referenced from `CLAUDE.md`. The human-facing version of this, with diagrams, is
`plugins/sdlc-graph/docs/artifacts/index.html` → the **Testing** view
([view](https://claude.ai/code/artifact/045a2e11-cade-45c0-9484-b2edf0db8903)).

**The rule everything here turns on:** a change is not finished until it adds the eval that would
have caught its absence — and that eval is not finished until a deliberately broken input makes it
fail. *A check that cannot fail is not evidence.* Contract, fixture format and the negative-control
requirement: `plugins/sdlc-graph/skills/sdlc-graph/evals/EVAL-INSTRUCTIONS.md`.

---

## Method 1 — deterministic (no agents)

Reads the spec files and fixtures and asks whether they contradict each other. No model, no network,
no dependencies. **The whole set runs in 3.6 seconds**, which is why the `PostToolUse` hook fires all
of it on every edit to a graph plugin — there was never a budget worth trading correctness for.

Two runners, because a plugin may not read above its own root: `run_all.py` in each. The hook runs
both when the *graph* is edited, since that is the edit which makes the viewer's copy stale.

**The suite list is not restated here.** It drifted three times when it was — 41 checks against
49, 7 against 8, 63 assertions against 81 — and the check policing it read only `evals/README.md`,
so it caught none of that. Print it instead:

```bash
python3 evals/run_all.py --list           # every suite, and how much of it there is now
python3 evals/spec/spec_consistency.py --list  # every check, and the defect it would have caught
```

Today that is six deterministic suites plus the Gate A script's runtime harness in this plugin, and
three more in the viewer. `every-deterministic-suite-is-wired-into-run-all` fails on any suite on
disk that no runner invokes.

## Method 2 — executing (agents)

Method 1 structurally cannot catch an orchestrator that reads the contract correctly and then
*behaves* wrong: spawns before arming its monitor, writes `history[]` from a bundle it never gated,
or answers a dead milestone agent by waiting longer. Behaviours have to be run to be observed.

### 2a · `evals/runs/` — real root, scripted milestone agent

A subagent plays the orchestrator against `mock_milestone.py`, a milestone agent with the model taken out: it emits
exactly the journal lines the scenario dictates and returns exactly the bundle it dictates,
**including a dishonest one**. Eight scenarios, each with a control that must break it.

This tier exists for the two things a real agent cannot be relied on to do: **lie in one exact way**
(a bundle hiding precisely one retry) and **die mid-node**.

### 2b · `evals/real/` — both sides real, then judged

A scripted milestone agent satisfies the journal contract *by construction* — perfect lines, correct `seq`,
appended before it returns. But nearly every demand in that contract is on the **milestone agent**: append as you
leave each node rather than reconstructing on the way out, write a `detail` useful to a reader with
none of your context, never touch a sibling's file. A fixture that cannot fail those cannot test them.

So both sides are real, against a real git repo whose test scripts actually run. Attribution does not
need a scripted counterpart — the artifacts are already separated by author: **journal shape is the
milestone agent's, state-file writes are the root's.**

Each test declares a **start**, an expected **path** and an **end**; `--check` compares them
mechanically and emits an evidence bundle. The **top-level orchestrator then judges** what a predicate
cannot express — whether a `detail` would really help the next milestone, whether a trail is
uniformly cheerful, whether a journal reads as written-afterwards. It judges *with the deterministic
results in hand*, and it did none of the work.

> **Never** ask the actor under test how it did. That is a self-report from the thing being checked —
> the exact failure the return gate exists to prevent, rebuilt one level up inside the harness.

---

## Running them

The hook watches `plugins/sdlc-graph/`, `plugins/sdlc-graph/` and
`plugins/sdlc-graph-viewer/`, matched on path **segments** so one fork never fires the other's
suite over its edit. Method 1 therefore runs itself. What is below is method 1 on demand, plus the
tiers no hook can run because they need a model.

```bash
B=plugins/sdlc-graph/skills/sdlc-graph/evals
V=plugins/sdlc-graph-viewer/skills/view-run/evals

python3 $B/run_all.py                         # method 1 — what the hook already ran
python3 $V/run_all.py                         # method 1 — the viewer's half of it
python3 .claude/hooks/run-graph-evals.selftest.py   # ...and that the hook still routes to every suite on disk

python3 $B/runs/run_scenario.py --list        # method 2a — the eight scenarios
python3 $B/real/run_real_eval.py --list       # method 2b — the real-agent tests
python3 $B/audit/audit_run.py docs/graph-runs/<run-id>/state.json --repo .   # audit a REAL run, afterwards
```

**Editing this plugin runs the viewer's suite too.** The viewer holds a copy of the transition
table, and a plugin may not read above its own root — so the graph's own suite cannot check the
page that renders it, and the checks that can live over there, in the one legal direction. The
routing table fans a graph edit out to both.

A red suite mid-change is expected — it is the second half of the edit, not an error.

## What each method has actually caught

| Found by | Defect |
|---|---|
| deterministic | A guard fixed in `edges.md` and not in the viewer that renders it — repeatedly. |
| deterministic | `guards-verbatim` going green *precisely when there was no guard to quote*: `norm(None)` is `""`, and `""` is a substring of everything. |
| deterministic | A guard-identifier extractor reading the cell *after* its backticks were stripped — zero matches corpus-wide, 26 of 42 guards checked against nothing. |
| deterministic | Three published artifacts a release behind, because the count check matched spelled-out numbers only and every footer used digits. |
| executing | **A contradiction between two spec files** — R13's repair path says replay the omitted hops; `state.md` says only the agent that was there may author an observation. An orchestrator obeying both had to halt on a milestone agent that merely tidied its story. |
| executing | **The auditor accusing a run of the thing it had just prevented** — refusing a fabricated bundle leaves the same shape as hiding the work. |
| executing | Two scenario fixtures whose bundles were too thin to pass the gate they were testing. |

The pattern is stable: deterministic finds **drift and dead checks**; executing finds
**contradictions that only surface when someone has to obey both rules at once**.
