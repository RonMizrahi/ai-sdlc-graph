---
name: sdlc-graph
description: >-
  Drive a feature end to end through the full SDLC as an explicit guarded graph — spec, plan,
  branching strategy, then per milestone: implement, test, the two quality gates, PR, CI, merge —
  then close-out and an independent QA pass. Keeps typed run state in `docs/graph-runs/<run-id>/state.json`
  so a run survives context loss and resumes exactly where it stopped, enforces a bound on every
  retry loop, and records every gate that could not run instead of silently passing it. Invoke
  explicitly to start a run, resume one ("where were we?", "next milestone", "continue the run"), or
  report its status. This skill is never auto-triggered — running an entire SDLC is not something to
  enter on a description match.
when_to_use: >-
  run the SDLC, drive this feature end to end, start the graph, resume the run, where were we,
  next milestone, continue the plan, SDLC status
disable-model-invocation: true
user-invocable: true
argument-hint: "[start <feature> | resume | status] [--plan <path>] [--spec <path>] [--trace]"
---

# SDLC Graph

## Goal

One feature carried from idea to accepted, through an explicit state machine rather than a chain of
prose. The run leaves behind three things: **the work itself** (branches, PRs, merged code), **the
plan file** updated to reflect what actually happened, and **`docs/graph-runs/<run-id>/state.json`** — the
typed record of every transition, every retry, and every gate that could not run.

What the graph adds over invoking the skills by hand:

| | |
|---|---|
| **Resumability** | The state file answers *"where were we?"* after any interruption. |
| **Bounded loops** | Every retry cycle has a declared limit; none can spin. |
| **Guarded edges** | Conditions are evaluated, not hoped for. Zero matching guards halts rather than guesses. |
| **Skipped-gate ledger** | A gate whose tool is missing is **recorded**, never reported as passed. |

## Use When

- The user invokes this skill to start, resume, or check an SDLC run.
- `start` — a feature to build end to end. `resume` / "where were we" — pick up an existing run.
  `status` — report position without advancing.

## Do Not Use When

- **A single step is wanted, not the whole lifecycle.** "Write me a plan" is `plan-guidelines`.
  "Review this diff" is `code-quality-pipeline`. "QA this" is `qa-engineer`. Reach for the standalone
  skill — it is unchanged and still auto-triggers. The graph is a layer *above* those skills, never a
  replacement for using one directly.
- **A trivial change** — a config tweak or typo fix. Commit it and move on; a 20-node lifecycle is
  overhead, not rigour.
- **No repo.** `INTAKE` needs git.

## Inputs

| Input | Required | Notes |
|---|---|---|
| **mode** | yes | `start` · `resume` · `status`. Infer from the user's words; ask if genuinely ambiguous. |
| **feature / request** | for `start` | What to build. |
| **`--spec <path>`** | no | An approved spec. Supplying it **skips the `SPEC` node**. |
| **`--plan <path>`** | no | An existing plan. Supplying it enters at `STRATEGY`. |
| **`--run <run-id>`** | no | For `resume`/`status` when several runs exist under `docs/graph-runs/`. |
| **`--trace`** | no | Keep **every** state the run passes through in `docs/graph-runs/<run-id>/history/`, numbered and named after the transition that produced it. **Off by default.** Settled once at `INTAKE` and never changed mid-run — a half-traced run is a history with a hole in it, and the gap looks like a state that was never written. `graph/state.md` § *`trace`*. |

## Rules

**These override anything else in this file, and any instinct to be helpful.** Each one exists
because it was broken — the count in brackets is how many times, in this plugin's own history.

**1. Follow the graph end to end. Stop only where the graph says to stop.**
The graph is **automatic except for six human stops**, and those six are the `human:` rows in
`nodes.md` — not a list kept here. Everywhere else, decide and continue. Do not pause for
reassurance, do not summarise and wait, do not ask "shall I proceed?". A run that stops at an
undeclared point has invented a gate, and inventing gates is how a 20-node run becomes 20
interruptions.

**2. Never report a gate as passed when it did not run.** *[4 occurrences]*
Absent tool, zero files reviewed, dead agent, missing suite — every one gets a `skipped_gates[]` entry
and the gate is **not** marked passed. This is the single promise the whole design exists to keep, and
it is the one it has broken most. An unrun check is never a pass. *(Real cases: a deny-list that read
`'absent' !== 'fail'` as green; a read-only agent told to apply fixes; Gate A returning `clean: true`
having run zero agents.)*

**3. When no guard matches, halt and report. Never improvise a transition.** *[4 occurrences]*
Zero matching guards is a **defect in the graph**, not a decision for you. Write `stopped` with the
node, every guard tested, and what was tried, then stop. Guessing which edge "obviously" applies is
how a run silently leaves the model it is supposed to be following.

