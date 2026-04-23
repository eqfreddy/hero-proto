"""Web shell smoke: verifies `/` redirects to `/app/` and the HTML has expected markers.

Run a dev server first: `uv run uvicorn app.main:app`
"""

from __future__ import annotations

import asyncio
import sys

import httpx

BASE = "http://127.0.0.1:8000"


async def main() -> int:
    async with httpx.AsyncClient(base_url=BASE, timeout=10.0, follow_redirects=False) as client:
        root = await client.get("/")
        assert root.status_code in (302, 307), f"/ did not redirect: {root.status_code}"
        loc = root.headers.get("location", "")
        assert loc.startswith("/app"), f"/ redirected to unexpected location {loc!r}"
        print(f"/ -> {root.status_code} {loc}")

        shell = await client.get("/app/")
        assert shell.status_code == 200, f"/app/ status {shell.status_code}"
        body = shell.text
        for marker in ("hero-proto", "heroproto_jwt", "data-tab=\"login\"", "/auth/register"):
            assert marker in body, f"missing marker in HTML: {marker!r}"
        print(f"/app/ -> 200 ({len(body)} bytes) with all expected markers")

        # Metrics endpoint is part of observability but easy to sanity-check here too.
        metrics = await client.get("/metrics")
        assert metrics.status_code == 200, f"/metrics status {metrics.status_code}"
        assert "requests_total" in metrics.text
        print("/metrics -> 200 with requests_total exposed")

    print("smoke_web OK")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
