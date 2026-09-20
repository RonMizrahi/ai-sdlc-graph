# BREAK-IT TAXONOMY — Categories of Attacks / Negative / Adversarial Probes

**THE RULE:** Developers constrain the happy path and forget the boundaries — so attack exactly where a constraint *should* exist and probably doesn't. Judge every response against the oracles: a clean 4xx with a safe message is a pass; a **500 with a stack trace, a silent partial write, an unhandled promise rejection, data belonging to another tenant, or a side effect that happened twice** all mean "the constraint was missing." Run these against the LIVE app (HTTP + Playwright) — no test code; each attack is a row in the QA plan file, ticked off with its result as you go. Always use randomized ids/emails per run so probes stay idempotent against a persistent DB; never poison real users (use a unique cache-buster / your own callback URL).

Work the surface systematically: for each endpoint, after the green path passes, walk every applicable category below. Two accounts (A and B) in two tenants are prerequisites for the authorization probes.

---

## API / BACKEND ATTACKS

### API-1. Malformed / missing / wrong-type / extra input (force every error path)
- [ ] Omit each required field → clean 400, not 500.
- [ ] Wrong type per field: string where number, array where scalar, object where string, boolean-as-"true"/1/0.
- [ ] Out-of-enum value; malformed email/date/ObjectId; duplicate of a unique key.
- [ ] `null` vs `undefined`/absent vs `""` vs `"   "` (whitespace) vs `0` — each may hit a different code path.
- [ ] Literal strings `"null"`, `"undefined"`, `"NaN"`, `"None"` into typed fields.
- [ ] Extra/unexpected fields; duplicate JSON keys `{"email":"a","email":"b"}`.
- [ ] Malformed JSON (trailing comma, unclosed brace), empty body.
- [ ] **Stack multiple violations** in one request to find handlers that only check the first error.

### API-2. Boundary / overflow / off-by-one
- [ ] For every numeric/length/date/quantity/pagination limit: min−1, min, min+1, max−1, max, max+1.
- [ ] Type edges: 0, −1, `Number.MAX_SAFE_INTEGER`, +1 past it (precision loss), `1e309`→Infinity, NaN via "NaN", floats where ints expected, leading zeros, hex/octal/scientific notation.
- [ ] String at maxLength and maxLength+1; multi-byte length ambiguity (emoji counted as chars vs bytes vs graphemes).
- [ ] Verify the boundary flips at exactly the spec value (`<` vs `<=`).

### API-3. Oversized / resource-exhaustion (OWASP API4)
- [ ] 10⁴/10⁶/10⁷-char string in an unbounded field; 100k-element array; deeply nested JSON (1000+ levels).
- [ ] List endpoint with `limit=1000000`, `limit=-1` (Mongoose treats as no-limit → whole collection), `limit=0`, missing limit → unbounded dump / OOM / event-loop stall.
- [ ] Oversized upload; many-small-files flood; unpaginated aggregation loading a whole collection into memory.
- [ ] Deep-pagination latency: `skip()` blowup — measure p95 as offset grows (page 1 vs 100k).

