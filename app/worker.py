"""Background maintenance task. Runs inside the app lifespan on a single interval.

Jobs:
  - Daily cleanup: delete CLAIMED quests older than the retention window.
  - Raid expiry: flip raids past their ends_at to EXPIRED.

Single-process only — fine for alpha. For horizontal scale, move to a worker
(Celery / RQ / arq / plain cron) and remove the lifespan task.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from sqlalchemy import delete, select

from app.db import SessionLocal
from app.models import DailyQuest, DailyQuestStatus, Raid, RaidState, utcnow

log = logging.getLogger("worker")

DAILY_RETENTION_DAYS = 7
WORKER_INTERVAL_SECONDS = 60.0


async def worker_loop() -> None:
    log.info("worker loop started (interval=%ss)", WORKER_INTERVAL_SECONDS)
    try:
        # One immediate pass at startup for a fresh DB state.
        await _tick_once()
        while True:
            await asyncio.sleep(WORKER_INTERVAL_SECONDS)
            await _tick_once()
    except asyncio.CancelledError:
        log.info("worker loop cancelled")
        raise


async def _tick_once() -> None:
    try:
        await asyncio.to_thread(_run_jobs)
    except Exception:
        log.exception("worker job failed")


def _run_jobs() -> None:
    now = utcnow()
    cutoff = now - timedelta(days=DAILY_RETENTION_DAYS)
    with SessionLocal() as db:
        result = db.execute(
            delete(DailyQuest).where(
                DailyQuest.status == DailyQuestStatus.CLAIMED,
                DailyQuest.completed_at.is_not(None),
                DailyQuest.completed_at < cutoff,
            )
        )
        deleted = result.rowcount or 0

        expired = 0
        for raid in db.scalars(
            select(Raid).where(
                Raid.state == RaidState.ACTIVE, Raid.ends_at <= now
            )
        ):
            raid.state = RaidState.EXPIRED
            expired += 1

        if deleted or expired:
            db.commit()
            log.info("worker tick: pruned %d dailies, expired %d raids", deleted, expired)
