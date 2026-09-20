---
name: sdlc-graph-engineering-install
description: >-
  Install graph engineering into a project: take an existing process — skills, a runbook, a README, a
  CI pipeline, or something the user can only describe out loud — and scaffold it into a working
  guarded graph with typed nodes, total exit guards, bounded retry loops, a durable run-state file,
  and a ledger recording every step that could not run. Writes the orchestrator skill and its model
  files into the target project, then proves the result sound by dry-tracing it before handing it
  over. Use this WHENEVER someone wants a multi-step process made resumable, auditable or reliable —
  "set up graph engineering here", "turn my workflow into a graph", "make this process a state
  machine", "my agent loses track halfway", "it retries forever", "it says it did things it didn't
  do", or when a prose runbook has grown too many conditionals to follow. Builds from scratch for any
  domain and needs no particular skills installed.
when_to_use: >-
  install graph engineering, set up a graph for this project, turn my workflow into a graph, build a
  state machine from my process, make this runbook executable, my agent forgets where it was, it
  loops forever, it claims steps it skipped
---

# Install Graph Engineering

## Goal

**Graph engineering, installed into a project that does not have it.** One existing process, turned
into a model a machine can actually execute: **nodes** with typed contracts,
**edges** with total guards, **bounded** cycles, a **run-state file** that survives a crash, and a
**ledger** of every step that could not run. Plus the orchestrator skill that walks it.

**The output is four files, written into their project, and a proof.** Not a diagram — diagrams are
the easy part. The deliverable is something they can run.

## Use When

- A prose process has grown enough conditionals that nobody can hold it in their head.
- An agent loses its place partway through a long task and restarts from guesswork.
- A retry loop has no limit, or a step reports success it did not earn.
- Someone wants a process auditable — "which steps actually ran, and which were skipped?"

## Do Not Use When

- **The process is genuinely linear** with no branching, no retries, and no human stops. A checklist
  is the right tool; a graph is overhead.
- **The steps are one action each.** A graph earns its cost across steps that can fail, retry, or be
  skipped — not around a single tool call.
- **The process is software delivery and `sdlc-graph` is installed.**
  That graph already exists — use it. This skill is for installing a *new* graph for a process that
  has none. It is also the worked reference for everything here, and worth reading when a rule below
  is unclear: total guards, per-item and per-dispatch attempt keys, a run directory, an append-only
  ledger, and a generated observability surface with a drift checker on the mirroring side.

## Inputs

| Input | Required | Notes |
|---|---|---|
| **the process** | yes | Skills, a runbook, a README, a CI config, an existing script, or a conversation. Anything that describes the steps. |
| **domain** | yes | What this graph is *for*. Shapes node names and what counts as a failure. |
| **target** | no | Which project to install into, and where. Default: a new skill in the user's own plugin or `.claude/skills/`. **Confirm the destination before writing.** |

**You need no particular skills installed.** If the user has some, their steps become nodes; if they
have only a description, interview them. The method is the same.

---

## Workflow

### 1. Inventory the steps — do not design yet

List every step the process performs, in the user's own words. Read whatever they have: skill files,
scripts, docs, CI config. Where the source is a conversation, ask **one question at a time.**

Two things to capture per step that people habitually omit:

- **What it needs to have happened first** — this becomes an input, and later an edge.
- **How it can fail** — not just succeed. Most prose processes describe only the happy path, and that
  omission is where the defects live.

### 2. Decide what is a node

A step is a **node** when it can fail, retry, be skipped, or be resumed into. A step that always
succeeds and always leads to the same next step is not a node — fold it into its neighbour.

**Fewer nodes with real contracts beat many nodes with vague ones.** Aim for the smallest set where
every one can be described by the contract in step 3.

### 2b. Source each node's procedure — dispatch it, or copy it

When the process you are converting **already exists as skills**, this is the step that converts them,
and getting it wrong is how a graph starts fighting its own sources. Each node's procedure arrives one
of two ways:

