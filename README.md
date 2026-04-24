# hero-proto

Gacha + turn-based team combat RPG backend. IT-themed heroes (ticket gremlins, oncall warriors, shadow-IT operators) fight through outage/audit/migration stages. FastAPI + SQLAlchemy + Alembic on Python 3.13.

**Status:** working alpha. 224 unit tests + 16 E2E smoke scripts. Postgres CI on every push. Full F2P surface (accounts, gacha, arena, guilds, raids, store with Stripe, admin tools, observability). No art yet.

```bash
uv sync --all-extras
uv run alembic upgrade head
uv run python -c "from app.seed import seed; seed()"
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
# → http://127.0.0.1:8000/app/   (dashboard)
# → http://127.0.0.1:8000/docs    (OpenAPI)
```

Full operator docs: **[`docs/RUNBOOK.md`](docs/RUNBOOK.md)**.

---

## Feature surface

Every endpoint below is covered by either unit tests or an end-to-end smoke script; most by both.

### Auth (Sprint E complete)
- `POST /auth/register` / `/login` — bcrypt password, JWT access + refresh
- `POST /auth/refresh` — rotates with reuse-detection (theft signal revokes the chain)
- `POST /auth/logout` — revoke refresh
- `POST /auth/forgot-password` + `/reset-password` — enumeration-resistant, hashed single-use tokens, 1h TTL
- `POST /auth/send-verification` + `/verify-email` — 48h TTL, staged `get_current_account_verified_only` dep for future gating
- `POST /auth/2fa/enroll`, `/confirm`, `/verify`, `/disable`, `/regenerate-codes`, `/status` — TOTP (RFC 6238) with 10 single-use recovery codes at enrollment. Login auto-issues a 5-min challenge JWT when 2FA is on.

### Gameplay
- `GET /me`, `DELETE /me` (GDPR-grade cascades verified against 20+ tables)
- `POST /summon`, `POST /summon/x10` — pity at 50 pulls
- `GET /heroes/mine`, `/heroes/templates`, `/heroes/{id}/skill_up`, `/heroes/{id}/ascend`
- `GET /stages` (with difficulty_tier + requires_code for locked hard-mode)
- `POST /battles` — full combat log + participants roster returned; gated on HARD-mode prereqs
- `POST /battles/sweep/{id}` — instant-replay cleared stages
- `GET /battles/{id}` — replay any completed fight
- `GET /gear/mine`, `POST /gear/{id}/equip|unequip` — 6 slots, 4 sets (passive + active)
- `POST /me/energy/refill` — gem sink (50 💎, capped 3/day)
- `POST /me/daily-bonus/claim` — 7-day login cycle with premium day-7 payout

### Social
- `GET /arena/opponents` — rating-proximity matchmaking with recent-attack cooldown
- `POST /arena/attack` — full replay stored, `GET /arena/matches/{id}` replays it
- `PUT /arena/defense`, `GET /arena/leaderboard`
- `POST /guilds` — create; `/join`, `/leave`, `/kick`, `/promote`, `/demote`, `/transfer`, application flow with `/apply`, `/applications`, `/applications/{id}/accept|reject`, self `DELETE` to withdraw
- `GET|POST /guilds/{id}/messages` with `?before=<id>` keyset pagination
- `POST /raids/start` (T1/T2/T3 tiers), `/attack`, `GET /raids/mine` — auto-rotated by the worker when cooldown elapses

### Live ops
- `GET /liveops/active`, `/scheduled?horizon_days=7`
- `GET /announcements/active` — server-wide MOTD
- `GET /daily` + `/daily/{id}/claim` — 7 quest kinds including hard-stage clears, raid damage, gem spend

### Monetisation
- `GET /shop/products` — catalog with time windows + per-account limits
- `POST /shop/purchases` — mock processor (dev-gated)
- `POST /shop/checkout/stripe` + `POST /shop/webhooks/stripe` — real Stripe checkout session + signed webhook
- Dual reward ledger (`PurchaseLedger`) tracks every GRANT + REFUND for chargeback reconciliation

### Admin
- `GET|POST /admin/accounts`, grant, ban (with duration), unban, promote
- `GET /admin/audit` — filterable admin action log
- `GET|POST /admin/purchases`, `/{id}/refund` — refund clamps balances at zero
- `POST /admin/liveops` — create with optional future `starts_at` + duration
- `POST /admin/announcements` — schedulable, priority-sorted, time-windowed
- CLI: `python -m app.admin promote|demote|list|audit`

### Operations
- `/healthz` — liveness + worker telemetry
- `/worker/status` — full tick/restart/error counters (supervised with respawn)
- `/metrics` — Prometheus counters + request duration histogram
- Structured JSON logs with per-request X-Request-ID correlation

### Frontend
- HTMX-driven dashboard at `/app/` — 7 tabs with full interactivity
- Phaser 3 battle replay at `/app/battle-phaser.html?id=N`
- Design-handoff HTML replay + setup + roster pages (`/app/battle-{replay,setup}.html`, `/app/roster.html`)

---

## Architecture

