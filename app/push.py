"""Fire-and-forget push notification delivery.

Environment variables
---------------------
FCM (Android / web) — uses FCM HTTP v1 API:
  FCM_PROJECT_ID            Firebase project ID (e.g. "hero-proto-prod")
  FCM_SERVICE_ACCOUNT_JSON  Full service-account JSON contents (Firebase
                            console → Project Settings → Service accounts →
                            Generate new private key). One line, JSON-escaped.
                            OR leave unset to use FCM_SERVICE_ACCOUNT_PATH.
  FCM_SERVICE_ACCOUNT_PATH  Path to service account JSON file on disk.

  (Legacy FCM_SERVER_KEY was sunsetted by Google in June 2024 and is no
  longer accepted; the legacy code path has been removed.)

APNs (iOS):
  APNS_KEY_ID               10-char key ID from Apple Developer portal
  APNS_TEAM_ID              10-char team ID (top-right in Apple Developer)
  APNS_BUNDLE_ID            Bundle ID registered in App Store Connect, e.g.
                            com.heroproto.app
  APNS_AUTH_KEY_PEM         Contents of the .p8 auth key file (newlines as
                            \\n) OR leave unset to use APNS_AUTH_KEY_PATH.
  APNS_AUTH_KEY_PATH        Path to the .p8 file on disk.
  APNS_SANDBOX              Set to "1" to target the APNs sandbox (dev
                            builds).

When all relevant vars are absent the corresponding send functions are no-ops
— safe in dev / test without any mocking.

Token hygiene: tokens that bounce with UNREGISTERED / NOT_FOUND (FCM) or
:unregistered / BadDeviceToken (APNs) are deleted from the DB. Caller must
commit after send_push_to_account() returns.
"""

from __future__ import annotations

import json
import logging
import os
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# FCM HTTP v1
# ---------------------------------------------------------------------------

_FCM_PROJECT_ID: str | None = os.getenv("FCM_PROJECT_ID")
_FCM_SCOPE = "https://www.googleapis.com/auth/firebase.messaging"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# Cache: (access_token, expires_at_unix)
_fcm_token_cache: tuple[str, float] | None = None


def _fcm_service_account() -> dict | None:
    raw = os.getenv("FCM_SERVICE_ACCOUNT_JSON")
    if raw:
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            log.warning("FCM_SERVICE_ACCOUNT_JSON is not valid JSON: %s", exc)
            return None
    path = os.getenv("FCM_SERVICE_ACCOUNT_PATH")
    if path and os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError) as exc:
            log.warning("FCM service account at %s unreadable: %s", path, exc)
    return None


def _fcm_configured() -> bool:
    return bool(_FCM_PROJECT_ID and _fcm_service_account())