| | Use when | Cost |
|---|---|---|
| **Live dispatch** — invoke the installed skill by name at run time | The source is a **standard, rulebook or external tool** whose content must never be stale | Coupling: the graph depends on it being installed. Handle with `requires` + a ledger entry, never a crash |
| **Copy** — a trimmed, graph-scoped file the node reads | The source contains **its own orchestration** — a loop, a sequence, an approval flow — that the graph now drives itself | Drift: two files that can disagree |

**The deciding question is not "how big is it" — it is "does it drive anything?"** A source that only
*describes how to do one thing* should be dispatched live: a copied coding standard that drifts means
writing and reviewing code against a stale rulebook, strictly worse than the coupling a copy removes.
A source that *sequences several things* must be copied and trimmed, or you get **two orchestrators
driving the same work** — see failure mode 14.

**What to trim from a copy**, in every case:

- the **loop or sequence the graph now owns** — this is the whole reason you copied it;
- **standalone framing**: trigger phrases, "load this skill before…", hand-offs to the next skill —
  all of it contradicts the graph's sequencing;
- **dependency warnings** that have become the node's `requires` row.

**Every copy carries its provenance in the file**, or it is unmaintainable within a month:

```
<!-- copied-from: <source path> @ <version> -->
<!-- trimmed: <what was removed, and why the graph owns it instead> -->
<!-- diverged: <deliberate differences, who decided, when> -->
```

### 2c. Copies create twins — write the two rules down now

The moment a copy exists, the source and the copy are **twins**, and both rules below belong in the
project's own instructions, not in your memory:

1. **Never load the standalone twin during a run.** It is not merely redundant — it re-introduces the
   orchestration you trimmed, and the loop runs twice. Name the twins explicitly; a rule that says
   "avoid loading related skills" is unenforceable.
2. **Changing either side is a human decision.** Ask which side a change belongs to — and remember
   that **divergence is often correct**: the copy was trimmed on purpose, so "make them identical" is
   the wrong default. Record the answer in the `diverged:` header so the next reader inherits the
   decision instead of re-litigating it.

### 3. Give every node a contract

| Field | Meaning |
|---|---|
| `id` | Short, uppercase, unambiguous |
| `owner` | Who performs it — inline, another skill, a script, an agent |
| `inputs` | What it reads from run state. It may read nothing else |
| `action` | What it does |
| `emits` | What it writes to run state. Anything not listed is not written |
| **`exits`** | **Every result this node can produce.** See step 4 — this is the field that matters |
| `exit guards` | `condition → next node`, evaluated in order, **exactly one matching** |
| `on failure` | Where control goes when the action fails rather than returning a result |
| `max attempts` | The re-entry bound |
| `requires` | External tools. **Absent → ledger entry; the node may never be recorded as passed** |
| `human` | `none` · `approval-after` · `choice-after` · `confirm-before` · `await-external` · `escalation` |

### 4. Make the guards **total** — the step everyone skips

**This is the hard part, and skipping it is the single most common way these graphs break.**

For each node, take its `exits` and check that **every one matches exactly one guard.** Not zero — a
result no guard covers halts the run on a legal outcome. Not two — an ambiguous transition.

The trap is that guard sets are usually exhaustive over the *happy predicates* but not over their
**product**. If a node's result has three independent properties, there are eight combinations, and
the obvious three guards cover maybe four of them.

**Enumerate the values that mean *route*, and test for them by name.** A field that can be null,
absent, unknown or pending has more than two values, so a guard pair written `X` / `NOT X` does not
cover it — it silently folds the third value into one branch, usually the one that skips work. Write
`== true` and `== false`, and give the remaining values their own guard: a halt, or a ledger entry.
This does not halt when it is wrong, which is what makes it worse than a missing guard.

Write the truth table — one row per *value*, not per interesting value. It is tedious and it is the
whole job.

