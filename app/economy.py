"""Energy regen, XP/leveling, battle reward helpers. No DB queries — mutate passed objects."""

from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime

from app.combat import level_cap_for_stars
from app.config import settings
from app.models import Account, HeroInstance, Stage, utcnow


# --- Energy -----------------------------------------------------------------


def compute_energy(account: Account, now: datetime | None = None) -> int:
    now = now or utcnow()
    elapsed = (now - account.energy_last_tick_at).total_seconds()
    if elapsed < 0:
        elapsed = 0
    gained = int(elapsed // settings.energy_regen_seconds)
    # The cap only governs passive regeneration. If something (admin grants,
    # LiveOps rewards, or test fixtures) has pushed stored > cap, that surplus
    # is preserved; regen simply can't push a below-cap account above cap.
    if account.energy_stored >= settings.energy_cap:
        return account.energy_stored
    return min(settings.energy_cap, account.energy_stored + gained)


def consume_energy(account: Account, amount: int, now: datetime | None = None) -> bool:
    """Atomically flush regen + spend. Returns True if the amount was deducted."""
    now = now or utcnow()
    current = compute_energy(account, now)
    if current < amount:
        # Still refresh the stored snapshot so we don't leak phantom energy later.
        account.energy_stored = current
        account.energy_last_tick_at = now
        return False
    account.energy_stored = current - amount
    account.energy_last_tick_at = now
    return True


# --- XP / levels ------------------------------------------------------------


def xp_for_level(level: int) -> int:
    # Quadratic-ish curve: 100 xp for level 1→2, 220 for 2→3, ...
    return 60 + 40 * level + 10 * level * level


def apply_xp(hero: HeroInstance, gained: int) -> tuple[int, int]:
    """Add XP, level up until XP bucket empty or star-gated level cap hit."""
    levels = 0
    cap = level_cap_for_stars(hero.stars)
    hero.xp += gained
    while hero.level < cap:
        need = xp_for_level(hero.level)
        if hero.xp < need:
            break
        hero.xp -= need
        hero.level += 1
        levels += 1
    if hero.level >= cap:
        hero.xp = 0  # hard cap: no overflow storage
    return levels, hero.level


# --- Rewards ----------------------------------------------------------------


@dataclass
class BattleRewards:
    coins: int
    gems: int
    shards: int
    xp_per_hero: int
    first_clear: bool
    level_ups: dict[int, int]  # hero_instance_id -> levels gained

    def as_json(self) -> dict:
        return {
            "coins": self.coins,
            "gems": self.gems,
            "shards": self.shards,
            "xp_per_hero": self.xp_per_hero,
            "first_clear": self.first_clear,
            "level_ups": self.level_ups,
        }


def award_rewards(
    account: Account,
    stage: Stage,
    heroes_on_team: list[HeroInstance],
    won: bool,
    first_clear: bool,
    rng: random.Random,
    liveops_multiplier: float = 1.0,
) -> BattleRewards:
    if won:
        coins = stage.coin_reward + rng.randint(0, stage.coin_reward // 5)
        xp = settings.xp_per_battle_win
        # Small random gem/shard drop even on repeat clears.
        gems = rng.randint(0, 5)
        shards = 1 if rng.random() < 0.2 else 0
    else:
        coins = max(10, stage.coin_reward // 5)
        xp = settings.xp_per_battle_loss
        gems = 0
        shards = 0

    if first_clear and won:
        gems += stage.first_clear_gems
        shards += stage.first_clear_shards

    # LiveOps multiplier applies to win rewards only (loss consolation stays flat).
    if won and liveops_multiplier != 1.0:
        coins = int(round(coins * liveops_multiplier))
        xp = int(round(xp * liveops_multiplier))
        gems = int(round(gems * liveops_multiplier))
        shards = int(round(shards * liveops_multiplier))

    account.coins += coins
    account.gems += gems
    account.shards += shards

    level_ups: dict[int, int] = {}
    for h in heroes_on_team:
        if h.level >= level_cap_for_stars(h.stars):
            continue
        lv, _ = apply_xp(h, xp)
        if lv:
            level_ups[h.id] = lv

    return BattleRewards(
        coins=coins,
        gems=gems,
        shards=shards,
        xp_per_hero=xp,
        first_clear=first_clear and won,
        level_ups=level_ups,
    )


# --- Stage clear tracking ---------------------------------------------------


def load_cleared(account: Account) -> set[str]:
    try:
        arr = json.loads(account.stages_cleared_json or "[]")
    except json.JSONDecodeError:
        return set()
    return {str(x) for x in arr if isinstance(x, str)}


def save_cleared(account: Account, cleared: set[str]) -> None:
    account.stages_cleared_json = json.dumps(sorted(cleared))


def mark_cleared(account: Account, stage_code: str) -> bool:
    cleared = load_cleared(account)
    if stage_code in cleared:
        return False
    cleared.add(stage_code)
    save_cleared(account, cleared)
    return True
