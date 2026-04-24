"""Background maintenance task. Runs inside the app lifespan on a single interval.

Jobs:
  - Daily cleanup: delete CLAIMED quests older than the retention window.
  - Raid expiry: flip raids past their ends_at to EXPIRED.
  - Raid auto-rotation: start a new T1 raid for any guild with members whose
    last raid ended at least RAID_ROTATION_COOLDOWN_HOURS ago.
  - Banned-account auto-unban: clear timed bans whose banned_until elapsed.

Single-process only — fine for alpha. For horizontal scale, move to a worker
(Celery / RQ / arq / plain cron) and remove the lifespan task.
"""

from __future__ import annotations

import asyncio
import logging
import random
from datetime import timedelta

from sqlalchemy import delete, func, select

from app.db import SessionLocal
from app.models import (
    Account,
    DailyQuest,
    DailyQuestStatus,
    Guild,
    GuildMember,
    HeroTemplate,
    Rarity,
    Raid,
    RaidState,
    RaidTier,
    utcnow,
)
from app.routers.raids import boss_hp_for_tier

log = logging.getLogger("worker")

DAILY_RETENTION_DAYS = 7
WORKER_INTERVAL_SECONDS = 60.0
# Gap after a raid ends (DEFEATED or EXPIRED) before auto-rotation starts a fresh one.
RAID_ROTATION_COOLDOWN_HOURS = 6
# Auto-rotated raids run for this long before expiring.
RAID_AUTO_DURATION_HOURS = 24


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

        unbanned = 0
        for account in db.scalars(
            select(Account).where(
                Account.is_banned.is_(True),
                Account.banned_until.is_not(None),
                Account.banned_until <= now,
            )
        ):
            account.is_banned = False
            account.banned_reason = ""
            account.banned_until = None
            unbanned += 1

        # Raid auto-rotation must run after raid expiry so just-expired raids become
        # candidates for replacement in the same tick.
        rotated = _auto_rotate_raids(db, now)

        if deleted or expired or unbanned or rotated:
            db.commit()
            log.info(
                "worker tick: pruned %d dailies, expired %d raids, "
                "auto-unbanned %d accounts, auto-rotated %d raids",
                deleted, expired, unbanned, rotated,
            )


def _auto_rotate_raids(db, now) -> int:
    """For every guild with ≥1 member and no ACTIVE raid, start a fresh T1 raid
    if their most recent raid ended at least RAID_ROTATION_COOLDOWN_HOURS ago
    (or they've never had one).

    Returns count of raids started."""
    # Candidate bosses: EPIC or LEGENDARY templates. Roster-scale filter so we
    # don't pick a generic COMMON as a raid boss.
    candidates = list(
        db.scalars(
            select(HeroTemplate).where(HeroTemplate.rarity.in_([Rarity.EPIC, Rarity.LEGENDARY]))
        )
    )
    if not candidates:
        return 0

    # Guilds with at least one member.
    guild_rows = db.execute(
        select(Guild.id, func.count(GuildMember.account_id))
        .outerjoin(GuildMember, GuildMember.guild_id == Guild.id)
        .group_by(Guild.id)
    )
    cooldown = timedelta(hours=RAID_ROTATION_COOLDOWN_HOURS)
    started = 0

    for guild_id, member_count in guild_rows:
        if not member_count:
            continue

        # Skip if they already have an active one.
        active = db.scalar(
            select(Raid).where(
                Raid.guild_id == guild_id,
                Raid.state == RaidState.ACTIVE,
            )
        )
        if active is not None:
            continue

        # Most recent completed raid (defeated or expired) — if within the cooldown, skip.
        last = db.scalar(
            select(Raid)
            .where(Raid.guild_id == guild_id)
            .order_by(Raid.started_at.desc())
        )
        if last is not None:
            last_ended = last.ends_at if last.state == RaidState.EXPIRED else (last.started_at + cooldown)
            # Use ends_at as the "ended" marker for both defeated and expired raids.
            # If ended_at is not available (DEFEATED with no explicit ended_at), fall back to
            # started_at + duration. Our model doesn't store a defeated_at — use ends_at.
            if last.ends_at + cooldown > now:
                continue

        # Seeded RNG so behaviour is deterministic across restarts (tests + reproducibility).
        rng = random.Random(f"{guild_id}:{now.isoformat()[:10]}")
        boss = rng.choice(candidates)

        max_hp = boss_hp_for_tier(boss.base_hp, 20, RaidTier.T1)
        raid = Raid(
            guild_id=guild_id,
            boss_template_id=boss.id,
            boss_level=20,
            max_hp=max_hp,
            remaining_hp=max_hp,
            state=RaidState.ACTIVE,
            tier=RaidTier.T1,
            started_at=now,
            ends_at=now + timedelta(hours=RAID_AUTO_DURATION_HOURS),
            started_by=None,  # signals "auto-rotated"
        )
        db.add(raid)
        started += 1

    return started
