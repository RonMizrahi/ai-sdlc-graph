# Transition Table

Every transition in the graph, with the guard that fires it and the bound that stops it looping.

**20 nodes · 40 guarded transitions · 30 rows.** The two `DEBUG` rules (19 and 20) are authored once
and cover six callers each, so the table is shorter than the graph. `graph_walk.py` expands them:
coverage is still counted in transitions, and every caller must still be exercised.

Companion files: **`nodes.md`** (node catalog and contracts) · **`state.md`** (run-state schema,
resume rules).

---

## How transitions are evaluated

1. The node finishes and returns its result.
2. Guards for that node are evaluated **in table order**. **Exactly one must match.**
3. The transition is written to `history[]` and the state file is saved **before** the next node
   starts — **one transition per write, never two batched after the fact.** The one legal batch is a
   **verified milestone replay**: a milestone agent runs the milestone loop and returns once, so its
   transitions are written on return — still one at a time, in the order the agent traced them, and
   **only after the return gate has passed** (`state.md` § *Write points*).
4. **`attempts["<KEY>"]` counts how many times the node has been ENTERED under that key, and the
   bound is the maximum number of entries.** A first pass writes `1`; a bound of `3` therefore
   allows two retries, and `GATE_A`'s "1 re-run" and its bound of `2` are the same statement said
   two ways.

### Who evaluates, who executes

> **The orchestrator evaluates every guard. The executing agent evaluates none.** A milestone agent is
> given a fixed itinerary computed before the spawn, plus mechanical red/green branching. It reports
> facts; the orchestrator turns those facts back into guards, in this table's order.

This split is not tidiness. It failed once in the other direction: `gate-a.workflow.js` returned a
`clean` field, the orchestrator routed on it, and the run deadlocked **twice** — because `clean` is
also false when a tool was absent or coverage fell short. An executor that both acts and decides is
that defect at the root. **Never route on a value the executor chose the meaning of.**

> **This file is the authoritative rendering of every guard, and the only one.** `history[].guard`
> quotes it verbatim, so a trail can be matched against the table mechanically. `nodes.md` names each
> node's *destinations* but does not restate the guard text — it used to, in different words, and the
> two renderings had to be policed by a check.

**Zero matching guards is a bug, not a stall.** Halt with `BLOCKED` and report the node, its result,
and every guard tested — never guess a transition.

**One matching guard, always.** Where two conditions could both hold (`PASS-WITH-ISSUES` with an S2
is both "has issues" and "not a BLOCK"), table order resolves it. Read the guards top-down.

> `[start]` and `[end]` are notation, not nodes: a run begins at `INTAKE` and ends at `DONE`. They
> were rows 1 and 33 of this table for two releases, costing two edges, two coverage obligations and
> two fixture steps to assert that a graph starts where it starts.

---

## Setup

| # | From | To | Guard | Bound |
|---|---|---|---|---|
| 1 | `INTAKE` | `SPEC` | `spec_path == null` | — |
| 2 | `INTAKE` | `PLAN` | `spec_path != null` | — |
| 3 | `SPEC` | `PLAN` | spec file on disk **and** user approved | — |
| 4 | `PLAN` | `PLAN` | user requested revisions — rewrite the file in place | unbounded (user-driven) |
| 5 | `PLAN` | `STRATEGY` | `plan_path` on disk **and** every milestone has its required steps **and** **user approved** | — |
| 6 | `STRATEGY` | `BRANCH` | `branching ∈ {A,B,C}` **and** milestone `deps` acyclic **and** `context.has_ui` is a boolean | — |
| 7 | `STRATEGY` | `HANDOFF` | `branching == D` | — |

> Edge 5 is the **cardinal-rule gate**: a plan that exists only in conversation does not pass, and
> the user must **approve** it, symmetric with edge 3 at `SPEC`. Edge 6 is where the task list is
> seeded, one task per milestone.

> **Edge 4 is unbounded on purpose.** Every other cycle here has a numeric bound, because every other
> cycle is a *retry* — an agent trying the same thing again. This one is a **conversation**: the human
> is changing their mind, which is exactly what this gate is for. `SPEC` is unbounded for the same
> reason.