> Formally this is van der Aalst's **option to complete** — from every reachable state, the end must
> remain reachable. A guard gap is a state from which it is not.

### 5. Find every cycle and bound it

Trace the edges for loops. **Every cycle needs a declared limit and a stated behaviour on
exhaustion** — usually blocking, occasionally proceeding with the problem recorded.

Two rules learned the hard way:

- **Count per-item, not globally.** A per-item key (`attempts["STEP:item-3"]`) means item 4 starts
  fresh while item 3 stays stuck. A global counter conflates them.
- **Never reset a counter, only key it.** A reset hands a stuck loop an unlimited budget, and it
  contradicts resume.

Add a **global step ceiling** as well. Every cycle can be individually within bounds while the run as
a whole never converges.

**One exception:** a loop whose other side is a *human changing their mind* — an approval being
revised — is a conversation, not a retry. Leave it unbounded, and say why.

### 5b. Put the irreversible node last

Find every node that is **hard to reverse** — a merge, a deploy, a publish, an outbound message, a
payment. For each one, ask: *does any node downstream of it produce information that could have
changed the decision to take it?*

If yes, **the ordering is wrong**, and no amount of guard correctness fixes it. A verification step
placed after the point of no return still runs, still reports honestly, and is still worthless — by
the time it can object, the thing it would have objected to has shipped. See failure mode 9.

The test is mechanical: **the irreversible node should be the last node reachable before a terminal.**
Everything that could reject the work goes upstream of it. Give the monitor the invariant directly —
*no entry into the irreversible node before the verifying node has been entered.*

### 6. Type the human stops

List every point the process must stop for a person, and **type each one** — they are not the same
event, and a single "interactive" flag cannot carry them:

| Type | Meaning | On resume |
|---|---|---|
| `approval-after` | Produce the artifact, then ask | Re-ask |
| `choice-after` | Present options, then ask which | Re-ask unless already in state |
| `confirm-before` | Ask **before** acting, because the act is hard to reverse | **Check the world first** |
| `await-external` | Not a question — block on something the world must do | **Re-poll, never re-ask** |
| `escalation` | Only once a bound is exhausted | Re-ask |

**Then declare the list complete.** "These are the only stops; everywhere else, decide and continue."
Without that sentence, an agent invents stops, and a 20-node run becomes 20 interruptions.

> **The re-execution hazard.** On resume, a node generally re-runs *from the start* — so anything it
> did before pausing happens twice. A `confirm-before` node must **ask first and act once**, and on
> resume must derive what already happened from the world, never from what state said it was about to
> do. Otherwise a resumed run opens a second pull request, sends a second email, charges a second time.

> **A conditional stop is a predicate, not a sentence.** "Pauses only when auto-open is off", "asks
> once the retry budget is spent" — written as prose, nothing evaluates it, and the pass that ignores
> the condition is invisible. Make the condition a **field in run state**, settled once at setup, and
> name it in the stop's declaration. Then test it **in both directions**: a stop that fires where the
> user said *continue* costs exactly what an invented stop costs, and reads as diligence rather than
> as a defect, so it is the one that survives review. **Failure mode 15.**
>
> **Derive the published stop list from the node contracts — never maintain both.** The moment a
> summary table and the contracts each state the same six stops, they can disagree, and the summary is
> what people read. Generate it, or check it (step 9b).

### 6b. Ask how the graph should *run*, not just what it should do

The stop list from step 6 is complete for one cadence. Real users want others, and if you do not offer
them, they get invented mid-run — which is exactly the defect step 6 exists to prevent.

Offer the cadence as an explicit, recorded choice alongside the other setup questions:

| cadence | Stops at |
|---|---|
| **continuous** *(default)* | the declared human stops, and nowhere else |
| **checkpoint** | those, **plus** after each unit of work lands — a look as it goes |
| **on-exception** | those, **plus** whenever a gate is skipped, a bound is exhausted, or the auditor is unhappy |

