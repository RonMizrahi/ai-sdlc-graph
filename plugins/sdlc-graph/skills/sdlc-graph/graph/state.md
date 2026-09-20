# Run State

The state file is the graph's only durable memory. Everything the orchestrator needs to answer
*"where were we?"* lives here — nothing important may exist only in conversation.

Companion files: **`nodes.md`** (node catalog and contracts) · **`edges.md`** (transitions, guards,
loop bounds).

---

## Location — one directory per run

```
docs/graph-runs/<run-id>/
├── state.json                       ← this file
├── journals/
│   └── milestone-<id>.jsonl         ← one per milestone agent, written by that agent alone
└── history/                         ← only when the run was started with `--trace`
    └── NNNN_m<M>_<FROM>-to-<TO>_<ts>.json
```

`<run-id>` is `<subject>-<DD>-<MM>-<YYYY>`, matching the plan file it drives. **`<subject>` is at
most five words from the opening request, slugified** — `add-rate-limiting`, not a paraphrase of the
whole feature. One directory per run; runs are never merged.

> **The run directory is gitignored, and `INTAKE` is what makes it so.** Before creating anything,
> `INTAKE` appends `docs/graph-runs/` to the project's `.gitignore` (creating the file if there is
> none) and no-ops when the entry is already there. That one edit is committed with the spec on the
> first branch `BRANCH` creates.
>
> **This deletes a rule rather than adding one.** `R12` used to run
> `git status --porcelain -- ':(exclude)docs/sdlc'` and then bound the exemption by re-checking that
> the excluded directory held nothing but this run's own bookkeeping. Ignored files never appear in
> `git status --porcelain` at all, so the exemption and its bound both go away and `R12` is the
> plain containment check it was always trying to be.
>
> **What it costs:** a run cannot be resumed from a fresh clone, and the state file is not a
> reviewable artifact in a PR. The **plan file** — committed, and updated at `CLOSE_OUT` with every
> milestone status and every `skipped_gates[]` entry — is the durable record that survives. A run is
> working memory; the plan is the record.

There is no `docs/sdlc/` and no `<run-id>-` filename prefix any more. A run left over from that
layout is not discovered and not resumed; point the viewer at it with `RUNS_DIR` if you need to read
one.

---

## `trace` — keeping every state, not just the last one

`state.json` is overwritten at every transition, so on an ordinary run every state but the final one
is gone. `history[]` records that the graph *moved*; it does not record what the file looked like
while it was moving — the counters as they climbed, the provisional `progress` block, the ledger as
it grew. Reconstructing that from the final file is guesswork.

**`--trace` at invocation turns it on. It is off by default and off when absent.** `INTAKE` settles
it once, states the resolved value in its summary the way it already states `has_ui`, and never
changes it again.

Every write to the state file is then copied into the run's own `history/`:

```
docs/graph-runs/<run-id>/history/
├── 0001_INTAKE-created_20260808T091422Z.json
├── 0002_INTAKE-to-SPEC_20260808T091510Z.json
├── 0003_SPEC-to-PLAN_20260808T093002Z.json
└── 0007_m2_GATE_A-to-E2E_20260808T094402Z.json
```

Numbered so the order is never in doubt, and named from the transition the state file itself
records — so `ls` reads as the run's story without opening anything. **The number comes from the
directory, not from `len(history)`**: a snapshot is also taken for writes that do not advance the
trail, and a `progress` tick while an agent works is a state the run passed through.

**Telemetry, not evidence — the same rule the milestone journals carry.** Nothing routes on
`history/`. The return gate reads the bundle; the auditor reads `state.json`. The hook that writes
it never blocks and has no non-zero exit path, because a lost snapshot must never be an interrupted
run.

**Who writes it:** the plugin's own `PostToolUse` hook (`hooks/hooks.json`), which installs and
uninstalls with the plugin. **The orchestrator does not write `history/` itself** — a second writer
would mean two things that can disagree about the sequence, and the orchestrator has enough to do
at a transition. If the hook is not installed, `history/` is simply absent, and
`trace-history-is-complete` in the auditor reports **NOT RUN** rather than a pass.

---

## Schema