> **`context.has_ui` is a boolean by edge 6, and that is where the tri-state ends.** The field is
> `true` / `false` / `null`, and only two of the three are routable — `null` means *not yet decided*,
> the normal state of a greenfield run. `STRATEGY` is the last node before the loop and already asks
> the user for the other run-level settings, so **it resolves `has_ui` too, and edge 6 refuses to
> leave without it.**
>
> This used to be enforced 200 lines later, at `GATE_A`, by a dedicated halt edge (`12d`) that had to
> be tested *before* the two real exits — because written as `NOT has_ui`, the `has_ui == false`
> exit (guard 13) matched `null` as if it were `false` and **erased `E2E` for the whole run without one ledger entry.** That halt also
> needed its own itinerary shape, its own `nodes.md` callout, its own diagram caveat and its own spec
> check. **Resolving the value where it is settled costs one clause; routing around it cost five
> surfaces.**

> **Edge 7 — strategy D is a hand-off, not a path.** `/batch` is a *user* command; a skill cannot
> invoke it. The graph writes the plan, tells the user to run `/batch` and point it at these
> guidelines, and parks at `status: HANDOFF` with the reason recorded.

## Milestone loop

| # | From | To | Guard | Bound |
|---|---|---|---|---|
| 8 | `BRANCH` | `IMPLEMENT` | branch checked out | — |
| 9 | `IMPLEMENT` | `TEST` | every step this node owns is committed — a step whose deliverable is a test belongs to `TEST` and is owed at 10, never here | — |
| 10 | `TEST` | `GATE_A` | every step `TEST` owns is committed **and** unit **and** integration **not red** — an `absent` suite is recorded to `skipped_gates[]` and never counted as passed | — |
| 11 | `GATE_A` | `GATE_A` | step 4 found a real bug/security/regression **and** `attempts < 2` | **1** re-run |
| 12 | `GATE_A` | `E2E` | tests green **and** (**no** rerun-worthy finding **or** re-run budget spent) **and** `context.has_ui == true` | — |
| 13 | `GATE_A` | `GATE_B` | tests green **and** (**no** rerun-worthy finding **or** re-run budget spent) **and** `context.has_ui == false` | — |
| 14 | `E2E` | `GATE_B` | journeys **not red** — an app that genuinely cannot be brought up while `has_ui` is recorded to `skipped_gates[]` and never counted as passed. **Playwright merely uninstalled is NOT that case — install it** (`nodes.md` § `E2E`) | — |
| 15 | `GATE_B` | `BRANCH` | tests green after review-and-fixes **and** a milestone remains **and** `integration.branch == null` | — |
| 16 | `GATE_B` | `CONSOLIDATE` | tests green after review-and-fixes **and** `branching == C` **and** no milestone remains **and** `integration.branch == null` | — |
| 17 | `GATE_B` | `CLOSE_OUT` | tests green after review-and-fixes **and** ((`branching ∈ {A,B}` **and** no milestone remains) **or** (`branching == C` **and** `integration.branch != null` — the integration pass)) | — |
| 18 | `CONSOLIDATE` | `GATE_B` | every milestone branch merged into `integration.branch` **and** the **integrated** suite is green | — |

> **Guards 9 and 10 PARTITION `milestones[].steps`; neither owns all of them.** `PLAN` is *required*
> to bake test steps into every milestone (`plan-guidelines-node.md` § *Every milestone MUST include*),
> and `TEST` — not `IMPLEMENT` — is the node that writes them. Guard 9 read *"all milestone steps
> committed"* for a release, which is **literally false** at `IMPLEMENT → TEST` on any milestone whose
> plan names a test file, and `IMPLEMENT` has exactly one exit: a real run therefore had a perfectly
> healthy milestone one strict reading away from `BLOCKED`. The split is by deliverable, mechanical,
> and written down once in `nodes.md` § *Which steps `IMPLEMENT` owns*. **Every step is owed at exactly
> one of the two guards** — 9 for implementation steps, 10 for test steps — so a step cannot be
> dropped in the gap between them, which is what a bare "IMPLEMENT owes less" would have opened.

