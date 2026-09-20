# R1 — a real milestone agent, doing real work, journalling as it goes

**Claim:** a real milestone agent satisfies the journal contract on a real milestone — appending as it goes, with details a later milestone could act on.

The test `../runs/` structurally cannot run: there, the milestone agent is a script that satisfies the
journal contract by construction. Here it is a real agent writing real code against real
tests, and every assertion below is one it could actually fail.

```setup
{
  "repo": {
    "package.json": "{\n  \"name\": \"token-svc\",\n  \"version\": \"0.1.0\",\n  \"private\": true,\n  \"type\": \"module\",\n  \"scripts\": {\n    \"test:unit\": \"node --test \\\"test/unit/*.test.js\\\"\",\n    \"test:integration\": \"node --test \\\"test/integration/*.test.js\\\"\"\n  }\n}\n",
    "src/rate-limiter.js": "// Fixed-window rate limiter. Milestone 1 builds the TTL cache this will later use.\nexport function createLimiter({ max = 100 } = {}) {\n  const hits = new Map();\n  return {\n    allow(key) {\n      const n = (hits.get(key) ?? 0) + 1;\n      hits.set(key, n);\n      return n <= max;\n    },\n    reset() { hits.clear(); },\n  };\n}\n",
    "test/unit/rate-limiter.test.js": "import { test } from 'node:test';\nimport assert from 'node:assert/strict';\nimport { createLimiter } from '../../src/rate-limiter.js';\n\ntest('allows up to max then refuses', () => {\n  const l = createLimiter({ max: 2 });\n  assert.equal(l.allow('a'), true);\n  assert.equal(l.allow('a'), true);\n  assert.equal(l.allow('a'), false);\n});\n",
    "test/integration/service.test.js": "import { test } from 'node:test';\nimport assert from 'node:assert/strict';\nimport { createLimiter } from '../../src/rate-limiter.js';\n\ntest('limiter refuses past its window', () => {\n  const l = createLimiter({ max: 1 });\n  assert.equal(l.allow('k'), true);\n  assert.equal(l.allow('k'), false);\n});\n",
    "README.md": "# token-svc\n\nA tiny service used as a real target for sdlc-graph evals.\n"
  },
  "state": {
    "run_id": "realeval-R1",
    "schema_version": 5,
    "status": "RUNNING",
    "node": "STRATEGY",
    "plan_path": "docs/plans/realeval-R1-plan.md",
    "spec_path": null,
    "context": {
      "stack": "backend",
      "has_ui": false,
      "main_branch": "main",
      "branching": "A",
      "run_mode": "continuous",
      "standards_handshake": null,
      "host": "none",
      "unborn_main": false
    },
    "milestones": [
      {
        "id": 1,
        "name": "TTL cache for tokens",
        "branch": null,
        "worktree": null,
        "deps": [],
        "steps": [
          "Add src/token-store.js exporting createTokenStore({ ttlMs, now }) with put(key,value), get(key) returning null for a missing or expired entry, and sweep() dropping expired entries.",
          "Add test/unit/token-store.test.js covering put/get, expiry via the injected clock, and sweep()."
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
    "skipped_gates": [],
    "stopped": null,
    "trace": false,
    "debug_return_to": null,
    "qa": {
      "verdict": null,
      "qa_plan_path": null,
      "bugs": []
    }
  },
  "expect_path": [
    [
      "STRATEGY",
      "BRANCH"
    ],
    [
      "BRANCH",
      "IMPLEMENT"
    ],
    [
      "IMPLEMENT",
      "TEST"
    ],
    [
      "TEST",
      "GATE_A"
    ],
    [
      "GATE_A",
      "GATE_B"
    ],
    [
      "GATE_B",
      "CLOSE_OUT"
    ]
  ]
}
```

```brief
Drive **milestone 1 only** of run `realeval-R1`, then stop.

The repository is at `{{SCRATCH}}` — a real Node project with real test scripts (`npm run test:unit`,
`npm run test:integration`). It has no dependencies to install; `node --test` runs them directly.

The milestone's two steps are in the state file. A **real milestone agent** implements them — you do not
write the code yourself.

`context.has_ui` is `false`, so the itinerary is `BRANCH → IMPLEMENT → TEST → GATE_A → GATE_B`, and
the milestone agent's last transition is *into* `GATE_B`. You evaluate the exit from `GATE_B` yourself; with one
milestone and `branching: A`, that is edge 17 to `CLOSE_OUT`. **Stop there** — do not run
`CLOSE_OUT`, `PR`, `CI`, `QA` or anything after it.

`context.host` is `none`, so several Gate tools are structurally inapplicable. Ledger what genuinely
could not run; never record it as passed.

Report at the end: the order you did things in, what the return gate found, and anything you could
not do.
```

