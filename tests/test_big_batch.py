"""Coverage for the final ranked-list batch:
  - Account level + XP grants
  - Story chapters (catalog + cutscene mark-seen)
  - Friends + DMs (request, accept, block, send DM, mark read, report)
  - IAP receipt verification (Apple + Google fake-mode)
"""

from __future__ import annotations

import json
import random

from sqlalchemy import select

from app.account_level import (
    ACCOUNT_LEVEL_CAP,
    STORY_CHAPTERS,
    grant_xp,
    xp_to_next,
)
from app.db import SessionLocal
from app.models import Account, DirectMessage, Friendship, FriendshipStatus
from app.payment_adapters import AppleAdapter, GoogleAdapter, ReceiptError


def _register(client) -> tuple[dict[str, str], int, str]:
    email = f"big+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    return hdr, client.get("/me", headers=hdr).json()["id"], email


# --- Account level + XP -----------------------------------------------------


def test_xp_curve_is_triangular() -> None:
    assert xp_to_next(1) == 100
    assert xp_to_next(5) == 500
    assert xp_to_next(50) == 5000


def test_grant_xp_increments_account_xp(client) -> None:
    hdr, acct_id, _ = _register(client)
    me_before = client.get("/me", headers=hdr).json()
    assert me_before["account_level"] == 1
    assert me_before["account_xp"] == 0

    with SessionLocal() as db:
        a = db.get(Account, acct_id)
        levelups = grant_xp(db, a, 50)
        db.commit()
    assert levelups == []  # 50 < 100 needed

    me = client.get("/me", headers=hdr).json()
    assert me["account_xp"] == 50


def test_grant_xp_levels_up_with_reward(client) -> None:
    hdr, acct_id, _ = _register(client)
    me_before = client.get("/me", headers=hdr).json()
    gems_before = me_before["gems"]

    with SessionLocal() as db:
        a = db.get(Account, acct_id)
        levelups = grant_xp(db, a, 250)  # exceeds 100 needed for L1->L2
        db.commit()

    assert len(levelups) >= 1
    assert levelups[0]["level"] == 2
    assert levelups[0]["granted"].get("gems", 0) > 0

    me = client.get("/me", headers=hdr).json()
    assert me["account_level"] >= 2
    assert me["gems"] > gems_before


def test_battle_win_grants_account_xp(client) -> None:
    hdr, acct_id, _ = _register(client)
    stages = client.get("/stages").json()
    tutorial = next(s for s in stages if s["code"] == "tutorial_first_ticket")
    roster = client.get("/heroes/mine", headers=hdr).json()
    team = [h["id"] for h in sorted(roster, key=lambda h: h["power"], reverse=True)[:3]]

    won = False
    for _ in range(3):
        r = client.post("/battles", json={"stage_id": tutorial["id"], "team": team}, headers=hdr)
        if r.status_code == 201 and r.json()["outcome"] == "WIN":
            won = True
            break
    assert won

    me = client.get("/me", headers=hdr).json()
    # First clear bonus + battle XP — at least 12 total. Achievement system
    # may also have leveled the account up; either way XP-or-level moved.
    assert me["account_xp"] > 0 or me["account_level"] > 1


# --- Story ------------------------------------------------------------------


def test_story_catalog_endpoint(client) -> None:
    hdr, _, _ = _register(client)
    r = client.get("/story", headers=hdr)
    assert r.status_code == 200
    body = r.json()
    assert body["account_level"] == 1
    assert len(body["chapters"]) == len(STORY_CHAPTERS)
    # First chapter must be unlocked at level 1.
    ch1 = body["chapters"][0]
    assert ch1["unlocked"] is True
    # Later chapters locked.
    later_locked = [c for c in body["chapters"] if c["unlock_level"] > 1]
    assert all(not c["unlocked"] for c in later_locked)


def test_cutscene_mark_seen_persists(client) -> None:
    hdr, acct_id, _ = _register(client)
    r = client.post("/story/cutscene-seen", json={
        "chapter_code": "onboarding_arc",
        "stage_code": "tutorial_first_ticket",
        "beat": "intro",
    }, headers=hdr)
    assert r.status_code == 204

    with SessionLocal() as db:
        a = db.get(Account, acct_id)
        state = json.loads(a.story_state_json or "{}")
    assert "onboarding_arc:tutorial_first_ticket:intro" in state


def test_cutscene_unknown_chapter_404(client) -> None:
    hdr, _, _ = _register(client)
    r = client.post("/story/cutscene-seen", json={
        "chapter_code": "fake_chapter", "stage_code": "x", "beat": "intro",
    }, headers=hdr)
    assert r.status_code == 404


