# 01 — a milestone agent that goes right, and an orchestrator that does the four things in order

**Claim:** state before spawn · monitor before spawn · `history[]` only after the gate · `delivered` recorded.

The baseline. Nothing goes wrong, which is the point: three of the four orderings this asserts are
invisible on a run that succeeds, and every one of them is load-bearing only when something later
fails. `milestones[]` written *after* the spawn looks identical to `milestones[]` written before — until a
crash lands in between and the run resumes with no idea a milestone agent was ever in flight.

The milestone agent is `mock_milestone.py`, not an agent: this scenario measures the **orchestrator**, and two
nondeterministic actors cannot tell you which of them was wrong.

**The milestone's `steps[]` names a test file, deliberately.** `PLAN` is required to bake test steps
into every milestone, and `TEST` — not `IMPLEMENT` — commits them, so the bundle's `IMPLEMENT` row
reports **1 of 2** steps and guard 9 is satisfied anyway. A real run planned exactly this shape and
met a guard reading *"all milestone steps committed"*, which was literally false at a node with one
exit: the healthiest milestone in the suite, one strict reading from `BLOCKED`.

```setup
{
  "git": true,
  "state": {
    "run_id": "runeval-01",
    "schema_version": 5,
    "status": "RUNNING",
    "node": "BRANCH",
    "plan_path": "docs/plans/runeval-01-plan.md",
    "spec_path": null,
    "context": {
      "stack": "backend",
      "has_ui": false,
      "main_branch": "main",
      "branching": "A",
      "run_mode": "continuous",
      "standards_handshake": null
    },
    "milestones": [
      {
        "id": 1,
        "name": "token store",
        "branch": null,
        "worktree": null,
        "deps": [],
        "steps": [
          "add src/token-store.js",
          "add test/unit/token-store.test.js"
        ],
        "pr": null,
        "is_fix": false,
        "touches_ui": false,
        "delivered": null
      }
    ],
    "cursor": 1,
    "in_flight": [],
    "integration": {
      "branch": null,
      "merged": []
    },
    "history": [],
    "attempts": {},
    "skipped_gates": []
  },
  "agents": {
    "1": {
      "lines": [
        {
          "seq": 1,
          "event": "node_done",
          "node": "BRANCH",
          "milestone": 1,
          "attempt": 1,
          "headline": "run branch selftest/run created off main",
          "_delay_s": 0.2
        },
        {
          "seq": 2,
          "event": "node_done",
          "node": "IMPLEMENT",
          "milestone": 1,
          "attempt": 1,
          "headline": "1 of 2 steps committed \u2014 TokenStore; the test file is TEST's",
          "_delay_s": 0.2
        },
        {
          "seq": 3,
          "event": "node_done",
          "node": "TEST",
          "milestone": 1,
          "attempt": 1,
          "headline": "token-store.test.js committed here, then unit + integration green on the first pass",
          "_delay_s": 0.2
        },
        {
          "seq": 4,
          "event": "node_done",
          "node": "GATE_A",
          "milestone": 1,
          "attempt": 1,
          "headline": "2 files reviewed, 1 simplification applied, no security findings"
        },
        {
          "seq": 5,
          "event": "node_done",
          "node": "GATE_B",
          "milestone": 1,
          "attempt": 1,
          "headline": "holistic review clean; suite green after"
        }
      ],
      "bundle": {
        "milestone_id": 1,
        "outcome": "completed",
        "notes": "TokenStore.put/get/evict with a 15-minute TTL, backed by an in-memory Map. Callers get null on a miss, never a throw. Milestone 2 should call TokenStore.get before minting a new token.",
        "trace": [
          {
            "from": "BRANCH",
            "claimed_to": "IMPLEMENT",
            "result": {
              "branch_checked_out": true
            },
            "observation": "run branch created off main"
          },
          {
            "from": "IMPLEMENT",
            "claimed_to": "TEST",
            "result": {
              "steps_committed": 1
            },
            "observation": "the 1 step this node owns committed in one turn with the transition; the test file is TEST's"
          },
          {
            "from": "TEST",
            "claimed_to": "GATE_A",
            "result": {
              "tests_state": "green"
            },
            "observation": "green first pass"
          },
          {
            "from": "GATE_A",
            "claimed_to": "GATE_B",
            "result": {
              "rerun_recommended": false
            },
            "observation": "1 simplification applied, no findings left"
          }
        ],
        "attempt_counts": {},
        "skipped_gates_proposed": [],
        "preflight": {
          "BRANCH": {
            "asserted": true,
            "tools": {
              "git": "present"
            },
            "method": "invoked --version"
          },
          "IMPLEMENT": {
            "asserted": true,
            "tools": {
              "git": "present"
            },
            "method": "invoked --version"
          },
          "TEST": {
            "asserted": true,
            "tools": {
              "git": "present"
            },
            "method": "invoked --version"
          },
          "GATE_A": {
            "asserted": true,
            "tools": {
              "git": "present"
            },
            "method": "invoked --version"
          },
          "GATE_B": {
            "asserted": true,
            "tools": {
              "git": "present"
            },
            "method": "invoked --version"
          }
        },
        "evidence": {
          "base_sha": "1111111111111111111111111111111111111111",
          "head_sha": "3333333333333333333333333333333333333333",
          "commits": [
            "2222222222222222222222222222222222222222",
            "3333333333333333333333333333333333333333"
          ],
          "tests": {
            "unit": "pass",
            "integration": "pass",
            "commands": {
              "unit": "test:unit",
              "integration": "test:integration"
            },
            "counts": {
              "unit": 12,
              "integration": 4
            }
          },
          "gate_a": {
            "run_id": "wf_runeval",
            "tools_asserted": true,
            "groups_completed": 2,
            "groups_total": 2,
            "files_supplied": 2,
            "uncovered_count": 0,
            "skipped_steps": [],
            "rerun_recommended": false,
            "dispatch": "workflow"
          },
          "gate_b": {
            "reviewer": "ran",
            "diff_base": "main",
            "findings_count": 0,
            "tests_after": "green"
          },
          "worktree_removed": false,
          "working_tree_clean": true
        }
      }
    }
  },
  "ideal_artifacts": {
    "state": {
      "run_id": "runeval-01",
      "schema_version": 5,
      "status": "RUNNING",
      "node": "CLOSE_OUT",
      "milestones": [
        {
          "id": 1,
          "delivered": "TokenStore.put/get/evict with a 15-minute TTL; callers get null on a miss."
        }
      ],
      "cursor": 1,
      "in_flight": [],
      "history": [
        {
          "from": "BRANCH",
          "to": "IMPLEMENT",
          "milestone": 1,
          "observation": "run branch created off main",
          "verified": "git rev-parse confirmed the branch"
        },
        {
          "from": "IMPLEMENT",
          "to": "TEST",
          "milestone": 1,
          "observation": "the 1 step this node owns committed in one turn; the test file is TEST's",
          "verified": "1 commit confirmed by git log; guard 9 asks for IMPLEMENT's partition, not the milestone's whole steps[]"
        },
        {
          "from": "TEST",
          "to": "GATE_A",
          "milestone": 1,
          "observation": "green first pass",
          "verified": "suite re-run by the orchestrator, exit 0"
        },
        {
          "from": "GATE_A",
          "to": "GATE_B",
          "milestone": 1,
          "observation": "1 simplification applied",
          "verified": "applied files confirmed against git diff --name-only"
        },
        {
          "from": "GATE_B",
          "to": "CLOSE_OUT",
          "milestone": 1,
          "observation": "holistic review clean",
          "verified": null
        }
      ],
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
          "headline": "run branch created"
        },
        {
          "seq": 2,
          "event": "node_done",
          "node": "IMPLEMENT",
          "milestone": 1,
          "attempt": 1,
          "headline": "1 of 2 steps committed"
        },
        {
          "seq": 3,
          "event": "node_done",
          "node": "TEST",
          "milestone": 1,
          "attempt": 1,
          "headline": "green first pass"
        },
        {
          "seq": 4,
          "event": "node_done",
          "node": "GATE_A",
          "milestone": 1,
          "attempt": 1,
          "headline": "1 simplification applied"
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
  }
}
```

