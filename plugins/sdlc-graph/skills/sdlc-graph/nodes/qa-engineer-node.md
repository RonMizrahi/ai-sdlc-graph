<!-- copied-from: the standalone `qa-engineer` skill @ v0.5.0 — a separate, unbundled skill of the author's; this copy is graph-scoped and meant to diverge -->
<!-- trimmed: Inputs REWRITTEN — the source consumed "whatever the orchestrator passed" as prose and
     ran a sufficiency gate over it, then spawned discovery subagents to fill the gaps. Here the
     inputs are fields of `context.qa_env` in the run-state file, read from state and NEVER from
     conversation, so a resumed run still knows how to reach the app. A missing required field is a
     `BLOCK` naming it, not something to discover or invent.
     Also removed: the "Use When" trigger phrases and the "when spawned as a QA subagent" framing —
     the graph decides when this file is read; and the `Do Not Use When` heading, whose substance
     survives below as § Your milestone agent.
     Output REFRAMED — the source "returned the JSON + human summary to the orchestrator". Here the
     node emits `qa.{verdict, qa_plan_path, bugs[]}` into run state and the `VERDICT` node routes on
     it (edges 30/31/32). The human summary is still printed; it is no longer the return value.
     Kept intact: the QA plan as a FILE written before the first probe, the milestone agent beyond the committed
     suite, the covered-map first action, the two obligations in tension, no-test-code, the oracles,
     the verdict rule, and the guardrails. -->

# Node: qa-engineer

Serves **one** graph node.

| Graph node | Section |
|---|---|
| `QA` | § QA |

> **This node authors exactly one file: the QA plan/report `.md`.** No Jest, no supertest, no
> Playwright spec files, ever. If you find yourself writing test code, stop — you are in the wrong
> node (`testing-standards-node.md` owns that, and it already ran).

---

## § QA

Independently QA the **running** application and leave behind two things: a **written QA plan that
becomes the QA report**, and the same verdict in run state for `VERDICT` to route on. You test by
**live-probing** — real HTTP/API calls and a **Playwright browser** against the actual server and
database.

### 1. Inputs come from the state file, never from conversation

Read every input from **`context.qa_env`**. Do not reconstruct it from the conversation, the plan
prose, or your memory of earlier nodes — a run resumed in a fresh session must still know how to
reach the app, and only the state file survives that.

| Field | Use |
|---|---|
| `run_instructions` | How to bring the stack up (docker/dev command, ports). |
| `api_base_url` | Where API probes go. |
| `web_base_url` | Where the browser goes — `null` when `context.has_ui == false`. |
| `api_docs` | Swagger/OpenAPI location, for enumerating the surface. |
| `seed` | How to seed/reset known state. |
| `identities` | **At least two distinct users/roles — required for authorization probing.** |

Plus `plan_path` and `milestones[]` for scope, and the milestone's changed files for risk-ranking.

**If a required field is missing or wrong, emit `qa.verdict = BLOCK` naming the exact field.** Never
invent credentials, endpoints, or run commands. Secrets are never in `qa_env` — it is committed (see
`state.md` § The state file is committed); resolve them from the environment at probe time and never
write them back.

### 2. Your milestone agent — the delta the committed suite structurally cannot reach

The committed tests own the regression/contract layer: per `testing-standards-node.md`, `TEST` covered
the HTTP layer with **supertest** (a happy path plus 2–3 key failures per endpoint, response **shape**
asserted) and `E2E` drove the UI journeys. **That layer is not your job** — re-issuing paths the suite
already asserts adds no information.

You own what the suite cannot reach:

- **Deploy/config/boot reality** — supertest runs *in-process* and can pass while the real server is
  broken. Only a request to the **actually-running app** proves it boots, that `main.ts` wiring
  (global `ValidationPipe`, CORS, route prefix) took effect, and that the real DB/proxy answer.
  **Probe the running app over the network — never `app.getHttpServer()`.**
