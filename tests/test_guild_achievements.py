"""Integration tests for per-guild achievements / milestones."""

from __future__ import annotations

import random


def _register(client) -> tuple[dict[str, str], int]:
    email = f"gachtest+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    token = r.json()["access_token"]
    hdr = {"Authorization": f"Bearer {token}"}
    me = client.get("/me", headers=hdr).json()
    return hdr, me["id"]


def _make_guild(client, hdr) -> int:
    name = f"GATest {random.randint(1, 999_999_999)}"
    n = random.randint(100000, 999999)
    tag = f"{n}"[:6]
    r = client.post("/guilds", json={"name": name, "tag": tag}, headers=hdr)
    assert r.status_code == 201, r.text
    return r.json()["id"]


# ---------------------------------------------------------------------------
# 1. List achievements — public endpoint, no auth
# ---------------------------------------------------------------------------

def test_list_achievements_public(client) -> None:
    hdr, _ = _register(client)
    guild_id = _make_guild(client, hdr)

    r = client.get(f"/guilds/{guild_id}/achievements")
    assert r.status_code == 200, r.text
    data = r.json()
    assert "achievements" in data
    codes = [a["code"] for a in data["achievements"]]
    assert "FIRST_MEMBER" in codes
    assert "DAMAGE_DEALERS" in codes


def test_list_achievements_no_auth_required(client) -> None:
    hdr, _ = _register(client)
    guild_id = _make_guild(client, hdr)

    # No Authorization header — should still succeed.
    r = client.get(f"/guilds/{guild_id}/achievements")
    assert r.status_code == 200


def test_list_achievements_unknown_guild_404(client) -> None:
    r = client.get("/guilds/999999/achievements")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 2. members_joined counter advances on join
# ---------------------------------------------------------------------------

def test_members_joined_progress_on_join(client) -> None:
    leader_hdr, _ = _register(client)
    guild_id = _make_guild(client, leader_hdr)

    # Immediately after creation, FIRST_MEMBER progress should be 1 (leader counted).
    r = client.get(f"/guilds/{guild_id}/achievements")
    achievements = {a["code"]: a for a in r.json()["achievements"]}
    first_member = achievements["FIRST_MEMBER"]
    assert first_member["current_value"] == 1
    assert first_member["completed"] is False

    # A second member joins — should complete FIRST_MEMBER (target=2).
    member_hdr, _ = _register(client)
    r = client.post(f"/guilds/{guild_id}/join", headers=member_hdr)
    assert r.status_code == 200

    r = client.get(f"/guilds/{guild_id}/achievements")
    achievements = {a["code"]: a for a in r.json()["achievements"]}
    first_member = achievements["FIRST_MEMBER"]
    assert first_member["current_value"] == 2
    assert first_member["completed"] is True


# ---------------------------------------------------------------------------
# 3. Achievement schema fields
# ---------------------------------------------------------------------------

def test_achievement_schema_fields(client) -> None:
    hdr, _ = _register(client)
    guild_id = _make_guild(client, hdr)

    r = client.get(f"/guilds/{guild_id}/achievements")
    ach = r.json()["achievements"][0]
    for field in ("code", "name", "description", "category", "metric",
                  "target_value", "reward_gems", "reward_coins",
                  "current_value", "completed", "reward_claimed"):
        assert field in ach, f"missing field: {field}"


# ---------------------------------------------------------------------------
# 4. Claim endpoint — 409 before complete, 200 after complete
# ---------------------------------------------------------------------------

def test_claim_before_complete_returns_409(client) -> None:
    hdr, _ = _register(client)
    guild_id = _make_guild(client, hdr)

    # FIRST_MEMBER target=2; we only have 1 member so far.
    r = client.post(f"/guilds/{guild_id}/achievements/FIRST_MEMBER/claim", headers=hdr)
    assert r.status_code == 409


def test_claim_after_complete_returns_200_and_grants_rewards(client) -> None:
    leader_hdr, leader_id = _register(client)
    guild_id = _make_guild(client, leader_hdr)

    # Add a second member to complete FIRST_MEMBER.
    member_hdr, _ = _register(client)
    r = client.post(f"/guilds/{guild_id}/join", headers=member_hdr)
    assert r.status_code == 200

    me_before = client.get("/me", headers=leader_hdr).json()
    gems_before = me_before["gems"]
    coins_before = me_before["coins"]

    r = client.post(f"/guilds/{guild_id}/achievements/FIRST_MEMBER/claim", headers=leader_hdr)
    assert r.status_code == 200, r.text
    ach = r.json()
    assert ach["reward_claimed"] is True

    me_after = client.get("/me", headers=leader_hdr).json()
    assert me_after["gems"] == gems_before + ach["reward_gems"]
    assert me_after["coins"] == coins_before + ach["reward_coins"]


# ---------------------------------------------------------------------------
# 5. Claim is idempotent
# ---------------------------------------------------------------------------