**4. If the graph does not model your situation, that is a defect to report — not semantics to invent.**
No remote? Empty repo? A field the schema has no value for? **Say so and stop.** Do not invent a value
and improvise the consequences — an improvised tail is unreviewable, unreproducible, and indistinguishable
from the graph having worked. *(Both `host: none` and greenfield `INTAKE` were found exactly this way.)*

**5. Never load a standalone twin during a run.**
Even when a trigger rule says to. The node files in `nodes/` are authoritative; loading
`plan-guidelines` mid-run pulls in its Phase 2, which *is* the milestone loop this graph already
drives. Live-dispatch skills are the exception and are expected.

**6. Never merge your own work, and never fake a green.**
`MERGE` waits for a human or a configured auto-merge. No skipped or deleted tests, no
`continue-on-error`, no `|| true`, no `.skip`, no lowered thresholds, no weakened assertions — at any
node, for any reason. A green earned that way is a failure of the node, not a pass.

**7. Never widen your own bounds.**
When a bound is exhausted, go `BLOCKED`. Do not grant yourself one more attempt because this one
"feels close". The bound is the disagreement between you and the graph, and the graph wins.

**8. Write the state file before the next node starts.**
Not at the end, not on a timer. A crash between two nodes must leave a file that says exactly where
the run was. Anything decided but unwritten does not survive, and a resumed run will not know it.
**The one exception is a verified milestone replay** (§ 4), where six nodes ran inside an agent and the
transitions are written on its return — still one at a time, in order, and only after the return gate
passes. What survives a crash *during* a milestone is the milestone's spawn record, written before the
spawn: it names the branch, the base sha and the journal, and resume re-derives the rest from git.

**9. Verify mechanically before reporting done.**
Grep it, run it, diff it. Re-reading your own work is the weakest check available — in this plugin's
history, cheap mechanical checks caught rename residue, two silently broken Markdown tables, and an
agent-cap guard that did not hold, all *after* the work was believed finished.

**10. A milestone agent's word is not evidence. Verify before you record it.**
Run the return gate; write nothing until it passes. A bundle whose gate cannot be evidenced is not a
fast milestone — it is Rule 2 happening one agent further away, and all four of Rule 2's occurrences
were a gate reported passed on somebody's say-so. The floor is at least one **world-sourced** check
per node: git for the commits, the suite re-run by you, the journal for the Gate A runId, the spec
files opened on disk. Never optimise those away because the bundle already said so.

**11. Your own work is ungated. Run § The orchestrator's own gate before every turn ends.**
Fourteen checks stand between an agent's bundle and the record. **Nothing stands between yours and
the record**, and that asymmetry is where this orchestrator's mistakes actually live — a run audited
against this file found four, all of them on the ungated side: a turn ended at an undeclared point,
two declared stops with no `stopped` written, and every orchestrator-authored `observation` over the
200-char cap while every agent-authored one obeyed it. **The discipline exists where it is checked.**
So check yourself, mechanically, at the one moment that catches all of it — before the turn ends.

---

## Workflow

**Load `graph/nodes.md`, `graph/edges.md` and `graph/state.md` before the first
transition.** They are the authoritative model — 20 node contracts, 40 guarded transitions, and the
state schema. Do not work from memory of this file's summary; the reference files are the spec.

### 1. Establish the run

- **`start`** → run `INTAKE`: classify the request, detect `stack` / `has_ui` / `main_branch` /
  `host`, then **make the run directory ignorable before you make it**: append `docs/graph-runs/` to
  the project's `.gitignore` (creating the file if there is none, no-op if the entry is already
  there), and only then create `docs/graph-runs/<run-id>/state.json`. A run is working memory, not a
  commit — and the order matters, because a state file written before the ignore rule lands is a
  tracked file every later `git status` has to explain away. That one `.gitignore` edit is committed
  with the spec on the first branch `BRANCH` creates. **State `has_ui` explicitly in the intake
  summary** — it decides whether the `E2E` node exists for the entire run.
  **Then invoke `/sdlc-graph:onboarding` — every run, no exceptions — and relay its checklist.**
  It reports, tool by tool, what this session can actually invoke and the install line for each gap.
  Every tool on that roster is **third-party and optional**; the graph requires `git` and nothing
  else. **It is advisory: it emits nothing, you do not wait on it, you do not route on it, and it
  can never stop, delay or block the run — it is not a seventh human stop.** If it fails or returns
  nothing, say so in one line and continue in the same turn. Preflight (§ 2) still ledgers every
  absence at the node that needed the tool; the checklist only says so earlier.
- **`resume` / `status`** → **check `schema_version` first**, then read the state file and
  **re-derive the current node's progress from the world** — was the branch created? are the tests
  green? is the PR open? has it merged? The filesystem, git, and the host are the truth; the state
  file only says where to look. A run may have died *during* a node, leaving partial work.