- **Authorization abuse** — BOLA/IDOR across two accounts (user B against user A's ids, every verb),
  and mass-assignment privilege escalation (`role`/`isAdmin`/`ownerId` in bodies). OWASP's #1 API
  risk; no tool can infer who *should* reach an object.
- **NoSQL operator injection** — `$`-operator type confusion (`{"$ne":null}`, `?f[$ne]=`), beyond the
  string inputs the happy path sends.
- **Serialization leaks** — fields that should be **ABSENT** from responses. The suite asserts the
  fields it expects, not the ones that shouldn't be there.
- **Fuzz-class unknowns and green-path completeness** — inputs no one scripted, plus the valid
  classes, roles and transitions beyond the happy-path minimum.

**First action: build a covered-map.** Read the committed `*.e2e-spec.ts`/integration tests and the
OpenAPI spec, then target **only the uncovered delta**. Risk-gate it: concentrate on
**auth / money / state / untrusted-input** and anything in the milestone's changed files; don't fuzz
plain CRUD uniformly.

Out of scope entirely — hand off, don't fake: load/concurrency (k6) and cross-service contracts
(Pact). A green pass here is not performance or contract assurance.

### 3. Two obligations, held in tension

1. **Cover every green path — systematically, not sampled**, so "did we cover everything?" is a
   countable question.
2. **Break it.** Attack exactly where a constraint *should* exist and probably doesn't.

A green-only pass ships auth bypasses; a break-only pass misses the untested branch that 500s in
production. Do both, track both.

### 4. Write the QA plan to a file — before any probe

**Hard gate: no probe fires until the plan file is on disk.** The QA plan is a document, not a memory.

Enumerate only the delta from the covered-map, consulting **`qa/green-paths.md`**,
**`qa/break-it.md`** and **`qa/edge-cases.md`** so no class is forgotten:

- **Green paths (must be complete):** equivalence partitioning (one rep per valid class — each role,
  each enum, optional present/absent, empty-but-valid, cardinality zero/one/many), valid
  boundary-inside values, decision-table success rows, every legal state transition (0-switch;
  1-switch on critical resources), and a read-back for every write. **Pairwise** for multi-param
  endpoints.
- **Break-it set (risk-ordered):** every error path; boundaries beyond valid; malformed ObjectId;
  NoSQL operator injection; BOLA/IDOR; mass assignment; function-level authz; idempotency/concurrency
  races; illegal state transitions; pagination/sort abuse (`limit=0/-1`, unstable sort); computation
  faults; stored XSS; JWT/session attacks; async side-effect verification.

Record each case as `{id, flow, variant, role, expected, oracle, risk, status}` with
`status: PLANNED`, and risk-rank the break-it rows.

**Then save it** to `docs/qa/<milestone-slug>-<DD>-<MM>-<YYYY>-qa-plan.md` (create `docs/qa/` if
absent) using **`qa/qa-plan-template.md`** — scope + inputs, environment, the green-path table, the
break-it table, an empty findings section, `Status: IN PROGRESS`. Announce the path. If a plan file
from an earlier pass exists (a `VERDICT` reopen), **append a new dated pass** rather than starting
blank.

### 5. Execute — live only, and keep the plan file current as you go

**Bring the full real stack up first** — you cannot probe what isn't running. Use `run_instructions`
(or whatever local-stack / deployment skill this project has installed): every service the feature needs
(API, DB, dependencies, and the web UI) as a user would actually hit it, **not** a partial or
in-process harness. If it cannot be brought up, emit `qa.verdict = BLOCK` with the exact failure
(port in use, missing env, crash log).

Then prepare it for observability: verbose logging on, DB access for oracles, `seed` run, health
endpoint polled until ready (**bounded timeout + backoff, never a blind sleep**), each identity
authenticated. Record the bring-up — commands, health result, seed, build/commit under test — in the
plan file's Environment section. A report whose environment no one can reproduce is not evidence.

Seed state API-first (namespaced, IDs recorded); drop to direct DB writes only to force states the
API refuses. Probe over HTTP capturing method/URL/headers-redacted/body/status/response/latency.
Drive the UI with the **Playwright MCP** (role/name locators; assert rendered success **and** the
network + console channels — right endpoint, exactly one call, correct status, no console errors;
cross-check persistence with an independent GET; if a flag only hides a UI control, replay the API
directly with the un-privileged session).

**Oracles — a 2xx is never proof.** Name the oracle before you look, then apply all of them: correct
status; body matches schema (types/required/enums, no phantom or over-exposed fields); no
500/stack-trace/Mongoose-error leak; **read-after-write on every mutation** (GET back or read the DB);
logs watched as an oracle. Mark a green cell PASS only when the request succeeded **and** read-back
confirmed the state.

**The plan file is the running log, not a write-up you do at the end.** Update each row's `status`
(`PASS`/`FAIL`/`BLOCKED`/`SKIPPED`) and `evidence` after each flow group, and **immediately** when a
probe fails — write the finding into the Findings section the moment you confirm it, so a crash or
lost context never loses a bug. Batch by group, not per request. Anything dropped mid-run gets its
row marked `SKIPPED` **with the reason** — never silently deleted.

### 6. Triage, close the plan file, emit the verdict

Triage on two independent axes: **Severity** (technical, yours — S1 breach/data-loss/crash/auth-or-
tenant-bypass → S4 cosmetic) separate from **Priority** (business, product's). Confirm reproducibility
from the recorded state and attach the violated oracle.

**Verdict rule:**

| Verdict | Condition |
|---|---|
| **BLOCK** | any confirmed **S1**, a core green path broken, or the app unreachable/un-bring-up-able |
| **PASS-WITH-ISSUES** | all green paths pass but **≥1 S2–S4** exists |
| **PASS** | every green path passes and **no S1/S2** |

**Close the plan file:** every row carries a terminal status, header flipped to `Status: COMPLETE` +
the verdict, and a **Final Report** section appended — verdict + one-line reason, coverage counts
(`passed/total`, failed), bugs most-severe first, risks & uncovered with residual severity, and the
follow-ups (which confirmed findings must become committed tests). A verdict with no plan file behind
it is not a QA pass. If the run aborts early, mark it `Status: ABORTED`, keep every row's real status,
and say why.

Then **emit `qa.{verdict, qa_plan_path, bugs[]}`** into run state — `bugs[]` must carry `severity`,
because `VERDICT` tests for S1/S2 to choose its edge. Any un-hit green-path cell is a **named** gap in
the report, never silently omitted. Print the human summary too (verdict, milestone, plan path,
coverage, bugs, risks, bottom line) — but the state fields are what the graph routes on.

### Contract

| | |
|---|---|
| **inputs** | `context.qa_env` (`run_instructions`, `api_base_url`, `web_base_url`, `api_docs`, `seed`, `identities`), `plan_path`, `milestones[]`, changed files |
| **emits** | `qa.{verdict, qa_plan_path, bugs[]}`; the QA plan/report file at `docs/qa/<milestone-slug>-<DD>-<MM>-<YYYY>-qa-plan.md` |
| **exit guard** | verdict returned → `VERDICT` |
| **on failure** | **missing a required `qa_env` field → `status: BLOCKED`** + `blocked` naming the field — does **not** consume `attempts.QA`, never reaches `VERDICT` · app unreachable *despite* valid inputs → `qa.verdict = BLOCK` → `VERDICT` (spends a reopen). See *Missing inputs vs. a broken app* below. |
| **max attempts** | 1 per pass; the reopen bound lives on `VERDICT` |
| **requires** | a runnable app, and **two distinct identities** — without them, BOLA/IDOR coverage is recorded as an uncovered risk, never as passed |

> **Failure here is a verdict, not a halt.** Even a stack that won't boot exits to `VERDICT` with
> `BLOCK`. This node has no path to `BLOCKED` of its own.

### The reopen path

`VERDICT` routes on what you emitted (edges 30/31/32):

- `PASS` → `DONE`.
- `PASS-WITH-ISSUES` with **no S1/S2** → `DONE`; S3/S4 become documented follow-ups.
- `BLOCK` **or any S1/S2 present** → back to **`BRANCH`** as a fix milestone (`is_fix: true`,
  `deps: []`, its own fresh branch off `main_branch`, its own PR), which re-enters the full loop and
  comes back here for a second pass. **Bounded at 2 reopens**, then `BLOCKED` for a human decision.

So severity is load-bearing, not decoration: mis-grading an auth bypass as S3 is what lets it ship.

> **Every confirmed finding must become a committed test at the right level before the run reaches
> `DONE`** — a `testing-standards-node.md` unit or integration negative case, not another live probe.
> **Discovery is your job; regression is the suite's.** List them as follow-ups in the Final Report so
> `CLOSE_OUT`/`DONE` can carry them.

### Guardrails

- **Confirm the target is non-production** before any write or destructive probe. If you cannot
  confirm it, treat every write as dangerous and abort destructive cleanup.
- **Randomly generated IDs for everything you create** (emails, slugs, ObjectIds), namespaced with a
  per-run marker, so probes stay idempotent against a persistent shared DB and never poison real
  users.
- Keep a ledger of created IDs; tear down in reverse-dependency order via the API, scoped by your
  marker; verify removal.
- Any discovery/read helper you spawn is **read-only** — only you write the plan file.
- **Redact secrets from every evidence field.** The plan file never contains credentials, tokens, or
  PII, and neither does anything you write into run state.

### References

Load these from this file's own directory:

- **`qa/qa-plan-template.md`** — the plan/report skeleton (tables, statuses, findings, Final Report).
  Load at step 4, before writing the file.
- **`qa/playbook.md`** — the mental model: five coverage models, oracles, FEW HICCUPPS, risk-based
  prioritisation. Load at the start of step 4.
- **`qa/green-paths.md`** — GREEN-PATH taxonomy (API A1–A12, UI B1–B12) + the completeness rule.
- **`qa/break-it.md`** — BREAK-IT taxonomy (API 1–18, UI 1–11) + the FEW HICCUPPS oracle.
- **`qa/edge-cases.md`** — high-yield edge-value catalog.

Companion node files: **`testing-standards-node.md`** (what `TEST`/`E2E` already covered — read it to
build the covered-map), **`nodes.md`** / **`edges.md`** (the `QA` and `VERDICT` contracts),
**`state.md`** (`context.qa_env`, the `qa` object, and the committed-state-file rule).

---

## Missing inputs vs. a broken app — three different outcomes

Do not collapse these. Only the middle one is a QA verdict.

| Situation | Outcome | Spends a reopen? |
|---|---|---|
| A required `qa_env` field is missing (`run_instructions`, `api_base_url`, `api_docs`, `seed`) | `status: BLOCKED` + `blocked` naming the exact field | **No** — it is an intake gap, resumable the instant the human supplies it |
| The app will not run or is unreachable **despite** valid inputs | `qa.verdict = BLOCK` → `VERDICT` | **Yes** — this is a real defect |
| `qa_env.identities` has fewer than two identities | Proceed **degraded**; record the uncovered BOLA/IDOR surface in `risks_and_uncovered` | No |

Never invent credentials, endpoints or run commands to get past the first row. Blocking on a missing
field costs a human one message; guessing costs a run that proved nothing.
