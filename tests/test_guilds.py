"""Integration tests for the guild router."""

from __future__ import annotations

import random

import pytest


def _register(client) -> tuple[dict[str, str], int]:
    email = f"guildtest+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    token = r.json()["access_token"]
    hdr = {"Authorization": f"Bearer {token}"}
    me = client.get("/me", headers=hdr).json()
    return hdr, me["id"]


def test_create_list_and_get_guild(client) -> None:
    hdr, _ = _register(client)
    name = f"Test Guild {random.randint(1000, 9999)}"
    r = client.post("/guilds", json={"name": name, "tag": "TG1", "description": "hi"}, headers=hdr)
    assert r.status_code == 201, r.text
    g = r.json()
    assert g["name"] == name and g["tag"] == "TG1" and g["member_count"] == 1

    r = client.get("/guilds")
    assert r.status_code == 200
    assert any(x["id"] == g["id"] for x in r.json())

    r = client.get(f"/guilds/{g['id']}")
    assert r.status_code == 200
    detail = r.json()
    assert len(detail["members"]) == 1
    assert detail["members"][0]["role"] == "LEADER"


def test_cannot_create_two_guilds_per_account(client) -> None:
    hdr, _ = _register(client)
    r = client.post("/guilds", json={"name": f"A{random.randint(1,999999)}", "tag": "AAA"}, headers=hdr)
    assert r.status_code == 201
    r = client.post("/guilds", json={"name": f"B{random.randint(1,999999)}", "tag": "BBB"}, headers=hdr)
    assert r.status_code == 409


def test_join_leave_and_leader_succession(client) -> None:
    leader_hdr, leader_id = _register(client)
    r = client.post(
        "/guilds",
        json={"name": f"Succession {random.randint(1,999999)}", "tag": "SUC"},
        headers=leader_hdr,
    )
    assert r.status_code == 201
    guild_id = r.json()["id"]

    member_hdr, member_id = _register(client)
    r = client.post(f"/guilds/{guild_id}/join", headers=member_hdr)
    assert r.status_code == 200
    detail = r.json()
    assert detail["member_count"] == 2

    # Leader leaves → member becomes LEADER.
    r = client.post("/guilds/leave", headers=leader_hdr)
    assert r.status_code == 200
    r = client.get(f"/guilds/{guild_id}")
    assert r.status_code == 200
    detail = r.json()
    assert detail["member_count"] == 1
    assert detail["members"][0]["account_id"] == member_id
    assert detail["members"][0]["role"] == "LEADER"


def test_chat_requires_membership_and_returns_messages(client) -> None:
    leader_hdr, _ = _register(client)
    r = client.post(
        "/guilds",
        json={"name": f"Chatters {random.randint(1,999999)}", "tag": "CHT"},
        headers=leader_hdr,
    )
    guild_id = r.json()["id"]

    # Non-member: 403 on messages.
    outsider_hdr, _ = _register(client)
    r = client.get(f"/guilds/{guild_id}/messages", headers=outsider_hdr)
    assert r.status_code == 403

    # Leader posts two messages.
    r = client.post(
        f"/guilds/{guild_id}/messages",
        json={"body": "first post"},
        headers=leader_hdr,
    )
    assert r.status_code == 201
    r = client.post(
        f"/guilds/{guild_id}/messages",
        json={"body": "second one"},
        headers=leader_hdr,
    )
    assert r.status_code == 201

    # Leader can read — newest first.
    r = client.get(f"/guilds/{guild_id}/messages", headers=leader_hdr)
    assert r.status_code == 200
    msgs = r.json()
    assert len(msgs) == 2
    assert msgs[0]["body"] == "second one"
    assert msgs[1]["body"] == "first post"


def test_leader_can_kick(client) -> None:
    leader_hdr, _ = _register(client)
    r = client.post(
        "/guilds",
        json={"name": f"Kick-club {random.randint(1,999999)}", "tag": "KIK"},
        headers=leader_hdr,
    )
    guild_id = r.json()["id"]
    victim_hdr, victim_id = _register(client)
    client.post(f"/guilds/{guild_id}/join", headers=victim_hdr)

    r = client.post(f"/guilds/{guild_id}/kick/{victim_id}", headers=leader_hdr)
    assert r.status_code == 200, r.text
    assert r.json()["member_count"] == 1

    # Victim now in no guild.
    r = client.get("/guilds/mine", headers=victim_hdr)
    assert r.status_code == 200
    assert r.json() is None


