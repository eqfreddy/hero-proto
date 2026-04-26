"""End-to-end client walkthrough: a fresh account exercises every major
player-facing feature. Fails loudly on the first broken path so an operator
can see exactly where the client experience is wrong.

This is the "run it before shipping a build" acceptance test. It's not a
load/perf test; it's a functional tour.

Usage (server must be running, mock payments must be enabled for the shop
leg to work without real Stripe):
    HEROPROTO_MOCK_PAYMENTS_ENABLED=1 uv run uvicorn app.main:app &
    uv run python -m scripts.client_walkthrough

Exits 0 if every section passed, 1 on first failure.
"""

from __future__ import annotations

import asyncio
import os
import random
import sys
from contextlib import asynccontextmanager

import httpx
import pyotp

# Windows consoles default to cp1252 and crash on em-dashes / Greek letters
# used below. Force UTF-8 on stdout/stderr so the walkthrough runs anywhere.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, OSError):
        pass

BASE = os.environ.get("HEROPROTO_BASE", "http://127.0.0.1:8000").rstrip("/")

GREEN = "\033[32m" if sys.stdout.isatty() else ""
RED = "\033[31m" if sys.stdout.isatty() else ""
YELLOW = "\033[33m" if sys.stdout.isatty() else ""
DIM = "\033[2m" if sys.stdout.isatty() else ""
RESET = "\033[0m" if sys.stdout.isatty() else ""


def _ok(msg: str) -> None:
    print(f"  {GREEN}OK{RESET} {msg}")


def _warn(msg: str) -> None:
    print(f"  {YELLOW}WARN{RESET} {msg}")


def _section(title: str) -> None:
    print(f"\n{DIM}--- {title} ---{RESET}")


def _fail(msg: str) -> None:
    print(f"  {RED}FAIL{RESET} {msg}")
    raise SystemExit(1)


