<!-- copied-from: the standalone `testing-standards` skill @ v0.5.0 — a separate, unbundled skill of the author's; this copy is graph-scoped and meant to diverge -->
<!-- trimmed: the "In plan mode:" framing REMOVED — deciding which milestone gets which test steps is
     the `PLAN` node's job now (`plan-guidelines-node.md` § PLAN requires them as explicit steps).
     Also removed: standalone trigger phrases and the "Use this skill WHENEVER… / load it before
     writing test code" framing — the graph decides when this file is read.
     Kept intact: the three levels and what each owns, the happy-path minimum, asserting the response
     shape at the integration level, and test-data isolation via randomly generated IDs. -->

# Node: testing-standards

Serves **two** graph nodes. Each section below is a separate node contract — read only the one for
the node you are executing.

| Graph node | Section | Loaded by |
|---|---|---|
| `TEST` | § TEST | **milestone agent** |
| `E2E` | § E2E | **milestone agent** |

Tests are written **during** development, not as an afterthought. Writing the test alongside the code
you're verifying is what makes the loop tight: correctness is confirmed before the graph advances,
instead of breakage surfacing three nodes later.

---

## The three levels — and what each one owns

Both nodes below draw from the same split. Put each case at the level that fits — **logic goes to
unit, wiring to integration, user journeys to e2e** — so detail doesn't pile up where tests are slow.

- **Unit** — alongside every service, repository, or utility. **This is where breadth lives:** every
  branch, validation rule, edge case, and input permutation. Go wide — the tests are cheap and fast.
- **Integration** — per controller. Cover the **wiring per endpoint**: one happy path plus its 2–3
  key failures (`401` unauthorized, `400` bad input, `404` not found). **Not input permutations** —
  those belong in the unit tests.
- **E2E** — **critical user journeys, not endpoints or screens**. The money paths a user actually
  completes (log in → do the core thing → see the result). A handful for the whole app, not one per
  feature.

### Minimum coverage

Every endpoint MUST have at least **one happy-path test** — the primary success scenario with valid
input, asserting the expected successful response. This applies **per endpoint** at the unit and
integration levels, and **per critical journey** at the e2e level. Error and edge cases matter, but
they never substitute for a working happy path.

### Test data isolation

Tests MUST use **randomly generated IDs** for all test entities — `crypto.randomUUID()`, a
`Date.now()` suffix, or similar. **Never hardcode IDs.** This keeps tests idempotent: they can run
repeatedly against a real, persistent database without collisions or stale-data conflicts.

### Never fake green

No skipping or deleting tests, no `continue-on-error`, no `|| true`, no `.skip`, no lowered coverage
thresholds, no weakened assertions. **A fake green is worse than a red** — a red routes to `DEBUG`
and gets fixed; a fake green ships the defect and destroys the signal the rest of the graph reads.
Suppressing a failure is a failure of the node, not a pass.

---

## § TEST

> **You are a milestone agent.** You do not have the run's state file and **you may never write it**.
> You evaluate no guard and quote no guard text. Report what happened; the orchestrator records it
> and decides where the run goes next.

Write and run the milestone's **unit** tests alongside each component, and its **integration** tests
per endpoint. Then run the project's unit + integration suites.

**The milestone's test steps are yours, and you commit them here.** `PLAN` writes test steps into
`milestones[].steps` alongside the implementation ones, and the two nodes split that list:
`IMPLEMENT` commits the implementation steps, **you commit every step whose deliverable is a test**
(`nodes.md` § *Which steps `IMPLEMENT` owns*). Neither node owes the other's half — and neither half
goes uncommitted, because each is collected by its own exit guard.

### Running them

Use the project's package manager (`yarn` or `npm`) and **whatever test scripts its `package.json`
actually defines** — e.g. `yarn test:unit` / `npm run test:unit`, then the integration suite.

### Assert the shape, not just the status

At the integration level, assert the response **shape** (a Zod schema), not only the status code.
A `200` with the wrong body is a passing test over a broken contract; shape assertions catch contract
drift cheaply, at the only level that sees the real serialized response.

### Contract

