"""Pluggable email sender.

Three backends today:
  - console: log the message to stdout. Default in dev/test.
  - file: append the message to a per-process log file (HEROPROTO_EMAIL_FILE_PATH).
  - smtp: send via SMTP (HEROPROTO_EMAIL_SMTP_*). For real providers
    (SES, Postmark, Mailgun, Gmail), use their SMTP relay config.

Auth flows (forgot-password, send-verification) should call `get_sender().send(...)`.
In non-prod envs, response bodies also return dev URLs so clients don't need email
to test. In prod, email_sender_type must not be `disabled` or `console` — the app
refuses to start otherwise (see main._check_secrets).

The interface is deliberately narrow: `send(to_email, subject, body_text)`. No
templating, no attachments, no HTML fancy — the token URLs are short strings and
the message bodies are plain text.
"""

from __future__ import annotations

import logging
import smtplib
from dataclasses import dataclass
from email.message import EmailMessage
from pathlib import Path
from typing import Protocol

from app.config import settings

log = logging.getLogger("email")


class EmailSender(Protocol):
    def send(
        self, to_email: str, subject: str, body_text: str,
        body_html: str | None = None,
    ) -> None: ...


@dataclass
class ConsoleSender:
    """Log-only sender. Writes every outbound email to the console/logs."""

    def send(
        self, to_email: str, subject: str, body_text: str,
        body_html: str | None = None,
    ) -> None:
        log.info(
            "EMAIL [console] to=%s subject=%r html=%s\n---\n%s\n---",
            to_email, subject, "yes" if body_html else "no", body_text,
        )


@dataclass
class FileSender:
    """Append outbound emails to a flat file. Each message separated by a ruler.
    Useful in staging when you want a tangible artifact without a real mailbox."""

    path: Path

    def send(
        self, to_email: str, subject: str, body_text: str,
        body_html: str | None = None,
    ) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as f:
            f.write(f"To: {to_email}\nSubject: {subject}\n\n{body_text}\n")
            if body_html:
                f.write(f"\n--- HTML ---\n{body_html}\n")
            f.write("\n====\n")


@dataclass
class SmtpSender:
    """SMTP relay. Works with SES SMTP, Postmark, Mailgun, Gmail, etc.
    Plain SMTP+STARTTLS only (no SSL-on-connect variant); every modern provider
    supports this. Sends a multipart message when body_html is provided —
    text/plain stays the canonical content (good clients respect it for
    screen readers + spam scoring), html is the alternative the average
    inbox renders.
    """

    host: str
    port: int
    username: str
    password: str
    from_address: str
    use_tls: bool = True

    def send(
        self, to_email: str, subject: str, body_text: str,
        body_html: str | None = None,
    ) -> None:
        msg = EmailMessage()
        msg["From"] = self.from_address
        msg["To"] = to_email
        msg["Subject"] = subject
        msg.set_content(body_text)
        if body_html:
            msg.add_alternative(body_html, subtype="html")
        log.info("EMAIL [smtp] to=%s subject=%r host=%s:%s", to_email, subject, self.host, self.port)
        try:
            with smtplib.SMTP(self.host, self.port, timeout=30) as s:
                if self.use_tls:
                    s.starttls()
                if self.username:
                    s.login(self.username, self.password)
                s.send_message(msg)
            log.info("EMAIL [smtp] delivered to=%s", to_email)
        except Exception as exc:
            log.error("EMAIL [smtp] FAILED to=%s subject=%r error=%s", to_email, subject, exc)
            raise


@dataclass
class DisabledSender:
    """Drop every message on the floor. Only safe in dev/test; prod refuses to start."""

    def send(
        self, to_email: str, subject: str, body_text: str,
        body_html: str | None = None,
    ) -> None:
        log.warning("EMAIL DROPPED — sender is disabled. to=%s subject=%r", to_email, subject)


def _build_sender() -> EmailSender:
    kind = (settings.email_sender_type or "").strip().lower() or "console"
    if kind == "disabled":
        return DisabledSender()
    if kind == "console":
        return ConsoleSender()
    if kind == "file":
        path = Path(settings.email_file_path or "./emails.log")
        return FileSender(path=path)
    if kind == "smtp":
        return SmtpSender(
            host=settings.email_smtp_host or "localhost",
            port=int(settings.email_smtp_port or 587),
            username=settings.email_smtp_username or "",
            password=settings.email_smtp_password or "",
            from_address=settings.email_from_address or "no-reply@hero-proto.local",
            use_tls=bool(settings.email_smtp_use_tls),
        )
    raise ValueError(
        f"unknown HEROPROTO_EMAIL_SENDER_TYPE={kind!r} "
        f"(expected: console, file, smtp, disabled)"
    )


_cached: EmailSender | None = None


def get_sender() -> EmailSender:
    """Returns the configured sender, cached after first call. Tests can override
    via set_sender_for_tests()."""
    global _cached
    if _cached is None:
        _cached = _build_sender()
    return _cached


def set_sender_for_tests(sender: EmailSender | None) -> None:
    """Test helper — injects or clears the cached sender."""
    global _cached
    _cached = sender
