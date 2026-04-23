# syntax=docker/dockerfile:1.7
FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# uv is copied in from the official image — no bootstrap install needed.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app

# Install deps (including the optional postgres driver) for cache-friendliness.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --extra postgres

# Copy application code.
COPY app/ ./app/
COPY alembic/ ./alembic/
COPY alembic.ini ./
COPY scripts/ ./scripts/
COPY README.md ./

EXPOSE 8000

# Non-root user for runtime.
RUN useradd --system --home-dir /app --shell /usr/sbin/nologin heroproto \
    && mkdir -p /data \
    && chown -R heroproto:heroproto /app /data
USER heroproto

# Default DB path points at the volume mount.
ENV HEROPROTO_DATABASE_URL=sqlite:////data/hero-proto.db

# Run migrations on startup via the app lifespan, then serve.
CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
