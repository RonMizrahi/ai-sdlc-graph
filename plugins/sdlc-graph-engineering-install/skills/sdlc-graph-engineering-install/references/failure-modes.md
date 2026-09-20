# How these graphs break

Read this at step 4, **before** you believe your guards are total. Every mode below has a published
name; using the name makes the defect searchable instead of folkloric.

Ordered by how often they actually occur, not by how interesting they are.

---

## 1. Zero matching guards — the dominant failure

**Standard name:** violation of **option to complete** — van der Aalst's workflow-net *soundness*.
From every reachable state, the end must remain reachable. A guard gap is a state from which it isn't.

**What it looks like:** a node returns a legal result, no guard covers it, and the run halts. Not on
an error — on a perfectly ordinary outcome nobody enumerated.

**Why it survives review:** guard sets are written exhaustive over the *happy predicates*, not over
their **product**. A result with three independent properties has eight combinations; three obvious
guards cover perhaps four. Reading the spec top-to-bottom never reveals it, because each guard looks
correct in isolation.

**The concrete trap:** a "clean" flag that means two things at once. If one field mixes *safe to
proceed* with *nothing was skipped*, routing on it deadlocks the moment a tool is merely absent —
there is no finding to retry for, and it is not clean either. **Route on one predicate; report on the
other.**

**The second concrete trap — a tri-state field read with a binary operator.** A nullable flag has
three values: true, false, and *not yet decided*. Write the pair of guards as `X` and `NOT X` and the
third value silently joins one of the branches — in most languages `NOT null` is **true**, so
"undecided" routes exactly where "false" does.

This one is worse than a zero-guard halt, because it does **not** halt. It picks a branch, confidently,
and if that branch is the one that *skips* a step, the step disappears for the whole run with nothing
recorded. A real graph lost its entire end-to-end testing stage this way: `has_ui` was `null` on a
greenfield run, `NOT has_ui` evaluated true, and the run took the no-UI edge past the e2e node without
a single ledger entry.

**The rule: enumerate the values that mean *route*.** `== true` and `== false`, never `X` / `NOT X`.
Everything outside the enumeration is a halt or a ledger entry — never a default branch. The same
applies to any field that can be absent, unknown, pending or "not applicable", which in practice is
most of them.

**How to catch it:** write the truth table per node. `exits × guards`, every row matching exactly one —
and give every nullable field its own row, not just its two interesting values.

---

## 2. Unearned pass

**Standard names:** **sequence manipulation** (Reward Hacking Benchmark) — "exploiting gaps in
stepwise enforcement by fabricating intermediate artifacts or skipping required upstream work".
Also **MAST FM-3.2**, *no or incomplete verification*.

**What it looks like:** a step exits green while its own artifacts say it never ran. Zero items
processed and a success result. A verifier that structurally *cannot* do what it was told to do.

**Three real shapes, all seen in practice:**

- **A deny-list where an allow-list was needed.** `status !== 'fail'` treats `'absent'`, `'unknown'`
  and `'skipped'` as success. Always ask "which values mean pass?" and enumerate *those*.
- **A worker without the capability it was told to use.** An agent given read-only tools and
  instructed to "apply the fixes" cannot, and will report as though it did.
- **An early return that skips the work and keeps the success shape.** Empty input, nothing to do,
  returns `clean`. **Nothing-processed is never a pass.**

**How to catch it:** every exit path returns the *same* shape through one builder, so no early return
can omit the fields the caller routes on. And cross-check claims against the world — if a step says
it changed files, diff them.

---

## 3. Unbounded or oscillating cycles

**Standard name:** livelock. The **ping-pong** shape `A→B→A→B` is the canonical agent loop.

Frameworks all converge on the same answer: a hard ceiling. LangGraph's `recursion_limit` (default
25) raising `GraphRecursionError`; CrewAI's `max_iter`; AutoGen's `max_turns`. Their docs also warn
that raising the limit just buys more calls when the agent is stuck.

**The subtler failure is not a missing bound but an unenforced one** — a counter that exists and is
never incremented. The loop looks bounded in the spec and runs forever in practice.

**How to catch it:** the transition count for a node must equal its counter plus one. If they drift,
the bound is decorative. Add a **global step ceiling** too: every cycle can be individually within
bounds while the run as a whole never converges.

---

## 4. The re-execution hazard

**What it is:** on resume, a node generally re-runs **from the start** — so everything it did before
pausing happens **twice**. LangGraph documents this explicitly for `interrupt()`.

**What it costs:** a node that performs an irreversible act and *then* pauses will, on resume, perform
it again. A second pull request. A second email. A second charge.

**The rule:** a node that asks before acting must **ask first and act once**. On resume, derive what
already happened **from the world** — query the API, check the filesystem — never from what state
said you were about to do.

---

