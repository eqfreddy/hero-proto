#!/usr/bin/env bash
# Run once to generate a release keystore and print the base64 for CI secrets.
# Usage: bash mobile/keygen.sh  (run from Git Bash or Android Studio terminal)

set -e

KEYSTORE="release.keystore"
ALIAS="heroproto"

# ── Find keytool ────────────────────────────────────────────────────────────
# Try PATH first, then common Windows install locations for Android Studio's JDK.
KEYTOOL=""
if command -v keytool &>/dev/null; then
    KEYTOOL="keytool"
else
    for candidate in \
        "/e/Android/Android Studio/jbr/bin/keytool" \
        "/c/Program Files/Android/Android Studio/jbr/bin/keytool" \
        "/c/Program Files/Android Studio/jbr/bin/keytool" \
        "/c/Program Files (x86)/Android/Android Studio/jbr/bin/keytool" \
        "$LOCALAPPDATA/Programs/Android Studio/jbr/bin/keytool" \
        "$HOME/AppData/Local/Programs/Android Studio/jbr/bin/keytool"
    do
        if [ -x "$candidate" ]; then
            KEYTOOL="$candidate"
            break
        fi
    done
fi

if [ -z "$KEYTOOL" ]; then
    echo "ERROR: keytool not found."
    echo ""
    echo "Install Android Studio, then re-run this script."
    echo "Or add keytool to PATH manually:"
    echo "  C:\\Program Files\\Android\\Android Studio\\jbr\\bin"
    exit 1
fi

echo "Using keytool: $KEYTOOL"

# ── Generate keystore ────────────────────────────────────────────────────────
if [ -f "$KEYSTORE" ]; then
  echo "Keystore already exists: $KEYSTORE"
  exit 0
fi

echo "Generating release keystore (you'll be prompted for passwords)..."
"$KEYTOOL" -genkey -v \
  -keystore "$KEYSTORE" \
  -alias "$ALIAS" \
  -keyalg RSA -keysize 2048 -validity 10000 \
  -dname "CN=Hero Proto, OU=Mobile, O=HeroProto, L=Unknown, S=Unknown, C=US"

echo ""
echo "Done. Add these to GitHub Secrets (Settings → Secrets and variables → Actions):"
echo ""
echo "  ANDROID_KEYSTORE_BASE64  →  $(base64 -w0 "$KEYSTORE" 2>/dev/null || base64 "$KEYSTORE")"
echo "  ANDROID_KEYSTORE_PASSWORD  →  <storePassword you entered>"
echo "  ANDROID_KEY_ALIAS  →  $ALIAS"
echo "  ANDROID_KEY_PASSWORD  →  <keyPassword you entered>"
echo ""
echo "For local builds, set these env vars before running Gradle:"
echo "  export ANDROID_KEYSTORE_PATH=$(pwd)/$KEYSTORE"
echo "  export ANDROID_KEYSTORE_PASSWORD=..."
echo "  export ANDROID_KEY_ALIAS=$ALIAS"
echo "  export ANDROID_KEY_PASSWORD=..."
