"""Worker tick prunes — battle log compaction + refresh-token cleanup.

Both run inside `_run_jobs` and are exercised against real DB rows seeded
with controlled timestamps. We avoid the supervisor loop and just call
`_run_jobs` synchronously to keep the tests deterministic.
"""

from __future__ import annotations

import json
import random
from datetime import timedelta

from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    Account,
    Battle,
    BattleOutcome,
    RefreshToken,
    utcnow,
)
from app.worker import (
    BATTLE_LOG_COMPACTION_DAYS,
    REFRESH_TOKEN_RETENTION_DAYS,
    _run_jobs,
)


def _register(client, prefix: str = "wcomp") -> int:
    email = f"{prefix}+{random.randint(100000, 999999)}@example.com"
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 201
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    return client.get("/me", headers=hdr).json()["id"]


# --- Battle log compaction ---------------------------------------------------


def test_old_battle_log_gets_compacted(client) -> None:
    """A Battle older than the retention window has its log_json replaced
    with the COMPACTED marker; participants/outcome/rewards are untouched."""
    aid = _register(client, "wbat")
    long_log = json.dumps([{"type": "TURN", "unit": "a0"}, {"type": "DAMAGE", "amount": 50}])
    with SessionLocal() as db:
        b = Battle(
            account_id=aid, stage_id=1,
            outcome=BattleOutcome.WIN,
            log_json=long_log,
            team_json="[]",
            participants_json="[]",
            rewards_json="{}",
            first_clear=0,
        )
        # Force the row's created_at past the cutoff.
        b.created_at = utcnow() - timedelta(days=BATTLE_LOG_COMPACTION_DAYS + 1)
        db.add(b)
        db.commit()
        bid = b.id

    _run_jobs()

    with SessionLocal() as db:
        b = db.get(Battle, bid)
        parsed = json.loads(b.log_json)
        assert len(parsed) == 1
        assert parsed[0]["type"] == "COMPACTED"
        assert parsed[0]["outcome"]  # outcome preserved in the marker
        # Other columns survive the compaction.
        assert b.outcome == BattleOutcome.WIN


def test_recent_battle_log_is_not_compacted(client) -> None:
    """Battles inside the retention window keep their full play-by-play."""
    aid = _register(client, "wbatr")
    keep_log = json.dumps([{"type": "TURN", "unit": "a0"}])
    with SessionLocal() as db:
        b = Battle(
            account_id=aid, stage_id=1,
            outcome=BattleOutcome.LOSS,
            log_json=keep_log,
            team_json="[]",
            participants_json="[]",
            rewards_json="{}",
            first_clear=0,
        )
        b.created_at = utcnow() - timedelta(days=1)
        db.add(b)
        db.commit()
        bid = b.id

    _run_jobs()

    with SessionLocal() as db:
        b = db.get(Battle, bid)
        assert b.log_json == keep_log


def test_compaction_is_idempotent(client) -> None:
    """Re-running the worker on an already-compacted row is a no-op (no new
    write, no log churn)."""
    aid = _register(client, "wbati")
    with SessionLocal() as db:
        b = Battle(
            account_id=aid, stage_id=1,
            outcome=BattleOutcome.DRAW,
            log_json='[{"type":"COMPACTED","outcome":"DRAW"}]',
            team_json="[]",
            participants_json="[]",
            rewards_json="{}",
            first_clear=0,
        )
        b.created_at = utcnow() - timedelta(days=BATTLE_LOG_COMPACTION_DAYS + 5)
        db.add(b)
        db.commit()
        bid = b.id

    _run_jobs()
    _run_jobs()

    with SessionLocal() as db:
        b = db.get(Battle, bid)
        # Still the original compacted form, no double-wrap or churn.
        parsed = json.loads(b.log_json)
        assert len(parsed) == 1
        assert parsed[0]["type"] == "COMPACTED"


# --- Refresh-token cleanup ---------------------------------------------------


def test_old_revoked_refresh_token_is_pruned(client) -> None:
    """Revoked-long-ago tokens get hard-deleted."""
    aid = _register(client, "wrt")
    with SessionLocal() as db:
        rt = RefreshToken(
            account_id=aid,
            token_hash="x" * 64,
            issued_at=utcnow() - timedelta(days=REFRESH_TOKEN_RETENTION_DAYS + 5),
            expires_at=utcnow() + timedelta(days=30),  # not yet expired
            revoked_at=utcnow() - timedelta(days=REFRESH_TOKEN_RETENTION_DAYS + 1),
        )
        db.add(rt)
        db.commit()
        rid = rt.id

    _run_jobs()

    with SessionLocal() as db:
        assert db.get(RefreshToken, rid) is None, "old revoked token must be deleted"


def test_old_expired_refresh_token_is_pruned(client) -> None:
    """Naturally-expired tokens (never explicitly revoked) also get pruned."""
    aid = _register(client, "wrte")
    with SessionLocal() as db:
        rt = RefreshToken(
            account_id=aid,
            token_hash="y" * 64,
            issued_at=utcnow() - timedelta(days=REFRESH_TOKEN_RETENTION_DAYS + 90),
            expires_at=utcnow() - timedelta(days=REFRESH_TOKEN_RETENTION_DAYS + 1),
            revoked_at=None,
        )
        db.add(rt)
        db.commit()
        rid = rt.id

    _run_jobs()

    with SessionLocal() as db:
        assert db.get(RefreshToken, rid) is None


def test_recent_revoked_refresh_token_is_kept(client) -> None:
    """Revoked-but-recent rows stay around — within the retention window
    they're still useful for the active-sessions list (revoked badge) and
    for forensics on a session that just got killed."""
    aid = _register(client, "wrtk")
    with SessionLocal() as db:
        rt = RefreshToken(
            account_id=aid,
            token_hash="z" * 64,
            issued_at=utcnow() - timedelta(days=2),
            expires_at=utcnow() + timedelta(days=30),
            revoked_at=utcnow() - timedelta(days=1),
        )
        db.add(rt)
        db.commit()
        rid = rt.id

    _run_jobs()

    with SessionLocal() as db:
        assert db.get(RefreshToken, rid) is not None
