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
    # Refresh tokens — long-lived credential to mint fresh access tokens.
    refresh_token_ttl_days: int = 30

    # Rate limits (per client IP, in-memory token bucket).
    # Tighten these for production — defaults here assume dev/alpha sharing an IP.
    auth_rate_per_minute: int = 60        # register + login combined
    general_rate_per_minute: int = 600    # everything else
    # Smoke scripts hammering a single IP can trip the general bucket — this lets
    # dev/CI short-circuit the middleware entirely. Never enable in prod.
    rate_limit_disabled: bool = False
    # Backend for rate-limit state: "memory" (in-process, per-instance — breaks
    # under horizontal scaling) or "redis" (shared across instances).
    rate_limit_backend: str = "memory"
    # Used when rate_limit_backend=redis. Leave as default for dev; point at
    # a real Redis for prod. fakeredis drives the test suite.
    redis_url: str = "redis://localhost:6379/0"

    # Email sender — drives forgot-password / send-verification delivery.
    # Valid: console (default), file, smtp, disabled. In prod, console/disabled
    # are rejected at startup (see main._check_secrets).
    email_sender_type: str = "console"
    email_file_path: str = "./emails.log"
    email_from_address: str = "no-reply@hero-proto.local"
    email_smtp_host: str = ""
    email_smtp_port: int = 587
    email_smtp_username: str = ""
    email_smtp_password: str = ""
    email_smtp_use_tls: bool = True
    # Public-facing base URL used to construct clickable links in emails.
    # e.g. https://app.hero-proto.com — in dev, defaults to the local server.
    public_base_url: str = "http://127.0.0.1:8000"

    # Store: when True, POST /shop/purchases accepts unsigned "mock" payments that
    # immediately grant contents. Used in dev/CI before real Stripe is wired.
    # Auto-disabled in prod by main._check_secrets.
    mock_payments_enabled: bool = False

    # Stripe integration. All empty strings by default — checkout endpoint refuses
    # to operate until stripe_api_key is set. Webhook endpoint refuses without
    # stripe_webhook_secret. Set via HEROPROTO_STRIPE_* env vars.
    stripe_api_key: str = ""           # sk_test_... for test mode, sk_live_... for prod
    stripe_webhook_secret: str = ""    # whsec_... from `stripe listen` or dashboard
    stripe_publishable_key: str = ""   # pk_... — not used server-side, exposed to client
    # Where Stripe Checkout redirects after payment. Use {CHECKOUT_SESSION_ID} literal
    # in success_url if you want to verify session server-side on return.
    stripe_success_url: str = "http://127.0.0.1:8000/app/shop?checkout=success"
    stripe_cancel_url: str = "http://127.0.0.1:8000/app/shop?checkout=cancel"

    # Comma-separated list of emails auto-promoted to admin on registration/login.
    admin_emails: str = ""

    def admin_email_set(self) -> set[str]:
        raw = [x.strip().lower() for x in (self.admin_emails or "").split(",")]
        return {e for e in raw if e}

    # Worker: when False, the in-process background tick doesn't start.
    # Useful for running a dedicated worker instance separately from web
    # (run one instance with worker_enabled=True, the rest False).
    worker_enabled: bool = True

    # Economy
    energy_cap: int = 100
    energy_regen_seconds: int = 360
    energy_per_battle: int = 5
    # Gem-for-energy refill — first premium-currency sink in the game. Capped per
    # day so whales can't trivialize the energy loop.
    energy_refill_cost_gems: int = 50
    energy_refill_max_per_day: int = 3
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
