"""Cloudflare Turnstile server-side verification.

Add HEROPROTO_TURNSTILE_SECRET_KEY as a Fly secret (from the Cloudflare
Turnstile dashboard). When the key is absent the check is skipped — safe
for dev/test, enforced in prod via main._check_secrets.

Usage:
    from app.captcha import verify_turnstile
    if not verify_turnstile(token, remote_ip=client_ip):
        raise HTTPException(400, "CAPTCHA failed")
"""

from __future__ import annotations

import logging

import httpx

from app.config import settings

log = logging.getLogger("captcha")

_VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v1/siteverify"


def verify_turnstile(token: str | None, *, remote_ip: str | None = None) -> bool:
    """Return True if the Turnstile token is valid (or Turnstile is not configured).

    Always returns True when HEROPROTO_TURNSTILE_SECRET_KEY is empty so dev
    and test environments don't need a real widget. Network errors are logged
    and treated as pass (open-fail) so a Cloudflare outage doesn't lock users out.
    """
    secret = settings.turnstile_secret_key
    if not secret:
        return True

    if not token:
        return False

    data: dict[str, str] = {"secret": secret, "response": token}
    if remote_ip:
        data["remoteip"] = remote_ip

    try:
        resp = httpx.post(_VERIFY_URL, data=data, timeout=5)
        result = resp.json()
        success = bool(result.get("success"))
        if not success:
            log.warning("turnstile rejected token: codes=%s", result.get("error-codes"))
        return success
    except Exception:
        log.exception("turnstile verification request failed — open-failing to allow")
        return True
