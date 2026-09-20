<!-- copied-from: the standalone `systematic-debugging` skill @ v0.5.0 — a separate, unbundled skill of the author's; this copy is graph-scoped and meant to diverge -->
<!-- trimmed: standalone trigger phrases and the "use when encountering ANY bug / When to Use /
     Don't skip when" framing REMOVED — the graph decides when this node runs. Reaching it means a
     caller already failed and set `debug.return_to`; there is no discretion left to argue with.
     Also removed: the `superpowers:test-driven-development` and
     `superpowers:verification-before-completion` pointers and the `root-cause-tracing.md` /
     `defense-in-depth.md` / `condition-based-waiting.md` file pointers — none of those exist inside
     this plugin, and `DEBUG` declares `requires: —`. The backward-tracing technique is inlined below
     instead of pointed at.
     Kept in full: the Iron Law and all four phases — the root-cause method IS the substance of this
     node and is not summarised anywhere.
     ADDED (graph-only, no source equivalent): the re-entrancy contract — four callers,
     `debug.return_to`, the caller-owned counter, and the caller-owned bounds. -->
<!-- third-party: derived in part from obra/superpowers (MIT, (c) 2025 Jesse Vincent) —
     see /THIRD-PARTY-NOTICES.md at the root of this repository. -->

# Node: systematic-debugging

Serves **one** graph node.

| Graph node | Section | Loaded by |
|---|---|---|
| `DEBUG` | § DEBUG | **milestone agent** when `debug.return_to` is `TEST`, `E2E`, `GATE_A` or `GATE_B` — the nodes a milestone agent owns. When it is `CI` or `CONSOLIDATE` the round-trip is the **orchestrator's**, because those callers are. |

---

## § DEBUG

> **You are a milestone agent.** You do not have the run's state file and **you may never write it**.
> You evaluate no guard and quote no guard text. Report what happened; the orchestrator records it
> and decides where the run goes next.

Random fixes waste time and create new bugs. Quick patches mask underlying issues.

**Core principle: ALWAYS find root cause before attempting fixes. Symptom fixes are failure.**

**Violating the letter of this process is violating the spirit of debugging.**

### The Iron Law

```
NO FIXES WITHOUT ROOT CAUSE INVESTIGATION FIRST
```

If you have not completed Phase 1, you cannot propose a fix.

---

## The re-entrancy contract

**This is the node's whole role in the graph, and it has no equivalent in the source skill.** `DEBUG`
is not a stage in a pipeline — it is a subroutine four different nodes call, and it must come back to
the one that called it.

### Four callers, one entry point

| Caller | Failure that routes here | In edge | Return edge | Bound |
|---|---|---|---|---|
| `TEST` | unit/integration suite red | 10 | **11** | **3** attempts |
| `E2E` | journeys red | 16 | **17** | **3** attempts |
| `GATE_B` | tests red after review fixes | 19 | **20** | **2** attempts |
| `CI` | required checks red | 23 | **24** | watch-ci's time budget + its 2-same-error guard |

### 1. Read `debug.return_to` and return to exactly that node

The caller wrote `debug.return_to` **before** control left it. Read it, and on success hand control to
that node and nothing else. **Without it the graph cannot tell a test failure from a CI failure on
resume** — a resumed run re-reads state, never the conversation, and four inbound edges converge on one
node with no other way to distinguish them.

Guessing the return target silently reroutes the run: returning to `TEST` from a `CI` failure re-runs a
local suite that was already green and skips the pipeline that was actually red.

### 2. Increment **the caller's** counter, never one of your own

Write `attempts["<caller>:<milestone-id>"]` — `attempts["TEST:2"]`, `attempts["CI:3"]`. **There is
deliberately no `debug.attempts` field**, and adding one would be a defect:

> The four callers have four **different** bounds — `TEST` 3, `E2E` 3, `GATE_B` 2, `CI` a time budget
> plus a same-error guard. **One unscoped counter could not honour them.** It would either cut `TEST`
> off at `GATE_B`'s 2, or hand `GATE_B` `TEST`'s 3 — and a run that bounced between callers would
> exhaust a shared counter on failures that belong to different loops entirely.

Counters are keyed **per milestone**, so milestone 3 starts with a fresh budget and never inherits
milestone 2's exhaustion. They are **never reset** — only keyed.

### 3. Clear `debug.return_to` on success