> **Guards 12/13/15/16/17 deliberately do NOT test `clean`.** `clean` is a *reporting* field: it also
> goes false when the reviewer tool is merely absent. Routing on it meant "reviewer not installed +
> suite green" matched **zero guards** and the run had to halt or improvise — a real halt, twice. The
> routing fact is the **suite state after the gate's own fixes**; a reviewer that could not run is a
> `skipped_gates[]` entry and the run proceeds. **Route on test state; report on `clean`.**

> **Edges 12/13 are structural, not conditional-skip.** When `has_ui == false` the `E2E` node does
> not exist for this run. It is never written to `skipped_gates[]` — a backend service has no UI to
> drive, and its request→response flow is already covered at the integration level.

> **Edge 11 is the narrowest guard in the graph.** It fires *only* for a genuine bug, security issue
> or regression found by the final review. A style nit does not re-run the gate — that is how a
> quality pipeline turns into an infinite polish loop.

> **`GATE_B` runs twice under C, and that is not redundancy.** The per-milestone pass reviews that
> milestone's diff; the integration pass (edge 18) reviews **the whole integrated diff against
> `main_branch`** — the cross-milestone interactions no single worktree could see. Under A and B the
> last milestone's `GATE_B` does both jobs at once. Counters are keyed separately:
> `attempts["GATE_B:<id>"]` per milestone, `attempts["GATE_B:integration"]` for the consolidated pass.

## The `DEBUG` round-trip — one rule, six callers

| # | From | To | Guard | Bound |
|---|---|---|---|---|
| 19 | **any of** `TEST` · `E2E` · `GATE_A` · `GATE_B` · `CI` · `CONSOLIDATE` | `DEBUG` | that node's result is red | **the calling node's `max attempts`** |
| 20 | `DEBUG` | **the node named in `debug_return_to`** | root cause fixed | — |

**This was twelve hand-written rows — six identical pairs — and it is now two.** Nothing about the
graph changed: `DEBUG`'s own contract already said *"re-entrant from six callers, and always returns
to whichever node called it"*, and the table then enumerated the six anyway. Twelve rows were 29% of
the transition table, six of the ten bound rows, and six `debug_return_to = X` clauses in six
`emits` rows, all restating one sentence.

Three things make the collapse safe rather than merely shorter:

- **Coverage is unchanged.** `graph_walk.py` expands row 19 into its six `(caller, DEBUG)` pairs and
  row 20 into the six returns, so the fixture set must still exercise **every** caller. A collapse
  that traded a maintenance win for a coverage loss would not be worth having.
- **The bound is where it belongs.** Each caller already declares `max attempts` in its `nodes.md`
  contract, and that number *is* the round-trip's bound. Stating it twice is what let the
  `GATE_B ↔ DEBUG` bound read 2 in one file and 3 in another.
- **The guard no longer restates the destination.** Row 20's guard used to read *"root cause fixed
  **and** `debug.return_to == TEST`"* — but a `DEBUG → TEST` transition cannot mean anything else.
  The clause was the destination written twice, and it is the field, not the guard, that makes resume
  deterministic.

> **Why `DEBUG` is one node and not six.** Every caller wants the same thing — root-cause before any
> fix, minimal legitimate change, the caller's bound. Splitting it per caller would give six copies
> of one procedure and six places for the method to drift.

> **A red suite and a merge conflict are not the same failure.** `CONSOLIDATE` routes a *semantic*
> conflict here — git merged cleanly, the suite went red, so there is a root cause to find. A
> **textual** conflict is `BLOCKED` with the paths named: git could not resolve it and neither should
> the graph guess.

## Tail — one sequence, every strategy

| # | From | To | Guard | Bound |
|---|---|---|---|---|
| 21 | `CLOSE_OUT` | `PR` | — **unconditional, every strategy**; the work still has to be merged | — |
| 22 | `PR` | `PR_FINAL_REVIEW` | PR/MR open — or `context.host == none`, nothing to open, ledgered | — |
| 23 | `CI` | `QA` | checks passing (or `context.host ∈ {gitlab, none}` — CI out of scope or no remote, logged to `skipped_gates[]`) **and** the app is assembled and runnable | — |
| 24 | `CI` | `MERGE` | checks passing **and** the plan produced nothing runnable | — |
| 25 | `QA` | `VERDICT` | verdict returned | — |
| 26 | `VERDICT` | `MERGE` | `verdict == PASS` | — |
| 27 | `VERDICT` | `MERGE` | `verdict == PASS-WITH-ISSUES` **and** no S1/S2 | — |
| 28 | `VERDICT` | `BRANCH` | `verdict == BLOCK` **or** any S1/S2 present | **2** reopens |
| 29 | `MERGE` | `DONE` | PR confirmed merged | — |
| 30 | `PR_FINAL_REVIEW` | `CI` | review posted — **or** the reviewer could not run and the ledger says so. **Unconditional: this node has one exit** | — |

