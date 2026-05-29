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
