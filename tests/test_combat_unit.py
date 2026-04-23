"""Pure unit tests for the combat resolver."""

from __future__ import annotations

import random

from app.combat import build_unit, level_cap_for_stars, power_rating, scale_stat, simulate
from app.models import BattleOutcome, Role


def _gremlin(uid: str, side: str, level: int = 1, stars: int = 1):
    return build_unit(
        uid=uid, side=side,
        name="Gremlin", role=Role.ATK, level=level,
        base_hp=800, base_atk=90, base_def=60, base_spd=95,
        basic_mult=1.0, special=None, special_cooldown=0,
        stars=stars,
    )


def test_scale_stat_linear_with_level_and_stars() -> None:
    assert scale_stat(100, 1, 1) == 100
    assert scale_stat(100, 11, 1) == 200  # +10% per level
    assert scale_stat(100, 1, 5) == 160   # +15% per star over base


def test_level_cap_increases_with_stars() -> None:
    assert level_cap_for_stars(1) == 15
    assert level_cap_for_stars(5) == 35
    # Clamped sanely below/above legal range.
    assert level_cap_for_stars(0) == 15
    assert level_cap_for_stars(99) == 35


def test_power_rating_monotonic() -> None:
    base = power_rating(1000, 100, 80, 90)
    assert power_rating(2000, 100, 80, 90) > base
    assert power_rating(1000, 200, 80, 90) > base
    assert power_rating(1000, 100, 80, 180) > base


def test_simulate_reaches_an_outcome() -> None:
    rng = random.Random(1312)
    a = [_gremlin(f"a{i}", "A") for i in range(3)]
    b = [_gremlin(f"b{i}", "B") for i in range(3)]
    res = simulate(a, b, rng)
    assert res.outcome in (BattleOutcome.WIN, BattleOutcome.LOSS, BattleOutcome.DRAW)
    assert res.log[-1]["type"] == "END"
    assert res.ticks > 0


def test_stronger_team_wins_consistently() -> None:
    # 5-star level-30 team vs 1-star level-1 team.
    wins = 0
    for seed in range(20):
        rng = random.Random(seed)
        strong = [_gremlin(f"a{i}", "A", level=30, stars=5) for i in range(3)]
        weak = [_gremlin(f"b{i}", "B", level=1, stars=1) for i in range(3)]
        if simulate(strong, weak, rng).outcome == BattleOutcome.WIN:
            wins += 1
    assert wins == 20, f"strong team lost {20 - wins}/20 times"