- For `status`, report and stop. Do not advance.

### 2. Preflight the node's `requires`

Before running any node, resolve the external tools its contract declares. **A missing tool appends
to `skipped_gates[]` with its reason and the node may not be recorded as passed.** Never silently
proceed as though the gate ran.

### 3. Run the node

Dispatch per its `owner`:

- **milestone agent** — `BRANCH`, `IMPLEMENT`, `TEST`, `GATE_A`, `E2E`, `GATE_B` and their `DEBUG`
  round-trips. **You do not run these.** In this order, every time:

  1. **Write the milestone's spawn record first** — `base_sha`, `main_sha_at_spawn`,
     `spawned_at_history_len`, `journal` (the path the agent will write), and its id into
     `in_flight`. An agent that dies before its first append still has to be findable.
  2. **Arm the monitor *before* the first spawn**, so no node completion is missed. **Name the
     journals explicitly — never a glob:**

     ```
     Monitor({ command: "tail -n +1 -F docs/graph-runs/<run-id>/journals/milestone-1.jsonl "
                        "docs/graph-runs/<run-id>/journals/milestone-2.jsonl | "     // one path per milestone spawned
                        "grep --line-buffered -v -e '^==>' -e '^$' | " // tail's per-file headers
                        "jq -Rc --unbuffered 'fromjson? // (.+\"}\"|fromjson?) // empty "
                        "| select(.event != \"heartbeat\")'",   // one bad line must not exit jq
               description: "sdlc-graph milestones — node completions, run <run-id>",
               persistent: true })
     ```

     > **The `grep` is not optional under C, and its absence is invisible under A and B.** Watching
     > more than one file makes `tail` print a `==> path <==` header and a blank line before each
     > file's output. `jq` rejects the header — *"parse error: Invalid numeric literal"* — and
     > **exits**, killing the monitor on its first line. With one file `tail` prints no header at
     > all, so A and B work and C dies, which is the strategy running the most agents and the one
     > where going blind costs most. Found by an orchestrator driving scenario 05: it armed the
     > monitor correctly, lost it immediately, and diagnosed it from the exit code.

     > **`-R` + `fromjson?` is not defensive tidiness — a plain `jq` dies on ONE bad line, and the
     > agent writing those lines is the one you are watching.** The `==>` case above is the same
     > failure from a friendlier cause: `jq` **exits** on any parse error, so a single malformed
     > journal line ends the monitor for the rest of the run. **Observed in a real run:** a milestone
     > agent serialized `detail` with a dropped closing brace, and *its `node_done` lines were the
     > malformed ones* — the orchestrator got `BRANCH` and then silence, while that milestone ran
     > `IMPLEMENT → TEST → GATE_A → E2E → GATE_B` completely unseen. It only noticed because the state
     > file still said `BRANCH` long after the branch existed. **The agent that emits the bad line is
     > precisely the agent whose progress you lose**, so the blast radius is never a single line.
     >
     > Raw-input mode makes each line a string, `fromjson?` yields nothing instead of erroring, and the
     > `+ "}"` retry recovers the one-dropped-brace case rather than merely surviving it. Anything still
     > unparseable is skipped and the stream continues. **Never let a malformed line be fatal** — a
     > monitor you believe is watching is worse than none, which is the whole reason the monitor agent
     > was retired.

     > **A glob here is silent blindness, and it is not a subtle failure.** At arm time — before the
     > spawn, which is the whole point — the journals do not exist, so `docs/graph-runs/<run-id>/journals/milestone-*.jsonl`
     > matches nothing and the shell fails the pipeline *before `tail` starts*. `Monitor` comes up,
     > reports no error, and delivers nothing for the entire milestone. **Five orchestrators driving
     > run-evals hit this independently**, every one blind while believing it was watching: exactly
     > the failure the monitor agent was retired for, rebuilt in its replacement. `tail -F` on an
     > **explicit** path waits for a file that does not exist yet, which is why naming them works and
     > globbing cannot. Do **not** `touch` the journals to make a glob work — `workflow-dispatch.md`
     > § *The milestone journal* gives each file exactly one writer, and that writer is the agent.

     **The filter must pass `blocked` as well as `node_done`.** A monitor that greps only for good
     news is silent through a crash, and silence is indistinguishable from work. Heartbeats are
     excluded on purpose: they would make the stream chatty enough to be auto-stopped, and a monitor
     that was stopped while you believe it is watching is worse than none. Read them from the file
     when diagnosing a stall. **Re-arm on any re-spawn**, adding the new journal's path — a re-spawn
     writes a new file, and a monitor armed on the old path never sees it.
  3. `Agent(subagent_type: "sdlc-graph:sdlc-graph-milestone", run_in_background: true, …)` — one
     per milestone, and under C **all of them in a single message**. **Background is not optional:**
     your turn has to end for the monitor's notifications to reach you, and a blocking dispatch makes
     you deaf for the whole milestone — the exact window this is here to close. **Record the returned
     agent id in `milestones[<id>].agent_id`**; it is the only handle for asking that agent anything
     later, and it exists nowhere but the transcript otherwise.

  Each agent returns one typed bundle; you run the return gate and replay it (step 4). Brief contents,
  `MILESTONE_BUNDLE`, the journal and the gate itself: **`subagents/workflow-dispatch.md`.**
