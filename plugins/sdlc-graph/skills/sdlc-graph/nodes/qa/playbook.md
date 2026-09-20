# How to think like the ultimate QA engineer

You test one milestone of a running app by **live-probing** it — real HTTP calls and a Playwright browser against the actual server and database. You write no test code. Your test plan is a **document** (`docs/qa/…-qa-plan.md`): enumerated and saved before the first probe, ticked off row by row as you execute, closed with a final report. Everything in it is an observed behavior judged against an oracle — never an assumption.

Hold two obligations in tension at all times:

1. **Cover every green path — systematically, not sampled.** Prove every valid flow works, by construction, so "did we test everything?" is a countable question, not a vibe.
2. **Actively try to break it.** Attack exactly where a constraint *should* exist and probably doesn't. Developers constrain the happy path and forget the boundaries — that gap is where you live.

Neither obligation is optional. A green-only pass ships auth bypasses. A break-only pass misses the untested legacy branch that 500s in production. Do both, and track both.

---

## Part 1 — The core mental model

Every bug is a developer's failure to constrain one of four things: **inputs, outputs, stored data, or computations**. The happy path is constrained; the edges are not. So:

- To **cover**, build an enumerable model of the app *before* probing, then tick boxes.
- To **break**, attack each constraint on the running system where it's likely missing.
- To **judge**, pick an explicit oracle for every single probe — because on a live app there is usually no pre-written expected result.

Work the loop per surface: **model → cover green → break → judge → record**.

---

## Part 2 — Enumerate green paths exhaustively (cover, don't sample)

Model the app along independent axes, then cover the cross-product. Coverage = items exercised / items identified; target 100% of valid items.

### Build the inventory from the app itself (never guess)

- **API:** fetch the NestJS OpenAPI/Swagger JSON (`/api-json`, `/api/docs-json`, `/swagger-json`). Every `path × method` is a row; every DTO field with its `class-validator` rules is an input spec; every documented status is a claim.
- **Frontend:** drive every route/screen in Playwright; `browser_snapshot` (accessibility tree) enumerates every interactive control; capture the Network channel to find the real requests the UI sends and the fields it reads — that union is the true contract.
- **Cross-check:** UI-used endpoints missing from Swagger, and documented endpoints the UI never calls, are both findings.

### The five models to build

1. **Route × Method × Role matrix** — rows = routes, columns = roles (anonymous, user A, a *second* user B, admin, per-tenant), cells = expected result. Every "should-succeed" cell is a green path; every "should-fail" cell is a break candidate.
2. **Equivalence-class table per input** — partition every field/param/header into valid classes and pick one representative each. A "green path" is not one happy value; it is one rep from *each* valid class. Structural valid classes every field has: empty-but-valid, single char, max-length, unicode/emoji, whitespace, optional-present vs optional-absent; arrays: `[]`, one, many, max cardinality; enums: each allowed value.
3. **State machine per stateful resource** — states + legal transitions (order: cart→placed→paid→shipped→delivered→cancelled/refunded). Every legal transition is a green path (0-switch coverage). Escalate critical resources to 1-switch (every consecutive pair, **without resetting between steps** — reuse the entity so accumulated state is exercised).
4. **Decision table for multi-condition rules** — enumerate every combination of conditions (role × ownership × resource-state; coupon × tier × cart-total). Each row with a distinct valid outcome is a green path. This catches the valid combinations teams forget.
5. **Requirements traceability** — every atomic claim (story/AC, Swagger description, DTO validator, help text) maps to at least one live probe. Empty cells are untested requirements.

### Tame the combinatorial explosion

When multiple valid inputs interact, don't run the full Cartesian product — use **pairwise (all-pairs)** so every pair of values co-occurs at least once (~10 params: 1024 → ~15 probes). Add known interacting triples by hand (currency × tax-region × plan). Keep single-field equivalence coverage as the floor.

### Verify, don't assume — a 2xx is not proof

For every green step, apply **multiple oracles** (Part 4): correct status, response body matches the DTO/Swagger schema, and **read-after-write** — GET the resource back (or read Mongo directly) and confirm it actually persisted with the right values. A silent write failure hides behind a 200. For UI flows, assert the DOM success state *and* confirm on the Network channel that exactly one call fired to the right endpoint with the right payload and got a 2xx.

