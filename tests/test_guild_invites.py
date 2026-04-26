"""Guild-initiated invite flow: leader/officer invites a player; player accepts/rejects."""

from __future__ import annotations

import random


def _register(client) -> tuple[dict[str, str], int]:
    email = f"ginv+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me = client.get("/me", headers=hdr).json()
    return hdr, me["id"]


def _make_guild(client, hdr) -> int:
    # Widen random space well past collision range — guild names + tags are
    # both globally unique. Tag is capped at 6 chars so we squeeze 5 digits in.
    name = f"InvG_{random.randint(10**12, 10**13 - 1)}"
    tag = f"i{random.randint(10000, 99999)}"  # 6 chars exactly
    r = client.post("/guilds", json={"name": name, "tag": tag}, headers=hdr)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_invite_lifecycle_pending_then_accepted(client) -> None:
    """Officer issues an invite; the targeted player accepts and becomes a member."""
    leader_hdr, _ = _register(client)
    gid = _make_guild(client, leader_hdr)

    invitee_hdr, invitee_id = _register(client)
    r = client.post(
        f"/guilds/{gid}/invite/{invitee_id}",
        json={"message": "we need a SUP main"},
        headers=leader_hdr,
    )
    assert r.status_code == 201, r.text
    inv = r.json()
    assert inv["status"] == "PENDING"
    assert inv["account_id"] == invitee_id
    assert inv["guild_id"] == gid

    # Invitee sees it in /guilds/invites/mine.
    mine = client.get("/guilds/invites/mine", headers=invitee_hdr).json()
    assert len(mine) == 1 and mine[0]["id"] == inv["id"]

    # Accept → joins.
    r = client.post(f"/guilds/invites/{inv['id']}/accept", headers=invitee_hdr)
    assert r.status_code == 200, r.text
    detail = r.json()
    assert detail["id"] == gid
    assert any(m["account_id"] == invitee_id for m in detail["members"])

    # Invite is now in terminal state.
    mine_after = client.get("/guilds/invites/mine", headers=invitee_hdr).json()
    assert mine_after[0]["status"] == "ACCEPTED"


def test_invite_reject_keeps_player_unaffiliated(client) -> None:
    leader_hdr, _ = _register(client)
    gid = _make_guild(client, leader_hdr)
    invitee_hdr, invitee_id = _register(client)

    r = client.post(f"/guilds/{gid}/invite/{invitee_id}", json={}, headers=leader_hdr)
    inv = r.json()
    r = client.post(f"/guilds/invites/{inv['id']}/reject", headers=invitee_hdr)
    assert r.status_code == 200
    assert r.json()["status"] == "REJECTED"

    # No membership added.
    me = client.get("/guilds/mine", headers=invitee_hdr)
    assert me.status_code == 200 and me.json() is None


def test_invite_cancel_by_officer(client) -> None:
    """Officer/leader can withdraw a still-pending invite. Becomes WITHDRAWN."""
    leader_hdr, _ = _register(client)
    gid = _make_guild(client, leader_hdr)
    _, invitee_id = _register(client)

    r = client.post(f"/guilds/{gid}/invite/{invitee_id}", json={}, headers=leader_hdr)
    inv = r.json()
    r = client.delete(f"/guilds/invites/{inv['id']}", headers=leader_hdr)
    assert r.status_code == 200
    assert r.json()["status"] == "WITHDRAWN"

    # Cannot cancel twice (already terminal).
    r = client.delete(f"/guilds/invites/{inv['id']}", headers=leader_hdr)
    assert r.status_code == 409


def test_member_cannot_invite(client) -> None:
    """Regular MEMBERs are not allowed to issue invites — leader/officer only."""
    leader_hdr, _ = _register(client)
    gid = _make_guild(client, leader_hdr)
    member_hdr, member_id = _register(client)
    # Officer invites the member so they can join.
    r = client.post(f"/guilds/{gid}/invite/{member_id}", json={}, headers=leader_hdr)
    inv_id = r.json()["id"]
    client.post(f"/guilds/invites/{inv_id}/accept", headers=member_hdr)

    # Now the new MEMBER tries to invite a third party.
    _, target_id = _register(client)
    r = client.post(f"/guilds/{gid}/invite/{target_id}", json={}, headers=member_hdr)
    assert r.status_code == 403


