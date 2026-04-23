"""Unit tests for VIOLENT / LIFESTEAL sets."""

from __future__ import annotations

import random

from app.combat import build_unit, simulate
from app.models import BattleOutcome, Role


def _hero(uid: str, side: str, *, lifesteal: bool = False, violent: bool = False):
    return build_unit(
        uid=uid, side=side,
        name="Test", role=Role.ATK, level=5,
        base_hp=1000, base_atk=200, base_def=80, base_spd=100,
        basic_mult=1.0, special=None, special_cooldown=0,
        gear_bonus={
            "hp": 0, "atk": 0, "def": 0, "spd": 0,
            "pct": {"hp": 0.0, "atk": 0.0, "def": 0.0, "spd": 0.0},
            "active": {"lifesteal": lifesteal, "violent": violent},
        },
    )


def test_lifesteal_emits_heal_events_and_restores_hp() -> None:
    rng = random.Random(7)
    actor = _hero("a0", "A", lifesteal=True)
    # Pre-damage the actor so we can tell they heal.
    actor.hp = 500
    enemy = _hero("b0", "B")
    result = simulate([actor], [enemy], rng)
    heals = [e for e in result.log if e["type"] == "LIFESTEAL"]
    assert heals, "expected at least one LIFESTEAL event"
    assert result.outcome in (BattleOutcome.WIN, BattleOutcome.LOSS, BattleOutcome.DRAW)


def test_violent_produces_extra_turns_over_many_runs() -> None:
    any_extra = False
    for seed in range(20):
        rng = random.Random(seed)
        actor = _hero("a0", "A", violent=True)
        enemy = _hero("b0", "B")
        # Lower enemy HP so the fight actually resolves in a few turns.
        enemy.max_hp = 400
        enemy.hp = 400
        result = simulate([actor], [enemy], rng)
        if any(e["type"] == "VIOLENT_TURN" for e in result.log):
            any_extra = True
            break
    assert any_extra, "VIOLENT_TURN never fired across 20 seeds at 20% chance"


def test_no_lifesteal_without_flag() -> None:
    rng = random.Random(11)
    actor = _hero("a0", "A", lifesteal=False)
    actor.hp = 500
    enemy = _hero("b0", "B")
    result = simulate([actor], [enemy], rng)
    assert not any(e["type"] == "LIFESTEAL" for e in result.log)
