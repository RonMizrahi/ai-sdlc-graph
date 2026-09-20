<!-- copied-from: the standalone `code-quality-pipeline` skill @ v0.5.0 — a separate, unbundled skill of the author's; this copy is graph-scoped and meant to diverge -->
<!-- trimmed: Gate A's four IN-SKILL WAVES REMOVED — the node no longer runs the pipeline itself, it
     DISPATCHES to `workflows/gate-a.workflow.js`, which owns the fan-out, the grouping and the
     step order. Running the waves in-skill as well would double-review every file and produce two
     conflicting verdicts for one node. The four steps survive as the script's per-group sequence;
     what stays here is the dispatch contract and the result → guard mapping.
     Also removed: the "Where each gate fits in the milestone flow" section — the graph defines
     placement now (`edges.md`, edges 12/13/14/18/18b/19), and a second flow diagram here would be a
     rival source of truth; standalone trigger phrases; and the "Use this skill WHENEVER…" framing.
     Gate B is kept essentially intact — it is still a holistic review of the whole diff vs. main —
     with its node contract added. -->

# Node: code-quality-pipeline

Serves **two** graph nodes. Each section below is a separate node contract — read only the one for
the node you are executing.

| Graph node | Section | Loaded by |
|---|---|---|
| `GATE_A` | § GATE_A | **milestone agent** |
| `GATE_B` | § GATE_B | **milestone agent** |

> **Both gates always run.** `GATE_A` reviews each changed file (or logical module) in isolation;
> `GATE_B` reviews the entire diff against `main_branch` as one change set. **Passing Gate A never
> exempts a change from Gate B** — they catch different defect classes: file-local vs. cross-file.
> Cross-file interactions and overall coherence are structurally invisible to a per-file pass.

> **A missing tool is never a pass.** Every reviewer listed under a node's `requires` that fails to
> resolve gets its **own `skipped_gates[]` entry**, and the gate **may never be recorded as passed**.
> Say so out loud in the run report. `CLOSE_OUT` copies the ledger into the plan file verbatim.

---

## § GATE_A

> **You are a milestone agent.** You do not have the run's state file and **you may never write it**.
> You evaluate no guard and quote no guard text. Report what happened; the orchestrator records it
> and decides where the run goes next.

Runs after `TEST` reports unit **and** integration green. If anything is red you are at the wrong
node — the pipeline assumes working code.

### Dispatch, don't review

`GATE_A` does not run the four review steps itself. It calls the workflow script once and reads the
result:

```js
Workflow({
  scriptPath: "${CLAUDE_PLUGIN_ROOT}/skills/sdlc-graph/workflows/gate-a.workflow.js",
  args: {
    files: ["src/auth/auth.service.ts", "src/auth/auth.controller.ts"],
    milestone: 2,
    tools: { reviewer: true, simplifier: false, security: true },
    filesPerGroup: 12
  }
})
```

| Arg | What to pass |
|---|---|
| `files` | The changed/created files for this milestone, **vs. its branch point** — an **array** of repo-relative paths. A stringified list, an absolute path, or any `..` segment is refused by the script. |
| `milestone` | `cursor.milestone`. Labelling only. |
| `tools` | **The preflight result** — one boolean per reviewer. `false` means the tool was absent, so its step is skipped and reported. **Omitting `tools` sets `tools_asserted: false`**, and a clean gate must never be recorded on an unverified preflight. |
| `filesPerGroup` | **Files per agent**; default 12. A quality limit — group **count** derives from it and is not capped. The script does not read `maxGroups`; concurrency is the Workflow runtime's own cap. |

Inside each group the script runs the four steps in strict order — **Code Review → Simplification →
Security Review → Final Review** — applying each step's findings before the next. Groups run
concurrently; files are grouped by directory as "logical modules" so agent count stays bounded. See
`workflow-dispatch.md` for the grouping rules and coverage cap.

### When there is no `Workflow` tool — mimic the script

**Always attempt the `Workflow` call first.** It is declared on you, and it may one day be there;
an agent that stopped trying would never notice the day it works.

In practice it is **absent in a subagent session** — observed on every milestone of every real run so
far — so treat the fallback as the normal path, and make it a **faithful replication of the script**
rather than an ad-hoc review. **Read `workflows/gate-a.workflow.js`. It is the specification**, and
these are the parts you must reproduce:

1. **Group by directory** — bucket the changed files by `dirname`; each bucket is one "logical
   module", so the reviewer sees a service, its controller and its tests together.
2. **Split, never truncate** — a module larger than `filesPerGroup` (default **12**) becomes
   `ceil(n/12)` groups labelled `dir (i/parts)`.
3. **Coalesce small siblings** repeatedly, while the merged result still fits `filesPerGroup`. Never
   fold a large module into another group's context.
4. **Sort groups by label**, so the same diff always produces the same groups.
5. **Four steps per group, strictly in order, each applying its findings before the next:** Code
   Review (`pr-review-toolkit:code-reviewer`, write-capable) → Simplification
   (`code-simplifier:code-simplifier`) → Security Review (`security-review`) → Final Review
   (`pr-review-toolkit:code-reviewer`).
