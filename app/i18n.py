"""Localization support: message catalog, locale resolution, and a context var.

No external dependencies — plain Python dicts.
"""

from __future__ import annotations

from contextvars import ContextVar

# ---------------------------------------------------------------------------
# Supported locales
# ---------------------------------------------------------------------------

SUPPORTED_LOCALES = {"en", "es"}
DEFAULT_LOCALE = "en"

# ---------------------------------------------------------------------------
# Catalog: locale -> key -> translated string
# ---------------------------------------------------------------------------

_CATALOG: dict[str, dict[str, str]] = {
    "en": {
        # Error messages
        "error.not_enough_energy": "Not enough energy. Refill in the Shop.",
        "error.not_enough_shards": "Not enough shards to summon.",
        "error.not_enough_gems": "Not enough gems.",
        "error.hero_not_found": "Hero not found.",
        "error.stage_not_found": "Stage not found.",
        "error.guild_not_found": "Guild not found.",
        "error.already_in_guild": "You are already in a guild.",
        "error.not_in_guild": "You are not in a guild.",
        "error.permission_denied": "You don't have permission to do that.",
        "error.invalid_team": "Invalid team — check hero ownership.",
        # Success messages
        "success.battle_won": "Victory!",
        "success.battle_lost": "Defeated. Better luck next time.",
        "success.summon_complete": "Summon complete!",
        "success.daily_claimed": "Daily bonus claimed!",
        # UI labels
        "label.power": "Power",
        "label.level": "Level",
        "label.stars": "Stars",
        "label.faction": "Faction",
        "label.role": "Role",
        # Rarity names
        "rarity.common": "Common",
        "rarity.uncommon": "Uncommon",
        "rarity.rare": "Rare",
        "rarity.epic": "Epic",
        "rarity.legendary": "Legendary",
        "rarity.myth": "Myth",
    },
    "es": {
        # Spanish stubs — mark untranslated ones so they're easy to find
        "error.not_enough_energy": "Energía insuficiente. Recarga en la Tienda.",
        "error.not_enough_shards": "No tienes suficientes fragmentos para invocar.",
        "error.not_enough_gems": "Gemas insuficientes.",
        "error.hero_not_found": "Héroe no encontrado.",
        "error.stage_not_found": "Etapa no encontrada.",
        "error.guild_not_found": "Gremio no encontrado.",
        "error.already_in_guild": "Ya perteneces a un gremio.",
        "error.not_in_guild": "No perteneces a ningún gremio.",
        "error.permission_denied": "No tienes permiso para hacer eso.",
        "error.invalid_team": "Equipo inválido — verifica la propiedad de los héroes.",
        "success.battle_won": "¡Victoria!",
        "success.battle_lost": "Derrotado. Mejor suerte la próxima vez.",
        "success.summon_complete": "¡Invocación completa!",
        "success.daily_claimed": "¡Bono diario reclamado!",
        "label.power": "Poder",
        "label.level": "Nivel",
        "label.stars": "Estrellas",
        "label.faction": "Facción",
        "label.role": "Rol",
        "rarity.common": "Común",
        "rarity.uncommon": "Poco común",
        "rarity.rare": "Raro",
        "rarity.epic": "Épico",
        "rarity.legendary": "Legendario",
        "rarity.myth": "Mito",
    },
}


def get_locale(accept_language: str | None, default: str = DEFAULT_LOCALE) -> str:
    """Pick the best supported locale from an Accept-Language header value.

    Args:
        accept_language: The raw ``Accept-Language`` header, e.g. ``"en-US,en;q=0.9"``.
        default: Fallback locale when nothing matches (defaults to DEFAULT_LOCALE,
                 but callers can pass ``settings.default_locale`` for regional overrides).

    Returns:
        A locale code from SUPPORTED_LOCALES, or ``default``.
    """
    if not accept_language:
        return default
    for part in accept_language.split(","):
        tag = part.split(";")[0].strip().lower()
        if tag in SUPPORTED_LOCALES:
            return tag
        lang = tag.split("-")[0]
        if lang in SUPPORTED_LOCALES:
            return lang
    return default


def t(key: str, locale: str = DEFAULT_LOCALE) -> str:
    """Translate a key. Falls back to English, then to the key itself."""
    return (
        _CATALOG.get(locale, {}).get(key)
        or _CATALOG["en"].get(key)
        or key
    )


# ---------------------------------------------------------------------------
# Locale context var — set by LocaleMiddleware per request
# ---------------------------------------------------------------------------

locale_var: ContextVar[str] = ContextVar("locale", default=DEFAULT_LOCALE)
