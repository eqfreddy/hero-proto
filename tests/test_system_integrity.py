from app.combat import CombatUnit, WEAKNESS_BREAK, OFF_TYPE_INTEGRITY_FACTOR, BURNOUT_MAX
from app.models import Faction, StatusEffectKind


def _mk(uid="e0", side="B", **kw):
    base = dict(
        uid=uid, side=side, name="t", role=__import__("app.models", fromlist=["Role"]).Role.ATK,
        level=10, max_hp=1000, hp=1000, atk=100, def_=50, spd=50, basic_mult=1.0,
        special=None, special_cooldown_max=0, base_atk=100, base_def=50,
    )
    base.update(kw)
    return CombatUnit(**base)


def test_combatunit_has_integrity_and_burnout_fields():
    u = _mk(integrity=150, integrity_max=150, weak_to=[Faction.HELPDESK], burnout=0)
    assert u.integrity == 150
    assert u.integrity_max == 150
    assert u.weak_to == [Faction.HELPDESK]
    assert u.burnout == 0


def test_vulnerable_status_enum_exists():
    assert StatusEffectKind.VULNERABLE == "VULNERABLE"


def test_tuning_constants_present():
    assert WEAKNESS_BREAK > 0
    assert 0 < OFF_TYPE_INTEGRITY_FACTOR < 1
    assert BURNOUT_MAX == 100


from app.combat import _is_weakness, _deplete_integrity


def test_is_weakness_true_when_attacker_faction_in_weak_to():
    atk = _mk(uid="a0", side="A", faction=Faction.HELPDESK)
    dfn = _mk(integrity=150, integrity_max=150, weak_to=[Faction.HELPDESK])
    assert _is_weakness(atk, dfn) is True


def test_is_weakness_false_for_off_type_or_no_bar():
    atk = _mk(uid="a0", side="A", faction=Faction.DEVOPS)
    dfn = _mk(integrity=150, integrity_max=150, weak_to=[Faction.HELPDESK])
    assert _is_weakness(atk, dfn) is False
    nobar = _mk(faction=Faction.HELPDESK)  # integrity_max defaults 0
    assert _is_weakness(atk, nobar) is False


def test_weakness_hit_drains_full_break():
    atk = _mk(uid="a0", side="A", faction=Faction.HELPDESK)
    dfn = _mk(integrity=150, integrity_max=150, weak_to=[Faction.HELPDESK])
    log = []
    _deplete_integrity(atk, dfn, log)
    assert dfn.integrity == 100  # 150 - WEAKNESS_BREAK(50)
    assert any(e["type"] == "INTEGRITY" for e in log)


def test_off_type_hit_drains_reduced():
    atk = _mk(uid="a0", side="A", faction=Faction.DEVOPS)
    dfn = _mk(integrity=150, integrity_max=150, weak_to=[Faction.HELPDESK])
    log = []
    _deplete_integrity(atk, dfn, log)
    assert dfn.integrity == 150 - int(50 * 0.15)  # 150 - 7 = 143


def test_no_bar_enemy_unaffected():
    atk = _mk(uid="a0", side="A", faction=Faction.HELPDESK)
    dfn = _mk()  # integrity_max 0
    log = []
    _deplete_integrity(atk, dfn, log)
    assert dfn.integrity == 0
    assert log == []


from app.combat import _apply_crash, FACTION_CRASH_DEBUFF


def test_crash_applies_stun_and_vulnerable():
    atk = _mk(uid="a0", side="A", faction=Faction.HELPDESK)
    dfn = _mk(integrity=0, integrity_max=150, weak_to=[Faction.HELPDESK])
    log = []
    _apply_crash(atk, dfn, log)
    kinds = {s.kind for s in dfn.statuses}
    assert StatusEffectKind.STUN in kinds
    assert StatusEffectKind.VULNERABLE in kinds
    assert any(e["type"] == "CRASH" for e in log)


def test_crash_flavored_debuff_matches_breaker_faction():
    atk = _mk(uid="a0", side="A", faction=Faction.LEGACY)
    dfn = _mk(integrity=0, integrity_max=150, weak_to=[Faction.LEGACY])
    log = []
    _apply_crash(atk, dfn, log)
    assert any(s.kind == FACTION_CRASH_DEBUFF[Faction.LEGACY] for s in dfn.statuses)


def test_full_debuff_map_covers_five_factions():
    for f in (Faction.HELPDESK, Faction.DEVOPS, Faction.EXECUTIVE,
              Faction.ROGUE_IT, Faction.LEGACY):
        assert f in FACTION_CRASH_DEBUFF


from app.combat import _tick_statuses, StatusEffect


def test_integrity_refills_when_vulnerable_expires():
    dfn = _mk(integrity=0, integrity_max=150, weak_to=[Faction.HELPDESK])
    dfn.statuses.append(StatusEffect(kind=StatusEffectKind.VULNERABLE, turns_left=1, value=0.30))
    log = []
    _tick_statuses(dfn, log)
    assert dfn.integrity == 150  # refilled to max
    assert not any(s.kind == StatusEffectKind.VULNERABLE for s in dfn.statuses)


def test_integrity_not_refilled_while_vulnerable_persists():
    dfn = _mk(integrity=0, integrity_max=150, weak_to=[Faction.HELPDESK])
    dfn.statuses.append(StatusEffect(kind=StatusEffectKind.VULNERABLE, turns_left=2, value=0.30))
    _tick_statuses(dfn, [])
    assert dfn.integrity == 0  # still crashed


from app.combat import _apply_damage


def test_vulnerable_amps_incoming_damage():
    dfn = _mk(hp=1000, max_hp=1000)
    dfn.statuses.append(StatusEffect(kind=StatusEffectKind.VULNERABLE, turns_left=2, value=0.30))
    dealt = _apply_damage(dfn, 100, attacker=None, log=[])
    assert dealt == 130  # +30%


def test_damaging_hit_depletes_integrity_then_crashes():
    atk = _mk(uid="a0", side="A", faction=Faction.HELPDESK)
    dfn = _mk(hp=1000, max_hp=1000, integrity=50, integrity_max=150, weak_to=[Faction.HELPDESK])
    log = []
    _apply_damage(dfn, 100, attacker=atk, log=log)  # weakness hit removes 50 -> 0 -> crash
    assert dfn.integrity == 0
    assert any(e["type"] == "CRASH" for e in log)


def test_no_integrity_change_when_no_attacker():
    dfn = _mk(hp=1000, max_hp=1000, integrity=150, integrity_max=150, weak_to=[Faction.HELPDESK])
    _apply_damage(dfn, 100, attacker=None, log=[])
    assert dfn.integrity == 150  # DoT / reflect (no attacker) doesn't break integrity
