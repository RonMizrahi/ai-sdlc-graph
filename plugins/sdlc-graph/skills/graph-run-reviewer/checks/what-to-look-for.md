# What to look for — the classes `audit_run.py` structurally cannot reach

`audit_run.py` checks whether the trail is **well-formed**: shapes, bounds, counters, guards quoted
verbatim, journals against the history they produced, commits against git, the trace sequence. It is
mechanical, and everything mechanical belongs to it.

What is left needs two artifacts side by side and a judgement about whether they tell the same
story. That is this file. Each entry names what to compare, what the tell is, and what it usually
turns out to be.

**Nothing here is a finding on its own.** Every one produces a *question*; the finding is the
answer, with the artifact cited.

---

## 1. The observation contradicts the journal

**Compare:** each `history[]` entry's `observation` against the journal `headline` for the same node
and milestone.

Both describe the same moment, written by the same agent — the headline as it left the node, the
observation in the bundle it composed afterwards. They should agree. When they do not, the bundle
was written from memory rather than from the record, and the memory is the half that was
reconstructed.

**The tell:** an observation that is *vaguer* than the headline it corresponds to. "gate A
completed" against a headline of "6 files, 2 security findings applied, 1 re-run". Detail does not
usually go missing on its way into a summary someone is about to be checked on.

> **Careful.** Wording differences are expected and are not findings. A *fact* in one and not the
> other is. If the headline names a retry and the observation does not, that is R13's territory and
> the auditor already has it — check it ran.

## 2. A gate that passed too cleanly

**Compare:** `GATE_A`'s reported findings against the size of the milestone — `evidence.commits`,
the number of steps, the diff if you have the repo.

A first-pass Gate A over a substantial milestone with zero findings across four review steps is
possible. It is also what a Gate A that dispatched nothing looks like, and that has happened here:
`clean: true` returned having run zero agents.

**The tell:** `clean: true` with `groups_completed` absent, or a `run_id` of `null` where the
milestone plainly had files. Ask what `files_reviewed` was, and whether `tools_asserted` was true.

**Usually:** a preflight that was not asserted, so the gate ran with tools it did not have.

## 3. A ledger entry that does not match the world

**Compare:** each `skipped_gates[]` reason against what is actually installed and reachable.

The ledger is the graph's honesty mechanism, which makes it the most useful thing to lie with. An
entry blaming an absent tool that is in fact present converts a skipped gate into a documented one.

**The tell:** a reason naming a tool the repo demonstrably has, or a dependency rather than a
capability. **Playwright is the standing example** — it is a dependency to install, not a capability
to ledger, and `audit_run.py` catches that specific one. Others are yours: a `--repo` that was
reachable, a suite that exists, a host that has a remote.

**Also check the shape:** an entry per *step*, not one per node covering several. `GATE_A.step2` and
`GATE_A.step3` are two entries.

## 4. A transition that was legal but wrong

**Compare:** each `history[]` entry's guard against the *other* guards on that node, evaluated
against the state as it was.

The walker proves a transition is declared. It does not prove it was the **right** declared
transition, because `edges.md` orders guards and the first match wins. A run that evaluated them out
of order can take a legal edge that a correct evaluation would not have reached.

**The tell:** a node with two guards that could both be true at that moment. `GATE_A`'s re-run edge
against its two exits is the one to look at first — routing there on `clean` rather than
`rerun_recommended` deadlocked the node once, and the trail of a run that gets it wrong is entirely
legal.

**Usually:** the orchestrator routed on the reported fact rather than the routing fact.

## 5. `delivered` does not match what the milestone did

**Compare:** `milestones[].delivered` against that milestone's `evidence.commits` and its `steps`.

`delivered` is what the *next* milestone is briefed from. It is prose, nothing routes on it, and a
wrong one misleads every dependent milestone under C without failing anything.

**The tell:** `delivered` describing interfaces no commit touched, or `null` on a milestone whose
`GATE_B` passed. The second is mechanical enough to be a bug in the replay.

## 6. The trace has states the trail does not explain

*Only when the run was traced.* **Compare:** consecutive snapshots in `history/`.

This is the richest source and the one nothing else can use. `state.json` shows where a run ended
up; the snapshots show how it got there, including the parts that were overwritten.

Worth diffing:

- **A counter that climbed and came back down.** `attempts` is monotonic; a decrease is a rewrite.
- **A `skipped_gates[]` entry that appears and then disappears.** The ledger is append-only.
- **A `history[]` that got shorter.** Transitions are appended, never revised.
- **A long run of snapshots at one node.** Not a defect — it is what an agent working looks like —
  but it is where to look when a run took far longer than it should have.
- **The last snapshot before a `BLOCKED`.** It is the state the halt was decided from, and it is
  usually gone by the time anyone asks.

```bash
cd docs/graph-runs/<run-id>/history
for a in *.json; do echo "== $a"; done          # the story, from the names alone
diff <(jq -S . 0006_*.json) <(jq -S . 0007_*.json)
```

## 7. The run stopped somewhere the graph does not stop

**Compare:** where the run actually paused against the `human:` rows in `graph/nodes.md`.

Six nodes declare a stop. A run that paused anywhere else invented a gate, and inventing gates is
how a 20-node run becomes 20 interruptions. This does not show up in `history[]` at all — a pause
leaves no artifact — so the evidence is the transcript or the user's memory of being asked.

**Ask the user** if you cannot tell. It is the one class here with no artifact, and saying so is
better than guessing.

## 8. What the run never got to

**Compare:** `history[]`'s final node against the graph's terminal states.

A run that stops mid-graph with `status: RUNNING` and no `stopped` object did not halt — it was
abandoned, or the process died. That is not a defect in the graph and it is worth saying, because it
looks identical to a run that is still going.

---

## Before you write any of it up

**Zero findings is a real answer.** Most runs of a working graph produce none, and a review that
manufactures one to justify itself is worse than a short report. Say the run was clean, say which
checks reported NOT RUN and why, and stop.
