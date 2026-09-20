# Emitting the eval suite — step 9b in full

Load at step 9b, once the graph traces cleanly on paper and you are about to write the files.

Step 9 verifies the graph you are shipping today. **The graph will change**, and a paper trace does
not re-run. This is how you make the traces executable, and how you keep them worth running.

---

Emit `evals/` alongside the four model files, and wire it to run on **every** edit to the graph — a
pre-commit hook, a CI job, or an editor hook, whichever the project already has.

Two suites, both plain scripts with no dependencies:

**`spec_consistency.py` — the files do not contradict each other.** The graph is described across
several files that restate the same facts, so **drift between them is the dominant defect class here,
ahead of any single-file bug**. One check per real defect, each named for the defect it caught:
vocabulary agreement, published counts, cycle counts, every state field read being declared, and the
diagram routing on the same predicate as the table. Name each check for the failure it prevents, not
for the property it asserts — a failing check should read as a diagnosis.

**`graph_walk.py` — a scripted run is legal.** Each fixture is a JSON list of transitions with every
node body mocked: nothing is built, nothing is spawned, no side effect occurs. The walker checks that
each transition is a declared edge, that the guard is quoted **verbatim** from the table, and that the
resulting state satisfies the schema's invariants. Four properties are worth more than the rest:

1. **Guards verbatim, not paraphrased.** A trail that does not match the table cannot be checked
   against it. Paraphrase is itself the finding.
2. **Coverage is a gate, not a report.** The fixture set as a whole must enter **every node** and
   traverse **every edge**. An untraversed edge is an untested guard, and it is precisely the
   configuration variant nobody traced. Fail the suite on a gap; the alternative is a coverage number
   nobody reads.
3. **Stops are derived from the contracts, never listed twice.** Parse the `human` field out of the
   node contracts and check the walk against *that* — a checker with its own hand-written copy of the
   stop list is the drift it exists to catch. Then assert each fixture's **exact ordered stop
   sequence**: it fails both when a stop is missing and when one appears that was not declared.
4. **Conditional stops get a fixture in each direction.** One where the condition holds and the stop
   must fire, one where it does not and the run must continue through. Failure mode 15 lives entirely
   in the second, and the second is the one nobody writes.

**Ship at least one negative control, and treat it as the load-bearing fixture.** A file of deliberate
violations the suite **must** reject, each named. If it ever passes, the checker has stopped checking
and every other green is worthless. Give it a legal step or two as well, so it cannot be satisfied by
a checker that rejects everything. Grow it whenever you add a check: the new check's first fixture is
a planted violation of it.

> **The rule that keeps the suite alive:** a change to the graph is not finished until it adds or
> updates the eval that would have caught its absence. A new edge needs a walk that traverses it — the
> coverage gate enforces that one for you. A new invariant needs a check. A new or changed stop needs
> both, plus a planted violation. Write this rule into the target project's own `CLAUDE.md`, next to
> the command that runs the suite; a convention that lives only in this skill is one the next
> contributor never sees.

---

## Surfaces outside the suite's reach — and the two that get them back

A suite may only read files inside its own unit, so anything that *mirrors* the graph from elsewhere
— the observability surface, a sibling package, a rendered page — sits outside it. That used to be
the end of the sentence, with "check those by hand" after it. Two mechanisms do better.

**1. Check from the mirroring side.** The dependency the layout forbids is the graph reading the
surface. The *reverse* is fine, and it is the direction that matters: the surface holds the copy, so
the surface is what needs to notice the original moved. Put a drift checker in the mirror's own
suite, pointed at the graph's spec files, and have it exit 0 with a message when the graph is not
installed — a standalone install of the surface must not go red. That single checker replaces every
"remember to update the viewer" line in every contributing guide.

**Then route the edit to it.** An editor or commit hook that runs the graph's suite on a graph edit
must also run the *mirror's*, because a guard edited in the graph is exactly what makes the mirror
stale, and the graph's own suite cannot see it. Keep that routing table in one place and give it a
self-test: a unit the hook silently stopped routing to looks identical to a unit with no defects.

**2. Receipts, for the tier a hook cannot run — reported, never gated.** Checks that need a model
(does an orchestrator *obey* the spec under pressure?) cost minutes and money each, so nothing can
run them on every edit. A hook cannot run them; it **can** report whether they ran and whether the
run is still valid. Record, per case: when it was driven, the verdict, and a **content hash of every
input the verdict depended on**. Re-check those hashes when the work leaves the machine — a push,
not a commit, because a gate that taxes every `wip` save gets uninstalled inside a week. Change a
spec file and every case that read it goes **stale by name**, with the command to re-drive it.

**Do not make it a gate.** That was tried and it was the wrong shape. Blocking a push on a tier that
needs money leaves exactly two options at the moment of pushing: pay right then, or reach for the
override — and an override people reach for routinely stops meaning anything, taking the cheap
gate's credibility with it. Worse, it makes the cheap signal hostage to the expensive one: a change
whose deterministic suites are perfectly green, blocked by evidence that went stale three changes
ago in a file nobody touched. **Report it and pass. Let a human decide to spend the minutes.**

**But keep authoring mandatory.** *Write the case with the change; do not drive it.* An authored,
undriven case costs minutes of writing and reads as `NO RECEIPT` — the honest state: it exists, it
is registered, it is addressable by name, and nobody has paid for it yet. **A case nobody wrote can
never be driven at all**, and that is the failure that actually happens, because the moment to think
of the case is the moment you are changing the rule. Separate the two decisions and you get a tier
that grows with the graph instead of ossifying at whatever was affordable the day it was built.

Three more rules make receipts worth having rather than decorative, and each deserves its own control:

- **A receipt is written only by a check that exited 0.** A receipt for a red run is worse than none
  — every later report goes green on it forever.
- **Driving is never automatic**, never unattended without an explicit opt-in, and capped. Something
  that silently spends minutes and money is something people route around.
- **Hand-editing is visible.** Seal each receipt over its own fields. That is tamper-*evident*, not
  tamper-proof — there is no secret to keep in a repo — but the cheap forgery, typing `passed` over
  `never-run`, stops working.

**Name what the receipts do not cover.** Whatever you leave out of the hashed inputs can change
without invalidating anything, and that will be the thing that surprises you. Write the exclusion
down where the mechanism is described, with the reason.

