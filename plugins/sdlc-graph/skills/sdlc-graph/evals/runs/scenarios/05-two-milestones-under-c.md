# 05 — two milestones at once, and neither writes the other's file

**Claim:** under C each milestone agent owns exactly one journal, and the replays stay serial in the trail.

Strategy C is the reason the journal is per milestone rather than per run. Two milestones running
concurrently against one file would give it two writers and no lock, which is the same
race the run state file avoids by having exactly one.

The two mock agents here emit on deliberately different timings so their lines interleave in
real time. What must NOT interleave is the trail: a replay is written one transition at a
time, after that milestone agent's bundle passed the gate, so milestone agent 1's block is contiguous and so is
milestone agent 2's.

```setup
{
  "state": {
    "run_id": "runeval-05",
    "schema_version": 5,
    "status": "RUNNING",
    "node": "BRANCH",
    "context": {
      "stack": "backend",
      "has_ui": false,
      "main_branch": "main",
      "branching": "C"
    },
    "milestones": [
      {
        "id": 1,
        "name": "token store",
        "branch": null,
        "worktree": null,
        "deps": [],
        "steps": [
          "s1"
        ],
        "is_fix": false,
        "touches_ui": false,
        "delivered": null
      },
      {
        "id": 2,
        "name": "rate limiter",
        "branch": null,
        "worktree": null,
        "deps": [],
        "steps": [
          "s2"
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
      "lines": [
        {
          "seq": 1,
          "event": "node_done",
          "node": "BRANCH",
          "milestone": 1,
          "attempt": 1,
          "headline": "m1: branch finished",
          "_delay_s": 0.15
        },
        {
          "seq": 2,
          "event": "node_done",
          "node": "IMPLEMENT",
          "milestone": 1,
          "attempt": 1,
          "headline": "m1: implement finished",
          "_delay_s": 0.15
        },
        {
          "seq": 3,
          "event": "node_done",
          "node": "TEST",
          "milestone": 1,
          "attempt": 1,
          "headline": "m1: test finished",
          "_delay_s": 0.15
        },
        {
          "seq": 4,
          "event": "node_done",
          "node": "GATE_A",
          "milestone": 1,
          "attempt": 1,
          "headline": "m1: gate_a finished",
          "_delay_s": 0.15
        },
        {
          "seq": 5,
          "event": "node_done",
          "node": "GATE_B",
          "milestone": 1,
          "attempt": 1,
          "headline": "m1: gate_b finished",
          "_delay_s": 0.15
        }
      ],
      "bundle": {
        "milestone_id": 1,
        "outcome": "completed",
        "notes": "milestone 1 shipped its module.",
        "trace": [
          {
            "from": "BRANCH",
            "claimed_to": "IMPLEMENT",
            "result": {},
            "observation": "m1: BRANCH ok"
          },
          {
            "from": "IMPLEMENT",
            "claimed_to": "TEST",
            "result": {},
            "observation": "m1: IMPLEMENT ok"
          },
          {
            "from": "TEST",
            "claimed_to": "GATE_A",
            "result": {},
            "observation": "m1: TEST ok"
          },
          {
            "from": "GATE_A",
            "claimed_to": "GATE_B",
            "result": {},
            "observation": "m1: GATE_A ok"
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
    },
    "2": {
      "lines": [
        {
          "seq": 1,
          "event": "node_done",
          "node": "BRANCH",
          "milestone": 2,
          "attempt": 1,
          "headline": "m2: branch finished",
          "_delay_s": 0.1
        },
        {
          "seq": 2,
          "event": "node_done",
          "node": "IMPLEMENT",
          "milestone": 2,
          "attempt": 1,
          "headline": "m2: implement finished",
          "_delay_s": 0.1
        },
        {
          "seq": 3,
          "event": "node_done",
          "node": "TEST",
          "milestone": 2,
          "attempt": 1,
          "headline": "m2: test finished",
          "_delay_s": 0.1
        },
        {
          "seq": 4,
          "event": "node_done",
          "node": "GATE_A",
          "milestone": 2,
          "attempt": 1,
          "headline": "m2: gate_a finished",
          "_delay_s": 0.1
        },
        {
          "seq": 5,
          "event": "node_done",
          "node": "GATE_B",
          "milestone": 2,
          "attempt": 1,
          "headline": "m2: gate_b finished",
          "_delay_s": 0.1
        }
      ],
      "bundle": {
        "milestone_id": 2,
        "outcome": "completed",
        "notes": "milestone 2 shipped its module.",
        "trace": [
          {
            "from": "BRANCH",
            "claimed_to": "IMPLEMENT",
            "result": {},
            "observation": "m2: BRANCH ok"
          },
          {
            "from": "IMPLEMENT",
            "claimed_to": "TEST",
            "result": {},
            "observation": "m2: IMPLEMENT ok"
          },
          {
            "from": "TEST",
            "claimed_to": "GATE_A",
            "result": {},
            "observation": "m2: TEST ok"
          },
          {
            "from": "GATE_A",
            "claimed_to": "GATE_B",
            "result": {},
            "observation": "m2: GATE_A ok"
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
      "run_id": "runeval-05",
      "schema_version": 5,
      "status": "RUNNING",
      "node": "CONSOLIDATE",
      "context": {
        "stack": "backend",
        "has_ui": false,
        "main_branch": "main",
        "branching": "C"
      },
      "milestones": [
        {
          "id": 1,
          "name": "token store",
          "branch": null,
          "worktree": null,
          "deps": [],
          "steps": [
            "s1"
          ],
          "is_fix": false,
          "touches_ui": false,
          "delivered": "TokenStore.put/get/evict, 15m TTL."
        },
        {
          "id": 2,
          "name": "rate limiter",
          "branch": null,
          "worktree": null,
          "deps": [],
          "steps": [
            "s2"
          ],
          "is_fix": false,
          "touches_ui": false,
          "delivered": "RateLimiter.allow(key), 100/min sliding window."
        }
      ],
      "cursor": 2,
      "in_flight": [],
      "history": [
        {
          "from": "BRANCH",
          "to": "IMPLEMENT",
          "milestone": 1,
          "observation": "m1: left BRANCH",
          "verified": "confirmed against git and the re-run suite"
        },
        {
          "from": "IMPLEMENT",
          "to": "TEST",
          "milestone": 1,
          "observation": "m1: left IMPLEMENT",
          "verified": "confirmed against git and the re-run suite"
        },
        {
          "from": "TEST",
          "to": "GATE_A",
          "milestone": 1,
          "observation": "m1: left TEST",
          "verified": "confirmed against git and the re-run suite"
        },
        {
          "from": "GATE_A",
          "to": "GATE_B",
          "milestone": 1,
          "observation": "m1: left GATE_A",
          "verified": "confirmed against git and the re-run suite"
        },
        {
          "from": "GATE_B",
          "to": "BRANCH",
          "milestone": 1,
          "observation": "m1: left GATE_B",
          "verified": null
        },
        {
          "from": "BRANCH",
          "to": "IMPLEMENT",
          "milestone": 2,
          "observation": "m2: left BRANCH",
          "verified": "confirmed against git and the re-run suite"
        },
        {
          "from": "IMPLEMENT",
          "to": "TEST",
          "milestone": 2,
          "observation": "m2: left IMPLEMENT",
          "verified": "confirmed against git and the re-run suite"
        },
        {
          "from": "TEST",
          "to": "GATE_A",
          "milestone": 2,
          "observation": "m2: left TEST",
          "verified": "confirmed against git and the re-run suite"
        },
        {
          "from": "GATE_A",
          "to": "GATE_B",
          "milestone": 2,
          "observation": "m2: left GATE_A",
          "verified": "confirmed against git and the re-run suite"
        },
        {
          "from": "GATE_B",
          "to": "CONSOLIDATE",
          "milestone": 2,
          "observation": "m2: left GATE_B",
          "verified": null
        }
      ],
      "attempts": {},
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
          "headline": "BRANCH done on m1"
        },
        {
          "seq": 2,
          "event": "node_done",
          "node": "IMPLEMENT",
          "milestone": 1,
          "attempt": 1,
          "headline": "IMPLEMENT done on m1"
        },
        {
          "seq": 3,
          "event": "node_done",
          "node": "TEST",
          "milestone": 1,
          "attempt": 1,
          "headline": "TEST done on m1"
        },
        {
          "seq": 4,
          "event": "node_done",
          "node": "GATE_A",
          "milestone": 1,
          "attempt": 1,
          "headline": "GATE_A done on m1"
        },
        {
          "seq": 5,
          "event": "node_done",
          "node": "GATE_B",
          "milestone": 1,
          "attempt": 1,
          "headline": "GATE_B done on m1"
        }
      ],
      "2": [
        {
          "seq": 1,
          "event": "node_done",
          "node": "BRANCH",
          "milestone": 2,
          "attempt": 1,
          "headline": "BRANCH done on m2"
        },
        {
          "seq": 2,
          "event": "node_done",
          "node": "IMPLEMENT",
          "milestone": 2,
          "attempt": 1,
          "headline": "IMPLEMENT done on m2"
        },
        {
          "seq": 3,
          "event": "node_done",
          "node": "TEST",
          "milestone": 2,
          "attempt": 1,
          "headline": "TEST done on m2"
        },
        {
          "seq": 4,
          "event": "node_done",
          "node": "GATE_A",
          "milestone": 2,
          "attempt": 1,
          "headline": "GATE_A done on m2"
        },
        {
          "seq": 5,
          "event": "node_done",
          "node": "GATE_B",
          "milestone": 2,
          "attempt": 1,
          "headline": "GATE_B done on m2"
        }
      ]
    }
  }
}
```