```json
{
  "run_id": "auth-27-07-2026",
  "plan_path": "docs/plans/auth-27-07-2026-plan.md",
  "spec_path": "docs/specs/auth-26-07-2026-design.md",
  "schema_version": 5,

  "node": "GATE_A",
  "status": "RUNNING",
  "stopped": null,
  "trace": false,

  "context": {
    "stack": "backend",
    "has_ui": false,
    "main_branch": "main",
    "unborn_main": false,
    "host": "github",
    "standards_handshake": null,
    "branching": "A",
    "auto_open_mr": true,
    "run_mode": "continuous",
    "qa_env": {
      "run_instructions": "docker compose up -d && yarn start:dev",
      "api_base_url": "http://localhost:3000",
      "web_base_url": null,
      "api_docs": "/api-json",
      "identities": ["qa-user-a", "qa-user-b"],
      "seed": "yarn seed:dev"
    }
  },

  "milestones": [
    {
      "id": 1,
      "name": "auth repository",
      "branch": "PROJ-1/auth-repo",
      "worktree": null,
      "deps": [],
      "steps": ["create auth repository", "unit tests for auth repository"],
      "pr": null,
      "is_fix": false,
      "touches_ui": false,
      "delivered": "Mongoose User schema + AuthRepository with findByEmail/create/updateRefreshToken; bcrypt cost 12; unique index on email. Callers get null, never a throw, on a miss."
    },
    {
      "id": 2,
      "name": "auth endpoints",
      "branch": "PROJ-2/auth-endpoints",
      "worktree": "../.worktrees/PROJ-2",
      "deps": [1],
      "steps": ["POST /auth/login", "POST /auth/refresh", "integration tests"],
      "pr": null,
      "is_fix": false,
      "touches_ui": true,
      "delivered": null,

      "base_sha": "a1b2c3d4e5f6a7b8c9d0e1f2a3b4c5d6e7f8a9b0",
      "spawned_at_history_len": 12,
      "main_sha_at_spawn": "0f1e2d3c4b5a69788796a5b4c3d2e1f009182736",
      "journal": "docs/graph-runs/auth-27-07-2026/journals/milestone-2.jsonl",
      "agent_id": "a85dde11a87a72841",
      "gate_a_run_id": null,

      "progress": {
        "at_node": "GATE_A",
        "headline": "Gate A: 6 files, 4 simplifications + 2 security findings applied, 1 re-run, clean",
        "seen_at": "2026-08-07T09:14:22Z"
      }
    }
  ],

  "cursor": 2,
  "in_flight": [2],

  "integration": { "branch": null, "merged": [] },

  "attempts": { "TEST:2": 1, "GATE_A:2": 1, "GATE_A-dispatch:2": 0, "CI:2": 0, "QA": 0 },
  "debug_return_to": null,

  "qa": { "verdict": null, "qa_plan_path": null, "bugs": [] },

  "skipped_gates": [
    { "node": "GATE_A.step2", "reason": "code-simplifier plugin not installed", "at_milestone": 2 }
  ],

  "history": [
    { "from": "IMPLEMENT", "to": "TEST", "guard": "every step this node owns is committed — a step whose deliverable is a test belongs to TEST and is owed at 10, never here", "milestone": 2 },
    { "from": "TEST", "to": "DEBUG", "guard": "that node's result is red", "milestone": 2 },
    { "from": "DEBUG", "to": "TEST", "guard": "root cause fixed", "milestone": 2 },
    { "from": "TEST", "to": "GATE_A", "guard": "unit and integration not red", "milestone": 2,
      "observation": "14 unit + 3 integration green on the 2nd attempt; the first failed on a fixture, not the code",
      "evidence": { "commits": ["a1b2c3d"], "run_id": null },
      "verified": "re-ran yarn test:unit and test:int myself — exit 0 both; 1 commit confirmed on PROJ-2/auth-endpoints" }
  ]
}
```

**18 top-level keys.** Four things that were here are not any more, and each removal deleted a rule
along with the field — see *What was removed, and why* at the end of this file.

## Schema version

```
SCHEMA_VERSION = 5
```

**That line is the only place the number is written.** It was previously stated twice — once in the
example above and once in the field table — and the two disagreed (`4` and `3`) while the rule they
govern is an unconditional halt. `spec_consistency.py` reads this line and requires the example and
every fixture to match it.

**A mismatched file is `BLOCKED`, naming both versions, and there is no migration path.** Earlier
versions of this file carried per-step migration recipes (`1 → 2` read the missing field as `true`;
`2 → 3` read the missing object as `{}`). They were written for schemas that no longer exist, no run
ever exercised them, and a recipe for reinterpreting a file written by a different graph is exactly
the silent reinterpretation the rule forbids. A run whose file predates the running spec is
**restarted, not migrated** — the work on the branch is still there, and re-deriving from the world
is what Resume does anyway.

## Fields

