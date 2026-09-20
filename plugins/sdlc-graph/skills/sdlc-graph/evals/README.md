# Evals

Seven deterministic suites, the Gate A script's own runtime harness, one behavioural set, and one
tier that **executes**. Everything here exists because a real run hit the defect it catches — no
check is hypothetical.

**`run_all.py` runs every deterministic one, and the repo's PostToolUse hook runs `run_all.py` on
every edit under this plugin** — along with the viewer's, because editing `edges.md` here is what
makes the viewer's copy of it stale. The whole set takes 3.6 seconds.

> **`runs/` is the tier that runs things.** Every other suite reads the spec and asks whether it
> contradicts itself; none of them can catch an orchestrator that reads the contract correctly and
> then behaves wrong. `run_scenario.py` drives ten scenarios in a scratch directory with
> `mock_milestone.py` — a milestone agent with the model taken out — as the deterministic other side, and asserts
> against the **artifacts** the run leaves rather than anything an actor says about itself. Its
> `--self-test` needs no agent and is what keeps the scenarios honest. See
> [`runs/README.md`](runs/README.md); it lists what the tier found on its first run,
> none of which was reachable by reading the spec.

## Where things are

```
evals/
├── run_all.py           the runner · EVAL-INSTRUCTIONS.md · README.md
├── lib/                 paths.py — THE LAYOUT, once · invariants.py — shared by walker and auditor
├── spec/                the spec agrees with itself, and those checks can fail
├── walks/               graph_walk.py · audit_walks.py · fixtures/
├── audit/               audit_run.py — a REAL run, offline · its self-tests
├── runs/                run_scenario.py · mock_milestone.py · scenarios/
├── real/                both sides real, against a real repo
├── hooks/               the trace hook's own cases
└── behavioural/         the cases only a model can answer
```

**Nothing counts `../` for itself — everything resolves through `lib/paths.py`.** Nine scripts here
used to, and the restructure invalidated every count; three broke *silently*, globbing a directory
that no longer existed and passing over an empty set.

```bash
cd plugins/sdlc-graph/skills/sdlc-graph

python3 evals/run_all.py              # everything below in one verdict — what the hook runs
python3 evals/spec/spec_consistency.py     # the spec files agree — with each other AND the milestone agent
python3 evals/spec/spec_controls.py        # ...and those checks can actually fail
python3 evals/walks/graph_walk.py           # scripted runs are legal, and cover the whole graph
python3 evals/audit/audit_selftest.py       # the offline auditor can actually fail
python3 evals/walks/audit_walks.py          # every legal walk holds up as a FINISHED run
python3 evals/runs/run_scenario.py --self-test    # every run-eval scenario is satisfiable AND breakable
python3 evals/hooks/snapshot_state_selftest.py    # the trace hook fires on a traced run, and on NOTHING else
node   workflows/gate-a.harness.mjs workflows/gate-a.workflow.js   # the one script, under a real runtime

# NOT in run_all.py — each needs something the hook cannot supply:
python3 evals/audit/audit_run.py docs/graph-runs/<run-id>/state.json --repo .   # a REAL run to audit
python3 evals/runs/run_scenario.py --list         # the ten scenarios that EXECUTE — a model
python3 evals/real/run_real_eval.py --list   # both sides real — a model
```

`audit_run.py` is the honest replacement for the monitor this graph no longer spawns: the same
checks, from the file alone, re-runnable by anyone who was not there.

It is pointed at exactly the files that went wrong, so **a malformed state file is its normal input,
not an edge case**: it reports on a history that is not a list, an entry that is not a transition, or
a counter that is not a number, and never answers with a traceback — a crash prints the report zero
times, which tells the person holding a broken run nothing at all. `audit_selftest.py` asserts that,
alongside the mutations.

No dependencies, no network, nothing to install. All exit non-zero on failure.