```assert
len(journals) == 1                                                                            # exactly one journal — one file per milestone
len(journals.get("1") or []) >= 5                                                             # the milestone journalled every node it ran
all(l.get("seq") for l in journals["1"])                                                      # every line is sequenced
[l["seq"] for l in journals["1"]] == sorted([l["seq"] for l in journals["1"]])                # seq increases across the milestone agent
torn.get("1", 0) == 0                                                                         # no torn line — the milestone agent finished its writes
all(l.get("milestone") in (1, "1") for l in journals["1"])                                    # the milestone agent wrote only its own milestone
done("BRANCH") and done("IMPLEMENT") and done("TEST") and done("GATE_A") and done("GATE_B")   # a node_done for every node on the itinerary
all((l.get("headline") or "").strip() for l in nd)                                            # every node_done carries a headline
all(len(l.get("headline") or "") <= 200 for l in nd)                                          # headlines stay within 200 chars
len(set(str(l.get("ts"))[:19] for l in nd)) >= 3                                              # timestamps SPREAD across the run — a journal with one timestamp was written from memory on the way out, which is the thing the append-on-exit rule forbids
all(isinstance(l.get("detail"), dict) for l in nd)                                            # every node_done carries a detail object
sum(len(json.dumps(l.get("detail") or {})) for l in nd) >= 2000                               # the details are substantial, not placeholders
(milestones[0].get("delivered") or "").strip() != ""                                          # the handover sentence exists — it is the BUNDLE's `notes`, recorded as `delivered`. This asserted `detail.for_next_milestone`, a field workflow-dispatch.md explicitly DELETED as "a third copy of the same sentence that nothing read". The assertion demanded it anyway, so it would have failed every honest agent forever; the real one that finally ran was right not to write it
any(l["detail"].get("interfaces") for l in nd)                                                # the interfaces a later milestone would call are named
not re.search(r"ghp_|glpat-|-----BEGIN|Bearer ", json.dumps(journals))                        # no credential reached the journal
len(history) == 6                                                                             # STRATEGY->BRANCH is the orchestrator's own, then the milestone agent's five
all(h.get("observation") for h in history)                                                    # every transition carries the milestone agent's own observation
all(h.get("verified") for h in history if h["from"] in ("BRANCH","IMPLEMENT","TEST","GATE_A","E2E","GATE_B") and h["to"] in ("BRANCH","IMPLEMENT","TEST","GATE_A","E2E","GATE_B","DEBUG"))   # every agent-replayed hop records what was checked; the hop OUT of the itinerary (GATE_B -> CLOSE_OUT) is the orchestrator's OWN and carries verified: null — it was the witness. The comment always said so; the expression keyed on `from` alone and caught it anyway
all(h.get("guard") for h in history)                                                          # every transition quotes the guard it took
(milestones[0].get("delivered") or "").strip() != ""                                          # the milestone says what it shipped
not inflight                                                                                  # the milestone was cleared from in_flight by its own replay
state.get("node") == "CLOSE_OUT"                                                              # the run stopped where the test said to stop
state.get("status") == "RUNNING"                                                              # ...without halting
```

```judge
Read the evidence bundle first, then the artifacts it points at. Decide these, and say which
are true, which are false, and what you read to decide:

1. **Was the journal written as the milestone agent went, or reconstructed at the end?** The timestamp-spread
   assertion is a proxy, not proof. Read the actual `ts` values and the headlines: do they read like
   a running account, or like a summary composed once the work was done?
2. **Is each `detail` genuinely useful to someone with none of the milestone agent's context?** Open two of
   them. Could the next milestone act on `interfaces` and `for_next_milestone` without reading the
   diff? A `detail` that restates the headline at greater length is a failure even when every key
   is present.
3. **Is the trail uniformly cheerful?** A real milestone has something awkward in it — a test that
   passed on the second run, a tool that was absent, a decision that could have gone the other way.
   If every observation is positive, either the run was trivial or the milestone agent is smoothing.
4. **Did the orchestrator verify, or narrate?** Read three `verified` strings. Do they name a
   command, a sha, an exit code — something checked — or do they paraphrase the milestone agent's claim?
5. **Does the ledger match reality?** `context.host` is `none`, so some gate tools are genuinely
   inapplicable. Is what was ledgered actually what could not run, and is anything recorded as
   passed that has no evidence behind it?
6. **Did the path deviate, and was the deviation honest?** A `DEBUG` round-trip is not a failure of
   this test. A path that matches the nominal one *because* something was skipped is.

Then give a verdict: PASS, PASS-WITH-ISSUES (naming each), or FAIL (naming what makes it a fail).
```

---

## Second real run — 08-08-2026 · verdict PASS, 23/23

