# 10 — a traced run advances, and the orchestrator writes nothing into `history/`

**Claim:** `history/` has exactly one writer, and it is the snapshot hook. The orchestrator reads
`trace`, carries it forward untouched, and never adds a file of its own.

This is the shape that has already gone wrong once in this plugin, in a different place: the
milestone journal. Give a file two plausible writers and they will disagree about the sequence, and
a sequence that disagrees with itself is worse than none — a numbered trace exists precisely so a
gap means *"a state was lost"* rather than *"someone numbered differently"*.

The temptation here is real and it is helpful-looking. An orchestrator that has just read
`state.md` § *`trace`* knows the run is traced, knows it is about to overwrite `state.json`, and can
see that writing the snapshot itself would be one line. It must not. The hook fires on the write
that has *already happened*; an orchestrator snapshotting beforehand records a state the run was
never in, and the two writers then interleave their numbering.

The run below is mid-milestone with `trace: true` and three snapshots already on disk. The agent
returns a clean bundle, the orchestrator runs the return gate and replays it. Afterwards
`history[]` has grown, `state.json` still says `trace: true`, and **`history/` is byte-for-byte the
three files it started with**.

```setup
{
  "state": {
    "run_id": "runeval-10",
    "schema_version": 5,
    "status": "RUNNING",
    "node": "BRANCH",
    "trace": true,
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
    "history": [
      {
        "from": "INTAKE",
        "to": "PLAN",
        "guard": "spec supplied",
        "milestone": null,
        "observation": "spec supplied at intake, so SPEC was skipped"
      },
      {
        "from": "PLAN",
        "to": "STRATEGY",
        "guard": "on disk AND approved",
        "milestone": null,
        "observation": "one milestone, plan approved"
      },
      {
        "from": "STRATEGY",
        "to": "BRANCH",
        "guard": "A/B/C, deps acyclic, has_ui is a boolean",
        "milestone": null,
        "observation": "strategy A, has_ui false"
      }
    ],
    "attempts": {},
    "skipped_gates": [],
    "integration": {
      "branch": null,
      "merged": []
    }
  },
  "history": [
    "0001_INTAKE-created_20260808T090000Z.json",
    "0002_INTAKE-to-PLAN_20260808T090100Z.json",
    "0003_PLAN-to-STRATEGY_20260808T090200Z.json",
    "0004_STRATEGY-to-BRANCH_20260808T090300Z.json"
  ],
  "agents": {
    "1": {
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
      ],
      "bundle": {
        "branch": "selftest/run",
        "outcome": "completed",
        "trace": [
          {
            "from": "BRANCH",
            "observation": "branch created off main",
            "claimed_to": "IMPLEMENT",
            "result": {}
          },
          {
            "from": "IMPLEMENT",
            "observation": "2 steps committed, 1 commit each",
            "claimed_to": "TEST",
            "result": {}
          },
          {
            "from": "TEST",
            "observation": "14 unit + 3 integration green",
            "claimed_to": "GATE_A",
            "result": {}
          },
          {
            "from": "GATE_A",
            "observation": "3 files reviewed, no findings",
            "claimed_to": "GATE_B",
            "result": {}
          }
        ],
        "attempt_counts": {},
        "notes": "nothing surprising",
        "milestone_id": 1,
        "evidence": {
          "base_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "head_sha": "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
          "commits": [
            "cccccccccccccccccccccccccccccccccccccccc"
          ],
          "tests": {
            "unit": "pass",
            "integration": "pass",
            "commands": {
              "unit": "npm run test:unit",
              "integration": "npm run test:integration"
            }
          },
          "gate_a": {
            "clean": true,
            "rerun_recommended": false,
            "run_id": "wf_runeval_1",
            "skipped_steps": [],
            "dispatch": "workflow",
            "tools_asserted": true,
            "groups_completed": 1,
            "groups_total": 1,
            "files_supplied": 3,
            "uncovered_count": 0
          },
          "gate_b": {
            "reviewer": "ran",
            "diff_base": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
            "findings_count": 0,
            "tests_after": "green"
          },
          "e2e": {
            "state": "not-applicable",
            "specs_authored": 0,
            "spec_paths": [],
            "mocked": false,
            "command": null
          }
        },
        "preflight": {},
        "skipped_gates_proposed": []
      }
    }
  },
  "ideal_artifacts": {
    "state": {
      "run_id": "runeval-10",
      "schema_version": 5,
      "status": "RUNNING",
      "node": "CLOSE_OUT",
      "trace": true,
      "milestones": [
        {
          "id": 1,
          "branch": "selftest/run",
          "base_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
          "journal": "docs/graph-runs/runeval-10/journals/milestone-1.jsonl",
          "agent_id": "mock-1",
          "spawned_at_history_len": 0,
          "delivered": "rate limiter: token bucket + per-key store, 14 unit and 3 integration tests",
          "progress": null
        }
      ],
      "cursor": 1,
      "in_flight": [],
      "history": [
        {
          "from": "INTAKE",
          "to": "PLAN",
          "guard": "spec supplied",
          "milestone": null,
          "observation": "spec supplied at intake, so SPEC was skipped"
        },
        {
          "from": "PLAN",
          "to": "STRATEGY",
          "guard": "on disk AND approved",
          "milestone": null,
          "observation": "one milestone, plan approved"
        },
        {
          "from": "STRATEGY",
          "to": "BRANCH",
          "guard": "A/B/C, deps acyclic, has_ui is a boolean",
          "milestone": null,
          "observation": "strategy A, has_ui false"
        },
        {
          "from": "BRANCH",
          "to": "IMPLEMENT",
          "milestone": 1,
          "observation": "branch created off main",
          "verified": "R4 NOT RUN (no repo)"
        },
        {
          "from": "IMPLEMENT",
          "to": "TEST",
          "milestone": 1,
          "observation": "2 steps committed, 1 commit each",
          "verified": "R4/R5 NOT RUN (no repo)"
        },
        {
          "from": "TEST",
          "to": "GATE_A",
          "milestone": 1,
          "observation": "14 unit + 3 integration green",
          "verified": "R6 NOT RUN (no suite)"
        },
        {
          "from": "GATE_A",
          "to": "GATE_B",
          "milestone": 1,
          "observation": "3 files reviewed, no findings",
          "verified": "R7/R8 NOT RUN (no repo)"
        },
        {
          "from": "GATE_B",
          "to": "CLOSE_OUT",
          "guard": "tests green after review-and-fixes **and** ((`branching ∈ {A,B}` **and** no milestone remains) **or** (`branching == C` **and** `integration.branch != null` — the integration pass))",
          "milestone": 1,
          "observation": "gate B clean; one milestone, strategy A, so the tail begins",
          "verified": null
        }
      ],
      "attempts": {},
      "skipped_gates": [
        {
          "node": "GATE_A",
          "reason": "world-sourced checks not runnable in the harness",
          "at_milestone": 1
        }
      ]
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
    },
    "history": [
      "0001_INTAKE-created_20260808T090000Z.json",
      "0002_INTAKE-to-PLAN_20260808T090100Z.json",
      "0003_PLAN-to-STRATEGY_20260808T090200Z.json",
      "0004_STRATEGY-to-BRANCH_20260808T090300Z.json"
    ]
  }
}
```

