# hero-proto API conventions

Rules every route follows. If you add one, conform — or document the deviation here and update this doc.

---

## Error response shape

All error responses use FastAPI's `HTTPException` convention:

```json
{ "detail": "human-readable message" }
```

Pydantic validation errors (wrong types, missing fields, failing `Field()` constraints) come back as 422 with a list structure:

```json
{ "detail": [{"type": "missing", "loc": ["body", "team"], "msg": "Field required", "input": {...}}] }
```

Clients should check `typeof response.detail` — string for everything we raise manually, list for validation.

### Status codes

- **401** — unauthenticated (missing/invalid/expired bearer token, revoked by `token_version` bump).
- **403** — authenticated but not authorized (non-admin hitting `/admin/*`, non-leader hitting guild leader actions, banned account).
- **404** — resource not found. Also used for "resource exists but the caller can't see it" where 403 would leak the existence (admin/purchase ids, arena matches the caller wasn't in).
- **409** — state conflict. Attempting a state transition that's blocked: already-used token, already-claimed quest, starter-pack already bought, energy already at cap, reset-token-already-used, etc.
- **410** — resource *was* valid but has expired (reset tokens, verification tokens past `expires_at`).
- **422** — validation. Field types/lengths/enum values/min-max bounds failed the Pydantic model.
- **429** — rate limit exceeded. Retry-After header on the response.
- **500** — unhandled exception. Should never happen in steady state.
- **502** — upstream dependency failed (Stripe SDK error during checkout creation).
- **503** — a feature is disabled by config (`/shop/checkout/stripe` before Stripe keys are set, `/shop/purchases` when `MOCK_PAYMENTS_ENABLED=false` and no Stripe, email-sender in `disabled` mode).

When in doubt, prefer more-specific codes over 500.

---

## List endpoints: pagination + caps

**Every list-returning endpoint has a server-enforced maximum.** Client-provided `limit` is clamped, not rejected. Out-of-range values just get pulled back into the cap range.

Two pagination styles, both supported:

### Offset + limit (most list endpoints)

Default when no stable secondary order exists or when the list is small.

```
GET /guilds?limit=50&offset=100
```

- `limit`: default varies per endpoint (see table below), hard cap enforced.
- `offset`: default 0, no upper bound but is slow at high values (use keyset for hot paths).

Order: documented per-endpoint; typically `id DESC` (newest first) or business-specific.

### Keyset / cursor (high-traffic history endpoints)

Used where new items arrive frequently and `offset` would miss/duplicate rows.

```
GET /guilds/{id}/messages?before=<last_seen_id>&limit=20
```

- Initial call: omit `before` to get the latest page.
- Subsequent: pass the **smallest** id from the current view as `before` to page into history.

Currently used only by `/guilds/{id}/messages`. New endpoints with a strict newest-first feel should follow suit (arena history, combat log history if it ever becomes user-facing, etc.).

### Limit defaults + caps by endpoint

| Endpoint | Default | Cap | Pagination |
|---|---:|---:|---|
| `GET /guilds` | 100 | 500 | offset |
| `GET /heroes/mine` | 500 | 1000 | offset |
| `GET /heroes/templates` | — | fixed (content-bounded) | — |
| `GET /gear/mine` | 500 | 1000 | offset |
| `GET /stages` | — | fixed (content-bounded) | — |
| `GET /arena/opponents` | — | `OPPONENT_SAMPLE_SIZE` (3) | — |
| `GET /arena/leaderboard` | 20 | 20 | — |
| `GET /arena/matches/{id}` | — | single resource | — |
| `GET /guilds/{id}/messages` | 50 | 200 | **keyset** (`before=<id>`) |
| `GET /guilds/{id}/applications` | — | all pending for that guild | — |
| `GET /guilds/applications/mine` | 50 | 200 | — |
| `GET /announcements/active` | 20 | 100 | — |
| `GET /liveops/active` | — | all active (small) | — |
| `GET /liveops/scheduled` | — | `horizon_days=7` window | — |
| `GET /shop/products` | — | all active (catalog-bounded) | — |
| `GET /shop/purchases/mine` | 50 | 200 | — |
| `GET /daily` | — | 3 per-day by design | — |
| `GET /admin/accounts` | 50 | 200 | `limit` + optional `q=<email-substring>` |
| `GET /admin/audit` | 100 | 500 | optional `target_id=` + `action=` filters |
| `GET /admin/purchases` | 100 | 500 | `account_id=` + `state=` filters |
| `GET /admin/announcements` | 100 | 500 | optional `include_inactive=true` |
| `GET /shop/products` | — | all active | optional `include_unavailable=true` |

---

## Naming

- **Timestamp fields:** `*_at` (ISO-8601 UTC strings in responses; naive UTC `datetime` in Python). Never `*_time` or `*_timestamp`.
- **Boolean fields:** `is_*` for state (`is_admin`, `is_banned`, `is_active`) or verb participles (`completed`, `revoked`).
- **Foreign key fields:** `<table>_id`. The one exception is arena's `attacker_id`/`defender_id` which are semantic roles within the same table.
- **Amount fields:** plain integer nouns (`gems`, `coins`, `shards`, `access_cards`). Never a unit suffix (`gem_count`, `coins_qty`).
- **Duration inputs:** `duration_hours` (float). Date inputs: `starts_at` / `ends_at`.
- **Enum values:** SCREAMING_SNAKE_CASE, match the StrEnum member exactly (`HARD`, `LEGENDARY`, `CLEAR_HARD_STAGE`).

---

## Idempotency

Endpoints where retries could accidentally double-act accept an idempotency key:

- `POST /shop/purchases` — `client_ref` (dedupes via `UNIQUE(processor, processor_ref)`).
- `POST /shop/checkout/stripe` — same.
- Stripe webhook — Stripe's own retry guards + `processor_ref=<session_id>` on our side.

Other write endpoints (summon, attack, claim) are intentionally *not* idempotent — double-click means you took the action twice. Clients should debounce on their side.

---

## Authentication

Bearer tokens in `Authorization: Bearer <jwt>`. Refresh flow:

- Access tokens: 24-hour default TTL (config `JWT_TTL_MINUTES`). Embedded `token_version` — bumped on ban, password reset, or detected refresh-token reuse.
- Refresh tokens: 30-day default TTL. Presented to `POST /auth/refresh` to rotate into a fresh access + refresh pair. Re-presenting a rotated refresh token revokes the entire chain (theft signal).
- 2FA (if enabled): login returns `{status: "totp_required", challenge_token}` instead of tokens. Client follows up with `POST /auth/2fa/verify`.

Endpoints that don't require auth: `/healthz`, `/worker/status`, `/metrics`, `/app/*`, `/auth/register`, `/auth/login`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/verify-email`, `/auth/refresh`, `/auth/logout`, `/auth/2fa/verify`, `/announcements/active`, `/stages`, `/liveops/active`, `/liveops/scheduled`, `/shop/webhooks/stripe`.

Everything else requires a valid access token.

---

## Admin-only gating

Admin endpoints live under `/admin/*` and depend on `get_current_admin`. Non-admin authenticated users get 403. Unauthenticated get 401. The CLI (`python -m app.admin`) bypasses the HTTP layer entirely and writes to the DB directly — use it for bootstrap tasks (first admin, DB forensics).

---

## Versioning

No API versioning today. The alpha tier is "single version, breaking changes communicated out-of-band." When this repo crosses into maintained-client territory:

- Introduce `/v1` prefix on all routes.
- Preserve `v1` indefinitely when adding `/v2`.
- Document breaking changes in a CHANGELOG.

Until then, don't assume backward-compat across commits.

---

## Backend-side safety defaults

Rules that the router enforces silently (no client error) and worth knowing:

- Ban + demote bump `token_version` — all prior access tokens die immediately, refresh tokens too.
- Password reset clears the refresh chain completely (stolen-password-also-stole-session).
- Purchase refunds clamp balances at zero — never push negative.
- Hero grants from purchases are NOT auto-revoked on refund (manual CS decision; logged in PurchaseLedger).
- Guild leaders deleting their account are auto-replaced by the oldest remaining member (or the guild disbands).
- Banned accounts can't appear in arena matchmaking even if they still have a defense team.
- Arena recently-attacked defenders are excluded from matchmaking for 30 minutes (falls back to no-exclusion only if the pool is empty).
- Rate limiter open-fails when Redis is unreachable — we prefer false-positives over locking users out.
- Worker supervisor respawns the tick loop on any crash (except `CancelledError`, which is a clean shutdown).