def test_cutscene_bad_beat_400(client) -> None:
    hdr, _, _ = _register(client)
    r = client.post("/story/cutscene-seen", json={
        "chapter_code": "onboarding_arc", "stage_code": "tutorial_first_ticket",
        "beat": "middle",
    }, headers=hdr)
    assert r.status_code == 400


# --- Friends ----------------------------------------------------------------


def _two_users(client) -> tuple[tuple[dict, int, str], tuple[dict, int, str]]:
    a = _register(client)
    b = _register(client)
    return a, b


def test_friend_request_by_email_prefix(client) -> None:
    (h1, id1, e1), (h2, id2, e2) = _two_users(client)
    prefix2 = e2.split("@")[0]
    r = client.post("/friends/request", json={"email_prefix": prefix2}, headers=h1)
    assert r.status_code == 201, r.text
    assert r.json()["account_id"] == id2
    # Other user sees an incoming request.
    incoming = client.get("/friends/requests", headers=h2).json()
    assert any(f["account_id"] == id1 for f in incoming)


def test_friend_accept_creates_bidirectional(client) -> None:
    (h1, id1, e1), (h2, id2, e2) = _two_users(client)
    client.post("/friends/request", json={"email_prefix": e2.split("@")[0]}, headers=h1)
    r = client.post(f"/friends/{id1}/accept", headers=h2)
    assert r.status_code == 200
    # Both see each other in /friends.
    assert any(f["account_id"] == id2 for f in client.get("/friends", headers=h1).json())
    assert any(f["account_id"] == id1 for f in client.get("/friends", headers=h2).json())


def test_friend_request_self_404(client) -> None:
    h1, id1, _ = _register(client)
    r = client.post("/friends/request", json={"account_id": id1}, headers=h1)
    assert r.status_code == 404


def test_friend_request_unknown_email_404(client) -> None:
    h1, _, _ = _register(client)
    r = client.post("/friends/request", json={"email_prefix": "definitely_not_a_real_user_zzz"}, headers=h1)
    assert r.status_code == 404


def test_unfriend_removes_both_rows(client) -> None:
    (h1, id1, e1), (h2, id2, e2) = _two_users(client)
    client.post("/friends/request", json={"email_prefix": e2.split("@")[0]}, headers=h1)
    client.post(f"/friends/{id1}/accept", headers=h2)
    r = client.delete(f"/friends/{id2}", headers=h1)
    assert r.status_code == 204
    # Neither sees the friendship.
    assert client.get("/friends", headers=h1).json() == []
    assert client.get("/friends", headers=h2).json() == []


def test_block_prevents_dm(client) -> None:
    (h1, id1, e1), (h2, id2, e2) = _two_users(client)
    # h1 blocks h2.
    r = client.post(f"/friends/{id2}/block", headers=h1)
    assert r.status_code == 201
    # h2 can't DM h1.
    r = client.post(f"/dm/with/{id1}", json={"body": "let me back in"}, headers=h2)
    assert r.status_code == 403


# --- DMs --------------------------------------------------------------------


def test_dm_send_and_thread(client) -> None:
    (h1, id1, e1), (h2, id2, e2) = _two_users(client)
    r = client.post(f"/dm/with/{id2}", json={"body": "hi"}, headers=h1)
    assert r.status_code == 201
    msg_id = r.json()["id"]
    # h2 sees the thread + unread.
    threads = client.get("/dm/threads", headers=h2).json()
    assert any(t["other_account_id"] == id1 and t["unread_count"] == 1 for t in threads)
    # h2 reads the thread.
    r = client.post(f"/dm/with/{id1}/read-all", headers=h2)
    assert r.status_code == 204
    threads = client.get("/dm/threads", headers=h2).json()
    assert next(t for t in threads if t["other_account_id"] == id1)["unread_count"] == 0


def test_dm_to_self_400(client) -> None:
    h1, id1, _ = _register(client)
    r = client.post(f"/dm/with/{id1}", json={"body": "hi"}, headers=h1)
    assert r.status_code == 400


def test_dm_report_creates_report_row(client) -> None:
    (h1, id1, e1), (h2, id2, e2) = _two_users(client)
    msg_id = client.post(f"/dm/with/{id2}", json={"body": "obviously rude"}, headers=h1).json()["id"]
    r = client.post(f"/dm/{msg_id}/report", json={"reason": "rude"}, headers=h2)
    assert r.status_code == 201
    assert r.json()["reported_message_id"] == msg_id


# --- IAP receipt verification -----------------------------------------------


