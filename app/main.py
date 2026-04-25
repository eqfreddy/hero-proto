import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from alembic import command
from alembic.config import Config as AlembicConfig
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from sqlalchemy import text as _text

from app.config import settings
from app.middleware import RateLimitMiddleware, RequestLogMiddleware
from app.observability import (
    MetricsMiddleware,
    RequestIDMiddleware,
    configure_logging,
    metrics_response,
)
from app.routers import achievements, admin, announcements, arena, auth, battles, crafting, daily, events, friends, gear, guilds, heroes, inventory, liveops, me, notifications, raids, shop, stages, story, summon, ui
from app.worker import health as worker_health, supervised_worker_loop

configure_logging(json_logs=settings.json_logs)

# Sentry must init before FastAPI creates the app so middleware hooks attach properly.
from app.sentry_init import init_sentry
init_sentry()
log = logging.getLogger("lifespan")


WEAK_DEFAULT_SECRET = "dev-only-change-me-at-least-32-bytes-long!"


def _check_secrets() -> None:
    if settings.environment.lower().startswith("prod"):
        if settings.jwt_secret == WEAK_DEFAULT_SECRET:
            raise RuntimeError(
                "HEROPROTO_JWT_SECRET is still the default — refuse to start in production"
            )
        if len(settings.jwt_secret.encode("utf-8")) < 32:
            raise RuntimeError("HEROPROTO_JWT_SECRET must be at least 32 bytes in production")
        if settings.mock_payments_enabled:
            raise RuntimeError(
                "HEROPROTO_MOCK_PAYMENTS_ENABLED must be false in production — real "
                "payment processor required"
            )
        if (settings.email_sender_type or "").lower() in ("", "console", "disabled"):
            raise RuntimeError(
                f"HEROPROTO_EMAIL_SENDER_TYPE={settings.email_sender_type!r} is not "
                f"allowed in production — set to 'smtp' with real credentials"
            )


def _run_migrations() -> None:
    ini_path = Path(__file__).resolve().parents[1] / "alembic.ini"
    cfg = AlembicConfig(str(ini_path))
    cfg.set_main_option("sqlalchemy.url", settings.database_url)
    command.upgrade(cfg, "head")
    log.info("alembic upgrade head complete")


@asynccontextmanager
async def lifespan(_: FastAPI):
    _check_secrets()
    _run_migrations()
    log.info("startup complete (env=%s)", settings.environment)

    worker_task: asyncio.Task | None = None
    if settings.environment != "test" and settings.worker_enabled:
        worker_task = asyncio.create_task(supervised_worker_loop(), name="worker_loop")
    try:
        yield
    finally:
        if worker_task is not None:
            worker_task.cancel()
            try:
                await worker_task
            except asyncio.CancelledError:
                pass


app = FastAPI(title="hero-proto backend", lifespan=lifespan)

# Middleware order (add_middleware is LIFO — last added runs first):
# request-id (outermost, so every log line/response has the ID) → log → rate-limit → metrics → CORS.
if settings.log_requests and settings.environment != "test":
    app.add_middleware(RequestLogMiddleware)
if settings.environment != "test" and not settings.rate_limit_disabled:
    app.add_middleware(
        RateLimitMiddleware,
        auth_rate_per_minute=settings.auth_rate_per_minute,
        general_rate_per_minute=settings.general_rate_per_minute,
        backend=settings.rate_limit_backend,
        redis_url=settings.redis_url,
    )
app.add_middleware(MetricsMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)

_STATIC_DIR = Path(__file__).resolve().parent / "static"
if _STATIC_DIR.is_dir():
    # UI router serves /app and /app/partials/*. Mount static one level deeper so
    # assets (battle.html, heroes/*.svg) stay reachable via /app/<filename>.
    app.mount("/app/static", StaticFiles(directory=str(_STATIC_DIR), html=False), name="static")

# UI router (HTMX shell + partials) must register BEFORE any /app fallback.
app.include_router(ui.router)

