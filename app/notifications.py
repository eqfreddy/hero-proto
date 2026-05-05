"""Helper for posting in-app notifications.

Use `notify(db, account, kind=..., title=..., body=..., link=..., icon=...)`
from anywhere a player-visible event happens. Caller commits — we only
db.add() so it batches with the surrounding transaction.

Kind values are short slugs used by the UI to filter / style. Common ones
this codebase uses:
  - "tutorial_reward"
  - "achievement"
  - "mailbox_item"
  - "raid_ready"
  - "daily_reset"
  - "guild_event"
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Account, Notification
from app.push import send_push_to_account


def notify(
    db: Session,
    account: Account,
    *,
    kind: str,
    title: str,
    body: str = "",
    link: str = "",
    icon: str = "🔔",
) -> Notification:
    """Insert a notification row and fire a push if tokens are registered.

    Caller commits the in-app row; push delivery is fire-and-forget.
    """
    n = Notification(
        account_id=account.id,
        kind=kind[:32],
        title=title[:120],
        body=body[:512],
        link=link[:256],
        icon=icon[:8] or "🔔",
    )
    db.add(n)
    db.flush()
    try:
        send_push_to_account(db, account.id, title=title[:120], body=body[:256])
    except Exception:
        pass  # push failure must never break the in-app notification
    return n
