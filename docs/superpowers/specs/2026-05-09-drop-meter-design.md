# Drop Meter — Per-Stage Guaranteed Rare+ Drop

**Goal:** Each `(stage, tier)` accumulates a meter that fills by 1 per run; at cap (20 runs), the next run guarantees a RARE+ gear drop rolled within a tier-appropriate pool, then resets to 0.

**Architecture:** A JSON column on `accounts` tracks per `(stage_code, tier)` run counts. On battle resolve, the count increments. On battle drop-roll, if count ≥ cap, the drop pipeline overrides the rarity roll with a tier-keyed RARE+ guarantee and resets the meter for that key.

**Tech Stack:** SQLAlchemy JSON column on `Account`; existing drop-roll logic in the battle resolver / loot pipeline.

**Depends on:** Subsystem #1 (4-tier system) for tier-keyed rolls.

---

## 1. Storage

New column on `Account`:

```python
stage_drop_pity_json: Mapped[str] = mapped_column(Text, default="{}")
```

Shape:
```json
{
  "1-1:NORMAL": 7,
  "1-1:HARD": 19,
  "2-3:LEGENDARY": 0
}
```

Key format: `"<stage_code>:<tier>"`. Value: integer count of runs since last guaranteed drop. Range `0..CAP`.

Migration: additive, defaults to `{}` for all existing rows.

## 2. Constants

```python
DROP_METER_CAP = 20    # runs

DROP_METER_GUARANTEE_POOL = {
    StageDifficulty.NORMAL:    {"RARE": 1.0},                              # always RARE
    StageDifficulty.HARD:      {"RARE": 0.7, "EPIC": 0.3},                 # mostly RARE
    StageDifficulty.NIGHTMARE: {"EPIC": 0.8, "LEGENDARY": 0.2},            # mostly EPIC
    StageDifficulty.LEGENDARY: {"EPIC": 0.4, "LEGENDARY": 0.6},            # mostly LEGENDARY
}
```

(Pool weights normalize to 1.0 per tier.)

## 3. Behavior

**On battle resolve (after WIN, before drop-roll):**

```python
key = f"{stage.stage_code}:{stage.difficulty_tier}"
counts = json.loads(account.stage_drop_pity_json or "{}")
count = counts.get(key, 0) + 1

if count >= DROP_METER_CAP:
    # Trigger the guaranteed drop, reset counter.
    rarity = _roll_guarantee_rarity(stage.difficulty_tier)
    drop = _roll_gear_within_rarity(stage, rarity)
    counts[key] = 0
else:
    # Normal RNG drop path.
    drop = _roll_gear_normal(stage)
    counts[key] = count

account.stage_drop_pity_json = json.dumps(counts)
```

`_roll_guarantee_rarity` is a weighted pick from `DROP_METER_GUARANTEE_POOL[tier]`.

`_roll_gear_within_rarity` reuses the existing per-stage drop pipeline but constrains the rarity roll to the chosen tier. Implementation: filter the stage's drop table to items of that rarity and roll within them; if the stage has no items of that rarity (content gap), fall back to the highest available rarity in its drop table.

## 4. Loss Doesn't Increment

Only WIN increments the meter. Losses don't fill the bar — this avoids exploits where players intentionally lose to fill the meter cheaply (running a stage they can clear is the cost).

## 5. Player Visibility

**Stage row badge:** Each stage row shows the current meter for the player's selected tier:

```
Guaranteed drop in 4 runs   [█████████████████░░░]
```

Or, when at cap:

```
★ Guaranteed drop next run!
```

**On the guaranteed drop:** Battle outcome screen highlights the drop with a "Guaranteed!" tag and a brief animation (sparkle / glow).

## 6. API Surface

Stage list response per tier includes:

```json
{
  "tier": "HARD",
  "drop_meter": 7,
  "drop_meter_cap": 20
}
```

## 7. Edge Cases

- **No gear in stage drop table at all:** Stage doesn't trigger drop-meter logic; counter stays at 0 forever. (Some stages might be currency-only.)
- **Stage drop table missing rare+ items entirely:** `_roll_gear_within_rarity` falls back to highest available rarity in the stage's table; logs a warning so designers know to fix the drop table.
- **Tier change resets meter for a different key:** Counter is per `(stage, tier)`. Switching tiers doesn't transfer progress — clearing 1-1 NIGHTMARE 19 times then switching to 1-1 LEGENDARY starts fresh at 0.

## 8. Testing

- Unit: meter increments by 1 on WIN, doesn't increment on LOSS.
- Unit: at count = 19, next WIN triggers guarantee, sets count to 0.
- Unit: `_roll_guarantee_rarity` distribution matches the configured weights over many samples.
- Unit: missing-rarity fallback returns highest-available rarity in the stage's table.
- Integration: 20-run loop on a stage produces exactly one guaranteed drop and resets the counter.
- API: stage list shows correct `drop_meter` after N battles.

## 9. Out of Scope

- Cross-stage meter ("clear any 20 stages, get a guaranteed drop") — rejected.
- Premium boosters that lower the cap — backlog.
- Showing the underlying RNG drop chance separately from meter — backlog.
