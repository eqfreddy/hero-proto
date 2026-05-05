#!/usr/bin/env bash
# Quick dev emulator build: SPA with Capacitor-relative paths + cap sync.
# Use this whenever you've changed frontend code and want the emulator
# to run the latest bundle WITHOUT needing the local server running.
#
# ⚠️  EMULATOR ONLY — the synced config contains server.url pointing at
#     10.0.2.2:8000 (Android emulator loopback to your host machine).
#     Real physical devices cannot reach that address → black screen.
#     For a real device or Play Store build, use build-prod-android.sh.
#
# After this, open mobile/android/ in Android Studio and click ▶ Run,
# or: cd mobile/android && ./gradlew installDebug
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

GIT_SHA="$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || echo dev)"
GIT_DIRTY=""
if ! git -C "$ROOT_DIR" diff --quiet 2>/dev/null || ! git -C "$ROOT_DIR" diff --cached --quiet 2>/dev/null; then
  GIT_DIRTY="-dirty"
fi
BUILD_VERSION="${GIT_SHA}${GIT_DIRTY}"

echo "[1/3] Building SPA with Capacitor-relative paths (v${BUILD_VERSION})"
( cd "$ROOT_DIR/frontend" \
  && VITE_APP_VERSION="$BUILD_VERSION" \
     VITE_APP_BUILD_TIME="$(date -u '+%Y-%m-%d %H:%M:%SZ')" \
     npm run build:cap )

echo "[2/3] cap sync android"
( cd "$SCRIPT_DIR" && npx cap sync android )

# build:cap overwrites app/static/spa/ with relative paths, which breaks the
# FastAPI server. Rebuild the server SPA (absolute paths) so both targets are
# left in a valid state.
echo "[3/3] Restoring server SPA (absolute paths for FastAPI)"
( cd "$ROOT_DIR/frontend" && npm run build )

echo ""
echo "Done. Run the app in Android Studio (or: cd mobile/android && ./gradlew installDebug)."
echo "The version badge in the corner should show: ${BUILD_VERSION}"
