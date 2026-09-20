# QA plan/report template

One file per milestone per QA pass: `docs/qa/<milestone-slug>-<DD>-<MM>-<YYYY>-qa-plan.md`.

It is written in three passes over the same document:

1. **Before probing (step 3)** — sections 1–4, every row `PLANNED`, header `Status: IN PROGRESS`.
2. **While probing (step 4)** — row statuses + evidence filled in as each group completes; findings appended the moment they're confirmed.
3. **At the end (step 5)** — sections 6–7 finished, header flipped to `Status: COMPLETE` + verdict.

Keep it terse — tables over prose. Every row must be traceable to a real request or click; never pre-fill a status you haven't observed. Redact tokens, passwords, and PII everywhere.

**Statuses:** `PLANNED` · `PASS` · `FAIL` · `BLOCKED` (couldn't run — say why) · `SKIPPED` (deliberately dropped — say why).

---

```markdown
# QA — <Milestone name>

- **Status:** IN PROGRESS | COMPLETE | ABORTED
- **Verdict:** — | PASS | PASS-WITH-ISSUES | BLOCK
- **Date:** DD-MM-YYYY   **Tester:** qa-engineer (independent live pass)
- **Build:** <branch / commit sha>   **Environment:** <local docker-compose | dev> (non-prod confirmed: yes/no)
- **Plan under test:** <path to docs/plans/...-plan.md, milestone N>

## 1. Scope & inputs

- **Under test:** <the milestone's acceptance criteria, in one or two lines>
- **Surfaces:** <endpoints / UI routes covered by this milestone>
- **Base URLs:** API `<url>` · Web `<url>` · API docs `<url>`
- **Identities:** <user A, user B (second tenant/owner), admin — roles only, no credentials>
- **Already covered by committed tests (out of scope):** <the covered-map: which e2e/integration specs assert what>
- **Explicitly out of scope:** load/concurrency (k6), cross-service contracts (Pact), <anything else>
- **Run marker:** `<per-run namespace used for all created data>`

## 2. Environment bring-up

| Step | Command / action | Result |
|---|---|---|
| Stack up | `<docker compose up / documented run command>` | <ok / failure> |
| Health | `GET <health url>` polled until ready | <ok, N ms> |
| Seed | <API-first seed, ids recorded> | <ok> |
| Auth | <login for each identity> | <ok> |
| Observability | <verbose logs, DB access for oracles> | <ok> |

## 3. Green-path plan (must be complete)

| ID | Flow (endpoint/method or UI journey) | Variant (valid class / boundary / transition) | Role | Expected | Oracle | Status | Evidence |
|---|---|---|---|---|---|---|---|
| G-01 | `POST /orders` | valid minimal body | user A | 201 + order persisted | response + DB read-back | PLANNED | |
| G-02 | | | | | | PLANNED | |

## 4. Break-it plan (risk-ordered)

| ID | Target | Attack class | Expected | Risk | Status | Evidence |
|---|---|---|---|---|---|---|
| B-01 | `GET /orders/:id` | BOLA — user B reads A's id | 403/404, no data | High | PLANNED | |
| B-02 | `POST /auth/login` | NoSQL operator injection `{"$ne":null}` | 400, no session | High | PLANNED | |

## 5. Execution log

Append as you go — one line per group, enough to reconstruct the run.

- `HH:MM` — <group: what ran, headline outcome, ids created>

## 6. Findings

Repeat per bug, most severe first. Add each one the moment it's confirmed.

### [S1] <title — what's broken + where + trigger>

- **Severity:** S1 · **Priority (proposed):** P1 · **Oracle violated:** <which>
- **Preconditions:** <seeded state, identity>
- **Steps to reproduce:** 1. … 2. … (literal request or clicks)
- **Expected:** <what should happen and why — spec/AC/standard>
- **Actual:** <status + body + DB state + log line, as observed>
- **Evidence:** request `<METHOD URL + body, redacted>` · response `<status + body>` · db/log `<…>` · screenshot `<ref>`

## 7. Final report

- **Verdict:** <PASS | PASS-WITH-ISSUES | BLOCK> — <one-line reason>
- **Green-path coverage:** <passed>/<total> passed (<failed> failed, <skipped> skipped)
- **Break-it coverage:** <run>/<planned> attacks run
- **Bugs:** S1 <n> · S2 <n> · S3 <n> · S4 <n> — <one line each, most severe first>
- **Risks & uncovered:** <area> — <why not covered> (residual S?)
- **Follow-up tests to commit:** <each confirmed finding → the unit/integration negative case that should hold the line, per `testing-standards`>
- **Teardown:** <created data removed by marker: yes/no, what remains>
- **Bottom line:** <1–2 sentences the orchestrator can act on>
```
