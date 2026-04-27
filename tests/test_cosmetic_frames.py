"""Phase 2.4 — POST /me/cosmetic-frame equips an owned frame.

Verifies the wiring between owning a frame (via shop / IAP) and the
visible roster border. Backend stores `active_cosmetic_frame`; the
roster partial renders the corresponding CSS class.
"""

from __future__ import annotations

import json
import random


def _register(client) -> tuple[dict, int]:
    email = f"frame+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    aid = client.get("/me", headers=hdr).json()["id"]
    return hdr, aid


def _grant_frame(aid: int, code: str) -> None:
    """Direct-DB grant — bypasses the IAP path."""
    from app.db import SessionLocal
    from app.models import Account
    db = SessionLocal()
    try:
        a = db.get(Account, aid)
        try:
            owned = json.loads(a.cosmetic_frames_json or "[]")
        except json.JSONDecodeError:
            owned = []
        if code not in owned:
            owned.append(code)
        a.cosmetic_frames_json = json.dumps(owned, separators=(",", ":"))
        db.commit()
    finally:
        db.close()


def test_default_active_frame_is_empty(client) -> None:
    hdr, _ = _register(client)
    me = client.get("/me", headers=hdr).json()
    assert me["active_cosmetic_frame"] == ""
    assert me["cosmetic_frames"] == []


def test_equip_owned_frame_succeeds(client) -> None:
    hdr, aid = _register(client)
    _grant_frame(aid, "frame_neon_cubicle")
    r = client.post("/me/cosmetic-frame", json={"code": "frame_neon_cubicle"}, headers=hdr)
    assert r.status_code == 200, r.text
    assert r.json()["active_cosmetic_frame"] == "frame_neon_cubicle"
    me = client.get("/me", headers=hdr).json()
    assert me["active_cosmetic_frame"] == "frame_neon_cubicle"


def test_equip_unowned_frame_returns_409(client) -> None:
    hdr, _ = _register(client)
    r = client.post("/me/cosmetic-frame", json={"code": "frame_legacy_brass"}, headers=hdr)
    assert r.status_code == 409
    assert "not owned" in r.text.lower()


def test_clear_frame_with_empty_string(client) -> None:
    """Empty `code` removes the active frame back to rarity-border default."""
    hdr, aid = _register(client)
    _grant_frame(aid, "frame_neon_cubicle")
    client.post("/me/cosmetic-frame", json={"code": "frame_neon_cubicle"}, headers=hdr)
    r = client.post("/me/cosmetic-frame", json={"code": ""}, headers=hdr)
    assert r.status_code == 200
    assert r.json()["active_cosmetic_frame"] == ""
    me = client.get("/me", headers=hdr).json()
    assert me["active_cosmetic_frame"] == ""


