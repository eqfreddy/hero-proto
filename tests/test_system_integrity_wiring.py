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
