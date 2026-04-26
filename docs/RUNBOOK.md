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

### Back up the database

```bash
# SQLite: auto-detects the path from HEROPROTO_DATABASE_URL and writes a
# gzipped snapshot to ./backups/ (override with BACKUP_DIR). Keeps the
# newest 14 backups (override with RETAIN).
bash scripts/backup_db.sh

# Postgres works the same; the script shells out to pg_dump in custom
# format. Requires pg_dump on PATH.
HEROPROTO_DATABASE_URL=postgresql+psycopg://user:pw@host/db \
  bash scripts/backup_db.sh
```

Scheduling (cron example — daily at 3 AM UTC):

```cron
0 3 * * *  cd /app && HEROPROTO_DATABASE_URL=... bash scripts/backup_db.sh >> /var/log/heroproto-backup.log 2>&1
```

Output files are named `hero-proto-<UTC timestamp>.(db.gz|dump)` so `ls -1` sorts chronologically. Retention prunes the oldest beyond `RETAIN`.

### Graceful shutdown

Send SIGTERM to the uvicorn process. FastAPI waits for in-flight HTTP requests to finish, then the `lifespan` context cancels the worker task and awaits its `CancelledError`. No special action needed — `docker stop`, `systemctl stop`, and `kubectl delete` all send SIGTERM.

**uvicorn flags worth setting in prod:**
- `--timeout-graceful-shutdown 30` — wait up to 30s for in-flight requests to drain. Default is no timeout (waits forever, which orchestrators kill via SIGKILL anyway).
- `--timeout-keep-alive 5` — drop idle keep-alive connections after 5s of silence. Speeds shutdown.

What's actually in flight to worry about:
- A `/battles` POST writing the Battle row — short, ~50–200ms.
- A `/me/export` GDPR dump — multi-second on accounts with full history. The 1/min rate limit caps blast radius.
- A `/raids/{id}/attack` resolving combat against a shared boss HP pool — short.
- The worker's tick (raid auto-rotate, expired raids, daily prune) — handled by the `CancelledError` path; in-flight DB writes commit before the next `await`.

If shutdown logs mention "active connections remaining," raise `--timeout-graceful-shutdown` to 60s. If it persists, check `/worker/status` for stuck ticks before restarting.

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

Each entry has a threshold tuned for the alpha workload — adjust as traffic grows. Severity tags map to: **page** = wake oncall, **ticket** = next-business-day investigation, **info** = dashboard signal only.

1. **5xx error rate.** [page]
   Threshold: `5xx_rate / total_rate > 0.02` sustained over 5 minutes. Anything above 2% is broken — rate-limit 429s and auth 401s don't count (they're 4xx).
   PromQL:
   ```
   sum(rate(requests_total{status=~"5.."}[5m]))
     /
   sum(rate(requests_total[5m])) > 0.02
   ```

2. **p99 latency.** [ticket]
   Threshold: `p99(request_duration_seconds) > 1.5s` sustained over 10 minutes for any path. /battles and /raids/<id>/attack should be < 500ms p99 on warm cache; /me/export can spike higher (capped by its 1/min rate limit).
   PromQL:
   ```
   histogram_quantile(0.99,
     sum by (le, path) (rate(request_duration_seconds_bucket[5m]))
   ) > 1.5
   ```

3. **Worker tick stalled.** [page]
   Threshold: `worker.last_tick_at` older than 5 minutes. The worker ticks every 60s; 5+ minutes without one means the supervisor couldn't revive it or the process is deadlocked. Alert source: `/worker/status`, not Prometheus.

4. **Worker tick failure rate.** [ticket]
   Threshold: `worker.ticks_failed / worker.ticks_total > 0.10` over a 15-minute window. Source: `/worker/status` JSON. A handful of failures during a deploy is fine; sustained means the tick logic is throwing.

5. **Rate-limit 429 burst.** [info → ticket if sustained]
   Threshold: `rate_429 > 1/s` sustained over 10 minutes from a single IP/account is suspicious; spread across many keys is just a popular hour. Sustained means real abuse — investigate which bucket is firing (battle / arena / DM / friend-request / data-export / guild-chat-IP).
   PromQL:
   ```
   sum by (path) (rate(requests_total{status="429"}[5m])) > 1
   ```

6. **Purchase failures.** [ticket]
   Threshold: > 5 failed purchases per hour or > 10% of purchase attempts. Common cause: stale Stripe price ID, network hiccup with Stripe API, or webhook signing secret out of sync.
   ```sql
   SELECT count(*) FROM purchases
   WHERE state='FAILED' AND created_at > now() - interval '1 hour';
   ```

