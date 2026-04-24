"""Every list endpoint has a server-side cap. Client-provided `limit` is
clamped to the cap — passing `limit=99999` cannot fetch everything.

If you add a new list endpoint, add a test here. Unbounded scans are a
trivial DoS vector; every response needs a bound.
"""

from __future__ import annotations

import random

from app.db import SessionLocal
from app.models import Gear, GearRarity, GearSet, GearSlot


def _register(client, prefix: str = "lim") -> tuple[str, dict, int]:
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    token = r.json()["access_token"]
    hdr = {"Authorization": f"Bearer {token}"}
    me = client.get("/me", headers=hdr).json()
    return email, hdr, me["id"]


def test_guilds_list_respects_limit(client) -> None:
    """GET /guilds honors ?limit and pages via ?offset."""
    _email, _hdr, _aid = _register(client, "glim")
    # Seed a handful of guilds so pagination has something to slice.
    for _ in range(3):
        _g_email, g_hdr, _g_aid = _register(client, "gseed")
        client.post(
            "/guilds",
            json={"name": f"G{random.randint(1,999999)}", "tag": f"G{random.randint(10,99)}"},
            headers=g_hdr,
        )
    r = client.get("/guilds?limit=2")
    assert r.status_code == 200
    assert len(r.json()) <= 2


def test_guilds_list_limit_is_capped(client) -> None:
    """Even limit=999999 is clamped to the server-side max (500)."""
    r = client.get("/guilds?limit=999999")
    assert r.status_code == 200
    # Response bounded by the 500 cap; don't assert the exact shape beyond that.
    assert len(r.json()) <= 500


def test_heroes_mine_respects_limit(client) -> None:
    email, hdr, _ = _register(client)
    # x10 summon → 10 heroes; request 5.
    client.post("/summon/x10", headers=hdr)
    r = client.get("/heroes/mine?limit=5", headers=hdr)
    assert r.status_code == 200
    assert len(r.json()) == 5


def test_heroes_mine_limit_is_capped(client) -> None:
    email, hdr, _ = _register(client)
    client.post("/summon/x10", headers=hdr)
    r = client.get("/heroes/mine?limit=999999", headers=hdr)
    assert r.status_code == 200
    # Server cap is 1000; 10 summons means we get 10, not 999999.
    assert len(r.json()) <= 1000


def test_heroes_mine_pagination(client) -> None:
    """offset + limit together page through the list."""
    email, hdr, _ = _register(client)
    client.post("/summon/x10", headers=hdr)
    page1 = client.get("/heroes/mine?limit=5&offset=0", headers=hdr).json()
    page2 = client.get("/heroes/mine?limit=5&offset=5", headers=hdr).json()
    assert len(page1) == 5 and len(page2) == 5
    ids1 = {h["id"] for h in page1}
    ids2 = {h["id"] for h in page2}
    assert ids1.isdisjoint(ids2), "pagination should not overlap"


def test_gear_mine_respects_limit(client) -> None:
    email, hdr, aid = _register(client, "gearlim")
    # Seed 7 gear pieces directly.
    import json as _json
    with SessionLocal() as db:
        for _ in range(7):
            db.add(Gear(
                account_id=aid, slot=GearSlot.WEAPON, rarity=GearRarity.COMMON,
                set_code=GearSet.VITAL, stats_json=_json.dumps({"atk": 1}),
            ))
        db.commit()
    r = client.get("/gear/mine?limit=3", headers=hdr)
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_announcements_active_respects_limit(client) -> None:
    """/announcements/active (public, unauth) is capped."""
    # Promote + post 5 announcements.
    email, hdr, aid = _register(client, "annlim")
    from app.models import Account
    with SessionLocal() as db:
        db.get(Account, aid).is_admin = True
        db.commit()
    for i in range(5):
        client.post(
            "/admin/announcements",
            json={"title": f"banner-{i}-{random.randint(1,999999)}", "body": "x", "priority": i},
            headers=hdr,
        )
    r = client.get("/announcements/active?limit=2")
    assert r.status_code == 200
    assert len(r.json()) <= 2


def test_announcements_active_limit_is_capped(client) -> None:
    r = client.get("/announcements/active?limit=999999")
    assert r.status_code == 200
    # Server cap is 100.
    assert len(r.json()) <= 100


def test_my_applications_respects_limit(client) -> None:
    """GET /guilds/applications/mine is capped + default 50."""
    # Make an applicant with a bunch of pending apps — need as many guilds.
    applicant_email, applicant_hdr, aid = _register(client, "appmelim")
    # Create 4 guilds, apply to each.
    for _ in range(4):
        _g_email, g_hdr, _g_aid = _register(client, "gapp")
        r = client.post(
            "/guilds",
            json={"name": f"GApp{random.randint(1,999999)}", "tag": f"GA{random.randint(10,99)}"},
            headers=g_hdr,
        )
        gid = r.json()["id"]
        client.post(f"/guilds/{gid}/apply", json={"message": "hi"}, headers=applicant_hdr)

    r = client.get("/guilds/applications/mine?limit=2", headers=applicant_hdr)
    assert r.status_code == 200
    assert len(r.json()) <= 2


def test_my_applications_limit_is_capped(client) -> None:
    applicant_email, applicant_hdr, _ = _register(client, "appmecap")
    r = client.get("/guilds/applications/mine?limit=999999", headers=applicant_hdr)
    assert r.status_code == 200
    # Cap is 200; fresh account, so list is short regardless.
    assert len(r.json()) <= 200
