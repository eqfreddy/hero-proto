"""Phase 2.5 — EXILE faction default for new accounts.

EXILE is the narrative "haven't picked a side yet" faction. Every new
register flow lands the account on EXILE; flipping to RESISTANCE /
CORP_GREED is Phase 3's level-50 fork. Tests pin the default + verify
it surfaces on /me.
"""

from __future__ import annotations

import random


def _register(client) -> tuple[dict, int]:
    email = f"exile+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    aid = client.get("/me", headers=hdr).json()["id"]
    return hdr, aid


def test_register_defaults_to_exile_faction(client) -> None:
    hdr, _ = _register(client)
    me = client.get("/me", headers=hdr).json()
    assert me["faction"] == "EXILE"


def test_existing_accounts_migrated_to_exile_via_server_default(client) -> None:
    """The migration uses server_default='EXILE' so any pre-existing rows
    that didn't have the column get backfilled. Verify the column reads
    EXILE for a fresh insert too."""
    from app.db import SessionLocal
    from app.models import Account, Faction

    hdr, aid = _register(client)
    db = SessionLocal()
    try:
        a = db.get(Account, aid)
        assert a is not None
        assert Faction(a.faction) == Faction.EXILE
    finally:
        db.close()


def test_faction_enum_includes_exile() -> None:
    from app.models import Faction

    assert Faction.EXILE.value == "EXILE"
    # The five legacy factions still resolve.
    for code in ("HELPDESK", "DEVOPS", "EXECUTIVE", "ROGUE_IT", "LEGACY"):
        assert Faction(code).value == code