Driven on the new layout: `docs/graph-runs/realeval-R1/` with `journals/milestone-1.jsonl`. A real
orchestrator, a real milestone agent, 11 journal lines arriving live, 3 commits, both suites re-run
by the orchestrator itself (R4 3/3 exact, R6 exit 0, R7 `direct` dispatch with its own
`git diff --name-only` matching `files_supplied`). Two ledger entries, both honest: `GATE_B`'s
`code-review` is `gh pr`-only and the repo has no remote, and `IMPLEMENT`'s preflight was never
asserted in the bundle.

**Three defects it found that no static check could.**

1. **R13 rejected every honest bundle.** It demanded a `trace[]` entry per journal `node_done`, and
   R3 says the trace never *leaves* `GATE_B` — which always has one. Two orchestrators hit it, each
   silently reading `claimed_to` as counting. Now stated.
2. **`context.host` was withheld from the agent** on the reasoning that "an agent never opens a PR".
   True and irrelevant: `GATE_B`'s `code-review` runs through `gh pr`, so without the host an agent
   cannot tell an absent tool from an inapplicable one. This run only completed because the
   orchestrator volunteered "this repo has no remote" in free text.
3. **`security-review` scoped its diff to the session cwd** — the marketplace checkout, not the
   target repo — and the milestone agent re-scoped it by hand. Under C that cwd is a worktree. An
   unscoped reviewer returns a clean diff of the wrong tree, and a false clean is indistinguishable
   from a pass.

**And two defects in this test itself**, both of which would have failed every honest agent forever:
it asserted `detail.for_next_milestone`, a field `workflow-dispatch.md` explicitly **deleted** as "a
third copy of the same sentence that nothing read"; and its `verified`-on-every-agent-hop assertion
keyed on `from` alone, so it caught the orchestrator's own `GATE_B → CLOSE_OUT` exit — the one hop
that correctly carries `verified: null`, as its own comment already said.

The fixture also declared `schema_version: 5` while carrying `paused`, `blocked`, `debug` and
`milestones[].node` — all removed at 5. The *number* matched, so the unconditional halt rule could
not see it. Normalised.

## First real run — 07-08-2026 · verdict PASS

23/23 assertions, path exact. The two that failed on the first attempt were **defects in this test**,
not in the run, and both are worth keeping written down:

1. `expect_path` started at `BRANCH → IMPLEMENT`, but the fixture's start node is `STRATEGY` — so the
   orchestrator correctly had to evaluate edge 6 and write `STRATEGY → BRANCH` itself before spawning
   anything. Six transitions, not five.
2. `all(h.verified)` demanded a `verified` string on **every** transition. A hop the orchestrator ran
   *itself* has none, correctly: `verified` is what it checked about a node it did **not** run, and on
   its own hop it was the witness. Demanding it everywhere contradicts `state.md`'s two-author rule.

Judged on the rubric: the journal was written **as it went** — 11 lines, 11 distinct timestamps over
16 minutes, `node_start`/`node_done` pairs and a heartbeat inside the long `GATE_A`. The `detail`
blocks were genuinely useful: `interfaces` carried the exact signature, and `gotchas` recorded that
expired entries are not reclaimed by `get()`, so the Map grows unbounded without a `sweep()` cadence —
something a later milestone could act on without reading the diff. The trail was not cheerful: it
recorded that only about a fifth of the coding standard applied, that both gates ran degraded, and
that no integration test was added and why.

### Three spec problems this run found — all three fixed, each with its own check

Fixed in `workflow-dispatch.md` (07-08-2026); the checks that would have caught each are
`r14-exempts-the-runs-own-bookkeeping`, `r10-ledgers-without-forbidding-the-transition` and
`r7-separates-no-dispatcher-from-a-dead-dispatch` in `spec_consistency.py`, with five negative
controls between them. **This is the tier's whole argument**: all three were invisible to a suite
that only reads the spec, because each is a rule that is internally coherent and only wrong against
the world.

- **R12's "working tree clean" can never pass** when run state lives inside the repo under test. The
  orchestrator's own state writes dirty the tree, and the milestone agent correctly reported the tree as
  not-pristine on entry — *caused by the orchestrator*. R12 needs to exempt `docs/graph-runs/`.
- **R9 contradicts `edges.md` on the `host: none` path.** R9 says a bare node ledger entry forbids
  a pass-shaped transition for that node; `edges.md` says an inapplicable reviewer is ledgered and the
  run proceeds via 13/14 and 17. Both gates were ledgered here, so the two rules pointed opposite
  ways. The run followed `edges.md` (self-declared authoritative for guards) and recorded that neither
  gate passed — the right call, but the spec should not have made it a judgement.
- **R7 cannot distinguish "the dispatch died" from "there is no dispatch mechanism here."** No
  `Workflow` tool exists in a subagent session, so Gate A ran its four steps by direct dispatch. The
  run refused to invent a `run_id` and refused to charge `GATE_A-dispatch` for a dispatch that never
  happened. Both correct, and neither is what R7 describes.