| Field | Type | Notes |
|---|---|---|
| `run_id` | string | `<subject>-<DD>-<MM>-<YYYY>`. Immutable. |
| `plan_path` | string | Set at `PLAN`. The plan file is the human-readable twin of this file. |
| `spec_path` | string \| null | Set at `INTAKE` if supplied, else at `SPEC`. |
| `schema_version` | number | See above. Set once at `INTAKE`, never updated mid-run. |
| `node` | string | The node the run is **currently in** — not the last one completed. |
| `status` | `RUNNING` \| `BLOCKED` \| `HANDOFF` \| `DONE` | `BLOCKED` is a resumable pause caused by a *failure*. `HANDOFF` is a deliberate stop where nothing went wrong: the only user is strategy D. A run parked at `HANDOFF` needs no diagnosis. |
| `trace` | boolean | **Keep every state this run passes through**, in `history/`. Set once at `INTAKE` from the `--trace` flag; **`false` when the flag is absent, and absent is `false`** — a run written by an older orchestrator has no key at all. Nothing reads it during a run except the snapshot hook, which reads it out of this file rather than out of any configuration of its own, so the two cannot disagree. **Never changed mid-run**: a half-traced run is a `history/` with a hole in it, which is worse than none because the gap looks like a state that was never written. |
| `stopped` | object \| null | **Why the run is not moving** — `{ kind, reason, at_node, guards_tested[], tried[] }`. See *One field for "not moving"*, below. `null` on a run that is moving. |
| `context.stack` | `backend` \| `frontend` \| `both` \| `unknown` | Resolved at `INTAKE` where detectable. **`unknown` on a greenfield repo is normal, not a failure** — `SPEC`/`PLAN` decide it and write it back before `IMPLEMENT` reads it. |
| `context.has_ui` | boolean \| null | **Decides whether the `E2E` node exists at all** for this run. `null` only until `STRATEGY` resolves it — **edge 6 refuses to leave `STRATEGY` while it is `null`**, so the loop never sees the third value. |
| `context.main_branch` | string | The repo default — `main`, `master`, or `develop`. |
| `context.unborn_main` | boolean | **True when `main_branch` has zero commits** — a fresh `git init`, the normal state of a greenfield run. `GATE_B` reads it to know its diff base is the **empty tree** rather than a ref that does not exist. |
| `context.host` | `github` \| `gitlab` \| `none` | From the `origin` remote. `none` = **no remote at all**: `PR` and `CI` become recorded skipped gates and `MERGE` asks you to merge locally, then confirms. |
| `context.branching` | `A` \| `B` \| `C` \| `D` | User's choice at `STRATEGY`. |
| `context.auto_open_mr` | boolean | Settled at `STRATEGY` so `PR` never pauses mid-loop. |
| `context.run_mode` | `continuous` \| `checkpoint` \| `on-exception` | Settled at `STRATEGY`. `continuous` (default) stops only at the six. **`checkpoint` adds a stop after every milestone's `GATE_B`** — the moment that milestone is finished and gated. `on-exception` adds one whenever a gate is skipped, a bound is exhausted, or a milestone bundle was rejected. **Declared stops, not invented ones.** |
| `context.standards_handshake` | object \| null | Frontend/both only. The answers to `front-react-development`'s mandatory handshake, settled once at `STRATEGY` so `IMPLEMENT` supplies them instead of stopping to re-ask. `null` for a backend stack. |
| `context.qa_env` | object \| null | How to run and reach the app, plus **two identities** for authorization probing. Gathered at `INTAKE` where discoverable, completed at `CLOSE_OUT` before `QA`. `QA` reads only from here — never from conversation, so a resumed run still knows how to reach the app. |
| `milestones[]` | array | Mirrors the plan's milestones, in plan order. |
| `milestones[].id` | number | Stable identifier. The suffix in every `attempts` key. |
| `milestones[].name` | string | Human label; becomes the task-list row. |
| `milestones[].deps` | number[] | Ids that must reach `GATE_B` clean first. Drives ordering **and** parallel eligibility — under C, milestones whose `deps` are all satisfied run **concurrently in separate worktrees**, and `CONSOLIDATE` merges in this order, parents first. Must be acyclic; `STRATEGY` blocks if not. |
| `milestones[].branch` | string \| null | Set by `BRANCH`. `null` until then. Under A/B every milestone shares the one run branch. |
| `milestones[].worktree` | string \| null | **Strategy C only.** Created at `BRANCH`, removed at `CONSOLIDATE`. `null` under A, B and D. |
| `milestones[].pr` | number \| null | PR/MR number, set by `PR`. Only the milestone that opens the PR carries it. |
| `milestones[].steps` | string[] | The milestone's steps, written by `PLAN` — **implementation steps and test steps together**, because `PLAN` is required to bake both in. **`IMPLEMENT` cannot run without this** — it is what the node builds — but it owes only the steps it owns: the two nodes partition this list, `nodes.md` § *Which steps `IMPLEMENT` owns*, and guards 9 and 10 each collect one half. Reading it as one undivided list is what put a healthy milestone one strict reading from `BLOCKED`. |
| `milestones[].is_fix` | boolean | **Seeded `false` by `PLAN` on every milestone**, set `true` only on a `VERDICT` reopen. Never absent — `BRANCH` reads it on every milestone. It makes `BRANCH` **skip** branch creation: by reopen time there is exactly one open unmerged branch carrying everything, and the fix belongs on it. |
| `milestones[].touches_ui` | boolean | **Seeded by `PLAN` on every milestone**, for the same reason — `E2E` reads it on every pass and must never find it absent. `true` when the milestone builds or changes user-facing components. **`has_ui && touches_ui` is what makes authoring Playwright specs mandatory** rather than a judgement call; `has_ui && !touches_ui` makes `E2E` a regression re-run. |
| `milestones[].delivered` | string \| null | **≤600 chars: what this milestone actually shipped**, written by the orchestrator **after** the bundle passes the return gate — never before, and never from the agent's word alone. `history[]` records that the graph moved and `observation` records how each hop went; neither answers *"what does this milestone now provide, and what must the next one know?"* `null` until `GATE_B` is passed and the replay is written. Read by `CLOSE_OUT`, and by any brief whose milestone has `deps`. **It is also how a milestone's completion is known** — see `cursor`. |
| `milestones[].base_sha` | sha40 \| null | The branch point this milestone was built from, recorded **before the agent is spawned**. `R4` diffs against it; `R12` checks it is still an ancestor. |
| `milestones[].spawned_at_history_len` | number \| null | `history.length` at spawn time — **the resume marker for THIS milestone's replay, not an index into `history[]`.** A replay in progress is detected by comparing it with the count of entries already carrying this milestone's id; a crash mid-replay therefore resumes at the right hop instead of double-writing. **Under C it is the same number for every agent** — they all spawn before any of them returns — and that is correct: replays are serialised, so the second milestone's transitions legitimately append far past its own marker. Reading it as "the index my rows start at" is what makes it look broken under C, and an orchestrator driving a run-eval reported exactly that. |
| `milestones[].main_sha_at_spawn` | sha40 \| null | The protected branch's head at spawn. **`R12` checks the returning agent left it byte-identical** — the worktree-is-not-a-sandbox guard. |
| `milestones[].journal` | string \| null | Path to this milestone's append-only journal, `docs/graph-runs/<run-id>/journals/milestone-<id>.jsonl`. **Written before the spawn**, because an agent that dies before its first append still has to be findable. One writer per file — see `workflow-dispatch.md` § *The journal*. |
| `milestones[].agent_id` | string \| null | The id the Agent dispatch returned, recorded at spawn. It is the **only** handle for asking that agent a question afterwards (`SKILL.md` § *Asking a milestone for more*). **It is not cleared on replay** — interrogation happens *after* the return, so clearing it there deleted the handle at exactly the moment it became useful. |
| `milestones[].gate_a_run_id` | string \| null | The `Workflow` runId from this milestone's `GATE_A` dispatch, recorded **at dispatch** and confirmed against the journal by `R7`. Without it, script-level resume (`resumeFromRunId`) is unreachable after exactly the context loss it exists to survive. `null` under `dispatch: "direct"`, where no run happened. |
| `milestones[].progress` | object \| null | **Provisional: what the milestone's agent *says* about itself**, from the last journal line — `{ at_node, headline, seen_at }`. Drives the viewer and the orchestrator's supervision. **Nulled the moment the milestone stops having a running agent** — the replay is written, the bundle is rejected, or the agent died — because it then describes an agent that no longer exists. **When the agent DIED, copy `at_node` and `headline` into `stopped.reason` before nulling**: this block is the only in-state record of how far it got, and clearing it at the moment of death deletes the diagnosis exactly when the re-spawn needs it. Two orchestrators driving run-evals hit this independently and both invented the same workaround. |
| `milestones[].progress.at_node` | string | Where the agent claims to be. **It is not a transition** — nothing routes on it and it never appears in `history[]`. |
| `milestones[].progress.headline` | string | One line on what the agent just finished. Provisional, exactly as above. |
| `milestones[].progress.seen_at` | string | Timestamp of that line. **This is the liveness signal**: older than the heartbeat window means the agent is dead or hung, which is the difference between supervising a run and waiting on one. |
| `cursor` | number | **Which milestone the loop is executing** — the one being spawned, or the one whose replay is being written. Initialised by `STRATEGY` to the first milestone with no unmet `deps`; advanced by edge 15; repointed by `VERDICT` on reopen. **The next milestone is derivable, not stored**: the first in plan order with `delivered == null` and every `deps` id `delivered`. |
| `in_flight` | number[] | **The milestones whose loop is delegated to a running agent.** `[]` when none is. Under A and B it holds at most one id; under C every concurrently-spawned one, which is the whole reason C exists. **Written *before* the spawn, and cleared when the milestone stops having a running agent** — its replay finished, its bundle was rejected, or it died and `stopped` was written. "Cleared as the replay finishes" alone stranded every id whose milestone ended any other way, in exactly the configuration this file calls the halt signature. `audit_run.py` fails a run that ends `DONE`/`BLOCKED`/`HANDOFF` with anything still in flight, so the file names the work in flight rather than the work last recorded. **An id here with no matching `history[]` block and no `stopped` is the signature of a halt that was NEVER RECORDED** — its agent died and nobody wrote it down. That is a defect the auditor detects, **not a description of how to record a halt**: recording one is § *Recording a halt*, and it writes both. Three orchestrators driving run-evals read "the halt signature" as the prescribed shape and wrote no `history[]` entry at all. |
| `integration.branch` | string \| null | **Strategy C only.** The branch `CONSOLIDATE` merges every worktree into, and the one thing `PR`, `CI`, `QA` and `MERGE` then act on. `null` under A, B and D — and **`null` under C until consolidation**, which is exactly what tells `GATE_B`'s per-milestone pass apart from its integration pass (edges 15/17 vs 16). |
| `integration.merged` | number[] | Milestone ids in the order `CONSOLIDATE` merged them — dependency order, parents first. On a `BLOCKED` conflict it holds everything that *did* merge, so a resume knows where it stopped. |
| `attempts` | object | Keyed `"<NODE>:<milestone-id>"`, bare `"QA"` for the run-level reopen bound, or `"GATE_A-dispatch:<id>"` / `"MILESTONE-dispatch:<id>"` for the two dispatch retries. **The single authority for every loop bound**, including the `DEBUG` cycles — keyed by the *calling* node, so `TEST`'s budget on milestone 2 is `"TEST:2"` and is independent of `GATE_B`'s. |
| `debug_return_to` | string \| null | **The node `DEBUG` must return to.** Without it, resume cannot tell a test failure from a CI failure. Carries no counter of its own — the caller's `attempts` key is the bound. |
| `qa` | object | `{ verdict, qa_plan_path, bugs[] }`. Filled at `QA`, read by `VERDICT`. `verdict` is `PASS` \| `PASS-WITH-ISSUES` \| `BLOCK`; `bugs[]` carries severity so `VERDICT` can test for S1/S2. |
| `skipped_gates[]` | array | Every check that could not run: `{ node, reason, at_milestone }`. `node` is a node id, **or a return-gate check written `R<n>`** — R5, R12 and R13 are milestone-wide and belong to no node, and three orchestrators invented three different keys for that before it was written down. Sub-steps keep the existing `GATE_A.step2` form. **Append-only — entries are never removed.** |
| `history[]` | array | **Also the global step counter — `length > 250` ⟹ `BLOCKED`**, a runaway backstop above the per-cycle bounds. Every transition, in order: `{ from, to, guard, milestone }`. `guard` quotes **`edges.md`** verbatim — the single authoritative rendering — so the trail can be matched against the table mechanically. Append-only. |
| `history[].observation` | string | One line on what actually *happened* in the node just left, **≤ 200 chars — and that applies to the ones YOU write too**. Required on every entry. R11 enforces the cap on an agent's; `O3` is where yours is enforced, because in an audited run all four orchestrator-authored observations ran to 365–775 chars while all five agent-authored ones fit. See *The observation trail*. |
| `history[].evidence` | object \| null | Only on transitions replayed from a milestone bundle: `{ commits[], run_id }` — short identifiers, never output. `commits[]` is what makes `commit ⇒ bundle ⇒ record` mechanically checkable. `null` on a transition the orchestrator ran itself. |
| `history[].verified` | string \| null | **The orchestrator's** one line naming what it checked and what it found, **≤ 300 chars**. It is the only field the orchestrator authors about a node it did not run, and it is never a rewrite of `observation`. `null` on a transition the orchestrator ran itself. **The cap exists because this field had none**: `observation` has been capped and enforced on agents since the schema existed, while `verified` — authored solely by the orchestrator, seen by no return gate — had no limit and no check. A field nothing measures is a field nothing disciplines. |

