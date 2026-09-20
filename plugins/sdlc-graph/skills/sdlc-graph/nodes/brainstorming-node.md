<!-- copied-from: the standalone `brainstorming` skill @ v0.5.0 — a separate, unbundled skill of the author's; this copy is graph-scoped and meant to diverge -->
<!-- trimmed: THE TERMINAL HAND-OFF REMOVED IN FULL — the source's last step handed the spec path to the
     user to paste into Plan Mode and forbade invoking any planning skill. In the graph, edge 4 carries
     `SPEC` straight to `PLAN`; the graph continues by itself and there is nobody to hand to. Keeping the
     hand-off would park a running graph at its second node.
     Also removed: the HARD-GATE framing about not invoking implementation skills (the graph controls
     sequencing — `IMPLEMENT` is five nodes away and unreachable from here), the
     `disable-model-invocation` / "invoke it explicitly (e.g. /brainstorming)" framing, and the Visual
     Companion section in full — a standalone-only browser tool that is no part of this node's contract.
     Kept intact: the Socratic one-question-at-a-time method, exploring project context first, 2-3
     approaches with trade-offs and a recommendation, dumping the spec to a file EARLY without being
     asked, presenting and revising the file in place, the spec self-review, the user review gate, and
     YAGNI. -->
<!-- third-party: derived in part from obra/superpowers (MIT, (c) 2025 Jesse Vincent) —
     see /THIRD-PARTY-NOTICES.md at the root of this repository. -->

# Node: brainstorming

Serves **one** graph node.

| Graph node | Section |
|---|---|
| `SPEC` | § SPEC |

> **The hand-off is NOT in this file.** The source skill ended by giving the user the spec path and
> telling them to paste it into Plan Mode. That step *is* edge 4 — `SPEC → PLAN` fires on
> `spec file on disk AND user approved`, and `PLAN` reads `spec_path` from state. If you find yourself
> telling the user to take the spec somewhere, stop — the graph is already going there.

> **This node is skipped entirely when a spec was supplied at `INTAKE`.** Edge 3 routes
> `spec_path != null` straight to `PLAN`. Reaching this node means there is no spec yet.

---

## § SPEC

Turn a rough idea into an approved design doc through natural collaborative dialogue. Understand the
project first, ask questions one at a time, then present the design and get approval.

### Anti-pattern: "this is too simple to need a design"

**Every request gets a spec.** A todo list, a single-function utility, a config change — all of them.
"Simple" work is where unexamined assumptions cause the most wasted downstream effort, and here that
waste is amplified: the spec is the input to `PLAN`, which decomposes it into milestones the whole loop
then executes. The spec can be **short** — a few sentences for genuinely simple work — but it must
exist on disk and be approved.

### The order of work

1. **Explore project context** — files, docs, recent commits.
2. **Ask clarifying questions** — one at a time; purpose, constraints, success criteria.
3. **Propose 2–3 approaches** — with trade-offs and your recommendation.
4. **Dump the spec to a file — early, without being asked.**
5. **Present the design from the file** — section by section, revising the file in place.
6. **Spec self-review** — placeholders, consistency, scope, ambiguity.
7. **User reviews the written spec** — the approval gate.

### Understanding the idea

- Check the current project state **first** — files, docs, recent commits — before asking anything.
- **Assess scope before asking detail questions.** If the request describes multiple independent
  subsystems ("a platform with chat, file storage, billing, and analytics"), flag it immediately rather
  than spending questions refining a project that needs decomposing first.
- If it is too large for one spec, help decompose it into sub-projects: what the independent pieces
  are, how they relate, what order they are built in. Then spec **the first sub-project** through the
  normal flow. Each sub-project gets its own spec → plan → implementation cycle — its own graph run.
- **One question per message.** If a topic needs more exploration, break it into several questions.
- **Prefer multiple choice** when possible; open-ended is fine when it isn't.

### Exploring approaches

