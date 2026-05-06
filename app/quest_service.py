"""Quest progression engine.

record_event() is fire-and-forget — never raises. Call it from any router
after a user action completes. It advances matching task progress on all
active AccountQuest rows for the account and marks completion when all
tasks hit their targets.

Task definition shape (stored in Quest.tasks_json):
[
  {"id": "first_battle", "label": "Run your first battle",
   "event": "BATTLE_COMPLETE", "target": 1},
  ...
]

Task 14 (DAILY_QUEST_COMPLETE with target=3) tracks unique calendar days,
not raw count. progress_json stores {"daily_3_days": 2, ...} for
simple counters and {"daily_quest_days": ["2026-05-06", ...]} for day-sets.
"""
from __future__ import annotations

import json
import logging
from datetime import date

from sqlalchemy.orm import Session

from app.models import Account, AccountQuest, Quest, utcnow

log = logging.getLogger(__name__)

# Events that track unique calendar days rather than raw count.
# The task id that triggers this behaviour is identified by checking
# task["id"] == DAY_TRACKING_TASK_ID.
DAY_TRACKING_TASK_ID = "daily_3_days"
# DAY_TRACKING_EVENT is the expected event for the day-tracking task.
# The outer loop already filters by event, so the inner branch keys on task_id only.
DAY_TRACKING_EVENT = "DAILY_QUEST_COMPLETE"
DAY_TRACKING_PROGRESS_KEY = "daily_quest_days"


def record_event(db: Session, account: Account, event: str, payload: dict | None = None) -> None:
    """Advance quest tasks matching `event` for this account. Never raises."""
    try:
        _record_event(db, account, event, payload or {})
    except Exception:
        log.exception("quest record_event failed (event=%s account=%s)", event, account.id)


def _record_event(db: Session, account: Account, event: str, payload: dict) -> None:
    rows = (
        db.query(AccountQuest)
        .filter(
            AccountQuest.account_id == account.id,
            AccountQuest.claimed_at.is_(None),
            AccountQuest.dismissed.is_(False),
            AccountQuest.completed_at.is_(None),
        )
        .all()
    )
    if not rows:
        return

    for aq in rows:
        quest = db.get(Quest, aq.quest_id)
        if quest is None:
            continue
        tasks = json.loads(quest.tasks_json)
        progress = json.loads(aq.progress_json)
        changed = False

        for task in tasks:
            if task["event"] != event:
                continue
            task_id = task["id"]
            target = int(task["target"])

            # Day-set tracking for the "3 separate days" daily task.
            if task_id == DAY_TRACKING_TASK_ID:
                days: list[str] = progress.get(DAY_TRACKING_PROGRESS_KEY, [])
                today = date.today().isoformat()
                if today not in days:
                    days.append(today)
                    progress[DAY_TRACKING_PROGRESS_KEY] = days
                    # current = unique day count
                    progress[task_id] = len(days)
                    changed = True
            else:
                current = int(progress.get(task_id, 0))
                if current >= target:
                    continue
                progress[task_id] = current + 1
                changed = True

        if not changed:
            continue

        aq.progress_json = json.dumps(progress)

        # Check if all tasks complete.
        all_done = all(
            _task_complete(t, progress) for t in tasks
        )
        if all_done and aq.completed_at is None:
            aq.completed_at = utcnow()

        db.flush()


def _task_complete(task: dict, progress: dict) -> bool:
    task_id = task["id"]
    target = int(task["target"])
    if task_id == DAY_TRACKING_TASK_ID:
        days = progress.get(DAY_TRACKING_PROGRESS_KEY, [])
        return len(days) >= target
    return int(progress.get(task_id, 0)) >= target