def test_cannot_invite_player_already_in_guild(client) -> None:
    leader_a_hdr, _ = _register(client)
    gid_a = _make_guild(client, leader_a_hdr)
    leader_b_hdr, _ = _register(client)
    _make_guild(client, leader_b_hdr)
    # leader_a tries to poach leader_b.
    leader_b_id = client.get("/me", headers=leader_b_hdr).json()["id"]
    r = client.post(f"/guilds/{gid_a}/invite/{leader_b_id}", json={}, headers=leader_a_hdr)
    assert r.status_code == 409


def test_duplicate_pending_invite_rejected(client) -> None:
    leader_hdr, _ = _register(client)
    gid = _make_guild(client, leader_hdr)
    _, invitee_id = _register(client)
    r = client.post(f"/guilds/{gid}/invite/{invitee_id}", json={}, headers=leader_hdr)
    assert r.status_code == 201
    r = client.post(f"/guilds/{gid}/invite/{invitee_id}", json={}, headers=leader_hdr)
    assert r.status_code == 409


def test_first_accept_wins_other_invites_auto_reject(client) -> None:
    """A player can hold pending invites from many guilds. Accepting one
    auto-rejects the others — they never had a chance once the player joined."""
    leader_a_hdr, _ = _register(client)
    leader_b_hdr, _ = _register(client)
    gid_a = _make_guild(client, leader_a_hdr)
    gid_b = _make_guild(client, leader_b_hdr)

    invitee_hdr, invitee_id = _register(client)
    inv_a = client.post(f"/guilds/{gid_a}/invite/{invitee_id}", json={}, headers=leader_a_hdr).json()
    inv_b = client.post(f"/guilds/{gid_b}/invite/{invitee_id}", json={}, headers=leader_b_hdr).json()

    # Accept A.
    r = client.post(f"/guilds/invites/{inv_a['id']}/accept", headers=invitee_hdr)
    assert r.status_code == 200

    # B should now be auto-rejected.
    mine = {x["id"]: x for x in client.get("/guilds/invites/mine", headers=invitee_hdr).json()}
    assert mine[inv_a["id"]]["status"] == "ACCEPTED"
    assert mine[inv_b["id"]]["status"] == "REJECTED"


def test_outgoing_invites_listing_is_officer_only(client) -> None:
    leader_hdr, _ = _register(client)
    gid = _make_guild(client, leader_hdr)
    _, target_id = _register(client)
    client.post(f"/guilds/{gid}/invite/{target_id}", json={}, headers=leader_hdr)

    r = client.get(f"/guilds/{gid}/invites", headers=leader_hdr)
    assert r.status_code == 200
    assert len(r.json()) == 1

    # Random non-member: forbidden.
    other_hdr, _ = _register(client)
    r = client.get(f"/guilds/{gid}/invites", headers=other_hdr)
    assert r.status_code == 403


def test_accept_someone_elses_invite_returns_404(client) -> None:
    leader_hdr, _ = _register(client)
    gid = _make_guild(client, leader_hdr)
    _, invitee_id = _register(client)
    inv = client.post(f"/guilds/{gid}/invite/{invitee_id}", json={}, headers=leader_hdr).json()

    # Different player tries to accept the invite addressed to invitee_id.
    other_hdr, _ = _register(client)
    r = client.post(f"/guilds/invites/{inv['id']}/accept", headers=other_hdr)
    assert r.status_code == 404


def test_cannot_invite_banned_player(client) -> None:
    """Banned accounts can't be invited — keeps a banned actor from being shuffled
    into a guild that doesn't realise their status."""
    from app.db import SessionLocal
    from app.models import Account

    leader_hdr, _ = _register(client)
    gid = _make_guild(client, leader_hdr)
    _, target_id = _register(client)

    db = SessionLocal()
    try:
        acct = db.get(Account, target_id)
        acct.is_banned = True
        db.commit()
    finally:
        db.close()

    r = client.post(f"/guilds/{gid}/invite/{target_id}", json={}, headers=leader_hdr)
    assert r.status_code == 409