def test_leader_promotes_member_to_officer(client) -> None:
    leader_hdr, _ = _register(client)
    r = client.post(
        "/guilds", json={"name": f"Promote-club {random.randint(1,999999)}", "tag": "PRO"}, headers=leader_hdr,
    )
    guild_id = r.json()["id"]
    member_hdr, member_id = _register(client)
    client.post(f"/guilds/{guild_id}/join", headers=member_hdr)

    r = client.post(f"/guilds/{guild_id}/promote/{member_id}", headers=leader_hdr)
    assert r.status_code == 200, r.text
    roles = {m["account_id"]: m["role"] for m in r.json()["members"]}
    assert roles[member_id] == "OFFICER"

    # Demote back to MEMBER.
    r = client.post(f"/guilds/{guild_id}/demote/{member_id}", headers=leader_hdr)
    assert r.status_code == 200
    roles = {m["account_id"]: m["role"] for m in r.json()["members"]}
    assert roles[member_id] == "MEMBER"


def test_non_leader_cannot_promote(client) -> None:
    leader_hdr, _ = _register(client)
    r = client.post(
        "/guilds", json={"name": f"Nolead-club {random.randint(1,999999)}", "tag": "NOL"}, headers=leader_hdr,
    )
    guild_id = r.json()["id"]
    m1_hdr, m1_id = _register(client)
    client.post(f"/guilds/{guild_id}/join", headers=m1_hdr)
    m2_hdr, m2_id = _register(client)
    client.post(f"/guilds/{guild_id}/join", headers=m2_hdr)

    r = client.post(f"/guilds/{guild_id}/promote/{m2_id}", headers=m1_hdr)
    assert r.status_code == 403


def test_demote_rejects_non_officer(client) -> None:
    leader_hdr, _ = _register(client)
    r = client.post(
        "/guilds", json={"name": f"Demoteonly {random.randint(1,999999)}", "tag": "DMO"}, headers=leader_hdr,
    )
    guild_id = r.json()["id"]
    m_hdr, m_id = _register(client)
    client.post(f"/guilds/{guild_id}/join", headers=m_hdr)
    # Member is not an officer — demote should 400.
    r = client.post(f"/guilds/{guild_id}/demote/{m_id}", headers=leader_hdr)
    assert r.status_code == 400


def test_leader_transfer(client) -> None:
    leader_hdr, leader_id = _register(client)
    r = client.post(
        "/guilds", json={"name": f"Xfer-club {random.randint(1,999999)}", "tag": "XFR"}, headers=leader_hdr,
    )
    guild_id = r.json()["id"]
    successor_hdr, successor_id = _register(client)
    client.post(f"/guilds/{guild_id}/join", headers=successor_hdr)

    r = client.post(f"/guilds/{guild_id}/transfer/{successor_id}", headers=leader_hdr)
    assert r.status_code == 200, r.text
    roles = {m["account_id"]: m["role"] for m in r.json()["members"]}
    assert roles[successor_id] == "LEADER"
    assert roles[leader_id] == "OFFICER"

    # Old leader can no longer transfer.
    r = client.post(f"/guilds/{guild_id}/transfer/{leader_id}", headers=leader_hdr)
    assert r.status_code == 403


def test_transfer_rejects_self(client) -> None:
    leader_hdr, leader_id = _register(client)
    r = client.post(
        "/guilds", json={"name": f"Xfer-self {random.randint(1,999999)}", "tag": "XFS"}, headers=leader_hdr,
    )
    guild_id = r.json()["id"]
    r = client.post(f"/guilds/{guild_id}/transfer/{leader_id}", headers=leader_hdr)
    assert r.status_code == 400


