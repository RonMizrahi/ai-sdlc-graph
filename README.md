# SDLC Graph Engineering

https://github.com/user-attachments/assets/c717c1dc-214d-4b6b-8ad5-55dd5107baf1

What you are watching is **`sdlc-graph`** — the software lifecycle as a guarded graph, running a
real feature end to end. It ships here, and so does the viewer rendering it.

*Two minutes, no audio. Not seeing a player? [Watch it on YouTube](https://www.youtube.com/watch?v=qrY74MvaVoU).*

**A process a machine can actually execute — and the method for turning any other process into one.**

Three [Claude Code](https://code.claude.com) plugins in one bundle. Two of them *are* a graph: the
software lifecycle expressed as typed nodes, *total* exit guards, bounded retry loops, a durable
run-state file that survives a crash, a ledger of every gate that could not run — and a
zero-dependency page that shows a run as it happens. The third turns **your** process into a graph
of its own: it writes the orchestrator, the auditor and the eval suite into your project, then
proves the result sound before handing it over.

[![License: MIT](https://img.shields.io/badge/License-MIT-black.svg)](LICENSE)
&nbsp;![Claude Code plugin](https://img.shields.io/badge/Claude%20Code-plugin-d97757)
&nbsp;![Domain agnostic](https://img.shields.io/badge/domain-agnostic-0d7d74)
&nbsp;![Zero dependencies](https://img.shields.io/badge/dependencies-0-6a787c)

![A linear SDLC — brainstorm, spec, plan, implement, review, release — transformed by graph engineering into an executable graph with typed nodes, guarded edges, bounded loops, durable state, and three typed terminal states: merge, publish, discard](docs/assets/traditional-vs-graph-sdlc.png)

---

## What's in the bundle

| Plugin | Skill | What it is |
|---|---|---|
| **`sdlc-graph`** | `sdlc-graph` · `graph-run-reviewer` | The software lifecycle already built as a graph: **20 nodes, 40 guarded transitions, ten bounded cycles, six declared human stops.** Spec → plan → strategy → per milestone (implement, test, Gate A, e2e, Gate B) → close-out → PR → CI → QA → merge. A run is one gitignored directory that survives context loss and resumes where it stopped. **Command-invoked — it never auto-triggers.** → [README](plugins/sdlc-graph/README.md) |
| **`sdlc-graph-viewer`** | `view-run` | The run viewer: one zero-dependency page rendering parallel milestone lanes, live or as a snapshot that opens from `file://`. One server per project, on a port derived from the project path. Optional — the graph runs identically without it. → [README](plugins/sdlc-graph-viewer/README.md) |
| **`sdlc-graph-engineering-install`** | `sdlc-graph-engineering-install` | The **method**: takes a process that has no graph — skills, a runbook, a CI config, or a description — and installs one, with its own orchestrator, auditor and eval suite. Domain-agnostic; needs no other plugin. → [README](plugins/sdlc-graph-engineering-install/README.md) |

The first two are one product in two halves — the viewer holds a copy of the graph's transition
table and checks itself against the spec on every edit. The third generalises what they are: the
method they are the worked reference for, and what you want if your process is not software
delivery.

---

## Example output

Example — superpowers as a graph (by [obra/superpowers](https://github.com/obra/superpowers)),
produced by `sdlc-graph-engineering-install`: **21 nodes, 96 guarded edges, 9 bounded cycles, 19
declared human stops** →
[RonMizrahi/superpowers-graph](https://github.com/RonMizrahi/superpowers-graph).

![Example output of the method — the spine: every node a run passes through, and the two shapes execution can take](docs/assets/superpowers-graph-spine.svg)

Read it as a state machine, not a flowchart. Guards are evaluated in table order and **exactly one
must match** — zero matching guards is a defect that halts the run, never a stall the graph guesses
its way out of. Cycles are annotated rather than drawn: 9 bounded, and 4 deliberately unbounded
because each one is a human revising their own decision, which is a conversation and not a retry.

*Your* graph will look nothing like this one — different nodes, different guards, your process. What
carries over is the structure: total guards, bounded cycles, typed stops, a ledger.

---

## Why prose processes fail

A process written as prose fails in ways prose cannot describe:

| | |
|---|---|
| **No run state** | Nothing records where it got to. An interruption restarts from guesswork. |
| **Unevaluated conditions** | *"retry if it's worth retrying"* is a condition nothing ever checks. |
| **Unbounded loops** | A retry with no declared limit runs until something else stops it. |
| **No record of what was skipped** | *"Never claim a step you didn't run"* is unenforceable if nothing records the absence. |
| **Invented human stops** | With no declared stop list, an agent invents them — and a 20-node run becomes 20 interruptions. |

Every one of those nine cycles already existed in the prose. None of them named a limit.

---

## Install

```
/plugin marketplace add RonMizrahi/sdlc-graph-engineering

/plugin install sdlc-graph@sdlc-graph-engineering                       # the SDLC as a graph
/plugin install sdlc-graph-viewer@sdlc-graph-engineering                # optional: watch a run
/plugin install sdlc-graph-engineering-install@sdlc-graph-engineering   # the method
```

Install any one of them on its own; none requires the others.

> **Breaking change, 0.7.0.** The method plugin was `sdlc-graph-engineering` through 0.6.0 and is
> **`sdlc-graph-engineering-install`** from 0.7.0. The *marketplace* name is unchanged, so
> `/plugin marketplace add` still works — but an existing install has to be removed and re-added
> under the new id.

**To run the lifecycle graph**, in the project you want it for: `/sdlc-graph start <feature>`, then
`resume` or `status`. It never auto-triggers — running an entire SDLC is not something to enter on a
description match.

**To install a graph for your own process**, say so: *"Install graph engineering here."* Or invoke
it directly: `sdlc-graph-engineering-install:sdlc-graph-engineering-install`. It also triggers on the
things people actually say — *"turn my workflow into a graph"*, *"make this runbook executable"*,
*"my agent loses track halfway"*, *"it retries forever"*, *"it says it did things it didn't do"*.

**No dependencies.** No npm install, no runtime, no service. Every eval suite here is plain Python 3
with an empty import list, and the viewer's server imports nothing but `node:*`. `sdlc-graph`
*dispatches* to review tools when they happen to be installed — see [Optional
tools](#optional-tools-and-what-happens-without-them) — and records the absence of every one that
is not.

---

## The method

*Everything from here to* **Layout** *is about `sdlc-graph-engineering-install` — the plugin that
builds a graph for a process that has none. `sdlc-graph` is the finished article: the same structure,
already built, for software delivery.*

### What it writes into your project

```
<your project>/
├── agents/
│   └── <graph>-monitor.md         the auditor — read-only, reports, never gates
└── skills/<graph>/
    ├── SKILL.md                   the orchestrator: dispatch loop, rules, human stops
    ├── references/
    │   ├── nodes.md               node contracts + diagrams
    │   ├── edges.md               the transition table, the bounds, the terminal states
    │   └── state.md               run-state schema, write points, resume rules
    └── evals/                     the traces, made executable — runs on every edit
```

Plus a **trace report** (three scenarios, each transition and the guard that fired), a **summary**
(nodes, edges, bounded cycles, human stops, every step whose tools may be absent), and a **green
eval run with its coverage line** — *N/N edges, N/N nodes*. Anything less names the gap.

---

### The nine steps

**Step 4 carries the weight** — the rest is drawing boxes.

| | Step | The point |
|---|---|---|
| 1 | **Inventory** | Every step in the user's own words — including *how it can fail*, which prose always omits. |
| 2 | **Decide what is a node** | A step is a node when it can fail, retry, be skipped, or be resumed into. Fewer nodes with real contracts beat many with vague ones. |
| 3 | **Contract every node** | `inputs` · `action` · `emits` · **`exits`** · guards · `on failure` · `max attempts` · `requires` · `human`. |
| **4** | **Make the guards total** | **Every exit matches exactly one guard.** Not zero — a legal outcome that halts the run. Not two — an ambiguous transition. |
| 5 | **Bound every cycle** | Count per-item, never globally. Never reset a counter, only key it. Plus a global step ceiling. |
| 6 | **Type the human stops** | `approval-after` · `choice-after` · `confirm-before` · `await-external` · `escalation` — then **declare the list complete**. |
| 7 | **Design the run state** | One file, written on *every* transition, *before* the next node starts. Including the ledger. |
| 8 | **Emit the files** | Model files, the orchestrator, the monitor, and the observability surface the state file has already paid for. |
| 9 | **Prove it** | Dry-trace the happy path, a retry that recovers, a retry that exhausts — then **emit those traces as an executable suite**. |

#### The trap step 4 exists to catch

Guard sets get written exhaustive over the **happy predicates** but not over their **product**. A
result with three independent properties has eight combinations; the three obvious guards cover
four. Reading a spec top-to-bottom never reveals the gap, because each guard looks correct in
isolation.

Worse: a field that can be `null`, absent, unknown or pending has more than two values, so a guard
pair written `X` / `NOT X` doesn't cover it — it silently folds the third value into one branch,
usually the one that skips work. **It doesn't halt when it's wrong**, which is what makes it worse
than a missing guard.

> Formally this is van der Aalst's **option to complete**: from every reachable state, the end must
> remain reachable. A guard gap is a state from which it is not.

#### And the reason to build a graph at all

> **The ledger is the load-bearing part.** Any process can claim it ran a step. Only one that
> records the *absence* can be trusted when it says it did.

---

### What ships with it

| File | Load at | Contents |
|---|---|---|
| **`SKILL.md`** | — | The nine-step method, the output contract, the validation checklist, and the rules for changing a graph that already has runs. |
| **`references/templates.md`** | step 8 | Skeletons for all five files, with the fields that matter already present rather than left to be remembered: `exits`, typed human stops, per-item attempt keys, the append-only ledger. |
| **`references/evals.md`** | step 9b | The eval suite in full — fixture format, how to write a check that reads as a diagnosis, what belongs in a negative control, and the scoping trap. |
| **`references/failure-modes.md`** | step 4 | **16 runtime failure modes**, each with its published name where one exists, so a defect is searchable rather than folkloric — workflow-net soundness, sequence manipulation (MAST FM-3.2), ping-pong livelock, the re-execution hazard, MAST FM-1.4, OWASP ASI01, the zombie-task stall, the surface that lies about the graph, the stop that fires where the human said *continue*, the obligation whose trigger is a judgement call. Plus a *what not to monitor* list, because a checker that fires constantly gets ignored. |

---

### Philosophy

- **A paper trace protects exactly one version of the graph.** Emit the traces as a suite and gate on
  coverage: every node entered, every edge traversed. A change that leaves the suite green without
  touching it has almost certainly added something untested.
- **A suite that cannot fail is not evidence.** Every graph ships a negative control — a file of
  deliberate violations the checker *must* reject.
- **Derive, never duplicate.** The moment a summary table and the node contracts each state the same
  six stops, they can disagree — and the summary is what people read.
- **Put the irreversible node last.** A verification step placed after the point of no return still
  runs, still reports honestly, and is still worthless.
- **Report, never gate.** The auditor is read-only. A monitor that halted runs would become a seventh
  human stop, right after you declared the list complete.
- **Tooling around a graph should be lighter than the graph.**

---

### When *not* to use it

- **The process is genuinely linear** — no branching, no retries, no human stops. A checklist is the
  right tool; a graph is overhead.
- **The steps are one action each.** A graph earns its cost across steps that can fail, retry, or be
  skipped — not around a single tool call.

---

## Layout

```
.claude-plugin/marketplace.json     the bundle manifest — three entries
plugins/
├── sdlc-graph/                     the SDLC as a graph
│   ├── agents/                     the milestone agent
│   ├── hooks/                      snapshots every state a --trace run passes through
│   ├── docs/                       EDITING · TESTING · the illustrated page
│   └── skills/{sdlc-graph,graph-run-reviewer}/
│       └── {graph,nodes,subagents,workflows,observability,evals}/
├── sdlc-graph-viewer/              the run viewer
│   └── skills/view-run/{viewer,server,fixtures,evals}/
└── sdlc-graph-engineering-install/ the method
    └── skills/sdlc-graph-engineering-install/{SKILL.md,references/}
.claude/hooks/                      runs the eval suites on every edit; gates every push
.githooks/pre-push                  the same gate for a human typing `git push`
docs/assets/                        the diagrams this README uses
THIRD-PARTY-NOTICES.md              the two files that are not first-party
CLAUDE.md                           repo operating guide
```

## Optional tools, and what happens without them

`sdlc-graph` dispatches to other tools at its quality gates rather than copying them, because a
copied reviewer drifts and then reviews against a stale rulebook. **Every absence is recorded in the
run's `skipped_gates[]` ledger and the run continues** — nothing is ever reported as passed because
its tool was missing.

| | Used at | Without it |
|---|---|---|
| `code-review`, `security-review` — built into Claude Code | Gate B, PR review, Gate A step 3 | Ledgered, run continues |
| `pr-review-toolkit:code-reviewer`, `code-simplifier` | Gate A steps 1, 2 and 4 | Ledgered, run continues |
| `claude-md-management:claude-md-improver` | Close-out | Ledgered; do the CLAUDE.md update by hand |
| `nestjs-backend-standards`, `front-react-development` — **the author's own private plugins, not installable from here** | Implement | Code is written against the project's own conventions instead |

## Contributing

Issues and PRs welcome. Two things make a change easy to accept:

1. **Say which failure it prevents.** Every rule here exists because a real graph broke without it
   — `references/failure-modes.md` is the running list, and a new rule belongs beside a new entry.
2. **A change is not done until it adds the eval that would have caught its absence**, and that eval
   is not done until a deliberately broken input makes it fail. *A check that cannot fail is not
   evidence.*
3. **`main` is PR-only**, and every change bumps the plugin `version` in *both* manifests so
   installed users actually receive it.

```bash
git config core.hooksPath .githooks                                        # once per clone
python3 plugins/sdlc-graph/skills/sdlc-graph/evals/run_all.py              # 9 suites
python3 plugins/sdlc-graph-viewer/skills/view-run/evals/run_all.py         # 8 suites
claude plugin validate ./plugins/<plugin> --strict && claude plugin validate .
```

Skill authoring follows the open [Agent Skills](https://code.claude.com/docs/en/skills) spec. The
rules that bind a change to this repo are in [`CLAUDE.md`](CLAUDE.md); the rules that bind a change
to the graph are in [`plugins/sdlc-graph/docs/EDITING.md`](plugins/sdlc-graph/docs/EDITING.md), and
that file comes first.

## Credits

By [Ron Mizrahi](https://github.com/RonMizrahi).

## License

MIT — see [LICENSE](LICENSE).

Two node procedures in `sdlc-graph` derive from [obra/superpowers](https://github.com/obra/superpowers)
(MIT, © 2025 Jesse Vincent) and carry its notice: see
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). Everything else here is first-party.