---

## One field for "not moving"

`stopped` answers a single question — **why is this run not advancing?** — with a `kind` that says
which sort of not-moving it is:

```jsonc
"stopped": { "kind": "blocked",              // "paused" | "blocked" | "handoff"
             "reason": "GATE_B ↔ DEBUG bound exhausted on milestone 2",
             "at_node": "GATE_B",
             "at_milestone": 2,
             "guards_tested": ["tests green after review-and-fixes and a milestone remains …"],
             "tried": ["re-ran the suite after each fix", "reverted the simplifier's change to auth.service.ts"] }
```

| `kind` | Set when | `status` | Cleared |
|---|---|---|---|
| `paused` | a declared human stop, or a `checkpoint` / `on-exception` return | `RUNNING` | on resume |
| `blocked` | a bound exhausted, or no guard could be satisfied. `guards_tested[]` and `tried[]` are what make it resumable | `BLOCKED` | when the human resolves it |
| `handoff` | strategy D parked | `HANDOFF` | never — it survives to the end of the run |
| `agent_lost` | an agent died or went silent and `MILESTONE-dispatch` still has budget — a diagnosis, not a failure of the graph. **`reason` names the liveness evidence AND how far the agent got** — the `at_node` and `headline` from the `progress` block being nulled, which is otherwise the only record of it. The re-spawn is the resume, and **`BLOCKED` is written even when the re-spawn follows in the same turn** — the write and the clear are two separate writes, so an orchestrator that dies between diagnosing the death and spawning the replacement leaves a file that says what happened instead of a `RUNNING` file describing an agent that no longer exists | `BLOCKED` | on the re-spawn, which clears it in the same turn it was written |

