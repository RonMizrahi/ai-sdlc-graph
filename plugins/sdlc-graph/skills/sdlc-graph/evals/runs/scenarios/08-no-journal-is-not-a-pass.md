# 08 — a run with no journals at all, and a check that says so out loud

**Claim:** an empty journal makes R13 NOT RUN — recorded as not-run, never as a pass — when the bundle's own `outcome` agrees the agent never got going. The missing check is ledgered, not waved through, and not mistaken for a halt of its own.

A `schema_version: 2` file, or a milestone agent that died before its first append, leaves no journal. R13 then
has nothing to compare and must report that — a missing check is not a passed one, which is the rule
the whole graph turns on and the one most easily lost at the edges.

The other fourteen checks still have to hold, so the run is not blocked either. Getting this wrong in
the safe direction — blocking every legacy run — is how a checker gets deleted.

**This bundle is also the only one in the suite that is degenerate in two further, deliberate ways.**
It reports `evidence.tests: "not-run"` — the sole true value for a milestone `blocked` at `IMPLEMENT`,
which `pass`/`fail`/`absent` cannot express and which R0 therefore admits exactly where the trace
never entered `TEST`. And it carries `working_tree_clean` and `worktree_removed`, two keys this
schema does not declare: they are dropped **unread** and named in `verified`. Neither is a halt — a
run that halts on a stale key burns real work, and a run that ignores one silently loses the only
thing it proves.

```setup
{
  "state": {
    "run_id": "runeval-08",
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
      "lines": [],
      "bundle": {
        "milestone_id": 1,
        "outcome": "blocked",
        "notes": "Nothing shipped: blocked at IMPLEMENT before the first commit.",
        "trace": [
          {
            "from": "BRANCH",
            "claimed_to": "IMPLEMENT",
            "result": {},
            "observation": "branch created"
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
          }
        },
        "evidence": {
          "base_sha": "1111111111111111111111111111111111111111",
          "head_sha": "3333333333333333333333333333333333333333",
          "commits": [],
          "tests": {
            "unit": "not-run",
            "integration": "not-run",
            "commands": {
              "unit": "test:unit",
              "integration": "test:integration"
            }
          },
          "worktree_removed": false,
          "working_tree_clean": true
        },
        "blocked": {
          "at_node": "IMPLEMENT",
          "why": "step s1 is not implementable as planned: the module it extends does not exist on this branch",
          "tried": [
            "read the plan step",
            "searched the tree for the module",
            "checked the branch point"
          ]
        }
      }
    }
  },
  "ideal_artifacts": {
    "state": {
      "run_id": "runeval-08",
      "schema_version": 5,
      "status": "BLOCKED",
      "node": "IMPLEMENT",
      "context": {
        "stack": "backend",
        "has_ui": false,
        "main_branch": "main",
        "branching": "A"
      },
      "milestones": [
        {
          "id": 1,
          "delivered": null
        }
      ],
      "cursor": 1,
      "in_flight": [],
      "history": [
        {
          "from": "BRANCH",
          "to": "IMPLEMENT",
          "milestone": 1,
          "observation": "branch runeval-08/m1 cut from main",
          "verified": "R13 NOT RUN — the journal is empty, which is a missing check and never a pass; the bundle's own outcome agrees the agent never got going. Dropped unread: working_tree_clean, worktree_removed — neither is declared by the schema. evidence.tests not-run is legal: the trace never entered TEST"
        },
        {
          "from": "IMPLEMENT",
          "to": "BLOCKED",
          "guard": "",
          "milestone": 1,
          "observation": "blocked at IMPLEMENT: the step is not implementable as planned"
        }
      ],
      "attempts": {},
      "skipped_gates": [],
      "integration": {
        "branch": null,
        "merged": []
      },
      "stopped": {
        "kind": "blocked",
        "reason": "the agent returned outcome=blocked at IMPLEMENT: step s1 is not implementable as planned. R13 was NOT RUN — the journal is empty — and is recorded as not-run, never as a pass.",
        "at_node": "IMPLEMENT",
        "at_milestone": 1,
        "guards_tested": [
          "edge 9 — every step this node owns is committed: no commits exist"
        ],
        "tried": [
          "ran R0-R13; R13 NOT RUN on an empty journal",
          "confirmed the bundle claims no gate"
        ]
      }
    },
    "journals": {}
  }
}
```

