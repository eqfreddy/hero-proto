# hero-proto cheat sheet

Quick reference for running, deploying, admin'ing, and unsticking this thing.
**Last updated:** 2026-04-29

---

## 🌐 Live URLs

| Where | URL | Notes |
|---|---|---|
| Production app | https://hero-proto.fly.dev | Fly.io deploy |
| Production SPA | https://hero-proto.fly.dev/app/me | After login |
| Marketing site | https://hero-proto.fly.dev/ | Privacy, terms, etc. |
| Privacy policy | https://hero-proto.fly.dev/privacy | Marketing version (full legal) |
| Terms | https://hero-proto.fly.dev/terms | |
| Admin panel | https://hero-proto.fly.dev/app/admin | Vanilla JS — gates on `is_admin`. 2FA required outside test env. |
| Healthcheck | https://hero-proto.fly.dev/healthz | Returns `{ ok: true }` |
| Metrics | https://hero-proto.fly.dev/metrics | Prometheus exposition |
| API docs | https://hero-proto.fly.dev/docs | FastAPI Swagger UI |
| Local dev | http://localhost:8000 | `uv run uvicorn app.main:app --reload` |
| Android emu → host | http://10.0.2.2:8000 | Special emulator alias |

---

## 🚀 Server lifecycle (Fly.io)

```bash
# Deploy current branch — builds Dockerfile, pushes image, rolls one machine at a time
fly deploy

# Deploy without confirmation prompts
fly deploy --yes

# Force-roll the live machine (no code change — picks up env var changes)
fly machine restart -a hero-proto

# Quick status (machines, regions, health)
fly status
fly machine list

# Tail logs (Ctrl-C to exit)
fly logs

# Filter logs (last 100 lines, only errors)
fly logs | grep -i "error\|exception\|traceback"

# SSH into the running machine
fly ssh console
fly ssh console -C "ls -la /data"        # one-shot command

# Scale up to keep it always warm (kills cold-start latency, costs more)
fly scale count 1 --max-per-region 1

# Scale to zero (default — auto-stops after idle, cold start on next request)
fly scale count 0

# Roll back to previous release if a deploy goes bad
fly releases
fly releases rollback <version>
```

### Secrets

```bash
# List configured secrets (names only — values never shown)
fly secrets list

# Set a single secret (triggers a rolling restart)
fly secrets set HEROPROTO_JWT_SECRET="$(openssl rand -base64 48)"

# Set multiple at once
fly secrets set \
  HEROPROTO_JWT_SECRET="..." \
  HEROPROTO_CORS_ORIGINS="https://hero-proto.fly.dev"

# Stage secrets without restarting (apply later with `fly deploy`)
fly secrets set --stage HEROPROTO_X="..."

# Unset a secret
fly secrets unset HEROPROTO_X
```

### Database (Postgres on Fly)

```bash
# Connect with psql
fly postgres connect -a hero-proto-db

# One-off query
fly postgres connect -a hero-proto-db -c "SELECT count(*) FROM accounts;"

# Backup (manual — there's also automated daily via scripts/backup_db.sh)
fly ssh console -C "pg_dump $DATABASE_URL -Fc -f /tmp/backup.dump"
fly ssh sftp get /tmp/backup.dump ./hero-proto-$(date +%F).dump

# Re-attach DB to app (in case DATABASE_URL gets lost)
fly postgres attach hero-proto-db -a hero-proto
```

---

## 🛠️ Local dev

```bash
# Install deps
uv sync

# Run server (auto-reload)
uv run uvicorn app.main:app --reload

# Migrations
uv run alembic current                              # show current head
uv run alembic upgrade head                         # apply all pending
uv run alembic downgrade -1                         # roll back one
uv run alembic history --verbose                    # full history
uv run alembic revision --autogenerate -m "msg"     # auto-generate from model diffs

# Reset database (DEV ONLY — wipes everything)
rm hero-proto.db && uv run alembic upgrade head

# Frontend
npm install --prefix frontend
npm run dev --prefix frontend                       # vite dev server (proxies /api → localhost:8000)
npm run build --prefix frontend                     # production build → app/static/spa/

# Run admin CLI for local DB ops
uv run python -m app.admin --help

# Seed demo data
uv run python scripts/seed_demo.py
```

### Mobile

```bash
# Sync SPA → Android (after rebuilding frontend)
cd mobile && npx cap sync android

# Open in Android Studio
cd mobile && npx cap open android

# Production Android build (writes prod API URL into bundle, swaps configs)
bash mobile/build-prod-android.sh
# Then: Android Studio → Build → Generate Signed Bundle / APK
```