```brief
You are the sdlc-graph ORCHESTRATOR. Drive milestone 1 of run `runeval-01` and then stop.

Read, and follow exactly:
  {{SKILL}}/SKILL.md            -- sections "3. Run the node" and "Replaying a milestone agent"
  {{SKILL}}/subagents/workflow-dispatch.md  -- "The milestone agent", "The milestone journal", "The return gate"
  {{SKILL}}/graph/state.md              -- "Provisional is not recorded", "Write points"

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
  state file : {{SCRATCH}}/docs/graph-runs/runeval-01/state.json   (you are its only writer)
  git repo   : {{SCRATCH}}                                    (branch `main`, one commit)

THE AGENT IS MOCKED. Instead of Agent(...), spawn it with this command, in the background:

  python3 {{EVALS}}/runs/mock_milestone.py \
      --script {{SCRATCH}}/agent-1.script.json \
      --journal {{SCRATCH}}/docs/graph-runs/runeval-01/journals/milestone-1.jsonl \
      --bundle-out {{SCRATCH}}/agent-1.bundle.json

It appends journal lines as it goes and writes its MILESTONE_BUNDLE to --bundle-out when it finishes.
Treat that bundle exactly as you would a real milestone agent's return value.

Because the milestone agent is mocked, the world-sourced checks have nothing real to read. Run the return gate
as far as the artifacts allow, and where a check cannot run, record that it did not — do not treat
it as passed.

Do not implement anything. Do not open a PR. Stop after the milestone's replay is written.
```