**This was two fields, `paused` and `blocked`, and keeping them apart cost a rule.** They answer the
same question, so a stop that is *also* a halt — `VERDICT`'s escalation on the spent 2nd reopen —
belonged to both, and `state.md` had to carry a paragraph deciding which one wins and asserting that
the other stays `null`. The file said *"two fields describing one pause is the drift this file exists
to prevent"* and then kept two fields. One field with a `kind` has no coincidence case: the
escalation is `kind: "blocked"` and also carries its reason, which is all the old paragraph was
trying to arrange.

**Without it, `status: RUNNING` with a quiet file is byte-identical between "working", "waiting for
you", and the `IMPLEMENT` halt.** That distinction is the whole point — Step Functions draws the same
line between `Timeout` and `HeartbeatTimeout`, because "slow" and "dead" are different failures.

---

## The state file is not committed — and still never put secrets in it

`docs/graph-runs/<run-id>/` is gitignored, so a mistake here is no longer permanent in git history.
**That is not a licence.** The file is read by the viewer, pasted into reports, handed to
`graph-run-reviewer`, and copied into scratch trees by the eval harnesses — a secret written here
still travels. The rule is unchanged; only the blast radius shrank:

| Field | Rule |
|---|---|
| `context.qa_env.identities` | **Identifiers only** — usernames, emails, role names. Never passwords, tokens, or API keys. Secrets resolve from the environment at `QA` time and are never written back. |
| `context.qa_env.*` | No connection string containing credentials. Store `mongodb://localhost:27017/db`, never `mongodb://user:pass@host`. |
| `history[]`, `stopped.tried[]` | Guard text and short descriptions only. **Never paste command output** — CI logs in particular carry tokens. |

Inherited from `qa-engineer`: redact every captured evidence field, and never record credentials or
PII. That rule applies to this file too — it is the one artifact of a run guaranteed to be committed.

---

## The observation trail

**Every `history[]` entry carries an `observation`: one line on what actually happened in the node you
just left.** Not what the guard says — the guard is already the next field. What *happened*.

Write it as you write the transition. It costs nothing and it is the only per-node record that exists;
`history` alone tells you the graph moved, never whether the move was healthy.

| Good | Useless |
|---|---|
| `"3 of 45 files had findings; all bugs, none style"` | `"gate A completed"` |
| `"passed, but code-simplifier absent so step 2 never ran"` | `"ok"` |
| `"2nd attempt — same fixture failure as the 1st"` | `"tests green"` |
| `"branch created off main; working tree was dirty, stashed 2 files"` | `"branched"` |

**Say the awkward thing.** A node that passed *but only just*, a retry that fixed a symptom rather
than a cause, a gate that ran degraded — those are the entries worth having, and they are exactly the
ones a run in a hurry omits. **Never paste command output**; one line of prose.

