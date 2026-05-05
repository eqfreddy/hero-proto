#!/usr/bin/env bash
# admin-login.sh — fetches a 2FA-blessed admin JWT and prints it to stdout.
#
# Usage:
#   TOKEN=$(bash scripts/admin-login.sh)
#   curl -H "Authorization: Bearer $TOKEN" https://hero-proto.fly.dev/admin/push/status
#
# Prereqs:
#   - $HOME/.heroproto-admin-creds is a JSON file with {"email":"...","password":"..."}
#     (chmod 600). Create it once, then never type your password into a terminal again.
#   - You'll be prompted for the current 6-digit TOTP code on each invocation.
#
# Override the API host with API=https://other.example.com bash scripts/admin-login.sh.
set -euo pipefail

API="${API:-https://hero-proto.fly.dev}"
CREDS_FILE="${CREDS_FILE:-$HOME/.heroproto-admin-creds}"

if [[ ! -f "$CREDS_FILE" ]]; then
  cat <<EOF >&2
Missing $CREDS_FILE.

Create it once with:
  cat > "$CREDS_FILE" <<JSON
  {"email":"ridler69@gmail.com","password":"YourActualPassword"}
  JSON
  chmod 600 "$CREDS_FILE"

Then re-run this script.
EOF
  exit 1
fi

# Step 1 — password login → challenge_token
RESP=$(curl -s -X POST "$API/auth/login" \
  -H "Content-Type: application/json" \
  -d @"$CREDS_FILE")

CHALLENGE=$(echo "$RESP" | sed -n 's/.*"challenge_token":"\([^"]*\)".*/\1/p')

if [[ -z "$CHALLENGE" ]]; then
  echo "Login step 1 failed:" >&2
  echo "$RESP" >&2
  exit 1
fi

# Step 2 — TOTP prompt + verify
echo -n "TOTP code (6 digits): " >&2
read -r CODE
if [[ ! "$CODE" =~ ^[0-9]{6}$ ]]; then
  echo "Code must be 6 digits, got: $CODE" >&2
  exit 1
fi

RESP2=$(curl -s -X POST "$API/auth/2fa/verify" \
  -H "Content-Type: application/json" \
  -d "{\"challenge_token\":\"$CHALLENGE\",\"code\":\"$CODE\"}")

TOKEN=$(echo "$RESP2" | sed -n 's/.*"access_token":"\([^"]*\)".*/\1/p')

if [[ -z "$TOKEN" ]]; then
  echo "2FA verify failed:" >&2
  echo "$RESP2" >&2
  exit 1
fi

# Stdout = token only (so $(...) capture works clean)
echo "$TOKEN"
