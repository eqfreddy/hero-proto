# 2026-05-12 — Shard remap

Convert duplicate hero pulls from "spawn another `HeroInstance` row" to
"increment a shard balance." Each template the player owns becomes a
single canonical `HeroInstance`; everything else collapses to a per-
template shard count.

## Locked decisions (from chat 2026-05-12)

1. **Variance: keep as-is.** Stays attached to the canonical
   `HeroInstance.variance_pct_json`. New dupes do not re-roll it.
2. **Skill-up cost: fixed N shards per level.** Static schedule, no
   scaling, no level-of-fodder math. Forecloses the exploits we saw in
   the fodder-shopping model.
3. **Cleanup: in scope this commit-stream.** Players need a way to
   bulk-convert excess shards.
4. **Backfill: rip and replace.** OK to wipe player rosters /
   shard balances. No safety net required — "it's just us under the
   hood."
5. **First-pull behavior: still spawns a `HeroInstance`.** First copy
   of a template = the canonical hero; subsequent duplicates = shards
   only. (Revisit later — flagged as open.)

## Today vs target

| | Today | Target |
|---|---|---|
| First pull of template X | Creates `HeroInstance` | Same |
| Duplicate pull of template X | Creates **another** `HeroInstance` + grants shards (both!) | **Grants shards only**, no new row |
| Skill-up source | Consumes N fodder `HeroInstance` rows of same template | Spends N shards |
| Ascension source | Two variants (fodder OR shards) | Shards only |
| Roster size for N templates owned, M dupes each | N × M rows | N rows |
| Roster UI | Grouped-by-rarity with `×N` stacked vanilla copies (shipped today) | Same grouping; stacks disappear since there's only ever 1 |
| Cleanup options | None | Bulk-convert excess shards → coins at fixed rate |

## File inventory

**Backend**
- `app/routers/summon.py` — gacha duplicate branch (2 sites: x1 and x10)
- `app/routers/heroes.py` — `skill_up` (rewrite), `ascend` (delete the fodder variant, keep `ascend_with_shards`)
- `app/template_shards.py` — confirm `grant_dupe_shards` logic + add `bulk_convert_shards` helper
- `app/schemas.py` — `SkillUpIn` shape change (drop fodder, add nothing — cost is implicit)
- DB migration — one-shot collapse script: for each (account, template), keep one row (highest variance_net or oldest id), delete the rest; sum the deletions into `template_shards_json`. This runs as an Alembic migration since we're nuking the prod data anyway.

**Frontend**
- `frontend/src/routes/battle/BattleSetupRoute.tsx` — vanilla stacking logic becomes dead code; one row per template means `isVanilla` is no longer needed for stacking. Keep the rarity grouping. Each card now shows shard balance as a badge.
- New `frontend/src/routes/InventoryShardRoute.tsx` (or extend existing inventory) — list all shard balances grouped by rarity, with "convert to coins" buttons.
- Skill-up flow — wherever fodder picker lives, replace with "Spend N shards" confirm button. Locate during phase 3.
- Ascension flow — drop fodder UI path; keep shard path.

**Tests**
- New `tests/test_shard_remap_gacha.py` — pulling owned template doesn't grow `HeroInstance` count
- New `tests/test_shard_remap_skillup.py` — skill_up consumes shards, not rows
- Update existing `tests/test_skill_up_fodder.py` and `tests/test_summon.py`
- Existing `test_template_shards.py` — extend with bulk-convert

## Phases / commit boundaries

1. **Phase 1 — Schema + migration script** (~1 commit)
   - Alembic migration that walks each account, collapses dupes,
     credits shards. Idempotent (writes a marker so it doesn't run
     twice).
2. **Phase 2 — Gacha rewrite** (~1 commit)
   - Drop the `HeroInstance(...)` creation in summon.py's dupe branch.
     Test the count invariant.
3. **Phase 3 — skill_up rewrite** (~1 commit)
   - Replace `SkillUpIn.fodder_ids` with empty body. Add `SHARD_COST`
     schedule (e.g. `{1:5, 2:10, 3:20, 4:40}` to climb 1→2, 2→3, etc).
   - Remove `ascend` (fodder variant). Endpoint can 410 or just
     disappear; frontend isn't using it after phase 3 lands.
4. **Phase 4 — Frontend** (~1-2 commits)
   - Drop vanilla-stacking branch from BattleSetupRoute.
   - Add Shards inventory page or section.
   - Rewrite skill-up flow.
5. **Phase 5 — Bulk-convert + polish** (~1 commit)
   - Backend: `POST /shards/{template_code}/convert` exchanges N shards
     for coins at a published rate. Per-day cap to keep it honest.
   - Frontend: "Convert excess" buttons on the shards page.

## Open questions to revisit (not blocking)

- **First-pull mechanic.** Should the *very first* copy of a template
  still spawn a free `HeroInstance`? Or should it cost shards too
  (forcing players to collect N shards before "summoning" the hero
  proper)? Locked for v1: keep first-pull spawn. May revisit when the
  gacha pity rework lands.
- **Variance re-roll.** Currently variance is fixed on the canonical
  hero forever. Should shards spent on re-rolling become a sink? Not
  in scope for the remap; track separately.

## Rollback

We agreed no safety net. If something is wildly broken in prod, the
fix path is forward-only: another commit, not a revert (because the
migration would have already collapsed rows). Keep each phase
deployable in isolation and lean on the test suite to catch the
regressions before they ship.
