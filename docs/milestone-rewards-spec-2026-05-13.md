# Milestone Rewards — Backend Spec (2026-05-13)

## 1. Overview

Every 5 or 10 cleared stages on the board-map Stages page unlocks a milestone reward containing a guaranteed quantity of generic template shards (the cross-template currency in `app/template_shards.py`) plus a non-deterministic chance at a new `legend_boss_shards` currency. Players accumulate `legend_boss_shards` until they hit the summon threshold, at which point they can summon a legendary boss-grade hero from a dedicated pool. Milestones are claimed once, persist forever, and expose progress counters to drive Zeigarnik-effect UI.

---

## 2. Schema Changes

### 2a. New column on `accounts`

```
legend_boss_shards        INTEGER  NOT NULL DEFAULT 0
milestone_legend_pity     INTEGER  NOT NULL DEFAULT 0
```

- `legend_boss_shards` — balance of the new currency. Scalar integer; no JSON needed because it is a single undifferentiated currency (unlike per-template shards).
- `milestone_legend_pity` — counts consecutive milestone claims that did NOT award a legendary shard. Resets to 0 on award. Drives the pity floor (see Section 5).

**Why scalars not JSON:** The existing JSON pattern (`template_shards_json`, `stage_pity_json`) is used where the key space is dynamic (one entry per hero template, one per stage+tier pair). `legend_boss_shards` has a fixed key space of 1, so a plain `Integer` column is cleaner and index-friendly.

### 2b. New table `stage_milestones`

Tracks which milestones exist and their static reward configuration.

```sql
CREATE TABLE stage_milestones (
    id              INTEGER PRIMARY KEY,
    stage_count     INTEGER NOT NULL UNIQUE,   -- 5, 10, 15, 20, …
    template_shards INTEGER NOT NULL,          -- guaranteed shard grant
    legend_shard_chance REAL NOT NULL,         -- 0.0–1.0 drop probability
    label           VARCHAR(64) NOT NULL DEFAULT ''  -- display label e.g. "Ticket Clerk"
);
CREATE INDEX ix_stage_milestones_stage_count ON stage_milestones(stage_count);
```

Seeded at migration time with the reward table from Section 5. Content-as-data (not content-as-code) so rewards can be adjusted via admin without a deploy.

### 2c. New table `account_milestone_claims`

Tracks per-account milestone claim state. A separate table (not a JSON column on `accounts`) because:
- Claim records need idempotency enforcement at the DB level (unique constraint).
- The set of milestones grows over time; a JSON column on `accounts` would bloat unboundedly.
- Querying "which milestones has this account NOT claimed" is a simple anti-join, not a JSON parse.

```sql
CREATE TABLE account_milestone_claims (
    id              INTEGER PRIMARY KEY,
    account_id      INTEGER NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    milestone_id    INTEGER NOT NULL REFERENCES stage_milestones(id),
    claimed_at      DATETIME NOT NULL,
    template_shards_granted  INTEGER NOT NULL,
    legend_shards_granted    INTEGER NOT NULL DEFAULT 0,
    UNIQUE (account_id, milestone_id)
);
CREATE INDEX ix_amc_account_id ON account_milestone_claims(account_id);
```

The `UNIQUE (account_id, milestone_id)` constraint is the idempotency lock — a second INSERT raises `IntegrityError`, which the endpoint maps to HTTP 409.

---

## 3. Migration Sketch

**File:** `alembic/versions/<hash>_add_milestone_rewards.py`

```
revision: str = "<new_hash>"
down_revision: str = "f9fcd159c6dd"   # shard_remap_collapse_dupes
```