def test_claim_idempotent(client) -> None:
    leader_hdr, _ = _register(client)
    guild_id = _make_guild(client, leader_hdr)

    member_hdr, _ = _register(client)
    client.post(f"/guilds/{guild_id}/join", headers=member_hdr)

    r1 = client.post(f"/guilds/{guild_id}/achievements/FIRST_MEMBER/claim", headers=leader_hdr)
    assert r1.status_code == 200

    me_mid = client.get("/me", headers=leader_hdr).json()

    r2 = client.post(f"/guilds/{guild_id}/achievements/FIRST_MEMBER/claim", headers=leader_hdr)
    assert r2.status_code == 200

    me_after = client.get("/me", headers=leader_hdr).json()
    # Second claim must not grant additional rewards.
    assert me_after["gems"] == me_mid["gems"]
    assert me_after["coins"] == me_mid["coins"]


# ---------------------------------------------------------------------------
# 6. Non-member cannot claim
# ---------------------------------------------------------------------------

def test_claim_non_member_forbidden(client) -> None:
    leader_hdr, _ = _register(client)
    guild_id = _make_guild(client, leader_hdr)

    member_hdr, _ = _register(client)
    client.post(f"/guilds/{guild_id}/join", headers=member_hdr)
    # Complete FIRST_MEMBER.
    client.post(f"/guilds/{guild_id}/achievements/FIRST_MEMBER/claim", headers=leader_hdr)

    outsider_hdr, _ = _register(client)
    r = client.post(f"/guilds/{guild_id}/achievements/FIRST_MEMBER/claim", headers=outsider_hdr)
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# 7. members_joined via accept_application path
# ---------------------------------------------------------------------------

def test_members_joined_via_application(client) -> None:
    leader_hdr, _ = _register(client)
    guild_id = _make_guild(client, leader_hdr)

    applicant_hdr, _ = _register(client)
    r = client.post(f"/guilds/{guild_id}/apply", json={"message": ""}, headers=applicant_hdr)
    assert r.status_code == 201
    app_id = r.json()["id"]

    r = client.post(f"/guilds/applications/{app_id}/accept", headers=leader_hdr)
    assert r.status_code == 200

    r = client.get(f"/guilds/{guild_id}/achievements")
    achievements = {a["code"]: a for a in r.json()["achievements"]}
    assert achievements["FIRST_MEMBER"]["completed"] is True


# ---------------------------------------------------------------------------
# 8. Unknown achievement code returns 404 on claim
# ---------------------------------------------------------------------------

def test_claim_unknown_code_404(client) -> None:
    hdr, _ = _register(client)
    guild_id = _make_guild(client, hdr)
    r = client.post(f"/guilds/{guild_id}/achievements/DOES_NOT_EXIST/claim", headers=hdr)
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# 9. Regular member (not officer) cannot claim
# ---------------------------------------------------------------------------

def test_claim_regular_member_forbidden(client) -> None:
    leader_hdr, _ = _register(client)
    guild_id = _make_guild(client, leader_hdr)

    member_hdr, _ = _register(client)
    client.post(f"/guilds/{guild_id}/join", headers=member_hdr)

    # FIRST_MEMBER is now complete.
    r = client.post(f"/guilds/{guild_id}/achievements/FIRST_MEMBER/claim", headers=member_hdr)
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# 10. messages_sent hook advances GUILD_CHAT_ACTIVE progress
# ---------------------------------------------------------------------------

def test_messages_sent_hook(client) -> None:
    leader_hdr, _ = _register(client)
    guild_id = _make_guild(client, leader_hdr)

    r = client.post(
        f"/guilds/{guild_id}/messages",
        json={"body": "hello guild"},
        headers=leader_hdr,
    )
    assert r.status_code == 201

    r = client.get(f"/guilds/{guild_id}/achievements")
    achievements = {a["code"]: a for a in r.json()["achievements"]}
    assert achievements["GUILD_CHAT_ACTIVE"]["current_value"] == 1


# ---------------------------------------------------------------------------
# 11. members_joined via accept_invite path
# ---------------------------------------------------------------------------

def test_members_joined_via_invite(client) -> None:
    leader_hdr, _ = _register(client)
    guild_id = _make_guild(client, leader_hdr)

    invitee_hdr, invitee_id = _register(client)
    r = client.post(
        f"/guilds/{guild_id}/invite/{invitee_id}",
        json={"message": ""},
        headers=leader_hdr,
    )
    assert r.status_code == 201
    invite_id = r.json()["id"]

    r = client.post(f"/guilds/invites/{invite_id}/accept", headers=invitee_hdr)
    assert r.status_code == 200

    r = client.get(f"/guilds/{guild_id}/achievements")
    achievements = {a["code"]: a for a in r.json()["achievements"]}
    assert achievements["FIRST_MEMBER"]["completed"] is True
