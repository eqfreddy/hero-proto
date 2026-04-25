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

from app.config import settings
from app.middleware import RateLimitMiddleware, RequestLogMiddleware
from app.observability import (
    MetricsMiddleware,
    RequestIDMiddleware,
    configure_logging,
    metrics_response,
)
from app.routers import admin, announcements, arena, auth, battles, daily, events, gear, guilds, heroes, liveops, me, raids, shop, stages, summon, ui
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