`on-exception` earns its place because the ledger's design is *record and continue* — right, but it
means you may not learn until the end that a gate ran degraded early and everything after it went
through the same weakened check. It puts attention on trouble rather than on a schedule.

**These are declared stops, not invented ones** — which is precisely why they must be chosen up front
and written into run state, not decided in the moment.

> **Anchor `checkpoint` to the node where a unit of work *finishes*, and re-check that anchor whenever
> the shape changes.** This is the one setting that rots without anybody editing it: anchor it to the
> node that lands the work, later collapse N landings into one, and the option still resolves, still
> validates, still reads correctly in the table — and now fires exactly once, at the end, after every
> decision it could have influenced. No structural check catches this, because nothing is structurally
> wrong. See *Changing a graph that already has runs*.

### 7. Design the run state

One file, written on **every** transition, **before the next node starts**. A crash between two nodes
must leave a file saying exactly where the run was.

**One directory per run, not one file per run.** `<runs-dir>/<run-id>/state.json` beats a flat
`<runs-dir>/<run-id>-state.json` the moment anything else belongs to the run — a per-item journal
from a delegated worker, a numbered trail of every state a traced run passed through, a rendered
snapshot. With a directory those land beside the state and `rm -rf` one path retires the whole run;
with a flat file they become a naming convention nobody enforces. `sdlc-graph` moved from the second
to the first at 1.0.0. **Decide before the first run**, because the layout is not something an
in-flight run can be migrated across.

Minimum:

- `node`, `status`, and whatever `context` the guards read
- the work items and their per-item position
- `attempts` — keyed per item
- `history[]` — every transition with the guard that fired, append-only
- **the ledger** — every step that could not run, with its reason, append-only

> **The ledger is the load-bearing part**, and the reason to build a graph at all. Any process can
> claim it ran a step. Only one that records the absence can be trusted when it says it did.

Then write the **resume rule**: read the file, **re-derive progress from the world** — not from what
the file says was intended — and continue. Never rewind `attempts`.

**If any node runs at two different points**, run state needs a **discriminator** — a field that is
null before the second phase and non-null after, tested directly in that node's guards. It doubles as
the phase marker on resume. Key that node's counters separately too (`<NODE>:<item>` vs
`<NODE>:<phase>`), or the first pass can spend the budget the second one needs. Failure mode 10.

**Dispatching a node is itself a phase.** When a node hands work to a subagent or an external
runner, "we tried to start it" and "it ran and came back red" are different failures with different
budgets: one re-spawn is generous, three re-runs of the work is not. Give the dispatch its own key —
`<NODE>-dispatch:<item>` — and bound it separately. `sdlc-graph` carries two of these
(`GATE_A-dispatch`, `MILESTONE-dispatch`), both bounded at 1, and both exist because a dead
dispatcher was spending the budget meant for a red result.

### 8. Emit the files

Load `references/templates.md` for the skeletons and fill them from steps 1–7:

```
<plugin-or-.claude>/
├── agents/
│   └── <graph-name>-monitor.md   the auditor — see step 8b (a skill is the other legal shape)
└── skills/<graph-name>/
    ├── SKILL.md                  the orchestrator: dispatch loop, rules, human stops
    └── graph/
        ├── nodes.md              the node contracts + a diagram
        ├── edges.md              the transition table, the bounds, the terminal states
        └── state.md              the run-state schema, write points, resume rules
```

**Group by kind once there is more than one kind.** Three model files in `graph/`, node procedures in
`nodes/`, executable code in `workflows/`, checks in `evals/`. A flat `references/` holding thirteen
markdown files, five of them one node's sub-procedures, is where `sdlc-graph` started and what it
restructured away from. **If you do that later, resolve every path through one module** — the
restructure invalidated every hand-counted `../` and three broke silently, globbing a directory that
no longer existed.

**Split the diagram.** One picture of every edge is unreadable once retry loops cross the middle —
draw the spine and each sub-loop separately, and **annotate cycles rather than drawing them.**