def test_apple_fake_receipt_verifies() -> None:
    fake = "fake-apple:" + json.dumps({"productId": "gems_small", "transactionId": "tx-001"})
    v = AppleAdapter().verify(fake, claimed_sku="gems_small")
    assert v.processor == "apple"
    assert v.processor_ref == "tx-001"
    assert v.sku == "gems_small"
    assert v.sandbox is True


def test_apple_fake_sku_mismatch_rejected() -> None:
    fake = "fake-apple:" + json.dumps({"productId": "gems_large", "transactionId": "tx-001"})
    import pytest
    with pytest.raises(ReceiptError, match="sku mismatch"):
        AppleAdapter().verify(fake, claimed_sku="gems_small")


def test_apple_empty_receipt_rejected() -> None:
    import pytest
    with pytest.raises(ReceiptError, match="empty"):
        AppleAdapter().verify("", claimed_sku="gems_small")


def test_apple_malformed_fake_rejected() -> None:
    import pytest
    with pytest.raises(ReceiptError, match="malformed"):
        AppleAdapter().verify("fake-apple:not_json", claimed_sku="gems_small")


def test_google_fake_receipt_verifies() -> None:
    fake = "fake-google:" + json.dumps({"productId": "shards_pack", "orderId": "ord-42"})
    v = GoogleAdapter().verify(fake, claimed_sku="shards_pack")
    assert v.processor == "google"
    assert v.processor_ref == "ord-42"
    assert v.sandbox is True


def test_iap_apple_endpoint_grants_currency(client) -> None:
    hdr, acct_id, _ = _register(client)
    me_before = client.get("/me", headers=hdr).json()
    gems_before = me_before["gems"]

    fake = "fake-apple:" + json.dumps({"productId": "gems_small", "transactionId": "tx-iap-001"})
    r = client.post("/shop/iap/apple", json={"sku": "gems_small", "receipt": fake}, headers=hdr)
    assert r.status_code == 201, r.text
    assert r.json()["state"] == "COMPLETED"

    me_after = client.get("/me", headers=hdr).json()
    assert me_after["gems"] > gems_before


def test_iap_apple_idempotent_on_duplicate_receipt(client) -> None:
    hdr, _, _ = _register(client)
    fake = "fake-apple:" + json.dumps({"productId": "gems_small", "transactionId": "tx-iap-dup"})
    r1 = client.post("/shop/iap/apple", json={"sku": "gems_small", "receipt": fake}, headers=hdr)
    r2 = client.post("/shop/iap/apple", json={"sku": "gems_small", "receipt": fake}, headers=hdr)
    assert r1.status_code == 201 and r2.status_code == 201
    # Same purchase id returned both times.
    assert r1.json()["id"] == r2.json()["id"]


def test_iap_google_endpoint_grants_currency(client) -> None:
    hdr, _, _ = _register(client)
    fake = "fake-google:" + json.dumps({"productId": "shards_pack", "orderId": "ord-iap-001"})
    r = client.post("/shop/iap/google", json={"sku": "shards_pack", "receipt": fake}, headers=hdr)
    assert r.status_code == 201
    assert r.json()["state"] == "COMPLETED"


def test_iap_unknown_sku_404(client) -> None:
    hdr, _, _ = _register(client)
    fake = "fake-apple:" + json.dumps({"productId": "this_sku_doesnt_exist", "transactionId": "tx-x"})
    r = client.post("/shop/iap/apple", json={"sku": "this_sku_doesnt_exist", "receipt": fake}, headers=hdr)
    assert r.status_code == 404


def test_iap_sku_mismatch_400(client) -> None:
    hdr, _, _ = _register(client)
    # Receipt says gems_large, claimed sku gems_small.
    fake = "fake-apple:" + json.dumps({"productId": "gems_large", "transactionId": "tx-mm"})
    r = client.post("/shop/iap/apple", json={"sku": "gems_small", "receipt": fake}, headers=hdr)
    assert r.status_code == 400
    assert "mismatch" in r.json()["detail"].lower()


# --- Analytics notebooks ----------------------------------------------------


def test_analytics_notebooks_present() -> None:
    """Catch deletions / accidental skips of the balance notebooks."""
    import pathlib
    nb_dir = pathlib.Path(__file__).resolve().parents[1] / "analytics"
    assert nb_dir.is_dir()
    expected = {"gacha_ev.ipynb", "combat_dps.ipynb", "arena_convergence.ipynb"}
    actual = {p.name for p in nb_dir.glob("*.ipynb")}
    assert expected <= actual, f"missing notebooks: {expected - actual}"
