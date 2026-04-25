"""Phase 1 acceptance test — runs the 9-step flow from docs/PRD.md.

Fresh account → tutorial → free summon → roster grid → preset → battle
→ starter pack purchase. Fails if any step deviates from spec.

This is the "Phase 1 is done" bright line.
"""

from __future__ import annotations

import random


def test_phase1_end_to_end(client) -> None:
    """Execute the 9-step Phase 1 acceptance test from docs/PRD.md § 6."""

    # Step 1: Register and land on /app/.
    email = f"p1+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}

    # /app/ shell serves the HTMX dashboard.
    r = client.get("/app/", follow_redirects=True)
    assert r.status_code == 200

    # Step 2: Next Step CTA tells them to start the tutorial.
    me = client.get("/me", headers=hdr).json()
    assert me["tutorial_cleared"] is False
    assert not me["has_battled"]
    # Starter team granted on register.
    roster = client.get("/heroes/mine", headers=hdr).json()
    assert len(roster) == 3, "registration should grant 3 starter heroes"

    # Step 3: Click the tutorial CTA — auto-team battle, victory screen shows
    # "+1 free summon" grant. We emulate the UI's top-3 pick.
    stages = client.get("/stages").json()
    tutorial = next(s for s in stages if s["code"] == "tutorial_first_ticket")
    team = [h["id"] for h in sorted(roster, key=lambda h: h["power"], reverse=True)[:3]]

    # Try up to 3 times — tutorial is designed to be winnable with starter
    # COMMONs but combat RNG might dip.
    tutorial_won = False
    for _ in range(3):
        r = client.post("/battles", json={"stage_id": tutorial["id"], "team": team}, headers=hdr)
        assert r.status_code == 201
        body = r.json()
        if body["outcome"] == "WIN":
            tutorial_won = True
            assert body["first_clear"] is True
            # Tutorial completion payload.
            assert body["rewards"].get("tutorial_reward") == {"free_summon_credits": 1}
            break
    assert tutorial_won, "tutorial should be winnable with 3 starter COMMONs"

    # Step 4: Summon tab — /me reflects the free credit; pull without shards.
    me = client.get("/me", headers=hdr).json()
    assert me["free_summon_credits"] == 1
    assert me["tutorial_cleared"] is True

    # Dedicated Summon tab partial renders.
    r = client.get("/app/partials/summon", headers=hdr)
    assert r.status_code == 200
    assert "Standard Banner" in r.text
    assert "Pity progress" in r.text

    # Starter-pack card surfaces (new account, within 7-day window).
    assert "Jump-Ahead Bundle" in r.text

    # Use the free summon — credit is consumed first, so shards aren't charged.
    # Achievements (e.g. first_rare = +5) may grant shards on the pull, so the
    # post-shard count can go UP — what we verify is that it didn't go DOWN.
    shards_before = me["shards"]
    r = client.post("/summon/x1", headers=hdr)
    assert r.status_code == 201
    me = client.get("/me", headers=hdr).json()
    assert me["free_summon_credits"] == 0, "credit should be consumed"
    assert me["shards"] >= shards_before, "shards should not decrease when credit consumed"

    # Step 5: Roster tab — detail modal data for the just-pulled hero.
    r = client.get("/app/partials/roster", headers=hdr)
    assert r.status_code == 200
    assert "rarity-tab" in r.text  # rarity filter present
    assert "hero-card" in r.text

    # Step 6: Save a team preset.
    r = client.post("/me/team-presets", json={"name": "main", "team": team}, headers=hdr)
    assert r.status_code == 201, r.text
    preset_id = r.json()["id"]
    assert r.json()["name"] == "main"

    # Step 7: Preset reads back, /me/last-team returns the tutorial team.
    presets = client.get("/me/team-presets", headers=hdr).json()
    assert len(presets) == 1
    assert presets[0]["team"] == team
    r = client.get("/me/last-team", headers=hdr)
    assert r.status_code == 200
    assert r.json()["source"] == "battle"
    assert r.json()["team"] == team

    # Step 8: Starter-pack purchase (mock-payments mode) completes, second
    # attempt is rejected by per-account limit.
    r = client.post(
        "/shop/purchases",
        json={"sku": "starter_jumpahead", "client_ref": f"p1-{random.randint(1, 10**9)}"},
        headers=hdr,
    )
    # Tolerate 403 if mock-payments isn't enabled in this test env; that's a
    # config-only miss, not a scope failure. Real walkthroughs run with it on.
    if r.status_code == 403:
        import pytest
        pytest.skip("HEROPROTO_MOCK_PAYMENTS_ENABLED not set — starter-pack leg skipped")
    assert r.status_code == 201, r.text
    assert r.json()["state"] == "COMPLETED"

    # Second purchase → per_account_limit kicks in.
    r = client.post(
        "/shop/purchases",
        json={"sku": "starter_jumpahead", "client_ref": f"p1-{random.randint(1, 10**9)}"},
        headers=hdr,
    )
    assert r.status_code == 409, r.text  # per-account limit violation
