---
name: graph-run-reviewer
description: >-
  Review a finished or stuck sdlc-graph run — read its state file, its milestone journals and
  (when it was traced) every state it passed through, find what actually went wrong, and write the
  eval that would have caught it. Runs the offline auditor first for the mechanical defects, then
  looks for the classes no static check reaches: an observation that contradicts the journal, a gate
  that passed too cleanly, a ledger entry that does not match the tools present, a transition that
  was legal but wrong. Every finding is triaged as a spec defect, a run defect, or an eval gap — and
  every eval gap is closed with a real test, at the tier that catches it. Read-only with respect to
  the run: it never fixes, resumes, or edits the run it is reviewing. Invoked by a human, never
  automatically.
when_to_use: >-
  review this graph run, what went wrong in that run, audit the sdlc run, why did the run block,
  check the run history, review the graph run and add tests for what it found
disable-model-invocation: true
user-invocable: true
allowed-tools: Read, Grep, Glob, Bash, Write, Edit
argument-hint: "[<run-id> | <path-to-state.json>] [--repo <path>] [--no-evals]"
---

# Graph Run Reviewer

## Goal

**Turn one run into one or more tests.** A run that went wrong and produced no eval is a run whose
lesson expires with the person who read it. This skill exists to stop that: it reads the artifacts a
run leaves behind, works out what actually happened, and — for anything nothing would have
caught — writes the check that catches it next time.

It is deliberately **not** a remediation tool. It never resumes the run, never fixes the code, never
edits the state file. The retired monitor agent was trustworthy for exactly that reason, and it is
the reason this can be pointed at a live run without changing its outcome.

## Use When

- A run reached `BLOCKED` and you want to know whether the graph or the orchestrator was at fault.
- A run reached `DONE` and something about it felt wrong.
- After a change to the graph, on a run that exercised it.
- You want the run's lessons turned into tests before you forget them.

## Do Not Use When

- **You want the run fixed or continued.** That is `sdlc-graph` itself — `resume`.
- **You want the code reviewed.** That is `code-quality-pipeline`. This reviews the *run*, not the
  diff it produced.
- **There is no run.** `docs/graph-runs/` empty means there is nothing to review; say so and stop.

## Inputs

| Input | Required | Notes |
|---|---|---|
| **run** | no | A `<run-id>` or a path to a `state.json`. With neither, list what is under `docs/graph-runs/` and ask which — **never pick silently**, because reviewing the wrong run produces findings that are true of nothing. |
| **`--repo <path>`** | no | The repository the run drove, for the checks that need git. Defaults to the current directory. **Without a resolvable repo, the git-backed checks report NOT RUN — never a pass.** |
| **`--no-evals`** | no | Report only; write no tests. For a first look. The default is to write them, because a review that produces no eval is the failure mode this skill exists to prevent. |

## Workflow

### 1. Find the run, and say which one

```bash
ls -1 docs/graph-runs/                       # the run directories
ls -1 docs/graph-runs/<run-id>/              # state.json, journals/, and history/ when traced
```

State plainly which run you are reviewing, its `status`, its `node`, and whether it was traced. A
review of a run the user did not mean is worse than none.

### 2. Run the auditor first — do not re-implement it

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/skills/sdlc-graph/evals/audit/audit_run.py \
        docs/graph-runs/<run-id>/state.json --repo .