Once the root cause is fixed and control returns, clear the field. A stale `return_to` is a live
mis-route waiting for the next caller.

### 4. The bound is the caller's, and exhaustion is `BLOCKED`

You do not own a budget. When the caller's bound is exhausted — the same error surviving its
`max_attempts` — the run goes **`BLOCKED`**, and `blocked` must name **what was tried**: every
hypothesis formed, every fix attempted, and why each failed. That list is the entire value of the
pause; a `BLOCKED` that says only "tests still red" wastes the human's turn.

> **`GATE_B` reaches its ceiling at 2, before Phase 4's third-fix architecture check.** When a
> `GATE_B` failure burns both attempts, do not silently take a third. Go `BLOCKED` and **raise the
> architectural question in the `blocked` report** — the human decides, which is exactly what Phase 4.5
> asks for anyway.

---

## Phase 1: Root cause investigation

**BEFORE attempting ANY fix.**

1. **Read error messages carefully.** Don't skip past errors or warnings — they often contain the exact
   solution. Read stack traces completely. Note line numbers, file paths, error codes.
2. **Reproduce consistently.** Can you trigger it reliably? What are the exact steps? Does it happen
   every time? **If not reproducible → gather more data, don't guess.**
3. **Check recent changes.** What changed that could cause this? `git diff`, recent commits, new
   dependencies, config changes, environmental differences. In this graph the answer is usually close:
   the milestone's own diff since its branch point.
4. **Gather evidence in multi-component systems.** When the system has multiple components (CI → build
   → signing, API → service → database), **add diagnostic instrumentation before proposing fixes**:

   ```
   For EACH component boundary:
     - Log what data enters the component
     - Log what data exits the component
     - Verify environment/config propagation
     - Check state at each layer

   Run once to gather evidence showing WHERE it breaks
   THEN analyze the evidence to identify the failing component
   THEN investigate that specific component
   ```

   Example, layer by layer:

   ```bash
   # Layer 1: workflow — are the secrets even present?
   echo "IDENTITY: ${IDENTITY:+SET}${IDENTITY:-UNSET}"
   # Layer 2: build script — did they propagate?
   env | grep IDENTITY || echo "IDENTITY not in environment"
   # Layer 3: signing script — is the state what we assume?
   security list-keychains && security find-identity -v
   # Layer 4: the actual operation
   codesign --sign "$IDENTITY" --verbose=4 "$APP"
   ```

   This reveals **which layer fails** (secrets → workflow ✓, workflow → build ✗) instead of which layer
   you guessed.

5. **Trace data flow backward.** When the error is deep in a call stack, trace it to its origin: where
   does the bad value originate? What called this with the bad value? Keep walking up until you find the
   source. **Fix at the source, not at the symptom** — a guard added where the bad value *surfaced*
   leaves it being produced.

## Phase 2: Pattern analysis

**Find the pattern before fixing.**

1. **Find working examples.** Locate similar working code in the same codebase. What works that is
   similar to what's broken?
2. **Compare against references.** If implementing a pattern, read the reference implementation
   **completely** — don't skim, read every line. Understand it fully before applying it.
3. **Identify differences.** What differs between working and broken? List **every** difference,
   however small. Don't assume "that can't matter".
4. **Understand dependencies.** What other components does this need? What settings, config,
   environment? What assumptions does it make?

## Phase 3: Hypothesis and testing

**Scientific method.**

1. **Form a single hypothesis.** State it clearly: *"I think X is the root cause because Y."* Write it
   down. Be specific, not vague.
2. **Test minimally.** Make the **smallest possible** change that tests the hypothesis. One variable at
   a time. Don't fix multiple things at once.
3. **Verify before continuing.** Worked? → Phase 4. Didn't? → form a **new** hypothesis. **Do not stack
   more fixes on top of a failed one.**
4. **When you don't know, say so.** "I don't understand X" — don't pretend. Research more; surface it.

## Phase 4: Implementation

**Fix the root cause, not the symptom.**

1. **Create a failing test case.** The simplest possible reproduction, automated if the project has a
   framework, a one-off script if not. **You must have it before fixing** — it is what proves the fix
   worked, and it is the regression guard that keeps this failure from coming back.
2. **Implement a single fix.** Address the identified root cause. **One change at a time.** No "while
   I'm here" improvements, no bundled refactoring.
3. **Verify the fix.** Does the test pass now? Are any other tests broken? Is the issue actually
   resolved?