Propose **2–3 approaches with trade-offs**, presented conversationally. Lead with your recommended
option and explain why. Never present a single option as the only one.

### Dump the spec to a file — early, don't wait to be asked

**The file is the deliverable, not a chat copy.** The moment you have a design worth reviewing, write
it to a Markdown file and keep it updated as the conversation evolves. Present and revise *the file*.

- **Be proactive.** The user should never have to ask "why didn't you save it?" If you have described a
  design, it is already on disk.
- **This is the node's only emitted value.** `SPEC` emits `spec_path`; a design that exists only in the
  transcript emits nothing, fails edge 4's `spec file on disk` clause, and cannot be resumed — a
  resumed run re-reads state, never the conversation.
- **Location:** match the project's own `docs/` convention if it has one (the sibling
  `docs/<subject>/<name>-<DD>-<MM>-<YYYY>-<type>.md` pattern the plan file also uses); otherwise
  default to `docs/superpowers/specs/YYYY-MM-DD-<topic>-design.md`.

### Presenting the design

- Scale each section to its complexity — a few sentences if straightforward, up to 200–300 words if
  nuanced.
- Ask after each section whether it looks right so far, and apply revisions **to the file in place**.
- Cover: architecture, components, data flow, error handling, testing.
- Be ready to go back and clarify when something doesn't make sense.

**Design for isolation and clarity.** Break the system into units that each have one clear purpose,
communicate through well-defined interfaces, and can be understood and tested independently. For each
unit you should be able to answer: what does it do, how do you use it, what does it depend on? If
someone cannot understand a unit without reading its internals, or you cannot change its internals
without breaking consumers, the boundaries need work.

**In existing codebases**, explore the current structure before proposing changes and follow existing
patterns. Where existing code has problems that affect this work — a file grown too large, tangled
responsibilities — include targeted improvements in the design. **Don't propose unrelated
refactoring.**

### Spec self-review

After writing the spec, read it with fresh eyes:

1. **Placeholder scan** — any "TBD", "TODO", incomplete section, or vague requirement? Fix it.
2. **Internal consistency** — do any sections contradict each other? Does the architecture match the
   feature descriptions?
3. **Scope check** — is this focused enough for a **single implementation plan**, or does it need
   decomposition? `PLAN` inherits whatever you leave here.
4. **Ambiguity check** — could any requirement be read two ways? Pick one and make it explicit.

Fix issues inline. No need to re-review — fix and move on.

### User review gate

Ask the user to review the written spec:

> "Spec written to `<path>`. Please review it and let me know if you want any changes."

**Wait for the response.** If they request changes, apply them to the file and re-run the self-review.
Only once they approve does edge 4 fire.

### Key principles

- **One question at a time** — don't overwhelm.
- **Multiple choice preferred** — easier to answer than open-ended.
- **YAGNI ruthlessly** — remove unnecessary features from every design. Each one becomes milestones,
  tests, and gate passes downstream.
- **Explore alternatives** — always 2–3 approaches before settling.
- **Incremental validation** — present, get approval, move on.
- **Be flexible** — go back and clarify when something doesn't make sense.

### Contract

| | |
|---|---|
| **inputs** | user request, `context` |
| **emits** | `spec_path` |
| **exit guard** | spec file on disk **and** user approved → `PLAN` |
| **on failure** | user abandons the dialogue → `BLOCKED` + `blocked` naming what was undecided |
| **max attempts** | unbounded — this is a user-driven dialogue, and revision happens inside the node |
| **requires** | — |
| **interactive** | **yes** — the approval is a human decision and stays in the skill layer |

> **The approval cannot be inferred.** "The user didn't object" is not approval. This is one of only
> three interactive nodes in the graph (`SPEC`, `STRATEGY`, and `PR` when `auto_open_mr == false`);
> self-approving here means the whole run executes a design nobody signed off.

> **`spec_path` must point at the finalized file.** Approval revisions are applied in place, so the
> path emitted is the same one presented — `PLAN` reads that file, not the transcript of it.
