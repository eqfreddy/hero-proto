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
from app.routers import admin, arena, auth, battles, daily, gear, guilds, heroes, liveops, me, raids, shop, stages, summon, ui
from app.worker import worker_loop

configure_logging(json_logs=settings.json_logs)
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
    if settings.environment != "test":
        worker_task = asyncio.create_task(worker_loop(), name="worker_loop")
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

# Backwards-compat: /app/battle.html and /app/index.html used to be served by the
# /app static mount with html=True. Serve them explicitly now.
from fastapi.responses import FileResponse as _FR

_battle_html = _STATIC_DIR / "battle.html"
if _battle_html.is_file():
    @app.get("/app/battle.html", include_in_schema=False)
    def _serve_battle_html() -> _FR:
        return _FR(str(_battle_html))

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
app.include_router(shop.router)


@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "env": settings.environment}


@app.get("/metrics")
def metrics():
    return metrics_response()


@app.get("/", include_in_schema=False)
def root():
    # Minimal HTML client is served from /app/ — send browsers there.
    return RedirectResponse(url="/app/")