### Definition of green-path complete

Every `route × method × role` should-succeed cell returns its documented 2xx with a verified side effect; every input field has ≥1 valid-class rep and both valid boundary values passing; every user role has done every action it's permitted; every legal state transition has been traversed once; every decision-table success row has run; every requirement row has a passing probe. Any un-ticked cell is a *named, specific* gap ("`PATCH /orders/:id` never covered for role=manager"), not "looks fine."

---

## Part 3 — Break it: the attack checklist

Attack each of the four constraint families. This is your usable mental checklist; run it against every endpoint and form after the green path passes.

### Input constraints

- **Force every error message.** For each field, craft one input that violates each rule (omit required, wrong type, out-of-enum, malformed email/date/ObjectId, duplicate unique key). Highest-yield attack — error paths are the least-tested code. Stack multiple violations to find handlers that only cover the first. A clean 4xx is correct; a 500 with a stack trace / Mongoose CastError is a leak + availability defect.
- **Force defaults.** Absent key vs `null` vs `""` vs `"   "` vs `0` each take different code paths. Does `role` default to something privileged? Does `limit=` (empty → `Number('')=0` → Mongoose `.limit(0)` = *no limit*) dump the whole collection?
- **Character sets & types.** Unicode, emoji (👨‍👩‍👧 ZWJ = 7 code points), RTL override (‮), null byte (`%00`), control chars, 4-byte UTF-8, NFC-vs-NFD, numbers-as-strings, `1e309`→Infinity. Watch storage, retrieval, length checks (bytes vs code units vs graphemes), and rendering (stored XSS via `dangerouslySetInnerHTML`).
- **Overflow / unbounded.** 10⁴–10⁷-char strings, 100k-element arrays, 1000-level nested JSON, oversized uploads, no `@MaxLength`. Look for a missing size cap → memory/DoS, or a clean 413.
- **Boundary Value Analysis.** For every numeric/length/date/quantity bound, send min−1, min, min+1, max−1, max, max+1, plus 0, −1, MAX_SAFE_INTEGER. Highest defect density per test — off-by-one and `<=` vs `<` live here.
- **Interacting inputs.** Fields individually valid but jointly invalid: `checkIn > checkOut`, `discount > price`, `quantity > stock`, `status='shipped'` with no address.

### The Mongoose/NestJS signature attacks

- **NoSQL operator injection.** Replace a scalar with an operator object anywhere input reaches a query. JSON body: `{"password":{"$ne":null}}`. Query string: `?password[$ne]=x` (Express `qs` parses brackets into an object). Auth bypass: `{"email":{"$gt":""},"password":{"$ne":"x"}}` → logs in as the first user. Blind extraction via `$regex`; timing via `$where`. Root cause: DTO accepted an object where a string was expected → `ValidationPipe` not global or no `whitelist`.
- **BOLA / IDOR.** The #1 API risk. Create users A and B. As A, capture a resource id; replay authenticated as B (and anonymously) against A's id, for **every verb** (read may be guarded while write/delete isn't). Any 200 with A's data, or a successful mutation, = broken object-level authorization (`findById(id)` with no `ownerId` filter). Enumerate sequential/ObjectId-prefixed ids.
- **Mass assignment / BOPLA.** Add fields the client shouldn't control to create/update bodies: `{"role":"admin","isVerified":true,"balance":999999,"ownerId":"<victim>"}`. GET back and check if they stuck. Works when `ValidationPipe` lacks `whitelist:true`/`forbidNonWhitelisted:true` and the service does `findByIdAndUpdate(id, dto)`. Also check the inverse (over-broad responses leaking `passwordHash`, tokens, other tenants' PII).
- **CastError on `:id` routes.** `GET /users/abc` (non-ObjectId) should be a clean 400/404, not a 500 stack trace. Near-universal bug found in seconds.

### Concurrency, idempotency & interruption

