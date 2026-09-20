# Caps — what each one is, and which file sets it

Every limit this plugin states, what it bounds, and the file that owns the value. **The spec file is
the only place a value is set**; this page is where you find out which one to open.

---

## 1. What reaches the orchestrator

The orchestrator holds the whole run, so these are the caps that decide whether it can.

**The first line of defence is not a number.** Seven nodes — `BRANCH`, `IMPLEMENT`, `TEST`, `GATE_A`,
`E2E`, `GATE_B` and the `DEBUG` round-trips they call — execute inside a milestone agent. Full test
output, whole diffs, review findings and CI logs never enter the orchestrator's context at all. The
caps below bound what is left.

| Cap | Value | What it bounds | Set in |
|---|---|---|---|
| **Brief** | **≤ 4 KB** | Orchestrator → milestone agent. Ids, the milestone record, fenced plan steps, remaining budgets, the return schema. | `subagents/workflow-dispatch.md` § *The brief* |
| **`MILESTONE_BUNDLE`** | **≤ 24 KB** (≈ 6,800 tokens) | Milestone agent → orchestrator. The only thing the orchestrator reads of a milestone. | `subagents/workflow-dispatch.md` § *`MILESTONE_BUNDLE`* |
| **Return-gate output** | **≤ 20 lines** per milestone | Command output the orchestrator may read running R0–R13. Redirect everything; read an exit code, a count, or a tail line. | `subagents/workflow-dispatch.md` § *The return gate*; `SKILL.md` |
| **Journal tier 1 — `headline`** | **≤ 200 chars** per line | Pushed the moment it is written, so it is the only part of the journal that costs context unconditionally. | `subagents/workflow-dispatch.md` § *The milestone journal* |
| **Journal tier 2 — `detail`** | **1–2k tokens** per line | Pulled on demand — before briefing a dependent agent, at `CLOSE_OUT`, or when supervising. | same section |
| **`history[]` backstop** | **`length > 250` ⟹ `BLOCKED`** | Runaway guard above every per-cycle bound. | `graph/state.md` § `history[]` |

> **Why the bundle is 24 KB.** It is the schema's own worst case plus headroom: `trace` at
> `maxItems 40` is ≈ 12.8 KB alone, and `commits: sha40[60]` adds ≈ 2.6 KB. It was 8 KB, which was
> **smaller than the field caps below** — an agent filling the schema in correctly could not fit, and
> a bundle short of its own evidence is what `R0` rejects, costing a whole milestone.
>
> **Precedence: the field caps win over the byte figure.** A bundle carrying all its evidence ships
> long; it never truncates to fit.

---

## 2. Field caps — inside the state file and the bundle

| Field | Cap | Enforced by |
|---|---|---|
| `history[].observation` | **200 chars** | `R11` (the agent's) · `O3` (the orchestrator's) |
| `history[].verified` | **300 chars** | `O3` |
| `milestones[].delivered` | **600 chars** | — |
| `MILESTONE_BUNDLE.notes` | **600 chars** | `R0` |
| `trace[]` | **maxItems 40** | `R2` |
| `evidence.commits[]` | **60 shas**, full 40-char | `R4`, `R12` |
| `evidence.tests.failures[]` | **20** | `R0` |
| `preflight[].method` | **120 chars** | `R9` |
| journal `detail.summary[]` | **2–3 lines, 200 chars each** | — |
| journal `agent_done.purpose` | **120 chars** | — |

Field caps live in `graph/state.md` (state fields) and `subagents/workflow-dispatch.md` (bundle
fields).

---

## 3. Loop bounds — how many times a node may be re-entered

**`graph/edges.md` § Loop bounds is authoritative and is the only list.** Per-node values live in
each contract's **max attempts** row in `graph/nodes.md`.

| Cycle | Counter key | Bound |
|---|---|---|
| `TEST` ↔ `DEBUG` | `TEST:<id>` | 3 |
| `E2E` ↔ `DEBUG` | `E2E:<id>` | 3 |
| `CONSOLIDATE` ↔ `DEBUG` | `CONSOLIDATE` | 3 |
| `GATE_A` ↻ / ↔ `DEBUG` | `GATE_A:<id>` | 2 — proceeds on exhaustion, never `BLOCKED` |
| `GATE_B` ↔ `DEBUG` | `GATE_B:<id>` | 2 |
| `GATE_A` dispatch retry | `GATE_A-dispatch:<id>` | 1 — workflow error only |
| Milestone-agent re-spawn | `MILESTONE-dispatch:<id>` | 1 — agent death only |
| `VERDICT` → `BRANCH` reopen | `QA` | 2, then `BLOCKED` for a human |
| `CI` | — | 15-minute budget + a 2-same-error guard |

Counters are **keyed per milestone and never reset**; a resume inherits them. A `DEBUG` round-trip is
bounded by its **caller's** max attempts.

---

## 4. Fan-out and concurrency

| Cap | Value | Set in |
|---|---|---|
| Files per review agent (`filesPerGroup`) | **12** — a quality limit; group *count* is uncapped | `subagents/workflow-dispatch.md` § *Grouping*, `workflows/gate-a.workflow.js` |
| Concurrent milestone agents under strategy C | **5** — the sixth waits for a slot | `subagents/workflow-dispatch.md` § *Strategy C* |
| Agents per workflow script lifetime | **1000** — the Workflow runtime's cap, not ours | same |

These cost the **subagent's** context and wall-clock, not the orchestrator's — except concurrency,
which sets how many bundles can land in one window.

---

## 5. Liveness

| Setting | Value | Set in |
|---|---|---|
| Journal `heartbeat` interval | **~90s** inside a long node | `subagents/workflow-dispatch.md` § *The milestone journal* |
| Silence threshold — `seen_at` older than *X* ⟹ agent dead or hung | **not set** | `SKILL.md` § *Watch for silence*, `graph/state.md` § `progress.seen_at` |

Both call sites route liveness off "older than the heartbeat window", and no file states that window.

---

*Change a number in the spec file that owns it; this page is a copy, and a stale row here is a stale
row, not a broken build.*
