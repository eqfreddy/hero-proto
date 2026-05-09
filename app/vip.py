"""VIP tiers — cumulative-spend retention loop.

1 USD cent of paid purchases = 1 VIP XP. Tiers unlock permanent perks
(AFK cap extension, daily gem drip, auto-battle speed boost, frames,
extra refreshes). Whales love the prestige meter; new players see a
clear "spend X to unlock Y" upgrade path.

VIP_TIERS is the single source of truth. Each row:
  level, xp_required (cumulative cents), perks {code -> value}, label.
Perks are derived by walking from level 0 upward and merging — higher
tiers stack on lower ones.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from app.models import Account, utcnow

# Cumulative-spend thresholds. xp_required is total $cents at-or-above for
# this tier to be active.
VIP_TIERS: list[dict[str, Any]] = [
    {"level": 1,  "xp_required": 100,    "label": "Bronze",     "perks": {"afk_cap_hours": 13, "daily_drip_gems": 10}},
    {"level": 2,  "xp_required": 500,    "label": "Silver",     "perks": {"afk_cap_hours": 14, "daily_drip_gems": 25}},
    {"level": 3,  "xp_required": 2000,   "label": "Gold",       "perks": {"afk_cap_hours": 16, "daily_drip_gems": 25, "auto_battle_speed": 2}},
    {"level": 4,  "xp_required": 5000,   "label": "Platinum",   "perks": {"afk_cap_hours": 18, "daily_drip_gems": 50, "auto_battle_speed": 2, "extra_energy_refresh": 1}},
    {"level": 5,  "xp_required": 10000,  "label": "Diamond",    "perks": {"afk_cap_hours": 20, "daily_drip_gems": 50, "auto_battle_speed": 3, "extra_energy_refresh": 1}},
    {"level": 6,  "xp_required": 25000,  "label": "Mythril",    "perks": {"afk_cap_hours": 22, "daily_drip_gems": 75, "auto_battle_speed": 3, "extra_energy_refresh": 2, "daily_quest_skip": 1}},
    {"level": 7,  "xp_required": 50000,  "label": "Obsidian",   "perks": {"afk_cap_hours": 24, "daily_drip_gems": 100, "auto_battle_speed": 4, "extra_energy_refresh": 2, "daily_quest_skip": 1}},
    {"level": 8,  "xp_required": 100000, "label": "Onyx",       "perks": {"afk_cap_hours": 24, "daily_drip_gems": 150, "auto_battle_speed": 4, "extra_energy_refresh": 3, "daily_quest_skip": 2, "cosmetic_frame": "frame_vip_gold"}},
    {"level": 9,  "xp_required": 250000, "label": "Crown",      "perks": {"afk_cap_hours": 30, "daily_drip_gems": 200, "auto_battle_speed": 5, "extra_energy_refresh": 3, "daily_quest_skip": 2, "cosmetic_frame": "frame_vip_gold", "extra_hero_slots": 5}},
    {"level": 10, "xp_required": 500000, "label": "Apex",       "perks": {"afk_cap_hours": 36, "daily_drip_gems": 300, "auto_battle_speed": 5, "extra_energy_refresh": 5, "daily_quest_skip": 3, "cosmetic_frame": "frame_vip_platinum", "extra_hero_slots": 10}},
]

DEFAULT_PERKS = {
    "afk_cap_hours": 12,
    "daily_drip_gems": 0,
    "auto_battle_speed": 1,
    "extra_energy_refresh": 0,
    "daily_quest_skip": 0,
    "cosmetic_frame": "",
    "extra_hero_slots": 0,
}


def level_for_xp(xp: int) -> int:
    lvl = 0
    for row in VIP_TIERS:
        if xp >= row["xp_required"]:
            lvl = row["level"]
        else:
            break
    return lvl


def perks_for_level(level: int) -> dict[str, Any]:
    """Walk tiers up to `level` and merge perks. Higher tier overrides lower."""
    out = dict(DEFAULT_PERKS)
    for row in VIP_TIERS:
        if row["level"] > level:
            break
        out.update(row["perks"])
    return out


def perks_for_account(account: Account) -> dict[str, Any]:
    return perks_for_level(level_for_xp(int(account.vip_xp or 0)))


def next_tier(level: int) -> dict[str, Any] | None:
    for row in VIP_TIERS:
        if row["level"] > level:
            return row
    return None


def status(account: Account) -> dict[str, Any]:
    xp = int(account.vip_xp or 0)
    lvl = level_for_xp(xp)
    nxt = next_tier(lvl)
    return {
        "level": lvl,
        "label": next((r["label"] for r in VIP_TIERS if r["level"] == lvl), "Unranked"),
        "xp": xp,
        "xp_to_next": (nxt["xp_required"] - xp) if nxt else 0,
        "next_label": nxt["label"] if nxt else None,
        "next_perks": nxt["perks"] if nxt else None,
        "perks": perks_for_account(account),
        "drip_available_today": _drip_available(account),
    }


def _today_utc_midnight() -> datetime:
    n = utcnow()
    return datetime(n.year, n.month, n.day)


def _drip_available(account: Account) -> bool:
    perks = perks_for_account(account)
    if int(perks.get("daily_drip_gems", 0)) <= 0:
        return False
    last = account.vip_last_drip_at
    return last is None or last < _today_utc_midnight()


def claim_daily_drip(account: Account) -> int:
    """Grant the VIP daily gem drip if available. Returns gems granted."""
    if not _drip_available(account):
        return 0
    gems = int(perks_for_account(account).get("daily_drip_gems", 0))
    if gems <= 0:
        return 0
    account.gems = int(account.gems or 0) + gems
    account.vip_last_drip_at = _today_utc_midnight()
    return gems


def grant_xp(account: Account, cents_paid: int) -> int:
    """Add cumulative-spend XP. Returns the new total."""
    if cents_paid <= 0:
        return int(account.vip_xp or 0)
    account.vip_xp = int(account.vip_xp or 0) + int(cents_paid)
    return account.vip_xp