4. **If the fix doesn't work: STOP.** Count the attempts. Below the caller's bound → return to Phase 1
   and re-analyze **with the new information**. At the bound → `BLOCKED`. **Never attempt one more fix
   past the bound.**
5. **If 3+ fixes failed: question the architecture.** The pattern that indicates an architectural
   problem: each fix reveals new shared state or coupling somewhere *else*; fixes would require "massive
   refactoring"; each fix creates new symptoms elsewhere. Stop and question fundamentals — is this
   pattern sound, or are we sticking with it through sheer inertia? **This is not a failed hypothesis,
   it is a wrong architecture**, and it is a human decision: raise it in the `blocked` report.

---

## Fix the cause. Never mask it.

**A green obtained by suppressing the failure is a failure of this node, not a pass.** Forbidden without
exception:

- Skipping or deleting a test, `.skip`, `.only` narrowing the suite around the failure
- `continue-on-error`, `|| true`, swallowed exit codes
- Lowered coverage or quality thresholds
- Weakened or removed assertions, loosened matchers, widened tolerances
- Increasing a timeout to hide a race (poll for the **condition** instead)

The graph reads verdicts, not transcripts. **A red routes here and gets fixed; a fake green ships the
defect and destroys the signal every downstream node depends on** — and it is worse still from `DEBUG`
than anywhere else, because masking the failure satisfies the return guard and closes the loop that
existed to catch it.

If a test itself is genuinely wrong, that is a **fix to the test with a stated reason**, not a
disablement — and say so out loud.

## Red flags — STOP and return to Phase 1

If you catch yourself thinking:

- "Quick fix for now, investigate later"
- "Just try changing X and see if it works"
- "Add multiple changes, run the tests"
- "Skip the test, I'll manually verify"
- "It's probably X, let me fix that"
- "I don't fully understand but this might work"
- "The pattern says X but I'll adapt it differently"
- "Here are the main problems:" — followed by fixes, with no investigation
- Proposing solutions before tracing data flow
- **"One more fix attempt"** when you have already tried two
- **Each fix reveals a new problem somewhere else**

**All of these mean: STOP. Return to Phase 1.** At 3+ failed fixes, question the architecture (Phase
4.5).

## Common rationalizations

| Excuse | Reality |
|---|---|
| "The issue is simple, no process needed" | Simple issues have root causes too, and the process is fast for them. |
| "No time for process, the loop is waiting" | Systematic debugging is **faster** than guess-and-check thrashing. |
| "Try this first, then investigate" | The first fix sets the pattern. Do it right from the start. |
| "I'll write the test after confirming the fix" | Untested fixes don't stick. The test first is what proves it. |
| "Multiple fixes at once saves time" | You can't isolate what worked, and it causes new bugs. |
| "The reference is long, I'll adapt the pattern" | Partial understanding guarantees bugs. Read it completely. |
| "I see the problem, let me fix it" | Seeing symptoms ≠ understanding the root cause. |
| "One more attempt" (after 2+) | 3+ failures = an architectural problem. Question the pattern, don't fix again. |

## When investigation reveals "no root cause"

If systematic investigation shows the issue is genuinely environmental, timing-dependent, or external:
document what you investigated, implement appropriate handling (condition-based waiting, a retry with a
real bound, a clear error message), and add logging for future investigation. **But 95% of "no root
cause" cases are incomplete investigation** — and "flaky, re-ran it and it passed" is not a root cause.

---

### Contract

| | |
|---|---|
| **inputs** | the failure (logs, failing command, diff), **`debug.return_to`** |
| **emits** | `attempts["<caller>:<milestone-id>"]` — the **caller's** counter, never its own; **clears `debug.return_to`** on success |
| **exit guard** | root cause fixed → **the node named in `debug.return_to`** (edge 11 / 17 / 20 / 24) |
| **on failure** | same error after the **caller's** `max_attempts` → `BLOCKED` + `blocked` naming every hypothesis and fix tried |
| **max attempts** | **inherited from the calling node** — `TEST` 3 · `E2E` 3 · `GATE_B` 2 · `CI` watch-ci's budget |
| **requires** | — |

> **`debug.return_to` is read, not chosen.** It is the only field that makes the return deterministic.
> If it is absent or does not name one of `TEST` / `E2E` / `GATE_B` / `CI`, that is a zero-matching-guard
> condition: halt with `BLOCKED` and report it — never pick a plausible caller.
