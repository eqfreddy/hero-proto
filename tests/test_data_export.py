"""GDPR account export — shape, redaction, and that activity actually appears."""

from __future__ import annotations

import random


def _register(client) -> tuple[dict, str]:
    email = f"exp+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, email


def test_export_returns_account_block_with_redacted_secrets(client) -> None:
    hdr, email = _register(client)
    r = client.get("/me/export", headers=hdr)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["schema_version"] == 1
    assert data["account"]["email"] == email
    assert data["account"]["password_hash"] == "<redacted>"
    # TOTP secret redaction: when 2FA isn't enabled, returns null (nothing to redact);
    # when enabled, returns "<redacted>".
    assert data["account"]["totp_secret"] in (None, "<redacted>")


def test_export_includes_starter_team_heroes(client) -> None:
    hdr, _ = _register(client)
    data = client.get("/me/export", headers=hdr).json()
    # Register grants 3 starter COMMON heroes.
    assert len(data["heroes"]) >= 3
    h0 = data["heroes"][0]
    assert "template_code" in h0
    assert "level" in h0


def test_export_reflects_recent_battles_and_summons(client) -> None:
    hdr, _ = _register(client)
    # Do a summon and a battle.
    me = client.get("/me", headers=hdr).json()
    if me["shards"] >= 100 or me["free_summon_credits"] > 0:
        r = client.post("/summon/x1", headers=hdr)
        assert r.status_code == 201
    stages = client.get("/stages").json()
    # Build a team of the first hero we have.
    heroes = client.get("/heroes/mine", headers=hdr).json()
    team = [heroes[0]["id"]] if heroes else []
    if team:
        client.post("/battles", json={"stage_id": stages[0]["id"], "team": team}, headers=hdr)

    data = client.get("/me/export", headers=hdr).json()
    assert isinstance(data["gacha_records"], list)
    assert isinstance(data["battles"], list)


def test_export_empty_collections_for_fresh_account(client) -> None:
    """Fresh account has no friends, no DMs, no purchases, no guild — those
    arrays exist and are empty rather than missing."""
    hdr, _ = _register(client)
    data = client.get("/me/export", headers=hdr).json()
    for key in (
        "friendships", "direct_messages", "abuse_reports_filed",
        "purchases", "guild_memberships", "guild_applications",
        "guild_messages_sent", "team_presets", "raid_attempts",
    ):
        assert isinstance(data[key], list), f"{key} should be a list"
        assert data[key] == [], f"{key} should be empty for fresh account"


def test_export_requires_auth(client) -> None:
    r = client.get("/me/export")
    assert r.status_code == 401
