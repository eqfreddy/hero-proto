"""Admin analytics overview: reads across Account/Battle/Purchase/GachaRecord/
ArenaMatch/RaidAttempt and produces a product-level dashboard."""

from __future__ import annotations

import random

from app.db import SessionLocal
from app.models import Account


def _register(client, prefix: str = "an") -> tuple[str, dict, int]:
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    token = r.json()["access_token"]
    hdr = {"Authorization": f"Bearer {token}"}
    me = client.get("/me", headers=hdr).json()
    return email, hdr, me["id"]


def _promote(account_id: int) -> None:
    with SessionLocal() as db:
        db.get(Account, account_id).is_admin = True
        db.commit()


def test_analytics_requires_admin(client) -> None:
    email, hdr, _ = _register(client)
    r = client.get("/admin/analytics/overview", headers=hdr)
    assert r.status_code == 403


def test_analytics_overview_shape(client) -> None:
    email, hdr, aid = _register(client, "an")
    _promote(aid)
    r = client.get("/admin/analytics/overview", headers=hdr)
    assert r.status_code == 200
    body = r.json()
    # Top-level integer/float fields.
    for key in (
        "accounts_total", "accounts_dau", "accounts_wau",
        "accounts_banned", "accounts_verified", "accounts_with_2fa",
        "payers_total", "payer_conversion_pct",
        "avg_summons_per_account",
    ):
        assert key in body, f"missing {key}"
    # Nested buckets.
    for bucket_name in ("purchases", "battles", "arena_matches", "raid_attempts", "summons"):
        bucket = body[bucket_name]
        for k in ("last_24h", "last_7d", "total"):
            assert k in bucket, f"missing {bucket_name}.{k}"
    # Revenue block.
    for k in ("total_cents", "last_24h_cents", "last_7d_cents", "refunded_cents"):
        assert k in body["revenue"], f"missing revenue.{k}"


def test_analytics_counts_activity(client) -> None:
    """Register 2 accounts, generate purchases/summons/battles on one, promote the
    other, hit the analytics endpoint and verify the counters reflect reality."""
    admin_email, admin_hdr, admin_id = _register(client, "ancount_adm")
    _promote(admin_id)

    # Player generates activity.
    email, hdr, aid = _register(client, "ancount")
    client.post("/summon/x10", headers=hdr)
    client.post("/summon/x1", headers=hdr)

    roster = sorted(
        client.get("/heroes/mine", headers=hdr).json(),
        key=lambda h: h["power"], reverse=True,
    )
    team = [h["id"] for h in roster[:3]]
    stage1 = next(s for s in client.get("/stages").json() if s["order"] == 1)
    client.post("/battles", json={"stage_id": stage1["id"], "team": team}, headers=hdr)

    # Make a purchase.
    client.post("/shop/purchases", json={"sku": "gems_small"}, headers=hdr)

    # Now check.
    body = client.get("/admin/analytics/overview", headers=admin_hdr).json()
    assert body["accounts_total"] >= 2
    assert body["payers_total"] >= 1
    assert body["payer_conversion_pct"] > 0
    # At least 10 pulls from the x10 (the x1 may fail if out of shards).
    assert body["summons"]["total"] >= 10
    assert body["battles"]["total"] >= 1
    # gems_small is 499 cents per shop seed.
    assert body["revenue"]["total_cents"] >= 499


def test_analytics_tracks_verified_and_2fa_accounts(client) -> None:
    import pyotp
    admin_email, admin_hdr, admin_id = _register(client, "anv_adm")
    _promote(admin_id)

    before = client.get("/admin/analytics/overview", headers=admin_hdr).json()

    # Verify one account.
    email, hdr, aid = _register(client, "anv")
    client.post("/auth/send-verification", headers=hdr)
    with SessionLocal() as db:
        a = db.get(Account, aid)
        a.email_verified = True
        db.commit()

    # 2FA-enable another.
    email2, hdr2, aid2 = _register(client, "antfa")
    with SessionLocal() as db:
        a = db.get(Account, aid2)
        a.totp_secret = pyotp.random_base32()
        a.totp_enabled = True
        db.commit()

    after = client.get("/admin/analytics/overview", headers=admin_hdr).json()
    assert after["accounts_verified"] >= before["accounts_verified"] + 1
    assert after["accounts_with_2fa"] >= before["accounts_with_2fa"] + 1


def test_analytics_handles_empty_state(client) -> None:
    """On a fresh-ish DB (no payers yet), payer_conversion_pct is 0, avg_summons=0."""
    admin_email, admin_hdr, admin_id = _register(client, "anfresh_adm")
    _promote(admin_id)
    body = client.get("/admin/analytics/overview", headers=admin_hdr).json()
    # Shape sane even when counts are low.
    assert isinstance(body["payer_conversion_pct"], (int, float))
    assert isinstance(body["avg_summons_per_account"], (int, float))
    assert body["payer_conversion_pct"] >= 0
    assert body["avg_summons_per_account"] >= 0


def test_analytics_tracks_refunds_separately(client) -> None:
    admin_email, admin_hdr, admin_id = _register(client, "anref_adm")
    _promote(admin_id)
    buyer_email, buyer_hdr, buyer_id = _register(client, "anref_buy")
    buy = client.post("/shop/purchases", json={"sku": "gems_small"}, headers=buyer_hdr).json()
    before = client.get("/admin/analytics/overview", headers=admin_hdr).json()["revenue"]

    # Refund the purchase — refunded_cents should grow.
    client.post(f"/admin/purchases/{buy['id']}/refund", json={"reason": "test"}, headers=admin_hdr)
    after = client.get("/admin/analytics/overview", headers=admin_hdr).json()["revenue"]

    assert after["refunded_cents"] >= before["refunded_cents"] + 499
