"""Soft-delete for direct messages.

Sender can DELETE /dm/{id}; the row stays in the DB (so reports/audit
still resolve) but the body is replaced with '[deleted]' in /dm/with/*
and /dm/threads responses, and a `deleted: true` flag is surfaced on
DirectMessageOut.
"""

from __future__ import annotations

import random


def _register(client, prefix: str = "dmsd") -> tuple[dict, int, str]:
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    return hdr, client.get("/me", headers=hdr).json()["id"], email


def _two_users(client):
    return _register(client), _register(client)


def test_sender_can_delete_their_own_message(client) -> None:
    (h1, id1, _), (_h2, id2, _) = _two_users(client)
    msg = client.post(f"/dm/with/{id2}", json={"body": "regret this"}, headers=h1).json()
    r = client.delete(f"/dm/{msg['id']}", headers=h1)
    assert r.status_code == 204


def test_deleted_message_body_is_redacted_in_thread(client) -> None:
    (h1, _id1, _), (h2, id2, _) = _two_users(client)
    msg = client.post(f"/dm/with/{id2}", json={"body": "secret thing"}, headers=h1).json()
    client.delete(f"/dm/{msg['id']}", headers=h1)

    # Recipient view: body shows the stub, deleted flag set.
    thread = client.get(f"/dm/with/{_id1 if False else msg['sender_id']}", headers=h2).json()
    found = next(m for m in thread if m["id"] == msg["id"])
    assert found["body"] == "[deleted]"
    assert found["deleted"] is True
    assert "secret thing" not in str(thread)  # full body never leaks

    # Sender's own view: same redaction applies.
    thread_sender = client.get(f"/dm/with/{id2}", headers=h1).json()
    own = next(m for m in thread_sender if m["id"] == msg["id"])
    assert own["body"] == "[deleted]"
    assert own["deleted"] is True


def test_deleted_message_redacted_in_threads_preview(client) -> None:
    """The /dm/threads list shows the latest message preview — deleted
    messages should show '[deleted]' there too."""
    (h1, id1, _), (h2, id2, _) = _two_users(client)
    msg = client.post(f"/dm/with/{id2}", json={"body": "preview text"}, headers=h1).json()
    client.delete(f"/dm/{msg['id']}", headers=h1)

    threads = client.get("/dm/threads", headers=h2).json()
    t = next(t for t in threads if t["other_account_id"] == id1)
    assert t["last_body"] == "[deleted]"


def test_recipient_cannot_delete_others_message(client) -> None:
    (h1, _id1, _), (h2, id2, _) = _two_users(client)
    msg = client.post(f"/dm/with/{id2}", json={"body": "something"}, headers=h1).json()
    # Recipient tries to delete sender's message — should 404 (not 403, to
    # avoid confirming the message exists if a stranger probes).
    r = client.delete(f"/dm/{msg['id']}", headers=h2)
    assert r.status_code == 404

    # Original body still intact for the recipient.
    thread = client.get(f"/dm/with/{msg['sender_id']}", headers=h2).json()
    found = next(m for m in thread if m["id"] == msg["id"])
    assert found["body"] == "something"
    assert found["deleted"] is False


def test_third_party_cannot_delete(client) -> None:
    """Random unrelated account gets the same 404 as the recipient."""
    (h1, _id1, _), (_h2, id2, _) = _two_users(client)
    h3, _id3, _ = _register(client, "dmsdthird")
    msg = client.post(f"/dm/with/{id2}", json={"body": "between us"}, headers=h1).json()
    r = client.delete(f"/dm/{msg['id']}", headers=h3)
    assert r.status_code == 404


def test_delete_is_idempotent(client) -> None:
    (h1, _id1, _), (_h2, id2, _) = _two_users(client)
    msg = client.post(f"/dm/with/{id2}", json={"body": "twice"}, headers=h1).json()
    r = client.delete(f"/dm/{msg['id']}", headers=h1)
    assert r.status_code == 204
    r = client.delete(f"/dm/{msg['id']}", headers=h1)
    assert r.status_code == 204  # second call is a no-op, not 409


def test_delete_unknown_message_returns_404(client) -> None:
    h1, _id1, _ = _register(client)
    r = client.delete("/dm/999999", headers=h1)
    assert r.status_code == 404


def test_deleted_message_still_reportable(client) -> None:
    """A deleted message stays in the DB so the recipient can still report
    it for moderation — the report row references the original content."""
    (h1, _id1, _), (h2, id2, _) = _two_users(client)
    msg = client.post(f"/dm/with/{id2}", json={"body": "regret"}, headers=h1).json()
    client.delete(f"/dm/{msg['id']}", headers=h1)
    r = client.post(f"/dm/{msg['id']}/report", json={"reason": "harassment"}, headers=h2)
    assert r.status_code == 201