def test_application_accept_flow(client) -> None:
    leader_hdr, _ = _register(client)
    r = client.post(
        "/guilds", json={"name": f"App-club {random.randint(1,999999)}", "tag": "APP"}, headers=leader_hdr,
    )
    guild_id = r.json()["id"]

    applicant_hdr, applicant_id = _register(client)
    r = client.post(f"/guilds/{guild_id}/apply", json={"message": "pls"}, headers=applicant_hdr)
    assert r.status_code == 201, r.text
    app_id = r.json()["id"]
    assert r.json()["status"] == "PENDING"

    # Second identical apply -> 409.
    r = client.post(f"/guilds/{guild_id}/apply", json={"message": "again"}, headers=applicant_hdr)
    assert r.status_code == 409

    # Applicant can see their own pending list.
    r = client.get("/guilds/applications/mine", headers=applicant_hdr)
    assert any(a["id"] == app_id for a in r.json())

    # Leader lists & accepts.
    r = client.get(f"/guilds/{guild_id}/applications", headers=leader_hdr)
    assert r.status_code == 200
    assert any(a["id"] == app_id and a["status"] == "PENDING" for a in r.json())

    r = client.post(f"/guilds/applications/{app_id}/accept", headers=leader_hdr)
    assert r.status_code == 200
    roles = {m["account_id"]: m["role"] for m in r.json()["members"]}
    assert roles[applicant_id] == "MEMBER"

    # Accepting again -> 409 (already accepted).
    r = client.post(f"/guilds/applications/{app_id}/accept", headers=leader_hdr)
    assert r.status_code == 409


def test_application_reject_and_withdraw(client) -> None:
    leader_hdr, _ = _register(client)
    r = client.post(
        "/guilds", json={"name": f"Rej-club {random.randint(1,999999)}", "tag": "REJ"}, headers=leader_hdr,
    )
    guild_id = r.json()["id"]

    # Reject path.
    a1_hdr, _ = _register(client)
    app1 = client.post(f"/guilds/{guild_id}/apply", json={}, headers=a1_hdr).json()
    r = client.post(f"/guilds/applications/{app1['id']}/reject", headers=leader_hdr)
    assert r.status_code == 200
    assert r.json()["status"] == "REJECTED"

    # Withdraw path.
    a2_hdr, _ = _register(client)
    app2 = client.post(f"/guilds/{guild_id}/apply", json={}, headers=a2_hdr).json()
    r = client.delete(f"/guilds/applications/{app2['id']}", headers=a2_hdr)
    assert r.status_code == 200
    assert r.json()["status"] == "WITHDRAWN"

    # Other users can't withdraw someone else's application.
    a3_hdr, _ = _register(client)
    app3 = client.post(f"/guilds/{guild_id}/apply", json={}, headers=a3_hdr).json()
    a4_hdr, _ = _register(client)
    r = client.delete(f"/guilds/applications/{app3['id']}", headers=a4_hdr)
    assert r.status_code == 404


def test_applications_require_officer_or_leader(client) -> None:
    leader_hdr, _ = _register(client)
    r = client.post(
        "/guilds", json={"name": f"Priv-club {random.randint(1,999999)}", "tag": "PRV"}, headers=leader_hdr,
    )
    guild_id = r.json()["id"]
    member_hdr, _ = _register(client)
    client.post(f"/guilds/{guild_id}/join", headers=member_hdr)

    applicant_hdr, _ = _register(client)
    app = client.post(f"/guilds/{guild_id}/apply", json={}, headers=applicant_hdr).json()

    # Regular member cannot list or act on applications.
    r = client.get(f"/guilds/{guild_id}/applications", headers=member_hdr)
    assert r.status_code == 403
    r = client.post(f"/guilds/applications/{app['id']}/accept", headers=member_hdr)
    assert r.status_code == 403


def test_chat_pagination(client) -> None:
    leader_hdr, _ = _register(client)
    r = client.post(
        "/guilds", json={"name": f"Chat-pages {random.randint(1,999999)}", "tag": "CHP"}, headers=leader_hdr,
    )
    guild_id = r.json()["id"]

    # Post 10 messages.
    ids = []
    for i in range(10):
        r = client.post(f"/guilds/{guild_id}/messages", json={"body": f"msg {i}"}, headers=leader_hdr)
        ids.append(r.json()["id"])

    # First page: newest 4.
    r = client.get(f"/guilds/{guild_id}/messages?limit=4", headers=leader_hdr)
    page1 = r.json()
    assert [m["id"] for m in page1] == sorted([m["id"] for m in page1], reverse=True)
    assert len(page1) == 4

    # Second page: older than page1's last id.
    oldest_so_far = page1[-1]["id"]
    r = client.get(f"/guilds/{guild_id}/messages?before={oldest_so_far}&limit=4", headers=leader_hdr)
    page2 = r.json()
    assert len(page2) == 4
    assert all(m["id"] < oldest_so_far for m in page2)
    assert set(m["id"] for m in page1) & set(m["id"] for m in page2) == set()


