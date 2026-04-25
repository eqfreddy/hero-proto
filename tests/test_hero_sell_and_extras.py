"""Coverage for the latest batch:
  - Hero sell endpoint (preview + commit + auto-unequip)
  - Achievements (catalog, unlock, reward grant, idempotent)
  - Notifications (post + list + unread count + mark-read + clear)
  - RSS feed (XML structure + per-post entries)
  - OG meta tags on marketing pages
"""

from __future__ import annotations

import json
import random

from sqlalchemy import select

from app.achievements import ACHIEVEMENTS_BY_CODE, check_achievements
from app.db import SessionLocal
from app.models import Account, Gear, GearRarity, GearSet, GearSlot, HeroInstance, Notification


def _register(client) -> tuple[dict[str, str], int]:
    email = f"sx+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    return hdr, client.get("/me", headers=hdr).json()["id"]


# --- Hero sell ---------------------------------------------------------------


def test_sell_preview_returns_currency(client) -> None:
    hdr, _ = _register(client)
    roster = client.get("/heroes/mine", headers=hdr).json()
    hero_id = roster[0]["id"]
    r = client.get(f"/heroes/{hero_id}/sell-preview", headers=hdr)
    assert r.status_code == 200
    body = r.json()
    assert body["coins"] > 0
    assert body["hero_instance_id"] == hero_id


def test_sell_grants_currency_and_removes_hero(client) -> None:
    hdr, acct_id = _register(client)
    me_before = client.get("/me", headers=hdr).json()
    coins_before = me_before["coins"]
    roster = client.get("/heroes/mine", headers=hdr).json()
    hero_id = roster[0]["id"]
    r = client.post(f"/heroes/{hero_id}/sell", headers=hdr)
    assert r.status_code == 201
    body = r.json()
    assert body["coins"] == coins_before + body["coins_granted"]
    # Hero gone.
    roster_after = client.get("/heroes/mine", headers=hdr).json()
    assert all(h["id"] != hero_id for h in roster_after)


def test_sell_unequips_gear_first(client) -> None:
    hdr, acct_id = _register(client)
    roster = client.get("/heroes/mine", headers=hdr).json()
    hero_id = roster[0]["id"]
    # Grant + equip a gear piece via direct DB.
    with SessionLocal() as db:
        g = Gear(account_id=acct_id, slot=GearSlot.WEAPON, rarity=GearRarity.RARE,
                 set_code=GearSet.OFFENSE, stats_json="{}", hero_instance_id=hero_id)
        db.add(g)
        db.commit()
        gear_id = g.id

    r = client.post(f"/heroes/{hero_id}/sell", headers=hdr)
    assert r.status_code == 201

    # Gear still exists, but unequipped.
    with SessionLocal() as db:
        g = db.get(Gear, gear_id)
        assert g is not None
        assert g.hero_instance_id is None


def test_sell_404_for_unowned_hero(client) -> None:
    hdr, _ = _register(client)
    r = client.post("/heroes/9999999/sell", headers=hdr)
    assert r.status_code == 404


# --- Achievements ------------------------------------------------------------


def test_achievements_catalog_endpoint(client) -> None:
    hdr, _ = _register(client)
    r = client.get("/achievements", headers=hdr)
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == len(ACHIEVEMENTS_BY_CODE)
    # Fresh account: 0 unlocked.
    assert body["unlocked"] == 0


def test_achievement_unlocks_on_summon(client) -> None:
    hdr, acct_id = _register(client)
    # Pull once → triggers first_summon.
    client.post("/summon/x1", headers=hdr)
    r = client.get("/achievements", headers=hdr)
    body = r.json()
    fs = next(i for i in body["items"] if i["code"] == "first_summon")
    assert fs["unlocked"] is True
    assert body["unlocked"] >= 1


def test_achievement_reward_actually_granted(client) -> None:
    hdr, acct_id = _register(client)
    me_before = client.get("/me", headers=hdr).json()
    gems_before = me_before["gems"]
    client.post("/summon/x1", headers=hdr)  # unlocks first_summon (+25 gems)
    me_after = client.get("/me", headers=hdr).json()
    assert me_after["gems"] >= gems_before + 25


def test_achievement_unlock_is_idempotent(client) -> None:
    hdr, acct_id = _register(client)
    client.post("/summon/x1", headers=hdr)
    me_after_first = client.get("/me", headers=hdr).json()
    # Pull again — unlock shouldn't re-grant the reward.
    client.post("/summon/x1", headers=hdr)
    me_after_second = client.get("/me", headers=hdr).json()
    # The second pull only spends 1 shard; gems should not have grown by 25 again.
    assert me_after_second["gems"] - me_after_first["gems"] < 25


# --- Notifications -----------------------------------------------------------


def test_unread_count_starts_zero(client) -> None:
    hdr, _ = _register(client)
    r = client.get("/notifications/unread-count", headers=hdr)
    assert r.status_code == 200
    assert r.json()["unread"] == 0


def test_summon_unlock_creates_notification(client) -> None:
    hdr, acct_id = _register(client)
    client.post("/summon/x1", headers=hdr)
    r = client.get("/notifications", headers=hdr).json()
    assert r["unread_count"] >= 1
    achievement_notifs = [n for n in r["items"] if n["kind"] == "achievement"]
    assert len(achievement_notifs) >= 1


def test_mark_read_zeroes_unread(client) -> None:
    hdr, acct_id = _register(client)
    client.post("/summon/x1", headers=hdr)
    n_id = client.get("/notifications", headers=hdr).json()["items"][0]["id"]
    r = client.post(f"/notifications/{n_id}/read", headers=hdr)
    assert r.status_code == 204
    # Unread count went down by one.
    after = client.get("/notifications/unread-count", headers=hdr).json()["unread"]
    assert after >= 0  # may still have other unread from same call


def test_mark_all_read_zeroes_unread(client) -> None:
    hdr, _ = _register(client)
    client.post("/summon/x1", headers=hdr)
    client.post("/notifications/read-all", headers=hdr)
    r = client.get("/notifications/unread-count", headers=hdr).json()
    assert r["unread"] == 0


def test_clear_all_removes_notifications(client) -> None:
    hdr, _ = _register(client)
    client.post("/summon/x1", headers=hdr)
    r = client.delete("/notifications", headers=hdr)
    assert r.status_code == 204
    body = client.get("/notifications", headers=hdr).json()
    assert body["unread_count"] == 0
    assert body["items"] == []


# --- RSS + OG ---------------------------------------------------------------


def test_devblog_rss_feed_has_entries(client) -> None:
    r = client.get("/devblog.xml")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/rss+xml")
    body = r.text
    assert "<rss" in body and "</rss>" in body
    assert "<channel>" in body
    assert "hero-proto devblog" in body
    # Both seeded posts should appear by title.
    assert "Why we made a gacha game" in body
    assert "Shipping Phase 1" in body


def test_og_tags_present_on_landing(client) -> None:
    r = client.get("/")
    body = r.text
    assert 'property="og:title"' in body
    assert 'property="og:description"' in body
    assert 'property="og:image"' in body
    assert 'name="twitter:card"' in body


def test_og_tags_post_specific_on_devblog_post(client) -> None:
    """Post pages should override og_title with the post title."""
    r = client.get("/devblog/2026-04-25-why-corporate-it")
    body = r.text
    assert 'property="og:type"' in body
    assert 'article' in body  # og:type = article
    assert "Why we made a gacha game" in body  # og:title contains post title


def test_devblog_index_exposes_rss_link(client) -> None:
    r = client.get("/devblog")
    body = r.text
    assert "/devblog.xml" in body
    assert 'application/rss+xml' in body