- **Replay & race.** Fire the identical POST N times sequentially and M times concurrently (`xargs -P`, `Promise.all`, double-click before the spinner resolves). Check-then-act windows overdraw balances, double-charge, reuse single-use coupons, and create duplicate "unique" records when the app does find-then-insert with no DB unique index. Test idempotency-key replay: same key twice → one effect; same key, different body → rejected.
- **Interrupt mid-operation.** Abort the socket / navigate away / make step 2 of a non-transactional multi-write fail. Mongo has no cross-document ACID unless transactions are used → order created but inventory not decremented, an impossible state no green-path test finds.
- **State-machine illegal transitions.** Every *empty cell* of the state table is an attack: pay an already-paid order, ship an unpaid one, refund twice, act on a deleted resource. Expect a clean 409/422 and unchanged DB state; a 200 that mutates status is the bug.

### Output, computation & storage constraints

- **Computation limits.** `quantity=1e309`→Infinity→`{"total":null}` in JSON→UI renders `NaN`; self-parenting category → infinite recursion → `RangeError: Maximum call stack size exceeded`; divide-by-zero; negative totals.
- **Storage/memory exhaustion.** Unpaginated `.find()` with no `.lean()` over a huge collection → heap OOM. `limit=1000000`, `limit=-1` (Mongoose "no limit"). Missing max-cap on any list endpoint = OWASP API4 DoS.
- **Output inconsistency.** Client-computed totals vs API aggregates after a concurrent edit; list-count vs detail-count disagreement; stale caches after a background update.

### Cross-cutting attacks (run where relevant)

- **Session/token lifecycle:** replay the token *after logout* (stateless JWT often still valid); replay after role revoked/account disabled; refresh-token rotation & reuse detection; `alg=none`/RS256→HS256 confusion; expired/tampered tokens; cookie flags (HttpOnly/Secure/SameSite); CSRF on cookie-auth mutations.
- **Caching:** private/authenticated data served from a shared/CDN cache (two-identity leak test); stale-read-after-write; `Vary` correctness; cache poisoning via unkeyed headers (`X-Forwarded-Host`); cache deception via path confusion (`/my-account/x.css`).
- **Async side effects:** never assert immediately and never sleep — **poll a terminal state with a bounded timeout** (AAAA: Arrange, Act, Await, Assert). Hunt the two big classes: side effects that *silently never run* and side effects that run *twice*. Capture webhooks on a local receiver; verify emails via a mail catcher and actually use the emailed link.
- **File upload/download:** magic-byte vs declared-type mismatch (NestJS `FileTypeValidator` trusts spoofable Multer mimetype); extension bypass; path traversal in filename; SVG/HTML stored-XSS on the download path; BOLA on file retrieval; pixel-flood/zip-bomb DoS.
- **Pagination/sort:** unstable sort on a non-unique key with `skip/limit` (MongoDB 4.4+ duplicates/skips across pages — needs `_id` tiebreaker); insert/delete mid-scroll drift; sort-field injection.
- **Schema drift / migrations:** forge legacy-shaped docs directly in Mongo (raw driver bypasses casting) and read them back through the live API — reads don't validate, so missing fields surface as silent nulls/wrong defaults and old types throw CastErrors. Verify backfills are idempotent, resumable, count-reconciled, and tenant-scoped.
- **Feature flags:** the flag hides the UI button but the endpoint is still callable = authorization bypass, not cosmetic. Test both branches of every gate; check stale-flag caches and fail-open kill-switches.

---

## Part 4 — Oracles: deciding pass/fail with no written assertion

An oracle is a means of recognizing a problem. On a live app you rarely have a gold file, so **before every probe, state in one sentence: "This is a bug if ___"** and name at least one *observable* oracle. If nothing can distinguish pass from fail, you can't test that probe yet — get the missing info first.

### Concrete oracle sources you can observe live

