<!-- copied-from: the standalone `watch-ci` skill @ v0.5.0 — a separate, unbundled skill of the author's; this copy is graph-scoped and meant to diverge -->
<!-- trimmed: "Do Not Use When — nothing is pushed yet" REMOVED — the `PR` node guarantees a push and
     an open PR/MR before this node is ever entered (edge 21), so the case cannot arise in the graph.
     Also removed: standalone trigger phrases and the `argument-hint` framing (target and budget come
     from state and `context`, not from a user-typed argument), and the "authoring CI from scratch"
     exclusion (out of scope for a node that only ever runs on an existing red run).
     CHANGED: the source spawns a monitor-and-fix subagent and forbids running the loop inline; here
     the loop IS the node body, because the graph already dispatches this node as its own unit and
     owns the state write on either side of it. -->

# Node: watch-ci

Serves **one** graph node: `CI`. Entered from `PR` on edge 21; exits to `MERGE` on edge 22, or to
`DEBUG` on edge 23 (returning via edge 24 with `debug.return_to == CI`).

## Goal

Every **required** check on the GitHub Actions run for `milestones[cursor].branch` /
`milestones[cursor].pr` ends **passing**, achieved only through legitimate fixes — application code,
tests, or CI/build config that addresses the actual cause. The node loops
watch → diagnose → fix → verify locally → push → re-watch, bounded by a **time budget (default 15
minutes)**. The outcome is always a clear report — never a fake-green produced by neutering checks.

---

## Preconditions

Confirm `gh auth status` succeeds and `origin` is a GitHub remote. Resolve the target run from
`milestones[cursor]`:

- PR recorded → `gh pr checks <n>` and `gh run list --branch <headRef>`.
- else the milestone's branch → `gh run list --branch <branch> -L 5`.

If the latest run's required checks are already **passing**, take edge 22 and stop. Fix the budget as
a **concrete integer** before starting: `BUDGET_MIN=15` unless the user set otherwise.

```
START=$(date +%s); DEADLINE=$((START + BUDGET_MIN*60))
```

## The monitor-and-fix loop

Treat `DEADLINE` as a hard boundary: **check `[ "$(date +%s)" -lt "$DEADLINE" ]` before each watch
cycle and before starting each fix.** If it fails, stop and report — do not start work you cannot
finish (you cannot interrupt an in-flight local build, so do not begin one near the deadline).

1. **Watch by polling, never a blocking wait.** Run
   `gh run view <run-id> --json status,conclusion,jobs` every ~20–30 s, **re-checking the deadline
   between polls**. `conclusion: null`, or a `status` of `queued` / `in_progress`, means still
   running — keep polling.
   > **`gh run watch` is forbidden here: it blocks with no deadline control.** A blocking wait cannot
   > honour the budget, which is the only thing standing between this node and an unbounded loop.
2. **Success** → confirm true green against the source of truth: if a PR exists, `gh pr checks <n>`
   (every *required* check `pass`); else the run's `conclusion == success`. Green → stop, take edge 22.
3. **Failure** → `gh run view <run-id> --log-failed` (and `--job <id>` for the failing job). Identify
   the failing job/step and the real error. **Redact any secrets seen in logs.**
4. **Reproduce it LOCALLY first.** Read the workflow file (`.github/workflows/*`) for the exact command
   the failing step runs, and run *that* command locally. Root-cause per **`systematic-debugging`**
   before proposing any fix — **do not guess-patch a remote run.**
5. **Fix minimally and legitimately** — the smallest change that fixes the *cause* (app code, test, or
   CI/build config).
6. **Verify locally** — re-run the same command; it must pass locally **before** you push.
7. **Commit + push** to the same branch. Clear message; never `--force`; never touch `main`.
8. **Pick up the new run** — a fresh run takes a moment to register, so poll
   `gh run list --branch <b> -L 1` until a run newer than the one you pushed over appears, set it
   current, and loop from step 1.

## Forbidden — these fake green instead of earning it

- Skipping or deleting tests
- `continue-on-error`
- `|| true`
- Lowering coverage thresholds
- `xit` / `.skip`
- Weakening assertions

> **A green obtained any of these ways is a FAILURE of this node, not a pass.** If the honest fix is
> out of scope, stop and surface it. Never record `CI` as passed on a neutralised check.

## Bounds

- **No-progress guard** — if the **same job** fails with the **same error** after **2** fix attempts,
  stop and escalate as needing human judgment. Two identical failures mean the diagnosis is wrong, and
  a third attempt at the same wrong diagnosis is not progress.
- **Time budget** — default **15 minutes**, enforced **at cycle boundaries** (before each watch and
  each fix), never mid-command. Extend only on explicit user instruction.
- **Escalate, never work around** — a human-judgment failure is not this node's to fix: a product-
  behaviour change, a missing secret or permission, an external-service outage, or a genuine flake.
  Surface it and stop.
- **Surgical** — change only what the failing check requires; no drive-by refactors.

## GitLab — out of scope

This node drives GitHub Actions via `gh`. **On GitLab there is no CI node behaviour to run**: record a
`skipped_gates[]` entry naming `CI` and the reason (`host == gitlab`, GitLab CI not driven by this
graph), and let the run proceed to `MERGE`. That is the second clause of edge 22's guard, not an
error path — but the run is **not** a clean run, and `CLOSE_OUT` must carry the entry into the plan
file verbatim.

---

## Contract

| | |
|---|---|
| **inputs** | `milestones[cursor].pr`, `milestones[cursor].branch`, `context.host` |
| **emits** | `milestones[cursor].node = CI`, `attempts["CI:<id>"]`, `debug.return_to = CI` on failure, `skipped_gates[]` on GitLab |
| **exit guards** | every **required** check passing → `MERGE` · `context.host == gitlab` → `MERGE` (logged to `skipped_gates[]`) |
| **on failure** | red → `DEBUG` (`debug.return_to = CI`) · budget exhausted, or the same error twice → `BLOCKED` + `blocked` |
| **max attempts** | watch-ci's own 15-min budget + its 2-same-error guard |
| **requires** | `gh` with GitHub Actions — **GitLab → `skipped_gates[]`**, never recorded as passed |

> **`debug.return_to = CI` is what makes the return deterministic.** Without it, a resumed run cannot
> tell a CI failure from a test failure, and `DEBUG` has nowhere to come back to.