```brief
You are the sdlc-graph ORCHESTRATOR. Run `runeval-05` is strategy C with two
INDEPENDENT milestones. Spawn BOTH agents, then replay both, then stop.

Read and follow:
  {{SKILL}}/SKILL.md            -- "3. Run the node", "While a milestone agent runs", "Replaying a milestone agent"
  {{SKILL}}/graph/state.md -- `in_flight` and `milestones[].progress`

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
  state file : {{SCRATCH}}/docs/graph-runs/runeval-05/state.json   (you are its only writer)

THE WORLD IS MOCKED TOO. The scratch run is not its own git repo and the mock agent makes no
commits, so the shas in its bundle are placeholders that resolve to nothing. That is the harness,
not a fabrication plant: treat every world-sourced check (R4, R5, R6, R7's diff, most of R12) as
NOT RUN, record it as not-run — never as passed — and ledger what it could not back. The scenario
under test is whatever this brief names, not the absence of a repo.

THE AGENTS ARE MOCKED. Spawn each in the background, one command per milestone:

  python3 {{EVALS}}/runs/mock_milestone.py \
      --script {{SCRATCH}}/agent-<N>.script.json \
      --journal {{SCRATCH}}/docs/graph-runs/runeval-05/journals/milestone-<N>.jsonl \
      --bundle-out {{SCRATCH}}/agent-<N>.bundle.json

...for N in 1 and 2. Gate and replay each bundle as it arrives.
```