### 8b. Emit an auditor — a graph with no auditor cannot be trusted

**Every graph you install gets one**, with its checks filled from *this* graph's nodes, edges and
state. Use the skeleton in `templates.md`.

Why it is not optional: a graph's core claim is *"no step passed that did not run."* Nothing in the
graph verifies its own claim. The auditor is what turns that from an assertion into something
checkable — and the failure classes in `failure-modes.md` are precisely the ones that look like
success from inside the run.

**Two shapes, and the choice is a real one.** A **live monitor agent** spawned alongside the run
(`agents/<graph-name>-monitor.md`) sees the run as it happens and can say something while there is
still time to act. An **after-the-fact reviewer** — a command-only skill, or a script over the
finished state file — costs nothing per run and is re-runnable by anyone, forever, without a live
agent. `sdlc-graph` shipped the first for eleven releases and replaced it with the second at 1.0.0,
for a reason worth knowing: the monitor cost tokens on **every** run, and in the one event it existed
to catch it died at a session rollover having observed 0 of 28 transitions while nothing noticed. A
live watcher is itself a thing that can fail silently. Prefer the offline form unless the run is long
enough that hearing about a defect at the end is too late.

Three things to get right whichever you pick, because each has bitten a real graph:

1. **Give the orchestrator the exact scoped name to invoke it with** — `<plugin>:<agent-or-skill>`. A
   `SKILL.md` that says "spawn the monitor" without naming it is an instruction nobody can follow, and
   the auditor silently never runs.
2. **Make the invocation points imperative**, not advisory: on `BLOCKED`, before the terminal state,
   and on demand. "Consider spawning" gets skipped exactly when a run is going wrong.
3. **Read-only, and never a stop.** It reports; it does not remediate, prompt, or gate. An auditor
   that halted runs would become an extra human stop — and you have just declared that list complete.

### 8c. Emit the observability surface — the run state is already watchable

A graph that persists typed state at every transition has **already paid for its own dashboard**.
The state file is the feed; something that renders it is a few hundred lines, and without one the
only way to answer *"where is it now?"* is to read JSON.

Build it, but build it as a **lens, never a second brain**:

1. **It reads the durable record; it never writes it.** The orchestrator is the single writer. A
   renderer that also wrote state would race the one record everything else depends on — worse than
   anything it could show you.
2. **Poll the record; do not build an event bus.** State is written *before every transition*, so a
   plain re-read is guaranteed to see every step. An event channel is machinery the graph does not
   have and does not need.
3. **Never stop watching at a terminal state.** A finished run can gain a resumed transition. "Ended"
   is a fact to display, not a reason to stop looking.
4. **Run content is data, never markup.** Node names, observations, blocked reasons and plan text all
   flow into the page — the same untrusted-input risk as failure mode 7, one layer out. Render with
   text nodes, escape everything, sanitize any identifier that reaches a path.
5. **If it holds graph knowledge, GENERATE that knowledge and check it — declaring a version is not
   enough.** A renderer that knows the guards can show *what can fire next*, which is genuinely
   useful and the reason to accept the duplication. But a copy pinned to `schema_version` still
   drifts inside a version, and the page goes on rendering confidently. What actually works, and
   what `sdlc-graph-viewer` does:
   - **Fence the copied part** — `/*__GRAPH_BEGIN__*/ … /*__GRAPH_END__*/`, and keep it **data only,
     no functions**, so a checker can parse it.
   - **One writer regenerates it from the spec** (`sync_graph.py --write`), and that writer is not
     in the check runner: a checker that can rewrite what it checks is not a checker.
   - **A drift checker reads the spec and fails on a mismatch** — edge ids, endpoints, node set,
     bounds, and whether each guard still tests the same fields.
   - **The check lives on the MIRRORING side.** A plugin may not read above its own root, so the
     graph's suite cannot see the viewer; the viewer reading the graph is the one legal direction,
     and it is enough.

   **And know what the fence does not cover.** Anything the surface *owns* rather than copies has to
   sit outside the markers or the generator deletes it — display-name maps, guard predicates — and
   outside the markers means outside the checker too. `sdlc-graph-viewer` shipped a guard-predicate
   map still keyed on the edge ids of the graph it was forked from: seven keys naming edges that no
   longer existed, and two dimming the exact inverse of their own guard, in a file whose generated
   half was checked the whole time. **A fence is a boundary, and the far side of it needs its own
   check.** See failure mode 13.
