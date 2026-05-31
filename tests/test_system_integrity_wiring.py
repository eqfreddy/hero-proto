import json

from app.db import SessionLocal
from app.models import HeroTemplate


def test_herotemplate_has_weakness_columns():
    db = SessionLocal()
    try:
        t = db.query(HeroTemplate).first()
        assert t is not None, "seed must have run"
        assert hasattr(t, "weak_to_json")
        assert hasattr(t, "integrity_base")
        assert isinstance(t.integrity_base, int)
    finally:
        db.close()


def test_unitsnapshot_has_integrity_burnout_fields():
    from app.schemas import UnitSnapshot
    f = UnitSnapshot.model_fields
    assert "integrity" in f and "integrity_max" in f
    assert "burnout" in f and "crashed" in f


def test_pendingturn_exposes_delete_targets():
    from app.schemas import PendingTurnOut
    assert "valid_delete_targets" in PendingTurnOut.model_fields


def test_interactiveactin_accepts_delete_action():
    # The HTTP request schema must accept action_type="delete" or the Delete
    # finisher 422s before reaching the resolver (frontend button + walkthrough).
    from app.schemas import InteractiveActIn
    m = InteractiveActIn(turn_number=1, target_uid="B0", action_type="delete")
    assert m.action_type == "delete"


def test_enemy_unit_gets_integrity_and_weakness():
    from app.models import HeroTemplate
    from app.routers.battles import _unit_from_template
    db = SessionLocal()
    try:
        t = db.query(HeroTemplate).filter(HeroTemplate.integrity_base > 0).first()
        assert t is not None
        u = _unit_from_template(t, level=10, side="B", idx=0)
        assert u.integrity_max == t.integrity_base
        assert u.integrity == t.integrity_base  # starts full
        assert [f.value for f in u.weak_to] == json.loads(t.weak_to_json)
    finally:
        db.close()


def test_seed_assigns_weaknesses_and_integrity():
    from app.models import Faction
    db = SessionLocal()
    try:
        templates = db.query(HeroTemplate).all()
        with_weakness = [t for t in templates if json.loads(t.weak_to_json or "[]")]
        with_bar = [t for t in templates if t.integrity_base > 0]
        assert len(with_weakness) >= len(templates) // 2
        assert len(with_bar) >= len(templates) // 2
        valid = {f.value for f in Faction}
        for t in with_weakness:
            for w in json.loads(t.weak_to_json):
                assert w in valid
    finally:
        db.close()


# --- Task 5: snapshots surface crash/integrity; submit accepts "delete" -------

def _crashed_enemy(uid="B0"):
    from app.combat import CombatUnit, StatusEffect
    from app.models import StatusEffectKind, Faction, Role
    return CombatUnit(
        uid=uid, side="B", name="e", role=Role.ATK, level=10,
        max_hp=1000, hp=200, atk=100, def_=50, spd=50, basic_mult=1.0,
        special=None, special_cooldown_max=0, base_atk=100, base_def=50,
        integrity=0, integrity_max=150, weak_to=[Faction.HELPDESK], burnout=40,
        statuses=[StatusEffect(kind=StatusEffectKind.VULNERABLE, turns_left=2, value=0.30)],
    )


def test_snapshot_builders_mark_crashed():
    from app.interactive import _unit_snapshot
    from app.routers.battles import _unit_snap
    from app.routers.raids import _unit_snap_r
    e = _crashed_enemy()
    for snap in (_unit_snapshot(e), _unit_snap(e), _unit_snap_r(e)):
        assert snap["crashed"] is True
        assert snap["integrity_max"] == 150
        assert snap["burnout"] == 40


def test_delete_in_allowed_action_types():
    import app.interactive as interactive
    assert "delete" in interactive.ALLOWED_ACTION_TYPES


def test_advance_session_rejects_unknown_action_type():
    import app.interactive as interactive

    class _Stub:
        status = "WAITING"
        turn_number = 1
    try:
        interactive.advance_session(
            _Stub(), turn_number=1, target_uid="B0", action_type="bogus"
        )
        raised = False
    except ValueError:
        raised = True
    assert raised, "unknown action_type must be rejected"