**Two of these were in no runner at all for a release** — `gate-a.harness.mjs`, because it was the
only `.mjs` in a directory of Python, and `run_scenario.py --self-test`, because the same file has
other modes that need an agent. Together they cost 0.10s. `every-deterministic-suite-is-wired-into-run-all`
now reads this directory and fails on a suite that no runner invokes; `.claude/hooks/run-graph-evals.selftest.py`
fails on a plugin the hook stopped routing to. Between them, "run them by hand" is no longer load-bearing.
A red suite mid-change is still expected — it is the second half of the edit, not an error.

> ### 📋 Adding or changing an eval? **Read [`EVAL-INSTRUCTIONS.md`](EVAL-INSTRUCTIONS.md) first.**
> It carries the rule (*a graph change is not finished until it adds the eval that would have caught
> its absence*), the fixture format, the negative-control requirement, the coverage gate, and what
> this suite deliberately cannot reach.

## `spec_consistency.py` — the spec does not contradict itself

The graph is described across `nodes.md`, `edges.md`, `state.md` and `SKILL.md`, and those
files restate the same facts in different words. **Drift between them is the dominant defect
class**: a Mermaid diagram routing on a predicate the transition table forbids, a cycle count
that says seven in one file and eight in another, a `context` field read by a node and declared
in no schema.

Each check names the real defect it guards against, in the `why` string beside it. **That list is
not restated here** — print it:

```bash
python3 evals/spec/spec_consistency.py --list     # every check, and the defect it would have caught
python3 evals/run_all.py --list              # every suite, and how much of it there is now
```

A table of them used to live in this file. It drifted twice — citing a check that had been renamed,
then one that had been retired — and it was policed by a check that read only this file, so it caught
none of the same drift in `docs/TESTING.md` or `docs/artifacts/index.html`. Deleting the copy deleted the
drift, the check, and the two surfaces' worth of it that nothing was watching.

## `graph_walk.py` — runs are legal, stops fire where declared, coverage is total

Walks scripted runs with **every node body mocked** — no code written, no agent spawned, no
branch created. Four things get checked:

1. Every transition is a declared edge quoting its guard **verbatim**.
2. The resulting state satisfies `state.md`'s invariants — bounds respected, counters keyed,
   ledger well-formed, history contiguous, `stopped` present on a halt, no invented values.
3. **The run stops for the human exactly where a node declares a stop, and nowhere else.** The
   stop table is parsed out of the `human` rows in `nodes.md`, so the checker cannot hold a stale
   copy of it; conditional stops are evaluated against the run's own state.
4. **The fixture set as a whole enters every node and traverses every edge** — a gate, not a
   report. 39/40 transitions, 19/20 nodes today.

### The fixtures

| Fixture | What only it proves |
|---|---|
| `strategy-a-happy.json` | Three milestones on one branch, then `CLOSE_OUT → PR → PR_FINAL_REVIEW → CI → QA → VERDICT → MERGE → DONE`. Five stops, including `PR`'s conditional one firing. |
| `strategy-b-backend-no-e2e.json` | **The stops that must not happen.** Spec supplied (no `SPEC`), `auto_open_mr` true (no `PR` stop), `has_ui` false (no `E2E`, and no ledger entry for it), 22b skipping QA out loud. Plus a `PLAN` revision and a red CI round-trip. |
| `strategy-c-checkpoint.json` | `CONSOLIDATE`, the second `GATE_B` pass, four `DEBUG` round-trips, and `checkpoint` mode — which stops after each milestone's `GATE_B` but **not** when `GATE_B` routes to `DEBUG`. |
| `loops-and-reopen.json` | A dead Gate A dispatch counted separately from a findings re-run, seven ledger entries, and a QA `BLOCK` reopening with an `is_fix` milestone. |
| `blocked-has-ui-null.json` | The tri-state halt, at `STRATEGY` where the field is settled rather than at `GATE_A` 200 lines later. The only walk ending `BLOCKED`; asserts `stopped` carries every guard tested. |
| `handoff-strategy-d.json` | Edge 7. The only walk ending `HANDOFF`, where `stopped` must **survive** to the end. |
| `verdict-escalation-on-exception.json` | `VERDICT`'s escalation firing — silent in every other fixture — plus `on-exception` mode. Starts mid-run. |
| `negative-control.json` | Five structural violations the harness must reject. |
| `negative-control-stops.json` | Six stop-and-coverage violations it must reject, including a stop invented at `IMPLEMENT`, and a node stop declared inside a milestone block. |
| `milestone-dies-and-is-respawned.json` | A milestone agent that returns no bundle. The re-spawn is charged to `MILESTONE-dispatch`, **never** to the node budgets — a dead milestone agent tested nothing. |
| `milestone-bundle-rejected.json` | **Negative control.** Four ways a bundle claims work nothing checked: a gate with no R7, an `IMPLEMENT` with no commits, `authored` specs nobody opened, and a block opening mid-itinerary. |
| `milestone-early-return-on-exception.json` | The only path where a milestone agent hands a question back — it cannot ask, so it returns `stop_requested` and the orchestrator serves the stop at the boundary. |
| `milestone-hides-a-retry.json` | **Negative control, and the only one the journal can catch.** A red `TEST`, a `DEBUG` fix and a green retry — all written to the journal as they happened — reported back as one clean pass. Every other check is satisfied: real shas, a green suite, the right branch, non-empty observations. Only R13 disagrees, and only in one direction. |

