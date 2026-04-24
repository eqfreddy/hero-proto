#!/usr/bin/env bash
# Dated DB backup. Detects the backend from HEROPROTO_DATABASE_URL:
#   sqlite://      -> gzipped file copy
#   postgresql://  -> pg_dump custom-format
#
# Writes to $BACKUP_DIR (default ./backups/) with UTC date-stamped names.
# Keeps the last $RETAIN backups (default 14) and deletes anything older.
#
# Run from cron/systemd-timer:
#   0 3 * * *  cd /app && bash scripts/backup_db.sh
#
# Exit codes:
#   0  backup succeeded
#   1  misconfig (unreadable URL, missing tools, etc.)
#   2  backup command itself failed

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-./backups}"
RETAIN="${RETAIN:-14}"
URL="${HEROPROTO_DATABASE_URL:-}"

if [[ -z "${URL}" ]]; then
  echo "HEROPROTO_DATABASE_URL is not set" >&2
  exit 1
fi

mkdir -p "${BACKUP_DIR}"
STAMP="$(date -u +%Y%m%d-%H%M%SZ)"

backup_sqlite() {
  # Strip scheme; handle both sqlite:///relative and sqlite:////absolute.
  local path="${URL#sqlite:///}"
  if [[ "${URL}" == sqlite:////* ]]; then
    path="/${URL#sqlite:////}"
  fi
  if [[ ! -f "${path}" ]]; then
    echo "sqlite file not found: ${path}" >&2
    exit 1
  fi
  local out="${BACKUP_DIR}/hero-proto-${STAMP}.db.gz"
  # Use the sqlite3 CLI's .backup command if available for a consistent
  # snapshot even if the DB is being written to. Falls back to cp.
  if command -v sqlite3 >/dev/null 2>&1; then
    local tmp="${BACKUP_DIR}/.in-flight-${STAMP}.db"
    sqlite3 "${path}" ".backup '${tmp}'" || { rm -f "${tmp}"; exit 2; }
    gzip -c "${tmp}" > "${out}" && rm -f "${tmp}" || exit 2
  else
    gzip -c "${path}" > "${out}" || exit 2
  fi
  echo "${out}"
}

backup_postgres() {
  if ! command -v pg_dump >/dev/null 2>&1; then
    echo "pg_dump not found — install postgresql-client" >&2
    exit 1
  fi
  local out="${BACKUP_DIR}/hero-proto-${STAMP}.dump"
  # pg_dump accepts the SQLAlchemy-style URL directly. Strip the +psycopg
  # driver suffix if present.
  local pg_url="${URL/postgresql+psycopg:/postgresql:}"
  pg_url="${pg_url/postgresql+asyncpg:/postgresql:}"
  pg_dump --format=custom --no-owner --no-privileges --file="${out}" "${pg_url}" || exit 2
  echo "${out}"
}

case "${URL}" in
  sqlite:*)       OUT=$(backup_sqlite) ;;
  postgresql:*|postgres:*) OUT=$(backup_postgres) ;;
  *)
    echo "unsupported database URL scheme: ${URL}" >&2
    exit 1
    ;;
esac

echo "[backup_db] wrote ${OUT} ($(du -h "${OUT}" | cut -f1))"

# Retention: keep the newest ${RETAIN}, delete anything older by name-sort.
# Names sort lexically with the ISO timestamp, so `ls -1` is ordered oldest-first.
mapfile -t ALL < <(ls -1 "${BACKUP_DIR}" | grep -E "^hero-proto-.*\.(db\.gz|dump)$" || true)
COUNT="${#ALL[@]}"
if (( COUNT > RETAIN )); then
  PRUNE=$(( COUNT - RETAIN ))
  for old in "${ALL[@]:0:${PRUNE}}"; do
    rm -f -- "${BACKUP_DIR}/${old}"
    echo "[backup_db] pruned ${old}"
  done
fi