This trail is the only **verified** contemporaneous record of a run. An empty or uniformly cheerful
one is not a clean run — it is a run nobody wrote down. The milestone journals sit beside it and are
watched live, but they are unverified telemetry: they tell you what an agent *said*, and this tells
you what the orchestrator *checked*.

### Provisional is not recorded — `progress` vs `history[]`

An agent emits a line per node while it runs, and the orchestrator reads those lines as they arrive.
That is genuinely useful and it is genuinely not the record. Keep the two apart:

| | `milestones[<id>].progress` | `history[]` |
|---|---|---|
| Written | while the agent runs, from its journal | **only after the bundle passes the return gate** |
| Says | where the agent **claims** to be | where the run **is**, and what was checked |
| Routes | never | every guard |
| Survives | cleared when the replay is written | permanent |

**The temptation this exists to refuse:** the orchestrator now knows, in runtime, that `TEST` went
green — so why not write the transition then and save the replay? Because at that moment nothing has
been checked. The suite has not been re-run, no sha has been looked up, no spec file has been opened.
Writing it early converts the return gate from *the thing that decides what enters the record* into a
review of rows already in it — and a gate that runs after the write is a gate that cannot refuse.

A run may therefore show `progress.at_node: "GATE_B"` while `history[]` still ends at
`BRANCH → IMPLEMENT`. That gap is the design, not a lag to be closed.

`progress.at_node` is **nested** rather than sitting beside a `milestones[].node` precisely so the two
can never be confused. There is no longer a `milestones[].node` to confuse it with — see the end of
this file.

### Two authors, two fields — never one field with two authors

The milestone loop runs in an agent, so most transitions are written by an orchestrator that was not
there. That makes authorship a schema question, not a style one:

- **`observation` is authored by the agent that was there.** For an agent-owned node that is the
  milestone agent, one line per transition, returned in its bundle. For every other node it is the
  orchestrator, as before.
- **The orchestrator MUST NOT rewrite an `observation`.** Rewriting is how an unwitnessed summary
  acquires the voice of a witness.
- **The orchestrator MUST NOT invent one.** A bundle transition with an empty `observation` is a
  **rejected bundle**, not a transition for the orchestrator to narrate.
- **A journal `headline` is a legal source, and it is the only other one.** When `R13`'s repair
  replays a hop the bundle omitted, the `observation` comes verbatim from that node's headline —
  which the agent wrote, at the time, while it was there. The test is *who authored the words*, not
  *which artefact carried them*. `verified` says it came from the journal. A missing hop with no
  headline has no witness at all and is not repairable.
- **`verified` is the orchestrator's**: what it checked, and what it found.

## Write points

**The state file is written on every transition, before the next node starts.** Not at the end, not
on a timer — a crash between two nodes must leave a file that describes exactly where the run was.

Each write records: the new `node`, the appended `history[]` entry, any `emits` from the node that
just finished, and any `attempts` increment.

**One transition per write. Never batch.** Writing two transitions in a single edit after both nodes
have run means `node` never held the intermediate value, and the trail claims a node that was never
entered. A real run batched `IMPLEMENT → TEST` with `TEST → GATE_A` on two milestones; `node` never
once read `"TEST"`, and that decoupling of *recording* from *doing* was the precursor to the
`IMPLEMENT` halt 102 minutes later.

**The one legal batch is a verified milestone replay.** An agent runs six nodes and returns once, so
the orchestrator physically cannot write while they happen — the rule had to move from *timing* to
*evidence* rather than be deleted:

- The replay writes **one transition at a time, in the order the agent traced them** — never one edit
  carrying six. Each write is a real write, with its own `node`, `history[]` entry, `emits` and
  `attempts` increment.
- **Nothing is written until the return gate has passed** (`workflow-dispatch.md`). A bundle is a
  claim; the gate is what turns it into a record.
- Every replayed entry carries `evidence` from the agent and `verified` from the orchestrator. **A
  replayed transition with no `verified` is exactly the defect the timing rule used to catch**, one
  agent further away: a node the file says ran, that nobody can show ran.

  > **The hop OUT of `GATE_B` is not a replayed entry**, and it is the one that reads like a
  > violation of the line above. The agent's trace never leaves `GATE_B` — its last row is
  > `claimed_to: GATE_B` — so 15/16/17 are evaluated by the orchestrator, on run-level state, and
  > written with **`verified: null`**. That is § *Two authors* working correctly, not an exception
  > to it: `verified` records what the orchestrator checked *of somebody else's claim*, and there is
  > no claim here — it was the witness. Two orchestrators driving run-evals read the two rules as a
  > contradiction, which they are only if "replayed" is read as "every row written during a
  > replay".

Outside a milestone replay the original rule is unchanged and absolute.

**The `commit ⇒ bundle ⇒ record` invariant.** Executing a node and recording it used to be two acts by
the **same** agent, so the second could be forgotten. Under delegation they are two acts by
**different** agents, and the old mechanical check broke in both directions: while an agent runs,
`node` legitimately holds a stale value with real commits landing (a false positive on every healthy
milestone), and an agent that commits then dies leaves `node` set to something other than `IMPLEMENT`
(a false negative on exactly the case it existed for). So:

> **Every commit on a milestone agent's branch appears in exactly one of: the bundle's
> `evidence.commits[]` — and therefore in `history[].evidence` once it is replayed — or the
> orchestrator's `stopped` record for that milestone. A commit no `history[]` entry accounts for is
> the halt.**

