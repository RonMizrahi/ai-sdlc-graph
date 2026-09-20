# 04 — a milestone agent stops emitting, and silence is diagnosed instead of waited out

**Claim:** heartbeat silence is detected from `seen_at` and routed to MILESTONE-dispatch, not to a longer wait.

The monitor agent this graph removed died at a session rollover and observed 0 of 28 transitions
while nothing noticed. A root that answers a silent milestone agent by waiting longer has reproduced exactly
that, with the roles swapped.

The mock milestone agent emits two nodes and a heartbeat, then exits without returning. There is no return to
wait for and no error to catch — the only evidence is that `seen_at` stops advancing. `MILESTONE-dispatch`
is bounded at 1 retry precisely so this cannot become an indefinite loop either.

```setup
{
  "state": {
    "run_id": "runeval-04",
    "schema_version": 5,
    "status": "RUNNING",
    "node": "BRANCH",
    "context": {
      "stack": "backend",
      "has_ui": false,
      "main_branch": "main",
      "branching": "A"
    },
    "milestones": [
      {
        "id": 1,
        "name": "m1",
        "branch": null,
        "deps": [],
        "steps": [
          "s1"
        ],
        "is_fix": false,
        "touches_ui": false,
        "delivered": null
      }
    ],
    "cursor": 1,
    "in_flight": [],
    "history": [],
    "attempts": {},
    "skipped_gates": [],
    "integration": {
      "branch": null,
      "merged": []
    }
  },
  "agents": {
    "1": {
      "dies": true,
      "lines": [
        {
          "seq": 1,
          "event": "node_done",
          "node": "BRANCH",
          "milestone": 1,
          "attempt": 1,
          "headline": "branch created",
          "_delay_s": 0.1
        },
        {
          "seq": 2,
          "event": "node_done",
          "node": "IMPLEMENT",
          "milestone": 1,
          "attempt": 1,
          "headline": "1 of 3 steps committed",
          "_delay_s": 0.1
        },
        {
          "seq": 3,
          "event": "heartbeat",
          "node": "IMPLEMENT",
          "milestone": 1,
          "headline": "still implementing",
          "_delay_s": 0.1
        }
      ]
    }
  },
  "ideal_artifacts": {
    "state": {
      "run_id": "runeval-04",
      "schema_version": 5,
      "status": "RUNNING",
      "node": "BRANCH",
      "context": {
        "stack": "backend",
        "has_ui": false,
        "main_branch": "main",
        "branching": "A"
      },
      "milestones": [
        {
          "id": 1,
          "name": "m1",
          "branch": null,
          "deps": [],
          "steps": [
            "s1"
          ],
          "is_fix": false,
          "touches_ui": false,
          "delivered": null,
          "spawned_at_history_len": 0,
          "journal": "docs/graph-runs/runeval-04/journals/milestone-1.jsonl",
          "agent_id": "mock-1",
          "progress": {
            "at_node": "IMPLEMENT",
            "headline": "still implementing",
            "seen_at": "2026-08-07T10:00:00Z"
          }
        }
      ],
      "cursor": 1,
      "in_flight": [
        1
      ],
      "history": [
        {
          "from": "BRANCH",
          "to": "BLOCKED",
          "guard": "",
          "milestone": 1,
          "observation": "the milestone agent died mid-node; MILESTONE-dispatch charged, re-spawn still owed"
        }
      ],
      "attempts": {
        "MILESTONE-dispatch:1": 1
      },
      "skipped_gates": [],
      "integration": {
        "branch": null,
        "merged": []
      }
    },
    "journals": {
      "1": [
        {
          "seq": 1,
          "event": "node_done",
          "node": "BRANCH",
          "milestone": 1,
          "attempt": 1,
          "headline": "BRANCH done"
        },
        {
          "seq": 2,
          "event": "node_done",
          "node": "IMPLEMENT",
          "milestone": 1,
          "attempt": 1,
          "headline": "IMPLEMENT done"
        },
        {
          "seq": 3,
          "event": "heartbeat",
          "node": "IMPLEMENT",
          "milestone": 1,
          "headline": "still implementing"
        }
      ]
    }
  }
}
```

```brief
You are the sdlc-graph ORCHESTRATOR. Spawn the milestone agent for milestone 1 of run `runeval-04` and
supervise it. STOP once you have decided what happened to it — within 60 seconds.

Read and follow:
  {{SKILL}}/SKILL.md            -- "3. Run the node", "While a milestone agent runs"
  {{SKILL}}/graph/edges.md -- the MILESTONE-dispatch bound

WHERE THE RUN IS. The state file's `node` says which node the run is in — read it, and start from
there. **If the milestone agent returns a bundle AND that bundle passes the return gate**, evaluate
`GATE_B`'s exit guard yourself and record that transition with `verified: null`: the agent runs Gate
B, but its exits are yours, and on your own hop there is no claim of anyone else's to verify.

That instruction is CONDITIONAL, and the condition is the point. Three orchestrators driving these
scenarios read it as unconditional and had to reason their way out of writing a `GATE_B` exit for a
milestone whose agent never returned, or whose bundle the gate had just refused. A weaker one writes
the hop. If no bundle arrives, or the gate rejects it, **nothing is recorded** — that is the whole
architecture.

The run lives at: {{SCRATCH}}
  state file : {{SCRATCH}}/docs/graph-runs/runeval-04/state.json   (you are its only writer)

THE WORLD IS MOCKED TOO. The scratch run is not its own git repo and the mock agent makes no
commits, so the shas in its bundle are placeholders that resolve to nothing. That is the harness,
not a fabrication plant: treat every world-sourced check (R4, R5, R6, R7's diff, most of R12) as
NOT RUN, record it as not-run — never as passed — and ledger what it could not back. The scenario
under test is whatever this brief names, not the absence of a repo.

THE AGENT IS MOCKED. Spawn it in the background with:

  python3 {{EVALS}}/runs/mock_milestone.py \
      --script {{SCRATCH}}/agent-1.script.json \
      --journal {{SCRATCH}}/docs/graph-runs/runeval-04/journals/milestone-1.jsonl

Do not wait indefinitely for a bundle. Decide, record, and report.
```

```assert
len([h for h in history if h.get("to") != "BLOCKED"]) == 0                    # no TRANSITION was recorded — no bundle ever arrived, let alone passed a gate
len(history) <= 1                                                            # ...and at most the one halt entry § Recording a halt mandates
all(h.get("guard") == "" for h in history if h.get("to") == "BLOCKED")       # ...whose guard is empty: no row in edges.md declares an `on failure` exit
(state.get("attempts") or {}).get("MILESTONE-dispatch:1", 0) >= 1                 # the death was charged to the milestone dispatch counter
not any(k.startswith("IMPLEMENT:") for k in (state.get("attempts") or {}))   # ...and never to the node budgets, which the milestone agent never spent
1 in inflight or (state.get("stopped") or {}).get("at_milestone") == 1       # the milestone agent is still accounted for: in flight, or halted
((m1().get("progress") or {}).get("seen_at")) or (state.get("stopped") or {})       # the liveness signal was actually read
(milestones[0].get("delivered") or None) is None                             # nothing shipped
```

```control
# The wait that never ends, dressed as progress: the counter is untouched and the milestone agent is simply
# still 'in flight', forever.
state["attempts"] = {}
```
