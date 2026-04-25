"""Per-IP guild chat rate limit — botnet-on-one-IP defense.

In the test env both the per-account and per-IP buckets are short-circuited
(env=test). What we *can* verify here is that the dependency wiring itself
is intact and didn't regress the happy path of posting a message. The
real-rate behavior is exercised by the bucket unit tests in
test_rate_limit_backends.py.
"""

from __future__ import annotations

import random


def test_post_guild_message_still_works_after_dep_change(client) -> None:
    """The added per-IP layer wraps the existing dep — make sure POST still 201s."""
    email = f"gchat+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    name = f"chatguild-{random.randint(100000, 999999)}"
    tag = f"C{random.randint(100, 999)}"  # avoid collision with other tests using "CHT"
    r = client.post("/guilds", json={"name": name, "tag": tag}, headers=hdr)
    assert r.status_code == 201, r.text
    gid = r.json()["id"]
    for body in ("hello", "second message", "third"):
        r = client.post(f"/guilds/{gid}/messages", json={"body": body}, headers=hdr)
        assert r.status_code == 201, r.text
