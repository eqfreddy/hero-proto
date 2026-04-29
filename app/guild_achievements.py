"""Guild achievement helper: increment progress counters and mark completion.

Call `_update_guild_achievement(db, guild_id, metric, increment)` from any
router that performs a guild action. Do NOT call db.commit() here — callers
own the transaction boundary.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import GuildAchievement, GuildAchievementProgress, utcnow


def _update_guild_achievement(
    db: Session,
    guild_id: int,
    metric: str,
    increment: int = 1,
) -> None:
    """Increment every achievement whose metric matches, creating progress rows as needed.

    This function deliberately does NOT call db.commit(). The caller owns the
    transaction so partial state is never committed mid-handler.
    """
    definitions = db.scalars(
        select(GuildAchievement).where(GuildAchievement.metric == metric)
    ).all()
    for ach in definitions:
        progress = db.scalar(
            select(GuildAchievementProgress).where(
                GuildAchievementProgress.guild_id == guild_id,
                GuildAchievementProgress.achievement_code == ach.code,
            )
        )
        if progress is None:
            progress = GuildAchievementProgress(
                guild_id=guild_id,
                achievement_code=ach.code,
                current_value=0,
            )
            db.add(progress)
        # Skip already-completed achievements — value is frozen at completion.
        if progress.completed_at is not None:
            continue
        progress.current_value += increment
        if progress.current_value >= ach.target_value:
            progress.current_value = ach.target_value
            progress.completed_at = utcnow()