> **The negative controls are the point.** A suite that cannot fail is not evidence. If either
> ever passes, the harness has stopped checking and every other green here is worthless.

**Adding or changing one? → [`EVAL-INSTRUCTIONS.md`](EVAL-INSTRUCTIONS.md).**

`expect` takes `final_status`, `reaches: []` for nodes the walk claims to exercise, and
`rejected: true` with `because: []` for a negative control.

## `spec_controls.py` — the spec checks can actually fail

`graph_walk.py` has had negative controls since it was written. `spec_consistency.py` never did, and
its checks are regexes over prose — the easiest kind to write in a way that cannot fail. This runner
copies the plugin, mutates **one** file, and requires the named check to go red.

It found two dead checks on its first run, both written the same hour as the change they guard: one
asserted `guards_tested`/`tried` existed anywhere in `state.md` rather than inside the `stopped`
shape, the other asserted `git diff --name-only` appeared anywhere in `workflow-dispatch.md` rather
than inside the `R7` row. Both passed with the thing they check for deleted.

**Scope: the checks the schema-5 change added or reshaped.** The older checks predate this runner and
are not covered — a real gap, named here rather than left implied.

## `audit_selftest.py` — the auditor can actually fail

`audit_run.py` is what replaced the monitor. An auditor nobody audits is the shape this plugin keeps
rediscovering, so this takes a healthy run state, breaks it **one way at a time**, and asserts the
auditor goes red for the right reason: a milestone agent transition with no verification, a gate green while its
own tool is ledgered, a blown bound, an invented counter key, an emptied observation, a leaked token,
a paraphrased guard, a stranded milestone agent, a milestone spawned before its journal was written.

It also asserts the **unmutated baseline passes** — a checker that fails on everything is not
evidence either — and that `commit-bundle-record` reports NOT RUN without `--repo` rather than
quietly counting as green.

## `audit_walks.py` — legal to walk, and still sound afterwards

`graph_walk.py` asks whether a run is legal **while it is walked**. `audit_run.py` asks whether the
trail holds up **to someone who was not there**. This closes the gap between them at no authoring
cost: every legal fixture already describes a complete run, so it replays each one to its final state
and audits it.

Four defects in `audit_run.py` surfaced the first time this ran — a missing `[handoff]` alias, a
guard demanded of halts that have none, and `GATE_A.step2` being read as `GATE_A`. All three would
have accused honest runs.

## `evals.json` — the behaviours no static check reaches

The deterministic suites verify the *spec*. They cannot verify that an orchestrator **obeys**
it — and the worst failure in this plugin's history was obedience, not structure: a run that
halted at `IMPLEMENT` with nothing wrong, and only restarted because a human noticed.

Those cases live in `evals.json` in the repository's usual prompt/expected-output form.