# Explicit routes for the dashboard's static pages — the /app static mount was
# moved to /app/static/ so root-level filenames here need direct routes.
from fastapi.responses import FileResponse as _FR


def _serve_static(filename: str):
    path = _STATIC_DIR / filename
    if not path.is_file():
        return None
    async def handler() -> _FR:
        return _FR(str(path))
    handler.__name__ = f"_serve_{filename.replace('-', '_').replace('.', '_')}"
    return handler


for _html in ("battle-phaser.html", "battle-setup.html", "battle-replay.html", "roster.html"):
    _h = _serve_static(_html)
    if _h is not None:
        app.add_api_route(f"/app/{_html}", _h, methods=["GET"], include_in_schema=False)


# PWA service worker served at /app/sw.js so its default scope is /app/
# (SW scope is capped at the path the file is served from). Manifest served
# from /app/manifest.webmanifest for the same reason — simpler root path for
# browsers that don't love deep manifest URLs.
async def _serve_sw() -> _FR:
    path = _STATIC_DIR / "sw.js"
    return _FR(str(path), media_type="application/javascript")


async def _serve_manifest() -> _FR:
    path = _STATIC_DIR / "manifest.webmanifest"
    return _FR(str(path), media_type="application/manifest+json")


app.add_api_route("/app/sw.js", _serve_sw, methods=["GET"], include_in_schema=False)
app.add_api_route("/app/manifest.webmanifest", _serve_manifest, methods=["GET"], include_in_schema=False)

app.include_router(auth.router)
app.include_router(me.router)
app.include_router(heroes.router)
app.include_router(summon.router)
app.include_router(stages.router)
app.include_router(battles.router)
app.include_router(gear.router)
app.include_router(arena.router)
app.include_router(daily.router)
app.include_router(guilds.router)
app.include_router(liveops.router)
app.include_router(raids.router)
app.include_router(admin.router)
app.include_router(announcements.public)
app.include_router(announcements.admin)
app.include_router(shop.router)
app.include_router(events.router)
app.include_router(crafting.router)
app.include_router(inventory.router)
app.include_router(achievements.router)
app.include_router(notifications.router)
app.include_router(story.router)
app.include_router(friends.router)

# Stripe checkout + webhook. Endpoints 503 until HEROPROTO_STRIPE_* vars are set.
from app import stripe_ext as _stripe_ext
app.include_router(_stripe_ext.router)


@app.get("/healthz")
def healthz() -> dict:
    payload: dict = {"status": "ok", "env": settings.environment}
    # Expose a light worker status so load balancers / ops dashboards can see
    # the tick is live. Absence of a tick for several minutes is the signal
    # that something's wrong — each instance's /healthz reports for itself.
    if settings.worker_enabled and settings.environment != "test":
        payload["worker"] = _worker_health_dict()
    return payload


def _worker_health_dict() -> dict:
    last_tick = worker_health.last_tick_at
    return {
        "enabled": settings.worker_enabled,
        "last_tick_at": last_tick.isoformat() if last_tick else None,
        "last_tick_success": worker_health.last_tick_success,
        "last_error": worker_health.last_error,
        "ticks_total": worker_health.ticks_total,
        "ticks_failed": worker_health.ticks_failed,
        "restarts": worker_health.restarts,
    }


@app.get("/worker/status")
def worker_status() -> dict:
    """Full worker telemetry — ops endpoint. Does NOT 503 when unhealthy (that
    would create a cascade between /healthz failing and orchestrators killing
    the container while the web side is fine). Probes should inspect fields."""
    return _worker_health_dict()


@app.get("/metrics")
def metrics():
    return metrics_response()


from fastapi import Request as _Request
from fastapi.templating import Jinja2Templates as _Jinja2Templates
_WELCOME_TEMPLATES = _Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