6. **Optional and non-gating, exactly like the monitor.** Installed → the orchestrator starts it and
   reports where to look. Absent → one line, and the run proceeds identically. A dashboard that can
   fail a run is a liability, not an instrument.

**Keep its configuration readable, not implicit.** If the surface is a process an agent starts, put
its settings in a file that agent writes and the next one can read — inline environment variables die
with the process, and the next agent has no way to learn what the running instance was told. Every
value the process uses should come from that file; hold defaults in code, never places.

**Audit its weight before shipping it.** Ask what a dependency actually holds: a framework bundled to
serve a few files can be three orders of magnitude larger than the logic it carries. **Tooling around
a graph should be lighter than the graph.**

### 9. Prove it — do not ship an untraced graph

Dry-trace on paper, before anything runs:

1. **The happy path**, end to end.
2. **A failure that retries and recovers.**
3. **A failure that exhausts its bound.**
4. **Each configuration variant separately** — every value of a setting that changes the *shape* of
   the graph rather than the content of a node. These are the traces that catch the guard written for
   one variant and silently wrong for another, and there is no shortcut: a variant you did not trace
   is a variant you did not check.
5. **Every re-entry**, if any node runs at two different points — see failure mode 10. Trace the
   second entry as carefully as the first; it is the one whose guards were written by accident.

At every step, exactly one guard must match. **Zero is a defect; two is a defect.** Also confirm every
node is reachable, and that every node except the declared terminals has an outgoing edge.

If tracing feels tedious, that is the point — it is cheaper here than at node 12 of 18, after the
side effects exist.

### 9b. Emit the traces as an executable suite — a paper trace protects one version

Step 9 verifies the graph you are shipping **today**. Emit `evals/` alongside the model files and
wire it to run on every edit, or the next change re-opens every question step 9 just closed.

Two dependency-free suites, plus the fixture that proves they work:

| | Answers |
|---|---|
| **`spec_consistency.py`** | Do the files describing the graph contradict each other? One check per real defect, each named for the defect. |
| **`graph_walk.py`** | Is a scripted run legal — every transition a declared edge, every guard quoted **verbatim**, every invariant held? And does the fixture set **enter every node and traverse every edge**? Make that a gate, not a report. |
| **A negative control** | A file of deliberate violations the suite **must** reject. If it ever passes, the checker has stopped checking and every other green is worthless. |

Three properties earn their keep beyond the obvious: **stops derived from the node contracts** rather
than listed twice, **each fixture asserting its exact ordered stop sequence**, and **a fixture in each
direction for every conditional stop** — failure mode 15 lives entirely in the second direction, and
that is the one nobody writes.

> **The rule that keeps the suite alive:** a change to the graph is not finished until it adds or
> updates the eval that would have caught its absence. Write that rule into the target project's own
> `CLAUDE.md`, next to the command that runs the suite — a convention living only in this skill is one
> the next contributor never sees.

**→ `references/evals.md`** for the fixture format, how to write a check that reads as a diagnosis,
what belongs in a negative control, and — the part people get wrong — **the surfaces the suite cannot
reach**. A suite may only read files inside its own unit, so anything that mirrors the graph from
elsewhere sits outside it. That is not a licence to check them by hand: put the drift checker in the
**mirror's** suite pointed back at the graph (the one legal direction), route the edit to it, and use
**receipts** for the tier that needs a model and so can never run on every edit — **reported, never
a gate**, and authored with the change even when nobody drives it.

