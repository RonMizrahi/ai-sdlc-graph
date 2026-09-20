# Run evals — the tier that executes

Every other suite here is **static**: it reads the spec and asks whether it contradicts itself. That
catches a great deal, and it structurally cannot catch an orchestrator that reads the contract
correctly and then *behaves* wrong — spawns before arming its monitor, writes `history[]` from a
bundle it never gated, or answers a dead milestone agent by waiting longer. Those are behaviours, and a
behaviour has to be run to be observed.

```bash
python3 ../run_scenario.py --list                        # every scenario and its claim
python3 ../run_scenario.py --self-test                   # every control must break its scenario
python3 ../run_scenario.py runs/scenarios/01-happy-milestone.md --setup # build the scratch run, print the brief
#   ...hand that brief to a subagent acting as the orchestrator...
python3 ../run_scenario.py runs/scenarios/01-happy-milestone.md --check # assert against what it left behind
```

## The two actor shapes, and why they differ

| | the thing under test | the other side |
|---|---|---|
| **01–06, 08, 09, 10** | the **orchestrator** | `mock_milestone.py` — a milestone agent with the model taken out |
| **07** | the **milestone agent** | a real milestone agent, deliberately abused by the orchestrator |

A mock root plus a mock milestone agent would prove nothing; a real root plus a real milestone agent proves nothing either,
because when the result disagrees you cannot tell which of them was wrong. So exactly one side is a
model, and the other is a script that does precisely what the scenario says — including returning a
dishonest bundle, which is the whole of scenario 03.

## Nothing is judged by asking a model how it did

The orchestrator is an agent and is not deterministic, but **the artifacts it leaves are**: a state
file, a set of journals, a git repo, and — where the point is something an actor *said* — a
`agent-reply.txt` it was told to write verbatim. Every assertion reads those, offline, and could be
re-run by someone who was not there.

A judged transcript would be a self-report from the thing being tested. That is the exact failure the
return gate exists to prevent, and building the harness that way would reproduce it one level up.

## What the last full drive found

Ten scenarios, ten orchestrators, none of which saw another's work. **Six spec defects**, and the
signal on every one was *independent agreement* — three readers taking the same sentence the same
wrong way is not three mistakes, it is one defect:

| Found by | The defect |
|---|---|
| **3 orchestrators** | Resume step 1's *"a mismatch or a missing field"* read as any absent key, which halts every healthy run — `stopped` is null until a halt, `trace` absent on anything older. |
| **3 orchestrators** | *"The halt signature"* — meaning a halt nobody RECORDED — read as the prescribed shape, so they wrote no `history[]` entry at all. Exactly the trail-ends-nowhere state § Recording a halt exists to prevent. |
| **3 orchestrators** | `Absent ⟹ reject` named no outcome, and each picked a different procedure. One would have asked the agent for a fact the gate exists to check. |
| **2 orchestrators** | R3 and § Write points read as a flat contradiction about `verified` on the `GATE_B` exit; one changed its behaviour over it. |
| **2 orchestrators** | Nulling `progress` on a dead agent deletes how far it got — and both invented the same workaround, which is the spec telling you what it should have said. |
| **1 orchestrator** | `SKILL.md` forbade what *Re-obtainable* prescribes, on the same field, in the one scenario built to test interrogation. |

Plus a mock that could not satisfy the contract it stands in for: it emitted no `ts`, so the
scenario built to test provisional supervision could not exercise the liveness signal the spec
routes on.

**The pattern is stable.** The deterministic suites find *drift* — a count, a path, a dead check.
The executing tier finds *contradictions*: rules that are individually sensible and cannot both be
obeyed. Nothing static reaches those, because each rule is fine where it is written.

## Every scenario carries a control, and `--self-test` is what makes this real

`--self-test` needs no agent. For each scenario it takes the **ideal artifacts** — what a correct run
would have left — and asserts two things:

1. The ideal artifacts **satisfy** the scenario's own assertions. A scenario nobody can pass is a
   scenario that will be "fixed" by weakening it.
2. After the `control` mutation, **at least one assertion fails**. A scenario whose assertions
   survive deliberately broken artifacts is a demo.

Both halves have already earned their keep: the first caught two assertions calling `max` and `len`
inside a generator expression, where `eval`'s locals are invisible and the names raised `NameError`
instead of comparing anything.

## What these found the first time they ran

Worth recording, because it is the argument for the tier existing:

- **A spec contradiction.** R13's *repairable* path says to replay the hops the bundle omitted, and
  `state.md` says only the agent that was there may author an `observation`. An orchestrator obeying
  both had to `BLOCK` on a milestone agent that merely tidied its story. Resolved by naming the journal
  `headline` as a legal source — it *is* the milestone agent's own line, written at the time.
- **A bug in `audit_run.py`.** `journal-agrees-with-history` flagged a correctly-**halted** run:
  refusing a fabricated bundle leaves the same shape as hiding the work, so the auditor accused a run
  of the thing it had just prevented.
- **Two under-specified fixtures of mine** whose bundles were too thin to pass the gate at all, so
  the scenario asserted an outcome no correct orchestrator could produce.

None of the three was reachable by reading the spec.

## Adding one

Copy the nearest scenario. Four fenced blocks, all required: `setup` (the starting state, the mock
milestone agent's script, and `ideal_artifacts`), `brief` (handed to the orchestrator verbatim; `{{SCRATCH}}` and
`{{EVALS}}` are substituted), `assert` (one expression per line, `#` for the reason), `control` (the
mutation that must break it).

Assert on **artifacts, never on prose**, and plant **one** defect per control — a control with two
defects cannot tell you which check caught it.
