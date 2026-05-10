"""Task 0 (Battle 3D Viewer): InteractiveStateOut exposes stage_code and last_event.

These fields let the 3D viewer pick a diorama (stage_code) and trigger one-shot
animations (last_event). last_event must persist across polls with no new events
so the animation driver isn't starved.
"""

from __future__ import annotations

import random


def _register(client) -> dict[str, str]:
    email = f"b3d+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _start_interactive(client, hdr) -> tuple[dict, dict]:
    """Return (start_response_body, tutorial_stage_dict)."""
    stages = client.get("/stages", headers=hdr).json()
    tutorial = next(s for s in stages if s["code"] == "tutorial_first_ticket")
    heroes = client.get("/heroes/mine", headers=hdr).json()
    team = [h["id"] for h in sorted(heroes, key=lambda h: h["power"], reverse=True)[:3]]
    r = client.post(
        "/battles/interactive/start",
        json={"stage_id": tutorial["id"], "team": team},
        headers=hdr,
    )
    assert r.status_code == 201, r.text
    return r.json(), tutorial


def test_interactive_state_includes_stage_code(client) -> None:
    """InteractiveStateOut must echo the stage_code so the 3D viewer can pick a diorama."""
    hdr = _register(client)
    body, tutorial = _start_interactive(client, hdr)
    assert body["stage_code"] == tutorial["code"]


def test_last_event_populated_after_act(client) -> None:
    """After /act, last_event should equal the most recent combat log entry."""
    hdr = _register(client)
    start, _ = _start_interactive(client, hdr)
    session_id = start["session_id"]
    pending = start["pending"]
    assert pending is not None

    # Pick any pending enemy uid as target.
    target_uid = pending["enemies"][0]["uid"]
    r = client.post(
        f"/battles/interactive/{session_id}/act",
        json={
            "target_uid": target_uid,
            "turn_number": pending["turn_number"],
        },
        headers=hdr,
    )
    assert r.status_code == 200, r.text
    act = r.json()
    assert act["last_event"] is not None
    assert act["log_delta"][-1] == act["last_event"]


def test_last_event_persists_when_log_delta_empty(client) -> None:
    """A no-op _state_out call (no new events) must preserve the prior last_event."""
    hdr = _register(client)
    start, _ = _start_interactive(client, hdr)
    session_id = start["session_id"]
    pending = start["pending"]
    target_uid = pending["enemies"][0]["uid"]
    client.post(
        f"/battles/interactive/{session_id}/act",
        json={"target_uid": target_uid, "turn_number": pending["turn_number"]},
        headers=hdr,
    )

    from app.interactive import _sessions
    sess = _sessions[session_id]
    prior = sess.last_event
    assert prior is not None

    # Simulate a no-op delta — cursor at end of log.
    sess.log_cursor = len(sess.combined_log)

    from app.routers.battles import _state_out
    out = _state_out(sess)
    assert out.last_event == prior
