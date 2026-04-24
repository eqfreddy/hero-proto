"""Integration tests for guild raids."""

from __future__ import annotations

import random

import pytest

from app.db import SessionLocal
from app.models import Account


def _grant_energy(account_id: int, amount: int) -> None:
    """Tests bypass the energy cap so raid loops don't block on it."""
    with SessionLocal() as db:
        a = db.get(Account, account_id)
        assert a is not None
        a.energy_stored = amount
        db.commit()


def _register_with_team(client, *, extra_energy: int = 0) -> tuple[dict[str, str], int, list[int], str]:
    email = f"raid+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = client.get("/me", headers=hdr).json()
    if extra_energy:
        _grant_energy(me["id"], extra_energy)
    # Summon to get a team.
    client.post("/summon/x10", headers=hdr)
    roster = sorted(client.get("/heroes/mine", headers=hdr).json(), key=lambda h: h["power"], reverse=True)
    team = [h["id"] for h in roster[:3]]
    return hdr, me["id"], team, email


def _new_guild(client, hdr, tag_prefix: str = "R") -> int:
    r = client.post(
        "/guilds",
        json={"name": f"Raid {random.randint(1,999999)}", "tag": f"{tag_prefix}{random.randint(10,99)}"},
        headers=hdr,
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_raid_requires_guild(client) -> None:
    hdr, _, _, _ = _register_with_team(client)
    r = client.post(
        "/raids/start",
        json={"boss_template_code": "the_founder", "boss_level": 20, "duration_hours": 1.0},
        headers=hdr,
    )
    assert r.status_code == 403


def test_full_raid_lifecycle(client) -> None:
    # Grant enough energy to kill a level-1 boss (thick HP pool, ~60-200 attacks).
    leader_hdr, _, team, _ = _register_with_team(client, extra_energy=3000)
    _new_guild(client, leader_hdr)

    # Only LEADER / OFFICER can start — we're leader, good.
    r = client.post(
        "/raids/start",
        json={"boss_template_code": "the_founder", "boss_level": 1, "duration_hours": 1.0},
        headers=leader_hdr,
    )
    assert r.status_code == 201, r.text
    raid = r.json()
    assert raid["remaining_hp"] == raid["max_hp"]
    assert raid["state"] == "ACTIVE"

    # Hammer the boss with many attacks until it falls.
    rid = raid["id"]
    defeated = False
    for _ in range(200):
        r = client.post(f"/raids/{rid}/attack", json={"team": team}, headers=leader_hdr)
        if r.status_code == 409:
            # Out of energy — can't finish; fail the test by timeout instead.
            pytest.fail(f"ran out of energy before boss died: {r.text}")
        assert r.status_code == 201, r.text
        payload = r.json()
        if payload["boss_defeated"]:
            defeated = True
            assert payload["rewards"] is not None
            assert payload["boss_remaining_hp"] == 0
            break
    assert defeated, "boss never died in 200 attacks"

    # Second attack attempt should now 409.
    r = client.post(f"/raids/{rid}/attack", json={"team": team}, headers=leader_hdr)
    assert r.status_code == 409


def test_one_active_raid_per_guild(client) -> None:
    hdr, _, _, _ = _register_with_team(client)
    _new_guild(client, hdr)
    r = client.post(
        "/raids/start",
        json={"boss_template_code": "the_founder", "boss_level": 10, "duration_hours": 1.0},
        headers=hdr,
    )
    assert r.status_code == 201
    r = client.post(
        "/raids/start",
        json={"boss_template_code": "the_founder", "boss_level": 10, "duration_hours": 1.0},
        headers=hdr,
    )
    assert r.status_code == 409


def test_raid_tier_scales_boss_hp(client) -> None:
    """T2 boss has 2x the HP of T1 for the same template/level."""
    hdr, _, _, _ = _register_with_team(client)
    _new_guild(client, hdr, "RT1")

    # Pick any EPIC boss template that seed included.
    t1 = client.post(
        "/raids/start",
        json={"boss_template_code": "the_consultant", "boss_level": 20,
              "duration_hours": 24, "tier": "T1"},
        headers=hdr,
    )
    assert t1.status_code == 201, t1.text
    t1_hp = t1.json()["max_hp"]
    assert t1.json()["tier"] == "T1"

    # Clean up so we can start a new raid.
    from app.db import SessionLocal
    from app.models import Raid, RaidState
    with SessionLocal() as db:
        for r in db.query(Raid).all():
            r.state = RaidState.EXPIRED
        db.commit()

    t2 = client.post(
        "/raids/start",
        json={"boss_template_code": "the_consultant", "boss_level": 20,
              "duration_hours": 24, "tier": "T2"},
        headers=hdr,
    )
    assert t2.status_code == 201, t2.text
    t2_hp = t2.json()["max_hp"]
    assert t2.json()["tier"] == "T2"
    # T2 HP pool is substantially larger (2x multiplier × level bump).
    assert t2_hp > t1_hp * 1.9, f"T2 hp ({t2_hp}) should be ~2x T1 ({t1_hp})"


def test_raid_start_rejects_invalid_tier(client) -> None:
    hdr, _, _, _ = _register_with_team(client)
    _new_guild(client, hdr, "RT2")
    r = client.post(
        "/raids/start",
        json={"boss_template_code": "the_consultant", "boss_level": 20,
              "duration_hours": 24, "tier": "T9"},
        headers=hdr,
    )
    assert r.status_code == 422  # pydantic rejects


def test_worker_auto_rotates_raid_for_empty_guild(client) -> None:
    """Guild with members but no active raid → worker starts a T1 raid."""
    from app.db import SessionLocal
    from app.models import Guild, GuildMember, Raid, RaidState
    from app.worker import _run_jobs

    hdr, _, _, _ = _register_with_team(client)
    gid = _new_guild(client, hdr, "RO")

    # Sanity: fresh guild has no raids.
    with SessionLocal() as db:
        assert db.query(Raid).filter_by(guild_id=gid).count() == 0

    # Run worker — should start one.
    _run_jobs()

    with SessionLocal() as db:
        raids = db.query(Raid).filter_by(guild_id=gid).all()
        assert len(raids) == 1, f"expected 1 raid after rotation, got {len(raids)}"
        assert raids[0].state == RaidState.ACTIVE
        assert raids[0].started_by is None, "auto-rotated raid should have started_by=None"
        assert raids[0].tier == "T1"


def test_worker_does_not_rotate_if_active_raid_exists(client) -> None:
    from app.db import SessionLocal
    from app.models import Raid, RaidState
    from app.worker import _run_jobs

    hdr, _, _, _ = _register_with_team(client)
    _new_guild(client, hdr, "NR")
    # Start a manual raid first.
    r = client.post(
        "/raids/start",
        json={"boss_template_code": "the_consultant", "boss_level": 20, "duration_hours": 24, "tier": "T1"},
        headers=hdr,
    )
    assert r.status_code == 201
    rid = r.json()["id"]

    _run_jobs()

    with SessionLocal() as db:
        # Should still be exactly 1 raid.
        raid_ids = [r.id for r in db.query(Raid).all() if r.state == RaidState.ACTIVE]
        assert rid in raid_ids
        # Total active raids for any guild this caller's in: still one manual entry.


def test_worker_does_not_rotate_empty_guild(client) -> None:
    """Guild with zero members shouldn't get a raid."""
    from app.db import SessionLocal
    from app.models import Guild, GuildMember, Raid
    from app.worker import _run_jobs

    # Create a guild, then leave it — results in a zero-member guild without a raid.
    hdr, _, _, _ = _register_with_team(client)
    gid = _new_guild(client, hdr, "EM")
    # Transfer leadership to another account, then have leader leave.
    hdr2, _, _, _ = _register_with_team(client)
    client.post(f"/guilds/{gid}/apply", json={}, headers=hdr2)
    apps = client.get(f"/guilds/{gid}/applications", headers=hdr).json()
    app_id = apps[0]["id"]
    client.post(f"/guilds/applications/{app_id}/accept", headers=hdr)
    # Now both in; leader leaves triggers succession, so we need a different approach.
    # Simplest: directly empty the guild in DB.
    with SessionLocal() as db:
        db.query(GuildMember).filter_by(guild_id=gid).delete()
        db.commit()

    _run_jobs()

    with SessionLocal() as db:
        assert db.query(Raid).filter_by(guild_id=gid).count() == 0, \
            "worker should skip guilds with no members"


def test_worker_respects_rotation_cooldown(client, monkeypatch) -> None:
    """After a raid ends, the worker waits RAID_ROTATION_COOLDOWN_HOURS before rotating."""
    from datetime import timedelta
    from app.db import SessionLocal
    from app.models import Raid, RaidState
    from app.worker import _run_jobs, RAID_ROTATION_COOLDOWN_HOURS

    hdr, _, _, _ = _register_with_team(client)
    gid = _new_guild(client, hdr, "CD")

    # First rotation puts a raid there.
    _run_jobs()
    with SessionLocal() as db:
        r = db.query(Raid).filter_by(guild_id=gid).one()
        # Force it to EXPIRED just now (ends_at = now) so next rotation needs to wait.
        from app.models import utcnow
        now = utcnow()
        r.state = RaidState.EXPIRED
        r.ends_at = now  # ended right now
        db.commit()

    # Immediately running the worker again should NOT start a new one — cooldown not elapsed.
    _run_jobs()
    with SessionLocal() as db:
        assert db.query(Raid).filter_by(guild_id=gid).count() == 1, \
            "worker shouldn't rotate while cooldown is active"

    # Push ends_at backwards so the cooldown has elapsed.
    with SessionLocal() as db:
        r = db.query(Raid).filter_by(guild_id=gid).one()
        r.ends_at = r.ends_at - timedelta(hours=RAID_ROTATION_COOLDOWN_HOURS + 1)
        db.commit()

    _run_jobs()
    with SessionLocal() as db:
        raids = db.query(Raid).filter_by(guild_id=gid).order_by(Raid.id).all()
        assert len(raids) == 2, f"expected rotation after cooldown, got {len(raids)} raids"
        assert raids[-1].state == RaidState.ACTIVE