> **Edge 30 posts a review; it never routes on one.** `PR_FINAL_REVIEW` is the only place
> `code-review:code-review` can run — it needs an open PR, and one finally exists. Its findings become
> inline PR comments for the human who merges. **A finding there does not reopen the loop**: `GATE_A`
> and `GATE_B` already gated this diff, `QA` is still ahead, and `VERDICT` (edge 28) owns reopening.
> A third reviewer with routing power would be a fourth opinion on an already-gated change.

> **The QA-skip edge must be stated out loud.** Edge **24** is the *only* legitimate path that skips
> QA — a plan that produced nothing runnable. Taking it silently is how an unverified change ships.
> Name it in the run report.
>
> It sits at `CI` rather than at `CLOSE_OUT` because `CLOSE_OUT` has a single unconditional exit: the
> work has to reach `main_branch` whether or not it is runnable, so routing it to `DONE` would strand
> the branch unmerged.

> **`VERDICT` is a node and not three more `QA` exits, deliberately.** It is tempting to hang 26/27/28
> off `QA` and delete a node — but `QA` is the executor, and *"never route on a value the executor
> chose the meaning of"* is the rule at the top of this file. `QA` reports; `VERDICT` decides, creates
> the fix milestone, repoints the cursor and writes the verdict into the plan file. Those are the
> orchestrator's acts, and merging them into the probing node is the exact shape that deadlocked
> `GATE_A` on `clean`.

> **Edge 27 does not mean "clean".** S3/S4 findings become documented follow-ups in the plan file, and
> every confirmed finding — at any severity — is converted into a committed test before `DONE`.

> **Edge 28 creates a fix milestone** scoped to the S1/S2 findings, appends it to `milestones[]`, and
> points the cursor at it. It re-enters the loop at `BRANCH`, so the fix gets the same gates as any
> other milestone. It does not shortcut to `PR`.

> **Nothing reaches `main_branch` until QA has passed — under every strategy.** `CI` comes before `QA`
> because `CI` needs an open PR to watch and because QA-ing a branch that fails CI wastes the most
> expensive node in the graph. This closes a real hole in the earlier ordering, where `MERGE` ran
> *before* close-out: the plan-file updates, the `CLAUDE.md` changes, the QA plan and every confirmed
> finding's regression test were all committed outside any review, and a `BLOCK` verdict meant the
> broken work was already in `main_branch`.

---

## Branching strategy shapes the loop, and nothing else

From `CLOSE_OUT` onward, A, B and C run the identical sequence:

```
CLOSE_OUT → PR → PR_FINAL_REVIEW → CI → QA → VERDICT → MERGE → DONE
```

| Strategy | Where the milestones are built | How they converge |
|---|---|---|
| **A** — one branch, one MR | `BRANCH` once, then the loop per milestone on the same branch, looping via **edge 15** | Already one branch — straight to `CLOSE_OUT` (**17**) |
| **B** — current branch | same as A, but `BRANCH` is a no-op throughout | same as A |
| **C** — worktree per milestone | **each milestone in its own git worktree**, independent milestones running concurrently | `CONSOLIDATE` (**16**) merges every branch into one integration branch, then a whole-diff `GATE_B` pass (**18**) |
| **D** — delegate to `/batch` | the graph does **not** run the loop — see edge 7 | outside the graph |

Under **A and B**: `BRANCH` is idempotent — it creates the run branch on first entry and is a no-op
on every later milestone.

> **C is parallel-first, and it is the only reason C exists.** Every milestone gets its own worktree;
> milestones whose `deps` are all satisfied run **concurrently**, because separate worktrees are
> separate working directories and cannot collide over the index. Dependent milestones branch off
> their parent's branch and wait for it.
>
> An earlier shape gave C its own tail — a PR, a CI run and a merge *per milestone* — at the cost of
> eight extra edges, per-milestone PR churn, and QA that could only run against `main_branch` after
> the fact. **Local consolidation gets the parallelism without any of that**: one integration branch,
> one PR, one QA pass that gates one merge.