- **`nodes/<name>-node.md`** — a graph-scoped copy of the source skill. Load and follow it.
  **If the copy is absent**, see *If a node file is missing* below. The four twins the agent loads —
  `plan-guidelines` § BRANCH, `testing-standards`, `code-quality-pipeline`, `systematic-debugging` —
  are loaded **by the agent, not by you**; loading them yourself is how a milestone gets driven twice.
- **live dispatch** — invoke the installed skill by name (**the project's own coding-standards
  skill** for the detected stack, `code-simplifier`, `security-review`, `claude-md-improver`, …).
  **Coding standards and external tools are always the current installed version, never a copy** —
  reviewing code against a stale rulebook is worse than the coupling a copy would remove. This
  plugin bundles no coding standard and names none: whatever the project has installed for its
  stack is what `IMPLEMENT` dispatches, and nothing installed is a `skipped_gates[]` entry.
  **If a dispatched skill runs its own approval handshake** — a coding-standards skill may end one
  with *"never start the actual work until the user has approved"* — supply
  `context.standards_handshake`, settled once at `STRATEGY`. The graph does not get to ignore
  another skill's approval rule: satisfy it early, never silently override it.
- **workflow script** — `GATE_A` fans out via `workflows/gate-a.workflow.js`; see
  `subagents/workflow-dispatch.md`.
- **`inline`** — `INTAKE`, `CONSOLIDATE`, `MERGE`, `VERDICT`, `DONE`: this skill performs them.
- **`PR_FINAL_REVIEW`** — live dispatch of `code-review:code-review` with `--comment` on the now-open PR. The one node where that tool is invocable; `GATE_B` uses the built-in `code-review` with a branch range instead.

#### If a node file is missing

Every node named in `nodes.md` has its `nodes/<name>-node.md`. If one is ever absent, do **not**
improvise: live-dispatch the standalone skill, **apply that node's documented trim by hand**, and
append a `skipped_gates[]` entry recording the substitution. Two trims are load-bearing —
`plan-guidelines` Phase 2 must be skipped (the graph drives the milestone loop) and `pr-mr-prepare`
Step 4 must be skipped (Gate A and Gate B already ran) — because running them would double-drive the
loop and duplicate the gates.

### 4. Evaluate exit guards and transition

Evaluate the node's guards **in the order `edges.md` lists them**. Exactly one must match.

- **Zero matching guards is a defect, not a stall.** Halt with `status: BLOCKED`, write `stopped`
  naming the node, every guard tested, and what was tried. **Never guess a transition.**
- Write the state file **before the next node starts** — the new `node`, the appended `history[]`
  entry, the finished node's `emits`, and any `attempts` increment.
- **Every `history[]` entry carries an `observation`**: one line on what actually *happened* in the
  node you just left, not what the guard says. "3 of 45 files had findings, all bugs, none style"
  beats "gate A completed". **Say the awkward thing** — a node that passed but only just, a retry that
  fixed a symptom rather than a cause, a gate that ran degraded. This is the only per-node record that
  exists, and with no live auditor watching, it is the only place a bad run shows up before its
  verdict.
- Update the in-flight milestone's task label with the node just entered (see *Task list*, below).

#### While a milestone agent runs — watching, not waiting

Node completions arrive as monitor notifications. On each one:

1. **Update the provisional fields only** — `milestones[<id>].progress.{at_node, headline, seen_at}`
   from the journal line. **Do not touch `history[]`.** You now know `TEST` went green, and nothing
   has been checked: the suite has not been re-run, no sha looked up, no spec file opened. Writing the
   transition now would turn the return gate from the thing that decides what enters the record into
   a review of rows already in it, and a gate that runs after the write cannot refuse.
   `state.md` § *Provisional is not recorded*.
2. **Read `detail` only when you need it.** The headline is pushed and cheap; the record is 1–2k
   tokens and sits on disk until something makes it worth reading — a decision you have to make, a
   question you have to answer, an agent you are about to brief.
