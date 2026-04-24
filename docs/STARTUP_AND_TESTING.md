# Game startup + testing procedure

Two phases. **Admin startup** gets the server into a known-good state and verifies it from the operator side. **Client walkthrough** exercises every player-facing feature as a real user would. Both phases have a documented manual path and an automated script.

Run order: admin first (build/config/start), then client (feature tour).

---

## Phase 1 — Admin startup

### 1a. First-time prep (skip if already done)

```bash
# From repo root
uv sync --all-extras
```

If `app/static/heroes/` is empty or missing SVGs: [`docs/ART_NEEDS.md`](ART_NEEDS.md). The backend works without art (placeholders are generated on demand); only visual pages look rough.

### 1b. Environment config

Pick the right preset per deploy tier:

**Local dev (quick iteration):**
```bash
export HEROPROTO_ENVIRONMENT=dev
export HEROPROTO_RATE_LIMIT_DISABLED=1
export HEROPROTO_MOCK_PAYMENTS_ENABLED=1
# Leave JWT_SECRET at default; it only matters in prod.
```

**Staging (mirrors prod closely):**
```bash
export HEROPROTO_ENVIRONMENT=prod
export HEROPROTO_JWT_SECRET="$(openssl rand -base64 48)"
export HEROPROTO_DATABASE_URL=postgresql+psycopg://...
export HEROPROTO_CORS_ORIGINS=https://staging.yourdomain.com
export HEROPROTO_JSON_LOGS=1
export HEROPROTO_EMAIL_SENDER_TYPE=smtp
export HEROPROTO_EMAIL_SMTP_HOST=...
export HEROPROTO_EMAIL_SMTP_PASSWORD=...
export HEROPROTO_PUBLIC_BASE_URL=https://staging.yourdomain.com
export HEROPROTO_STRIPE_API_KEY=sk_test_...
export HEROPROTO_STRIPE_WEBHOOK_SECRET=whsec_...
# Optional: shared rate-limit + error tracking
export HEROPROTO_RATE_LIMIT_BACKEND=redis
export HEROPROTO_REDIS_URL=redis://redis:6379/0
export HEROPROTO_SENTRY_DSN=https://...@sentry.io/...
```

**Prod:** same as staging with `sk_live_*` Stripe keys and `prod` DSN. Full env var reference in [`docs/RUNBOOK.md`](RUNBOOK.md).

### 1c. Migrate + seed

```bash
# Applies any pending Alembic migrations.
uv run alembic upgrade head

# Seeds 25 hero templates, 10 stages, 10 hard-mode stages, 7 shop products,
# and a launch LiveOps event. Idempotent — skips anything that already exists.
uv run python -c "from app.seed import seed; seed()"
```

Expected output:
```
seeded heroes+=25 stages+=20 liveops+=1 products+=7
```

On re-runs after the initial seed: `heroes+=0 stages+=0 liveops+=0 products+=0` is correct (nothing new to add).

### 1d. Create the first admin

Two options, both idempotent:

- **Env-driven** — set `HEROPROTO_ADMIN_EMAILS=you@example.com` before the first registration of that email; they auto-promote.
- **CLI** (if the account already exists):
  ```bash
  uv run python -m app.admin promote you@example.com
  ```

Verify:
```bash
uv run python -m app.admin list
```

### 1e. Start the server

```bash
uv run uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Prod: behind a reverse proxy (Nginx / Caddy / ALB) terminating TLS.

If `_check_secrets()` raises `RuntimeError` at startup, read the message carefully — it's telling you a specific env var is still at a dev-only default in a prod environment. **Don't work around it.**

### 1f. Admin-side health verification

```bash
# Local:
uv run python -m scripts.startup_check

# Against a remote:
HEROPROTO_BASE=https://your-domain uv run python -m scripts.startup_check