## 5. Silent structural skip

**What it looks like:** a step that legitimately does not apply in some configurations, and a
condition that decides it, set wrongly or set late. The step vanishes and nothing records it, because
"not applicable" was declared not to be a skip.

**The distinction that must be explicit:**

- **The step does not apply** (there is nothing to do) → structural absence, correctly not a ledger
  entry.
- **The step applies and could not run** (its tool is missing) → **that is a skipped gate**, and must
  be recorded.

Conflating them is how coverage silently disappears. State both cases in the node contract.

---

## 6. Context loss

**Standard names:** **MAST FM-1.4** *loss of conversation history*, **FM-2.1** *conversation reset*.

**What it looks like:** a decision that exists only in the transcript. The run continues, the decision
is gone, and a resumed run either re-asks something already settled or proceeds without it.

**How to catch it:** every decision a later node reads must be a named field in run state. If a node's
`inputs` mention something the schema does not define, that is the defect.

---

## 7. Control-flow hijack via input text

**Standard name:** **OWASP ASI01 Agent Goal Hijack** — distinct from transient prompt injection in
that it redirects *goals and multi-step planning*, not a single reply.

**What it looks like:** free text from the process definition — an item name, a step description —
interpolated into a prompt for a worker with real tool access.

**How to defend:** fence untrusted text in a labelled data block, state the hard constraints **both
before and after** it so injected text cannot be the last word, and instruct the worker to **stop and
report** rather than obey anything instruction-shaped inside it.

---

## 8. Stall

**Standard names:** **zombie task** (Airflow) — killed so suddenly it never reported failure. Also
Temporal's schedule-to-start latency, and Step Functions' rule that a task without a timeout is
"stuck waiting for a response that will never come".

**How to catch it:** running status, no new transition, past a threshold. If the runtime has no clock,
use file modification time.

---

## 9. The gate that runs after the point of no return

**What it is:** a verification step placed *downstream* of the node that makes the work irreversible.
The graph still runs every gate, in order, and still reports honestly — and the gate is worthless,
because by the time it can object, the thing it would have objected to has already shipped.

**How it happens:** the irreversible node feels like the *end* of the build, so everything
"administrative" — the final report, the acceptance pass, the documentation update — gets appended
after it. Each addition is individually reasonable. The ordering is never revisited.

**What it costs, concretely:** a rejecting verdict is no longer a gate, it is an incident. And every
artifact those later nodes produce — reports, documentation, the regression test written for each
confirmed finding — is committed **outside whatever review the irreversible step was gated by**.

**The rule:** find the node that is hard to reverse — a merge, a deploy, a publish, an outbound
message, a payment — and **make it the last node that can be reached**. Every step whose output could
change the decision to take it must be upstream of it. State it as an invariant the monitor checks:
*no entry into the irreversible node before the verification node has been entered.*

**Watch for the ordering exception that isn't one.** "This configuration produces nothing to verify"
is legitimate, but it belongs on an explicit edge that says so out loud, not on the absence of one.

---

## 10. A node entered twice with nothing to tell the passes apart

**What it is:** the same node legitimately runs at two different points — a per-item pass and a
whole-set pass, a per-request check and a batch check. The guards are written as if it runs once, so
on the second entry they either match the first pass's exit (and loop) or match nothing at all.

**What it costs:** either an infinite loop, or a zero-guard halt — and if the two passes share one
attempts key, the first pass can exhaust the budget the second one needs.

**The rule, two parts:**

1. **Put a discriminator in run state**, and test it in the guards. A field that is null before the
   second phase begins and non-null after is enough, and it doubles as the phase marker on resume.
2. **Key the counters separately** — `<NODE>:<item>` for the per-item pass, `<NODE>:<phase>` for the
   other. One node, one contract, two budgets.

**Do not solve this by cloning the node.** Two nodes with the same contract drift, and the second copy
is the one nobody updates.

---

## 11. Renumbering edges a live run already recorded

**What it is:** the graph changes, some edges become unreachable, and the tidy instinct is to close
the gaps in the numbering — or reuse the freed numbers for new edges.

**What it costs:** every finished run's history refers to edge ids. Reuse one and old records silently
describe a transition that never happened; renumber and they describe a different one. The audit trail
you built the graph to produce becomes untrustworthy retroactively, with no error to notice.

**The rule:** **retire ids, never reuse them.** Leave the gaps, list the retired ids with one line on
why they became unreachable, and give new edges new numbers. Numbering is an identifier scheme, not an
ordered list — gaps cost nothing and reuse costs the record.

---

## 12. A schema change that orphans every in-flight run

**What it is:** the graph evolves — edges retired, a field's semantics inverted, new state added —
and the run-state schema has no version marker. A run started under the old graph resumes under the
new one, and every recorded value is silently reinterpreted by rules it was never written against.