@app.get("/", include_in_schema=False)
def root(request: _Request):
    """Marketing landing page. Logged-in users are client-side-bounced to
    /app/ via a small JS check in the template; unauthenticated visitors see
    the hero-showcase + pitch + register panel.
    """
    return _WELCOME_TEMPLATES.TemplateResponse(request, "welcome.html", {})


# --- Marketing-site pages (about / FAQ / support / privacy / terms / press / changelog) ---


def _site_page(name: str):
    async def handler(request: _Request):
        return _WELCOME_TEMPLATES.TemplateResponse(request, f"site/{name}.html", {})
    handler.__name__ = f"_site_{name}"
    return handler


for _page in ("about", "faq", "support", "privacy", "terms", "press", "roadmap"):
    app.add_api_route(f"/{_page}", _site_page(_page), methods=["GET"], include_in_schema=False)


@app.get("/reset-password", include_in_schema=False)
def reset_password_page(request: _Request):
    """User-facing reset page. The link in the password-reset email points
    here. JS reads ?token=... and POSTs to /auth/reset-password with the
    new password to actually flip the credential.
    """
    return _WELCOME_TEMPLATES.TemplateResponse(request, "site/reset_password.html", {})


_STARTED_AT = _datetime_module_for_uptime = None


@app.on_event("startup")
def _record_start_time():
    global _STARTED_AT
    from datetime import datetime as _dt
    _STARTED_AT = _dt.utcnow()


def _format_uptime(started_at) -> str:
    from datetime import datetime as _dt
    if started_at is None:
        return "unknown"
    delta = _dt.utcnow() - started_at
    s = int(delta.total_seconds())
    days, s = divmod(s, 86400)
    hours, s = divmod(s, 3600)
    minutes, _ = divmod(s, 60)
    if days > 0:
        return f"{days}d {hours}h {minutes}m"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