## Output Contract

1. **The files** above, written to the target — four model files, the auditor, the eval suite, and
   (when built) the observability surface.
2. **A trace report** — the three scenarios, each transition and the guard that fired.
3. **A summary**: node count, edge count, bounded cycles, human stops, and every step whose `requires`
   may be absent.
4. **A green eval run**, with its coverage line: *N/N edges, N/N nodes*. Anything less names the gap.

## Validation

The graph is ready when:

- **Every node's `exits` matches exactly one guard.** Not zero, not two. Prove it per node.
- **Every cycle has a bound**, plus a global step ceiling.
- **Every node is reachable**, and every non-terminal has an outgoing edge.
- **Every guard reads only declared state**, and every state field read is written by some node first.
- **Every human stop is typed**, and the list is declared complete. **Every conditional stop has a
  fixture in each direction** — one where it fires, one where the run must continue past it.
- **The three traces resolve cleanly.**
- **The eval suite is green, its coverage is total, and its negative control fails.** A suite that
  cannot fail is not evidence of anything.
- **Every `requires` has a ledger path** — no step can be marked passed when its tool was absent.
- **A monitor exists, and the orchestrator names it by its exact scoped invocation string.** An
  un-nameable monitor never runs.

## Changing a graph that already has runs

The method above builds one. Changing one that has already produced state files has a rule of its own:

**Retire edge ids; never reuse or renumber them.** Finished runs record which edge fired at each
transition. Reuse a freed number and old records silently describe a transition that never happened.
Leave the gaps, list the retired ids with one line each on why they became unreachable, and give new
edges new numbers. Failure mode 11.

**Re-trace every variant after the change, not just the one you touched.** A guard narrowed for one
configuration is the classic way another configuration loses its only matching guard.

**Re-check the counts you published.** Node and edge totals appear in READMEs, diagrams and monitor
checks. They drift silently and they are the first thing a reader uses to decide whether the docs are
current.

**Ship the eval with the change, not after it.** A new edge needs a walk that traverses it, a new
invariant needs a check, a new or changed stop needs both plus a planted violation in the negative
control. This is not process for its own sake: the coverage gate in step 9b turns "re-trace every
variant" from a discipline someone has to remember into a suite that goes red on its own. **A change
that leaves the suite green without touching it has almost certainly added something untested** — the
gate only knows about edges and nodes, so a changed *guard* on an existing edge slips through unless
you add the case yourself.

**A cadence option can rot without a single line changing.** When the topology moves, re-read every
setting that names a node: a mode described as *"stop after every X"* stops meaning what it says the
moment X stops happening per item. That is not caught by any structural check — the graph is still
sound, the option still resolves — so it is worth one deliberate pass over the run-mode table after
any change to the shape of the loop or the tail.

## Guardrails

- **Do not invent steps the user does not have.** You are modelling their process, not designing an
  idealised one. Where a step is missing, say so and let them decide.
- **Do not copy a skill you are turning into a node without saying so.** A copy that drifts from its
  original is worse than a reference. Record what it was copied from and what you trimmed.
- **Never let the graph perform an irreversible act unprompted** — merging, deploying, deleting,
  sending, paying. Those are `confirm-before` or `await-external`, always.
- **Never emit a guard set you have not traced.** An untraced graph looks identical to a traced one
  and fails at runtime, on a path nobody walked.

## References

- **`references/templates.md`** — skeletons for the four files. Load at step 8.
- **`references/evals.md`** — the eval suite in full: fixture format, writing a check that reads as a
  diagnosis, the negative control, checking a mirroring surface from the mirror's side, and the
  model-driven tier: receipts, why it must report rather than gate, and why the case is authored
  with the change but driven on demand. Load at step 9b.
- **`references/failure-modes.md`** — the ways these graphs break at runtime, with the signal for each.
  Worth reading at step 4, before you believe your guards are total.
