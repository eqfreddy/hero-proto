# hero-proto — Gary-verse IT Collector Backend

Gacha + turn-based team combat RPG backend, alpha candidate. IT-themed heroes fight through outage/audit/migration stages. Built with FastAPI + SQLAlchemy + uv on Python 3.13.

---

## Alpha tester quickstart

**Requirements:** Docker (recommended) or Python 3.13 + [uv](https://docs.astral.sh/uv/).

### Option A — Docker (recommended)

```bash
cp .env.example .env
# Edit .env — at minimum set HEROPROTO_JWT_SECRET to something long & random.
docker compose up -d --build
curl http://localhost:8000/healthz   # {"status":"ok","env":"dev"}
```

The server auto-runs migrations on startup and persists SQLite to a named Docker volume (`hero-data`). Seed content doesn't auto-load in the container build — run it once:

```bash
docker compose exec hero-proto uv run python -m app.seed
```

### Option B — uv locally (Windows / macOS / Linux)

```powershell
cd hero-proto
uv sync
uv run python -m app.seed
uv run uvicorn app.main:app --reload
# new terminal — interactive play
uv run python scripts/play_hero.py
```

### Create your alpha account

The CLI auto-registers if you don't pass `--email`:

```powershell
uv run python scripts/play_hero.py
# or explicitly:
uv run python scripts/play_hero.py --email alpha1@test.com --password hunter22
```

---

## What works (all end-to-end tested)

| Surface | Endpoint / action |
|---|---|
| Auth | `POST /auth/register`, `POST /auth/login` → JWT |
| Profile | `GET /me` — currencies + regenerating energy |
| Gacha | `POST /summon`, `POST /summon/x10` — pity at 50 pulls |
| Roster | `GET /heroes/mine`, `GET /heroes/templates` |
| Campaign | `GET /stages`, `POST /battles` (full combat log returned) |
| Sweep | `POST /battles/sweep/{stage_id}` — instant-replay cleared stages |
| Gear | `GET /gear/mine`, `POST /gear/{id}/equip`, `POST /gear/{id}/unequip` |
| Skill up | `POST /heroes/{id}/skill_up` (consume duplicates) |
| Ascension | `POST /heroes/{id}/ascend` (stars 1–5) |
| Arena | `PUT /arena/defense`, `GET /arena/opponents`, `POST /arena/attack`, `GET /arena/leaderboard` |
| Daily | `GET /daily`, `POST /daily/{id}/claim` — 3 quests per UTC day |

OpenAPI UI at <http://localhost:8000/docs>.

---

## Content snapshot

- **25 hero templates** across 5 factions (HELPDESK, DEVOPS, EXECUTIVE, ROGUE_IT, LEGACY) and 3 roles (ATK / DEF / SUP)
- **10 campaign stages** — Onboarding Day → The Singularity
- **5 status effects** (ATK_UP, DEF_DOWN, POISON, STUN, SHIELD)
- **4 gear sets** (VITAL / OFFENSE / DEFENSE / SWIFT), 6 slots, 4 rarity tiers

---

## Running the tests

```bash
uv run pytest                 # unit + in-process integration tests (fast)

# Or the scripted end-to-end smokes against a running server:
uv run uvicorn app.main:app --port 8000
uv run python scripts/test_combat.py
uv run python scripts/smoke_hero.py
uv run python scripts/smoke_gear.py
uv run python scripts/smoke_skill.py
uv run python scripts/smoke_arena.py
uv run python scripts/smoke_daily.py
uv run python scripts/smoke_sets.py
uv run python scripts/smoke_ascend.py
uv run python scripts/smoke_sweep.py
uv run python scripts/smoke_cli.py
```

---

## Deploying for alpha

Minimum checklist before handing the URL to testers:

1. **Strong JWT secret.** Set `HEROPROTO_JWT_SECRET` to ≥ 32 random bytes. Generate with:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(48))"
   ```
2. **Set `HEROPROTO_ENVIRONMENT=prod`.** The app refuses to start with the default secret in prod.
3. **Lock down CORS.** `HEROPROTO_CORS_ORIGINS=https://your-frontend.example.com` (comma-separated for multiple).
4. **Rate limits.** Defaults: 10 auth requests / minute and 120 general requests / minute per IP. Adjust via `HEROPROTO_AUTH_RATE_PER_MINUTE` / `HEROPROTO_GENERAL_RATE_PER_MINUTE`.
5. **Database.** SQLite is fine for small alpha. For more concurrency, switch to Postgres:

   Install the optional driver:
   ```bash
   uv sync --extra postgres
   ```
   Bring it up via compose (dedicated `postgres` profile, plus the app):
   ```bash
   export HEROPROTO_DATABASE_URL='postgresql+psycopg://hero:heropw@postgres:5432/heroproto'
   docker compose --profile postgres up -d --build
   docker compose exec hero-proto uv run alembic upgrade head
   docker compose exec hero-proto uv run python -m app.seed
   ```
   For a hosted Postgres (RDS, Supabase, Neon etc.), just set the URL and skip the `--profile postgres` flag:
   ```bash
   HEROPROTO_DATABASE_URL=postgresql+psycopg://user:pass@host/heroproto
   ```
   Schema is managed by Alembic — same `uv run alembic upgrade head` flow works on any SQLAlchemy-supported backend.
6. **Backups.** For SQLite in Docker, back up the `hero-data` volume:
   ```bash
   docker run --rm -v hero-data:/data -v $(pwd):/backup alpine tar czf /backup/heroproto-$(date +%F).tgz /data
   ```

---

## Migrations

```bash
# Apply all pending migrations
uv run alembic upgrade head

# Create a new one after editing app/models.py
uv run alembic revision --autogenerate -m "describe your change"

# Roll back one step (careful — SQLite doesn't support every downgrade path)
uv run alembic downgrade -1
```

---

## Project layout

```
hero-proto/
├── app/
│   ├── main.py            # FastAPI + lifespan (migrations, secret check)
│   ├── config.py          # pydantic-settings (HEROPROTO_* env vars)
│   ├── middleware.py      # rate limit + request log
│   ├── db.py              # SQLAlchemy Base + sessionmaker
│   ├── models.py          # all tables
│   ├── schemas.py         # pydantic I/O
│   ├── security.py        # bcrypt + PyJWT
│   ├── deps.py            # Bearer auth dep
│   ├── combat.py          # pure turn-based resolver
│   ├── gacha.py           # pure pulls + pity
│   ├── economy.py         # energy/xp/rewards
│   ├── gear_logic.py      # roll gear + set bonuses
│   ├── daily.py           # daily quest rotation + progress hooks
│   ├── game.py            # (unused placeholder; keep for future)
│   ├── seed.py            # content seeder
│   └── routers/
│       ├── auth.py me.py heroes.py summon.py stages.py
│       └── battles.py gear.py arena.py daily.py
├── alembic/               # migrations
├── scripts/               # CLI client + smokes
│   ├── play_hero.py
│   └── smoke_*.py
├── tests/                 # pytest: unit + in-process integration
├── Dockerfile
├── docker-compose.yml
└── .env.example
```

---

## Known limitations (alpha scope)

- SQLite by default — fine for small concurrent load only.
- Energy regen is lazy (no background ticker) — correct but doesn't push notifications.
- No email verification or password reset (use throwaway test accounts).
- No monetisation — all gems are earned in game.
- Single-instance rate limiting — doesn't coordinate across replicas.
- No admin panel — use `docker compose exec` + sqlite3 to poke at state.

## License

Internal / alpha. No redistribution outside the alpha cohort.