```assert
len(journals) == 2                                                                       # two milestones, two journals — never one shared file
all(len(set(l["milestone"] for l in v)) == 1 for v in journals.values())                 # each journal contains ONE milestone: no milestone agent wrote into a sibling
all(str(v[0]["milestone"]) == k for k, v in journals.items())                            # ...and the file is named for the milestone inside it
len([x for x in history if x.get("milestone") == 1]) == 5                                # milestone agent 1's block was replayed whole
len([x for x in history if x.get("milestone") == 2]) == 5                                # milestone agent 2's block was replayed whole
[x.get("milestone") for x in history] == sorted([x.get("milestone") for x in history])   # the replays are SERIAL — one milestone block, then the other, never interleaved in the trail
all(m.get("delivered") for m in milestones)                                              # both milestones say what they shipped
not inflight                                                                                # both progress objects were nulled by their own replays
all(x.get("verified") for x in history if x["from"] in {"BRANCH","IMPLEMENT","TEST","GATE_A","E2E","DEBUG"})   # every AGENT transition was checked before it was written
all(x.get("verified") is None for x in history if x["from"] not in {"BRANCH","IMPLEMENT","TEST","GATE_A","E2E","DEBUG"})   # ...and GATE_B's exit is the orchestrator's own, so it verifies nothing
```

```control
# Both agents appending to one file — the race the per-milestone split exists to remove.
journals["1"] = journals["1"] + journals["2"]
del journals["2"]
```
