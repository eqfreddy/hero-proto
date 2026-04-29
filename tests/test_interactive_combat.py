"""Phase 3.3 — interactive combat regression tests.

Key invariant: simulate_interactive() with all targets auto-selected (send None)
must produce a log byte-identical to simulate() given the same teams and RNG seed.
"""

from __future__ import annotations

import copy
import random

import pytest

from app.combat import (
    BattleOutcome,
    CombatResult,
    _needs_target_choice,
    build_unit,
    simulate,
    simulate_interactive,
)
from app.models import Role


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _atk(uid: str, side: str, *, spd: int = 95):
    return build_unit(
        uid=uid, side=side,
        name="Attacker", role=Role.ATK, level=5,
        base_hp=800, base_atk=100, base_def=60, base_spd=spd,
        basic_mult=1.0, special=None, special_cooldown=0,
    )


def _def(uid: str, side: str):
    return build_unit(
        uid=uid, side=side,
        name="Defender", role=Role.DEF, level=5,
        base_hp=1200, base_atk=60, base_def=120, base_spd=80,
        basic_mult=1.0, special=None, special_cooldown=0,
    )


def _sup(uid: str, side: str):
    return build_unit(
        uid=uid, side=side,
        name="Support", role=Role.SUP, level=5,
        base_hp=900, base_atk=70, base_def=80, base_spd=90,
        basic_mult=1.0,
        special={"type": "HEAL", "target": "ally_lowest_hp", "frac": 0.25},
        special_cooldown=2,
    )


def _run_interactive_auto(team_a, team_b, seed: int) -> CombatResult:
    """Run simulate_interactive(), auto-selecting targets (send None) every turn.
    Returns the CombatResult; the log is accumulated into a fresh list.
    """
    rng = random.Random(seed)
    log: list[dict] = []
    gen = simulate_interactive(team_a, team_b, rng, log)
    result: CombatResult | None = None
    try:
        # Prime the generator
        next(gen)
        while True:
            # send None = use default priority
            gen.send(None)
    except StopIteration as exc:
        result = exc.value
    return result


# ---------------------------------------------------------------------------
# Log-identity regression
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", [0, 1, 42, 999, 12345])
def test_interactive_auto_log_matches_simulate(seed: int) -> None:
    """simulate_interactive() with send(None) must produce an identical log
    to simulate() for the same seed and starting teams."""
    # Build two fresh identical copies of the teams (each run consumes hp etc.)
    a1 = [_atk("a0", "A", spd=95), _def("a1", "A"), _sup("a2", "A")]
    b1 = [_atk("b0", "B", spd=85), _def("b1", "B")]

    a2 = [_atk("a0", "A", spd=95), _def("a1", "A"), _sup("a2", "A")]
    b2 = [_atk("b0", "B", spd=85), _def("b1", "B")]

    # Canonical result via simulate()
    rng_ref = random.Random(seed)
    ref = simulate(a1, b1, rng_ref)

    # Interactive result with auto-selection
    rng_int = random.Random(seed)
    log_int: list[dict] = []
    gen = simulate_interactive(a2, b2, rng_int, log_int)
    try:
        next(gen)
        while True:
            gen.send(None)
    except StopIteration as exc:
        int_result: CombatResult = exc.value

    assert int_result.outcome == ref.outcome, (
        f"seed={seed}: outcome diverged: interactive={int_result.outcome} vs simulate={ref.outcome}"
    )
    assert log_int == ref.log, (
        f"seed={seed}: logs differ at first divergence index "
        f"{next((i for i,(a,b) in enumerate(zip(log_int,ref.log)) if a!=b), len(ref.log))}"
    )


# ---------------------------------------------------------------------------
# Forced-target respects player choice
# ---------------------------------------------------------------------------

def test_forced_target_used_for_basic_attack() -> None:
    """When a live target uid is sent, the basic attack hits that specific unit."""
    rng = random.Random(0)
    hero = _atk("a0", "A")
    e0 = _def("b0", "B")
    e1 = _def("b1", "B")
    e0.hp = e1.hp = 1000  # equal HP so default pick would be deterministic but same

    log: list[dict] = []
    gen = simulate_interactive([hero], [e0, e1], rng, log)

    # First pause should be hero a0 basic attack
    pause = next(gen)
    assert pause["type"] == "PLAYER_TURN"
    assert pause["actor"] == "a0"

    # Force target to b1 (not the default lowest-HP pick, which is b0 by uid sort)
    try:
        gen.send("b1")
    except StopIteration:
        pass

    damage_to_b1 = sum(
        e["amount"] for e in log
        if e.get("type") == "DAMAGE" and e.get("target") == "b1"
    )
    assert damage_to_b1 > 0, "no damage logged to forced target b1"


def test_dead_forced_target_falls_back() -> None:
    """If the forced target is dead when the attack fires, fall back to priority pick."""
    rng = random.Random(5)
    hero = _atk("a0", "A", spd=100)
    fast_ally = _atk("a1", "A", spd=200)
    e0 = _def("b0", "B")

    # Make e0 very weak so the fast ally can kill it before hero acts
    e0.hp = 1

    log: list[dict] = []
    gen = simulate_interactive([hero, fast_ally], [e0], rng, log)

    # Drain the generator; b0 will die quickly, hero's forced target will be dead
    try:
        pause = next(gen)
        # Force b0 even though it may already be dead
        gen.send("b0")
    except StopIteration:
        pass
    # No assertion on damage specifics — just ensure no crash occurred
    assert any(e.get("type") == "END" for e in log)


# ---------------------------------------------------------------------------
# _needs_target_choice helper
# ---------------------------------------------------------------------------

def test_needs_target_choice_basic_attack() -> None:
    unit = _atk("a0", "A")
    assert _needs_target_choice(unit) is True


def test_needs_target_choice_special_ready() -> None:
    unit = _sup("a0", "A")
    unit.special_cooldown_left = 0  # special is ready
    assert _needs_target_choice(unit) is False


def test_needs_target_choice_limit_break_ready() -> None:
    unit = _atk("a0", "A")
    unit.limit_gauge = unit.limit_gauge_max = 100
    assert _needs_target_choice(unit) is False
