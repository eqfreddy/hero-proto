"""Phase 3.1 — melee / ranged attack channel split.

Backend-only checkpoint: HeroTemplate.attack_kind threads through
build_unit + CombatUnit.attack_kind, and basic-attack log entries
echo `channel` so the replay viewer can render melee-lunge vs
ranged-projectile differently.

Phase 3.2 will add player-controlled targeting that consumes this
field. For now we just verify the data flow.
"""

from __future__ import annotations

import random


def _register(client) -> tuple[dict, int]:
    email = f"attkind+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    aid = client.get("/me", headers=hdr).json()["id"]
    return hdr, aid


def test_combat_unit_attack_kind_defaults_to_melee() -> None:
    """build_unit defaults to 'melee' when no attack_kind is supplied —
    keeps pre-Phase-3 callsites backwards-compatible."""
    from app.combat import build_unit
    from app.models import Role

    u = build_unit(
        uid="A0", side="A", name="X", role=Role.ATK,
        level=1, base_hp=100, base_atk=10, base_def=8, base_spd=50,
        basic_mult=1.0, special=None, special_cooldown=0,
    )
    assert u.attack_kind == "melee"


def test_combat_unit_accepts_ranged() -> None:
    from app.combat import build_unit
    from app.models import Role

    u = build_unit(
        uid="A0", side="A", name="X", role=Role.ATK,
        level=1, base_hp=100, base_atk=10, base_def=8, base_spd=50,
        basic_mult=1.0, special=None, special_cooldown=0,
        attack_kind="ranged",
    )
    assert u.attack_kind == "ranged"


def test_invalid_attack_kind_falls_back_to_melee() -> None:
    """A typo in seed data shouldn't blow up combat — fall back to
    'melee' rather than carry an unknown value through the resolver."""
    from app.combat import build_unit
    from app.models import Role

    u = build_unit(
        uid="A0", side="A", name="X", role=Role.ATK,
        level=1, base_hp=100, base_atk=10, base_def=8, base_spd=50,
        basic_mult=1.0, special=None, special_cooldown=0,
        attack_kind="trebuchet",
    )
    assert u.attack_kind == "melee"


def test_battle_log_emits_channel_on_basic_damage(client) -> None:
    """A real battle through /battles must include `channel` on every
    basic-attack DAMAGE log entry. Replay viewer keys off this field."""
    hdr, _ = _register(client)
    stages = client.get("/stages").json()
    tutorial = next(s for s in stages if s["code"] == "tutorial_first_ticket")
    heroes = client.get("/heroes/mine", headers=hdr).json()
    team = [h["id"] for h in sorted(heroes, key=lambda h: h["power"], reverse=True)[:3]]

    r = client.post("/battles", json={"stage_id": tutorial["id"], "team": team}, headers=hdr)
    assert r.status_code == 201, r.text
    log = r.json().get("log", [])
    basic_dmg = [e for e in log if e.get("type") == "DAMAGE" and e.get("via") == "BASIC"]
    assert basic_dmg, "expected at least one basic-attack DAMAGE entry"
    for entry in basic_dmg:
        assert "channel" in entry, entry
        assert entry["channel"] in ("melee", "ranged"), entry


def test_hero_template_seeded_with_default_melee(client) -> None:
    """Existing seeded templates get the 'melee' default via the
    server_default in the migration. Templates can opt into 'ranged'
    via seed updates without breaking anyone already running."""
    from app.db import SessionLocal
    from app.models import HeroTemplate
    db = SessionLocal()
    try:
        templates = db.query(HeroTemplate).limit(5).all()
        assert templates, "no hero templates seeded"
        for t in templates:
            assert getattr(t, "attack_kind", None) in ("melee", "ranged"), t.code
    finally:
        db.close()