---

## 🧪 Testing

```bash
# Backend full suite
uv run pytest

# Quiet mode (just dots)
uv run pytest -q

# Single file
uv run pytest tests/test_named_gear.py -v

# Match a name
uv run pytest -k "alignment" -v

# Stop on first failure, drop to debugger
uv run pytest -x --pdb

# Frontend tests (vitest)
cd frontend && npx vitest run                       # one-shot
cd frontend && npx vitest                           # watch mode
cd frontend && npx vitest --coverage                # with coverage

# Acceptance scripts (E2E smoke)
uv run python scripts/startup_check.py              # admin/operator health
uv run python scripts/client_walkthrough.py         # 17-section feature tour

# Postgres compose stack smoke (needs Docker daemon up)
bash scripts/postgres_stack_validate.sh
```

---

## 👑 Admin panel & endpoints

The web UI is at `/app/admin` (vanilla JS, gates on `is_admin`). All admin endpoints are also callable via `curl` with a JWT.

### Admin auth

- `is_admin` flag must be `true` on the account row
- 2FA (TOTP) **required** in prod (skipped in `HEROPROTO_ENVIRONMENT=test`)
- `HEROPROTO_SUPERADMIN_EMAILS` (comma-separated) auto-promote on register
- Regular admins **cannot** act on superadmins (403 guard in `_guard_superadmin_target`)

### Granting yourself admin from prod

```bash
# Open psql via Fly
fly postgres connect -a hero-proto-db

# Promote
UPDATE accounts SET is_admin = true WHERE email = 'ridler69@gmail.com';

# Or superadmin (immune to demote)
UPDATE accounts SET is_admin = true, is_superadmin = true WHERE email = 'ridler69@gmail.com';
```

### Admin endpoints (cheat sheet)

| Method | Path | What |
|---|---|---|
| GET | `/admin/accounts` | List all accounts |
| GET | `/admin/accounts/{id}` | One account, full detail |
| POST | `/admin/accounts/{id}/grant` | Body: `{gems, shards, coins, hero_template_id, …}` |
| POST | `/admin/accounts/{id}/ban` | Body: `{reason, until?}`. Bumps token_version → kills active JWTs |
| POST | `/admin/accounts/{id}/unban` | |
| POST | `/admin/accounts/{id}/promote` | superadmin-only: makes target an admin |
| POST | `/admin/accounts/{id}/demote` | superadmin-only |
| GET | `/admin/stats` | Prom-friendly counters: accounts, battles, summons, GMV |
| GET | `/admin/audit?action=ban&actor_id=42&limit=50` | Action log |
| GET | `/admin/purchases` | Paginated purchase ledger |
| POST | `/admin/purchases/{id}/refund` | Reverses currency grants + flags purchase REFUNDED |
| POST | `/admin/liveops` | Body: `{kind, name, multiplier, starts_at?, ends_at}` |
| DELETE | `/admin/liveops/{id}` | Cancel an event |
| GET | `/admin/analytics/overview` | DAU/MAU, retention, revenue buckets |
| GET | `/admin/push/status` | Returns `{fcm: bool, apns: bool}` — secrets sanity check |
| POST | `/admin/push/test` | Body: `{title, body}` — fires a real push to YOUR registered devices |

### Curl recipes

```bash
# Get a JWT (admin user)
TOKEN=$(curl -s -X POST https://hero-proto.fly.dev/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"ridler69@gmail.com","password":"…"}' | jq -r .access_token)

# Push status check
curl -H "Authorization: Bearer $TOKEN" \
  https://hero-proto.fly.dev/admin/push/status

# Ban a cheater
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"reason":"automated combat bot","until":null}' \
  https://hero-proto.fly.dev/admin/accounts/123/ban

# Grant yourself test currency
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"gems":10000,"shards":1000,"access_cards":50}' \
  https://hero-proto.fly.dev/admin/accounts/1/grant

# Schedule an event (1 hour DOUBLE_REWARDS starting now)
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"kind":"DOUBLE_REWARDS","name":"Weekend Boost","multiplier":2.0,"ends_at":"2026-05-01T00:00:00Z"}' \
  https://hero-proto.fly.dev/admin/liveops

# Last 50 audit entries
curl -H "Authorization: Bearer $TOKEN" \
  "https://hero-proto.fly.dev/admin/audit?limit=50" | jq
```

---

## 🔑 Environment variables (the ones that matter)