3. **Watch for silence.** `seen_at` older than the heartbeat window means the agent is dead or hung,
   not slow. Confirm from the journal's tail, then treat it as an agent failure: the
   `MILESTONE-dispatch` retry, charged to that key and never to the node budgets. **Waiting longer is
   not a diagnosis** — an indefinite wait on a dead agent is the failure this whole channel exists to
   end.

**Two moments where reading the records is mandatory, not optional:**

- **Before spawning an agent whose milestone has `deps`** — read every parent's `delivered` and the
  relevant `detail.interfaces`, and put what matters into the new brief. A dependent milestone briefed
  without its parents' output is the whole failure C exists to avoid.
- **At `CLOSE_OUT`** — read every milestone's records to write the plan file's outcome section. That
  is the run's own account of itself, and per-hop observations do not add up to one.

#### Asking a milestone agent for more

An agent keeps its context after it returns, and `milestones[<id>].agent_id` reaches it. When a record
does not answer something — *why did the auth interface change?*, *what did the failing assertion
actually say?* — **ask the agent that was there** rather than reconstructing it or carrying that
context yourself all along. That is the point: total recall on request, paid for only on request.

Two limits, and they are not soft:

- **Questions only. Never an instruction.** Telling a returned agent to fix, change, commit or
  re-enter anything re-drives a milestone outside its itinerary, outside its preflight, and outside a
  return gate that has already passed on its bundle — every guarantee this architecture buys, spent in
  one message. Real work needs a **new agent**, with its own budgets and its own gate. The agent is
  told to decline; do not put it in that position.
- **An answer is not evidence.** It is prose from the same agent the gate exists to check. It informs
  you; **it never satisfies an R-check.** If an answer would change routing, verify it against the
  world first — the world-sourced floor is unchanged.

  > **It may, however, supply a missing `observation`** — and only that. `workflow-dispatch.md`
  > § *Five outcomes* calls this **Re-obtainable**: the evidence is sound, and the one field the
  > orchestrator may not author is empty. An answer is the same agent's words about a node it was
  > present for, which is exactly what an `observation` is; nothing routes on it, so no R-check is
  > being satisfied. **Say where it came from in `verified`.**
  >
  > This line read *"never becomes an `observation`"*, which contradicted *Re-obtainable* outright —
  > on the one field that rule names, in the one scenario built to test interrogation. The
  > orchestrator driving it found both rules and could obey only one. **The distinction is evidence
  > versus authorship**: ask for what only the agent can author and nothing routes on; never ask for
  > a fact the gate checks — `dispatch`, a `run_id`, a sha. Those come from the artifact or the node
  > is re-run.

**Best-effort by nature.** A returned agent's context does not survive a session rollover or a crash.
When the agent is gone the answer is gone, and the journal is what remains — which is the argument
for the record being *written*, not for this tier being relied on.

#### Replaying a milestone agent

An agent returns six transitions at once, so this step runs **after** it comes back rather than
between its nodes. The order is not negotiable:

1. **Run the return gate** — `workflow-dispatch.md` § *The return gate*, R0–R13. **Write nothing
   until it passes.** Budget ≤ 20 lines of output: redirect every command to a file and read an exit
   code, a count, or a tail line.
2. **Evaluate each guard yourself**, in `edges.md` order, on the facts in the bundle — not on the
   agent's `claimed_to`. A disagreement between the two rejects the bundle.
3. **Write one transition at a time, in the agent's order.** Each write is a real write: `node`, the
   `history[]` entry, that node's `emits`, any `attempts` increment. Never one edit carrying six.
4. **Carry both authors across.** `observation` is the agent's, verbatim — you may neither rewrite it
   nor invent one, and an empty one is a rejected bundle. `verified` is yours: name what you checked
   and what you found.
5. **Append every proposed ledger entry**, plus your own for anything the bundle failed to prove.
   The ledger is never smaller than what the agent proposed.
6. **Record `milestones[<id>].delivered`** from the bundle's `notes`, corrected against what you
   verified. This is the milestone's own answer to *what does it now provide, and what must the next
   one know* — the thing `history[]` cannot say, and what every dependent brief is built from. A
   `completed` bundle with an empty `notes` is a rejected bundle, not a blank to fill in yourself.
7. **Null `milestones[<id>].progress` and drop the id from `in_flight`** as the replay finishes.
   `progress` described an agent that no longer exists, and `in_flight` is the run's only statement
   about what is running — an id left in it with no transitions and no `stopped` is the halt
   signature.

   **Keep everything else on the milestone.** `base_sha`, `spawned_at_history_len`,
   `main_sha_at_spawn`, `journal`, `gate_a_run_id` and especially **`agent_id` survive the replay**.
   This was a real defect: the whole record used to be cleared here, which deleted `agent_id` at
   exactly the moment it became useful — interrogation happens **after** the return, so the handle was
   destroyed one step before the only step that needs it. The journal file stays too: it is the run's
   record of how the milestone was built, and `audit_run.py` reads it afterwards.

