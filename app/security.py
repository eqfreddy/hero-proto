from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from app.config import settings

_BCRYPT_MAX = 72


def _prep(raw: str) -> bytes:
    encoded = raw.encode("utf-8")
    if len(encoded) > _BCRYPT_MAX:
        raise ValueError(f"password exceeds {_BCRYPT_MAX} bytes after utf-8 encoding")
    return encoded


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(_prep(raw), bcrypt.gensalt()).decode("ascii")


def verify_password(raw: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_prep(raw), hashed.encode("ascii"))
    except ValueError:
        return False


def issue_token(account_id: int, token_version: int = 0) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(account_id),
        "tv": int(token_version),
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_ttl_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)


def decode_token(token: str) -> tuple[int, int]:
    """Returns (account_id, token_version). Older tokens without tv default to 0."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    return int(payload["sub"]), int(payload.get("tv", 0))
