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
