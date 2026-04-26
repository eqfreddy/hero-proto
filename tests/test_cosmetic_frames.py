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


def test_roster_partial_renders_active_frame_class(client) -> None:
    """The /app/partials/roster HTML should include the active frame's
    CSS class on #roster-grid so the css overrides apply."""
    hdr, aid = _register(client)
    _grant_frame(aid, "frame_terminal_green")
    client.post("/me/cosmetic-frame", json={"code": "frame_terminal_green"}, headers=hdr)
    r = client.get("/app/partials/roster", headers=hdr)
    assert r.status_code == 200
    assert "frame-frame_terminal_green" in r.text
    assert "has-frame" in r.text


def test_roster_partial_no_frame_class_when_none_active(client) -> None:
    """The grid container should NOT carry `has-frame` when no frame is
    equipped. The static CSS rules for individual frames stay in place
    (they're declarative and only fire when the parent class matches),
    so we only assert the dynamic class is absent."""
    hdr, _ = _register(client)
    r = client.get("/app/partials/roster", headers=hdr)
    assert r.status_code == 200
    assert 'class=""' in r.text or 'id="roster-grid" class=""' in r.text or 'class="active"' in r.text
    # Specifically, the grid-container class attribute should not include
    # "has-frame" or "frame-frame_*" — those are the *active-frame* hooks.
    import re
    grid_match = re.search(r'id="roster-grid"\s+class="([^"]*)"', r.text)
    if grid_match:
        cls = grid_match.group(1)
        assert "has-frame" not in cls, cls
        assert "frame-frame_" not in cls, cls
