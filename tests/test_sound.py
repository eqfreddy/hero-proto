"""Sound system smoke — file is served, dashboard loads it."""

from __future__ import annotations


def test_sound_js_is_served(client) -> None:
    """app/static/sound.js must be reachable for the dashboard to use it."""
    r = client.get("/app/static/sound.js")
    assert r.status_code == 200
    body = r.text
    # Sanity: SoundManager singleton + key API surface present.
    assert "window.sound" in body
    assert "play(name)" in body or "play(name " in body
    assert "setMute" in body
    assert "AudioContext" in body
    # Sound bank includes the canonical names callers reference.
    for name in (
        "click", "tab", "victory", "defeat",
        "pull_common", "pull_legendary", "pull_myth",
        "purchase", "mailbox", "coin_grant",
    ):
        assert f"'{name}'" in body or f'"{name}"' in body, f"sound bank missing {name!r}"


def test_dashboard_loads_sound_js(client) -> None:
    """The /app/ shell must include the sound script tag."""
    r = client.get("/app/")
    assert r.status_code == 200
    assert "/app/static/sound.js" in r.text
    # Settings popover scaffolding present.
    assert "sound-gear" in r.text
    assert "sound-popover" in r.text


def test_landing_page_does_not_load_sound(client) -> None:
    """Marketing landing page (welcome.html) intentionally has no sound —
    cold visitors shouldn't get audio context spun up before they consent."""
    r = client.get("/", follow_redirects=False)
    assert r.status_code == 200
    assert "/app/static/sound.js" not in r.text
