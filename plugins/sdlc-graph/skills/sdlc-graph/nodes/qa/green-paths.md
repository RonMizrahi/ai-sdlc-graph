# GREEN-PATH TAXONOMY — Categories of VALID Flows to Always Cover

**THE RULE:** Every category below that is *present in the milestone* MUST be covered — **all of them, not a sample**. You may sample values only *within* a single equivalence class (all members behave alike); you must never skip a class, endpoint, verb, role, state transition, or flow. Coverage is "done" only when every applicable cell in every table has at least one passing live probe (2xx/visible-success) **and** a read-back confirms the side effect actually persisted. A 200 is not proof — re-GET the resource (or read the DB) and confirm the data agrees.

**How to build the inventory first (do this before probing):**
- Pull the NestJS OpenAPI/Swagger JSON (`/api-json`, `/api/docs-json`, `/swagger-json`) — every path×method×DTO×documented-response is a green-path row.
- Walk the React/Next.js app in Playwright; `browser_snapshot` enumerates every interactive control; capture `browser_network_requests` to find endpoints the UI actually calls (including ones missing from Swagger).
- List roles (anonymous, user, admin, service, ≥2 tenants) and resource states — both are inputs.

---

## A) API / BACKEND — valid flows to always cover

### A1. CRUD happy paths (per resource)
- [ ] **Create** returns the documented success status (201 on create, +`Location` header where applicable) and echoes the created resource.
- [ ] **Read by id** returns the resource with the full documented body shape.
- [ ] **Read list** returns the collection with the documented envelope.
- [ ] **Full update (PUT)** persists and read-back matches.
- [ ] **Partial update (PATCH)** persists only the intended fields; other fields untouched.
- [ ] **Delete** returns 200/204; **read-after-delete** returns 404 (or soft-deleted state as designed).
- [ ] **Create→read consistency (read-after-write):** immediately GET a just-created/updated resource and confirm it persisted and matches.

### A2. Authentication & session success
- [ ] Valid credentials → login succeeds, token/session issued; a **fresh** session id/token is minted at login (not the pre-login one).
- [ ] Each supported auth method works: password, OAuth/social, magic link, API key, "remember me" (checked vs unchecked).
- [ ] Token **within its valid window** authorizes protected endpoints.
- [ ] Refresh endpoint returns a NEW access+refresh pair and the new tokens work.
- [ ] Logout succeeds and the user can immediately re-establish a fresh valid session.

### A3. Authorization success — every allowed (role × action) cell
- [ ] For every endpoint gated by role/ownership, run the **authorized** path once per role that SHOULD succeed (admin creates, owner edits own resource, member reads shared resource, viewer reads).
- [ ] Run the same valid flow as ≥2 tenants and confirm each sees only its own data (positive-authorization + isolation).

### A4. Pagination / filtering / sorting (valid variants)
- [ ] Default page, a middle page, the exact **last** (partial) page, and the **first empty page past the end** (returns empty array + 200, not error, not wrap-to-page-1).
- [ ] Each valid page size incl. default, 1, and documented max.
- [ ] Each valid filter value: none-match, one-match, many-match; toggling a filter only shrinks the set; every returned row satisfies the filter.
- [ ] Each valid sort field × each direction (asc/desc), correctly ordered **and deterministic** across repeated runs.
- [ ] **Reassembly invariant:** concatenation of all pages == a single unpaginated fetch; reported `total` == distinct items delivered.

### A5. Valid boundary-INSIDE values (confirm ACCEPTANCE)
- [ ] Numeric min and max that SHOULD be accepted (e.g. 18 and 65 on an 18–65 field) both pass.
- [ ] String at exactly minLength and exactly maxLength both pass.
- [ ] Array at min and max cardinality both pass.
- [ ] Valid date at each recognized format passes. (Complements the break-path min−1/max+1.)

