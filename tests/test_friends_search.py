"""GET /friends/search — typo-tolerant lookup before sending a request.

Returns up to N candidates whose email local-part starts with the
query, annotated with the caller's relationship state so the UI can
render "already friends" / "request pending" / "blocked" inline."""

from __future__ import annotations

import random


def _register(client, prefix: str) -> tuple[dict, int, str]:
    suffix = random.randint(100000, 999999)
    email = f"{prefix}+{suffix}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201, r.text
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    aid = client.get("/me", headers=hdr).json()["id"]
    return hdr, aid, email


def test_search_returns_matching_prefixes(client) -> None:
    seeker, _, _ = _register(client, "seekfriendsx")
    _, _, target_email = _register(client, "matchprefix")
    target_local = target_email.split("@", 1)[0]
    # Search for the first 5 chars of the target's prefix.
    q = target_local[:5]
    r = client.get(f"/friends/search?q={q}", headers=seeker)
    assert r.status_code == 200, r.text
    hits = r.json()
    found = [h for h in hits if h["name"] == target_local]
    assert found, hits
    assert found[0]["is_friend"] is False
    assert found[0]["has_pending_request"] is False


def test_search_under_2_chars_returns_empty(client) -> None:
    hdr, _, _ = _register(client, "seekempty")
    r = client.get("/friends/search?q=a", headers=hdr)
    assert r.status_code == 200
    assert r.json() == []


def test_search_excludes_self(client) -> None:
    hdr, _, email = _register(client, "selfsearch")
    prefix = email.split("@", 1)[0][:7]
    r = client.get(f"/friends/search?q={prefix}", headers=hdr)
    assert r.status_code == 200
    for h in r.json():
        assert h["name"] != email.split("@", 1)[0], h


def test_search_marks_pending_request(client) -> None:
    seeker_hdr, _, _ = _register(client, "seekerpend")
    _, _, target_email = _register(client, "targetpend")
    target_prefix = target_email.split("@", 1)[0]
    # Send a request first.
    r = client.post(
        "/friends/request",
        json={"email_prefix": target_prefix},
        headers=seeker_hdr,
    )
    assert r.status_code == 201, r.text
    # Now search — that hit should report has_pending_request=True.
    r = client.get(
        f"/friends/search?q={target_prefix[:5]}",
        headers=seeker_hdr,
    )
    assert r.status_code == 200
    matched = [h for h in r.json() if h["name"] == target_prefix]
    assert matched, r.json()
    assert matched[0]["has_pending_request"] is True


def test_search_marks_already_friends(client) -> None:
    seeker_hdr, _, _ = _register(client, "frseeker")
    target_hdr, target_id, target_email = _register(client, "frtarget")
    target_prefix = target_email.split("@", 1)[0]
    # Mutual request → auto-accept.
    client.post("/friends/request", json={"email_prefix": target_prefix}, headers=seeker_hdr)
    # Target accepts.
    client.post(f"/friends/{client.get('/me', headers=seeker_hdr).json()['id']}/accept", headers=target_hdr)
    # Search should now mark them as friends.
    r = client.get(
        f"/friends/search?q={target_prefix[:5]}",
        headers=seeker_hdr,
    )
    assert r.status_code == 200
    matched = [h for h in r.json() if h["name"] == target_prefix]
    assert matched, r.json()
    assert matched[0]["is_friend"] is True


def test_search_limit_capped_at_10(client) -> None:
    """limit query param is clamped to [1, 10] regardless of input."""
    hdr, _, _ = _register(client, "limittest")
    # Even asking for 1000 should not return more than 10.
    r = client.get("/friends/search?q=user&limit=1000", headers=hdr)
    assert r.status_code == 200
    assert len(r.json()) <= 10
