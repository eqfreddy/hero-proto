"""Phase 2.6 — keep balance-notebook code paths from bitrotting.

The Jupyter notebooks in `analytics/` import directly from app.gacha,
app.combat, and app.seed. They've broken twice now because of renamed
symbols. We don't run nbconvert in CI (Jupyter pulls in too much), but
we *do* mirror the import shape + the smallest helpers so a rename
breaks a unit test instead of a notebook nobody opens until balance day.

These tests are "is the surface still there" checks, not deep balance
asserts.
"""

from __future__ import annotations


def test_gacha_notebook_import_surface() -> None:
    """analytics/gacha_ev.ipynb's first code cell imports `roll`, `RATES`,
    and reads `settings.gacha_pity_threshold`. Each must still exist."""
    from app.config import settings
    from app.gacha import RATES, roll

    assert callable(roll)
    assert isinstance(RATES, list) and len(RATES) >= 4
    assert isinstance(settings.gacha_pity_threshold, int)
    # Rate table must sum close to 1.0 — drift here breaks every gacha sim.
    total = sum(p for _, p in RATES)
    assert abs(total - 1.0) < 1e-6, f"RATES doesn't sum to 1.0: got {total}"


def test_combat_notebook_import_surface() -> None:
    """analytics/combat_dps.ipynb relies on app.combat.scale_stat /
    power_rating + app.seed.HERO_SEEDS being a non-empty list of dicts
    with the expected stat keys."""
    from app.combat import power_rating, scale_stat
    from app.seed import HERO_SEEDS

    assert callable(scale_stat)
    assert callable(power_rating)
    assert isinstance(HERO_SEEDS, list) and len(HERO_SEEDS) >= 10
    sample = HERO_SEEDS[0]
    for key in ("name", "rarity", "role", "base_hp", "base_atk", "base_def", "base_spd"):
        assert key in sample, key

    # Spot-check the math the notebook depends on.
    assert scale_stat(100, 1) == 100
    assert scale_stat(100, 10) > scale_stat(100, 1)
    assert power_rating(1000, 100, 80, 50) > 0


def test_balance_simulators_run_quickly() -> None:
    """Tiny in-process gacha simulation — same shape as the notebook's
    main loop. Catches resolver-level breakage before it hits Jupyter."""
    import random as _r

    from app.config import settings
    from app.gacha import roll

    rng = _r.Random(42)
    pity = 0
    pulls = []
    for _ in range(500):
        res = roll(pity, rng)
        pulls.append(str(res.rarity))
        pity = res.new_pity

    # 500 pulls must fire pity at least once (threshold is 50, and we
    # don't roll EPIC every 50 naturally).
    assert "EPIC" in pulls or "LEGENDARY" in pulls

    # No infinite-pity bug: counter must not climb past the threshold.
    assert pity <= settings.gacha_pity_threshold + 1