| | |
|---|---|
| **inputs** | `cursor.milestone`, `context.stack` |
| **emits** | `milestones[cursor].node = TEST`, `attempts["TEST:<id>"]`, **`debug.return_to = TEST`** on failure |
| **exit guard** | this node's steps committed **and** unit **and** integration green → `GATE_A` |
| **on failure** | red suite → `DEBUG`, having set `debug.return_to = TEST` |
| **max attempts** | **3**. Spent, and you are the milestone agent: return `outcome: "bound_exhausted"` with `attempt_counts` showing it, and surface the failure and every fix tried. **`BLOCKED` is a status only the orchestrator writes** — you report the budget is gone, it decides what that means. |
| **requires** | the project's test scripts — **absent → `skipped_gates[]`**, and the node may **never** be recorded as passed |

> **`debug.return_to = TEST` must be written before control leaves for `DEBUG`.** It is the only thing
> that tells the graph a test failure from a CI failure on resume; without it `DEBUG` has no
> deterministic way back.

> **A missing test script is a skipped gate, not a pass.** Append `{ node: "TEST", reason, at_milestone }`
> and say so out loud. "There were no tests to run" recorded as green is the exact silent skip the
> ledger exists to catch.

---

## § E2E

> **You are a milestone agent.** You do not have the run's state file and **you may never write it**.
> You evaluate no guard and quote no guard text. Report what happened; the orchestrator records it
> and decides where the run goes next.

Playwright journeys driving the **UI**, covering critical user paths only.

### Before anything else: does this node exist?

`context.has_ui` was resolved **once, at `INTAKE`**, and decides whether this node is part of the run
at all. The two cases below look similar in a transcript and are **completely different things**.

| Condition | What it means | `skipped_gates[]`? |
|---|---|---|
| `has_ui == false` | **The node does not exist for this run.** A structural absence — `GATE_A` goes straight to `GATE_B` (edge 14), and there is no `E2E` edge to take. A backend-only service has **no UI to drive**, and its full request → response flow is already covered by the integration tests. | **NEVER.** Recording it would log a gate that was never in the graph. |
| `has_ui == true`, Playwright **not installed** | **NOT a skipped gate — install it.** See *Playwright is a dependency, not a capability*, below. | **NO.** Installing it is this node's work, not a reason to skip this node. |
| `has_ui == true`, Playwright installed and the app **genuinely cannot be brought up** | **The node exists and could not run.** The journeys this run needed were not executed. | **YES — required.** Append the entry, and the run may not be recorded as e2e-covered. |

**Conflating these is exactly the silent skip the ledger exists to catch.** The first is "there was
nothing to test"; the last is "there was something to test and we couldn't test it." Never write the
first to justify the last, and never let a `has_ui == false` run report a skipped gate it never had.

### Playwright is a dependency, not a capability — install it, never ledger it

> **`pnpm add -D @playwright/test && pnpm exec playwright install chromium` is two commands and it is
> inside every milestone's scope.** A tool you can install is not an absent tool.

`requires` exists for capabilities the run **cannot obtain** — a reviewer plugin that is not on the
machine, a remote that does not exist on a `host: none` repo, an app that will not boot. Playwright is
none of those: it is an npm devDependency and a browser download.

**Observed in a real run:** a `has_ui == true` project ledgered `E2E` at milestone 1 with the reason
*"Playwright is not installed and there is no runnable front-end yet"*. Both halves were true and the
conclusion was still wrong — the front-ends were nine milestones away, so that entry would have
repeated on **every milestone until M12**, and the run would have reached its first UI milestone with
no config, no browser, and a ledger implying e2e was structurally unavailable. The user caught it. The
fix took two commands and produced three green specs against the live stack the same afternoon.

**So, in order:**

1. **Not installed → install it.** Root devDependency, `playwright.config.ts`, browser binary. Do it at
   the first `E2E` entry of the run, not at the first `touches_ui` milestone — the whole point is that
   it is ready before it is needed.
2. **No front-end yet?** `has_ui == true` means one is coming. Write a spec against whatever real HTTP
   surface the milestone *did* produce — a health endpoint, a generated Swagger UI, an admin route —
   driven by a **real browser against the real running stack**. That is a legitimate spec, not a
   placeholder: it proves browser → port → service, which every later journey depends on, and it means
   this node runs from milestone 1. Supersede it later; do not delete it.
3. **Only when the app genuinely will not come up** does this become a `skipped_gates[]` entry.

> **The ledger is append-only, so a premature entry cannot be tidied away.** `state.md`: *"installing
> the missing tool later does not retroactively pass the gate — re-run the node."* Re-running is the
> correct repair, and the entry stays as the record that it was skipped once. That asymmetry is
> deliberate, and it is exactly why writing the entry too readily is expensive: **the cost of
> installing Playwright is two commands; the cost of ledgering it is permanent.**

