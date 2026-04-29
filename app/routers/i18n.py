"""i18n router — exposes the full string catalog for a given locale.

GET /i18n/strings?lang=en  →  {"locale": "en", "strings": {...}}
"""

from __future__ import annotations

from fastapi import APIRouter, Query

from app.i18n import DEFAULT_LOCALE, SUPPORTED_LOCALES, _CATALOG, get_locale

router = APIRouter(prefix="/i18n", tags=["i18n"])


@router.get("/strings")
def get_strings(lang: str = Query(default=DEFAULT_LOCALE)) -> dict:
    """Return the full string catalog for the requested locale.

    Falls back to ``"en"`` when the requested locale is unsupported.
    The ``locale`` field in the response always reflects the locale actually served.
    """
    # Normalise to lower-case and strip subtags so "ES" and "es-ES" both resolve.
    resolved = get_locale(lang.lower())
    # get_locale already handles subtag stripping and fallback to DEFAULT_LOCALE.
    # Grab the catalog for the resolved locale; fall back to "en" just in case.
    strings = _CATALOG.get(resolved) or _CATALOG[DEFAULT_LOCALE]
    return {"locale": resolved, "strings": strings}
