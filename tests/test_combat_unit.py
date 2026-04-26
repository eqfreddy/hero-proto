"""Pure unit tests for the combat resolver."""

from __future__ import annotations

import random

from app.combat import (
    StatusEffect,
    build_unit,
    level_cap_for_stars,
    power_rating,
    scale_stat,
    simulate,
    team_faction_synergy,
)
from app.models import BattleOutcome, Faction, Role, StatusEffectKind


def _gremlin(uid: str, side: str, level: int = 1, stars: int = 1, faction: Faction | None = None):
    return build_unit(
        uid=uid, side=side,
        name="Gremlin", role=Role.ATK, level=level,
        base_hp=800, base_atk=90, base_def=60, base_spd=95,
        basic_mult=1.0, special=None, special_cooldown=0,
        stars=stars,
        faction=faction,
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


# --- New status effects: FREEZE, BURN, HEAL_BLOCK, REFLECT -----------------


def test_freeze_skips_turn_then_breaks_when_damaged() -> None:
    """FREEZE makes the unit skip its turn (like STUN) but the moment it takes
    damage the freeze breaks. STUN, by contrast, persists through hits."""
    rng = random.Random(0)
    target = _gremlin("a0", "A")
    target.statuses.append(StatusEffect(kind=StatusEffectKind.FREEZE, turns_left=3))
    attacker = _gremlin("b0", "B")
    log: list[dict] = []
    target.base_atk = target.atk; target.base_def = target.def_
    attacker.base_atk = attacker.atk; attacker.base_def = attacker.def_

    # Drive one action from each side.
    from app.combat import _act
    _act(target, allies=[target], enemies=[attacker], rng=rng, log=log)
    assert any(e.get("type") == "FROZEN" and e["unit"] == "a0" for e in log)
    # Attacker now hits target — FREEZE should break.
    _act(attacker, allies=[attacker], enemies=[target], rng=rng, log=log)
    assert not any(s.kind == StatusEffectKind.FREEZE for s in target.statuses)
    assert any(e.get("type") == "STATUS_BROKEN" and e["kind"] == "FREEZE" for e in log)


def test_burn_ticks_max_hp_fraction_per_actor_turn() -> None:
    """BURN ticks for max_hp * value at end of the unit's turn. Verifies the
    DoT machinery runs for BURN, not just POISON."""
    from app.combat import _tick_statuses
    u = _gremlin("a0", "A")
    u.statuses.append(StatusEffect(kind=StatusEffectKind.BURN, turns_left=2, value=0.10))
    log: list[dict] = []
    hp_before = u.hp
    _tick_statuses(u, log)
    expected = max(1, int(u.max_hp * 0.10))
    assert u.hp == hp_before - expected
    assert any(e.get("source") == "BURN" for e in log if e.get("type") == "DAMAGE")


def test_heal_block_suppresses_inbound_heal_and_lifesteal() -> None:
    from app.combat import _heal, _lifesteal
    target = _gremlin("a0", "A")
    target.hp = 100
    target.statuses.append(StatusEffect(kind=StatusEffectKind.HEAL_BLOCK, turns_left=2))
    log: list[dict] = []

    healed = _heal(None, target, 200, log)
    assert healed == 0
    assert target.hp == 100
    assert any(e.get("type") == "HEAL_BLOCKED" for e in log)

    # Lifesteal also routes through _heal so it must respect HEAL_BLOCK.
    target.has_lifesteal = True
    _lifesteal(target, 500, log)
    assert target.hp == 100  # still no progress


def test_reflect_returns_fraction_of_damage_to_attacker_no_recursion() -> None:
    """REFLECT bounces some incoming damage to the attacker. The bounced damage
    itself MUST NOT trigger reflect again — otherwise two REFLECT-buffed units
    would ping-pong forever."""
    from app.combat import _apply_damage
    attacker = _gremlin("b0", "B")
    defender = _gremlin("a0", "A")
    # Both sides have REFLECT — verify no infinite recursion / no stack overflow.
    attacker.statuses.append(StatusEffect(kind=StatusEffectKind.REFLECT, turns_left=3, value=0.5))
    defender.statuses.append(StatusEffect(kind=StatusEffectKind.REFLECT, turns_left=3, value=0.5))
    log: list[dict] = []

    attacker_hp_before = attacker.hp
    defender_hp_before = defender.hp
    _apply_damage(defender, 100, attacker=attacker, log=log)

    # Defender took 100. Attacker took ~50 reflected (no second-bounce).
    assert defender.hp == defender_hp_before - 100
    assert attacker.hp == attacker_hp_before - 50
    reflects = [e for e in log if e.get("type") == "REFLECT"]
    assert len(reflects) == 1


def test_cleanse_clears_new_statuses() -> None:
    """CLEANSE used to drop only POISON/DEF_DOWN/STUN; with the new statuses it
    must also strip BURN, FREEZE, HEAL_BLOCK so the cleanser actually counters them."""
    from app.combat import _act
    rng = random.Random(0)
    target = _gremlin("a0", "A")
    target.statuses.extend([
        StatusEffect(kind=StatusEffectKind.BURN, turns_left=2, value=0.05),
        StatusEffect(kind=StatusEffectKind.FREEZE, turns_left=2),
        StatusEffect(kind=StatusEffectKind.HEAL_BLOCK, turns_left=2),
    ])
    cleanser = _gremlin("a1", "A")
    cleanser.special = {"type": "CLEANSE", "target": "ally_lowest_hp"}
    cleanser.special_cooldown_max = 0
    cleanser.special_cooldown_left = 0
    target.base_atk = target.atk; target.base_def = target.def_
    cleanser.base_atk = cleanser.atk; cleanser.base_def = cleanser.def_
    log: list[dict] = []
    _act(cleanser, allies=[cleanser, target], enemies=[_gremlin("b0", "B")], rng=rng, log=log)
    assert target.statuses == []


# --- AOE_REVIVE -------------------------------------------------------------


def test_aoe_revive_brings_back_all_dead_allies() -> None:
    from app.combat import _act
    rng = random.Random(0)
    a0 = _gremlin("a0", "A"); a0.dead = True; a0.hp = 0
    a1 = _gremlin("a1", "A"); a1.dead = True; a1.hp = 0
    rezzer = _gremlin("a2", "A")
    rezzer.special = {"type": "AOE_REVIVE", "frac": 0.3}
    rezzer.special_cooldown_max = 5
    rezzer.special_cooldown_left = 0
    for u in (a0, a1, rezzer):
        u.base_atk = u.atk; u.base_def = u.def_
    log: list[dict] = []
    _act(rezzer, allies=[a0, a1, rezzer], enemies=[_gremlin("b0", "B")], rng=rng, log=log)

    assert not a0.dead and a0.hp > 0
    assert not a1.dead and a1.hp > 0
    rez_events = [e for e in log if e.get("type") == "REVIVE"]
    assert len(rez_events) == 2


def test_heal_block_blocks_revive() -> None:
    """HEAL_BLOCK on a corpse stops the rez. Lets a heal-blocker template
    counter a rez-stalling comp."""
    from app.combat import _revive
    target = _gremlin("a0", "A")
    target.dead = True; target.hp = 0
    target.statuses.append(StatusEffect(kind=StatusEffectKind.HEAL_BLOCK, turns_left=3))
    log: list[dict] = []
    revived = _revive(None, target, 0.5, log)
    assert revived is False
    assert target.dead is True
    assert any(e.get("type") == "REVIVE_BLOCKED" for e in log)


# --- Faction synergy --------------------------------------------------------


def test_no_synergy_with_fewer_than_three_same_faction() -> None:
    team = [
        _gremlin("a0", "A", faction=Faction.HELPDESK),
        _gremlin("a1", "A", faction=Faction.HELPDESK),
        _gremlin("a2", "A", faction=Faction.DEVOPS),
    ]
    assert team_faction_synergy(team) is None


def test_synergy_tiers_by_count() -> None:
    base = [_gremlin(f"a{i}", "A", faction=Faction.HELPDESK) for i in range(3)]
    syn3 = team_faction_synergy(base)
    assert syn3 == {"faction": Faction.HELPDESK, "count": 3, "atk_pct": 0.10, "def_pct": 0.0}

    base.append(_gremlin("a3", "A", faction=Faction.HELPDESK))
    syn4 = team_faction_synergy(base)
    assert syn4["count"] == 4 and syn4["atk_pct"] == 0.15 and syn4["def_pct"] == 0.05

    base.append(_gremlin("a4", "A", faction=Faction.HELPDESK))
    syn5 = team_faction_synergy(base)
    assert syn5["count"] == 5 and syn5["atk_pct"] == 0.20 and syn5["def_pct"] == 0.10


def test_simulate_logs_faction_synergy_and_buffs_atk() -> None:
    """End-to-end: a 3-faction team gets the +10% ATK bake into base_atk and
    the synergy event is logged so the replay viewer can show it."""
    rng = random.Random(0)
    syn_team = [_gremlin(f"a{i}", "A", faction=Faction.HELPDESK) for i in range(3)]
    base_atk_before = syn_team[0].atk
    plain_team = [_gremlin(f"b{i}", "B", faction=Faction.DEVOPS) for i in range(2)] + [
        _gremlin("b2", "B", faction=Faction.LEGACY)
    ]
    res = simulate(syn_team, plain_team, rng)
    # Synergy event present for side A only.
    syn_events = [e for e in res.log if e.get("type") == "FACTION_SYNERGY"]
    assert len(syn_events) == 1 and syn_events[0]["side"] == "A"
    # Each helpdesk hero now has buffed atk and base_atk reflects the bonus.
    assert syn_team[0].atk == max(1, int(round(base_atk_before * 1.10)))
    assert syn_team[0].base_atk == syn_team[0].atk


def test_aoe_heal_tops_up_all_allies_and_can_apply_buff() -> None:
    """AOE_HEAL heals every live ally and (with an `effect` field) applies
    a status to each. Dead allies are not healed; HEAL_BLOCK still suppresses
    the heal but the buff still goes through."""
    from app.combat import _act
    rng = random.Random(0)
    a0 = _gremlin("a0", "A"); a0.hp = 100
    a1 = _gremlin("a1", "A"); a1.hp = 200
    dead = _gremlin("a2", "A"); dead.hp = 0; dead.dead = True
    healer = _gremlin("a3", "A")
    healer.special = {
        "type": "AOE_HEAL",
        "frac": 0.30,
        "effect": {"kind": "ATK_UP", "turns": 3, "value": 0.20},
    }
    healer.special_cooldown_max = 4
    healer.special_cooldown_left = 0
    for u in (a0, a1, dead, healer):
        u.base_atk = u.atk; u.base_def = u.def_
    log: list[dict] = []
    _act(healer, allies=[a0, a1, dead, healer], enemies=[_gremlin("b0", "B")], rng=rng, log=log)

    # a0 and a1 healed (a0 from 100 closer to max, a1 from 200 closer to max).
    assert a0.hp > 100
    assert a1.hp > 200
    # The dead ally stays dead — AOE_HEAL doesn't revive.
    assert dead.dead is True and dead.hp == 0
    # Each live ally got the ATK_UP buff (including the healer themselves).
    from app.models import StatusEffectKind as K
    assert any(s.kind == K.ATK_UP for s in a0.statuses)
    assert any(s.kind == K.ATK_UP for s in a1.statuses)
    assert any(s.kind == K.ATK_UP for s in healer.statuses)


# --- BOSS_PHASE special type (raid bosses only) -----------------------------


def test_boss_phase_aoe_damages_all_enemies_and_applies_each_effect() -> None:
    """BOSS_PHASE = AOE damage + N statuses on enemies + N self-buffs in one
    cast. Verifies all three components fire on a single use."""
    from app.combat import _act
    rng = random.Random(42)
    boss = _gremlin("b0", "B")
    boss.special = {
        "type": "BOSS_PHASE",
        "name": "Bureaucratic Inertia",
        "mult": 1.2,
        "effects": [
            {"kind": "DEF_DOWN", "turns": 3, "value": 0.30},
            {"kind": "HEAL_BLOCK", "turns": 2, "value": 1.0},
        ],
        "self_effects": [{"kind": "REFLECT", "turns": 4, "value": 0.30}],
    }
    boss.special_cooldown_max = 5
    boss.special_cooldown_left = 0
    enemies = [_gremlin(f"a{i}", "A") for i in range(3)]
    for u in enemies + [boss]:
        u.base_atk = u.atk; u.base_def = u.def_
    log: list[dict] = []
    _act(boss, allies=[boss], enemies=enemies, rng=rng, log=log)

    # Every live enemy took damage and is now both DEF_DOWN-ed and HEAL_BLOCK-ed.
    boss_hits = [e for e in log if e.get("via") == "BOSS_PHASE"]
    assert len(boss_hits) == 3
    for e in enemies:
        assert e.hp < e.max_hp
        kinds = {s.kind for s in e.statuses}
        from app.models import StatusEffectKind as K
        assert K.DEF_DOWN in kinds and K.HEAL_BLOCK in kinds

    # Boss now has REFLECT on itself.
    from app.models import StatusEffectKind as K
    assert any(s.kind == K.REFLECT for s in boss.statuses)


def test_boss_phase_doesnt_apply_status_to_corpses() -> None:
    """Heroes killed by the AOE swing don't get DEF_DOWN/HEAL_BLOCK applied —
    matches the existing AOE_DAMAGE convention. (Status on a corpse would
    persist into a rez and confuse the viewer.)"""
    from app.combat import _act
    rng = random.Random(0)
    boss = _gremlin("b0", "B"); boss.atk = 100000  # one-shot anything alive
    boss.special = {
        "type": "BOSS_PHASE",
        "mult": 5.0,
        "effects": [{"kind": "BURN", "turns": 3, "value": 0.10}],
        "self_effects": [],
    }
    boss.special_cooldown_max = 0
    enemy = _gremlin("a0", "A"); enemy.hp = 1
    for u in (boss, enemy):
        u.base_atk = u.atk; u.base_def = u.def_
    log: list[dict] = []
    _act(boss, allies=[boss], enemies=[enemy], rng=rng, log=log)
    assert enemy.dead
    assert not any(s.kind.value == "BURN" for s in enemy.statuses)


# --- Hail-mary at ≤5% HP -----------------------------------------------------


def _hero(uid: str, side: str, role: Role, *, hp: int = 800, atk: int = 90):
    return build_unit(
        uid=uid, side=side,
        name=f"H_{uid}", role=role, level=1,
        base_hp=hp, base_atk=atk, base_def=60, base_spd=95,
        basic_mult=1.0, special=None, special_cooldown=0,
    )


def test_hail_mary_does_not_fire_above_threshold() -> None:
    """At >5% HP, end-of-turn doesn't trigger the desperation move."""
    from app.combat import _maybe_hail_mary
    actor = _hero("a0", "A", Role.ATK)
    actor.hp = int(actor.max_hp * 0.10)  # 10% — above 5% threshold
    actor.base_atk = actor.atk; actor.base_def = actor.def_
    enemies = [_hero("b0", "B", Role.DEF)]
    enemies[0].base_atk = enemies[0].atk; enemies[0].base_def = enemies[0].def_
    log: list[dict] = []
    _maybe_hail_mary(actor, allies=[actor], enemies=enemies, rng=random.Random(0), log=log)
    assert not any(e.get("type") == "HAIL_MARY" for e in log)
    assert actor.has_used_hail_mary is False


def test_hail_mary_atk_role_burst_damages_lowest_hp_enemy() -> None:
    from app.combat import _maybe_hail_mary
    actor = _hero("a0", "A", Role.ATK, atk=200)
    actor.hp = int(actor.max_hp * 0.04)  # under threshold
    actor.base_atk = actor.atk; actor.base_def = actor.def_
    full = _hero("b0", "B", Role.DEF, hp=2000)
    weak = _hero("b1", "B", Role.ATK, hp=2000); weak.hp = 100
    for u in (full, weak):
        u.base_atk = u.atk; u.base_def = u.def_
    log: list[dict] = []
    _maybe_hail_mary(actor, allies=[actor], enemies=[full, weak], rng=random.Random(0), log=log)
    hm = next((e for e in log if e.get("type") == "HAIL_MARY"), None)
    assert hm is not None and hm["role"] == "ATK"
    # Damage went to the lowest-HP target (weak), not to full.
    dmg_events = [e for e in log if e.get("type") == "DAMAGE" and e.get("via") == "HAIL_MARY"]
    assert len(dmg_events) == 1
    assert dmg_events[0]["target"] == "b1"
    assert weak.hp < 100 or weak.dead


def test_hail_mary_def_role_aoe_stuns_all_enemies() -> None:
    from app.combat import _maybe_hail_mary
    actor = _hero("a0", "A", Role.DEF, atk=120)
    actor.hp = int(actor.max_hp * 0.03)
    actor.base_atk = actor.atk; actor.base_def = actor.def_
    enemies = [_hero(f"b{i}", "B", Role.ATK, hp=2000) for i in range(3)]
    for u in enemies:
        u.base_atk = u.atk; u.base_def = u.def_
    log: list[dict] = []
    _maybe_hail_mary(actor, allies=[actor], enemies=enemies, rng=random.Random(0), log=log)
    # Each surviving enemy got STUN.
    from app.models import StatusEffectKind as K
    for e in enemies:
        if not e.dead:
            assert any(s.kind == K.STUN for s in e.statuses)


def test_hail_mary_sup_role_heals_team_and_buffs() -> None:
    from app.combat import _maybe_hail_mary
    actor = _hero("a0", "A", Role.SUP)
    actor.hp = int(actor.max_hp * 0.04)
    actor.base_atk = actor.atk; actor.base_def = actor.def_
    ally = _hero("a1", "A", Role.ATK); ally.hp = 200
    actor.hp_before = actor.hp
    for u in (ally,):
        u.base_atk = u.atk; u.base_def = u.def_
    log: list[dict] = []
    _maybe_hail_mary(actor, allies=[actor, ally], enemies=[_hero("b0", "B", Role.DEF)],
                     rng=random.Random(0), log=log)
    assert ally.hp > 200, "ally should have been healed"
    from app.models import StatusEffectKind as K
    assert any(s.kind == K.ATK_UP for s in ally.statuses)
    assert any(s.kind == K.ATK_UP for s in actor.statuses), "actor self-buffs too"


def test_hail_mary_only_fires_once_per_battle() -> None:
    """Even if the unit drops to ≤5% twice (heal then dropped again), the
    desperation move is one-shot."""
    from app.combat import _maybe_hail_mary
    actor = _hero("a0", "A", Role.ATK)
    actor.hp = int(actor.max_hp * 0.04)
    actor.base_atk = actor.atk; actor.base_def = actor.def_
    enemy = _hero("b0", "B", Role.DEF)
    enemy.base_atk = enemy.atk; enemy.base_def = enemy.def_
    log: list[dict] = []
    _maybe_hail_mary(actor, allies=[actor], enemies=[enemy], rng=random.Random(0), log=log)
    first_count = sum(1 for e in log if e.get("type") == "HAIL_MARY")
    assert first_count == 1
    # Heal back up + drop again — should NOT re-fire.
    actor.hp = actor.max_hp
    actor.hp = int(actor.max_hp * 0.02)
    _maybe_hail_mary(actor, allies=[actor], enemies=[enemy], rng=random.Random(0), log=log)
    second_count = sum(1 for e in log if e.get("type") == "HAIL_MARY")
    assert second_count == 1, "hail-mary must not re-fire"


# --- Unchanged regressions --------------------------------------------------


def test_trim_combat_log_short_unchanged() -> None:
    from app.combat import COMBAT_LOG_MAX_ENTRIES, trim_combat_log
    log = [{"i": i} for i in range(COMBAT_LOG_MAX_ENTRIES)]
    assert trim_combat_log(log) is log


def test_trim_combat_log_long_truncates_middle() -> None:
    from app.combat import COMBAT_LOG_MAX_ENTRIES, trim_combat_log
    log = [{"i": i} for i in range(COMBAT_LOG_MAX_ENTRIES * 3)]
    out = trim_combat_log(log)
    assert len(out) == COMBAT_LOG_MAX_ENTRIES
    # First and last entries preserved, marker in the middle.
    assert out[0] == {"i": 0}
    assert out[-1] == {"i": COMBAT_LOG_MAX_ENTRIES * 3 - 1}
    markers = [e for e in out if e.get("type") == "log_truncated"]
    assert len(markers) == 1 and markers[0]["skipped"] > 0
