from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="HEROPROTO_")

    # Env / deployment
    environment: str = "dev"  # "dev" or "prod" — prod refuses weak secrets
    database_url: str = "sqlite:///./hero-proto.db"
    cors_origins: str = "*"  # comma-separated; "*" allows any (dev only)
    log_requests: bool = True
    json_logs: bool = False  # set HEROPROTO_JSON_LOGS=1 in prod for structured logs

    # Auth
    jwt_secret: str = "dev-only-change-me-at-least-32-bytes-long!"
    jwt_alg: str = "HS256"
    jwt_ttl_minutes: int = 60 * 24

    # Rate limits (per client IP, in-memory token bucket).
    # Tighten these for production — defaults here assume dev/alpha sharing an IP.
    auth_rate_per_minute: int = 60        # register + login combined
    general_rate_per_minute: int = 600    # everything else
    # Smoke scripts hammering a single IP can trip the general bucket — this lets
    # dev/CI short-circuit the middleware entirely. Never enable in prod.
    rate_limit_disabled: bool = False

    # Comma-separated list of emails auto-promoted to admin on registration/login.
    admin_emails: str = ""

    def admin_email_set(self) -> set[str]:
        raw = [x.strip().lower() for x in (self.admin_emails or "").split(",")]
        return {e for e in raw if e}

    # Economy
    energy_cap: int = 100
    energy_regen_seconds: int = 360
    energy_per_battle: int = 5
    starter_shards: int = 10
    starter_energy: int = 100
    starter_coins: int = 500
    onboarding_bonus_shards: int = 10  # granted on first /me after registration

    gacha_pity_threshold: int = 50

    xp_per_battle_win: int = 60
    xp_per_battle_loss: int = 15
    level_cap: int = 30

    def cors_origin_list(self) -> list[str]:
        raw = self.cors_origins.strip()
        if not raw or raw == "*":
            return ["*"]
        return [o.strip() for o in raw.split(",") if o.strip()]


settings = Settings()