6. **Groups run concurrently; the four steps inside a group never do.** Spawn the groups together in
   one message. A sequential mimic is correct but throws away the only thing the script was for.
7. **A dead step agent is not an absent tool** — record it per `(step, group)`, do not count that
   group complete, and set `tools_asserted: false`.
8. **Journal each step agent** — `agent_spawn` before you wait on it, `agent_done` when it returns,
   per `workflow-dispatch.md` § *Every subagent you spawn gets two lines*. This is the only dispatch
   where the fan-out is yours to record; without it, forty agents report as one sentence.

Then report **`evidence.gate_a.dispatch = "mimic"`** with `run_id: null` and **real**
`groups_completed` / `groups_total`.

Three things you must not do:

- **Never invent a `run_id`.** There was no run. A runId the journal does not know is read as a
  fabricated bundle.
- **Never report `groups_completed: 0` under `mimic`.** It claims you grouped and then reports no
  groups — that is fabrication, and it rejects.
- **Never report `dispatch: "direct"` when you could have mimicked.** `direct` means *no grouping
  happened at all*; it reports `groups_*: null`, which leaves the orchestrator with no coverage
  arithmetic whatsoever. Use it only when you genuinely cannot group — no `Agent` tool available.

None of this is a `skipped_gates_proposed[]` entry: **the gate ran.** And nothing is charged to
`GATE_A-dispatch` — that budget is for a script that crashed, not for a script that was never called.

### Map the result onto the guards

The script returns:

```js
{ clean, rerun_recommended, rerun_reasons, findings, skipped_steps, tools_asserted,
  applied, uncovered, groups_completed, groups_total, files_reviewed, files_supplied, groups }
```

**You are not choosing an edge here.** Return the whole result object in `evidence.gate_a` and let
the orchestrator route on it. What each field means for *your* next move inside the itinerary:

| Result | What it means here |
|---|---|
| `rerun_recommended: false` | This gate is done. Continue along your itinerary — `E2E` next, or `GATE_B`. **This is the signal, not `clean`.** |
| `rerun_recommended: true` **and** `GATE_A` budget remaining | Re-enter `GATE_A` once, and record the extra attempt in `attempt_counts`. |
| `rerun_recommended: true` **and** budget spent | **Continue anyway**, with the findings reported. `GATE_A` is the one cycle that does not block on exhaustion. |
| `skipped_steps` non-empty | One `skipped_gates_proposed[]` entry **per step**. **Not a pass** — but not a stop either; the run proceeds and the orchestrator ledgers it. |
| `uncovered` non-empty | Those files were **not** reviewed. Report it; never treat it as a pass. Splitting the milestone is a planning decision, not yours. |
| `groups_completed < groups_total` | A group died and reviewed nothing. Report the counts exactly — the orchestrator distinguishes this from a real gate pass. |
| `groups_completed == 0`, no result, no edits | The **dispatch** failed; the gate did not run. Report it as such — it is counted against a different budget than a findings re-run. **Only under `dispatch: "workflow"`.** Under `direct` there were never any groups, and reporting `0` there charges a bound for a dispatcher that never existed. |
| `tools_asserted: false` | No preflight was asserted, so nothing here may be reported as a gate that ran. Re-run with the preflight result. |
| `applied` | Return it as-is, and do not rely on it — it has come back empty in every observed run while the steps edited files. The orchestrator cross-checks it against `git diff --name-only`. |

**Never route on `clean`.** It is also false when a tool was absent or coverage fell short, which is
reporting, not routing — and routing on it deadlocked this node twice.

**`rerun_recommended` counts only `bug`, `security` and `regression` findings.** A `quality` or `nit`
finding never re-runs the gate — that is how a quality pipeline turns into an infinite polish loop.

### Re-verify the suite before leaving

Steps 2 and 3 **changed code that was green when the gate started.** Re-run unit + integration after
the script returns and its `applied` fixes are in place.

A red suite here routes to `DEBUG` with `debug.return_to = GATE_A` (edges 12b/12c, 2 attempts) —
symmetric with § GATE_B. **Without this the break would match no guard at all** and halt the run, which
is exactly why those edges exist.

### Contract

| | |
|---|---|
| **inputs** | `cursor.milestone`, changed files vs. the milestone's branch point |
| **emits** | `milestones[cursor].node = GATE_A`, `attempts["GATE_A:<id>"]`, `debug.return_to = GATE_A` on a red suite, `skipped_gates[]` for any absent reviewer |
| **exit guards** | `step-4 found a real bug/security/regression AND attempts < 2 → GATE_A` · `(clean OR re-run budget spent) AND context.has_ui → E2E` · `(clean OR re-run budget spent) AND NOT context.has_ui → GATE_B` |
| **on failure** | unit/integration red after the gate's own edits → `DEBUG` (`debug.return_to = GATE_A`, **2** attempts, edges 12b/12c) · workflow error → retry once, then `BLOCKED` |
| **max attempts** | **2** — one re-run, and **only** for a genuine bug/security/regression finding. A style nit never re-runs the gate. |
| **requires** | `pr-review-toolkit:code-reviewer` (steps 1 & 4) · `code-simplifier` (step 2) · `security-review` (step 3) — **each absent → its own `skipped_gates[]` entry** |