# With admin-endpoint verification (recommended):
STARTUP_CHECK_ADMIN_EMAIL=you@example.com \
STARTUP_CHECK_ADMIN_PASS=your-password \
uv run python -m scripts.startup_check
```

What it checks:

| Check | What it validates |
|---|---|
| `/healthz` responds 200 | FastAPI is up |
| `/worker/status` ticked recently | Background worker is alive (not stuck) |
| `/metrics` exposes Prometheus counters | Observability is wired |
| Database migrations + content seeded | `/stages` returns > 0 |
| Registration round-trip | `/auth/register` + `/auth/login` work |
| Announcements endpoint | Public `/announcements/active` serves |
| Static pages (dashboard + replay) | `/app/` and friends all 200 |
| Admin login + `/admin/stats` | Admin creds work and the account is actually admin |
| Admin analytics overview | DAU / WAU / revenue queries succeed |
| Stripe configured *(optional)* | If `STARTUP_CHECK_EXPECT_STRIPE=1`, fails on 503 from `/shop/checkout/stripe` |

Exit code 0 = safe to proceed; 1 = something's wrong. Failures print exactly which check and why.

### 1g. Manual sanity (optional — if the script can't hit your env)

```bash
# 1. Liveness
curl -s https://your-domain/healthz
# → {"status":"ok","env":"prod","worker":{...}}

# 2. Worker tick is recent (last_tick_at within last ~2 min)
curl -s https://your-domain/worker/status

# 3. Metrics
curl -s https://your-domain/metrics | head -30

# 4. Content seeded
curl -s https://your-domain/stages | python -c "import sys,json; print(f'{len(json.load(sys.stdin))} stages')"

# 5. Admin analytics (after login)
TOKEN=$(curl -s -X POST https://your-domain/auth/login \
  -H 'content-type: application/json' \
  -d '{"email":"you@example.com","password":"..."}' | jq -r .access_token)
curl -s https://your-domain/admin/analytics/overview \
  -H "Authorization: Bearer $TOKEN" | jq
```

---

## Phase 2 — Client walkthrough

The `client_walkthrough.py` script registers a fresh account and exercises 13 feature sections back-to-back. Failing sections print what went wrong + which endpoint returned the unexpected status.

```bash
# Server must be running. Mock payments must be enabled for the shop leg.
HEROPROTO_MOCK_PAYMENTS_ENABLED=1 uv run uvicorn app.main:app &

# Local:
uv run python -m scripts.client_walkthrough

# Remote:
HEROPROTO_BASE=https://your-staging uv run python -m scripts.client_walkthrough
```

What it exercises, in order:

| # | Section | Validates |
|---:|---|---|
| 1 | Auth — register / login / refresh | `POST /auth/register`, `/login`, `/refresh` (with rotation) |
| 2 | `/me` + daily login bonus | Balances + `POST /me/daily-bonus/claim` returns day-1 reward |
| 3 | Gacha | `POST /summon/x10` returns 10 heroes, `/heroes/mine` lists them |
| 4 | Combat + replay | `POST /battles` → log+participants, `GET /battles/{id}` round-trips |
| 5 | Gem sink — energy refill | `POST /me/energy/refill` responds correctly (rejects fresh accounts, 409 vs 201) |
| 6 | Arena | `PUT /arena/defense`, `GET /arena/opponents`, `POST /arena/attack`, `/arena/matches/{id}` |
| 7 | Daily quests | `/daily` returns exactly 3 quests |
| 8 | Guilds | Create, member list, chat message round-trip |
| 9 | Raids | `/raids/start` (as guild leader), `/raids/{id}/attack` |
| 10 | Shop | `/shop/products` + mock purchase completes + grants currency |
| 11 | Password reset | `/auth/forgot-password` → `/auth/reset-password` + new password logs in |
| 12 | Email verification | `/auth/send-verification` → `/auth/verify-email` |
| 13 | 2FA (TOTP) | Enroll → confirm (10 recovery codes) → login returns challenge → verify |

All 13 must pass for the script to exit 0.

### 2a. UI smoke (visual-only, not scripted)

Open in a browser after the walkthrough passes:

- **Dashboard:** `https://your-domain/app/`
  - Every tab should load without errors: Me / Roster / Stages / Daily / Arena / Guild / Shop
  - Daily login bonus card should show on the Me tab with "Claim" button
  - Shop tab should list 6+ products with Buy buttons