8. **Do NOT end the turn here.** Evaluate `GATE_B`'s exit, and when it is edge 15, **write the next
   milestone's spawn record, re-arm the monitor, and spawn its agent — in this same turn.** Only then
   report. The replay boundary is the single most common place this orchestrator stops with nothing
   wrong: a milestone is a big, satisfying piece of work, so finishing one *feels* like a reporting
   point, and O1 says it is not one. **Observed in a real run** — five milestones replayed, four of
   them correctly continued straight into the next spawn, and the fifth ended the turn with
   `status: RUNNING`, `in_flight: []`, `cursor` pointing at a milestone that had no agent, and
   `stopped: null`. Nothing had failed; the graph simply stopped, and the file could not say so.

   Writing the summary before the next agent is running is the tell. **Spawn, then narrate.**

**A rejected bundle is not a slow milestone.** Repairable → write with your corrections, named in
`verified`. Unproven gate → re-run that node yourself, against **that node's** bound — except a `GATE_A` whose
dispatch ran zero agents, charged to `attempts["GATE_A-dispatch:<id>"]` and never to the findings
budget. Fabricated →
`BLOCKED`, naming the R-check that failed. Never repair a fabrication silently.

### 4b. The orchestrator's own gate — O1–O7, before every turn ends

The return gate in `workflow-dispatch.md` checks everything an **agent** claims. **Nothing checks
what you do**, and a run audited against this file found four defects, every one of them on the
ungated side. So the symmetry is restored here: **before you end a turn, run these seven.** They are
cheap, they are mechanical, and each one exists because it was broken.

| # | Check | The failure it catches |
|---|---|---|
| **O1** | **Am I at one of the six `human:` rows in `nodes.md`, or a `run_mode` stop I declared at `STRATEGY`?** If not, **the turn does not end** — evaluate the guard and start the next node now. Announcing what you are about to do is not doing it. | The `IMPLEMENT` halt, and its twin at a **replay boundary** — **the one that actually recurs.** Two real cases: an orchestrator that wrote a milestone's transitions, said "spawning the next one now", and stopped; and one that replayed five milestones, continued correctly after four, and after the fifth ended the turn on a summary — `RUNNING`, `in_flight: []`, `stopped: null`, a `cursor` with no agent behind it. Finishing a big piece of work *feels* like a reporting point at every node, not just `IMPLEMENT`. **The next spawn happens BEFORE the summary** (§ *Replaying a milestone agent*, step 8) |
| **O2** | If I **am** stopping: is `stopped = { kind: "paused", reason, at_node }` **written to disk**? | Two of three declared stops in a real run had no `stopped` record. A quiet `RUNNING` file is byte-identical between "working", "waiting for you", and "dead" — which is the entire reason the field exists |
| **O3** | Every `history[]` entry I wrote this turn: `observation` **≤ 200 chars**, `verified` **≤ 300**, neither empty on a replayed hop, no secrets in either. | In the audited run **all four** orchestrator-authored observations were over — 365, 461, 581 and 775 chars — while **all five** agent-authored ones fit. The return gate caps the agent's; nothing capped the orchestrator's |
| **O4** | `history[-1].to == node` — except on a halt, where `node` stays the node that failed. | A trail that arrives somewhere the run is not describes no run, and resume picks up in the wrong place |
| **O5** | Every id in `in_flight` has either a live agent or a `stopped` record; every completed replay cleared its id and nulled its `progress`. | The halt signature — an agent died and nobody wrote it down |
| **O6** | Every node entered this turn incremented `attempts["<NODE>:<id>"]`; no key exceeds its bound; a dispatch failure went to its **own** key. | An uncounted loop, and a findings budget spent on a harness crash |
| **O7** | **Did I read the guard I just used, in `edges.md`, this turn — or did I recall it?** Quote it verbatim into `history[].guard`. | Guard text drifts from memory faster than anything else here, and a paraphrased guard cannot be matched against the table mechanically |

**O1 is the one that actually gets broken**, so read it as the default: *the turn continues unless a
declared stop says otherwise.* If you find yourself wanting to stop anywhere else — to summarise, to
report a milestone, to check something reads well — that is not a stop, that is a sentence you can
write **after** the next node has started.

### 5. Respect the bounds

**`edges.md` § Loop bounds is the authoritative list, and the only one.** Ten cycles exist, stated
there in five rules; every one is bounded. This file used to summarise that table under a rule saying
it "must never disagree with it" — which is a copy plus a hope, and it needed two spec checks to hold.

Two things worth knowing without opening the file:

- **A `DEBUG` round-trip is bounded by its *caller's* `max attempts`**, keyed `"<CALLER>:<milestone>"`.
  `TEST`'s budget on milestone 2 is `"TEST:2"` and is independent of `GATE_B`'s.