> If `has_ui == true` and you are tempted to reason your way to "no UI to drive here" — stop. `has_ui`
> is not re-decided per milestone. Getting it wrong at `INTAKE` silently skips e2e for a UI project;
> fix the intake value explicitly rather than routing around it here.

**Once the node exists, `milestones[cursor].touches_ui` decides what this pass owes** — authoring new
specs, or re-running the existing set. See *The mandate*, below. The two questions are separate and
must not be collapsed: `has_ui` is per-run and structural, `touches_ui` is per-milestone and about
work.

### Scope — two sets, and only one of them is a handful

| Set | Size | When it grows |
|---|---|---|
| **Journeys** | A handful for the **whole app** — log in → do the core thing → see the result. | Only when the app gains a genuinely new money path. |
| **Component specs** | One per **milestone that builds UI**. | **Every `touches_ui` milestone. Always.** |

Journeys stay scoped to journeys, not endpoints or screens — reaching for one journey per feature is
how the slowest suite in the project becomes the broadest, and duplicates coverage that already lives
at the unit and integration levels. **The component specs are a different set with a different rule**,
and they are the reason this node stopped being optional.

### The mandate — a milestone that builds UI writes Playwright for it

**`context.has_ui == true` and `milestones[cursor].touches_ui == true` ⟹ this pass authors Playwright
specs for the components the milestone added, before the suite is run.** Not "consider it", not "if it
looks like a money path" — always.

This replaces the old rule, *author a new journey only when this milestone adds a user-facing money
path*. That rule was correct about journeys and wrong as the whole policy: it made authoring a
judgement call, and **the judgement came out "not this one" on every milestone**, so a run could build
six UI milestones and end with the same e2e suite it started with. The observable outcome was always
the same — **the Playwright tests are missing** — and the ledger never recorded it, because nothing had
been skipped, only declined.

**Not authoring them is a `skipped_gates[]` entry**, identical in treatment to Playwright being
absent, because the consequence is identical: the components this milestone shipped were never driven.
The node is then **not** recorded as passed.

```json
{ "node": "E2E", "reason": "touches_ui milestone shipped without component specs: <why>", "at_milestone": 3 }
```

When `touches_ui` is false the mandate does not fire and this node is a **regression re-run** of the
existing set — which is its own value, and is still not optional.

> **`touches_ui` absent?** Only possible on a run resumed from a `schema_version: 1` file. Read it as
> **`true`** and ledger the ambiguity. The default runs the opposite way to `has_ui`'s deliberately:
> guessing wrong there erases a gate silently, guessing wrong here writes a spec nobody needed.

### Run it for real — no mocks

**The spec drives the running frontend against the running backend, both up locally.** A mocked API
turns an e2e test into an expensive unit test of the component's rendering — and it passes for exactly
the wiring bugs this level exists to catch, which is worse than not having the test, because the suite
now reports coverage it does not have.

- **No network mocking**, no stubbed fetch, no fixture server standing in for the API.
- **The database is the one permitted substitution** — disposable, seeded, or in-memory. A fixed
  fixture is what makes the run repeatable, and the DB is not the wiring under test.
- **The app will not come up locally?** That is a `skipped_gates[]` entry. Never a mocked substitute
  quietly recorded as e2e coverage.

Run it via the project's own e2e command.

### Contract

| | |
|---|---|
| **inputs** | `cursor.milestone`, `context.has_ui`, **`milestones[cursor].touches_ui`** |
| **emits** | `milestones[cursor].node = E2E`, `attempts["E2E:<id>"]`, **`debug.return_to = E2E`** on failure, `skipped_gates[]` when a `touches_ui` milestone ships without its component specs |
| **exit guard** | journeys green → `GATE_B` |
| **on failure** | red → `DEBUG`, having set `debug.return_to = E2E` |
| **max attempts** | **3**. Spent, and you are the milestone agent: return `outcome: "bound_exhausted"`. **`BLOCKED` is the orchestrator's to write**, never yours. |
| **requires** | **A locally runnable app + API.** Playwright is deliberately NOT listed: it is an npm devDependency plus a browser download, so it is **work to do, not a gate to skip** — install it. The ledgerable absence is an app that genuinely cannot be brought up while `has_ui == true`; then the run may not be recorded as e2e-covered. See *Playwright is a dependency, not a capability*, above. |

> **Counters are keyed per milestone** (`attempts["E2E:2"]`). A milestone that burned all three
> attempts does not poison the next one, and resume never rewinds the count.