```python
def upgrade() -> None:
    # 1. New columns on accounts (batch_alter for SQLite safety)
    with op.batch_alter_table("accounts") as b:
        b.add_column(sa.Column("legend_boss_shards",    sa.Integer(), nullable=False, server_default="0"))
        b.add_column(sa.Column("milestone_legend_pity", sa.Integer(), nullable=False, server_default="0"))

    # 2. stage_milestones table
    op.create_table(
        "stage_milestones",
        sa.Column("id",                  sa.Integer(), primary_key=True),
        sa.Column("stage_count",         sa.Integer(), nullable=False, unique=True),
        sa.Column("template_shards",     sa.Integer(), nullable=False),
        sa.Column("legend_shard_chance", sa.Float(),   nullable=False),
        sa.Column("label",               sa.String(64), nullable=False, server_default=""),
    )
    op.create_index("ix_stage_milestones_stage_count", "stage_milestones", ["stage_count"])

    # 3. account_milestone_claims table
    op.create_table(
        "account_milestone_claims",
        sa.Column("id",                      sa.Integer(), primary_key=True),
        sa.Column("account_id",              sa.Integer(), sa.ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("milestone_id",            sa.Integer(), sa.ForeignKey("stage_milestones.id"),            nullable=False),
        sa.Column("claimed_at",              sa.DateTime(), nullable=False),
        sa.Column("template_shards_granted", sa.Integer(), nullable=False),
        sa.Column("legend_shards_granted",   sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("account_id", "milestone_id", name="uq_amc_account_milestone"),
    )
    op.create_index("ix_amc_account_id", "account_milestone_claims", ["account_id"])

    # 4. Seed milestone rows (backfill — safe to run on non-empty DBs)
    bind = op.get_bind()
    rows = [
        (5,  20, 0.05,  "Ticket Clerk"),
        (10, 35, 0.08,  "On-Call Warrior"),
        (15, 50, 0.10,  "Change Window"),
        (20, 70, 0.12,  "Incident Commander"),
        (25, 90, 0.15,  "The Root Cause"),
        (30, 115, 0.18, "Post-Mortem Legend"),
        (40, 150, 0.22, "Zero-Day Survivor"),
        (50, 200, 0.28, "The BOFH"),
    ]
    for stage_count, shards, chance, label in rows:
        bind.execute(sa.text(
            "INSERT INTO stage_milestones (stage_count, template_shards, legend_shard_chance, label) "
            "VALUES (:sc, :ts, :lc, :lb)"
        ), {"sc": stage_count, "ts": shards, "lc": chance, "lb": label})


def downgrade() -> None:
    op.drop_table("account_milestone_claims")
    op.drop_table("stage_milestones")
    with op.batch_alter_table("accounts") as b:
        b.drop_column("legend_boss_shards")
        b.drop_column("milestone_legend_pity")
```

`op.batch_alter_table` is required for SQLite (which does not support `ALTER TABLE ADD COLUMN` with constraints in all versions); Postgres handles it natively via the same call.

---

## 4. API Contract

### 4a. `GET /stages/milestones`

Returns the full milestone list with per-account claim state and current progress.

**Auth:** `get_current_account` (JWT).

**Response:**
```json
{
  "stages_cleared_count": 12,
  "next_milestone": {
    "id": 3,
    "stage_count": 15,
    "stages_to_go": 3,
    "template_shards": 50,
    "legend_shard_chance": 0.10,
    "label": "Change Window"
  },
  "milestones": [
    {
      "id": 1,
      "stage_count": 5,
      "template_shards": 20,
      "legend_shard_chance": 0.05,
      "label": "Ticket Clerk",
      "unlocked": true,
      "claimed": true,
      "claimed_at": "2026-05-13T04:00:00Z",
      "legend_shards_granted": 0
    },
    {
      "id": 2,
      "stage_count": 10,
      "template_shards": 35,
      "legend_shard_chance": 0.08,
      "label": "On-Call Warrior",
      "unlocked": true,
      "claimed": true,
      "claimed_at": "2026-05-13T05:00:00Z",
      "legend_shards_granted": 1
    },
    {
      "id": 3,
      "stage_count": 15,
      "template_shards": 50,
      "legend_shard_chance": 0.10,
      "label": "Change Window",
      "unlocked": false,
      "claimed": false,
      "claimed_at": null,
      "legend_shards_granted": null
    }
  ],
  "legend_boss_shards": 1,
  "legend_summon_cost": 30,
  "pity_counter": 1,
  "pity_floor": 10
}
```

`stages_cleared_count` is `len(load_cleared(account))` (reuses `app/economy.py:217`). The `next_milestone` block drives the "3 stages to next milestone" Zeigarnik counter in the UI. `legend_shard_chance` is published verbatim — transparency Rule #1 requirement.

### 4b. `POST /stages/milestones/{milestone_id}/claim`