- **Hero codex:** `https://your-domain/app/roster.html`
  - All 25 heroes visible as cards with portraits + rarity frames + faction badges
  - Filter chips work (All / faction / role)
- **Battle replay:** `https://your-domain/app/battle-replay.html?id=<battle-id>`
  - (battle-id from step 4 of the walkthrough)
  - Unit cards show portraits + status icons + HP bars
  - Combat log is filterable (All/Damage/Heal/Status/Deaths)
- **Battle Phaser:** `https://your-domain/app/battle-phaser.html?id=<battle-id>`
  - Canvas renders 2 teams with animated HP bars + floating damage numbers

### 2b. Manual admin sanity (optional)

After the walkthrough populates some data, admin endpoints become interesting:

```bash
# Signed in as admin:
curl -H "Authorization: Bearer $TOKEN" https://your-domain/admin/analytics/overview

# Expected non-zero: accounts_total, summons.total, battles.total, purchases.total
```

Post a public announcement so it's visible on every `/me`:

```bash
curl -X POST https://your-domain/admin/announcements \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Post-deploy test","body":"You are seeing this because the server is live.","priority":10,"duration_hours":1}'
```

---

## Continuous checks after deploy

**Alerts to watch** (see [`docs/RUNBOOK.md`](RUNBOOK.md#monitoring--alerting-hooks) for details):

- `/worker/status.last_tick_at` stale > 5 min → worker died
- `/worker/status.ticks_failed / ticks_total > 10%` → job crashes
- Purchase state = `FAILED` count spiking → Stripe or store logic regression
- 4xx/5xx spike on `/shop/webhooks/stripe` → webhook signing secret drift

**Repeat runs:**

- `startup_check.py` — on every deploy, and before handing an environment to a tester.
- `client_walkthrough.py` — nightly against staging; pre-ship on prod just before cutover. Not on every deploy (it creates a fresh account each time, so prod DBs accumulate test accounts if you aren't careful).

---

## When checks fail — diagnostic index

| Symptom | Likely cause | Fix |
|---|---|---|
| `/healthz` 500 | Startup `_check_secrets()` raised — weak JWT / prod w/ mock-payments / prod w/ console-email | Fix the flagged env var. **Don't** turn off the check. |
| `/worker/status.last_tick_at is null` | `worker_enabled=False` or the supervisor task died | Check logs for supervisor respawn; set `HEROPROTO_WORKER_ENABLED=1` if web-only was accidentally deployed |
| `/stages` returns `[]` | Seed didn't run | `uv run python -c "from app.seed import seed; seed()"` |
| Registration round-trip fails | DB isn't writable / migrations behind head | `uv run alembic current` + compare to `head`; check DB user has write grants |
| Admin endpoints 403 for the admin account | Email not in `HEROPROTO_ADMIN_EMAILS` and hasn't been CLI-promoted | `uv run python -m app.admin promote you@example.com` |
| Shop purchase 403 | `HEROPROTO_MOCK_PAYMENTS_ENABLED` unset (dev) OR `HEROPROTO_STRIPE_API_KEY` unset (prod) | Set the appropriate env var |
| 2FA verify fails with "invalid TOTP" | Client clock drift vs server > 30s | Check clock sync on the client and the server |
| Stripe webhook 400 "invalid signature" | `HEROPROTO_STRIPE_WEBHOOK_SECRET` doesn't match the secret Stripe issued | Re-copy from Stripe dashboard (or output of `stripe listen` in dev) |
| Rate-limited on the walkthrough | Default rate limit hits in sequence | `HEROPROTO_RATE_LIMIT_DISABLED=1` for the test window |

---

## Summary

- **Admin (automated):** `uv run python -m scripts.startup_check` → exit 0 means the server is verified
- **Client (automated):** `HEROPROTO_MOCK_PAYMENTS_ENABLED=1 uv run python -m scripts.client_walkthrough` → exit 0 means every feature round-trips
- **Visual:** open `/app/` and `/app/roster.html` and click around

If all three green, you're cleared to hand the URL to testers.
