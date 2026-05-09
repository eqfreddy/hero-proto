# Tier Locks + Power Floor

**Goal:** Gate higher difficulty tiers behind clearing the prior tier of the same stage, plus enforce a minimum team-power floor on NIGHTMARE and LEGENDARY tiers.

**Architecture:** Per-stage tier-clear flags keyed by `(account_id, stage_code, difficulty_tier)` in a `StageClear` table (or extension of an existing per-stage progress table). Battle resolver checks unlock state before accepting a battle request; `/stages` API surfaces locked/unlocked status to the frontend.

**Tech Stack:** SQLAlchemy + new (or extended) `StageClear` model; existing battle-start request validation in `app/routers/battles.py`.

**Depends on:** Subsystem #1 (4-tier system) must ship first.

---

## 1. Lock Chain

```
NORMAL  → HARD  → NIGHTMARE  → LEGENDARY
```

Per stage, not per account. Player must first clear stage `1-1` at NORMAL to unlock `1-1` HARD; clearing `1-1` HARD unlocks `1-1` NIGHTMARE; clearing `1-1` NIGHTMARE unlocks `1-1` LEGENDARY.

Account-level chapter gates (lvl 1 / 10 / 20 / 50) remain unchanged — the new gate is per-stage, layered under the existing chapter gate.

## 2. Storage

Reuse the existing per-stage clear tracking if present. If not, add:

```python
class StageClear(Base):
    __tablename__ = "stage_clears"
    id: int  PK
    account_id: int  FK
    stage_code: str  # e.g., "1-1"
    difficulty_tier: StageDifficulty
    cleared_at: datetime
    UNIQUE (account_id, stage_code, difficulty_tier)
```

Pre-flight before writing the plan: check `app/models.py` for an existing per-stage progress structure. If it exists with a `cleared_tiers` JSON or similar, extend that instead of adding a new table.

## 3. Power Floor

Global thresholds (not per-stage):

| Tier        | Min team power |
|-------------|---------------:|
| NORMAL      | none           |
| HARD        | none           |
| NIGHTMARE   | 50,000         |
| LEGENDARY   | 100,000        |

Team power = sum of `hero.power` across the 5 heroes selected for the battle, computed by the existing power calc. Enforced in the battle-start endpoint; returns `400 {"detail": "team power below tier floor", "required": 50000, "current": 38421}` on rejection.

## 4. API Surface

**`/stages` response addition:**

```json
{
  "stage_code": "1-1",
  "tiers": [
    {"tier": "NORMAL",    "unlocked": true,  "cleared": true,  ...},
    {"tier": "HARD",      "unlocked": true,  "cleared": false, "power_floor": null},
    {"tier": "NIGHTMARE", "unlocked": false, "cleared": false, "power_floor": 50000},
    {"tier": "LEGENDARY", "unlocked": false, "cleared": false, "power_floor": 100000}
  ]
}
```

`unlocked` is computed server-side from clear-state of the prior tier on the same `stage_code`.

## 5. Battle-Start Validation

In `app/routers/battles.py`'s start-battle endpoint:

```python
# After loading stage and team:
if not _tier_unlocked(db, account, stage.stage_code, stage.difficulty_tier):
    raise HTTPException(400, "tier locked — clear prior tier first")
floor = TIER_POWER_FLOOR.get(stage.difficulty_tier)
if floor and team_power < floor:
    raise HTTPException(400, {
        "detail": "team power below tier floor",
        "required": floor,
        "current": team_power,
    })
```

`_tier_unlocked` returns `True` if either:
- Tier is NORMAL, OR
- Player has a `StageClear` row for `(stage_code, prior_tier)` where prior tier follows the chain

## 6. Recording a Clear

On a winning battle outcome (existing path), the resolver writes a `StageClear` row idempotently:

```python
if outcome == BattleOutcome.WIN:
    _upsert_stage_clear(db, account, stage.stage_code, stage.difficulty_tier)
```

Idempotent: unique constraint on `(account_id, stage_code, difficulty_tier)` — second clear is a no-op.

## 7. Frontend

Stage row in the stage list:
- Cleared tiers show a check icon
- Locked tiers show a lock icon + tooltip ("Clear HARD first" or "Requires 50,000 power")
- Power-floor failure shows an inline warning before the player even taps Battle (frontend computes team power locally)

## 8. Testing

- Unit: `_tier_unlocked` returns false for HARD when NORMAL not cleared; true after NORMAL is cleared.
- Integration: 400 on locked tier; 400 on power floor violation with the right error body.
- API: `/stages` response correctly reflects unlock state after clears.
- E2E: clear NORMAL stage 1-1, verify HARD 1-1 becomes available.

## 9. Out of Scope

- Auto-unlock notifications (toast/announcement) — backlog.
- Per-stage power floor (rejected design — global thresholds were chosen).
