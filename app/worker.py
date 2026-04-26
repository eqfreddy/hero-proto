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
import json
import logging
import random
from datetime import timedelta

from sqlalchemy import delete, func, select

from app.db import SessionLocal
from app.models import (
    Account,
    Battle,
    DailyQuest,
    DailyQuestStatus,
    Guild,
    GuildMember,
    HeroTemplate,
    Rarity,
    Raid,
    RaidState,
    RaidTier,
    RefreshToken,
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
# After this many days, replace a Battle.log_json with a single END event.
# Players almost never re-watch month-old battles; the full per-tick log is
# 30-65 KB each and accumulates faster than any other table. The participants
# snapshot, outcome, and rewards stay intact — only the play-by-play is lost.
BATTLE_LOG_COMPACTION_DAYS = 30
# Hard delete refresh-token rows that have been revoked (or simply expired)
# for longer than this. The active sessions list filters them out already, so
# they're dead weight in the DB after this window.
REFRESH_TOKEN_RETENTION_DAYS = 30
# Backoff on loop-level crash (not individual job failures — those are swallowed).
SUPERVISOR_RESTART_DELAY_SECONDS = 5.0
SUPERVISOR_RESTART_DELAY_MAX = 60.0


class WorkerHealth:
    """Per-process worker telemetry. Exposed via /healthz and /worker/status so
    operators / probes can tell the difference between 'running fine' and 'the
    loop died and nobody noticed'."""

    last_tick_at: "datetime | None" = None
    last_tick_success: bool = True
    last_error: str = ""
    ticks_total: int = 0
    ticks_failed: int = 0
    restarts: int = 0  # loop-level crashes the supervisor recovered from


health = WorkerHealth()


async def _tick_once() -> None:
    """Run _run_jobs off-thread and record telemetry. Never raises — per-tick
    failures are swallowed so the outer loop keeps marching."""
    try:
        await asyncio.to_thread(_run_jobs)
        health.last_tick_success = True
        health.last_error = ""
    except Exception as exc:
        health.last_tick_success = False
        health.last_error = f"{type(exc).__name__}: {exc}"
        health.ticks_failed += 1
        log.exception("worker job failed")
    finally:
        health.last_tick_at = utcnow()
        health.ticks_total += 1


async def worker_loop() -> None:
    """Single iteration of the tick loop. Raises CancelledError on shutdown
    (normal); any other exception is treated as a bug and the supervisor
    respawns this function. Per-tick failures inside _tick_once are already
    swallowed, so worker_loop should almost never raise."""
    log.info("worker loop started (interval=%ss)", WORKER_INTERVAL_SECONDS)
    try:
        await _tick_once()
        while True:
            await asyncio.sleep(WORKER_INTERVAL_SECONDS)
            await _tick_once()
    except asyncio.CancelledError:
        log.info("worker loop cancelled")
        raise


async def supervised_worker_loop() -> None:
    """Supervise worker_loop with exponential backoff. If the loop exits with
    an unexpected exception, log it, wait, and respawn. Cancellation (shutdown
    signal) propagates cleanly."""
    backoff = SUPERVISOR_RESTART_DELAY_SECONDS
    while True:
        try:
            await worker_loop()
            # Loop returned cleanly — shouldn't happen without CancelledError.
            # Log it and respawn.
            log.warning("worker_loop exited without cancellation — respawning")
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("worker_loop crashed — restarting in %ss", backoff)
            health.restarts += 1
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, SUPERVISOR_RESTART_DELAY_MAX)


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

        # Battle log compaction. Replace log_json with a single END marker on
        # battles older than the retention window. We use json.dumps directly
        # rather than going through the resolver to avoid pulling combat code
        # into worker land. Match by an explicit prefix on log_json so re-
        # running this never re-touches an already-compacted row.
        compaction_cutoff = now - timedelta(days=BATTLE_LOG_COMPACTION_DAYS)
        compacted = 0
        for b in db.scalars(
            select(Battle).where(
                Battle.created_at < compaction_cutoff,
                # Compacted rows start with [{"type":"COMPACTED"... — skip them.
                ~Battle.log_json.startswith('[{"type":"COMPACTED"'),
            ).limit(500)  # cap each tick's work so we don't lock the table
        ):
            b.log_json = json.dumps([{
                "type": "COMPACTED",
                "outcome": str(b.outcome),
                "reason": f"battle log compacted after {BATTLE_LOG_COMPACTION_DAYS} days",
            }], separators=(",", ":"))
            compacted += 1

        # Refresh-token cleanup. Once a token has been revoked or has expired
        # past the retention window, the active-sessions endpoint already
        # filters it out — but the row still occupies space and slows index
        # lookups. Hard-delete past the window. Replaced rows have a non-null
        # replaced_by_id pointing at the new token; ondelete=SET NULL on that
        # FK means deleting the old one just nulls the back-pointer (no
        # cascade to the live token).
        token_cutoff = now - timedelta(days=REFRESH_TOKEN_RETENTION_DAYS)
        token_result = db.execute(
            delete(RefreshToken).where(
                # Either revoked long ago, or expired long ago.
                ((RefreshToken.revoked_at.is_not(None)) & (RefreshToken.revoked_at < token_cutoff))
                | ((RefreshToken.revoked_at.is_(None)) & (RefreshToken.expires_at < token_cutoff))
            )
        )
        tokens_pruned = token_result.rowcount or 0

        if deleted or expired or unbanned or rotated or compacted or tokens_pruned:
            db.commit()
            log.info(
                "worker tick: pruned %d dailies, expired %d raids, "
                "auto-unbanned %d accounts, auto-rotated %d raids, "
                "compacted %d battle logs, pruned %d refresh tokens",
                deleted, expired, unbanned, rotated, compacted, tokens_pruned,
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
