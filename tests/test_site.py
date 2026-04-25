"""Marketing-site coverage — every public page renders, has the shared
nav, and surfaces what the store-submission compliance flow needs.
"""

from __future__ import annotations


PUBLIC_PAGES = ["/", "/about", "/faq", "/support", "/privacy", "/terms", "/press", "/changelog"]


def test_every_public_page_returns_200(client) -> None:
    for path in PUBLIC_PAGES:
        r = client.get(path, follow_redirects=False)
        assert r.status_code == 200, f"{path} returned {r.status_code}"


def test_every_public_page_has_shared_nav(client) -> None:
    """Every page should use the marketing_base.html shell — nav links to
    each major section must appear."""
    for path in PUBLIC_PAGES:
        r = client.get(path)
        for nav_target in ("/about", "/faq", "/support", "/privacy", "/terms"):
            assert nav_target in r.text, f"{path} missing nav link to {nav_target}"


def test_about_describes_the_game(client) -> None:
    r = client.get("/about")
    assert r.status_code == 200
    body = r.text.lower()
    # Key phrases that should be present in any future revision.
    for phrase in ("hero-proto", "no pay-to-win", "gacha", "fastapi"):
        assert phrase in body, f"about page missing '{phrase}'"


def test_privacy_marks_itself_as_template(client) -> None:
    """Until a real lawyer signs off, the draft banner has to be visible."""
    r = client.get("/privacy")
    assert r.status_code == 200
    assert "draft-banner" in r.text or "needs lawyer review" in r.text.lower()


def test_terms_marks_itself_as_template(client) -> None:
    r = client.get("/terms")
    assert r.status_code == 200
    assert "draft-banner" in r.text or "needs lawyer review" in r.text.lower()


def test_support_includes_contact_info(client) -> None:
    """Apple + Google require a discoverable support contact for store
    submission. This page is the canonical one — assert the shape stays."""
    r = client.get("/support")
    assert r.status_code == 200
    body = r.text.lower()
    assert "github" in body
    assert "support@" in body or "contact" in body


def test_changelog_renders(client) -> None:
    """Changelog page parses git log + renders. Empty repo should not crash;
    populated repo should show at least one month group."""
    r = client.get("/changelog")
    assert r.status_code == 200
    # Either we have commits (and see a category badge) or the empty-state copy.
    assert "Changelog" in r.text


def test_robots_txt_disallows_admin(client) -> None:
    r = client.get("/robots.txt")
    assert r.status_code == 200
    body = r.text
    assert "Disallow: /admin" in body
    assert "Disallow: /metrics" in body
    assert "Sitemap:" in body


def test_sitemap_xml_lists_public_pages(client) -> None:
    r = client.get("/sitemap.xml")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/xml")
    body = r.text
    for path in ("/about", "/faq", "/support", "/privacy", "/terms", "/changelog"):
        assert path in body, f"sitemap missing {path}"


def test_press_kit_lists_downloadable_assets(client) -> None:
    """Press kit page should include direct download links to the icon set."""
    r = client.get("/press")
    assert r.status_code == 200
    body = r.text
    assert "/app/static/icons/hero-proto-1024.png" in body
    assert "/app/static/heroes/cards/the_founder.png" in body


def test_landing_includes_play_cta(client) -> None:
    """Single-source-of-truth: the landing page CTA points at /app/."""
    r = client.get("/")
    assert r.status_code == 200
    assert 'href="/app/"' in r.text or "location.href = '/app/'" in r.text


def test_landing_does_not_load_dashboard_sound(client) -> None:
    """sound.js is for /app/, not the marketing surface — confirmed by
    test_sound.test_landing_page_does_not_load_sound but worth the duplicate
    here since marketing layout changed."""
    r = client.get("/")
    assert "/app/static/sound.js" not in r.text
