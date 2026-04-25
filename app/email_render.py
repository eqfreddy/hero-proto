"""Email body renderer.

Produces (subject, body_text, body_html) triples for each templated email.
Plain-text body is the canonical content (better for accessibility +
spam-scoring); HTML is the pretty alternative most clients render.

Usage:
    from app.email_render import render_password_reset
    subject, text, html = render_password_reset(reset_url=..., ttl_hours=1)
    get_sender().send(to_email, subject, text, html)
"""

from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.config import settings

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
    trim_blocks=False,
    lstrip_blocks=False,
)


def _render_html(template_name: str, ctx: dict) -> tuple[str, str]:
    """Render a templates/email/*.html and pull the subject from its
    {% block subject %}. Returns (subject, full_html)."""
    full_ctx = {
        "public_base_url": settings.public_base_url.rstrip("/"),
        **ctx,
    }
    tmpl = _env.get_template(template_name)
    html = tmpl.render(**full_ctx)
    # Subject is in <title> — pull it out for the email header.
    subject = ""
    m = re.search(r"<title>(.*?)</title>", html, re.S | re.I)
    if m:
        subject = m.group(1).strip()
    return subject, html


def _html_to_text(html: str) -> str:
    """Naive HTML → text fallback. Strips tags; replaces <br> + block ends
    with newlines; collapses whitespace. Good enough for our fully-controlled
    template HTML — not a general-purpose conversion.
    """
    # Replace <br>, <p>, </p>, </div>, </tr>, </h{n}>, </li> with newlines.
    text = re.sub(r"<\s*br\s*/?>", "\n", html, flags=re.I)
    text = re.sub(r"</\s*(p|div|tr|h\d|li)\s*>", "\n\n", text, flags=re.I)
    # Drop <head>...</head> and <style>...</style> entirely.
    text = re.sub(r"<\s*head\b.*?</\s*head\s*>", "", text, flags=re.S | re.I)
    text = re.sub(r"<\s*style\b.*?</\s*style\s*>", "", text, flags=re.S | re.I)
    # Drop all remaining tags.
    text = re.sub(r"<[^>]+>", "", text)
    # HTML entity unescape (basic).
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">").replace("&quot;", '"').replace("&#39;", "'")
    # Collapse whitespace.
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n[ \t]+", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


# --- Public renderers --------------------------------------------------------


def render_password_reset(*, reset_url: str, ttl_hours: int) -> tuple[str, str, str]:
    """Returns (subject, body_text, body_html) for the password-reset email."""
    ctx = {"reset_url": reset_url, "ttl_hours": int(ttl_hours)}
    subject, html = _render_html("email/password_reset.html", ctx)
    text = (
        f"Password reset\n\n"
        f"Someone asked to reset the password for the hero-proto account associated with this address.\n\n"
        f"Open this link within {ttl_hours} hour(s) to pick a new password:\n"
        f"  {reset_url}\n\n"
        f"Didn't request this? Ignore this email — your existing password keeps working."
    )
    return subject or "hero-proto — password reset", text, html


def render_verify_email(*, verify_url: str, ttl_hours: int) -> tuple[str, str, str]:
    """Returns (subject, body_text, body_html) for the email-verify email."""
    ctx = {"verify_url": verify_url, "ttl_hours": int(ttl_hours)}
    subject, html = _render_html("email/verify_email.html", ctx)
    text = (
        f"Confirm your email\n\n"
        f"Welcome to hero-proto. Confirm this email address belongs to you:\n\n"
        f"  {verify_url}\n\n"
        f"Link expires in {ttl_hours} hours.\n\n"
        f"Didn't sign up? You can ignore this — without verifying, no further mail goes to you."
    )
    return subject or "hero-proto — verify your email", text, html