All read at startup with `HEROPROTO_` prefix. Set via `fly secrets set` in prod or `.env` locally.

| Var | Required | What |
|---|---|---|
| `HEROPROTO_JWT_SECRET` | ✅ prod | 48+ random bytes. **Rotating logs out everyone.** |
| `HEROPROTO_DATABASE_URL` | ✅ | Set automatically by `fly postgres attach`. SQLite in dev. |
| `HEROPROTO_CORS_ORIGINS` | ✅ prod | Comma-separated. Add your custom domain here. |
| `HEROPROTO_PUBLIC_BASE_URL` | ✅ prod | Used for password reset / verify links in emails. |
| `HEROPROTO_ADMIN_EMAILS` | ✅ prod | Comma-separated. Auto-promote on register. |
| `HEROPROTO_SUPERADMIN_EMAILS` | ✅ prod | Comma-separated. Untouchable by regular admins. |
| `HEROPROTO_ENVIRONMENT` | | `prod` / `dev` / `test`. `test` bypasses 2FA + email verify. |
| `HEROPROTO_EMAIL_*` | recommended | SMTP creds (Postmark/Mailgun/SES). Without these, emails go to console. |
| `HEROPROTO_STRIPE_API_KEY` | for live $$$ | `sk_live_…`. Without it, mock-payments path is used. |
| `HEROPROTO_STRIPE_WEBHOOK_SECRET` | for live $$$ | `whsec_…` for verifying Stripe → us callbacks. |
| `HEROPROTO_TURNSTILE_SECRET_KEY` | recommended | Cloudflare Turnstile (CAPTCHA on register). |
| `HEROPROTO_TURNSTILE_SITE_KEY` | recommended | Public — set in `[env]` block of fly.toml, not as secret. |
| `HEROPROTO_SENTRY_DSN` | recommended | Error reporting. Without it, stack traces only hit Fly logs. |
| `HEROPROTO_OTEL_ENDPOINT` | optional | OTLP/gRPC collector for distributed tracing. |
| `HEROPROTO_POSTHOG_API_KEY` | optional | Analytics. Without, analytics is no-op. |
| `HEROPROTO_JSON_LOGS` | recommended prod | Set to `1` for structured logs Fly's parser likes. |
| `HEROPROTO_LOG_REQUESTS` | optional | Set to `true` to log every HTTP request. |
| `HEROPROTO_RATE_LIMIT_DISABLED` | dev only | Set to `true` to bypass all rate limits. |
| `HEROPROTO_MOCK_PAYMENTS_ENABLED` | dev only | Set to `false` in prod. |
| `HEROPROTO_WORKER_ENABLED` | ✅ prod | Background tasks: liveops scheduling, raid auto-rotate, retention sweeps. |
| `FCM_PROJECT_ID` | for push | Firebase project ID |
| `FCM_SERVICE_ACCOUNT_JSON` | for push | Full service account JSON (one line). |
| `APNS_KEY_ID` / `APNS_TEAM_ID` / `APNS_BUNDLE_ID` / `APNS_AUTH_KEY_PEM` | for iOS push | Apple Developer creds |

---

## 🚨 Incident playbook

### Server returning 500s

```bash
fly logs | grep -i "error\|traceback\|exception" | head -50

# Force restart the machine
fly machine restart -a hero-proto

# Last-resort rollback
fly releases
fly releases rollback <previous-version>
```

### "Login is broken / users can't log in"

1. Check `HEROPROTO_JWT_SECRET` is still set: `fly secrets list`
2. Check token_version vs JWT — was someone bulk-banned recently? `fly logs | grep "token_version"`
3. Check rate limiter: `curl https://hero-proto.fly.dev/healthz` should still 200

### "Push notifications not arriving"

```bash
# Verify provider config end-to-end (admin auth required)
curl -H "Authorization: Bearer $TOKEN" https://hero-proto.fly.dev/admin/push/status
# Expected: {"fcm": true, "apns": true, ...}

# Fire a test to your own device(s)
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"diag","body":"test"}' \
  https://hero-proto.fly.dev/admin/push/test
# Returns: {"sent": <n>, "providers": {...}}
```

If `sent > 0` but you don't get the push:
- FCM: check Firebase Console → Cloud Messaging → Reports
- APNs: check device permissions, check `APNS_SANDBOX` matches your build (sandbox=1 for dev/TestFlight)

### "Admin panel won't load"

- 2FA required in prod. Enroll at `/app/account` if you haven't.
- Bypass 2FA in test env with `HEROPROTO_ENVIRONMENT=test` (DO NOT do this in prod).