@app.get("/status", include_in_schema=False)
def status_page(request: _Request):
    """Public status board. Reads live state from the same systems that
    /healthz + /worker/status expose, dressed up for humans."""
    from datetime import datetime as _dt, timedelta as _td
    from sqlalchemy import func, select
    from app.db import SessionLocal
    from app.models import Account, ArenaMatch, Battle, GachaRecord, RaidAttempt
    from app.worker import health as worker_health

    now = _dt.utcnow()
    one_hour_ago = now - _td(hours=1)

    # Database — try a trivial query.
    db_status = "ok"
    db_pill = "ok"
    db_head = "—"
    activity = {
        "battles": "—", "summons": "—",
        "arena_attacks": "—", "raid_attacks": "—",
        "new_accounts": "—",
    }
    try:
        with SessionLocal() as db:
            db.execute(select(func.count(Account.id)))
            # Migration head from alembic_version.
            row = db.execute(_text("SELECT version_num FROM alembic_version LIMIT 1")).first()
            if row is not None:
                db_head = str(row[0])[:12]
            # Counts in last hour.
            activity["battles"] = db.scalar(
                select(func.count(Battle.id)).where(Battle.created_at >= one_hour_ago)
            ) or 0
            activity["summons"] = db.scalar(
                select(func.count(GachaRecord.id)).where(GachaRecord.pulled_at >= one_hour_ago)
            ) or 0
            activity["arena_attacks"] = db.scalar(
                select(func.count(ArenaMatch.id)).where(ArenaMatch.created_at >= one_hour_ago)
            ) or 0
            activity["raid_attacks"] = db.scalar(
                select(func.count(RaidAttempt.id)).where(RaidAttempt.created_at >= one_hour_ago)
            ) or 0
            activity["new_accounts"] = db.scalar(
                select(func.count(Account.id)).where(Account.created_at >= one_hour_ago)
            ) or 0
    except Exception:
        db_status = "✗ unreachable"
        db_pill = "bad"

    # Worker.
    worker_status_str = "✓ ticking"
    worker_pill = "ok"
    worker_detail = "—"
    if not settings.worker_enabled:
        worker_status_str = "disabled"
        worker_pill = "muted"
        worker_detail = "HEROPROTO_WORKER_ENABLED=0 — web-only deploy"
    elif worker_health.last_tick_at is None:
        worker_status_str = "⏳ starting"
        worker_pill = "warn"
        worker_detail = "no tick yet — first tick within ~60s of startup"
    else:
        delta = (now - worker_health.last_tick_at.replace(tzinfo=None)).total_seconds()
        worker_detail = f"last tick {int(delta)}s ago · ticks={worker_health.ticks_total} · failed={worker_health.ticks_failed}"
        if delta > 300:
            worker_status_str = "✗ stale"
            worker_pill = "bad"
        elif delta > 90:
            worker_status_str = "⚠ slow"
            worker_pill = "warn"

    # Rate limiter.
    rate_backend = settings.rate_limit_backend
    rate_status = "✓ active"
    rate_pill = "ok"
    if settings.rate_limit_disabled:
        rate_status = "disabled"
        rate_pill = "muted"

    # Stripe.
    if settings.stripe_api_key:
        stripe_status = "✓ configured"
        stripe_pill = "ok"
        key_kind = "live" if settings.stripe_api_key.startswith("sk_live_") else "test"
        stripe_detail = f"keys present · {key_kind} mode"
    else:
        stripe_status = "not configured"
        stripe_pill = "muted"
        stripe_detail = "HEROPROTO_STRIPE_API_KEY unset — purchases via mock-payments only"

    # Email.
    email_kind = (settings.email_sender_type or "").lower() or "console"
    email_detail = f"adapter: {email_kind}"
    if email_kind == "smtp":
        email_status = "✓ smtp"
        email_pill = "ok"
    elif email_kind in ("console", "file"):
        email_status = "dev-mode"
        email_pill = "warn"
    else:
        email_status = "disabled"
        email_pill = "muted"

    # Sentry.
    if settings.sentry_dsn:
        sentry_status = "✓ enabled"
        sentry_pill = "ok"
        sentry_detail = "DSN configured · errors will report"
    else:
        sentry_status = "not configured"
        sentry_pill = "muted"
        sentry_detail = "HEROPROTO_SENTRY_DSN unset — errors stay in local logs"

    # Overall banner — worst pill rules.
    pills = [db_pill, worker_pill]
    if "bad" in pills:
        overall = {"cls": "bad", "icon": "✗", "label": "Some systems are down"}
    elif "warn" in pills:
        overall = {"cls": "warn", "icon": "⚠", "label": "Operational with warnings"}
    else:
        overall = {"cls": "ok", "icon": "✓", "label": "All systems operational"}

    return _WELCOME_TEMPLATES.TemplateResponse(
        request, "site/status.html",
        {
            "overall": overall,
            "uptime": _format_uptime(_STARTED_AT),
            "db_status": db_status, "db_pill": db_pill, "db_head": db_head,
            "worker_status": worker_status_str, "worker_pill": worker_pill, "worker_detail": worker_detail,
            "rate_backend": rate_backend, "rate_status": rate_status, "rate_pill": rate_pill,
            "stripe_status": stripe_status, "stripe_pill": stripe_pill, "stripe_detail": stripe_detail,
            "email_status": email_status, "email_pill": email_pill, "email_detail": email_detail,
            "sentry_status": sentry_status, "sentry_pill": sentry_pill, "sentry_detail": sentry_detail,
            "activity": activity,
            "checked_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


@app.get("/devblog", include_in_schema=False)
def devblog_index(request: _Request):
    from app.devblog import all_posts
    return _WELCOME_TEMPLATES.TemplateResponse(
        request, "site/devblog_index.html", {"posts": all_posts()},
    )


@app.get("/devblog.xml", include_in_schema=False)
def devblog_rss():
    """RSS 2.0 feed of the devblog."""
    from datetime import datetime, timezone
    from email.utils import format_datetime
    from fastapi.responses import Response
    from html import escape as _esc
    from app.devblog import all_posts

    base = settings.public_base_url.rstrip("/")
    items_xml = []
    for p in all_posts():
        link = f"{base}/devblog/{p.slug}"
        pub_dt = datetime.combine(p.date, datetime.min.time()).replace(hour=12, tzinfo=timezone.utc)
        items_xml.append(
            "<item>"
            f"<title>{_esc(p.title)}</title>"
            f"<link>{link}</link>"
            f'<guid isPermaLink="true">{link}</guid>'
            f"<pubDate>{format_datetime(pub_dt)}</pubDate>"
            f"<description>{_esc(p.summary or p.title)}</description>"
            f"<author>noreply@hero-proto.local ({_esc(p.author)})</author>"
            f"<content:encoded><![CDATA[{p.body_html}]]></content:encoded>"
            "</item>"
        )

    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<rss version="2.0" xmlns:content="http://purl.org/rss/1.0/modules/content/" '
        'xmlns:atom="http://www.w3.org/2005/Atom">'
        "<channel>"
        "<title>hero-proto devblog</title>"
        f"<link>{base}/devblog</link>"
        f'<atom:link href="{base}/devblog.xml" rel="self" type="application/rss+xml" />'
        "<description>Build-in-public posts from the hero-proto team.</description>"
        "<language>en-us</language>"
        + "".join(items_xml) +
        "</channel></rss>"
    )
    return Response(content=body, media_type="application/rss+xml; charset=utf-8")


@app.get("/devblog/{slug}", include_in_schema=False)
def devblog_post(slug: str, request: _Request):
    from app.devblog import post_by_slug
    post = post_by_slug(slug)
    if post is None:
        from fastapi.responses import HTMLResponse
        return HTMLResponse("<h1>Post not found</h1><p><a href='/devblog'>back</a></p>", status_code=404)
    return _WELCOME_TEMPLATES.TemplateResponse(
        request, "site/devblog_post.html", {"post": post},
    )


@app.get("/changelog", include_in_schema=False)
def changelog_page(request: _Request):
    """Render git history as patch notes. Cached at module-load — restart to refresh."""
    from app.changelog import get_commits, grouped_by_month, short_summary
    commits = get_commits(limit=80)
    # Inject short_summary into each commit dict for the template.
    for c in commits:
        # CommitEntry is frozen — we can't add attrs. Use a dict view.
        pass
    months = grouped_by_month(commits)
    months_view = [
        (label, [
            {
                "sha": c.sha, "short_sha": c.short_sha, "date": c.date,
                "title": c.title, "category": c.category,
                "short_summary": short_summary(c.body),
            } for c in cs
        ])
        for label, cs in months
    ]
    return _WELCOME_TEMPLATES.TemplateResponse(request, "site/changelog.html", {"months": months_view})


# --- robots.txt + sitemap.xml -----------------------------------------------


_PUBLIC_PAGES = ("/", "/about", "/devblog", "/changelog", "/roadmap", "/faq", "/press", "/support", "/status", "/privacy", "/terms")


@app.get("/robots.txt", include_in_schema=False)
def robots_txt():
    from fastapi.responses import PlainTextResponse
    body = (
        "User-agent: *\n"
        "Allow: /\n"
        "Disallow: /admin\n"
        "Disallow: /metrics\n"
        "Disallow: /worker/\n"
        "Disallow: /shop/webhooks/\n"
        "Sitemap: /sitemap.xml\n"
    )
    return PlainTextResponse(body, media_type="text/plain")


@app.get("/sitemap.xml", include_in_schema=False)
def sitemap_xml():
    from fastapi.responses import Response
    urls = "".join(
        f'<url><loc>{settings.public_base_url.rstrip("/")}{path}</loc></url>'
        for path in _PUBLIC_PAGES
    )
    body = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">'
        f'{urls}'
        '</urlset>'
    )
    return Response(content=body, media_type="application/xml")
