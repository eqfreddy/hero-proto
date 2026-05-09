"""Tests for template-shard ascension currency."""
from __future__ import annotations

import json
import random

from tests.conftest import *  # noqa


def _register(client, tag):
    email = f"shard-{tag}-{random.randint(1000000,9999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    return tok, client.get("/me", headers={"Authorization": f"Bearer {tok}"}).json()["id"]


def _hdr(t):
    return {"Authorization": f"Bearer {t}"}


def _set_shards_balance(aid, code, n):
    from app.db import SessionLocal
    from app.models import Account
    with SessionLocal() as db:
        a = db.get(Account, aid)
        a.template_shards_json = json.dumps({code: n})
        db.commit()


def test_template_shards_default_empty(client):
    tok, _ = _register(client, "empty")
    r = client.get("/heroes/template-shards", headers=_hdr(tok))
    assert r.status_code == 200
    assert r.json() == {}


def test_dupe_pull_grants_shards(client):
    """A duplicate summon pull grants template shards based on rarity.
    Hard to test the standard banner reliably (RNG), so we go via service
    directly and just confirm the contract."""
    from app.db import SessionLocal
    from app.models import Account, Rarity
    from app.template_shards import grant_dupe_shards, SHARDS_ON_DUPE

    tok, aid = _register(client, "dupe")
    with SessionLocal() as db:
        a = db.get(Account, aid)
        new_bal = grant_dupe_shards(a, "ticket_gremlin", Rarity.RARE)
        db.commit()
    assert new_bal == SHARDS_ON_DUPE[Rarity.RARE]
    r = client.get("/heroes/template-shards", headers=_hdr(tok))
    assert r.json() == {"ticket_gremlin": 25}


def test_ascend_with_shards_succeeds(client):
    tok, aid = _register(client, "asc")
    # Summon enough heroes to get one to ascend.
    client.post("/summon/x10", headers=_hdr(tok))
    heroes = client.get("/heroes/mine", headers=_hdr(tok)).json()
    hero = heroes[0]
    # Top up shards for this template.
    _set_shards_balance(aid, hero["template"]["code"], 100)
    r = client.post(f"/heroes/{hero['id']}/ascend-with-shards", headers=_hdr(tok))
    assert r.status_code == 200, r.text
    assert r.json()["stars"] == 2
    # 10 shards spent (1->2 cost), 90 remaining.
    bal = client.get("/heroes/template-shards", headers=_hdr(tok)).json()
    assert bal[hero["template"]["code"]] == 90


def test_ascend_with_insufficient_shards_409(client):
    tok, aid = _register(client, "broke")
    client.post("/summon/x10", headers=_hdr(tok))
    hero = client.get("/heroes/mine", headers=_hdr(tok)).json()[0]
    _set_shards_balance(aid, hero["template"]["code"], 5)  # need 10
    r = client.post(f"/heroes/{hero['id']}/ascend-with-shards", headers=_hdr(tok))
    assert r.status_code == 409
    assert "need 10" in r.text


def test_ascend_with_shards_at_max_stars_409(client):
    """Cannot ascend at MAX_STARS=6 even with shards."""
    tok, aid = _register(client, "maxed")
    client.post("/summon/x10", headers=_hdr(tok))
    hero = client.get("/heroes/mine", headers=_hdr(tok)).json()[0]
    from app.db import SessionLocal
    from app.models import Account, HeroInstance
    with SessionLocal() as db:
        h = db.get(HeroInstance, hero["id"])
        h.stars = 6
        db.commit()
    _set_shards_balance(aid, hero["template"]["code"], 10000)
    r = client.post(f"/heroes/{hero['id']}/ascend-with-shards", headers=_hdr(tok))
    assert r.status_code == 409
    assert "max stars" in r.text.lower()


def test_six_star_level_cap_climbs():
    """Pure unit test — bumping stars to 6 raises the cap.
    (Pre-existing formula: 10 + 5*stars; 5★=35, 6★=40.)"""
    from app.combat import level_cap_for_stars
    assert level_cap_for_stars(5) == 35
    assert level_cap_for_stars(6) == 40
    # Cap doesn't keep climbing past 6 (defensive).
    assert level_cap_for_stars(99) == 40
