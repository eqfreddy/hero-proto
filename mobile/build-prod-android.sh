#!/usr/bin/env bash
# Build a production-flavoured Android bundle.
#   - SPA is built with VITE_API_BASE_URL pointing at the live API
#   - capacitor.config.prod.ts (no server.url) is used so the bundled SPA loads from file://
#   - cap sync runs to refresh native assets
#   - prints a version banner so you can verify the running app matches the build
#
# After this script, open mobile/android/ in Android Studio and run
# Build > Generate Signed Bundle / APK to produce the .aab for Play Console.
#
# Override the API URL with API_BASE=... if needed (default: hero-proto.fly.dev).
set -euo pipefail

API_BASE="${API_BASE:-https://hero-proto.fly.dev}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEV_CFG="$SCRIPT_DIR/capacitor.config.ts"
PROD_CFG="$SCRIPT_DIR/capacitor.config.prod.ts"
BACKUP_CFG="$SCRIPT_DIR/capacitor.config.dev.bak"

if [[ ! -f "$PROD_CFG" ]]; then
  echo "Missing $PROD_CFG — bail." >&2
  exit 1
fi

# ── Version stamp ────────────────────────────────────────────────────────────
GIT_SHA="$(git -C "$ROOT_DIR" rev-parse --short HEAD 2>/dev/null || echo dev)"
GIT_BRANCH="$(git -C "$ROOT_DIR" rev-parse --abbrev-ref HEAD 2>/dev/null || echo '?')"
GIT_DIRTY=""
if ! git -C "$ROOT_DIR" diff --quiet 2>/dev/null || ! git -C "$ROOT_DIR" diff --cached --quiet 2>/dev/null; then
  GIT_DIRTY="-dirty"
fi
BUILD_VERSION="${GIT_SHA}${GIT_DIRTY}"
BUILD_TIME="$(date -u '+%Y-%m-%d %H:%M:%SZ')"

cat <<EOF

╔═══════════════════════════════════════════════════════════════════════╗
║  hero-proto Android prod build
║
║   Version : $BUILD_VERSION
║   Branch  : $GIT_BRANCH
║   Built   : $BUILD_TIME
║   API     : $API_BASE
╚═══════════════════════════════════════════════════════════════════════╝

EOF

echo "[1/4] Building SPA (relative paths for Capacitor file://, version $BUILD_VERSION)"
( cd "$ROOT_DIR/frontend" \
  && VITE_API_BASE_URL="$API_BASE" \
     VITE_APP_VERSION="$BUILD_VERSION" \
     VITE_APP_BUILD_TIME="$BUILD_TIME" \
     npx tsc -b \
  && VITE_API_BASE_URL="$API_BASE" \
     VITE_APP_VERSION="$BUILD_VERSION" \
     VITE_APP_BUILD_TIME="$BUILD_TIME" \
     npx vite build --base ./ )

echo "[2/4] Swapping in production capacitor.config.ts"
cp "$DEV_CFG" "$BACKUP_CFG"
cp "$PROD_CFG" "$DEV_CFG"

restore() {
  echo "[restore] Putting dev capacitor.config.ts back"
  mv "$BACKUP_CFG" "$DEV_CFG"
}
trap restore EXIT

echo "[3/4] cap sync android"
( cd "$SCRIPT_DIR" && npx cap sync android )

# build --base ./ wrote relative asset paths to app/static/spa/; restore absolute paths for FastAPI.
echo "[4/4] Restoring server SPA (absolute paths for FastAPI)"
( cd "$ROOT_DIR/frontend" \
  && VITE_APP_VERSION="$BUILD_VERSION" \
     VITE_APP_BUILD_TIME="$BUILD_TIME" \
     npm run build )

cat <<EOF

╔═══════════════════════════════════════════════════════════════════════╗
║  ✅ BUILD READY — version $BUILD_VERSION
║
║  Look for "v$BUILD_VERSION" in the bottom-right corner of the running
║  emulator app to confirm it actually picked up THIS build.
║
║  Next: open mobile/android/ in Android Studio, click ▶ Run.
║  Or from CLI:
║     cd mobile/android && ./gradlew installDebug
╚═══════════════════════════════════════════════════════════════════════╝

EOF