```brief
You are the sdlc-graph ORCHESTRATOR. Run milestone 1 of run `runeval-10` to its return, run the
return gate, replay the bundle, and STOP.

Read and follow:
  {{SKILL}}/SKILL.md                            -- "3. Run the node", "Replaying a milestone agent"
  {{SKILL}}/subagents/workflow-dispatch.md      -- "The return gate"
  {{SKILL}}/graph/state.md                      -- "`trace`", "Write points"

THIS RUN IS TRACED. `state.json` carries `trace: true`, and the run directory already has a
`history/` with three snapshots in it. Read `state.md` § `trace` before you touch anything: it says
who writes that directory. Do what it says.

WHERE THE RUN IS. The state file's `node` says which node the run is in — read it, and start from
there. When the milestone agent returns, evaluate `GATE_B`'s exit guard YOURSELF: the agent runs
Gate B, but its exits are yours.

The run lives at: {{SCRATCH}}
  state file : {{SCRATCH}}/docs/graph-runs/runeval-10/state.json   (you are its only writer)

THE WORLD IS MOCKED TOO. The scratch run is not its own git repo and the mock agent makes no
commits, so the shas in its bundle are placeholders that resolve to nothing. Treat every
world-sourced check (R4, R5, R6, R7's diff, most of R12) as NOT RUN, record it as not-run — never as
passed — and ledger what it could not back. The scenario under test is whatever this brief names,
not the absence of a repo.

THE AGENT IS MOCKED. Spawn it in the background with:

  python3 {{EVALS}}/runs/mock_milestone.py \
      --script {{SCRATCH}}/agent-1.script.json \
      --journal {{SCRATCH}}/docs/graph-runs/runeval-10/journals/milestone-1.jsonl \
      --bundle {{SCRATCH}}/agent-1.bundle.json

It emits five nodes and returns a clean bundle. Gate it, replay it, record `delivered`, and report.
```

```assert
state.get("trace") is True                         # the flag survived the replay untouched
len(history) == 8                                  # 3 seeded + the 4 agent-owned hops + the orchestrator's own GATE_B exit
(milestones[0].get("delivered") or "") != ""       # ...and the milestone's rollup was written
len(snapshots) == 4                                # history/ is EXACTLY what it started as — a helpful orchestrator ADDS
sorted(snapshots) == ["0001_INTAKE-created_20260808T090000Z.json", "0002_INTAKE-to-PLAN_20260808T090100Z.json", "0003_PLAN-to-STRATEGY_20260808T090200Z.json", "0004_STRATEGY-to-BRANCH_20260808T090300Z.json"]   # ...the same four, unrenamed
```

```control
# The helpful shortcut: the orchestrator knows the run is traced and knows it is about to write the
# state file, so it snapshots the state itself. One line, plausible, and it gives `history/` a
# second writer whose numbering interleaves with the hook's.
snapshots = snapshots + ["0004_GATE_A-to-GATE_B_20260808T091500Z.json"]
```