- **A dispatch failure has its own key and that is not cosmetic.** A `GATE_A` workflow that dies
  without running a single agent is not a review finding and must not spend the findings re-run
  budget. Observed in a real run: a checkpointed, unresumable dispatch consumed the findings budget,
  so the *actual* Gate A pass that followed had none left — a genuine bug would have exited via
  "budget spent" instead of getting its re-review. **A harness crash can silently downgrade a security
  re-review.** Count a harness failure in `GATE_A-dispatch:<id>`, a dead agent in
  `MILESTONE-dispatch:<id>`, and a real finding in `GATE_A:<id>`.

**Counters are never reset, only keyed.** Per-milestone keying already gives each milestone a fresh
budget. Resume inherits the counter it left behind — rewinding it hands a stuck loop an unlimited
budget.

### 6. Stop for the human — in six places, and nowhere else

**The six stops are the `human:` rows of the node contracts in `nodes.md`, and that is the whole
list.** They are `SPEC` and `PLAN` (`approval-after`), `STRATEGY` (`choice-after`), `PR`
(`confirm-before`, and only when `auto_open_mr == false`), `MERGE` (`await-external`) and `VERDICT`
(`escalation`, and only once the 2nd reopen is spent).

*(This file carried a second table of them for two releases. It drifted to eight rows under a heading
that said six, because two `STRATEGY` sub-questions were added as rows. One list, in the file that
declares the field.)*

**Every deliberate stop writes `stopped: { kind: "paused", reason, at_node }` — and resume clears
it.** This is what makes an intentional wait distinguishable, on disk, from the `IMPLEMENT` halt: a
quiet `RUNNING` file with `stopped` set is someone waiting for you; without it, it is a stall, and
anyone reading the file — you, the user, the viewer — is entitled to read it as one. Applies to the
six stops, to `checkpoint`/`on-exception` returns, and to `HANDOFF`.

**Ask at these six; never infer them. Never add a seventh.** If you find yourself wanting to stop and
confirm somewhere else, that is a defect in the graph to raise — not a judgement call to make mid-run.
Every other node (`IMPLEMENT`, `TEST`, `GATE_A`, `E2E`, `GATE_B`, `CI`, `DEBUG`, `CONSOLIDATE`,
`CLOSE_OUT`, `QA`) runs start to finish without asking anything.

> **`IMPLEMENT` is where this actually goes wrong.** Two real runs halted there with
> `status: RUNNING` and `stopped: null` — nothing failed, the graph just stopped. It is the longest,
> most open-ended node, so finishing the code *feels* like a reporting point. **It is not.** When the
> last step is committed, continue to `TEST` in the same turn. If a per-milestone look is wanted, that
> is `run_mode: "checkpoint"`, chosen at `STRATEGY`.

**`run_mode` can add declared stops, and only declared ones.** `continuous` (default) is the six.
`checkpoint` adds one after every milestone's `GATE_B`. `on-exception` adds one whenever a gate is
skipped, a bound is exhausted, or a bundle was rejected. All three are settled at `STRATEGY`.

### 7. Report at the terminal state

| Status | Meaning |
|---|---|
| `DONE` | Reached the end. **Not necessarily clean** — lead the report with `skipped_gates[]`. |
| `BLOCKED` | Something failed. `stopped` holds the node, guards tested, and what was tried. Resumable. |
| `HANDOFF` | A deliberate stop, nothing wrong — strategy D only. Needs action, not diagnosis. |

## Companions — the viewer, the tooling check, and the evals

Three things sit alongside the graph. **None is a node, and none may gate a run.**

| | What it is | When |
|---|---|---|
| **`sdlc-graph-viewer`** — a separate plugin, declared as a **dependency** of this one | Live and snapshot HTML views of the run; one server per project. | Installed and enabled with the graph. Invoke at run start; if it is somehow not invocable, one line and carry on. Never a gate. |
| **`/sdlc-graph:onboarding`** — a skill in this plugin | The tooling checklist: which of the roster in `docs/DEPENDENCIES.md` this session can invoke, the install line for each gap, and what a run does without it. **All of it third-party and optional.** | **Invoked at `INTAKE`, on every run**, and by a human any time. **It installs nothing, emits nothing and gates nothing** — it cannot stop or delay a run. |
| **`evals/`** — the graph checked against itself | The spec files agreeing, scripted runs covering every node and every transition, the offline auditor's own self-tests, and the Gate A script's runtime harness. | `python3 evals/run_all.py`, and before changing anything in this plugin. |

