# Graph Engineering — Install

Installs **graph engineering** into a project that has none.

Point it at whatever process you already have — a set of skills, a runbook, a CI config, or just a
description — and it produces a **guarded graph** for that process: typed nodes, total exit guards,
bounded retry loops, a durable run-state file, a ledger of every step that could not run, the
orchestrator that walks it, and an auditor that checks it.

**Domain-agnostic and self-contained.** It needs no other plugin installed and assumes nothing about
software delivery. Its worked examples deliberately use a document-review pipeline.

## Why

A prose process fails in ways prose cannot describe:

| | |
|---|---|
| **No run state** | Nothing records where it got to. An interruption restarts from guesswork. |
| **Unevaluated conditions** | "retry if it's worth retrying" is a condition nothing checks. |
| **Unbounded loops** | A retry with no declared limit runs until something else stops it. |
| **No record of what was skipped** | "Never claim a step you didn't run" is unenforceable if nothing records the absence. |

## What it produces

```
<target>/
├── agents/<graph>-monitor.md      the auditor — read-only, reports, never gates
└── skills/<graph>/
    ├── SKILL.md                   the orchestrator: dispatch loop, rules, human stops
    └── references/
        ├── nodes.md               node contracts + diagrams
        ├── edges.md               the transition table, bounds, terminal states
        └── state.md               run-state schema, write points, resume rules
```

## The method

Nine numbered steps and seven sub-steps, and **step 4 carries the weight** — making the guards
*total*. The rest is drawing boxes.

The trap it names: guard sets get written exhaustive over the **happy predicates** but not over their
**product**. A result with three independent properties has eight combinations; the three obvious
guards cover four. Reading a spec top-to-bottom never reveals the gap, because each guard looks
correct in isolation.

It finishes by **dry-tracing three scenarios** — happy path, a retry that recovers, a retry that
exhausts its bound — because an untraced graph looks identical to a traced one and fails at runtime on
a path nobody walked.

## Skills

| Skill | Invocation |
|---|---|
| `sdlc-graph-engineering-install` | `sdlc-graph-engineering-install:sdlc-graph-engineering-install` |

## References it ships

- **`templates.md`** — skeletons for all four files, with the fields that matter already present
  rather than left to be remembered: `exits`, typed human stops, per-item attempt keys, the
  append-only ledger.
- **`failure-modes.md`** — the **sixteen** ways these graphs break at runtime, each with its
  published name where one exists so a defect is searchable rather than folkloric: workflow-net
  **soundness**, **sequence manipulation** / **MAST FM-3.2**, ping-pong livelock, the re-execution
  hazard, silent structural skip, **MAST FM-1.4**, **OWASP ASI01**, the zombie-task stall, the gate
  that runs after the point of no return, the surface that lies about the graph, the stop that fires
  where the human said *continue*, and the obligation whose trigger is a judgement call. Plus a
  *what not to monitor* list, because a checker that fires constantly gets ignored.
- **`evals.md`** — how to turn the dry traces into a suite that still protects the graph after it
  moves.

## Related

`sdlc-graph`, which ships beside this plugin, is a graph already built, for software delivery — and
the worked reference for everything here: total guards, per-item attempt keys, a skipped-gate ledger,
a run directory, a generated observability surface with a drift checker. This plugin is for
installing a **new** graph for a process that has none. Neither requires the other.
