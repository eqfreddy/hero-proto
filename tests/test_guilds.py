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