```brief
You are the sdlc-graph ORCHESTRATOR. Drive milestone 1 of run `runeval-08`, then stop.

Read and follow:
  {{SKILL}}/SKILL.md                         -- "Replaying a milestone agent"
  {{SKILL}}/subagents/workflow-dispatch.md  -- "The return gate", especially R13

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
  state file : {{SCRATCH}}/docs/graph-runs/runeval-08/state.json   (you are its only writer)

THE WORLD IS MOCKED TOO. The scratch run is not its own git repo and the mock agent makes no
commits, so the shas in its bundle are placeholders that resolve to nothing. That is the harness,
not a fabrication plant: treat every world-sourced check (R4, R5, R6, R7's diff, most of R12) as
NOT RUN, record it as not-run — never as passed — and ledger what it could not back. The scenario
under test is whatever this brief names, not the absence of a repo.

THE AGENT IS MOCKED, and this one writes NO journal. Spawn it with:

  python3 {{EVALS}}/runs/mock_milestone.py \
      --script {{SCRATCH}}/agent-1.script.json \
      --journal {{SCRATCH}}/docs/graph-runs/runeval-08/journals/milestone-1.jsonl \
      --bundle-out {{SCRATCH}}/agent-1.bundle.json

Run the return gate. Where a check cannot run, say so in what you record — do not count it as passed.
```

```assert
state.get("status") == "BLOCKED"                                          # the agent returned outcome=blocked; the orchestrator maps it to IMPLEMENT's on-failure row
not any(journals.values())                                                # the journal is empty — 0 lines, whether or not the file exists
"R13" in json.dumps([h.get("verified") for h in history] + (state.get("skipped_gates") or []) + [state.get("stopped")])   # ...and the RECORD says so — in verified, the ledger, or stopped; which of the three is the orchestrator's call
"R13" in json.dumps(state.get("stopped") or {})                           # the halt names it too, so a resume does not think R13 passed
len([h for h in history if h.get("to") != "BLOCKED"]) == 1   # only the one hop the bundle actually traced was replayed
len(history) <= 2                                            # ...plus at most the one halt entry § Recording a halt mandates
all(h.get("guard") == "" for h in history if h.get("to") == "BLOCKED")   # ...whose guard is empty: no row declares an `on failure` exit
all(h.get("verified") for h in history if h["from"] in {"BRANCH","IMPLEMENT","TEST","GATE_A","E2E","DEBUG"} and h.get("to") != "BLOCKED")   # every AGENT transition says what WAS checked
(milestones[0].get("delivered") or None) is None                          # nothing shipped, so nothing is claimed shipped
"R0" not in ((state.get("stopped") or {}).get("reason") or "") and (state.get("stopped") or {}).get("at_node") == "IMPLEMENT"   # the halt is the agent's blocked step, NOT a schema complaint: `not-run` is the only true value for a suite on a trace that never entered TEST, and R0 admits it exactly there
all("working_tree_clean" in (h.get("verified") or "") for h in history[:1])   # the bundle carried two fields this schema does not declare; they are dropped UNREAD and the record names them — neither ignored nor fatal
```

```control
# Absent read as fine: the gate is recorded as fully passed, and every trace of the unrun check is
# gone from all three places it could have been recorded — the trail, the ledger, and the halt. A
# run that cannot say WHICH check did not run is a run reporting fourteen checks it ran thirteen of.
for h in state["history"]:
    h["verified"] = "return gate passed"
state["skipped_gates"] = []
state["stopped"] = {"kind": "blocked", "reason": "agent blocked at IMPLEMENT",
                    "at_node": "IMPLEMENT", "at_milestone": 1,
                    "guards_tested": ["edge 9"], "tried": ["read the bundle"]}
```