Claims an unlocked, unclaimed milestone.

**Auth:** `get_current_account`.

**Preconditions (checked in order):**
1. Milestone row exists — 404 if not.
2. `stages_cleared_count >= milestone.stage_count` — 409 `"milestone not yet unlocked"` if not.
3. No existing `account_milestone_claims` row for `(account.id, milestone_id)` — 409 `"already claimed"` if exists (idempotency enforced by the DB UNIQUE constraint as a second backstop).

**Side effects (all in one DB transaction):**
- Roll legendary shard (see Section 5).
- Credit `template_shards_json` via `app/template_shards.grant(account, "_milestone", amount)` — or, since milestone shards are cross-template, credit the `account.shards` scalar (the generic shard currency at `models.py:209`) rather than a template-specific key. This avoids polluting `template_shards_json` with a fake template code.
- Credit `account.legend_boss_shards` by roll result.
- Update `account.milestone_legend_pity`.
- INSERT into `account_milestone_claims`.

**Response:**
```json
{
  "milestone_id": 3,
  "template_shards_granted": 50,
  "legend_shards_granted": 1,
  "legend_boss_shards_balance": 2,
  "pity_counter": 0
}
```

`legend_shards_granted` is 0 or 1. The client shows a special reveal animation when it is 1.

### 4c. Hook point in stage-clear flow

In `app/routers/battles.py`, after line 229 (`first_clear = mark_cleared(...)`), add:

```python
if first_clear:
    from app.milestones import check_milestone_unlocks as _check_ms
    milestone_unlocks = _check_ms(account, db)
    # milestone_unlocks: list[int] of newly-unlocked milestone IDs
    # Returned in BattleOut.milestone_unlocks so the client can prompt the claim CTA.
```

`app/milestones.check_milestone_unlocks` is a pure read: count cleared stages, query `stage_milestones` where `stage_count <= cleared_count` and no claim row exists. Returns IDs. No state mutation — claiming is always explicit via `POST /stages/milestones/{id}/claim`.

Add `milestone_unlocks: list[int] = []` to `BattleOut` schema (`app/schemas.py`).

The same hook should be added in the sweep path (wherever `mark_cleared` is called in the sweep loop).

---

## 5. Reward Calculation

### Milestone reward table (seeded in migration)

| Milestone (stages cleared) | Template shards | Legend shard base chance | Label |
|---|---|---|---|
| 5  | 20  | 5%  | Ticket Clerk |
| 10 | 35  | 8%  | On-Call Warrior |
| 15 | 50  | 10% | Change Window |
| 20 | 70  | 12% | Incident Commander |
| 25 | 90  | 15% | The Root Cause |
| 30 | 115 | 18% | Post-Mortem Legend |
| 40 | 150 | 22% | Zero-Day Survivor |
| 50 | 200 | 28% | The BOFH |

Template shards credited to `account.shards` (the generic scalar at `models.py:209`), not to `template_shards_json`, because milestone shards are cross-template ascending currency, not bound to a specific hero.

### Pity floor

```
LEGEND_PITY_FLOOR = 10   # consecutive non-award claims before guarantee
```

**Roll logic (`app/milestones.py`):**

```python
def roll_legend_shard(account: Account, base_chance: float, rng: random.Random) -> int:
    pity = account.milestone_legend_pity
    if pity >= LEGEND_PITY_FLOOR:
        account.milestone_legend_pity = 0
        return 1
    if rng.random() < base_chance:
        account.milestone_legend_pity = 0
        return 1
    account.milestone_legend_pity = pity + 1
    return 0
```

Pity counter is stored on the account so it persists across sessions and survives server restarts. The floor of 10 means a player claiming all 8 milestones will get at least 0–1 guaranteed shards from pity (floor triggers once every 10 claims). Adjust `LEGEND_PITY_FLOOR` down to 6 if testing shows the legendary summon feels too distant.

---

## 6. Legendary Boss Summon

### Currency cost

**30 `legend_boss_shards` = one legendary boss summon.**

Rationale: at the best per-milestone drop rate (28% at milestone 50), expected shards per claim is ~0.28. Across all 8 milestones the expected total is ~1.1 shards from drops alone; pity guarantees ~0.8 more. A fresh player completing all 50 stages can expect 1–3 shards. Setting the cost to 30 means the legendary boss summon is a long-term goal requiring repeated playthroughs or event top-ups — appropriate for a boss-grade hero.