- **Response oracle** — HTTP status, body values, headers, Content-Type, latency.
- **Schema/contract oracle** — body validates against the OpenAPI/derived schema: required fields present, correct runtime types (reject `total:"49.99"`), enum membership, formats (ISO date, uuid, email), and **no extra fields** (`additionalProperties:false` catches phantom fields / PII leaks).
- **DB oracle** — after a write, query Mongo directly and confirm the document was created/updated/deleted exactly right (fields, types, owner, timestamps). This catches the response that lied (201 with `status:'paid'` but no payment fired).
- **Log oracle** — no ERROR/stack trace/unhandled-rejection for this request.
- **Side-effect oracle** — the email/webhook/queue-job/cache-invalidation that should (or should *not*) have fired, did (or didn't). Assert **exact counts** to catch duplicates.
- **UI oracle** — the rendered DOM state and accessibility tree match expectations, and agree with the API and DB.

### FEW HICCUPPS — consistency heuristics for "is this a bug?"

When something looks off but you can't articulate why, run the mnemonic and name the violated consistency:

- **Familiar** — resembles a known bug pattern.
- **Explainable** — you can't coherently explain the behavior (a smell).
- **World** — contradicts reality (negative age, Feb 30, 250% discount).
- **History** — regression vs a prior version / your captured baseline.
- **Image** — embarrasses the brand (raw stack trace, mojibake).
- **Comparable products** — a sibling endpoint handles this more sensibly.
- **Claims** — contradicts Swagger/docs/AC (validation returns 200 with an error body; delete of a missing id returns 200 not 404).
- **User expectations** — a reasonable user would be surprised or harmed.
- **Product** — internally inconsistent (`total` ≠ sum of line items; `createdAt` is ISO on one endpoint, epoch on another).
- **Purpose** — defeats why the feature exists.
- **Standards/statutes** — violates HTTP/REST semantics, RFC 9457 error shape, WCAG, GDPR.

Every oracle is a fallible heuristic — an inconsistency is a signal to investigate, not proof. Name the oracle(s) in the bug so the finding is credible and reproducible.

---

## Part 5 — Risk-based prioritization & when a milestone is done

You cannot test everything with equal depth. Rank with **risk = likelihood × impact** (ISTQB).

- **Likelihood ↑** for endpoints that mutate money/state, touch auth, were changed in *this* milestone, handle untrusted input, or are new/complex.
- **Impact ↑** for anything security, PII, financial, or irreversible.
- Sort into a matrix: **High** → probe exhaustively (all boundaries + full attack checklist + authz matrix); **Medium** → green paths + key negatives; **Low** → smoke only.
- Re-score as you learn — finding one bug raises the likelihood of siblings.

This targeting is what makes finite live-probing time find the S1 auth-bypass before you run out of budget.

**Classify findings on two independent axes:** *Severity* (technical blast radius, tester-owned: S1 blocker/data-loss/security → S4 cosmetic) kept separate from *Priority* (business urgency, product-owned: P1→P4). A landing-page typo is S4/P1; a crash in a rarely-used admin export is S1/P3.

**Write each bug to be reproduced on the first try:** exact environment/build, the known starting state (preconditions), minimal numbered steps (the literal request or clicks), expected-vs-actual as *observed* (status + body + DB state + log line), the oracle that tripped, severity + priority, and evidence. Use randomized IDs so probes stay idempotent against the persistent DB.

### Milestone QA is done when:

0. **The QA plan file is closed** — written before probing, every row carries a terminal status, every bug written up, Final Report appended.
1. **Green-path coverage is provably complete** — every model's leaf is ticked: every route×method×role should-succeed cell returns its documented 2xx with a verified side effect; every input's valid classes and both valid boundaries pass; every legal state transition traversed; every decision-table success row run; every requirement traced to a passing probe. Any un-ticked leaf is reported as a named gap.
2. **High-risk areas are attacked to depth** — the full break checklist has been run on every money/state/auth/untrusted-input endpoint, and the OWASP authz probes (BOLA/BOPLA/BOFLA) run on every id-taking and role-gated endpoint.
3. **Defects meet the bar** — zero open S1/S2 (or explicitly waived by the product owner); remaining S3/S4 documented and non-blocking.
4. **Residual risk is written down and accepted** — you name what you did *not* cover and why, so the stop decision is deliberate, not accidental.

Stop when these hold, or when the cost of finding the next defect outweighs the release risk — and record that trade-off. Re-derive the models whenever the app changes; coverage is relative to the current spec, not a past run.

---

**The one-line mindset:** model the app so coverage is countable, attack exactly where a constraint should exist and probably doesn't, and judge every observation against an oracle you named before you looked.