### Bulk-revoke all sessions (security incident)

```sql
-- Logs everyone out, including yourself
UPDATE accounts SET token_version = token_version + 1;
```

### Unstick the worker

```bash
# Worker logs
fly logs | grep -i "worker"

# If it's stalled, restart the machine
fly machine restart -a hero-proto

# Check worker health from API
curl https://hero-proto.fly.dev/worker/status
```

### Rate limiter went haywire

```bash
# Disable temporarily (DANGER — restore ASAP)
fly secrets set HEROPROTO_RATE_LIMIT_DISABLED=true
# Restore
fly secrets unset HEROPROTO_RATE_LIMIT_DISABLED
```

---

## 📦 Migrations

```bash
# Locally — auto-generate from model changes
uv run alembic revision --autogenerate -m "add_field_x"

# Always review the generated file before running. autogenerate misses:
#   - StrEnum value renames (use op.execute("UPDATE ..."))
#   - JSON column content shape changes
#   - Index renames

# Apply locally
uv run alembic upgrade head

# Apply on prod — runs automatically on `fly deploy` (entrypoint hook),
# but to run by hand:
fly ssh console
> uv run alembic upgrade head
```

### Migrations are at:
`alembic/versions/` — current head: `b2c3d4e5f6a7` (armor slots + named gear)

---

## 🎮 Game-specific cheats

```sql
-- Full inventory dump for a player
SELECT * FROM gear WHERE account_id = (SELECT id FROM accounts WHERE email = 'foo@bar.com');

-- Force a story chapter complete
UPDATE accounts SET stages_cleared_json = '["tutorial_first_ticket","onboarding_day","first_outage","quarterly_audit","legacy_server_room"]'
WHERE email = 'foo@bar.com';

-- Reset alignment so you can pick again
UPDATE accounts SET faction = 'EXILE', alignment_chosen_at = NULL WHERE id = 1;

-- Give a hero (template_id 5 = whatever)
INSERT INTO hero_instances (account_id, template_id, level, xp, stars, special_level)
VALUES (1, 5, 1, 0, 1, 1);

-- Scrub auto-team caches after a power formula change
UPDATE accounts SET defense_team_id = NULL;

-- Lift a ban without auditing it (ONLY in emergencies)
UPDATE accounts SET banned_until = NULL, banned_reason = NULL WHERE id = 123;
```

---

## 📚 Doc map

| File | What |
|---|---|
| `README.md` | Project intro + quickstart |
| `TODO.md` | Living list of work (phases shipped, sprints open, papercuts) |
| `CHEATSHEET.md` | This file |
| `docs/RUNBOOK.md` | Operator deep-dive: alerts, PromQL cookbook, Grafana layout |
| `docs/PRD.md` | Product requirements doc — phase planning |
| `docs/PHASE_2_HUMAN_TEST.md` | Phase 2 manual test script |
| `docs/PLAN_B_INTEGRATION.md` | DragonBones battle visuals integration spec |
| `docs/BATTLE_RIG_EVENT_MAPPING.md` | Combat event → animation map |
| `docs/BATTLE_VISUALS_STACK.md` | DragonBones stack overview |
| `fly.toml` | Fly.io deploy config (env + secrets template) |
| `codemagic.yaml` | iOS / Android cloud-build config |
| `.github/workflows/android-build.yml` | GitHub Actions Android pipeline |
| `.github/workflows/ios-build.yml` | GitHub Actions iOS pipeline |

---

## 🔗 External services

| Service | What | Where to log in |
|---|---|---|
| Fly.io | App hosting | https://fly.io/apps/hero-proto |
| Firebase | FCM (Android push) | https://console.firebase.google.com |
| Apple Developer | APNs key + iOS provisioning | https://developer.apple.com/account |
| Play Console | Android distribution | https://play.google.com/console |
| App Store Connect | iOS distribution | https://appstoreconnect.apple.com |
| Codemagic | iOS/Android cloud builds | https://codemagic.io |
| Stripe | Payments dashboard | https://dashboard.stripe.com |
| PostHog | Analytics | https://app.posthog.com |
| Sentry | Error reporting | https://sentry.io |
| Cloudflare Turnstile | CAPTCHA | https://dash.cloudflare.com → Turnstile |

---

## 🆘 If you only remember three things

```bash
fly logs                              # what's broken
fly deploy                            # ship a fix
fly releases rollback <previous>      # undo a bad ship
```