> **`is_fix` does not force a fresh branch under any strategy.** By reopen time there is exactly one
> open unmerged branch carrying everything — the run branch under A/B, the **integration branch**
> under C — with a PR open against it. A reopen commits there and pushes to the **already-open PR**,
> which makes `PR` idempotency load-bearing: check for an existing PR on the branch and update it
> rather than open a second.

---

## Loop bounds

**Ten cycles exist, in five rules. Every one is bounded** — an unbounded cycle is the failure mode
this table exists to prevent.

| Cycle | Counter key | Bound | On exhaustion |
|---|---|---|---|
| **Any node ↔ `DEBUG`** (edges 19/20) | `"<CALLER>:<milestone-id>"` | **the caller's `max attempts` in `nodes.md`** — `TEST` 3 · `E2E` 3 · `GATE_A` 2 · `GATE_B` 2 · `CONSOLIDATE` 3 · `CI` watch-ci's 15-min budget and its 2-same-error guard | `BLOCKED` (`CI`: `STILL-RED` / `BLOCKED`) |
| `GATE_A` ↻ `GATE_A` (edge 11) | `"GATE_A:<id>"` | 1 re-run, **real findings only** | **proceeds** via 12/13, findings documented — *not* `BLOCKED` |
| `GATE_A` dispatch retry (no edge — re-entry) | `"GATE_A-dispatch:<id>"` | 1 retry, **workflow error only** | `BLOCKED` |
| Milestone-agent dispatch retry (no edge — re-spawn) | `"MILESTONE-dispatch:<id>"` | **1** — one entry, so one re-spawn and no more, counted the moment the death is diagnosed rather than when the replacement starts. **Agent failure only** | `BLOCKED` |
| `VERDICT` → `BRANCH` (edge 28) | `"QA"` | 2 reopens | `BLOCKED` — human decision |

**Counters are keyed per milestone, and never reset.** `"TEST:3"` starts absent, therefore zero, so
per-milestone keying already gives each milestone a fresh budget and no reset rule is needed. Resume
inherits the counter it left behind — rewinding it hands a stuck loop an unlimited budget.

> **A dispatch retry has its own key, and that is not cosmetic.** A `GATE_A` workflow that dies
> without running a single agent is not a review finding and must not spend the findings re-run
> budget. Observed in a real run: a checkpointed, unresumable dispatch consumed the findings budget,
> so the *actual* Gate A pass that followed had none left — a genuine bug would have exited via
> "budget spent" instead of getting its re-review. **A harness crash can silently downgrade a
> security re-review.**
>
> A dispatch failure must be *verified*, not assumed: the workflow returns no result,
> `groups_completed` is 0, the run journal holds no `result` line, and `git diff` shows no edits.
> Anything else is a real Gate A pass and belongs in `GATE_A:<id>`.
>
> **The milestone agent's `MILESTONE-dispatch` key exists for the same reason.** An agent that died
> without returning a bundle reviewed nothing, tested nothing and implemented nothing verifiable;
> charging it to `TEST:<id>` hands the milestone a re-run budget it never spent. Verify against git
> before the re-spawn — an agent that committed and then died is not an agent that did nothing.

---

## Terminal states

| State | Meaning |
|---|---|
| `DONE` | Reached the end. **Not necessarily clean** — check `skipped_gates[]` and the follow-up list. |
| `BLOCKED` | Something **failed**: a bound was exhausted, or no guard could be satisfied. `stopped` names the node, every guard tested, and what was tried. **Resumable** once the human resolves it. |
| `HANDOFF` | A deliberate stop with **nothing wrong**. Only strategy D reaches it (edge 7). Needs action, not diagnosis. |

**`BLOCKED` and `HANDOFF` are deliberately separate.** A strategy-D park satisfied its guard and hit
no bound — filing it under `BLOCKED` would send a reader hunting for a failure that never happened.

`BLOCKED` is a pause, not a failure of the run. The state file holds enough to resume: re-derive the
node's progress from the world (`state.md` → Resume) and continue.