```

`audit_run.py` already owns the mechanical half — history shape, bounds, ledger well-formedness,
guards quoted verbatim, secrets in observations, journals against the trail, commits against git,
and the trace sequence. **Its findings are the review's first section, quoted as it reported them.**

**Read its NOT RUN lines as findings in their own right.** `NOT RUN` means a check could not
evaluate, which is exactly the state a run can hide in: no `--repo` and the commit check says
nothing; no journals and R13 says nothing. Report each one and say what would make it runnable.

Writing your own version of any of these is the one thing that would make this skill worse than
nothing — a second checker that disagrees with the first is how a run gets two verdicts.

### 3. The narrative pass — what the auditor structurally cannot reach

Load **[`checks/what-to-look-for.md`](checks/what-to-look-for.md)** and work through it. Those are
the classes that need judgement plus the artifacts side by side: prose that contradicts other prose,
a result too clean to be true, a legal transition that was still the wrong one.

**Every finding needs an artifact citation** — a `history[]` index, a journal line number, a
snapshot filename. A finding you cannot point at is a suspicion, and suspicions do not become tests.

### 4. Triage every finding into exactly one of three

| | The graph told it to do that | Fix |
|---|---|---|
| **Spec defect** | The orchestrator followed the contract and the contract was wrong — two files disagreed, a guard was unreachable, a rule was unsatisfiable. | The spec file, plus a check that the contradiction cannot come back. |
| **Run defect** | The contract was right and the run did not follow it. | Nothing to fix in the plugin *unless* nothing would have caught it — which makes it an eval gap too. |
| **Eval gap** | Nothing in `evals/` would have failed on this. | **The point of the whole exercise.** Step 5. |

A finding is often two of these at once. Say so; do not force it into one.

### 5. Close every eval gap, at the tier that catches it

| The defect is… | Write | Where |
|---|---|---|
| two spec files disagreeing | a check **and its mutation control** | `evals/spec/spec_consistency.py` + `evals/spec/spec_controls.py` |
| an illegal or wrong transition | a walk fixture, plus a planted violation in a negative control | `evals/walks/fixtures/` |
| an orchestrator behaving wrong against a correct spec | a scenario, with its `control` block | `evals/runs/scenarios/` |
| something only a real agent would do | a real-agent case | `evals/real/tests/` |
| a hook that fired wrongly, or did not fire | a case in the hook's self-test | `evals/hooks/` |

**Read [`evals/EVAL-INSTRUCTIONS.md`](../sdlc-graph/evals/EVAL-INSTRUCTIONS.md) before writing
any of them.** It carries the fixture format, the negative-control requirement, and the failure mode
that has bitten this suite more than any other: *a check that matches its own explanatory prose and
therefore cannot fail.*

**Every eval you write is proved by breaking it.** Run the suite, then re-run it against the defect
the finding describes and confirm it goes red. An eval added without that step is an assertion that
the defect is now covered, which is exactly the claim under review.

### 6. Write the report

`docs/code-review/graph-run-<run-id>-<DD>-<MM>-<YYYY>-review.md`:

1. **The run** — id, status, node, strategy, traced or not, how many milestones.
2. **The auditor's output**, verbatim, including every NOT RUN.
3. **Findings**, each with its artifact citation and its triage.
4. **Evals written**, each with the command that proves it goes red.
5. **What could not be checked, and why** — the honest section. A review with no such section has
   either checked everything or not noticed what it skipped.

### 7. Verify before you report done

```bash
cd ${CLAUDE_PLUGIN_ROOT}/skills/sdlc-graph && python3 evals/run_all.py
```

Green, with your new checks in it. Then, for each one, the red run that proves it works.

## Output Contract

1. **The report file** — the path above.
2. **New or updated evals**, committed with the report.
3. **A summary**: findings by triage, evals written, and what could not be checked.

## Guardrails

- **Never write to the run.** Not `state.json`, not a journal, not `history/`. The run is evidence;
  a reviewer that edits its evidence has no standing. If the run needs continuing, say so and stop —
  that is `sdlc-graph resume`, and it is the user's call.
- **Never fix the code the run produced.** A run that shipped a bug is a finding about the run's
  gates, not a task for this skill.
- **Never report a finding you cannot cite.** An artifact reference or it does not go in.
- **Never write an eval you have not seen fail.** The suite's own first principle, applied to the
  tool that adds to it.
- **A clean run is a real outcome.** Report zero findings when there are zero. A reviewer that finds
  something in everything is not evidence — it is a mood.
- **Do not re-implement `audit_run.py`.** Run it, quote it, and add only what it cannot reach.

## References

- **[`checks/what-to-look-for.md`](checks/what-to-look-for.md)** — the taxonomy for step 3.
- **`../sdlc-graph/evals/EVAL-INSTRUCTIONS.md`** — what an eval owes, and how to write one.
- **`../sdlc-graph/graph/state.md`** — the schema every artifact is read against.
- **`../sdlc-graph/subagents/workflow-dispatch.md`** — the return gate R0–R15, for judging
  whether a bundle should have been accepted.