**Why it is the most commonly missing item:** nothing fails at the moment of the change. The failure
arrives later, on the first resume of an older run, presenting as inexplicable routing — and by then
the change that caused it looks unrelated.

**The rule:** one integer, `schema_version`, written once at run creation and checked **first** on
resume. A mismatch is a hard stop naming both versions — never a silent reinterpretation. The mature
form is Temporal's workflow versioning/patching; the cheap form is the integer and the refusal.

---

## 13. The observability surface that lies about the graph

**What it is:** a viewer, dashboard or report that carries its own copy of the graph — the node list,
the guard conditions, the bounds — so it can show what will happen next. The graph then changes, and
the surface keeps rendering the old shape with total confidence.

**Why it is worse than having no viewer:** a missing dashboard is an inconvenience someone routes
around. A confident, wrong one is consulted *instead of* the record, and it fails in the direction of
reassurance — showing a next step that no longer exists, or omitting a node that now runs. The person
watching has no way to tell.

**Why the duplication is still worth it:** a surface that only echoes the state file can show where a
run *is*; one that knows the guards can show what can fire *next*, and why the other branches cannot.
That is most of its value. The answer is not to forbid the copy — it is to date it.

**The rules:**

1. **Generate the copied part; do not maintain it.** Fence it — `/*__GRAPH_BEGIN__*/ …
   /*__GRAPH_END__*/` — keep it **data only, no functions** so it can be parsed, and give it exactly
   one writer that regenerates it from the spec. Dating the copy was the old advice and it is not
   enough: a hand-kept copy pinned to a version still drifts *inside* that version.
2. **Check it from the mirroring side, and put that checker where it can reach both.** The graph
   usually cannot read the surface — a plugin may not read above its own root — but the surface
   reading the graph is legal and sufficient. Compare ids, endpoints, the node set, the bounds, and
   whether each guard still tests the same fields.
3. **The writer is not the checker.** A checker that can rewrite the thing it checks always agrees
   with itself. Keep the generator out of the check runner.
4. **Whatever the surface OWNS lives outside the fence — and therefore outside the checker.** This
   is the trap the fence creates. Display-name maps, guard predicates, layout: anything not derived
   from the spec must sit outside the markers or the generator deletes it, and outside the markers
   nothing is checking it. Observed: a viewer's guard-predicate map still keyed on the edge ids of
   the graph it was **forked** from — seven keys naming edges that no longer existed and evaluating
   for nothing, and two dimming the exact **inverse** of their own guard — inside a file whose
   generated half had been checked green all along. **Every fenced surface needs a second check for
   the unfenced half**, and it is easy: read the guard out of the generated block and assert the
   hand-written predicate agrees with it.
5. **Pin the schema version too, and make a mismatch visible on the page** — not in a log nobody
   reads. Generation handles same-version drift; the version pin handles the run written by a
   different graph entirely.
6. **One renderer, one copy.** Snapshots, live views and reports all generate from the same source
   file. The moment a second copy exists to be "adjusted", the two begin diverging.
7. **A guard fixed in the graph is not fixed until it is fixed in the surface.** The copy reproduces
   the *logic*, so it reproduces the *bugs* — and the surface states its answer with more confidence
   than the graph ever does, because it renders a single next-step rather than evaluating a table.
   Observed: a graph corrected a tri-state guard from `NOT X` to `== false` (mode 1, second trap), and
   the viewer's mirrored predicate — `x !== true` — kept the original defect, so it went on displaying
   the wrong next node for exactly the runs the fix was written for. **Make "does the surface mirror
   this?" a step in the guard change itself, not a follow-up.**

**Where the counts live is the same problem, one size down.** Node totals, edge totals and cycle
counts get published in READMEs, diagrams, title blocks and page footers, and none of them are
generated. One real graph carried *three different counts in a single HTML file* — title block, body
heading and footer — each correct on the day it was written. **Grep every published number after every
structural change**; they are the first thing a reader uses to decide whether the documentation is
current, and the cheapest thing to get wrong.

---

## 14. Two orchestrators driving the same work

**What it is:** the graph copied a source that contained its own loop, trimmed that loop out — and
then, mid-run, something loads the **original** anyway. A trigger phrase matches. A project rule says
"always load X before doing Y". The model recognizes the task and reaches for the familiar skill.

**What it costs:** the loop the graph drives and the loop the source describes both run. Two branches
created for one unit of work, two pull requests, two attempts at the same side effect — each one
individually justified by whichever instructions were in context at that moment. It looks like an
agent being thorough; it is the same work happening twice.

**Why the obvious defenses fail:** trimming the loop out of the copy does nothing, because the
*original still has it*. And a general instruction like "avoid loading overlapping skills" is
unenforceable — nobody can evaluate "overlapping" mid-run.

