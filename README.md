# SDLC Graph Engineering

The software lifecycle as a **guarded graph your coding agent can actually execute** — typed nodes,
total exit guards, bounded retry loops, durable run state, and a ledger of every gate that could not
run. Plus the viewer that shows a run as it happens, and the method for turning any *other* process
into a graph of its own.

https://github.com/user-attachments/assets/c717c1dc-214d-4b6b-8ad5-55dd5107baf1

What you are watching is `sdlc-graph` driving a real feature end to end, rendered by
`sdlc-graph-viewer`. Both ship here.

*Two minutes, no audio. Not seeing a player? [Watch it on YouTube](https://www.youtube.com/watch?v=qrY74MvaVoU).*

[![License: MIT](https://img.shields.io/badge/License-MIT-black.svg)](LICENSE)
&nbsp;![Claude Code plugins](https://img.shields.io/badge/Claude%20Code-3%20plugins-d97757)
&nbsp;![20 nodes, 40 guarded transitions](https://img.shields.io/badge/20%20nodes-40%20guarded%20transitions-0d7d74)
&nbsp;![Zero dependencies](https://img.shields.io/badge/dependencies-0-6a787c)

![A linear SDLC — brainstorm, spec, plan, implement, review, release — transformed by graph engineering into an executable graph with typed nodes, guarded edges, bounded loops, durable state, and three typed terminal states: merge, publish, discard](docs/assets/traditional-vs-graph-sdlc.png)

## Table of Contents

- [How it works](#how-it-works)
- [Installation](#installation)
- [The basic workflow](#the-basic-workflow)
  - [Where it stops for you](#where-it-stops-for-you)
  - [What each gate catches](#what-each-gate-catches)
  - [Branching strategy changes the topology](#branching-strategy-changes-the-topology)
  - [Watching a run live](#watching-a-run-live)
- [When something goes wrong](#when-something-goes-wrong)
- [What's inside](#whats-inside)
- [Optional tools, and what happens without them](#optional-tools-and-what-happens-without-them)
- [How this is tested](#how-this-is-tested)
- [Philosophy](#philosophy)
- [Contributing](#contributing)
- [Updating](#updating)
- [License](#license)

## How it works

You say `/sdlc-graph start "<feature>"`. Nothing auto-triggers it — running an entire lifecycle is not
something to enter on a description match.

From there the run is a **state machine, not a prompt**. Twenty nodes, forty transitions, and every
transition guarded: guards are evaluated in table order and **exactly one must match**. Zero matching
guards halts the run as a defect rather than letting an agent guess its way forward. Every retry loop
declares a bound, counted per item, never reset. Every transition writes
`docs/graph-runs/<run-id>/state.json` **before** the next node starts, so a crash between two nodes
still leaves a file saying exactly where the run was — and *"where were we?"* resumes it.

Five things follow from that, and they are the whole point:

| | Written as prose | Executed as a graph |
|---|---|---|
| **Run state** | nothing records where it got to; an interruption restarts from guesswork | one typed file per run, written on every transition, resumable |
| **Conditions** | *"re-run if the findings are significant"* — a condition nothing checks | a guard that evaluates, in a table where exactly one must match |
| **Loops** | real cycles, none naming a limit | every cycle bounded, per item, and the bound is enforced |
| **Skipped work** | *"never claim a gate you didn't run"* — unenforceable if nothing records the absence | preflight resolves each node's `requires`; a missing tool appends to `skipped_gates[]` and **the node cannot be marked passed** |
| **Human stops** | invented ad hoc, so a 20-node run becomes 20 interruptions | six declared stops, derived from the node contracts so the list cannot drift |

The work itself does not happen in the orchestrator's context. **A milestone agent is spawned per
milestone**, runs the whole build-and-review loop, and returns one typed bundle. The orchestrator
verifies that bundle against git, against a test suite it re-runs itself, and against the agent's
journal — and only then writes the transition. **A gate it cannot evidence is re-run, not recorded.**

## Installation

Claude Code:

```
/plugin marketplace add RonMizrahi/sdlc-graph-engineering

/plugin install sdlc-graph@sdlc-graph-engineering                       # the graph
/plugin install sdlc-graph-viewer@sdlc-graph-engineering                # optional: watch a run
/plugin install sdlc-graph-engineering-install@sdlc-graph-engineering   # optional: the method
```

Install any one of them on its own; none requires the others. **No npm install, no runtime, no
service** — every eval suite is plain Python 3 with an empty import list, and the viewer's server
imports nothing but `node:*`.

> **Breaking change, 0.7.0.** The method plugin was `sdlc-graph-engineering` through 0.6.0 and is
> **`sdlc-graph-engineering-install`** from 0.7.0. The *marketplace* name is unchanged, so
> `/plugin marketplace add` still works — but an existing install must be removed and re-added under
> the new id.

Then, in the project you want driven:

```
/sdlc-graph start "add rate limiting to the public API"
/sdlc-graph resume          # or just: "where were we?"
/sdlc-graph status
```

## The basic workflow

1. **`INTAKE`** — detects stack, whether there is a UI, branch and host; creates the run directory.
2. **`SPEC`** → **stops for you.** A design dialogue, then it waits for approval.
3. **`PLAN`** → **stops for you.** Writes the plan file, then waits. *The last cheap moment to change
   direction.*
4. **`STRATEGY`** → **stops for you.** Branching A/B/C/D, and whether PRs open automatically.
5. **Then it runs by itself, per milestone.** A **milestone agent** is spawned per milestone — under
   strategy C, one per worktree, all in one message — and runs
   `BRANCH → IMPLEMENT → TEST → GATE_A → [E2E] → GATE_B`, returning one typed bundle the orchestrator
   verifies before recording anything. The loop returns to `BRANCH` for the next milestone **without
   opening a PR**.
   - **`GATE_A` executes JavaScript**: changed files grouped by module, four review steps per group,
     groups concurrent. *1,000 files → 85 groups → 340 agents, every file reviewed.*
   - **`E2E` does not exist without a UI** — the node is absent, not skipped.
6. **`CONSOLIDATE`** *(strategy C only)* merges every worktree into one integration branch in
   dependency order, runs the **integrated** suite, removes the worktrees, then a whole-diff `GATE_B`.
7. **One shared tail, every strategy** — `CLOSE_OUT → PR → PR_FINAL_REVIEW → CI → QA → VERDICT → MERGE`.
   **Nothing reaches the main branch until QA has passed**, so the diff a human approves carries its
   own QA verdict, plan updates and regression tests. `MERGE` waits for you; it never merges.
8. **`DONE`** — and it reports **what was skipped, first**.

### Where it stops for you

Six places, and nowhere else.

| Stop | Type | What it needs |
|---|---|---|
| `SPEC` | `approval-after` | Approve the design |
| `PLAN` | `approval-after` | Approve the milestones |
| `STRATEGY` | `choice-after` | Branching, and auto-open-MR |
| `PR` | `confirm-before` | Only if you asked it not to open automatically |
| `MERGE` | `await-external` | Not a question — it waits for the merge |
| `VERDICT` | `escalation` | Only on the second exhausted QA reopen |

That table is **derived from the `human` field on each node contract**, so it cannot drift from them.

### What each gate catches

Not redundant — each sees a defect class the others structurally cannot.

| Gate | Scope | Catches |
|---|---|---|
| `TEST` | one milestone's code | Logic. Breadth lives here — every branch, validation rule, edge case. |
| `GATE_A` | **each file in isolation**, four steps per file | File-local defects: bugs, needless complexity, vulnerabilities. Fans out so files review concurrently. |
| `E2E` | the running UI | Whether a user can actually complete a money path. |
| `GATE_B` | **the whole diff at once** | Cross-file interaction and coherence — invisible to a per-file pass, which is why passing Gate A never exempts a change from Gate B. |
| `CI` | the real pipeline | "Passes locally, red in CI" — environment, ordering and config reality. |
| `QA` | the **deployed, running** app | What a committed suite structurally cannot reach: boot and config reality, authorization abuse across two accounts, injection, serialization leaks. |

### Branching strategy changes the topology

Not a parameter — a different graph.

| | Milestone agents | Where milestones are built | How they converge |
|---|---|---|---|
| **A** one branch, one MR | one at a time | `BRANCH` once, then the loop on that branch | already one branch |
| **B** current branch | one at a time | same as A; `BRANCH` is a no-op | already one branch |
| **C** worktree per milestone | **N at once** | each milestone in **its own git worktree**, independent ones concurrent | `CONSOLIDATE` merges them into one integration branch |
| **D** delegate to `/batch` | none | the graph writes the plan and **stops** at `HANDOFF` | user-run |

QA gates the merge under every strategy, and a `BLOCK` verdict never reaches the main branch.

### Watching a run live

With `sdlc-graph-viewer` installed, the graph starts it at run start: **one server per project**, on a
port derived from the project path, the page polling the state file every second — forever, even after
`DONE`. It renders parallel milestone lanes, and under strategy C highlights the least advanced,
because a run is only as far along as its slowest milestone. It also writes a **self-contained
snapshot** that opens from `file://`. Without the plugin the run proceeds identically; you watch the
state file instead of a page.

## When something goes wrong

**A run that died resumes.** Read the state file, then **re-derive the current node's progress from the
world** — was the branch created? are the tests green? has the PR merged? The filesystem, git and the
host are the truth; the state file only says where to look. `attempts` is never rewound, because
rewinding hands a stuck loop an unlimited budget.

Four states: `RUNNING` · `BLOCKED` (something failed; resumable) · `HANDOFF` (a deliberate stop,
nothing wrong) · `DONE` — **not necessarily clean, so read the ledger first.**

**A run that finished badly gets reviewed.** `/sdlc-graph:graph-run-reviewer` reads a finished or stuck
run, runs the offline auditor over its whole history, triages each finding as a spec defect, a run
defect or an eval gap — and writes the evals the run should have had. It is read-only with respect to
the run.

**The ledger is the load-bearing part.** Any process can claim it ran a step. Only one that records the
*absence* can be trusted when it says it did. Entries are append-only: installing the tool later does
not retroactively pass the gate.

## What's inside

### `sdlc-graph` — the lifecycle graph

| | Invocation | What it does |
|---|---|---|
| **`sdlc-graph`** (skill) | `/sdlc-graph` — command only | Drives a feature end to end through 20 nodes and 40 guarded transitions. Never auto-triggers. |
| **`graph-run-reviewer`** (skill) | `/sdlc-graph:graph-run-reviewer` | Reviews a finished run and writes the evals it should have had. |
| **`sdlc-graph-milestone`** (agent) | never by hand | One per milestone — under strategy C, one per worktree. Returns a typed bundle the orchestrator verifies against git. |

The model is three files — `graph/nodes.md` (node contracts), `graph/edges.md` (the transition table
and its bounds), `graph/state.md` (the run-state schema, write points, resume rules, the ledger) —
plus eight node procedures loaded only when their node runs, and a hook that snapshots every state a
`--trace` run passes through. Full detail:
**[`plugins/sdlc-graph/README.md`](plugins/sdlc-graph/README.md)**, or the illustrated version,
[`docs/artifacts/index.html`](plugins/sdlc-graph/docs/artifacts/index.html).

### `sdlc-graph-viewer` — the run viewer

One skill, `view-run`: a zero-dependency page rendering parallel milestone lanes, live or as a
self-contained snapshot. Read-only with respect to the run, and it holds a **copy of the transition
table** that is checked against the graph's spec on every edit — because a surface that lies about the
graph is worse than no surface.
→ [`plugins/sdlc-graph-viewer/README.md`](plugins/sdlc-graph-viewer/README.md)

### `sdlc-graph-engineering-install` — the method

The generalisation: take a process that has **no** graph — skills, a runbook, a CI config, or a
description — and install one, with its own orchestrator, its own read-only auditor, and its own
executable eval suite. Domain-agnostic; needs no other plugin.

Nine numbered steps, and **step 4 carries the weight**: making the guards *total*. The trap it exists
to catch is that guard sets get written exhaustive over the happy predicates but not over their
product — three independent properties give eight combinations, and the three obvious guards cover
four. It finishes by dry-tracing three scenarios, then emitting those traces as an executable suite,
because a paper trace protects exactly one version of a graph.

**Worked example — the method pointed at somebody else's methodology.** Superpowers (by
[obra/superpowers](https://github.com/obra/superpowers)) as a graph: **21 nodes, 96 guarded edges, 9
bounded cycles, 19 declared human stops** →
[RonMizrahi/superpowers-graph](https://github.com/RonMizrahi/superpowers-graph).

![The spine of the superpowers graph: every node a run passes through, and the two shapes execution can take](docs/assets/superpowers-graph-spine.svg)

→ [`plugins/sdlc-graph-engineering-install/README.md`](plugins/sdlc-graph-engineering-install/README.md)

## Optional tools, and what happens without them

`sdlc-graph` dispatches to other tools at its gates rather than copying them, because a copied reviewer
drifts and then reviews against a stale rulebook. **Every absence is recorded in `skipped_gates[]` and
the run continues** — nothing is ever reported as passed because its tool was missing.

| | Used at | Without it |
|---|---|---|
| `code-review`, `security-review` — built into Claude Code | Gate B, PR review, Gate A step 3 | Ledgered, run continues |
| `pr-review-toolkit:code-reviewer`, `code-simplifier` | Gate A steps 1, 2 and 4 | Ledgered, run continues |
| `claude-md-management:claude-md-improver` | Close-out | Ledgered; do the CLAUDE.md update by hand |
| `nestjs-backend-standards`, `front-react-development` — the author's own private plugins, not installable from here | Implement | Code is written against the project's own conventions |

The eight process skills the nodes came from are **copied in, not depended on**: they ship inside the
plugin as `nodes/<name>-node.md`, trimmed to their graph role. Nothing needs installing.

## How this is tested

Two methods, because neither reaches what the other does.

```bash
python3 plugins/sdlc-graph/skills/sdlc-graph/evals/run_all.py          # 9 suites
python3 plugins/sdlc-graph-viewer/skills/view-run/evals/run_all.py     # 8 suites
```

**Deterministic** — spec consistency and its negative controls, scripted graph walks covering every
edge and every node, the offline auditor against its own selftest, and the viewer's copy of the
transition table against the spec. Dependency-free Python, about 3.6 seconds, and a repo hook runs them
on **every edit** to either plugin: editing the graph fires the viewer's suite too, because a guard
edited in `edges.md` is exactly what makes the viewer stale.

**Executing** — scenarios driven by a real orchestrator against a scripted agent, and tests with a real
milestone agent. These need a model and real minutes, so they run on demand, by a human who decided to
spend them: `python3 .claude/hooks/eval-receipts.py --list`.

A push carrying a red deterministic suite is blocked before it leaves the machine.

## Philosophy

- **A guard that cannot fire is a lie.** Guards are total: exactly one matches, and zero halts the run.
- **A check that cannot fail is not evidence.** Every suite ships a negative control — a deliberately
  broken input the checker *must* reject.
- **Record the absence.** A gate whose tool was missing is ledgered, never quietly passed.
- **Derive, never duplicate.** The moment a summary table and the node contracts both state the six
  stops, they can disagree — and the summary is what people read.
- **Put the irreversible node last.** A verification step placed after the point of no return still
  runs, still reports honestly, and is still worthless.
- **Report, never gate.** The auditor is read-only; a monitor that halted runs would become a seventh
  human stop right after you declared the list complete.
- **Verify the worker's claim against the world.** A returned bundle is checked against git and a
  re-run suite before a transition is written.

## Contributing

Issues and PRs welcome. Three things make a change easy to accept:

1. **Say which failure it prevents.** Every rule here exists because a real graph broke without it —
   `references/failure-modes.md` is the running list, and a new rule belongs beside a new entry.
2. **A change is not done until it adds the eval that would have caught its absence**, and that eval is
   not done until a deliberately broken input makes it fail.
3. **`main` is PR-only**, and every change bumps the plugin `version` in *both* manifests, so installed
   users actually receive it.

```bash
git config core.hooksPath .githooks        # once per clone — arms the push gate
claude plugin validate ./plugins/<plugin> --strict && claude plugin validate .
```

Skill authoring follows the open [Agent Skills](https://code.claude.com/docs/en/skills) spec. The rules
that bind a change to this repo are in [`CLAUDE.md`](CLAUDE.md); the rules that bind a change to the
graph are in [`plugins/sdlc-graph/docs/EDITING.md`](plugins/sdlc-graph/docs/EDITING.md), and that file
comes first.

## Updating

`/plugin update <name>@sdlc-graph-engineering`, or whatever your harness does for plugin updates.

**Run state changed shape at 1.0.0 and there is no migration**: a run written by 0.11.1 cannot be
resumed by 1.0.0 or later — the version check is an unconditional halt, because a half-understood state
file drives a graph into transitions nobody wrote. Finish in-flight runs before upgrading.

## Credits

By [Ron Mizrahi](https://github.com/RonMizrahi).

## License

MIT — see [LICENSE](LICENSE).

Two node procedures in `sdlc-graph` derive from [obra/superpowers](https://github.com/obra/superpowers)
(MIT, © 2025 Jesse Vincent) and carry its notice, as does the Superpowers diagram above: see
[THIRD-PARTY-NOTICES.md](THIRD-PARTY-NOTICES.md). Everything else here is first-party.
