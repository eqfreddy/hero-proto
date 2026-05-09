# Fail Pity — 3-Loss Mercy on Stages

**Goal:** After 3 consecutive losses on a `(stage, tier)`, the next attempt fights an enemy with -10% HP. Counter resets on any win.

**Architecture:** A JSON column on `accounts` tracks `{(stage_code, tier): consecutive_loss_count}`. On battle resolve, the count increments on loss and resets on win. On battle start, the resolver reads the count and applies a 0.9× HP modifier to the enemy team if count ≥ 3, then resets the count regardless of outcome (so the discount is one-shot).

**Tech Stack:** SQLAlchemy JSON column on `Account`; Alembic migration; battle-start hook in `app/routers/battles.py`.

**Depends on:** Subsystem #1 (4-tier system) — pity is keyed by tier.

---

## 1. Storage

New column on `Account`:

```python
stage_pity_json: Mapped[str] = mapped_column(Text, default="{}")
```

Shape:
```json
{
  "1-1:HARD": 2,
  "2-3:LEGENDARY": 0,
  "1-1:LEGENDARY:_consumed": true
}
```

Key format: `"<stage_code>:<tier>"`. Value: integer consecutive-loss count. The `:_consumed` suffix flag tracks "the discount was already used on the next attempt."

Migration: additive, defaults to `{}` for all existing rows.

## 2. Behavior

**On battle start (`battles.py` start-battle endpoint, before resolving combat):**

1. Read `stage_pity_json[stage_key]` (default 0).
2. Read `stage_pity_json[stage_key + ":_consumed"]` (default false).
3. If count ≥ 3 and not yet consumed: set `enemy_hp_mult = 0.9` for this battle and mark `:_consumed = true`. Otherwise `enemy_hp_mult = 1.0`.
4. Apply `enemy_hp_mult` to all enemy HP values when constructing the battle state. Combat resolver sees pre-multiplied HP — it doesn't know about pity.

**On battle resolve (after outcome determined):**

| Outcome | Pity action |
|---|---|
| WIN  | Reset both `[stage_key]` and `[stage_key+":_consumed"]` to absent (delete keys). |
| LOSS | If `:_consumed` was true: reset count to 0 and clear `:_consumed` (the discount didn't save them, restart cycle). If `:_consumed` was false: increment count by 1. |

This means: lose 3 → discount on attempt 4 → if you still lose, count resets to 0 (you don't get permanent -10%). Win at any point resets cleanly.

## 3. Applies to All Tiers

NORMAL/HARD/NIGHTMARE/LEGENDARY all participate. New player who loses 3 times on stage 1-1 NORMAL gets the -10% nudge too.

## 4. Player Visibility

**Not shown as a counter.** Player never sees "you've lost 2 in a row, 1 more for pity." Hidden mechanic — the spec deliberately keeps it implicit so it feels like the stage "felt easier" rather than a system reward.

Optional UX: a subtle one-time toast on the discounted attempt: *"The enemy looks slightly weaker."* (Decide during plan; default = no toast for v1.)

## 5. Edge Cases

- **Tier was just unlocked:** No prior pity row exists; default 0 — fresh attempt, no discount until the player loses 3 times.
- **Player switches stages mid-streak:** Each `(stage, tier)` has its own counter — switching doesn't reset others. Stage 1-1 HARD pity at 2 stays at 2 even if the player runs 1-2 HARD in between.
- **Consecutive losses across long sessions:** No time decay. Loss yesterday + loss today still counts as consecutive.

## 6. Testing

- Unit: 3 losses on `(1-1, HARD)` then start → enemy HP × 0.9 + `:_consumed` flag set.
- Unit: WIN on any attempt clears both keys.
- Unit: LOSS on a consumed attempt resets count to 0.
- Unit: Pity on `(1-1, HARD)` doesn't affect `(1-1, NIGHTMARE)`.
- Integration: full 3-loss → discounted attempt → win cycle through battle endpoints.

## 7. Out of Scope

- Time decay on the loss counter (rejected — adds complexity, no clear benefit).
- Per-tier different thresholds (e.g., 2 losses on LEGENDARY) — uniform 3 across all tiers.
- Stacking pity (two stage_pity tracks on related stages) — out of scope.
