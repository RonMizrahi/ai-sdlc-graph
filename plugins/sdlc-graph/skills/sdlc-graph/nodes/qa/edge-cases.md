# EDGE-CASE CATALOG — High-Yield Values to Throw at Any Field/Flow

Punchy, high-density list. Bugs cluster at boundaries and at the seam between valid and invalid. Feed these into every text field, numeric field, param, date, id, and list — one at a time (so you can attribute the failure). A clean 4xx/handled result is a pass; a 500 / silent corruption / wrong stored value / cross-tenant leak is the bug.

## Null / empty / whitespace (5 distinct "empty" shapes)
- [ ] Key **absent** vs `null` vs `""` vs `"   "` (spaces/tabs) vs `0` — each often takes a different path.
- [ ] Whitespace-only that passes `required` but is semantically empty; non-breaking space `U+00A0`; zero-width space `U+200B` (500'd Twitter); newline/CRLF in a single-line field.
- [ ] Literal `"null"`, `"undefined"`, `"NaN"`, `"None"`, `"true"`/`"false"` as text.
- [ ] Trimming consistency: is `"a@b.com "` trimmed the same on write and on the uniqueness check?

## Huge inputs
- [ ] 1MB / 10MB string; 100k-element array; deeply nested JSON (1000+ levels); repeated JSON keys.
- [ ] Unbounded pagination: `limit=999999999` (whole-collection dump / OOM), `limit=-1` (Mongoose = no limit), `limit=0`.
- [ ] Oversized/zero-byte upload; pixel-flood image (tiny file, 64000×64000 dims); zip bomb.

## Unicode / emoji / RTL
- [ ] 4-byte & ZWJ emoji (`😍`, `👩🏽`, `👨‍👩‍👦`) — break length checks (bytes vs UTF-16 units vs graphemes), truncate mid-grapheme, overflow fixed columns.
- [ ] NFC `é`(U+00E9) vs NFD `e`+`U+0301` treated as different → duplicate users / failed search.
- [ ] RTL override `U+202E` (`exploit‮gpj.exe` shows as `exe.jpg`); mixed bidi (Arabic+Latin+digits) layout.
- [ ] Zalgo / combining overload; homoglyphs; case-folding traps (German `ß`↔`SS`, Turkish dotless `ı`).

## Timezones / DST
- [ ] Non-existent local time (02:30 on spring-forward day); ambiguous time (01:30 on fall-back, occurs twice).
- [ ] Day-boundary: user in UTC+13 vs server UTC — "today"/"created today" off by a day.
- [ ] Time with vs without explicit offset (interpreted as UTC vs server-local vs user-local).
- [ ] Naive local-time storage (no TZ) → shifts for other-timezone users and drifts across DST.

## Money / rounding
- [ ] Float drift: `0.1+0.2 = 0.30000000000000004`; sums failing exact-equality payment checks.
- [ ] Half-up vs banker's half-even mismatch (1.005 stored as 1.00499… → surprising round).
- [ ] Proration/split not summing back (10.00 ÷ 3 leaking a cent); negative/refund rounding direction.
- [ ] Zero-decimal currency (JPY) vs 2-decimal (USD); money as JSON float instead of integer cents.
- [ ] Discount > price → negative total; quantity 0 → divide-by-zero.

## Leap years / dates
- [ ] Ghost dates: `2023-02-29`, `2024-02-30`, `2023-04-31`, `2023-13-01`, `2023-00-15` → reject, not silent-roll or 500.
- [ ] Leap anniversary: `+1 year` from `2024-02-29` → `2025-02-28` vs `2025-03-01` (verify vs spec).
- [ ] Century rule: 1900 (not leap), 2000 (leap); year rollover `2024-12-31 + 1 day`.
- [ ] Epoch 0, far-future (9999), far-past; `checkOut < checkIn`; expiry in the past.

## Off-by-one / boundaries
- [ ] Numeric: min−1, min, min+1, max−1, max, max+1; 0, 1, −1; `MAX_SAFE_INTEGER` and +1 (precision loss).
- [ ] String length: 0, 1, minLength±1, maxLength, maxLength+1.
- [ ] `<` vs `<=` at the exact threshold ($100 free-shipping tested at 99.99 / 100.00 / 100.01).

## Duplicate keys / uniqueness
- [ ] Sequential create-twice (E11000 leaking a 500?) and **concurrent** race with no DB unique index → two rows.
- [ ] Case/whitespace-only difference (`User@X.com` vs `user@x.com`); NFC vs NFD duplicates.
- [ ] Duplicate JSON object key `{"email":"a","email":"b"}` (which wins?); duplicate array items where a set is expected.

## Pagination limits & stability
- [ ] `page=0` vs `page=1` off-by-one; last partial page remainder; page past the end → empty (not wrap-to-1, not 500).
- [ ] Insert-during-scroll (offset) → duplicate at page seam; delete-during-scroll → skipped item.
- [ ] Sort on a non-unique key with no `_id` tiebreaker → items duplicated/dropped across pages (MongoDB 4.4+ unstable).
- [ ] Sort by nonexistent/unindexed field → non-deterministic order / COLLSCAN blowup / 500 on 32MB sort.

## Concurrency
- [ ] Two identical creates/writes fired simultaneously (double-submit, double-charge, double-create).
- [ ] Check-then-act race: balance withdraw, inventory reserve, single-use coupon, rate-limit counter → invariant broken.
- [ ] Two writers on one document → lost update (no optimistic lock); request arriving during redeploy/shutdown → partial write.
- [ ] Non-idempotent job re-run after worker crash / retry → side effect fires twice.

## Auth / authorization edges
- [ ] Another tenant's id (BOLA) in path/query/header/body; sequential/guessable id enumeration.
- [ ] Extra privileged fields in body (mass assignment); token for a deleted/suspended user; expired vs not-yet-valid token; `alg=none`; role param pollution.
- [ ] Access an object in a state your role can't (read a draft); replay token after logout / after role revoke.

## Malformed transport / ids
- [ ] Malformed ObjectId (`abc`, `00`, non-hex, valid-length-but-nonexistent) → 400/404, not CastError 500.
- [ ] Wrong `Content-Type`; truncated/garbage JSON; missing/expired/tampered JWT; array where scalar expected (`?id=1&id=2`).
- [ ] NoSQL operator object where scalar expected (`{"$ne":null}`, `{"$gt":""}`, `{"$regex":".*"}`).

## Output / rendering
- [ ] 0 results, exactly 1, exactly page-full; result containing HTML/script (stored XSS); count-in-header vs count-in-body disagreement; stale cache; currency/locale mis-format.
