"""Build/release version metadata.

Resolved once at import time. Order of preference:
  1. HEROPROTO_BUILD_VERSION env var (set in CI / Dockerfile / fly deploy)
  2. git short SHA from `git rev-parse --short HEAD`
  3. fallback: "dev"

Surfaced via GET /version so a client can ask "what code am I hitting?"
"""

from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone


def _resolve() -> dict[str, str]:
    version = os.getenv("HEROPROTO_BUILD_VERSION")
    if not version:
        try:
            version = subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
                timeout=2,
            ).decode().strip()
        except Exception:
            version = "dev"

    built_at = os.getenv("HEROPROTO_BUILD_TIME") or datetime.now(timezone.utc).isoformat(timespec="seconds")

    branch = os.getenv("HEROPROTO_BUILD_BRANCH")
    if not branch:
        try:
            branch = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                stderr=subprocess.DEVNULL,
                timeout=2,
            ).decode().strip()
        except Exception:
            branch = "?"

    return {
        "version": version,
        "branch": branch,
        "built_at": built_at,
    }


VERSION_INFO: dict[str, str] = _resolve()