Two halves, one per agent. **Agent side:** its final act is to return the bundle; an agent that
commits and then does anything else has violated the same rule one level down. **Orchestrator side:**
the milestone's spawn fields are written before the spawn and its id leaves `in_flight` only on a
completed replay or on writing `stopped` — an id in `in_flight` with neither is a halt nobody
recorded, which is a defect rather than a shape to copy.

Checkable by anyone, three commands, no judgement:

```bash
git -C <repo> log --format=%H <base_sha>..<branch>                     # every commit the agent made
jq -r '.history[].evidence.commits[]?' docs/graph-runs/<run-id>/state.json   # every one recorded
jq -r '.in_flight[]' docs/graph-runs/<run-id>/state.json                     # agents claimed in flight
```

**A sha in the first list and not the second ⟹ work exists that the trail does not account for. An id
in the third with no new `history[]` entries and no `stopped` ⟹ the agent died, or its replay was
forgotten.**

**No timestamps are generated inside Workflow scripts.** `Date.now()` and `new Date()` are
unavailable there — they would break resume by making cached results non-deterministic. Where a
timestamp is genuinely needed, the skill layer stamps it after the script returns.

---

## Resume

To resume a run — after a context loss, a crash, a `BLOCKED` pause, or a new session:

1. **Check `schema_version` first.** A value that differs from `SCHEMA_VERSION`, **or a missing
   `schema_version` key**, means the file was written by a different version of this spec —
   `BLOCKED`, naming both versions. Resuming under a changed topology reinterprets recorded history
   silently, which is worse than stopping.

   > **This is about `schema_version` and nothing else.** It read *"a mismatch or a missing field"*,
   > and **three orchestrators driving separate run-evals independently took it to mean any absent
   > key in the schema** — which would block on every hand-written fixture and on every run whose
   > optional fields are legitimately unset. `stopped` is `null` on a healthy run; `spec_path` is
   > null until `SPEC`; `trace` is absent on a run written before it existed. An absent optional
   > field is a value, not a version mismatch. **The only key whose absence blocks is
   > `schema_version` itself.**
2. **Read** the state file. **`node` is the run's position** — the node it is currently in. It is the
   run-level field and it stays; `milestones[].node` was the *per-milestone* one, written by ten
   nodes, read by no guard, and deleted. A milestone's own position is the last `history[]` entry
   carrying its id, and its completion is `delivered != null`.
3. **Re-derive the current node's progress from the world — do not trust it from the file.** The file
   says *which* node the run was in; it does not say how far that node got. Check directly: was the
   branch created? are the tests green? is the PR open? has it merged? The filesystem, git, and the
   host are the truth; the state file only says where to look.

> **`node` and `history[]` must agree, and a fixture is where they stop agreeing.** `node` is the
> node the run is *in*; the last `history[]` entry is how it got there, so `history[-1].to == node`
> on any run that has moved at all. A hand-written state file that sets `node` to one thing and
> leaves a trail arriving somewhere else describes no run. Two orchestrators driving run-evals hit
> exactly this and made opposite, defensible choices — which is why `run_scenario.py` now refuses a
> scenario whose seeded `node` and `ideal_artifacts` disagree.
>
> **The one exception is a halt**, below: `history[-1].to` is then `BLOCKED`/`HANDOFF` while `node`
> stays the node that failed, because that is where a resume has to pick the run up.

### Recording a halt

Seventeen node contracts declare an **`on failure`** exit — *"a step is not implementable as planned
→ `BLOCKED`"*, *"cyclic dependencies → `BLOCKED` naming the cycle"*, and so on. **None of them is a
numbered row in `edges.md`, and none ever will be.** They are not guarded transitions: nothing is
evaluated and nothing is chosen. The run stops.

So a halt is written like this, and the shape is not optional:

| | |
|---|---|
| `history[]` | one final entry — `{ from: <the node that failed>, to: "BLOCKED", guard: "", milestone }`. **`guard` is empty**, because no row declares it. |
| `node` | **stays the node that failed.** This is the only case where `history[-1].to != node`, and it is deliberate: `BLOCKED` is a status, not a place to resume from. |
| **when the RETURN GATE is what failed** | No node failed — the gate did, and the run never left the node it was in. `from` and `node` are both **that** node, and the fabricated one the bundle claimed is never entered. Writing `from: <the claimed node>` would strand resume at a node the run has never been in. |
| `status` | `BLOCKED` (or `HANDOFF` for the strategy-D park, which is not a failure). |
| `stopped` | carries the reason, `at_node`, `guards_tested[]` and `tried[]`. **This is where the `on failure` row's text goes** — it is the only record of *why*, since there is no guard to quote. |

> **Why this is written down.** `SKILL.md` § Validation requires every `history[]` entry to name a
> guard that appears in `edges.md`, and this file requires `guard` to quote it verbatim. Read
> together with the `on failure` rows, an orchestrator that halts correctly could not record having
> halted. An orchestrator driving a run-eval hit exactly that, resolved it by writing no halt entry
> at all, and reported the contradiction — which left the trail ending at a node with no exit,
> mechanically indistinguishable from a run that simply stopped being written to.
4. **Re-run the node from that point**, then evaluate its exit guards as normal.

Re-deriving rather than trusting is what makes resume safe. A run may have died *during* a node,
leaving partial work — a branch created but nothing committed, a PR opened but CI never watched.

> **There is no "entry guard".** Nodes declare **exit** guards only. Resume is a progress-rediscovery
> step, not a guard evaluation — the guards run afterwards, on the node's result.

**Clear `stopped` on resume** when its `kind` is `paused`: it described the stop that just ended, and
a stale one would make the next genuine stall look deliberate. A `blocked` one is cleared when the
human resolves the blocker; a `handoff` one is never cleared.