### API-4. Authorization: BOLA / IDOR (object-level)
- [ ] As user A, capture A's resource id; replay authenticated as B (and unauthenticated) with A's id — GET, then PATCH/PUT/DELETE (read may be guarded while write isn't).
- [ ] Enumerate sequential ids; harvest ObjectIds from list endpoints/errors (they're semi-guessable).
- [ ] Try the id in every location: path, query, header, and body.
- [ ] List/search endpoints: as B, confirm results never include A's / other tenants' rows.

### API-5. Authorization: BFLA / privilege-function escalation
- [ ] Call admin-shaped routes (`/admin/*`, `/users/export_all`, `/:id/promote`) as a low-priv user and unauthenticated.
- [ ] Method swap on a readable endpoint (GET→PUT/PATCH/DELETE) to find handlers missing a guard.
- [ ] `OPTIONS` to read the `Allow` header, then attack any admitted method the UI never uses.

### API-6. Authorization: BOPLA / mass assignment
- [ ] Inject privileged/read-only fields into create/update bodies: `role:"admin"`, `isAdmin:true`, `isVerified:true`, `balance:999999`, `ownerId:<someone-else>`, `_id`, `createdAt`. Re-GET to see if they stuck.
- [ ] Excessive exposure (read side): scan responses for fields the caller shouldn't see (passwordHash, resetToken, internal flags, other users' PII).
- [ ] Confirm the ValidationPipe uses `whitelist:true, forbidNonWhitelisted:true`.

### API-7. Authentication bypass & token manipulation
- [ ] NoSQL auth bypass on login: `{"email":{"$gt":""},"password":{"$ne":"x"}}` → logs in as first user.
- [ ] JWT: no token, garbage token, expired token, `exp` removed / set far-future, tampered payload (role user→admin) without re-signing, `alg=none`/`None`/`nOnE` with stripped signature, RS256→HS256 confusion using the public key as HMAC secret, decode-vs-verify (accepts any structurally-valid token), future `nbf`, wrong `iss`/`aud`.
- [ ] 401-vs-403 correctness (anonymous getting 403, wrong-role getting 401 = semantic defect).

### API-8. Injection
- [ ] **NoSQL operator injection:** replace a scalar with an operator object `{"$ne":null}`, `{"$gt":""}`, `{"$regex":".*"}`, `{"$where":"sleep(5000)"}` — in JSON body and via bracket query (`?password[$ne]=x`); blind char-by-char extraction with `$regex:"^a"`.
- [ ] **ReDoS:** catastrophic-backtracking regex (`(a+)+$`) or a long `aaaa…!` input into a search/`$regex` field; watch latency climb ~2× per char.
- [ ] **Stored XSS:** submit `<img src=x onerror=...>` / `<svg><script>…</script></svg>` via API, then render the page in Playwright and check console/dialog for execution.
- [ ] Sort/filter injection: `?sortBy=passwordHash`, `?sort[$where]=…`, object form to order by an excluded field.

### API-9. HTTP parameter pollution & content/verb tampering
- [ ] Duplicate params `?role=user&role=admin` (guard sees one value, handler uses the other).
- [ ] Array where scalar expected `?id=1&id=2`.
- [ ] Wrong `Content-Type` (form-encoded/text-plain to a JSON endpoint) → expect 415/400, not 500.
- [ ] Unsupported verb → 405 (+`Allow`), not 404; trailing dot/slash/case-variant on the path to slip past route-based auth.

### API-10. Rate-limit & abuse
- [ ] Fire an unauthenticated endpoint in a tight loop → expect 429; if a "5/min" limit lets 30 through, the counter is check-then-increment (racy).
- [ ] Repeated calls to a paid side effect (email/SMS) for cost/DoS.
- [ ] Oversized body → expect 413 cap.

### API-11. Concurrency / races
- [ ] Fire N identical/competing requests **simultaneously** through a check-then-act window: balance withdraw, inventory reserve, single-use coupon, unique-email signup, rate limit — then assert DB invariants (no negative balance, no double-consume, no duplicate unique row).
- [ ] Two concurrent creates racing a unique constraint (no DB unique index → two rows).
- [ ] Two concurrent transition requests on the same resource (missing optimistic lock / guard).
- [ ] Two tabs/writers editing the same document → lost update.

### API-12. Idempotency violation
- [ ] Replay the identical POST 2×/10× sequentially and concurrently → duplicate records / double charges / double webhooks / non-monotonic counters.
- [ ] Same Idempotency-Key with a DIFFERENT body → must be rejected (key bound to one op).
- [ ] Two concurrent requests with the SAME key → exactly one executes.
- [ ] Replay a spent refresh token / a webhook event twice → no second side effect; dedup TTL must outlive the provider's retry window.

### API-13. Broken / invalid state transitions
- [ ] Fire every **illegal** edge (empty cells of the state table): pay an already-paid order, ship an unpaid one, cancel a delivered one, refund twice, act on a deleted/expired resource, skip a required intermediate state, child before parent. Expect clean 409/422 and unchanged state.
- [ ] Out-of-sequence API calls (call a later endpoint directly to skip a prior step).
- [ ] Self-referential/cyclic parent link → traversal recursion / stack overflow.

### API-14. Referential integrity
- [ ] Delete a parent with existing children → orphan handling / cascade; render an orphaned doc in the UI (populate null → crash).
- [ ] Reference a non-existent foreign id; malformed ObjectId on a `:id` route → 400/404, not a CastError 500.

### API-15. Interrupt / partial-write / network & latency faults
- [ ] Abort the socket mid multi-write; make the second write of a non-transactional op fail → inspect DB for half-completed state (order created, inventory not decremented).
- [ ] Point at a slow/paused/killed dependency (Mongo/Redis/upstream) → expect clean 503/timeout, not a 30s hang, event-loop stall, or leaked stack trace.
- [ ] Missing outbound timeout: inject latency and confirm the request doesn't hang forever.
- [ ] Retry behavior: force 500/429 from a controllable receiver → confirm retries with backoff+jitter, `Retry-After` respected, no retry on permanent 4xx, retries stop after max.

### API-16. Computation / output faults
- [ ] Force results out of range: `price*quantity` with `quantity=1e309`→Infinity/null in JSON; discount > price → negative total; divide-by-zero (quantity 0); money float drift (0.1+0.2), half-up vs banker's rounding mismatch; proration not summing back to the whole.
- [ ] Cross-field contradictions: `checkIn > checkOut`, `status:'shipped'` with no address, start>end.

### API-17. Caching correctness & security
- [ ] After a write, immediately re-read → stale value from CDN/cache = invalidation failure.
- [ ] Two-identity shared-cache leak: private/authenticated response served to another user (must be `private`/`no-store`).
- [ ] `Vary` correctness: language/encoding/auth variant cross-contaminating cache.
- [ ] Web cache **poisoning** (unkeyed header `X-Forwarded-Host` reflected) and **deception** (private page cached as `/account/x.css`) — always with a cache-buster.

### API-18. File upload/download
- [ ] MIME/extension spoof (script bytes declared `image/png`; `shell.php.png`, `shell.php%00.png`, `.svg`/`.html`); magic-byte vs declared-type mismatch.
- [ ] Path-traversal filename `../../../etc/x`; overwrite another user's file; pixel-flood / zip-bomb / oversize.
- [ ] Download BOLA: fetch another tenant's file by mutating id/storage key; signed-URL expiry/tamper; SVG/HTML served inline → stored XSS.

---

## UI / FRONTEND ATTACKS

### UI-1. Bypass the client (server is the real boundary)
- [ ] Capture the request a valid UI action sends, then replay it with mutated fields the UI never offered (negative quantity, price override, extra `role:'admin'`, another user's id) — confirm the server re-validates.
- [ ] Submit values the UI's dropdown/validation forbade, directly via HTTP.

### UI-2. Malformed / boundary input in forms
- [ ] Empty, whitespace-only, boundary lengths, wrong format, leading/trailing spaces into each field — confirm inline error AND that the server rejects the same via direct HTTP (not just the client).
- [ ] Cross-field rules both directions (password==confirm, end>start).

### UI-3. Unicode / emoji / RTL / encoding
- [ ] Emoji/ZWJ (`👨‍👩‍👦`), 4-byte UTF-8, combining chars, RTL override (`‮`), homoglyphs, null byte, zero-width space, zalgo — into every text field. Check storage, length limits, truncation mid-grapheme, layout overflow, and re-read round-trip.
- [ ] NFC vs NFD normalization (`café` two ways) → duplicate accounts / failed dedupe.

### UI-4. XSS (stored & reflected)
- [ ] Inject `<script>`/`<img onerror>`/`<svg onload>` into text fields, then load the rendering page in Playwright and watch `browser_console_messages`/dialogs for execution (esp. `dangerouslySetInnerHTML`).
- [ ] Reflected: payload in a query param echoed into the DOM.

### UI-5. Double-submit / non-idempotency
- [ ] Double-click Submit as fast as possible; count requests via `page.on('request')` (expect exactly 1).
- [ ] Observe whether the button disables **synchronously** on click or only after the response (the vulnerable window).
- [ ] Back-button → resubmit; retry after timeout → duplicate order / double charge.

### UI-6. Actionability-as-oracle (hangs and silent no-ops reveal bugs)
- [ ] When an action hangs: map to the failed check — never Stable (spinner/animation never settles), never Enabled (validation gate never cleared), never ReceivesEvents (invisible overlay/backdrop intercepting clicks).
- [ ] When an action "does nothing": an auto-wait that eventually succeeds can MASK a race (button disabled 800ms) — a human clicking in that window triggers the double-submit.

### UI-7. Back / refresh / deep-link / unauth access
- [ ] Deep-link to a detail route/modal/wizard-step in a fresh tab → must rehydrate from URL, not blank/404.
- [ ] Refresh mid-wizard → state must persist, not silently reset the cart.
- [ ] Back after a successful mutation → must not re-show the pay form and allow re-pay.
- [ ] Direct-URL to a protected route while logged OUT → redirect to login, not a broken shell.

### UI-8. Session/state edges in the browser
- [ ] Token expires mid-flow (between "add to cart" and "pay") → clean re-auth, not silent data loss.
- [ ] Two tabs mutating the same resource → last-write-wins clobber without concurrency check.
- [ ] Stale render: change a value via API while a tab holds an old render; list vs detail views disagree after a concurrent edit.
- [ ] Optimistic UI shows success while the API actually 4xx/5xx'd and never rolled back → DOM and DB disagree; item reappears on refresh.

### UI-9. Responsive / viewport breakage
- [ ] Drive key flows at 320/375/768/1024/1440 and just above/below each breakpoint: no horizontal overflow, no clipped submit, hamburger toggle reachable and named, no fixed footer/menu overlapping (intercepting) the primary button.

### UI-10. Accessibility failures (real blockers)
- [ ] Icon-only control with no accessible name (unreachable by AT / `getByRole`).
- [ ] Keyboard trap; focus not returned after modal close; focus obscured by sticky header.
- [ ] Clickable `<div>` with no role/keyboard handler (mouse-only).
- [ ] Error conveyed by color alone; contrast below 4.5:1 (text) / 3:1 (large/non-text).
- [ ] `opacity:0` element still focusable/clickable (hidden but interactable).

### UI-11. Network-channel divergence
- [ ] For every mutation, confirm via the network log that exactly ONE call fired, to the right endpoint+verb+payload, with a 2xx — a success toast + removed row while the DELETE returned 500 is a lie.
- [ ] A "saved" form where `waitForResponse` never fires = the submit handler threw client-side and no call was made.

---

## The oracle (apply to EVERY observation) — FEW HICCUPPS
Familiar bug pattern · Explainable · World (physically possible) · History (regression) · Image (leaked stack trace/PII) · Comparable products · Claims (matches Swagger/docs) · User expectations · Product (internally consistent across sibling endpoints) · Purpose · Standards/Statutes (HTTP/REST/RFC/WCAG/GDPR). Any inconsistency = candidate bug; name the violated oracle in the report.