def _fcm_access_token() -> str | None:
    """Exchange the service-account JWT for a 1-hour OAuth2 access token, cached."""
    global _fcm_token_cache

    sa = _fcm_service_account()
    if not sa:
        return None

    now = time.time()
    if _fcm_token_cache and (_fcm_token_cache[1] - now) > 60:
        return _fcm_token_cache[0]

    try:
        import urllib.parse
        import urllib.request
        import jwt as pyjwt  # PyJWT is already a dep
    except ImportError as exc:
        log.warning("FCM v1: missing dep: %s", exc)
        return None

    private_key = sa.get("private_key")
    client_email = sa.get("client_email")
    if not private_key or not client_email:
        log.warning("FCM service account is missing private_key or client_email")
        return None

    iat = int(now)
    payload = {
        "iss": client_email,
        "scope": _FCM_SCOPE,
        "aud": _GOOGLE_TOKEN_URL,
        "iat": iat,
        "exp": iat + 3600,
    }
    try:
        assertion = pyjwt.encode(payload, private_key, algorithm="RS256")
    except Exception as exc:
        log.warning("FCM v1: JWT sign failed: %s", exc)
        return None

    body = urllib.parse.urlencode({
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": assertion,
    }).encode()
    req = urllib.request.Request(
        _GOOGLE_TOKEN_URL,
        data=body,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
    except Exception as exc:
        log.warning("FCM v1: token exchange failed: %s", exc)
        return None

    token = data.get("access_token")
    expires_in = int(data.get("expires_in", 3600))
    if not token:
        return None
    _fcm_token_cache = (token, now + expires_in)
    return token


def _fcm_send(token: str, title: str, body: str) -> str | None:
    """POST to FCM v1. Returns FCM error code on failure, None on success."""
    import urllib.error
    import urllib.request

    access_token = _fcm_access_token()
    if not access_token:
        return None

    url = f"https://fcm.googleapis.com/v1/projects/{_FCM_PROJECT_ID}/messages:send"
    payload = json.dumps({
        "message": {
            "token": token,
            "notification": {"title": title, "body": body},
            "android": {"priority": "HIGH"},
        }
    }).encode()
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; UTF-8",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return None if resp.status == 200 else f"HTTP {resp.status}"
    except urllib.error.HTTPError as exc:
        try:
            err_body = json.loads(exc.read().decode())
            code = (err_body.get("error", {}).get("details", [{}])[0]
                    .get("errorCode", err_body.get("error", {}).get("status", str(exc.code))))
        except Exception:
            code = str(exc.code)
        log.warning("FCM v1 error token=%s: %s", token[:16], code)
        return code
    except Exception as exc:
        log.warning("FCM v1 send error token=%s: %s", token[:16], exc)
        return "NETWORK_ERROR"


_FCM_STALE_CODES = {"UNREGISTERED", "NOT_FOUND", "INVALID_ARGUMENT", "404"}


# ---------------------------------------------------------------------------
# APNs (iOS)
# ---------------------------------------------------------------------------

_APNS_KEY_ID: str | None = os.getenv("APNS_KEY_ID")
_APNS_TEAM_ID: str | None = os.getenv("APNS_TEAM_ID")
_APNS_BUNDLE_ID: str | None = os.getenv("APNS_BUNDLE_ID")
_APNS_SANDBOX: bool = os.getenv("APNS_SANDBOX", "0") == "1"

_APNS_HOST_PROD = "api.push.apple.com"
_APNS_HOST_SANDBOX = "api.sandbox.push.apple.com"

# Lazy-loaded per process — built once on first APNs call.
_apns_jwt_cache: tuple[str, float] | None = None  # (token, issued_at)


def _get_apns_key_pem() -> str | None:
    pem = os.getenv("APNS_AUTH_KEY_PEM")
    if pem:
        return pem.replace("\\n", "\n")
    path = os.getenv("APNS_AUTH_KEY_PATH")
    if path and os.path.exists(path):
        with open(path) as f:
            return f.read()
    return None


def _apns_jwt() -> str | None:
    """Return a cached APNs provider JWT, re-issuing when > 45 min old."""
    global _apns_jwt_cache

    if not (_APNS_KEY_ID and _APNS_TEAM_ID):
        return None
    key_pem = _get_apns_key_pem()
    if not key_pem:
        return None

    now = time.time()
    if _apns_jwt_cache and (now - _apns_jwt_cache[1]) < 2700:  # 45 min
        return _apns_jwt_cache[0]

    try:
        import jwt as pyjwt  # PyJWT — already a dep (used by auth)
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        private_key = load_pem_private_key(key_pem.encode(), password=None)
        token = pyjwt.encode(
            {"iss": _APNS_TEAM_ID, "iat": int(now)},
            private_key,
            algorithm="ES256",
            headers={"kid": _APNS_KEY_ID},
        )
        _apns_jwt_cache = (token, now)
        return token
    except Exception as exc:
        log.warning("APNs JWT error: %s", exc)
        return None


def _apns_send(device_token: str, title: str, body: str) -> str | None:
    """Send via APNs HTTP/2. Returns error reason string or None on success."""
    bearer = _apns_jwt()
    if not bearer or not _APNS_BUNDLE_ID:
        return None

    import httpx

    host = _APNS_HOST_SANDBOX if _APNS_SANDBOX else _APNS_HOST_PROD
    url = f"https://{host}/3/device/{device_token}"
    headers = {
        "authorization": f"bearer {bearer}",
        "apns-topic": _APNS_BUNDLE_ID,
        "apns-push-type": "alert",
        "apns-priority": "10",
    }
    payload = {"aps": {"alert": {"title": title, "body": body}, "sound": "default"}}

    try:
        with httpx.Client(http2=True, timeout=5) as client:
            resp = client.post(url, json=payload, headers=headers)
        if resp.status_code == 200:
            return None
        reason = resp.json().get("reason", str(resp.status_code))
        log.warning("APNs error token=%s: %s", device_token[:16], reason)
        return reason
    except Exception as exc:
        log.warning("APNs send error token=%s: %s", device_token[:16], exc)
        return None


def _apns_configured() -> bool:
    return bool(_APNS_KEY_ID and _APNS_TEAM_ID and _APNS_BUNDLE_ID and _get_apns_key_pem())


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def push_provider_status() -> dict:
    """For admin diagnostics: returns which providers are configured."""
    return {
        "fcm": _fcm_configured(),
        "fcm_project_id": _FCM_PROJECT_ID,
        "apns": _apns_configured(),
        "apns_sandbox": _APNS_SANDBOX,
    }


def send_push_to_account(
    db: "Session",
    account_id: int,
    *,
    title: str,
    body: str = "",
) -> int:
    """Deliver a push to every registered device for account_id.

    Silently skips when no credentials are configured. Stale/unregistered
    tokens are deleted from the DB; call db.commit() after this returns if
    you want the deletes flushed (the caller in notifications.py does).

    Returns the number of devices the push attempt was made to (0 if not
    configured / no devices).
    """
    if not _fcm_configured() and not _apns_configured():
        return 0

    from sqlalchemy import select, delete as sa_delete
    from app.models import DeviceToken

    rows = db.scalars(
        select(DeviceToken).where(DeviceToken.account_id == account_id)
    ).all()
    if not rows:
        return 0

    sent = 0
    stale_ids: list[int] = []
    for row in rows:
        if row.platform == "fcm" and _fcm_configured():
            err = _fcm_send(row.token, title, body)
            sent += 1
            if err and err.upper() in _FCM_STALE_CODES:
                stale_ids.append(row.id)
        elif row.platform == "apns" and _apns_configured():
            reason = _apns_send(row.token, title, body)
            sent += 1
            if reason in ("Unregistered", "BadDeviceToken"):
                stale_ids.append(row.id)

    if stale_ids:
        db.execute(sa_delete(DeviceToken).where(DeviceToken.id.in_(stale_ids)))

    return sent