7. **Stripe webhook signature failures.** [page if sustained]
   Threshold: any sustained 400 rate on `/shop/webhooks/stripe`. Stripe retries with exponential backoff for ~3 days; a stale signing secret will burn through that quickly.
   PromQL:
   ```
   sum(rate(requests_total{path="/shop/webhooks/stripe",status="400"}[15m])) > 0
   ```

8. **Access-token revocation spikes.** [info]
   Threshold: 401-from-`/me` rate > 10× baseline for 15+ minutes. Unusual spike may indicate a password-reset storm, mass-ban event, or session-token theft.

9. **Battle throughput drop.** [info]
   Threshold: `battles_total` 5-minute rate falls > 80% off its weekly trailing average during peak hours. Useful for spotting silent regressions where battles still 200 but the route is broken further down.

10. **Refresh-token fingerprint mismatch rate.** [info → page if sustained]
    Threshold: `refresh_token_anomaly_total` rising at > 5/min sustained over 15 minutes is a token-theft signal. Single events are noisy (legit users roam between wifi and tether all the time, browsers update UAs); a sustained burst from a population of accounts is the actual signal. Cross-reference the structured `auth.refresh` warning logs by `account_id` to see whether one account is hot or many are.
    PromQL:
    ```
    rate(refresh_token_anomaly_total[5m]) > (5 / 60)
    ```

### PromQL cookbook

Copy-paste-ready queries for common Grafana panels.

| What you want to see | Query |
|---|---|
| Request rate (req/s) | `sum(rate(requests_total[1m]))` |
| Error rate (%) | `100 * sum(rate(requests_total{status=~"5.."}[5m])) / sum(rate(requests_total[5m]))` |
| Latency p50 / p95 / p99 (s) | `histogram_quantile(0.<N>, sum by (le) (rate(request_duration_seconds_bucket[5m])))` |
| Latency by path (p99) | `histogram_quantile(0.99, sum by (le, path) (rate(request_duration_seconds_bucket[5m])))` |
| Top 10 slowest paths | `topk(10, histogram_quantile(0.95, sum by (le, path) (rate(request_duration_seconds_bucket[5m]))))` |
| Battles per minute | `60 * rate(battles_total[5m])` |
| Summons per minute | `60 * rate(summons_total[5m])` |
| Status mix over time | `sum by (status) (rate(requests_total[1m]))` |
| 429s by path | `sum by (path) (rate(requests_total{status="429"}[5m]))` |
| Auth failures (401 on auth paths) | `sum(rate(requests_total{path=~"/auth/.*",status="401"}[5m]))` |
| Active in-flight (estimate) | `sum(rate(requests_total[1m])) * histogram_quantile(0.50, sum by (le) (rate(request_duration_seconds_bucket[5m])))` |
| Refresh-token fingerprint anomalies (per min) | `60 * rate(refresh_token_anomaly_total[5m])` |

### Dashboard layout

Recommended Grafana dashboard rows (top → bottom). Screenshots TBD — capture once a real prod instance is running with non-trivial traffic.

1. **Pulse** — request rate, error rate %, p99 latency (3 stat panels).
2. **Latency** — p50/p95/p99 over time (line graph), top 10 slowest paths (bar).
3. **Status mix** — `requests_total` rate by status code (stacked area).
4. **Game activity** — battles/min, summons/min, arena attacks/min (3 line panels).
5. **Worker** — last tick age, tick failure ratio, ticks total counter (3 stat panels reading from `/worker/status` via a JSON datasource).
6. **Rate limits** — 429s by path stacked over time.
7. **Payments** — purchase rate by state (stacked area), webhook 400s if any.

### Log lines worth tagging

All logs include `X-Request-ID` (generated if absent, echoed on response). Grep on that ID to stitch a request's lifecycle across log lines.

Structured logs (`HEROPROTO_JSON_LOGS=1`) emit JSON with `request_id` + `account_id` (when available) + `method` + `path` + `status` + `duration_ms`. Point Datadog / CloudWatch / whatever at them.

---

## Analytics (PostHog)

Product-analytics events flow through `app/analytics.py` → posthog-python → a self-hosted (or PostHog Cloud) PostHog project. The wrapper is graceful — if no API key is set or the dep isn't installed, every `track()` call is a silent no-op.

### Configuration

```sh
HEROPROTO_POSTHOG_API_KEY=phc_<your project key>
HEROPROTO_POSTHOG_HOST=https://app.posthog.com   # or your self-hosted URL
HEROPROTO_POSTHOG_DISABLED=0                      # set to 1 to kill-switch
```

The runtime client is an **optional dep** behind the `analytics-runtime` extra:

```sh
uv sync --extra analytics-runtime
```

If the key is set but the dep is missing, the wrapper logs a single warning at startup and stays no-op — no crashes, no per-request log spam.

### The 12 instrumented events

Each event uses `account_id` (stringified) as the PostHog `distinct_id`. All events carry baseline properties: `env`, `request_id`. Event-specific properties below.

| Event | Where | Properties |
|---|---|---|
| `register` | `POST /auth/register` | `email_domain` |
| `login` | `POST /auth/login` | `method` (`password` / `password+2fa`), `stage` (`challenge` for 2FA leg) |
| `summon_x1` | `POST /summon/x1` | `rarity`, `epic_pity_triggered` |
| `summon_x10` | `POST /summon/x10` | `best_rarity`, `rarity_counts` (per-rarity histogram), `epic_pity_triggered` |
| `stage_start` | `POST /battles` after energy/auth checks | `stage_id`, `stage_code`, `stage_order`, `team_size` |
| `stage_clear` | `POST /battles` after resolution | `stage_id`, `stage_code`, `outcome`, `won`, `ticks` |
| `first_clear` | `POST /battles` when first-time stage clear | `stage_id`, `stage_code`, `stage_order` |
| `arena_attack` | `POST /arena/attack` | `outcome`, `won`, `rating_delta`, `rating_after` |
| `raid_attack` | `POST /raids/{id}/attack` | `raid_id`, `tier`, `damage_dealt`, `boss_defeated`, `boss_remaining_pct` |
| `purchase_start` | Right before `purchase_complete` | `sku`, `processor` (`mock`/`apple`/`google`), `price_cents` |
| `purchase_complete` | After `state=COMPLETED` | `sku`, `processor`, `price_cents`, `currency` |
| `daily_bonus_claim` | `POST /me/daily-bonus/claim` | `streak_after`, `was_reset` |

### Funnels worth building

Set these up in PostHog (Insights → New funnel) — they're the Phase 2 acceptance-criteria funnels.

1. **First-purchase funnel.** `register` → first `stage_clear` (won=true) → first `purchase_complete`. Conversion windows: 24h, 7d, 30d.
2. **First-fight funnel.** `register` → first `stage_start` → first `stage_clear`. Catches drop-off in the tutorial flow.
3. **Pull-to-battle funnel.** `register` → first `summon_x1` OR `summon_x10` → first `stage_start`. Surfaces players who pull but never fight.
4. **Daily-engagement.** `daily_bonus_claim` count per account per day, plotted as a histogram. Targets the retention loop.

### Dashboards

Recommended PostHog dashboard rows:
1. **DAU / WAU** (line): unique `distinct_id` per day on any event.
2. **Conversion**: stacked bar, `register` count vs `purchase_complete` count per week.
3. **Pull behavior**: `summon_x1` vs `summon_x10` rate, plus distribution of `summon_x10` `best_rarity` values.
4. **Stage progression**: `first_clear` count grouped by `stage_order` — shows where players plateau.
5. **Arena activity**: `arena_attack` count per day, `won` rate.
6. **Raid activity**: `raid_attack` per day, average `damage_dealt`, `boss_defeated` rate.
7. **Revenue**: `purchase_complete` count by `processor`, sum of `price_cents` per day.

### Self-hosted deploy notes

- PostHog ships an official `docker-compose.yml`. Run it on its own host (Postgres + Redis + ClickHouse — heavier than hero-proto itself).
- Behind your own TLS terminator. The product is fine on a single 4-CPU box for alpha-scale traffic; scale ClickHouse first if you outgrow.
- Set `HEROPROTO_POSTHOG_HOST` to that host's URL (https://posthog.your-domain.com); leave the default for PostHog Cloud.
- The posthog-python client batches + flushes async (default 1Hz / 100-event batches). The hero-proto lifespan calls `analytics.shutdown()` on graceful stop so the last batch isn't lost — see `app/main.py`.

### Operational notes

- **Test environment is hard-disabled.** `settings.environment == "test"` short-circuits before client init, so no synthetic traffic from the test suite reaches the project. No PII filter to think about; nothing is sent.
- **CI / load tests:** set `HEROPROTO_POSTHOG_DISABLED=1` even if the key happens to be set in the env. Belt-and-suspenders.
- **Anomaly counter:** Prometheus metric `refresh_token_anomaly_total` already alerts on session-token mismatches; PostHog's `login` events can be cross-referenced on `account_id` if you want to spot the human side of those alerts.
- **Failure mode:** all `track()` calls are wrapped — exceptions from posthog-python are logged at WARNING and swallowed. A broken PostHog never 500s the API.

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
