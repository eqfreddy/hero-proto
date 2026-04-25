"""Email sender adapter: console/file/disabled variants + auth-flow integration."""

from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.email_sender import (
    ConsoleSender,
    DisabledSender,
    FileSender,
    _build_sender,
    get_sender,
    set_sender_for_tests,
)


@dataclass
class _SpySender:
    calls: list[tuple[str, str, str]]

    def send(
        self, to_email: str, subject: str, body_text: str,
        body_html: str | None = None,
    ) -> None:
        self.calls.append((to_email, subject, body_text))


@pytest.fixture(autouse=True)
def _restore_sender():
    yield
    set_sender_for_tests(None)  # clear cache so each test picks up fresh config


def test_console_sender_does_not_crash(caplog) -> None:
    s = ConsoleSender()
    s.send("user@example.com", "test subject", "test body")
    # Logs but produces no output; just verifying no exception.


def test_file_sender_appends_each_message(tmp_path: Path) -> None:
    target = tmp_path / "emails.log"
    s = FileSender(path=target)
    s.send("a@ex.com", "first", "hello a")
    s.send("b@ex.com", "second", "hello b")
    text = target.read_text(encoding="utf-8")
    assert "first" in text and "hello a" in text
    assert "second" in text and "hello b" in text
    # Separator between messages.
    assert text.count("====") == 2


def test_disabled_sender_drops_silently(caplog) -> None:
    s = DisabledSender()
    s.send("who@ex.com", "dropped", "never sent")
    # Only warns; doesn't raise.


def test_build_sender_defaults_to_console(monkeypatch) -> None:
    from app.config import settings
    monkeypatch.setattr(settings, "email_sender_type", "console")
    s = _build_sender()
    assert isinstance(s, ConsoleSender)


def test_build_sender_file_uses_configured_path(monkeypatch, tmp_path: Path) -> None:
    from app.config import settings
    p = tmp_path / "out.log"
    monkeypatch.setattr(settings, "email_sender_type", "file")
    monkeypatch.setattr(settings, "email_file_path", str(p))
    s = _build_sender()
    assert isinstance(s, FileSender)
    assert s.path == p


def test_build_sender_rejects_unknown_type(monkeypatch) -> None:
    from app.config import settings
    monkeypatch.setattr(settings, "email_sender_type", "pigeon-post")
    with pytest.raises(ValueError, match="unknown"):
        _build_sender()


# --- Integration: auth flows call through the sender -------------------------


def test_forgot_password_calls_sender_with_reset_url(client) -> None:
    spy = _SpySender(calls=[])
    set_sender_for_tests(spy)

    email = f"sndr+{random.randint(100000, 999999)}@example.com"
    client.post("/auth/register", json={"email": email, "password": "hunter22"})
    client.post("/auth/forgot-password", json={"email": email})

    assert len(spy.calls) == 1
    to_email, subject, body = spy.calls[0]
    assert to_email == email
    assert "password reset" in subject.lower()
    # Email links to the user-facing /reset-password page (not the JSON
    # POST endpoint at /auth/reset-password).
    assert "/reset-password?token=" in body


def test_forgot_password_doesnt_call_sender_for_unknown_email(client) -> None:
    spy = _SpySender(calls=[])
    set_sender_for_tests(spy)
    client.post("/auth/forgot-password", json={"email": "ghost@example.com"})
    # No email to send when account doesn't exist — but response is still 200.
    assert spy.calls == []


def test_send_verification_calls_sender(client) -> None:
    spy = _SpySender(calls=[])
    set_sender_for_tests(spy)
    email = f"sndrv+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    client.post("/auth/send-verification", headers=hdr)

    assert len(spy.calls) == 1
    to_email, subject, body = spy.calls[0]
    assert to_email == email
    assert "verify" in subject.lower()
    assert "/auth/verify-email?token=" in body


def test_sender_failure_does_not_break_auth_endpoint(client) -> None:
    """If the email sender blows up, the endpoint must still 200 — theft/probe
    resistance is more important than delivery signal."""

    class BrokenSender:
        def send(self, to_email, subject, body_text):
            raise RuntimeError("smtp connection refused")

    set_sender_for_tests(BrokenSender())
    email = f"brk+{random.randint(100000, 999999)}@example.com"
    client.post("/auth/register", json={"email": email, "password": "hunter22"})

    r = client.post("/auth/forgot-password", json={"email": email})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_dev_url_still_returned_when_sender_is_active(client) -> None:
    """In the test env (not prod), dev URLs stay in response bodies even if the
    sender also delivers. This simplifies the dev loop for clients."""
    set_sender_for_tests(ConsoleSender())
    email = f"devu+{random.randint(100000, 999999)}@example.com"
    client.post("/auth/register", json={"email": email, "password": "hunter22"})
    r = client.post("/auth/forgot-password", json={"email": email})
    assert r.json()["dev_reset_url"] is not None
