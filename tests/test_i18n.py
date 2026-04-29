"""Tests for the i18n localization foundation.

Covers:
  - get_locale() header parsing and fallback
  - t() key lookup, language fallback, and missing-key passthrough
  - GET /i18n/strings endpoint
  - LocaleMiddleware context-var wiring
"""

from __future__ import annotations

import pytest

from app.i18n import DEFAULT_LOCALE, SUPPORTED_LOCALES, _CATALOG, get_locale, t


# ---------------------------------------------------------------------------
# get_locale() unit tests
# ---------------------------------------------------------------------------


def test_get_locale_en_us_returns_en() -> None:
    """en-US,en;q=0.9 — subtag stripped → 'en'."""
    assert get_locale("en-US,en;q=0.9") == "en"


def test_get_locale_es_es_returns_es() -> None:
    """es-ES,es;q=0.9,en;q=0.8 — first match is 'es' via subtag strip."""
    assert get_locale("es-ES,es;q=0.9,en;q=0.8") == "es"


def test_get_locale_unsupported_falls_back_to_en() -> None:
    """fr-FR is not in SUPPORTED_LOCALES, so DEFAULT_LOCALE is returned."""
    assert get_locale("fr-FR") == DEFAULT_LOCALE


def test_get_locale_none_returns_default() -> None:
    """Missing Accept-Language header returns DEFAULT_LOCALE."""
    assert get_locale(None) == DEFAULT_LOCALE


def test_get_locale_empty_string_returns_default() -> None:
    """Empty Accept-Language header returns DEFAULT_LOCALE."""
    assert get_locale("") == DEFAULT_LOCALE


def test_get_locale_custom_default() -> None:
    """Caller can pass a custom default (used by LocaleMiddleware for regional deploys)."""
    assert get_locale("fr-FR", default="es") == "es"


def test_get_locale_exact_es() -> None:
    """Exact 'es' tag (no subtag, no q-value) matches directly."""
    assert get_locale("es") == "es"


# ---------------------------------------------------------------------------
# t() unit tests
# ---------------------------------------------------------------------------


def test_t_es_energy_error() -> None:
    """Spanish translation for error.not_enough_energy returns the expected string."""
    assert t("error.not_enough_energy", "es") == "Energía insuficiente. Recarga en la Tienda."


def test_t_en_fallback_for_missing_locale() -> None:
    """Unknown locale falls back to English string."""
    result = t("success.battle_won", "zz")
    assert result == _CATALOG["en"]["success.battle_won"]


def test_t_missing_key_returns_key() -> None:
    """A key that doesn't exist in any locale is returned as-is."""
    assert t("nonexistent.key", "en") == "nonexistent.key"
    assert t("nonexistent.key", "es") == "nonexistent.key"


def test_t_all_en_keys_present() -> None:
    """Every English catalog key can be retrieved without falling back to the key."""
    for key in _CATALOG["en"]:
        assert t(key, "en") == _CATALOG["en"][key]


def test_t_all_es_keys_present() -> None:
    """Every Spanish catalog key can be retrieved without falling back."""
    for key in _CATALOG["es"]:
        assert t(key, "es") == _CATALOG["es"][key]


# ---------------------------------------------------------------------------
# GET /i18n/strings endpoint tests
# ---------------------------------------------------------------------------


def test_i18n_strings_en_200(client) -> None:
    """GET /i18n/strings?lang=en returns 200 with locale='en' and all catalog keys."""
    r = client.get("/i18n/strings?lang=en")
    assert r.status_code == 200
    body = r.json()
    assert body["locale"] == "en"
    assert set(body["strings"].keys()) == set(_CATALOG["en"].keys())
    assert body["strings"]["error.not_enough_energy"] == _CATALOG["en"]["error.not_enough_energy"]


def test_i18n_strings_es_200(client) -> None:
    """GET /i18n/strings?lang=es returns 200 with locale='es' and all Spanish strings."""
    r = client.get("/i18n/strings?lang=es")
    assert r.status_code == 200
    body = r.json()
    assert body["locale"] == "es"
    assert set(body["strings"].keys()) == set(_CATALOG["es"].keys())
    assert body["strings"]["error.not_enough_energy"] == "Energía insuficiente. Recarga en la Tienda."


def test_i18n_strings_unsupported_lang_falls_back_to_en(client) -> None:
    """GET /i18n/strings?lang=fr returns 200 with locale='en' (fallback)."""
    r = client.get("/i18n/strings?lang=fr")
    assert r.status_code == 200
    body = r.json()
    assert body["locale"] == "en"
    assert body["strings"] == _CATALOG["en"]


def test_i18n_strings_default_lang_is_en(client) -> None:
    """GET /i18n/strings with no lang param defaults to en."""
    r = client.get("/i18n/strings")
    assert r.status_code == 200
    assert r.json()["locale"] == "en"


def test_i18n_strings_lang_case_insensitive(client) -> None:
    """?lang=ES (uppercase) is treated as 'es'."""
    r = client.get("/i18n/strings?lang=ES")
    assert r.status_code == 200
    assert r.json()["locale"] == "es"


def test_i18n_strings_subtag_stripped(client) -> None:
    """?lang=es-ES resolves to 'es' via subtag stripping."""
    r = client.get("/i18n/strings?lang=es-ES")
    assert r.status_code == 200
    assert r.json()["locale"] == "es"


# ---------------------------------------------------------------------------
# LocaleMiddleware — verify it doesn't crash under various Accept-Language values
# ---------------------------------------------------------------------------


def test_middleware_does_not_crash_with_es_header(client) -> None:
    """Requests with Accept-Language: es reach the app without error.

    The locale_var is a server-side context var; we cannot read it from the
    client side. What we can verify is that the middleware processes the header
    and lets the request through cleanly.
    """
    r = client.get("/i18n/strings?lang=es", headers={"Accept-Language": "es"})
    assert r.status_code == 200
    assert r.json()["locale"] == "es"


def test_middleware_does_not_crash_without_header(client) -> None:
    """Requests without Accept-Language reach the app without error."""
    r = client.get("/i18n/strings?lang=en")
    assert r.status_code == 200
    assert r.json()["locale"] == "en"


def test_middleware_does_not_crash_with_unsupported_header(client) -> None:
    """Unsupported Accept-Language (fr) doesn't crash the middleware."""
    r = client.get("/i18n/strings", headers={"Accept-Language": "fr-FR,fr;q=0.9"})
    assert r.status_code == 200
    # ?lang defaults to "en", so the response locale is "en"
    assert r.json()["locale"] == "en"
