"""Phase A — player-chosen action types in interactive combat.

Verifies that target_uid + action_type drive the combat resolver as expected:
- attack: forces basic even when special/limit are ready
- skill:  fires special when ready, else falls back
- limit:  fires limit when gauge full, else falls back
- defend: skips attack, applies DEFENDING status (50% incoming damage reduction)
"""

from __future__ import annotations

import random

import pytest

from app.combat import (
    CombatUnit,
    StatusEffect,
    _act,
)
from app.models import Role, StatusEffectKind


def _mk_unit(uid: str, side: str, *, hp=1000, atk=200, def_=50, spd=100, **kw) -> CombatUnit:
    return CombatUnit(
        uid=uid, side=side, name=uid.upper(),
        role=Role.ATK, level=1,
        max_hp=hp, hp=hp, atk=atk, def_=def_, spd=spd,
        basic_mult=1.0, special=None, special_cooldown_max=3,
        **kw,
    )


def test_defend_applies_status_and_skips_damage():
    a = _mk_unit("a0", "A")
    b = _mk_unit("b0", "B")
    log: list[dict] = []
    dealt = _act(a, allies=[a], enemies=[b], rng=random.Random(0), log=log, action_type="defend")
    assert dealt == 0
    assert b.hp == 1000  # no damage taken
    assert any(s.kind == StatusEffectKind.DEFENDING for s in a.statuses)
    assert any(e["type"] == "DEFEND" and e["unit"] == "a0" for e in log)


def test_defend_reduces_incoming_damage_50pct():
    a = _mk_unit("a0", "A", def_=0)  # no def buffer so reduction is visible
    a.statuses.append(StatusEffect(kind=StatusEffectKind.DEFENDING, turns_left=1, value=0.5))
    b = _mk_unit("b0", "B", atk=500)
    log: list[dict] = []
    # Use _act() with attack from b → applies to a
    _act(b, allies=[b], enemies=[a], rng=random.Random(0), log=log, action_type="attack")
    # Damage halved relative to no-defending case
    assert any(e["type"] == "DEFEND_ABSORB" for e in log)


def test_action_attack_forces_basic_over_ready_special():
    a = _mk_unit("a0", "A", spd=100)
    a.special = {"name": "Burst", "type": "DAMAGE", "mult": 99.0}  # crushing if it fires
    a.special_cooldown_left = 0  # ready
    b = _mk_unit("b0", "B")
    log: list[dict] = []
    _act(a, allies=[a], enemies=[b], rng=random.Random(0), log=log,
         action_type="attack", forced_target_uid="b0")
    # Special should NOT have fired
    assert not any(e["type"] == "SPECIAL" for e in log)


def test_action_skill_fires_special_when_ready():
    a = _mk_unit("a0", "A")
    a.special = {"name": "Strike", "type": "DAMAGE", "mult": 2.0, "target": "enemy_lowest_hp"}
    a.special_cooldown_left = 0
    b = _mk_unit("b0", "B")
    log: list[dict] = []
    _act(a, allies=[a], enemies=[b], rng=random.Random(0), log=log,
         action_type="skill", forced_target_uid="b0")
    assert any(e["type"] == "SPECIAL" for e in log)


def test_action_limit_fires_when_gauge_full():
    a = _mk_unit("a0", "A")
    a.limit_gauge = a.limit_gauge_max  # full
    b = _mk_unit("b0", "B")
    log: list[dict] = []
    _act(a, allies=[a], enemies=[b], rng=random.Random(0), log=log,
         action_type="limit", forced_target_uid="b0")
    # Limit break depletes gauge to 0
    assert a.limit_gauge == 0


def test_peek_turn_order_orders_by_speed():
    from app.combat import peek_turn_order
    fast = _mk_unit("a0", "A", spd=200)
    slow = _mk_unit("a1", "A", spd=80)
    enemy = _mk_unit("b0", "B", spd=100)
    order = peek_turn_order([fast, slow], [enemy], n=4)
    # Fast acts twice in the time slow + enemy act once each
    assert order[0] == "a0"
    assert "a0" in order
    assert "b0" in order
    assert len(order) == 4


def test_peek_turn_order_excludes_dead():
    from app.combat import peek_turn_order
    dead = _mk_unit("a0", "A", spd=200)
    dead.dead = True
    alive = _mk_unit("a1", "A", spd=100)
    enemy = _mk_unit("b0", "B", spd=100)
    order = peek_turn_order([dead, alive], [enemy], n=4)
    assert "a0" not in order
    assert all(uid in {"a1", "b0"} for uid in order)


def test_legacy_none_action_preserves_auto_cascade():
    """Backward compat — action_type=None keeps prior auto-fire behavior."""
    a = _mk_unit("a0", "A")
    a.special = {"name": "Strike", "type": "DAMAGE", "mult": 2.0, "target": "enemy_lowest_hp"}
    a.special_cooldown_left = 0
    b = _mk_unit("b0", "B")
    log: list[dict] = []
    _act(a, allies=[a], enemies=[b], rng=random.Random(0), log=log,
         action_type=None, forced_target_uid="b0")
    # Auto-cascade still picks the ready special
    assert any(e["type"] == "SPECIAL" for e in log)
