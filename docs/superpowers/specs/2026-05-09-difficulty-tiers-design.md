# Difficulty Tiers — 4-Tier Stage System

**Goal:** Replace the 3-tier `StageDifficulty` enum with a 4-tier ladder, scale enemy stats and XP rewards per tier, and auto-generate higher-tier variants for every existing stage so players have content to climb.

**Architecture:** Extend the `StageDifficulty` enum to add `LEGENDARY`. Stage records are keyed by `(stage_code, difficulty_tier)`; one seed pass walks the existing 32 NORMAL stages and produces three derived rows (HARD/NIGHTMARE/LEGENDARY) with stats multiplied by a tier factor. XP grant in `battles.py` reads tier-keyed XP table.

**Tech Stack:** SQLAlchemy enum + Alembic migration; existing `stages` seed pipeline; existing `grant_xp` path in `battles.py`.

---

## 1. Enum & Display Names

```python
class StageDifficulty(StrEnum):
    NORMAL = "NORMAL"
    HARD = "HARD"
    NIGHTMARE = "NIGHTMARE"
    LEGENDARY = "LEGENDARY"   # new
```

| Tier        | Display name           |
|-------------|------------------------|
| `NORMAL`    | Floppy                 |
| `HARD`      | Hard Disk              |
| `NIGHTMARE` | RAID-0                 |
| `LEGENDARY` | Legen'waitforit'dary   |

Display names live in a single `STAGE_TIER_DISPLAY: dict[StageDifficulty, str]` map in `app/stages.py` (or wherever current display strings live), surfaced via `/stages` API.

## 2. XP Per Win

| Tier        | XP per win |
|-------------|-----------:|
| NORMAL      | 12         |
| HARD        | 28         |
| NIGHTMARE   | 50         |
| LEGENDARY   | 60         |

Lookup table in `app/battles.py` (or `app/xp.py` if it exists). Replaces any hardcoded 12 currently emitted on win. **Account XP only** — hero XP grants are not retiered by this subsystem (their existing per-battle formula stays). Subsystem #4 (Rest XP) applies its 2× multiplier to both account and hero XP grants on top of whatever base each system computes.

## 3. Enemy Stat Multipliers

| Tier        | HP × | ATK × |
|-------------|-----:|------:|
| NORMAL      | 1.0  | 1.0   |
| HARD        | 2.0  | 2.0   |
| NIGHTMARE   | 4.0  | 4.0   |
| LEGENDARY   | 8.0  | 8.0   |

Applied at stage-seed time (multiplier baked into the per-tier `StageEnemy` rows), **not** at battle resolution. This keeps the runtime combat resolver oblivious to tier — it just reads enemy HP/ATK.

## 4. Backfill Strategy

For each of the 32 existing NORMAL stages, the seed pass produces three sibling rows (HARD/NIGHTMARE/LEGENDARY) with:
- Same `stage_code` (e.g., `1-1`)
- Same enemies, same composition, same drop tables (drop weights are NOT multiplied)
- Enemy `hp` and `atk` multiplied per tier table above
- `difficulty_tier` set per tier
- New PK; existing API key `(stage_code, difficulty_tier)` already supports this

Final stage count: 32 × 4 = 128 rows.

The seed pass is idempotent — re-running upserts but does not duplicate.

## 5. API & Frontend

**Backend:** `/stages` endpoint groups by `stage_code` and returns a `tiers: [{tier, display_name, xp, enemy_power, …}]` array per stage.

**Frontend:** Stage list shows the current tier the player is attempting, with a tier picker (tabs or dropdown) to switch. Locked tiers display a lock icon (subsystem #2 controls unlock state).

## 6. Migration

Alembic migration:
1. `ALTER TYPE stagedifficulty ADD VALUE 'LEGENDARY'` (Postgres) or table rebuild (SQLite — copy enum into a temp table).
2. Run seed pass to upsert the 96 new tier rows.
3. No data backfill needed for player progress — players who haven't cleared any HARD/NIGHTMARE/LEGENDARY stages simply have none, which is the correct empty state.

## 7. Testing

- Unit: enum has 4 values; XP table returns 60 for LEGENDARY, etc.
- Integration: seed pass produces exactly 128 stage rows after running on a 32-stage NORMAL fixture; multipliers are applied correctly.
- API: `/stages` response includes all 4 tiers per stage.
- Battle: a HARD-tier battle grants 28 XP on win.

## 8. Out of Scope

- Tier unlock gating (subsystem #2)
- Power floor enforcement (subsystem #2)
- Fail pity (subsystem #3)
- Rest XP multiplier on top of base XP (subsystem #4)
- Drop meter guarantees (subsystem #5)

These layer on top of the tier system but ship in separate plans.