**The rules:**

1. **Name the twins explicitly** — an enumerated list, in the project's own instructions. Enumerated
   is enforceable; a category is not.
2. **Suspend the ordinary triggers for the duration of a run.** State that while the graph is running
   it is *the only authority on which procedure loads when* — including over rules that would
   otherwise fire.
3. **Say what the graph loads instead**, in the same breath. A prohibition without a replacement gets
   ignored the moment someone needs the procedure.
4. **Make the run's active state detectable** — a status field in the run-state file — so "is a run
   active?" is a question with an answer on disk, not a judgement call.

---

## 15. The stop that fires where the human said *continue*

**Standard name:** the inverse of MAST's *premature termination* — same cost, opposite trigger.

**What it looks like:** a node pauses and asks. Nothing is wrong. The pause is even at a node that
genuinely declares a stop — but the stop was **conditional**, and its condition was false. The
condition was usually settled deliberately, once, early, exactly so the run would not stop here.

**Why it survives review:** it reads as diligence. An invented stop is obviously wrong; a *conditional
stop taken unconditionally* looks like care. Nobody files a bug because the agent asked. The cost is
identical to the invented stop, and it is the cost the whole design was minimising: **a 20-node run
that asks at each node is 20 interruptions and the user stops reading them.** Worse, once the pattern
is established the genuinely required stops arrive in the same undifferentiated stream.

**Where it hides:** conditional stops are typically written as a *sentence* — "pauses for confirmation
only when auto-open is off", "asks once the retry budget is spent". A sentence is not a predicate.
Nothing evaluates it, so nothing catches the pass where it was ignored.

**The fix:** make the condition a value the run can read, and test it **in both directions**. One
fixture where it fires, one where it must not — and a checker that fails the second if a stop appears.
The negative case is the one nobody writes, and it is the one that regresses.

**The signal:** a `paused` object naming a node whose stop condition, read from the same state file,
is false.

---

## 16. The obligation whose trigger is a judgement call

**What it looks like:** the process says a thing must be produced *when it is warranted* — write an
end-to-end test **when the change adds a user-facing path**, add a migration **when the schema
meaningfully changes**, update the docs **when the behaviour is user-visible**. Every run evaluates
the trigger honestly, and every run concludes: not this one. Six milestones later the artifact has
never once been produced.

**Why it survives review:** every individual decision was defensible, and there is **no ledger entry**
to find. Nothing was skipped — the obligation simply never triggered. The absence looks identical to
the absence on a run that legitimately owed nothing, which is exactly why it can persist for the life
of a project without anyone naming it.

**Why it is worse than a missing gate:** a gate that cannot run gets recorded and the run is reported
as degraded. This one reports clean. The output of the process claims coverage it does not have, and
that claim is what the next decision is made on.

**The fix, in three parts:**

1. **Make the trigger a field, not a judgement.** Something an earlier node *writes* — set at the
   point where the information actually exists, seeded on every item so it is never absent.
2. **Make the absence ledgerable.** Trigger true and artifact absent ⟹ a ledger entry and the step is
   not recorded as passed. That converts a silence into a fact.
3. **Check it mechanically.** A rule enforced by prose alone has the same reliability as the judgement
   it replaced.

**The signal:** an artifact class the process mandates that appears in **zero** completed runs. Count
it across runs rather than within one — within one run, "not this time" is always plausible.

---

## What NOT to monitor

A checker that fires constantly gets ignored, which is worse than no checker.

- **A non-empty ledger is not a defect.** It is the design working. Only *passed while skipped* is.
- **A deliberate stop is not a failure.** Keep it a distinct status so nobody hunts for a problem that
  did not happen.
- **Reaching the end with a non-empty ledger is not a failure either** — it is an expected, documented
  outcome. Lead the report with it; do not raise an alarm.
- **State disagreeing with the world is not corruption.** Resume *requires* re-deriving from the
  world; partial work from a run that died mid-node is normal.
- **Do not judge quality.** Whether the work was any *good* is a human question. Surface it; never
  rule on it.

---

## Sources

- van der Aalst, *Verification of Workflow Nets* — soundness: option to complete, proper completion,
  no dead transitions.
- Cemri et al., *Why Do Multi-Agent LLM Systems Fail?* (**MAST**), arXiv 2503.13657 — 14 failure modes
  in 3 categories, NeurIPS 2025.
- *Reward Hacking Benchmark* — six exploit categories including sequence manipulation and tampering.
- LangGraph docs — `recursion_limit`, `interrupt` / `Command(resume=…)`, and the re-execution note.
- OWASP Top 10 for Agentic Applications — ASI01 goal hijack.
- Airflow (zombie tasks), Temporal (worker health), AWS Step Functions (task timeouts) — the
  practitioner equivalents of stall detection.
