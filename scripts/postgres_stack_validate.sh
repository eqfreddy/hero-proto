#!/usr/bin/env bash
# End-to-end Postgres validation via docker compose.
#
# Brings up the `postgres` profile, waits for the app healthcheck, points the
# acceptance scripts at it, and tears down on exit. Run whenever Docker Desktop
# is up — this is the only thing that exercises the actual Postgres code path
# (CI runs unit tests against Postgres but never the full HTTP flow with the
# worker running).
#
# Usage:
#   bash scripts/postgres_stack_validate.sh
#
# Requires:
#   - Docker Desktop running
#   - Nothing else listening on :8000 (or override PORT below)

set -euo pipefail

PROJECT="heroproto_pgsmoke"
APP_PORT="${APP_PORT:-8000}"
BASE="http://127.0.0.1:${APP_PORT}"

echo "==> Bringing up postgres-backed stack (project=${PROJECT})..."
HEROPROTO_DATABASE_URL="postgresql+psycopg://hero:heropw@postgres:5432/heroproto" \
HEROPROTO_RATE_LIMIT_DISABLED=1 \
HEROPROTO_MOCK_PAYMENTS_ENABLED=1 \
  docker compose -p "${PROJECT}" --profile postgres up -d --build

cleanup() {
  echo "==> Tearing down..."
  docker compose -p "${PROJECT}" --profile postgres down -v || true
}
trap cleanup EXIT

echo "==> Waiting for /healthz at ${BASE}..."
for i in $(seq 1 60); do
  if curl -sf "${BASE}/healthz" >/dev/null 2>&1; then
    echo "    ready after ${i}s"
    break
  fi
  sleep 1
  if [[ "$i" == "60" ]]; then
    echo "!! healthcheck never came up"
    docker compose -p "${PROJECT}" logs --tail=50 hero-proto
    exit 1
  fi
done

echo ""
echo "==> Seeding content..."
docker compose -p "${PROJECT}" exec -T hero-proto \
  uv run python -c "from app.seed import seed; seed()"

echo ""
echo "==> Running startup_check against compose-Postgres..."
HEROPROTO_BASE="${BASE}" uv run python -m scripts.startup_check

echo ""
echo "==> Running client_walkthrough against compose-Postgres..."
HEROPROTO_BASE="${BASE}" uv run python -m scripts.client_walkthrough

echo ""
echo "POSTGRES STACK VALIDATION OK"
