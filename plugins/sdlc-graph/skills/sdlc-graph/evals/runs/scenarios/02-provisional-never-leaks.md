# 02 — the milestone agent reaches GATE_B and the trail is still empty

**Claim:** live knowledge updates `milestones[]` and never `history[]`, however far ahead the milestone agent gets.

The single most tempting shortcut this change introduces. The orchestrator now *knows*, in runtime,
that `TEST` went green — so why not write the transition then and save the replay?

Because at that moment nothing has been checked. The suite has not been re-run, no sha looked up, no
spec file opened. Writing it early turns the return gate from the thing that decides what enters the
record into a review of rows already in it, and a gate that runs after the write cannot refuse.

The mock milestone agent emits five nodes and then **never returns**. A correct orchestrator ends this scenario
knowing exactly where the milestone agent is and having recorded none of it.

```setup
{
  "state": {
    "run_id": "runeval-02",
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
        "name": "rate limiter",
        "branch": null,
        "deps": [],
        "steps": [
          "add limiter",
          "tests"
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
          "headline": "2 steps committed",
          "_delay_s": 0.1
        },
        {
          "seq": 3,
          "event": "node_done",
          "node": "TEST",
          "milestone": 1,
          "attempt": 1,
          "headline": "unit + integration green",
          "_delay_s": 0.1
        },
        {
          "seq": 4,
          "event": "node_done",
          "node": "GATE_A",
          "milestone": 1,
          "attempt": 1,
          "headline": "3 files, no findings",
          "_delay_s": 0.1
        },
        {
          "seq": 5,
          "event": "node_done",
          "node": "GATE_B",
          "milestone": 1,
          "attempt": 1,
          "headline": "review clean, suite green after",
          "_delay_s": 0.1
        }
      ]
    }
  },
  "ideal_artifacts": {
    "state": {
      "run_id": "runeval-02",
      "schema_version": 5,
      "status": "RUNNING",
      "node": "BRANCH",
      "milestones": [
        {
          "id": 1,
          "delivered": null,
          "branch": "selftest/run",
          "base_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "journal": "docs/graph-runs/runeval-02/journals/milestone-1.jsonl",
          "agent_id": "mock-1",
          "spawned_at_history_len": 0,
          "progress": {
            "at_node": "GATE_B",
            "headline": "review clean, suite green after",
            "seen_at": "2026-08-07T10:00:05Z"
          }
        }
      ],
      "cursor": 1,
      "in_flight": [
        1
      ],
      "history": [],
      "attempts": {},
      "skipped_gates": []
    },
    "journals": {
      "1": [
        {
          "seq": 1,
          "event": "node_done",
          "node": "BRANCH",
          "milestone": 1,
          "attempt": 1,
          "headline": "branch created"
        },
        {
          "seq": 2,
          "event": "node_done",
          "node": "IMPLEMENT",
          "milestone": 1,
          "attempt": 1,
          "headline": "2 steps committed"
        },
        {
          "seq": 3,
          "event": "node_done",
          "node": "TEST",
          "milestone": 1,
          "attempt": 1,
          "headline": "green"
        },
        {
          "seq": 4,
          "event": "node_done",
          "node": "GATE_A",
          "milestone": 1,
          "attempt": 1,
          "headline": "3 files, no findings"
        },
        {
          "seq": 5,
          "event": "node_done",
          "node": "GATE_B",
          "milestone": 1,
          "attempt": 1,
          "headline": "review clean"
        }
      ]
    }
  },
  "git": true
}
```

```brief
You are the sdlc-graph ORCHESTRATOR. Spawn the milestone agent for milestone 1 of run `runeval-02`,
follow it while it runs, and STOP when it has been silent for 30 seconds.

Read and follow:
  {{SKILL}}/SKILL.md                         -- "3. Run the node", "While a milestone agent runs"
  {{SKILL}}/graph/state.md              -- "Provisional is not recorded"

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
  state file : {{SCRATCH}}/docs/graph-runs/runeval-02/state.json   (you are its only writer)

THE WORLD IS PARTLY REAL. The scratch run **is** its own git repo with one commit on `main`, so
`base_sha` and `main_sha_at_spawn` are derivable and belong in the spawn record — do not ledger them
as unavailable. The mock agent still makes no commits, so any sha in a bundle is a placeholder that
resolves to nothing. That is the harness,
not a fabrication plant: treat every world-sourced check (R4, R5, R6, R7's diff, most of R12) as
NOT RUN, record it as not-run — never as passed — and ledger what it could not back. The scenario
under test is whatever this brief names, not the absence of a repo.

THE AGENT IS MOCKED. Spawn it in the background with:

  python3 {{EVALS}}/runs/mock_milestone.py \
      --script {{SCRATCH}}/agent-1.script.json \
      --journal {{SCRATCH}}/docs/graph-runs/runeval-02/journals/milestone-1.jsonl

This milestone agent will emit several nodes and then exit WITHOUT returning a bundle. That is the scenario,
not a mistake.

RECORD ITS HANDLE AS `agent_id`, the literal `mock-1`, and say in `verified` that it is the harness's
handle rather than an Agent id. The mock is a background process, not an `Agent` dispatch, so there is
no id to return — `state.md` defines the field as *"the id the Agent dispatch returned"*. **Do not
invent a shell PID and present it as one.** An orchestrator driving this scenario refused to fabricate
a value and left the field null, which is exactly the right instinct and left the spawn record without
the handle this scenario asserts. The honest fix is a documented value, not a guessed one. Keep the state file current with what you learn, stop when it goes quiet, and report
where the milestone agent got to.

DO NOT DIAGNOSE IT DEAD, and do not re-spawn it. Stop while it is still `in_flight` with its
`progress` block intact — what is under test here is that live knowledge reached `milestones[]` and
never `history[]`, and declaring death nulls `progress` (`state.md`), which erases the very thing
this scenario measures. Diagnosing a dead agent and charging the re-spawn is scenario 04's subject,
and it has its own fixture. Two orchestrators driving this one went straight past "report where it
got to" into `agent_lost`, so the instruction is spelled out rather than implied.
```

```assert
history == []                                      # NOTHING was recorded: no bundle ever passed a gate
(1 in inflight) == (state.get("status") == "RUNNING")       # in flight IFF the run is still moving
(m1().get("progress") or {}).get("at_node") == "GATE_B"     # the orchestrator tracked it to its last emitted node
((m1().get("progress") or {}).get("headline") or "") != ""  # ...and kept the line the agent wrote about it
((m1().get("progress") or {}).get("seen_at") or "") != ""   # ...with a timestamp, which is the liveness signal
(m1().get("journal") or "").endswith(".jsonl")              # the journal path was written before the spawn
((m1().get("base_sha") or "") != "") and ((m1().get("agent_id") or "") != "")   # ...and either way the pre-spawn write left it findable
(milestones[0].get("delivered") or None) is None   # nothing shipped: the milestone never passed its gate
len(journals.get("1") or []) == 5                  # the milestone agent really did get five nodes ahead
```

```control
# The shortcut: the orchestrator writes what it learned live. Plausible, tidy, and it means the
# return gate now runs against rows already in the record.
state["history"] = [
    {"from": "BRANCH", "to": "IMPLEMENT", "milestone": 1, "observation": "branch created", "verified": None},
    {"from": "IMPLEMENT", "to": "TEST", "milestone": 1, "observation": "2 steps committed", "verified": None},
]
```
