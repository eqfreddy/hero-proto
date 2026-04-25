"""Devblog + status + roadmap + email-template coverage."""

from __future__ import annotations


# --- Devblog -----------------------------------------------------------------


def test_devblog_index_lists_posts(client) -> None:
    r = client.get("/devblog")
    assert r.status_code == 200
    body = r.text
    # The two seeded posts must appear by title.
    assert "Why we made a gacha game about corporate IT" in body
    assert "Shipping Phase 1" in body


def test_devblog_post_detail_renders(client) -> None:
    r = client.get("/devblog/2026-04-25-why-corporate-it")
    assert r.status_code == 200
    body = r.text
    assert "<article" in body or "post-body" in body
    # Markdown body got rendered to HTML.
    assert "</p>" in body or "</h2>" in body


def test_devblog_unknown_slug_404(client) -> None:
    r = client.get("/devblog/nope-not-a-real-post")
    assert r.status_code == 404


# --- Status page -------------------------------------------------------------


def test_status_page_renders(client) -> None:
    r = client.get("/status")
    assert r.status_code == 200
    body = r.text
    # Headers for each system block.
    for label in ("Web server", "Database", "Background worker", "Rate limiter",
                  "Stripe", "Email sender", "Sentry"):
        assert label in body, f"status missing block {label!r}"
    # Auto-refresh script.
    assert "location.reload" in body


def test_status_overall_banner_present(client) -> None:
    r = client.get("/status")
    assert "All systems operational" in r.text or "Operational with warnings" in r.text or "Some systems are down" in r.text


# --- Roadmap -----------------------------------------------------------------


def test_roadmap_renders_phases(client) -> None:
    r = client.get("/roadmap")
    assert r.status_code == 200
    body = r.text
    for phase in ("Phase 0", "Phase 1", "Phase 2", "Phase 3", "Phase 4"):
        assert phase in body, f"roadmap missing {phase!r}"


def test_roadmap_lists_things_we_wont_do(client) -> None:
    r = client.get("/roadmap")
    body = r.text.lower()
    assert "won't do" in body or "won&#39;t do" in body
    assert "nft" in body  # explicit no-NFT call-out


# --- Email templates ---------------------------------------------------------


def test_render_password_reset_produces_text_and_html() -> None:
    from app.email_render import render_password_reset
    subject, text, html = render_password_reset(reset_url="https://example.com/r?t=abc", ttl_hours=2)
    assert "password reset" in subject.lower()
    assert "https://example.com/r?t=abc" in text
    assert "https://example.com/r?t=abc" in html
    # HTML should look like html (basic structural check).
    assert "<html" in html.lower() or "<table" in html.lower()
    # Plural pluralization works.
    assert "2 hour" in text


def test_render_verify_email_produces_text_and_html() -> None:
    from app.email_render import render_verify_email
    subject, text, html = render_verify_email(verify_url="https://example.com/v?t=xyz", ttl_hours=1)
    assert "verify" in subject.lower()
    assert "https://example.com/v?t=xyz" in text
    assert "https://example.com/v?t=xyz" in html
    # Singular pluralization works.
    assert "1 hour" in text


def test_email_sender_accepts_html_arg() -> None:
    """ConsoleSender (and others) must accept the new body_html kwarg."""
    from app.email_sender import ConsoleSender
    s = ConsoleSender()
    # No exception on either signature variant.
    s.send(to_email="x@y.com", subject="t", body_text="text body")
    s.send(to_email="x@y.com", subject="t", body_text="text body", body_html="<p>html</p>")


def test_smtp_sender_constructs_multipart_when_html_present() -> None:
    """SmtpSender should build the message in a way the smtplib mock can serialize."""
    import smtplib
    from unittest.mock import MagicMock, patch
    from app.email_sender import SmtpSender

    s = SmtpSender(host="smtp.example.com", port=587, username="u", password="p",
                   from_address="from@example.com", use_tls=True)
    with patch.object(smtplib, "SMTP") as mock_smtp:
        mock_conn = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_conn
        s.send(to_email="to@example.com", subject="hi", body_text="text", body_html="<p>html</p>")
        # Must have called send_message — exact alternative-part construction
        # is harder to assert without rebuilding MIME parsing; smoke the call
        # site instead.
        assert mock_conn.send_message.called
        # Verify TLS + login were hit.
        assert mock_conn.starttls.called
        assert mock_conn.login.called


# --- Marketing nav inclusion -------------------------------------------------


def test_marketing_nav_includes_new_pages(client) -> None:
    """Devblog / Roadmap / Status need to be discoverable from any marketing page."""
    r = client.get("/about")
    body = r.text
    for path in ("/devblog", "/roadmap", "/status"):
        assert path in body, f"nav missing link to {path}"


def test_sitemap_includes_new_pages(client) -> None:
    r = client.get("/sitemap.xml")
    body = r.text
    for path in ("/devblog", "/roadmap", "/status"):
        assert path in body, f"sitemap missing {path}"
