"""Constants for arena rewards and weekly leaderboard payouts.

Kept separate from config.Settings because these are flat tables, not
tunable knobs. Editing values here is a balance change requiring a code
review, not an environment-variable override.
"""
from __future__ import annotations

ARENA_REWARDS: dict[str, dict[str, int]] = {
    "win":  {"coins": 75, "shards": 3, "gems": 5},
    "loss": {"coins": 25, "shards": 0, "gems": 0},
    "draw": {"coins": 25, "shards": 0, "gems": 0},
}

# ±20% jitter on the coin reward only (matches stage-clear coin variance).
ARENA_REWARD_JITTER: float = 0.20

# (rank_lo, rank_hi, gems) — top 50 paid out at the Monday 00:00 UTC boundary.
ARENA_WEEKLY_PAYOUT: list[tuple[int, int, int]] = [
    (1, 1, 500),
    (2, 5, 250),
    (6, 20, 100),
    (21, 50, 50),
]

# Cosmetic frame granted to rank 1 only (idempotent — already-held is a no-op).
ARENA_CHAMPION_FRAME: str = "arena_champion"
