# Observability — the viewer

One companion sits alongside a run. **It is not a node, it is not a gate, and it may not stop the
graph.** A companion that halted runs would be a seventh human stop, and there are six.

Companion files: **`nodes.md`** (node contracts) · **`edges.md`** (transitions) · **`state.md`**
(run-state schema). For the graph's self-checks see **`../evals/EVAL-INSTRUCTIONS.md`**.

---

## There is no live auditor

This graph used to spawn a read-only auditor agent alongside every run. **It no longer does** — it
cost tokens on every run and, in the one event it existed to catch, died at a session rollover having
observed **0 of 28 transitions** while nothing noticed. An auditor that is assumed to be alive audits
nothing.

What carries its weight instead:

| | |
|---|---|
| **The state file** | Every transition is on disk before the next node starts, with the guard quoted verbatim and a one-line `observation` of what actually happened. That trail is re-readable by you, the user, or a checker, at any time, with no live agent and no transcript. |
| **The milestone journals** | `docs/graph-runs/<run-id>/journals/milestone-<id>.jsonl` — what each milestone agent wrote *while it ran*, appended on every node exit — **and on every subagent it spawns and every one that returns**, so a forty-agent Gate A is a readable list rather than one sentence. See `workflow-dispatch.md` § *The milestone journal*. |
| **The eval suite** | `../evals/run_all.py` — the spec cannot contradict itself, and every scripted walk is legal against `edges.md` and `state.md`. Plus `../evals/runs/`, which drives real scenarios and asserts on the artifacts they leave. The repo's PostToolUse hook runs both on every edit under this plugin. |
| **`history/`, when `--trace` is on** | Every state the run passed through, numbered and named after the transition that produced it — `0007_m2_GATE_A-to-E2E_<ts>.json`. `state.json` is overwritten at every hop, so without this the counters as they climbed, the `progress` block, and the ledger as it grew are simply gone. **Off by default**, written by the plugin's own PostToolUse hook, and telemetry rather than evidence: nothing routes on it. `state.md` § *`trace`*. |
| **`audit_run.py`** | The whole trail re-checked offline, afterwards, by anyone — including R13, which compares the journals against the history they produced. |

### Something does watch a run now — and it is not an auditor

The orchestrator reads each milestone agent's journal as it is written, so a node finishing is a fact it holds
**in runtime** rather than at the end of a milestone. That is what makes it able to supervise: a milestone agent
that stops emitting is visible as silence rather than as a return that never comes.

**Be precise about what that is and is not.** It is not the independence the monitor agent was
supposed to provide, and it must not be mistaken for it:

- The journal is **telemetry, not evidence.** Nothing routes on it, and it never satisfies an R-check.
  The single exception is R13, which runs the other way round — using the journal to catch the bundle
  *omitting* something, never to prove that anything happened.
- The orchestrator is still **checking its own work.** A self-check reported by the thing being checked
  is structurally weaker than an outside look, however much of it there is. What restores the outside
  look is `audit_run.py`, run afterwards by someone who was not there.

> So the trail still has to carry more weight than it used to. An `observation` that says nothing, or
> a `history[]` that is uniformly cheerful, is still where a bad run shows up before its verdict —
> there is simply now a second contemporaneous record beside it that can be compared against the first.

---

## The live viewer — an optional companion plugin

The viewer lives in its own plugin, **`sdlc-graph-viewer`** — the graph runs fine without it.

At run start, check whether the `sdlc-graph-viewer:view-run` skill is available:

- **Installed** → invoke it (live mode). It starts **one server for this project on its own stable
  port** (never shared with another project), serving the run's live view — the page polls the state
  file every 1s, forever, even after `DONE`. **Relay its printed summary** (project, port, URLs)
  verbatim, so the user always knows what is running and where to look.
- **Not installed** → one line — *"sdlc-graph-viewer not installed; no live view for this run"* — and
  continue. This is the same optional-companion pattern as every live-dispatched tool: never a
  failure, never a gate.

The server outlives the run on purpose; note it in the `DONE` report so a forgotten server is a
known server.

> **The viewer renders the guards, so it can lie about them.** It carries its own copy of the
> transition logic in order to show what happens next, and the graph's eval suite **cannot reach it**
> — a different plugin, and a plugin may not read above its own root. A guard fixed in `edges.md` is
> not fixed until it is fixed there too. Check it by hand on any change to a guard, a bound, or a
> stop.
