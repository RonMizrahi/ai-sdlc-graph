<!-- copied-from: the standalone `plan-guidelines` skill @ v0.5.0 — a separate, unbundled skill of the author's; this copy is graph-scoped and meant to diverge -->
<!-- trimmed: Phase 2 REMOVED IN FULL — Phase 2 *is* the milestone loop, and the graph drives it.
     Running both would double-drive the loop: two branch-creations, two MR flows per milestone.
     Its individual steps survive as the graph nodes BRANCH / IMPLEMENT / TEST / GATE_A / PR.
     Also removed: standalone trigger phrases, the "load this skill BEFORE planning" framing, and
     the Phase 3 dependency warning (now the CLOSE_OUT node's `requires`). -->
<!-- diverged: § CLOSE_OUT ordering and the is_fix branch rule. The standalone keeps "all milestone
     branches merged, then QA" (Phase 4 step 1). The graph splits it by branching strategy: under
     A/B, close-out and QA run BEFORE the merge so QA gates it; under C the standalone's ordering
     still holds. Decided with the human on 2026-07-29 — node copy only, standalone unchanged.
     This is a deliberate divergence, not drift. Do not "sync" it away. -->

# Node: plan-guidelines

Serves **four** graph nodes. Each section below is a separate node contract — read only the one for
the node you are executing.

| Graph node | Section | Loaded by |
|---|---|---|
| `PLAN` | § PLAN | orchestrator |
| `STRATEGY` | § STRATEGY | orchestrator |
| `BRANCH` | § BRANCH | **milestone agent** |
| `CLOSE_OUT` | § CLOSE_OUT | orchestrator |

> **The milestone loop is NOT in this file.** The source skill's Phase 2 defined a
> branch → implement → test → gates → MR flow per milestone. That flow *is* the graph
> (`edges.md`, the milestone-loop table). If you find yourself following a loop described here, stop — you are
> double-driving it.

---

## § PLAN

**Cardinal rule: the plan is saved to a `.md` file BEFORE any implementation begins.** Write it, save
it, then build. `STRATEGY` will not accept a plan held only in conversation.

### Structure

A plan is **steps** grouped into **milestones**.

- **Steps** — small, granular implementation units ("create auth repository", "add middleware").
- **Milestones** — groupings of related steps forming one complete piece of functionality.

Trivial changes that don't warrant a milestone (a config tweak, a typo) are committed directly; they
do not enter the graph.

### Every milestone MUST include

Bake these in as explicit steps. A milestone missing either is not a valid milestone:

1. **Test steps** — per `testing-standards-node.md`. Unit tests alongside each implementation step,
   plus integration steps per endpoint, plus e2e journeys **only if the project has a UI**.
2. **A quality-gate step** — Gate A before e2e, Gate B before the PR.

> **Write test steps in, and do not worry that `IMPLEMENT` will owe them.** It does not: `IMPLEMENT`
> and `TEST` **partition** `steps[]` between them by deliverable, and each half is collected by its own
> guard — 9 and 10 (`nodes.md` § *Which steps `IMPLEMENT` owns*). The alternative was to forbid test
> files here, which would have deleted the requirement above to protect a guard's wording. **A step
> naming the test file it will add is the clearest kind of plan step there is**, and it is the one that
> made the defect visible: a real run planned `test/unit/token-store.test.js`, committed it at `TEST`
> exactly as prescribed, and left a guard reading *"all milestone steps committed"* false at
> `IMPLEMENT → TEST` on a milestone where nothing at all had gone wrong.

### Four phases: lock, draft, approve, hand off

**1 — `EnterPlanMode`.** Do this *before* exploring. It needs the user's consent, and it turns on the
**edit lock**: the tool layer will refuse to write code for as long as you are in plan mode. That is
the point. If the user declines, fall through to *Without plan mode* below.

**2 — Draft.** Explore, decide the milestones and their dependencies, and write the plan to the plan
file plan mode gives you.

**3 — `ExitPlanMode`.** It reads that file and asks the user to approve. **Do not also ask in prose** —
`ExitPlanMode` *is* the request. Revisions rewrite the file in place and re-present; unbounded, because
this is a conversation, not a retry.

**4 — Hand off.** Once approved, copy the plan to
`docs/<subject>/<name>-<DD>-<MM>-<YYYY>-plan.md`, set `plan_path` to it, and stop using the harness
file. **One direction, one moment.** From here `docs/plans/…` is the only authoritative plan — keeping
both alive would recreate exactly the twin drift this graph exists to prevent.

#### Without plan mode

If the user declines to enter it, write the plan directly, present it, and wait for approval as
before — **and append a `skipped_gates[]` entry recording that the edit lock did not apply.** The run
continues; it is simply one guarantee weaker, and the ledger says so rather than the run pretending
otherwise.

### Save it, then get it approved

This is the **last cheap moment to change direction.** After `STRATEGY` commits to a branching shape
the loop starts, and a correction then costs branches, PRs and CI runs. A plan that was merely *seen*
while the user answered a different question has not been approved.

### Contract

| | |
|---|---|
| **inputs** | `spec_path`, `context` |
| **emits** | `plan_path`; `milestones[]` — each with `id` (number), `name`, `deps` (number[]), `steps` (string[]), and **`is_fix: false`** |
| **exit guards** | revisions requested → `PLAN` (rewrite in place, unbounded) · plan file on disk **and** every milestone has its required steps **and** **user approved** → `STRATEGY` |
| **on failure** | cannot decompose → `BLOCKED` + `blocked` naming what could not be split |
| **max attempts** | revision unbounded — user-driven, like `SPEC` |
| **requires** | — |
| **interactive** | **yes** |

> **`is_fix: false` must be seeded on every milestone**, not left absent. `BRANCH` and `GATE_B` read
> it unconditionally; an absent field is a different thing from `false`.

> **`deps` must be present and an array on every milestone**, even when empty. A missing `deps` is
> refused by the strategy-C fan-out rather than assumed independent — see
> `workflow-dispatch.md`.

---

## § STRATEGY

Present the milestone list **and its dependency graph** to the user, then ask for two decisions.
**Never infer either.**

### 1. Branching strategy

- **A — one side branch for the whole plan.** Every milestone commits onto it; one MR at the end.
  Sequential. *(recommended default)*
- **B — current branch.** Only when it is already a safe working branch, **never a protected one**.
- **C — branch per milestone.** Each milestone gets its own branch and worktree; `CONSOLIDATE` merges
  them into one integration branch, so the run still opens **one** MR. **The only strategy that
  unlocks parallelism** — independent milestones run concurrently, one milestone agent each.
  Dependent milestones stay sequential: branch each off its parent and run that chain in order.
- **D — delegate to `/batch`.** For a large, broadly-independent change. **A skill cannot invoke
  `/batch`** — it is a user command. So this is a hand-off: write the plan, tell the user to run
  `/batch` and point it at these guidelines, and stop at `status: HANDOFF`.

**Parallelise only milestones with zero shared state.** Running dependent milestones concurrently
causes merge conflicts and broken integration.

### 2. `auto_open_mr`

Ask whether the `PR` node may open the pull request automatically, or must pause for confirmation
first.

> **This settles a real conflict between two source skills.** `plan-guidelines` said *ask for
> confirmation before creating the MR*; `pr-mr-prepare` said *open it automatically, don't pause*.
> Asking once here means the loop is never interrupted to **decide** it — though `PR` still honours a
> `false`.

### Validate the dependency graph

Every milestone's `deps` must reference real milestone ids, and the graph must be **acyclic**. A cycle
is a planning defect, not something to work around.

### Seed the task list

One task per milestone, from `milestones[]`. See `state.md` § Task-list projection — it is a
projection, never an input.

### Contract

| | |
|---|---|
| **inputs** | `plan_path`, `milestones[]` |
| **emits** | `context.branching`, `context.auto_open_mr`, **`cursor.milestone`** (first milestone with no unmet `deps`), task list seeded |
| **exit guards** | `branching ∈ {A,B,C}` **and** deps acyclic → `BRANCH` · `branching == D` → `status: HANDOFF` |
| **on failure** | cyclic or dangling deps → `BLOCKED` + `blocked` naming the cycle |
| **max attempts** | 1 |
| **requires** | — |
| **interactive** | **yes** — both decisions are the user's |

> **`cursor.milestone` is initialised here.** Nothing before this node writes it, and `BRANCH` reads
> it — without this the loop cannot start.

---

## § BRANCH

> **You are a milestone agent.** You do not have the run's state file and **you may never write it**.
> You evaluate no guard and quote no guard text. Report what happened; the orchestrator records it
> and decides where the run goes next.

1. **Resolve the parent branch.** `context.main_branch` for an independent milestone; **the parent
   milestone's branch** for a dependent one. Note the dependency in the eventual MR description.
2. **Create** `<task-id>/<short-description>` — the Jira/issue id as prefix if the milestone has one,
   otherwise the milestone number (`PROJ-1234/add-auth-endpoints`, `milestone-2/auth-system`).

### Strategy-dependent behaviour

| Strategy | Behaviour |
|---|---|
| **A** | Create the run branch on **first** entry; **no-op** on every later milestone. |
| **B** | **No-op throughout** — stay on the current branch. Refuse if it is protected. |
| **C** | A fresh branch per milestone. One branch per milestone, never combined. |

**Under strategy C, a milestone with `is_fix == true` gets its own fresh branch off `main_branch`** —
by reopen time the original branch is merged and gone. **Under A and B it does not**: QA runs before
the merge there, so the run branch is still open when `VERDICT` reopens, and the fix stays on it and
pushes to the already-open PR.

### Contract

| | |
|---|---|
| **inputs** | `cursor.milestone`, `milestones[]`, `context.{branching,main_branch}` |
| **emits** | `milestones[cursor].branch`, `milestones[cursor].node = BRANCH` |
| **exit guard** | branch checked out → `IMPLEMENT` |
| **on failure** | protected branch, or a dirty tree → `BLOCKED` + `blocked` |
| **max attempts** | 1 |
| **requires** | `git` |

> **Never create a branch on a protected branch, and never commit to one.** `main`, `master`,
> `develop` are off limits under every strategy.

---

## § CLOSE_OUT

Runs once. **Under C**, after every milestone is merged. **Under A and B**, after the last milestone's
`GATE_B` and *before* the PR — so the plan-file updates and `CLAUDE.md` changes below land inside the
reviewed diff rather than being committed past the only review gate in the run.

Turns the plan file into a permanent record and leaves the project documented for future sessions.

### 1. Update the plan file

- **Milestone/step statuses** — `[DONE]` / `[SKIPPED]` / `[DEFERRED]`, with a brief reason for each
  skip or deferral.
- **Key decisions** — architectural or implementation choices that deviated from the original plan.
- **Verification results** — which tests ran and their outcomes.
- **Every `skipped_gates[]` entry**, copied in verbatim. This is not optional: the ledger is the only
  durable record that a gate could not run, and a plan that omits it reads as a clean run.

### 2. Update the project `CLAUDE.md`

Only **major structural** changes, so future sessions are onboarded without re-reading the plan:
new/removed source directories, new commands, new architectural patterns, changed dependencies or
environment requirements.

- **Keep it under 100 lines.** Compress or drop stale sections if it is approaching the limit.
- **Don't duplicate plan content** — `CLAUDE.md` describes current state, not history. Link to the
  plan for detail.
- **Use progressive disclosure** — point at subdirectory `CLAUDE.md` files or `docs/`.

### 3. Run the improver

Live-dispatch **`claude-md-management:claude-md-improver`** to validate the edit. **If it is absent,
append a `skipped_gates[]` entry, do the update by hand, and say the improver was skipped** — never
report this step as done when the tool was missing.

### 4. Assemble for QA and complete `context.qa_env`

The `QA` node probes the **real running app** and reads its inputs **only** from `context.qa_env`,
never from conversation — so a resumed run still knows how to reach the app. Fill in anything `INTAKE`
could not discover:

`run_instructions` · `api_base_url` · `web_base_url` · `api_docs` · `seed` · **`identities` (at least
two distinct users/roles — required for authorization probing)**

> **Identifiers only.** No passwords, tokens, or credentialed connection strings — this goes into a
> state file that is **committed to the repo**. See `state.md` § The state file is committed.

### Contract

| | |
|---|---|
| **inputs** | `plan_path`, `milestones[]`, `skipped_gates[]` |
| **emits** | plan file updated, `context.qa_env` completed, `status` |
| **exit guards** | → `PR` — **unconditional, every strategy**; the work still has to reach `main_branch` |
| **on failure** | — |
| **max attempts** | 1 |
| **requires** | `claude-md-management:claude-md-improver` — **absent → `skipped_gates[]`** |

> **There is no `→ DONE` shortcut here any more.** The retired `nothing runnable → DONE` exit would
> strand the branch unmerged now that close-out runs *before* the PR. The "nothing runnable, skip QA"
> decision lives at `CI` (edge 22b), once the PR is open — and taking it must still be stated out
> loud, because a silent QA skip is how an unverified change ships.