> **Exhaustion here does not block.** After the single re-run, remaining findings are documented and
> the run moves on to `E2E`/`GATE_B`, where the holistic gate gets its own look. That is why guards 2
> and 3 read `clean OR re-run budget spent` — without the second clause a genuine finding at
> `attempts == 2` would match no guard at all and halt the graph.

---

## § GATE_B

> **You are a milestone agent.** You do not have the run's state file and **you may never write it**.
> You evaluate no guard and quote no guard text. Report what happened; the orchestrator records it
> and decides where the run goes next.

The final gate before code leaves the branch: a **holistic review of the entire diff against
`main_branch`**, looking at the complete change set as a whole rather than file-by-file.

1. **Run the holistic review** — dispatch the **built-in `code-review`** skill with an explicit range:
   `code-review <main_branch>..<branch> high`. It reads a **local diff** and needs **no open PR**, so do
   NOT pass `--comment`. **Do not reach for `/code-review:code-review` here** — that plugin command is
   `gh pr`-only and cannot read a local diff, so it can never run at this node, which always precedes
   `PR`. It has its own node, `PR_FINAL_REVIEW`, once the PR is open.
2. **Fix every issue found.** Don't hand the PR to reviewers with known findings — catching them
   here is the entire point of the gate.
3. **Re-run unit + integration after the fixes** (`yarn` or `npm`):
   ```bash
   yarn test:unit          # or: npm run test:unit
   yarn test:integration   # or: npm run test:integration
   ```
   Red after the review fixes → `DEBUG` with `debug.return_to = GATE_B`, not onward.
4. **Take the exit guard** once the diff is clean and both suites are green.

### Contract

| | |
|---|---|
| **inputs** | the whole diff of the milestone branch vs. `main_branch` |
| **emits** | `milestones[cursor].node = GATE_B`, `attempts["GATE_B:<id>"]`, `debug.return_to = GATE_B` on failure, `skipped_gates[]` if the reviewer is absent |
| **exit guards** | **Not yours.** `GATE_B` is where a milestone agent's itinerary ends: its exits (18 / 18c / 18d) read `integration.branch`, `context.branching` and whether a milestone remains — run-level state a milestone agent is deliberately not given. Run the node body, record the transition **into** `GATE_B`, and return. `edges.md` is the authoritative rendering of what happens next. |
| **on failure** | tests red after fixes → `DEBUG` (`debug.return_to = GATE_B`) |
| **max attempts** | 2 |
| **requires** | the **built-in `code-review`** skill, invoked as `code-review <main_branch>..<branch> high` (no PR needed, no `--comment`) — **absent → `skipped_gates[]`** |

> **Gate B never leads straight to a PR.** Under A and B with milestones remaining it loops back to
> `BRANCH` (a no-op for B); on the last milestone it goes to `CLOSE_OUT`, and the single PR comes
> after that. Under C the last milestone goes to `CONSOLIDATE` first and comes *back* through
> `GATE_B` for the integration pass. `GATE_B → PR` does not exist, and edge 18b is retired — see
> `edges.md` edges 18 / 18c / 18d.

---

## Routing: use `rerun_recommended`, never `clean`

The script returns both. They answer different questions and only one is a routing signal.

| Field | Question it answers | Use it for |
|---|---|---|
| `rerun_recommended` | Is there an unresolved **bug / security / regression** finding? | **Routing.** Edge 12 vs 13/14. |
| `clean` | Did everything run, with full coverage and nothing found? | **Reporting** only. |

`clean` is also `false` when a reviewer tool was absent or files exceeded coverage. Routing on it
created a live deadlock: with `code-simplifier` merely uninstalled and **zero** findings, edge 12
could not fire (no finding) and 13/14 could not fire (`clean` false, budget unspent) — **no guard
matched and the run halted.** A skipped gate is recorded and the run continues; it is never a halt.

So: `skipped_steps` and `uncovered` go to `skipped_gates[]` and the gate is not recorded as passed —
**but the run proceeds.**

---

## `applied` is corroboration, not evidence

The script returns `applied` so the orchestrator can cross-check what the gate says it changed against
`git diff --name-only`. **A real run showed the field is not trustworthy on its own:** it came back
`[]` while the working tree held 20+ files modified by the gate's own simplification and security
steps.

Handle the two directions differently, because they mean opposite things:

| | Meaning | Do |
|---|---|---|
| **Changed but unclaimed** | Under-reporting. The work happened; the report was thin. | **Verify the diff yourself**, continue, and record that `applied` was unreliable this run. Not a `BLOCKED` — nothing was falsely claimed. |
| **Claimed but unchanged** | A **false claim**. The gate says it fixed something it did not touch. | **`BLOCKED`.** This is the unearned-pass class. |

**Never treat `applied` as proof a fix landed.** `git diff` is the source of truth; `applied` only
tells you what the agent believes it did.
