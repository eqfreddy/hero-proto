"""End-to-end store smoke: register -> list products -> buy -> balance updates.

Also exercises idempotency (same client_ref returns the same purchase) and the
HTMX shop partial renders with seeded products.
"""

from __future__ import annotations

import asyncio
import random
import sys

import httpx

BASE = "http://127.0.0.1:8000"


async def _register(client: httpx.AsyncClient, prefix: str) -> tuple[dict, int]:
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = await client.post("/auth/register", json={"email": email, "password": "hunter22"})
    r.raise_for_status()
    token = r.json()["access_token"]
    hdr = {"Authorization": f"Bearer {token}"}
    me = (await client.get("/me", headers=hdr)).json()
    return hdr, me["id"]


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=30.0) as client:
        hdr, account_id = await _register(client, "shop")
        before = (await client.get("/me", headers=hdr)).json()
        print(f"OK registered #{account_id} — starting gems={before['gems']} shards={before['shards']} access_cards={before['access_cards']}")

        r = await client.get("/shop/products", headers=hdr)
        r.raise_for_status()
        products = r.json()
        skus = {p["sku"] for p in products}
        assert {"starter_pack", "gems_small", "shards_pack", "access_cards_pack"} <= skus, \
            f"missing seeded products: got {skus}"
        print(f"OK /shop/products lists {len(products)} available products")

        # Purchase starter pack — should grant all 3 premium currencies.
        r = await client.post("/shop/purchases", json={"sku": "starter_pack"}, headers=hdr)
        assert r.status_code == 201, r.text
        purchase = r.json()
        assert purchase["state"] == "COMPLETED"
        assert purchase["granted"]["gems"] == 500
        assert purchase["granted"]["access_cards"] == 5
        print(f"OK bought starter_pack ${purchase['price_cents_paid']/100:.2f} — granted {purchase['granted']}")

        mid = (await client.get("/me", headers=hdr)).json()
        assert mid["gems"] == before["gems"] + 500
        assert mid["access_cards"] == before["access_cards"] + 5
        print(f"OK balances updated: gems={mid['gems']} access_cards={mid['access_cards']}")

        # Starter should now be missing from default product list.
        r = await client.get("/shop/products", headers=hdr)
        assert "starter_pack" not in {p["sku"] for p in r.json()}
        print("OK starter_pack filtered out after one-time purchase")

        # Idempotency: same client_ref gives same row, no double-grant.
        ref = "dedupe-" + str(random.randint(1, 10**9))
        r1 = await client.post("/shop/purchases", json={"sku": "gems_small", "client_ref": ref}, headers=hdr)
        r2 = await client.post("/shop/purchases", json={"sku": "gems_small", "client_ref": ref}, headers=hdr)
        assert r1.status_code == 201 and r2.status_code == 201
        assert r1.json()["id"] == r2.json()["id"], "idempotency broke: different purchase ids"
        after = (await client.get("/me", headers=hdr)).json()
        # Only +300 gems from one grant, not +600.
        assert after["gems"] == mid["gems"] + 300
        print(f"OK idempotent: duplicate client_ref '{ref}' returned same purchase id={r1.json()['id']}")

        # Purchase history.
        r = await client.get("/shop/purchases/mine", headers=hdr)
        r.raise_for_status()
        history = r.json()
        assert len(history) >= 2
        assert history[0]["sku"] == "gems_small"
        assert history[-1]["sku"] == "starter_pack" or any(h["sku"] == "starter_pack" for h in history)
        print(f"OK purchase history — {len(history)} rows, newest={history[0]['sku']}")

        # HTMX shop partial renders with expected markup.
        r = await client.get("/app/partials/shop", headers=hdr)
        assert r.status_code == 200
        body = r.text
        assert "Shop" in body
        assert "Gem Packs" in body
        assert "💎" in body or "gems" in body
        print("OK /app/partials/shop renders HTML with product groups")

        print("SMOKE SHOP OK")
        return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