```
app/
├── main.py              # FastAPI + lifespan (migrations, secret check, worker supervisor)
├── config.py            # pydantic-settings (HEROPROTO_* env vars — see RUNBOOK.md)
├── db.py                # SQLAlchemy engine + SQLite FK-enforcement listener
├── models.py            # all tables (Account, HeroInstance, Battle, Purchase, ...)
├── schemas.py           # pydantic I/O models
├── security.py          # bcrypt + JWT (access) — token_version in claims
├── deps.py              # Bearer auth + banned-JWT gate
├── middleware.py        # rate limit + request log
├── observability.py     # Prometheus metrics + JSON logs + request ID
├── email_sender.py      # pluggable (console/file/smtp/disabled)
├── combat.py            # pure turn-based resolver; produces deterministic log
├── gacha.py             # pure pulls + pity
├── economy.py           # energy/xp/rewards + level curve
├── gear_logic.py        # roll gear + set bonuses (passive + active)
├── liveops.py           # active + scheduled event queries + reward multiplier
├── daily.py             # quest rotation + progress hooks
├── daily_bonus.py       # login streak + reward table
├── store.py             # apply_grant / apply_refund + PurchaseLedger writes
├── stripe_ext.py        # Stripe checkout + webhook handler
├── worker.py            # supervised background tick (cleanup, raid rotation, ban expiry)
├── admin.py             # operator CLI (promote / demote / audit)
├── seed.py              # content seeder (heroes, stages, products, launch event)
├── routers/             # auth, me, heroes, summon, stages, battles, gear, arena, daily,
│                        # guilds, liveops, raids, shop, admin, announcements, ui
├── templates/           # Jinja2 — HTMX shell + per-tab partials
└── static/              # battle-phaser.html, battle-replay.html, battle-setup.html,
                         # roster.html, placeholder status/faction/rarity SVGs
```

Layered concerns — combat/gacha/economy are pure (no DB, no I/O) so they're unit-testable without spinning the app up. Routers compose those with the session and models.

---

## Environment & deploy

Every env var is `HEROPROTO_<UPPER>`. Full reference in [`docs/RUNBOOK.md`](docs/RUNBOOK.md). Starred items are mandatory for prod:

- **Core:** `ENVIRONMENT=prod★`, `DATABASE_URL★`, `CORS_ORIGINS★`, `JSON_LOGS=1★`
- **Auth:** `JWT_SECRET★` (32+ random bytes), `JWT_TTL_MINUTES`, `REFRESH_TOKEN_TTL_DAYS`
- **Email:** `EMAIL_SENDER_TYPE=smtp★` + `EMAIL_SMTP_HOST/PORT/USERNAME/PASSWORD★`, `EMAIL_FROM_ADDRESS`, `PUBLIC_BASE_URL★`
- **Payments:** `STRIPE_API_KEY★`, `STRIPE_WEBHOOK_SECRET★`, `STRIPE_PUBLISHABLE_KEY`
- **Rate limits:** `AUTH_RATE_PER_MINUTE`, `GENERAL_RATE_PER_MINUTE`
- **Worker:** `WORKER_ENABLED` (false on web-only instances in a scaled deploy)

At startup, `_check_secrets()` refuses to boot in prod if any of the starred items is missing or weak (default JWT secret, `mock_payments_enabled=true`, console email sender, etc.).

### Stripe

Full onboarding in [`docs/STRIPE_SETUP.md`](docs/STRIPE_SETUP.md):
1. Create Products + Prices in the Stripe dashboard matching the seeded SKUs.
2. Populate `shop_products.stripe_price_id` with the `price_...` ids.
3. Set up the webhook endpoint → populate `STRIPE_WEBHOOK_SECRET`.
4. Test with `4242 4242 4242 4242` in test mode before going live.

### Art

25 hero portraits + rarity frames + faction badges needed. Full brief with filename conventions in [`docs/ART_NEEDS.md`](docs/ART_NEEDS.md). Until files land in `app/static/heroes/<code>.svg`, the placeholder endpoint generates role-colored silhouettes with hero initials — the replay viewer never shows a broken image.

### Design handoff

[`docs/BATTLE_UI_HANDOFF.md`](docs/BATTLE_UI_HANDOFF.md) — designer's notes on the three battle pages (setup, replay, roster). Integration layer documented there.

---

## Testing

```bash
# Unit + in-process integration (fast, ~55s)
uv run pytest tests/ -q

# Run against Postgres (CI matrix uses this)
HEROPROTO_DATABASE_URL="postgresql+psycopg://hero:heropw@localhost:5432/heroproto" \
  uv run pytest tests/ -q

# End-to-end smokes against a live server
uv run uvicorn app.main:app &
uv run python -m scripts.smoke_api_core
uv run python -m scripts.smoke_shop
uv run python -m scripts.smoke_guild
# ... 16 smokes total — see scripts/
```

CI (`.github/workflows/test.yml`) runs pytest against SQLite and Postgres on every push to `master`.

For a full compose-stack smoke against Postgres (runs the app container, worker, and both acceptance scripts end-to-end):

```bash
# Requires Docker Desktop running. Tears down on exit.
bash scripts/postgres_stack_validate.sh
```

---

## Migrations

```bash
# Apply pending
uv run alembic upgrade head

# Create a new one after editing app/models.py
uv run alembic revision --autogenerate -m "describe your change"

# Roll back one step
uv run alembic downgrade -1
```

Autogen generally produces the right migration; the main gotcha is that adding a NOT NULL column to a table with existing rows needs an explicit `server_default` — the Postgres CI job catches this when you forget.

---

## What's next

See the commit log for the shipped roadmap. Genuine open items:

- **Redis rate limiter** — current in-memory buckets don't cluster and reset on restart.
- **Content expansion** — more heroes / stages / events. Blocked on art pipeline.
- **README-grade frontend polish** — the HTMX dashboard works but isn't beautiful; the design session delivered standalone HTML pages (integrated), a deeper SPA pass would be next.

---

## License

Internal / alpha. No redistribution outside the alpha cohort.