**An id in `in_flight` with no matching `history[]` block means its agent died in flight.** This is
the case delegation created, and the reason the milestone's `journal` and `base_sha` are written
before the spawn: they name where to look, so re-derivation has somewhere to start. Re-derive from
the world — `git log <base_sha>..<branch>` is what the agent actually did — then decide between
finishing the milestone in the orchestrator and re-spawning. **A re-spawn is counted in
`attempts["MILESTONE-dispatch:<id>"]`, never against the node budgets:** an agent that died reviewed
nothing, tested nothing and implemented nothing verifiable.

**Resume never rewinds `attempts` or `skipped_gates[]`.** A run that already burned two of three test
attempts resumes with one left. Resetting the counter would defeat the bound it exists to enforce.

**Who catches the graph's own death:** no node can — a run that dies mid-node writes nothing more
(Step Functions has the same boundary: catchers never cover top-level failure). The answer is the one
thing *outside* the run: the state file, written before every node.

### One counter, not two

Loop bounds are enforced **only** by `attempts["<CALLER>:<milestone-id>"]`. There is deliberately no
separate debug counter: `DEBUG` is re-entrant from six callers with different bounds, and a single
unscoped counter could not honour them — it would either block early by accumulating across callers,
or sit unused. `debug_return_to` carries routing and nothing else.

---

## The skipped-gate ledger

This is the field the whole design turns on.

Both `code-quality-pipeline` and `plan-guidelines` state that a gate must **never be reported as
passed when its tool was absent** — but in prose form nothing records the absence, so the rule is
unenforceable. Here it is mechanical:

- At each node, preflight resolves its `requires`.
- A missing tool appends to `skipped_gates[]` with the node, the reason, and the milestone.
- **The node may not be recorded as passed.** The run continues, but the gap is now durable.
- `CLOSE_OUT` copies every entry into the plan file's verification results.
- `DONE` **leads with** the skipped list. A run that finishes with a non-empty ledger is not a clean
  run, and the report must say so first, not in a footnote.

Append-only means installing the missing tool later does not retroactively pass the gate — re-run
the node.

**Under delegation the agent proposes and the orchestrator appends.** Preflight happens inside the
agent, which is the one part of the ledger the orchestrator cannot witness — so the bundle carries
`skipped_gates_proposed[]` and a per-node `preflight` assertion, and the orchestrator writes the
entries. Two rules make that safe:

- **The orchestrator never drops a proposed entry**, and adds its own for anything the bundle failed
  to prove — an unasserted preflight is itself a ledger entry. **The ledger is never smaller than
  what the agent proposed.**
- **A node with a ledger entry at this milestone may never be recorded as having PASSED.** The
  transition still happens: `edges.md` is authoritative for guards, and 10/13/17 route on the test
  state rather than on a gate's verdict, so a bare-ledgered gate advances the run with the pass
  claim withheld. What the entry bars is the claim, in `verified` and in any summary — never the
  hop. *(This bullet used to open "**No transition leaving a node on a pass-shaped guard may be
  recorded** while a ledger entry exists" and close "it bars the pass claim, never the transition",
  three sentences apart. An orchestrator driving a run-eval read the first sentence, found it would
  have blocked a legal `BRANCH → IMPLEMENT`, and followed R9 instead.)*

> **"Missing" means the run cannot obtain it — not that it is not there yet.** A tool the node could
> install in a command or two is *work*, and writing the entry instead is how a run buys a permanent
> record to avoid a two-minute install. This is not hypothetical: `E2E` lost Playwright from its
> `requires` for exactly this reason, after a real run ledgered it at milestone 1. Because the ledger
> is append-only the asymmetry is the whole point — **installing costs two commands, ledgering costs
> forever.**

---

## Task-list projection

The task list mirrors `milestones[]` at milestone grain (one task per milestone, seeded at
`STRATEGY`, label updated with the current node on every transition, closed at `MERGE`).

**It is a projection, never an input.** The graph writes to it and never reads from it. If the two
disagree, the state file wins.

---

## What was removed, and why

Four fields left this schema at version 5. Each of them cost a rule as well as a field, and the rule
went with it.

| Removed | Was | Why it went |
|---|---|---|
| **`milestones[].node`** | a per-milestone position, written by ten nodes | **Read by none.** It appeared in no node's `inputs` and in no guard. A milestone's position is the last `history[]` entry carrying its id, and its completion is `delivered != null`. It was not free: a real run wrote the invented value `GATE_B_PASSED` into it, and the answer was a paragraph enumerating the legal values (a node id · `null` · `CONSOLIDATED` · `MERGED`) and explaining why `MERGED` is deliberately not `MERGE`. **A field nothing reads acquired an invented value and got a rule instead of a delete.** |
| **`paused` + `blocked`** | two nullable objects | One question — *why is this run not moving* — answered twice, which forced a rule about which wins when a stop is also a halt. Now `stopped.kind`. |
| **`workflow_runs`** | a top-level map keyed `"GATE_A:<id>"` | A run-id belonging to one milestone's Gate A, stored at the root under a string-concatenated key. It is now `milestones[].gate_a_run_id`, where the thing it describes lives. |
| **`cursor.milestones`** | a second in-flight list | It shadowed nothing useful: `cursor.milestone` and `cursor.milestones` had to agree, so there was a check that they did. `cursor` is now a plain number and `in_flight` is the one list. **One list cannot disagree with itself.** |