```assert
len(history) == 5                                  # the whole milestone block was replayed
history[0]["from"] == "BRANCH"                     # replayed in the milestone agent's order, from the start
history[-1]["from"] == "GATE_B"                    # ...through to the milestone agent's last transition
all(h.get("observation") for h in history)         # every transition carries the milestone agent's own line
all(h.get("verified") for h in history if h["from"] in {"BRANCH","IMPLEMENT","TEST","GATE_A","E2E","DEBUG"})   # every AGENT transition carries what the orchestrator checked
all(h.get("verified") is None for h in history if h["from"] not in {"BRANCH","IMPLEMENT","TEST","GATE_A","E2E","DEBUG"})   # ...and it never "verifies" a transition it ran itself (state.md)
len(journals.get("1") or []) >= 5                  # the milestone journalled every node as it ran
all(l.get("headline") for l in journals["1"] if l.get("event") == "node_done")   # no silent node
sorted(set(l["node"] for l in journals["1"] if l.get("event") == "node_done")) == sorted(set(h["from"] for h in history))   # R13: journal and trail describe the same milestone
(milestones[0].get("delivered") or "").strip() != ""    # the milestone says what it shipped
len(milestones[0].get("delivered") or "") <= 600        # ...in <=600 chars, per the schema
not inflight                                          # the progress object was nulled by its own replay
not state.get("in_flight")                          # ...and the in-flight list is empty again
any(h["from"] == "IMPLEMENT" and h["to"] == "TEST" for h in history)   # guard 9 collects the steps IMPLEMENT owns: the milestone plans a test file, TEST commits it, and this hop is still taken
state.get("status") != "BLOCKED"                   # ...so a milestone where nothing went wrong does not halt on a step another node owes
```

```control
# The failure this scenario exists to catch: history written from the bundle with nothing checked.
# Every other artifact is untouched and plausible.
for h in state["history"]:
    h["verified"] = None
state["milestones"][0]["delivered"] = None
```