### Hero pool

A new `Faction` value `RAID_BOSS` (or reuse the existing `MYTH` rarity) gates the pool. The summon pulls from `HeroTemplate` rows where `rarity = MYTH` AND a new boolean column `is_legend_boss_pool = TRUE`. This keeps the pool separately curated from event banners (`LiveOpsKind.EVENT_BANNER`) and the standard MYTH pool.

New column on `hero_templates`:
```sql
is_legend_boss_pool  BOOLEAN  NOT NULL DEFAULT FALSE
```

The summon endpoint (`POST /summon/legend-boss`) deducts 30 `legend_boss_shards`, pulls one template from the boss pool with equal weight, and follows the existing duplicate-to-template-shards flow from `app/gacha.py` and `app/template_shards.grant_dupe_shards`.

The endpoint belongs in `app/routers/heroes.py` alongside the existing summon endpoints, following the same `BattleOut`/`SummonOut` response pattern.

---

## 7. Tests to Write

All in `tests/` as pytest cases with the existing SQLite test DB fixture:

1. **`test_milestone_claim_grants_shards`** — claim milestone 1, assert `account.shards` increased by 20.
2. **`test_milestone_claim_idempotent`** — claim milestone 1 twice; second call returns HTTP 409 `"already claimed"`.
3. **`test_milestone_not_yet_unlocked`** — account with 3 cleared stages attempts to claim milestone 1 (requires 5); assert HTTP 409 `"milestone not yet unlocked"`.
4. **`test_milestone_counter_increments_on_stage_clear`** — simulate stage clear via battles endpoint, assert `GET /stages/milestones` returns updated `stages_cleared_count`.
5. **`test_pity_floor_triggers_at_n`** — set `account.milestone_legend_pity = 10`, claim any milestone; assert `legend_shards_granted == 1` and `account.milestone_legend_pity == 0`.
6. **`test_pity_resets_on_legend_award`** — set pity to 5, roll hits (mock `random.random` to return 0.0), assert pity resets to 0.
7. **`test_pity_increments_on_miss`** — set pity to 3, roll misses (mock `random.random` to return 1.0), assert pity is 4.
8. **`test_legend_boss_summon_deducts_shards`** — set `legend_boss_shards = 30`, POST to `/summon/legend-boss`, assert balance is 0 and a hero was created.
9. **`test_legend_boss_summon_insufficient_shards`** — balance 29, assert HTTP 409.
10. **`test_get_milestones_progress_field`** — account with 12 cleared stages; assert response `next_milestone.stage_count == 15` and `stages_to_go == 3`.
11. **`test_milestone_unlocks_in_battle_out`** — clear stage that crosses a milestone threshold for first time; assert `BattleOut.milestone_unlocks` contains the newly-unlocked milestone ID.
12. **`test_legend_boss_pool_only_myth`** — seed one MYTH hero with `is_legend_boss_pool=True` and one without; summon 20 times; assert only the pool hero ever results.

---

## 8. Rollback Plan

The migration has a working `downgrade()` that:
1. Drops `account_milestone_claims` (no FK dependents).
2. Drops `stage_milestones`.
3. Drops `legend_boss_shards` and `milestone_legend_pity` from `accounts`.

Data loss on downgrade: all claimed milestone records and any `legend_boss_shards` balances are destroyed. If a rollback is needed in production after any claims have been made, the safe approach is:

1. Before running `alembic downgrade`, export `account_milestone_claims` and `accounts.legend_boss_shards` to a CSV.
2. Run `alembic downgrade -1`.
3. Compensate affected accounts manually via admin gem/shard grants if re-migration is not planned.

The `is_legend_boss_pool` column on `hero_templates` (added in a follow-on migration) should be in its own migration so it can be independently reverted without touching the milestone tables.

Feature-flag alternative: if zero-downtime rollback is required, add a `MILESTONE_REWARDS_ENABLED: bool` setting in `app/settings.py`. The battles hook and both endpoints check this flag and short-circuit when `False`, making the feature dark-launchable without a DB migration rollback.
