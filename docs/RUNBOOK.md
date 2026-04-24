# hero-proto operator runbook

Everything a fresh operator needs to take this from clone to running-in-prod. If a step here is wrong or stale, fix it — this doc is load-bearing.

Contents:
1. [Quickstart (local dev)](#quickstart-local-dev)
2. [Environment variables](#environment-variables)
3. [First-time prod deploy checklist](#first-time-prod-deploy-checklist)
4. [Operational tasks](#operational-tasks)
5. [Monitoring + alerting hooks](#monitoring--alerting-hooks)
6. [Footguns](#footguns)

---

## Quickstart (local dev)

```bash
# Clone + install
git clone https://github.com/eqfreddy/hero-proto
cd hero-proto
uv sync --all-extras

# Run migrations + seed
uv run alembic upgrade head
uv run python -c "from app.seed import seed; seed()"

# Start the server
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000

# Hit it
curl http://127.0.0.1:8000/healthz
# → http://127.0.0.1:8000/app/ — dashboard
```

For a dev loop with looser limits and mock payments:

```bash
HEROPROTO_RATE_LIMIT_DISABLED=1 \
HEROPROTO_MOCK_PAYMENTS_ENABLED=1 \
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

Run tests:

```bash
uv run pytest tests/ -q            # SQLite, ~45s
HEROPROTO_DATABASE_URL="postgresql+psycopg://hero:heropw@localhost:5432/heroproto" \
  uv run pytest tests/ -q           # Postgres (same suite)
```

Run smokes against a live server:

```bash
uv run python -m scripts.smoke_api_core
uv run python -m scripts.smoke_shop
uv run python -m scripts.smoke_guild
# ... see scripts/ for all 16
```

---

## Environment variables

All prefixed `HEROPROTO_`. Defaults are dev-friendly; the asterisk (★) marks things you **must** set in prod.

### Core

| Var | Default | Notes |
|---|---|---|
| `ENVIRONMENT` | `dev` | Set to `prod` to enable strict-mode checks. |
| `DATABASE_URL` | `sqlite:///./hero-proto.db` ★ | Prod: `postgresql+psycopg://user:pw@host/db` |
| `CORS_ORIGINS` | `*` ★ | Prod: comma-separated list of your real origins. |
| `LOG_REQUESTS` | `true` | Per-request log line. |
| `JSON_LOGS` | `false` ★ | Prod: `true` for structured logs. |

### Auth / sessions

| Var | Default | Notes |
|---|---|---|
| `JWT_SECRET` | dev default ★ | Prod: 32+ random bytes. Server refuses to start with the default in prod. |
| `JWT_ALG` | `HS256` | |
| `JWT_TTL_MINUTES` | `1440` (24h) | Access token lifetime. |
| `REFRESH_TOKEN_TTL_DAYS` | `30` | |
| `ADMIN_EMAILS` | `""` | Comma-separated emails auto-promoted to admin on register/login. |

### Rate limits

| Var | Default | Notes |
|---|---|---|
| `AUTH_RATE_PER_MINUTE` | `60` | `/auth/*` per-IP. |
| `GENERAL_RATE_PER_MINUTE` | `600` | Everything else per-IP. |
| `RATE_LIMIT_DISABLED` | `false` | Dev convenience — **never true in prod**. |

### Email (password reset + verification)

| Var | Default | Notes |
|---|---|---|
| `EMAIL_SENDER_TYPE` | `console` ★ | Prod: `smtp`. Values: `console` / `file` / `smtp` / `disabled`. Server refuses prod start with console/disabled. |
| `EMAIL_FROM_ADDRESS` | `no-reply@hero-proto.local` ★ | |
| `EMAIL_FILE_PATH` | `./emails.log` | Only used when type=file. |
| `EMAIL_SMTP_HOST` | `""` | |
| `EMAIL_SMTP_PORT` | `587` | |
| `EMAIL_SMTP_USERNAME` | `""` | |
| `EMAIL_SMTP_PASSWORD` | `""` | |
| `EMAIL_SMTP_USE_TLS` | `true` | |
| `PUBLIC_BASE_URL` | `http://127.0.0.1:8000` ★ | Prefixed on reset/verify URLs. Prod: your real public URL. |

### Payments

| Var | Default | Notes |
|---|---|---|
| `MOCK_PAYMENTS_ENABLED` | `false` | Dev: `true` to skip Stripe. Server refuses prod start with this on. |
| `STRIPE_API_KEY` | `""` ★ | Prod: `sk_live_...`. Dev: `sk_test_...`. |
| `STRIPE_WEBHOOK_SECRET` | `""` ★ | `whsec_...` from Stripe dashboard or `stripe listen`. |
| `STRIPE_PUBLISHABLE_KEY` | `""` | Client-side only. |
| `STRIPE_SUCCESS_URL` | localhost | Where Stripe redirects after a successful checkout. |
| `STRIPE_CANCEL_URL` | localhost | |

See `docs/STRIPE_SETUP.md` for the full Stripe onboarding flow.

### Worker

| Var | Default | Notes |
|---|---|---|
| `WORKER_ENABLED` | `true` | Scaled deploy: run one worker instance, web-only instances set this to `false`. |

### Economy tuning

All these are safe to tune without migrations. Defaults are game-balanced.

| Var | Default |
|---|---|
| `ENERGY_CAP` | 100 |
| `ENERGY_REGEN_SECONDS` | 360 |
| `ENERGY_PER_BATTLE` | 5 |
| `ENERGY_REFILL_COST_GEMS` | 50 |
| `ENERGY_REFILL_MAX_PER_DAY` | 3 |
| `STARTER_SHARDS` / `STARTER_ENERGY` / `STARTER_COINS` | 10 / 100 / 500 |
| `ONBOARDING_BONUS_SHARDS` | 10 |
| `GACHA_PITY_THRESHOLD` | 50 |
| `XP_PER_BATTLE_WIN` / `_LOSS` | 60 / 15 |
| `LEVEL_CAP` | 30 |

---

## First-time prod deploy checklist

Copy/paste as-is. Tick each box.

### Infra

- [ ] **Postgres instance provisioned.** `DATABASE_URL` points at it. `psycopg[binary]` extras installed (`uv sync --all-extras`).
- [ ] **Domain + TLS termination.** HTTPS is mandatory — Stripe refuses webhooks over plain HTTP in live mode.
- [ ] **Outbound SMTP reachable** (or SES SMTP / Postmark / Mailgun credentials on hand).
- [ ] **Stripe account in live mode.** Products + Prices created per `docs/STRIPE_SETUP.md`; each seeded SKU has a `stripe_price_id` populated in the DB.

### Secrets

- [ ] `HEROPROTO_JWT_SECRET` — 32+ random bytes (`openssl rand -base64 48`).
- [ ] `HEROPROTO_STRIPE_API_KEY` — live key (`sk_live_...`).
- [ ] `HEROPROTO_STRIPE_WEBHOOK_SECRET` — from the webhook endpoint you configured in Stripe.
- [ ] `HEROPROTO_EMAIL_SMTP_PASSWORD` — from your email provider.

Rotating any of these is a regular ops task — no code changes needed.

### Settings

- [ ] `HEROPROTO_ENVIRONMENT=prod` — unlocks the secret-validation checks.
- [ ] `HEROPROTO_CORS_ORIGINS=https://your-domain.com` (comma-sep list, no `*`).
- [ ] `HEROPROTO_JSON_LOGS=1`.
- [ ] `HEROPROTO_MOCK_PAYMENTS_ENABLED=false` (the default — don't set to true).
- [ ] `HEROPROTO_RATE_LIMIT_DISABLED=false`.
- [ ] `HEROPROTO_EMAIL_SENDER_TYPE=smtp` + SMTP vars set.
- [ ] `HEROPROTO_PUBLIC_BASE_URL=https://your-domain.com`.

At startup, the server runs `_check_secrets()` and refuses to boot if any of the above is wrong. **If the process logs `RuntimeError: ... must be false in production` or similar, your config is unsafe — do not work around it.**

### First steps after deploy

1. **Run migrations.** Lifespan does this automatically on first boot. To verify:
   ```bash
   alembic current    # should print the latest revision id
   ```
2. **Seed content.** Heroes + stages + shop products + initial liveops:
   ```bash
   uv run python -c "from app.seed import seed; seed()"
   ```
   Idempotent — skips entries that already exist by code/sku.
3. **Create first admin.** Either:
   - Set `HEROPROTO_ADMIN_EMAILS=you@domain` before anyone registers — the first user with that email auto-promotes.
   - OR register normally, then promote from the CLI:
     ```bash
     uv run python -m app.admin promote you@domain
     ```
4. **Smoke test.** Hit `/healthz`, log in via the dashboard, buy a test-mode product (switch to test keys first), watch the webhook complete.
5. **Set up monitoring.** See next section.

---

## Operational tasks

### Promote someone to admin

```bash
uv run python -m app.admin promote user@example.com
```

### List current admins

```bash
uv run python -m app.admin list
```

### Revoke admin

```bash
uv run python -m app.admin demote former-admin@example.com
```

Demote bumps `token_version` so their existing JWTs die immediately.

### Ban an account (timed or permanent)

Via admin API:

```bash
# Permanent
curl -X POST https://.../admin/accounts/42/ban \
  -H "Authorization: Bearer <admin-jwt>" \
  -H "Content-Type: application/json" \
  -d '{"reason": "ToS violation"}'

# 24-hour timed ban
curl ... -d '{"reason": "cooler", "duration_hours": 24}'
```

Timed bans auto-clear via the worker. Ban also bumps `token_version` so existing sessions die.

### Refund a purchase

```bash
curl -X POST https://.../admin/purchases/<id>/refund \
  -H "Authorization: Bearer <admin-jwt>" \
  -d '{"reason": "chargeback"}'
```

Clawback clamps balances at zero — never pushes negative. Hero grants are *not* auto-revoked (manual CS call). The `PurchaseLedger` records every GRANT + REFUND for audit.

### Read audit log

```bash
curl https://.../admin/audit?limit=50 -H "Authorization: Bearer <admin-jwt>"
curl https://.../admin/audit?target_id=42 -H ...           # filter by target
curl https://.../admin/audit?action=ban -H ...             # filter by action
```

### Post a server-wide announcement

```bash
curl -X POST https://.../admin/announcements \
  -H "Authorization: Bearer <admin-jwt>" \
  -d '{"title": "Maintenance Thursday", "body": "Server down 8-9pm UTC", "priority": 50, "duration_hours": 48}'
```

Appears on every player's `/me` tab + `/announcements/active`. Priority ≥ 50 gets an "important" pill.

---

## Monitoring + alerting hooks

### Endpoints to scrape

| Endpoint | Purpose |
|---|---|
| `/healthz` | Liveness probe. Returns 200 always. Contains `worker.last_tick_at`. |
| `/worker/status` | Worker telemetry. Full health fields. Never 503s (don't cascade). |
| `/metrics` | Prometheus scrape target. Counters: `requests_total`, `battles_total`, `summons_total`. Histogram: `request_duration_seconds`. |

### Alerts worth configuring

1. **Worker tick stalled.** Alert if `worker.last_tick_at` is older than 5 minutes. The worker ticks every 60s; 5+ minutes without one means the supervisor couldn't revive it or the process is deadlocked.

2. **Tick failure rate.** Alert if `worker.ticks_failed / worker.ticks_total > 0.1` over a 15-minute window.

3. **Purchase failures.** Prometheus: `sum(rate(...))` for failed purchase states. You can also query the DB directly: `SELECT count(*) FROM purchases WHERE state='FAILED' AND created_at > now() - interval '1 hour'`.

4. **Stripe webhook signature failures.** The handler returns 400 for bad signatures. Stripe will retry; a sustained 400 rate on `/shop/webhooks/stripe` usually means the signing secret is stale.

5. **Access token revocation spikes.** Unusual spike in 401s from `/me` (token revoked message) may indicate a password-reset storm or token theft.

### Log lines worth tagging

All logs include `X-Request-ID` (generated if absent, echoed on response). Grep on that ID to stitch a request's lifecycle across log lines.

Structured logs (`HEROPROTO_JSON_LOGS=1`) emit JSON with `request_id` + `account_id` (when available) + `method` + `path` + `status` + `duration_ms`. Point Datadog / CloudWatch / whatever at them.

---

## Footguns

Real issues we've hit; worth internalizing.

### "The design AI said it pushed files"

Web Claude's GitHub connector is **read-only**. If a design-oriented Claude session reports "I've pushed the files," they probably haven't — their sandbox write is not your disk. Always verify via `git pull` + `ls`. If nothing landed, have them paste the file contents as text and use Claude Code (filesystem + git) to save + commit.

### "Stripe webhook works in dev but not prod"

Each call to `stripe listen` generates a new signing secret. `HEROPROTO_STRIPE_WEBHOOK_SECRET` in dev must match whatever the listener printed. In prod, the secret comes from the webhook endpoint you configured in the Stripe dashboard — different secret per endpoint, and it rotates when you regenerate it there.

### "New account didn't get the seeded heroes"

`/auth/register` creates an Account but doesn't grant heroes — the player summons for heroes with shards. New accounts get `starter_shards + onboarding_bonus_shards` (20 by default), which is enough for exactly one x10 summon. If you need to grant heroes to a specific account:

```bash
curl -X POST https://.../admin/accounts/42/grant \
  -H "Authorization: Bearer <admin-jwt>" \
  -d '{"hero_template_code": "keymaster_gary"}'
```

### "Banned user's token still works"

Not anymore. Bans bump `token_version` which invalidates all outstanding JWTs immediately. If you see a ban-then-valid-token-works flow, check your deps chain — `deps.get_current_account` compares tv on every request. A stale `token_version` check would be the bug.

### "We can't run the full smoke suite against one IP"

Dev rate limits were tight enough to trip the 10-smoke sequential run. Set `HEROPROTO_RATE_LIMIT_DISABLED=1` for local smoke runs. **Never enable this in prod** — it removes the per-IP abuse protection.

### "Tests pass but Postgres CI fails"

Check the autogenerated migration for `batch_alter_table` or `server_default` mishaps. Every ALTER COLUMN that adds a NOT NULL column needs an explicit `server_default` or existing rows fail to backfill. The CI job catches this but it's a fast way to break things.

### "Daily quest claim reward fields are zero"

`DailyQuest.reward_*` fields are set at roll time from the `TEMPLATES` list in `app/daily.py`. If you added a new `DailyQuestKind` and didn't update the templates, the quest rolls but pays nothing. There's no server-side validator for "kind in TEMPLATES" — silent footgun.

### "Worker didn't auto-rotate raids even though cooldown passed"

Check:
- The guild actually has ≥1 member (empty guilds skipped).
- No other raid is ACTIVE for that guild.
- Most recent raid's `ends_at + 6h < now`.
- There exist EPIC/LEGENDARY hero templates to pick from.

All four conditions are gated. Look at the worker log line for "auto-rotated N raids" to confirm it ran at all.
