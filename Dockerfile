# syntax=docker/dockerfile:1.7

# ── Stage 1: build the React SPA ─────────────────────────────────────────────
FROM node:22-alpine AS spa-builder

WORKDIR /frontend
COPY frontend/package.json frontend/package-lock.json* ./
RUN npm ci --prefer-offline

COPY frontend/ ./
# outputs to ../app/static/spa relative to the frontend dir, but inside the
# container that's /app/static/spa — we redirect with VITE_OUTDIR instead of
# relying on the relative path crossing the workdir boundary.
RUN npm run build -- --outDir /spa-dist

# ── Stage 2: Python backend ───────────────────────────────────────────────────
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra postgres

COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY scripts/ ./scripts/
COPY README.md ./

# Drop the SPA dist from stage 1 into the static path the router expects.
COPY --from=spa-builder /spa-dist ./app/static/spa/

EXPOSE 8000

RUN useradd --system --home-dir /app --shell /usr/sbin/nologin heroproto \
    && mkdir -p /data \
    && chown -R heroproto:heroproto /app /data
USER heroproto

ENV HEROPROTO_DATABASE_URL=sqlite:////data/hero-proto.db

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