### A6. Valid input equivalence classes (one representative per class)
- [ ] Each valid enum/status value accepted.
- [ ] Optional field present-with-valid-value AND absent — both succeed (and don't diverge into different stored states).
- [ ] Each distinct valid shape (order with 1 item vs many; saved vs new address; guest vs authed).
- [ ] For multi-parameter endpoints, cover valid combinations via **pairwise** (every valid value-pair co-occurs at least once).

### A7. Empty-but-valid states
- [ ] List for a brand-new user/tenant with zero documents → 200 `[]` (not 404/500).
- [ ] Cardinality exactly one vs many vs max (serialization can differ per case).
- [ ] Empty-but-valid optional field (`""`, `[]`) accepted where the spec allows it.

### A8. State-machine / lifecycle transitions (0-switch: every legal edge once)
- [ ] Walk **every legal transition** of each stateful resource live (draft→placed→paid→shipped→delivered; invited→active→suspended; trial→active→cancelled), asserting the new persisted state after each.
- [ ] Confirm valid actions are ACCEPTED in the states where they're legal.
- [ ] For critical resources, also cover 1-switch (every legal *consecutive pair*) **without resetting** the entity between steps, so accumulated state is exercised.

### A9. Decision-table success rows (multi-condition rules)
- [ ] For every rule that depends on a combination of conditions (pricing/discount/eligibility/permission), run **every condition combination that yields a distinct valid outcome** and confirm the exact action.

### A10. Idempotent repeats (valid re-issue)
- [ ] Repeated GET/PUT/DELETE produce the same effect as once (GET has no side effect; second DELETE → 404 or 204, never 500).
- [ ] A create carrying the same **Idempotency-Key** replayed returns the identical result and produces the side effect **once** (DB count == 1).

### A11. Async side-effect green paths (the 200 is not the whole flow)
- [ ] Each enqueued job reaches its **terminal** state (`completed`) and populates all expected fields — verified by AWAIT-poll-until-terminal (never sleep, never assert-early).
- [ ] Each transactional email/notification actually lands (mail catcher), with correct recipient/subject/body; **use the emitted link/OTP end-to-end** (click reset link → set password → log in).
- [ ] Each outbound webhook actually fires with the correct payload and valid signature.
- [ ] Each cron/scheduled job's expected effect appears within its window, exactly once, and its run-marker advances.

### A12. Content / contract green paths
- [ ] Standard `Content-Type`/`Accept` headers → correct 2xx and body matching the DTO/OpenAPI schema (every required field present, correct types, enums valid, formats valid).
- [ ] Each documented response variant is actually produced (empty list, single, paginated, each status/discount tier).

---

## B) UI / FRONTEND — valid flows to always cover

### B1. CRUD happy paths through the browser
- [ ] Create via form (fill with valid unique data, submit) → success UI **and** a follow-up API GET/DB read confirms the backend state changed.
- [ ] Read: list and detail screens render the persisted data.
- [ ] Update: edit form saves; re-render/re-fetch shows the new value.
- [ ] Delete: item removed from UI **and** confirmed gone server-side.

### B2. Auth success flows
- [ ] Login form with valid credentials → authenticated UI.
- [ ] Signup → (verify) → login → first authenticated action, end-to-end.
- [ ] Logout → protected pages no longer render; re-login works.
- [ ] "Remember me" persists a session as designed.

### B3. Pagination / filtering / sorting in the UI
- [ ] Next/Prev/Last page controls; infinite-scroll load-more; page-size change.
- [ ] Apply each filter and each sort; rendered rows match the API ordering with **no visible duplicates** and no skips.
- [ ] Empty-state, single-item, and full-page renders each display correctly.

### B4. Role / permission variations (UI)
- [ ] Run each primary persona's full journey (admin, member, viewer) and confirm the intended controls are present and functional for each allowed role.
- [ ] Two live contexts (two Playwright sessions / tenants) each complete their valid flow.

### B5. Valid boundary-inside & equivalence input (forms)
- [ ] Submit valid values at min/max boundaries and confirm the form accepts and persists them.
- [ ] Cover each valid variant of a form (guest vs logged-in checkout; saved vs new payment/address; with vs without valid coupon) — every success branch.

### B6. Empty / populated states
- [ ] Zero rows, exactly one row, and exactly page-size rows each render as intended.

### B7. Lifecycle / multi-step wizards (legal transitions)
- [ ] Walk every legal step of each wizard/workflow to completion; assert the visible success post-condition **and** the underlying network request/response.
- [ ] Valid re-entry/resume (resume abandoned cart, re-open editable draft) reaches success.

### B8. Idempotent repeats (UI)
- [ ] Re-loading a completed screen, or re-running an idempotent read, shows consistent state (no double-append, no drift).

### B9. Navigation / state-persistence green paths
- [ ] Deep-link directly to a detail route/filtered list/wizard step → the app rehydrates that exact state from the URL.
- [ ] Refresh on each meaningful screen → state persists (or degrades gracefully).
- [ ] Back/Forward after navigation → URL, rendered state, and network all agree.
- [ ] Direct-URL to a protected route while logged in works; while logged out redirects to login and returns after auth.

### B10. Cross-platform green path (Platform)
- [ ] Run each critical journey at mobile (375px), tablet (768px), and desktop widths — the same green paths complete at every breakpoint (controls reachable, no clipped submit).

### B11. Accessibility green path (the app is usable, not just present)
- [ ] Each key journey is completable **keyboard-only** (Tab/Shift+Tab/Enter/Space/Esc/Arrows), with visible focus, no keyboard trap, and focus returned after a modal closes.
- [ ] Every interactive control has a role + accessible name (verify via `ariaSnapshot`/`getByRole`).

### B12. i18n / localization green path (where applicable)
- [ ] Each supported locale renders correct date/number/currency formats; RTL locales mirror the whole layout; non-ASCII input round-trips form→API→DB→re-read without corruption.

---

## Coverage completeness rule of thumb (all must be true)
- [ ] Every endpoint×verb in the OpenAPI spec has ≥1 authorized success (read-back confirmed).
- [ ] Every input field has ≥1 valid-partition rep AND both valid boundary values passing.
- [ ] Every user role has performed every action it is permitted.
- [ ] Every valid state transition has been traversed once (0-switch), critical ones 1-switch.
- [ ] Every decision-table success row has run.
- [ ] Every async side effect (job/email/webhook/cron) has a positive assertion at its terminal state.
- [ ] Every primary persona has one full end-to-end UI journey, at every supported breakpoint.
- [ ] Every list endpoint covered for cardinality zero / one / many / max and pagination first / middle / last / past-last.