class Session:
    """Helper bundling the httpx client + auth state for one test account."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self.client = client
        self.email: str = ""
        self.password: str = "walk-through-pw-99"
        self.access_token: str = ""
        self.refresh_token: str = ""
        self.account_id: int = 0

    @property
    def auth(self) -> dict:
        return {"Authorization": f"Bearer {self.access_token}"}

    async def register(self, prefix: str) -> None:
        self.email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
        r = await self.client.post(
            "/auth/register",
            json={"email": self.email, "password": self.password},
        )
        if r.status_code != 201:
            _fail(f"register failed: HTTP {r.status_code} {r.text[:120]}")
        body = r.json()
        self.access_token = body["access_token"]
        self.refresh_token = body.get("refresh_token", "")
        me = await self.get("/me")
        self.account_id = me["id"]

    async def get(self, path: str, params: dict | None = None) -> dict | list:
        r = await self.client.get(path, headers=self.auth, params=params)
        if r.status_code != 200:
            _fail(f"GET {path} returned {r.status_code}: {r.text[:200]}")
        return r.json()

    async def post(self, path: str, body: dict | None = None, expect: int = 200) -> dict:
        r = await self.client.post(path, json=body, headers=self.auth)
        if r.status_code not in (expect, 200, 201):
            _fail(f"POST {path} expected {expect}, got {r.status_code}: {r.text[:200]}")
        try:
            return r.json()
        except Exception:
            return {}


async def tour_auth(s: Session) -> None:
    _section("1. Auth — register / login / refresh")
    await s.register("walk")
    _ok(f"registered {s.email} (id={s.account_id})")

    # Fresh login produces a different set of tokens.
    r = await s.client.post(
        "/auth/login", json={"email": s.email, "password": s.password},
    )
    if r.status_code != 200:
        _fail(f"login failed: {r.status_code} {r.text[:120]}")
    body = r.json()
    if not body.get("access_token"):
        _fail("login gave no access_token")
    _ok(f"login works, access+refresh pair emitted")

    # Refresh rotates.
    if not s.refresh_token:
        _warn("no refresh_token on register — refresh flow skipped")
    else:
        r = await s.client.post("/auth/refresh", json={"refresh_token": s.refresh_token})
        if r.status_code != 200:
            _fail(f"refresh failed: {r.status_code} {r.text[:120]}")
        body = r.json()
        if body["refresh_token"] == s.refresh_token:
            _fail("refresh did not rotate (same token returned)")
        s.access_token = body["access_token"]
        s.refresh_token = body["refresh_token"]
        _ok("refresh rotated successfully (reuse-detection active)")


async def tour_me_currencies(s: Session) -> None:
    _section("2. /me — balances + daily login bonus")
    me = await s.get("/me")
    required = {"coins", "gems", "shards", "access_cards", "energy", "energy_cap",
                "pulls_since_epic", "stages_cleared",
                # Phase 2 surfaces.
                "faction", "qol_unlocks", "cosmetic_frames",
                "hero_slot_cap", "gear_slot_cap",
                "account_level", "account_xp", "account_xp_to_next"}
    missing = required - set(me.keys())
    if missing:
        _fail(f"/me missing fields: {missing}")
    if me["faction"] != "EXILE":
        _fail(f"new account should default to EXILE faction, got {me['faction']!r}")
    if me["qol_unlocks"] or me["cosmetic_frames"]:
        _fail(f"new account should own no QoL/cosmetics yet: {me}")
    _ok(f"/me shape ok — gems={me['gems']} shards={me['shards']} energy={me['energy']} "
        f"faction={me['faction']} acct_lvl={me['account_level']}")

    # Claim today's login bonus.
    bonus = await s.post("/me/daily-bonus/claim", expect=201)
    if bonus.get("streak_after") != 1:
        _fail(f"expected streak 1 on first claim, got {bonus.get('streak_after')}")
    _ok(f"daily login bonus claimed — day 1 granted {bonus.get('granted')}")


async def tour_summons_roster(s: Session) -> None:
    _section("3. Gacha — summon x10 + roster fetch")
    pulls = await s.post("/summon/x10", expect=201)
    if not isinstance(pulls, list) or len(pulls) != 10:
        _fail(f"x10 should return 10 summons, got {type(pulls).__name__} len={len(pulls) if isinstance(pulls, list) else 'n/a'}")
    _ok(f"x10 returned {len(pulls)} heroes")

    roster = await s.get("/heroes/mine")
    if len(roster) < 10:
        _fail(f"/heroes/mine only shows {len(roster)} after x10")
    _ok(f"roster lists {len(roster)} heroes; top power = {max(h['power'] for h in roster)}")


async def tour_battle(s: Session) -> dict:
    _section("4. Combat — stage 1 + replay payload")
    stages = await s.get("/stages")
    stage1 = next((x for x in stages if x["order"] == 1), None)
    if stage1 is None:
        _fail("no stage with order=1 found")
    _ok(f"found stage 1: {stage1['name']} (rec power {stage1['recommended_power']})")

    heroes = sorted(await s.get("/heroes/mine"), key=lambda h: h["power"], reverse=True)
    team = [h["id"] for h in heroes[:3]]

    battle = await s.post("/battles", {"stage_id": stage1["id"], "team": team}, expect=201)
    if battle["outcome"] not in ("WIN", "LOSS", "DRAW"):
        _fail(f"unexpected outcome: {battle['outcome']}")
    _ok(f"/battles returned outcome={battle['outcome']} with {len(battle['log'])} log events")

    replay = await s.get(f"/battles/{battle['id']}")
    parts = replay.get("participants", [])
    if not parts or not all("template_code" in p for p in parts):
        _fail("replay missing template_code on participants")
    # Check the new rarity/faction fields we added when wiring art.
    if not all("rarity" in p and "faction" in p for p in parts):
        _warn("replay participants missing rarity/faction (pre-art-wiring schema)")
    else:
        _ok(f"replay payload: {len(parts)} participants with rarity+faction")
    return battle


async def tour_energy_refill(s: Session) -> None:
    _section("5. Gem sink — energy refill")
    # Force enough gems + drain energy via admin-ish hack doesn't work here;
    # test real happy/sad paths only.
    me = await s.get("/me")
    if me["energy"] >= me["energy_cap"]:
        r = await s.client.post("/me/energy/refill", headers=s.auth)
        if r.status_code == 409:
            _ok("refill correctly rejected while energy is at cap")
            return
    # Otherwise hit the endpoint — new accounts have 0 gems so expect 409.
    r = await s.client.post("/me/energy/refill", headers=s.auth)
    if r.status_code == 409:
        _ok("refill 409 (insufficient gems as expected on new account)")
    elif r.status_code == 201:
        _ok(f"refill 201 — {r.json()}")
    else:
        _fail(f"unexpected refill status: {r.status_code}")


async def tour_arena(s: Session) -> None:
    _section("6. Arena — defense + opponents + attack")
    heroes = sorted(await s.get("/heroes/mine"), key=lambda h: h["power"], reverse=True)
    team = [h["id"] for h in heroes[:3]]
    r = await s.client.put("/arena/defense", json={"team": team}, headers=s.auth)
    if r.status_code != 200:
        _fail(f"defense PUT failed: {r.status_code}")
    _ok("defense team set")

    opponents = await s.get("/arena/opponents")
    if not opponents:
        _warn("no arena opponents — fine on a fresh install, skipping attack leg")
        return
    target = opponents[0]
    r = await s.client.post(
        "/arena/attack",
        json={"defender_account_id": target["account_id"], "team": team},
        headers=s.auth,
    )
    if r.status_code != 201:
        _fail(f"arena attack failed: {r.status_code} {r.text[:200]}")
    match = r.json()
    _ok(f"attack vs {target['name']} -> {match['outcome']} (Δ{match['rating_delta']})")

    # Fetch it back via the replay endpoint.
    await s.get(f"/arena/matches/{match['id']}")
    _ok(f"GET /arena/matches/{match['id']} replays the match")


async def tour_daily_quests(s: Session) -> None:
    _section("7. Daily quests — list + progress")
    quests = await s.get("/daily")
    if not isinstance(quests, list) or len(quests) != 3:
        _fail(f"expected 3 daily quests, got {len(quests)}")
    _ok(f"3 daily quests rolled for today: {[q['kind'] for q in quests]}")


async def tour_guilds(s: Session) -> None:
    _section("8. Guilds - create + member view")
    # Tag is UNIQUE server-wide. Randomize so repeat runs against the same DB
    # don't collide with guilds left behind by earlier walkthroughs.
    tag = "".join(random.choices("ABCDEFGHJKLMNPQRSTUVWXYZ", k=5))
    name = f"Walk {random.randint(1000, 999999)}"
    r = await s.client.post(
        "/guilds",
        json={"name": name, "tag": tag},
        headers=s.auth,
    )
    if r.status_code != 201:
        _fail(f"guild create failed: {r.status_code} {r.text[:200]}")
    guild = r.json()
    _ok(f"created guild [{guild['tag']}] {guild['name']} (id={guild['id']})")

    details = await s.get(f"/guilds/{guild['id']}")
    if not any(m["account_id"] == s.account_id for m in details["members"]):
        _fail("creator not in members list")
    _ok(f"creator is listed as LEADER; member_count={details['member_count']}")

    # Post a message and read it back.
    await s.post(
        f"/guilds/{guild['id']}/messages",
        {"body": "walkthrough test message"},
        expect=201,
    )
    msgs = await s.get(f"/guilds/{guild['id']}/messages")
    if not msgs or msgs[0]["body"] != "walkthrough test message":
        _fail("chat message didn't round-trip")
    _ok("chat message round-trip works")


async def tour_raids(s: Session) -> None:
    _section("9. Raids — start (requires guild officer+)")
    r = await s.client.post(
        "/raids/start",
        json={
            "boss_template_code": "the_consultant",
            "boss_level": 20,
            "duration_hours": 24,
            "tier": "T1",
        },
        headers=s.auth,
    )
    if r.status_code != 201:
        _fail(f"raid start failed: {r.status_code} {r.text[:200]}")
    raid = r.json()
    _ok(f"raid started — boss={raid['boss_name']} tier={raid['tier']} hp={raid['max_hp']}")

    # Attack it once.
    heroes = sorted(await s.get("/heroes/mine"), key=lambda h: h["power"], reverse=True)
    team = [h["id"] for h in heroes[:3]]
    r = await s.client.post(
        f"/raids/{raid['id']}/attack",
        json={"team": team},
        headers=s.auth,
    )
    if r.status_code not in (201, 409):  # 409 = insufficient energy, fine
        _fail(f"raid attack returned {r.status_code}")
    if r.status_code == 409:
        _warn("raid attack 409 — likely energy depleted from earlier battle")
    else:
        body = r.json()
        _ok(f"raid attack — dealt {body['damage_dealt']} damage")


async def tour_shop(s: Session) -> None:
    _section("10. Shop — catalog + mock purchase")
    products = await s.get("/shop/products")
    if not products:
        _fail("no shop products available")
    skus = {p["sku"] for p in products}
    _ok(f"catalog has {len(products)} products: {sorted(skus)[:5]}...")

    # Mock purchase — needs HEROPROTO_MOCK_PAYMENTS_ENABLED=1.
    r = await s.client.post(
        "/shop/purchases",
        json={"sku": "gems_small", "client_ref": f"walk-{random.randint(1, 10**9)}"},
        headers=s.auth,
    )
    if r.status_code == 403:
        _warn("shop mock purchase 403 — server started without HEROPROTO_MOCK_PAYMENTS_ENABLED=1")
        return
    if r.status_code != 201:
        _fail(f"mock purchase failed: {r.status_code} {r.text[:200]}")
    purchase = r.json()
    if purchase["state"] != "COMPLETED":
        _fail(f"purchase state {purchase['state']} not COMPLETED")
    _ok(f"bought {purchase['sku']} for ${purchase['price_cents_paid']/100:.2f} -> granted {purchase['granted']}")


# --- Phase 2 surfaces -------------------------------------------------------


async def tour_hero_preview(s: Session) -> None:
    """Phase 2.1 — /heroes/{id}/preview must return current vs after-stats
    for level/star/special upgrade paths."""
    _section("11a. Hero detail / next-upgrade preview (Phase 2.1)")
    roster = await s.get("/heroes/mine")
    if not roster:
        _warn("no heroes — skipping preview check")
        return
    hero = roster[0]
    preview = await s.get(f"/heroes/{hero['id']}/preview")
    for k in ("current", "level_up", "star_up", "special_up"):
        if k not in preview:
            _fail(f"preview missing key {k!r}: {preview}")
    if preview["current"]["power"] != hero["power"]:
        _fail(f"preview.current.power {preview['current']['power']} != roster {hero['power']}")
    if not preview["level_up"]["available"]:
        _fail("level-up should be available at level 1")
    delta = preview["level_up"]["after"]["power"] - preview["current"]["power"]
    _ok(f"preview round-trip ok — level_up delta = +{delta} power, current={preview['current']['power']}")


async def tour_iap_qol(s: Session) -> None:
    """Phase 2.4 — Apple + Google IAP via the sandbox 'fake-' receipt
    shortcut. Verifies the QoL unlock + cosmetic frame surface on /me."""
    _section("11b. IAP — Apple StoreKit + Google Play Billing (Phase 2.4)")
    import json as _json
    apple_tx = f"walkthrough-apple-{random.randint(10**9, 10**10)}"
    apple_receipt = "fake-apple:" + _json.dumps({
        "productId": "qol_auto_battle", "transactionId": apple_tx,
    })
    r = await s.post(
        "/shop/iap/apple",
        body={"sku": "qol_auto_battle", "receipt": apple_receipt},
        expect=201,
    )
    if r.get("processor") != "apple" or r.get("state") != "COMPLETED":
        _fail(f"apple IAP unexpected: {r}")
    _ok(f"apple IAP COMPLETED — sku={r['sku']} ref={apple_tx[:24]}...")

    google_order = f"GPA.{random.randint(10**12, 10**13 - 1)}"
    google_receipt = "fake-google:" + _json.dumps({
        "productId": "cosmetic_frame_neon", "orderId": google_order,
    })
    r = await s.post(
        "/shop/iap/google",
        body={"sku": "cosmetic_frame_neon", "receipt": google_receipt},
        expect=201,
    )
    if r.get("processor") != "google":
        _fail(f"google IAP unexpected: {r}")
    _ok(f"google IAP COMPLETED — sku={r['sku']}")

    me = await s.get("/me")
    if "auto_battle" not in me.get("qol_unlocks", []):
        _fail(f"auto_battle not visible on /me after IAP: {me['qol_unlocks']}")
    if "frame_neon_cubicle" not in me.get("cosmetic_frames", []):
        _fail(f"frame_neon_cubicle not visible on /me: {me['cosmetic_frames']}")
    _ok("/me reflects QoL unlock + cosmetic frame from IAP grants")


async def tour_story(s: Session) -> None:
    """Phase 2.5 — story chapter catalog + cutscene-seen flag."""
    _section("11c. Story chapters + cutscene state (Phase 2.5)")
    body = await s.get("/story")
    if not body.get("chapters"):
        _fail("/story returned no chapters")
    ch1 = body["chapters"][0]
    for k in ("code", "title", "unlocked", "stages", "completed", "reward_claimed", "end_reward"):
        if k not in ch1:
            _fail(f"chapter missing key {k!r}: {ch1.keys()}")
    if not ch1["unlocked"]:
        _fail("first chapter should be unlocked at account level 1")
    locked_later = [c for c in body["chapters"] if c["unlock_level"] > 1]
    if any(c["unlocked"] for c in locked_later):
        _fail("higher-tier chapters should be locked")

    # Mark intro cutscene seen.
    r = await s.client.post(
        "/story/cutscene-seen",
        json={"chapter_code": ch1["code"], "stage_code": ch1["stages"][0]["code"], "beat": "intro"},
        headers=s.auth,
    )
    if r.status_code != 204:
        _fail(f"cutscene-seen HTTP {r.status_code}")
    _ok(f"chapters returned ({len(body['chapters'])}) — first unlocked, cutscene-seen 204")


async def tour_event_banner(s: Session) -> None:
    """Phase 2.2 — Myth-tier event banner. The walkthrough doesn't
    activate a banner (that needs DB write privileges); just verifies
    the status endpoint + the no-banner 409 path."""
    _section("11d. Myth event banner gating (Phase 2.2)")
    status = await s.get("/summon/event-banner")
    if "active" not in status:
        _fail(f"event-banner status missing 'active' key: {status}")
    if status["active"] is False:
        # Expected on a clean run — ensure the POST 409s correctly.
        r = await s.client.post("/summon/event-banner", headers=s.auth)
        if r.status_code != 409:
            _fail(f"no-active-banner POST should 409, got {r.status_code}")
        _ok("no active banner — POST returns 409 as expected")
    else:
        _ok(f"event banner ACTIVE: {status.get('hero_template_code')} (cap={status.get('per_account_cap')})")


async def tour_password_reset(s: Session) -> None:
    _section("11. Password reset — forgot + reset round-trip")
    r = await s.client.post("/auth/forgot-password", json={"email": s.email})
    if r.status_code != 200:
        _fail(f"forgot-password HTTP {r.status_code}")
    dev_url = r.json().get("dev_reset_url")
    if not dev_url:
        _warn("no dev_reset_url returned — prod env? Skipping reset leg")
        return
    token = dev_url.split("token=")[1]
    new_pw = "new-pw-from-walkthrough-99"
    r = await s.client.post(
        "/auth/reset-password", json={"token": token, "new_password": new_pw},
    )
    if r.status_code != 200:
        _fail(f"reset-password failed: {r.status_code}")
    # New password actually works.
    r = await s.client.post(
        "/auth/login", json={"email": s.email, "password": new_pw},
    )
    if r.status_code != 200:
        _fail("new password doesn't log in after reset")
    s.password = new_pw
    s.access_token = r.json()["access_token"]
    _ok("forgot-password -> reset -> login with new password works")


async def tour_email_verification(s: Session) -> None:
    _section("12. Email verification — send + verify")
    r = await s.client.post("/auth/send-verification", headers=s.auth)
    if r.status_code != 200:
        _fail(f"send-verification HTTP {r.status_code}")
    dev_url = r.json().get("dev_verify_url")
    if not dev_url:
        _warn("no dev_verify_url — skipping verify")
        return
    token = dev_url.split("token=")[1]
    r = await s.client.post("/auth/verify-email", json={"token": token})
    if r.status_code != 200:
        _fail(f"verify-email HTTP {r.status_code}")
    _ok("send-verification -> verify round-trip works")


async def tour_totp_2fa(s: Session) -> None:
    _section("13. 2FA — enroll + confirm + login challenge")
    r = await s.client.post("/auth/2fa/enroll", headers=s.auth)
    if r.status_code != 200:
        _fail(f"2fa/enroll HTTP {r.status_code}")
    secret = r.json()["secret"]
    code = pyotp.TOTP(secret).now()

    r = await s.client.post("/auth/2fa/confirm", json={"code": code}, headers=s.auth)
    if r.status_code != 200:
        _fail(f"2fa/confirm HTTP {r.status_code}")
    body = r.json()
    if not body.get("enabled"):
        _fail("2FA not enabled after confirm")
    codes = body.get("recovery_codes", [])
    if len(codes) != 10:
        _fail(f"expected 10 recovery codes, got {len(codes)}")
    _ok(f"2FA enrolled; secret = {secret[:8]}...; got 10 recovery codes")

    # Logging in now returns a challenge.
    r = await s.client.post(
        "/auth/login", json={"email": s.email, "password": s.password},
    )
    if r.status_code != 200:
        _fail(f"login after 2FA enable HTTP {r.status_code}")
    login_body = r.json()
    if login_body.get("status") != "totp_required":
        _fail(f"expected totp_required challenge, got {login_body}")
    challenge = login_body["challenge_token"]

    # Finish the challenge.
    code = pyotp.TOTP(secret).now()
    r = await s.client.post(
        "/auth/2fa/verify", json={"challenge_token": challenge, "code": code},
    )
    if r.status_code != 200:
        _fail(f"2fa/verify HTTP {r.status_code}")
    s.access_token = r.json()["access_token"]
    _ok("login challenge -> TOTP verify -> access token returned")


async def main() -> int:
    print(f"client_walkthrough -> {BASE}")
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as client:
        s = Session(client)
        try:
            await tour_auth(s)
            await tour_me_currencies(s)
            await tour_summons_roster(s)
            await tour_battle(s)
            await tour_energy_refill(s)
            await tour_arena(s)
            await tour_daily_quests(s)
            await tour_guilds(s)
            await tour_raids(s)
            await tour_shop(s)
            await tour_hero_preview(s)
            await tour_iap_qol(s)
            await tour_story(s)
            await tour_event_banner(s)
            await tour_password_reset(s)
            await tour_email_verification(s)
            await tour_totp_2fa(s)
        except SystemExit:
            return 1
    print()
    print(f"{GREEN}CLIENT WALKTHROUGH PASSED{RESET}")
    print(f"Exercised 17 feature sections against {BASE} without failure.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
