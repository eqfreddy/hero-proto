"""Phase 3 teaser — /achievements surfaces a `hardcore` block alongside
the regular unlock list. No predicates yet; these are visible-but-locked
chase goals to give players a reason to come back.

When Hardcore mode ships (Phase 3.5), these get real predicates +
rewards and graduate into the main ACHIEVEMENTS list.
"""

from __future__ import annotations

import random


def _register(client) -> dict:
    email = f"hc+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def test_achievements_endpoint_includes_hardcore_block(client) -> None:
    hdr = _register(client)
    r = client.get("/achievements", headers=hdr)
    assert r.status_code == 200, r.text
    body = r.json()
    assert "hardcore" in body
    assert isinstance(body["hardcore"], list)
    assert len(body["hardcore"]) >= 5  # at least the seed teasers
    for h in body["hardcore"]:
        for k in ("code", "title", "description", "icon", "reward_preview"):
            assert k in h, h
        assert h["code"].startswith("hc_"), h


def test_hardcore_codes_unique(client) -> None:
    hdr = _register(client)
    body = client.get("/achievements", headers=hdr).json()
    codes = [h["code"] for h in body["hardcore"]]
    assert len(codes) == len(set(codes)), f"duplicate hardcore codes: {codes}"


def test_hardcore_does_not_pollute_unlocked_count(client) -> None:
    """Hardcore teasers must not count toward `total` / `unlocked` —
    those numbers track real shippable achievements only."""
    hdr = _register(client)
    body = client.get("/achievements", headers=hdr).json()
    assert body["total"] == len(body["items"]), \
        "total must equal len(items); hardcore is a separate block"
    assert body["unlocked"] <= body["total"]
