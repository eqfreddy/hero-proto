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