**There is no live auditor.** This graph used to spawn one alongside every run; it does not any more,
and `observability/observability.md` says what carries that weight instead. You *do* see a run while it
happens — each milestone's journal reaches you node by node — but that is **your own** telemetry, not
an independent look, and nothing routes on it. The outside look is `evals/audit/audit_run.py`, run
afterwards by someone who was not there.

**→ `observability/observability.md`** for the viewer's fallback and why neither companion may gate.
**→ `evals/EVAL-INSTRUCTIONS.md`** for what a change to this graph owes in tests. A change is not
finished until it adds the eval that would have caught its absence.

## Task list

Progress is mirrored to the task list at **milestone grain** — seeded at `STRATEGY` (one task per
milestone), the in-flight task's label updated with the current node on every transition, closed at
`MERGE`. It is a **projection, never an input**: the graph writes to it and never reads from it. If
the two disagree, the state file wins.

## Output Contract

1. **`docs/graph-runs/<run-id>/state.json`** — written on every transition. The durable record.
2. **The plan file** — updated at `CLOSE_OUT` with milestone statuses, key decisions, verification
   results, every `skipped_gates[]` entry, and the QA verdict + `qa_plan_path`.
3. **A final report** — position, what shipped, **what was skipped and why**, and any follow-ups.

## Validation

A run is correctly executed when:

- **Every transition is in `history[]`**, and each names a guard that appears in `edges.md` —
  **except the final halt entry**, whose `guard` is empty because an `on failure` exit is not a
  guarded transition and no row declares it. `stopped` carries its reason instead. See
  `state.md` § *Recording a halt*.
- **No node was recorded as passed while its `requires` was absent** — cross-check `history[]`
  against `skipped_gates[]`.
- **No cycle exceeded its bound.**
- **`CLOSE_OUT` copied every `skipped_gates[]` entry into the plan file**, and `DONE` led with them.
- **The state file alone is enough to resume** — no decision lives only in conversation.
- **Every confirmed QA finding became a committed test** before `DONE`.

## Guardrails

- **Never merge the graph's own work.** `MERGE` polls until a human or configured auto-merge lands
  the PR, and blocks if it is closed unmerged.
- **Never fake a green.** Skipping or deleting tests, `continue-on-error`, `|| true`, lowered
  coverage thresholds, `.skip`, or weakened assertions are forbidden at `TEST`, `E2E` and `CI`.
- **Never report a gate as passed when its tool was absent.** That is what `skipped_gates[]` is for.
- **Never write secrets to the state file** — it is committed to the project repo, permanently.
  `qa_env.identities` holds identifiers only; no credentialed connection strings; no command output
  in `history[]` or `stopped.tried[]` (CI logs carry tokens).
- **Never guess a transition.** Halt instead.
- **Never modify the standalone skills.** They are unchanged and independently usable; this graph
  sits above them and must never become a dependency of them.
- **Never LOAD a standalone twin during a run — not even when a trigger rule says to.** A project or
  global `CLAUDE.md` may carry a mandatory "about to plan → load `plan-guidelines`" style trigger.
  **While this graph is running, those triggers are suspended**: the node files in `nodes/` are
  authoritative. Loading `plan-guidelines` mid-run pulls in its Phase 2 — which *is* the milestone
  loop this graph already drives — and double-drives it into two branch creations and two MR flows per
  milestone. Loading `pr-mr-prepare` re-runs the quality pipeline `GATE_A` and `GATE_B` already ran.
  The eight twins are: `brainstorming` · `plan-guidelines` · `testing-standards` ·
  `code-quality-pipeline` · `pr-mr-prepare` · `watch-ci` · `systematic-debugging` · `qa-engineer`.
  **Live-dispatch skills are the exception and are expected.**
- **`/batch` cannot be invoked by a skill.** Strategy D writes the plan, stops at `HANDOFF`, and
  tells the user to run it.

## References

- **`graph/nodes.md`** — the 20 node contracts, the figure, and the `human:` rows that *are* the
  six stops. Load before the first transition.
- **`graph/edges.md`** — 40 guarded transitions, the ten bounded cycles in five rules, terminal
  states. **Authoritative for every guard.**
- **`graph/state.md`** — run-state schema, write points, resume, the skipped-gate ledger.
- **`subagents/workflow-dispatch.md`** — the Gate A script, the milestone agent, the brief, the
  bundle, the journal, and the return gate R0–R13.
- **`nodes/<name>-node.md`** — the eight graph-scoped node procedures. `nodes/qa/` holds
  the QA playbook, taxonomies and plan template that travel with `qa-engineer-node.md`.
- **`observability/observability.md`** — the viewer: when to offer it, what to relay, why it may not
  gate the run, and what replaced the auditor this graph no longer spawns. Load at run start.
- **`evals/EVAL-INSTRUCTIONS.md`** — **load before changing anything in this plugin.**
- **`evals/README.md`** — what each suite and fixture covers, and how to run them.
