from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_prefix="HEROPROTO_")

    # Env / deployment
    environment: str = "dev"  # "dev" or "prod" — prod refuses weak secrets
    database_url: str = "sqlite:///./hero-proto.db"
    cors_origins: str = "*"  # comma-separated; "*" allows any (dev only)
    log_requests: bool = True
    json_logs: bool = False  # set HEROPROTO_JSON_LOGS=1 in prod for structured logs

    # Sentry error reporting. Empty DSN disables Sentry entirely (default).
    # In prod, set HEROPROTO_SENTRY_DSN=<your project DSN> to capture unhandled
    # exceptions + traces. Expected 4xx HTTPExceptions are filtered out.
    sentry_dsn: str = ""
    sentry_environment: str = ""  # defaults to `environment` (dev/prod) if empty
    sentry_traces_sample_rate: float = 0.0  # 0.0 = no perf tracing; tune up later

    # OpenTelemetry tracing. Empty endpoint disables OTel entirely (default).
    # In prod, set HEROPROTO_OTEL_ENDPOINT to your OTLP/gRPC collector URL
    # (e.g. http://localhost:4317). Install with: uv sync --extra otel
    otel_endpoint: str = ""

    # PostHog product analytics. Empty key disables analytics entirely (default).
    # In prod, set HEROPROTO_POSTHOG_API_KEY + HEROPROTO_POSTHOG_HOST to ship
    # the 12 instrumented events (see docs/RUNBOOK.md → Analytics for the list
    # and funnel setup). Account ID is the distinct_id; events are flushed in a
    # background thread by the posthog-python client.
    posthog_api_key: str = ""
    posthog_host: str = "https://app.posthog.com"
    # Hard kill switch — disables analytics even when api_key is set. Useful in
    # CI / load tests so synthetic traffic doesn't pollute the prod project.
    posthog_disabled: bool = False

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
    # Per-account anti-hammer on /battles (and /battles/sweep/*). In addition
    # to the per-IP general bucket. 30/min = ~1 fight every 2s, generous for
    # humans but catches bot-like loops signed in as a real account.
    battle_per_minute_per_account: int = 30
    # Per-account anti-hammer on /arena/attack. Arenas pay a matchmaking cost
    # server-side, so tighter: 20/min = one attack every 3s.
    arena_attack_per_minute_per_account: int = 20
    # Per-account anti-flood on /guilds/{id}/messages. 30/min matches a fast
    # human chatter; bots trying to spam a guild chat hit this first.
    guild_message_per_minute_per_account: int = 30
    # Additional per-IP cap on POST /guilds/{id}/messages. Stops botnets from
    # cycling through compromised accounts on one IP to bypass the per-account
    # gate. Higher than the per-account cap because legit shared-IP cases (NAT,
    # offices, dorms) exist.
    guild_message_per_minute_per_ip: int = 90
    # Per-account caps on friend system + DMs to slow abuse without
    # frustrating real users. Daily caps catch slow-burn spammers that
    # the per-minute bucket misses.
    friend_request_per_minute_per_account: int = 10
    friend_request_per_day_per_account: int = 50
    direct_message_per_minute_per_account: int = 30
    direct_message_per_day_per_account: int = 300
    # Max DM message length (chars). Anything past this is rejected
    # 422; normal users never hit it, spammers hit it on every paste.
    direct_message_max_length: int = 1500
    # GDPR data export is expensive (multi-table query, ~10MB JSON). Cap hard:
    # legitimate users want this once a year, never repeatedly.
    data_export_per_minute_per_account: int = 1
    # Trust X-Forwarded-For for client IP attribution. Only enable behind a
    # proxy that strips/replaces this header on ingress — otherwise clients
    # can spoof their source IP, defeating per-IP rate limits and planting
    # misleading entries in their own session list.
    trust_forwarded_for: bool = False

    # Shard store — in-game gems-to-shards exchange. Set the rate so a
    # mid-game gem balance buys a meaningful pull batch but real-money
    # shard purchases still feel cheaper. 50 gems → 10 shards = 5 gems
    # per shard. Daily cap stops players from converting away their entire
    # gem stack the moment they get a free-summon-credit reward.
    shard_exchange_gems_per_batch: int = 50
    shard_exchange_shards_per_batch: int = 10
    shard_exchange_max_per_day: int = 20  # 20 batches = 200 shards/day

    # Inventory slot caps. Soft-enforced: drops over the cap go to the
    # mailbox (Account.mailbox_overflow_json) rather than disappearing —
    # players reclaim them after expanding cap or selling/sweeping junk.
    hero_slot_cap_default: int = 50
    gear_slot_cap_default: int = 200
    # Per-slot expansion price (gems). Each purchase adds slot_expansion_step
    # slots. Tuned so 5 expansions ≈ a $5 gem pack — cosmetics/QoL pricing.
    slot_expansion_step: int = 10
    slot_expansion_cost_gems: int = 50
    slot_cap_max: int = 500  # absolute ceiling so accounts can't unbounded-grow
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

    # Apple StoreKit 2 (iOS in-app purchases) — only used when the Capacitor
    # mobile build POSTs receipts to /shop/iap/apple. All empty by default
    # so non-mobile deploys don't need to configure these.
    apple_bundle_id: str = ""
    apple_app_id: int = 0              # numeric app store id; required by SignedDataVerifier
    apple_sandbox: bool = True         # set False in production
    # Google Play Billing — service-account JSON content (not a path) to
    # avoid filesystem assumptions in container deploys. Empty = unconfigured.
    google_package_name: str = ""
    google_service_account_json: str = ""
    # Where Stripe Checkout redirects after payment. Use {CHECKOUT_SESSION_ID} literal
    # in success_url if you want to verify session server-side on return.
    stripe_success_url: str = "http://127.0.0.1:8000/app/shop?checkout=success"
    stripe_cancel_url: str = "http://127.0.0.1:8000/app/shop?checkout=cancel"

    # Comma-separated list of emails auto-promoted to admin on registration/login.
    admin_emails: str = ""

    def admin_email_set(self) -> set[str]:
        raw = [x.strip().lower() for x in (self.admin_emails or "").split(",")]
        return {e for e in raw if e}

    # Localization — default locale served when Accept-Language is absent or
    # unsupported. Ops can set HEROPROTO_DEFAULT_LOCALE=es for regional deploys.
    default_locale: str = "en"

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
