"""Friend Points — daily ping currency + friend-summon banner.

Loop:
- Player A pings player B once per UTC day → both A and B receive +5 FP.
- Daily send cap (FP_DAILY_SEND_CAP = 30) so heavy farmers don't grind
  500-friend lists; per-pair UTC-day uniqueness in friend_pings PK.
- 50 FP buys one pull on the friend-summon banner. Pool = COMMON/UNCOMMON
  with rare RARE/EPIC bumps and a 100-pull hard pity.
- Separate pity counter (fp_pulls_since_epic) so spending FP doesn't
  burn standard-banner pity.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Account, FriendPing, Friendship, FriendshipStatus, Rarity, utcnow

FP_PER_PING = 5
FP_DAILY_SEND_CAP = 30
FP_PER_SUMMON = 50
FP_PITY_THRESHOLD = 100

# Friend banner pool: weighted toward Uncommon/Rare; small Epic bleed.
_FP_RATES: list[tuple[Rarity, float]] = [
    (Rarity.COMMON, 0.55),
    (Rarity.UNCOMMON, 0.32),
    (Rarity.RARE, 0.10),
    (Rarity.EPIC, 0.03),
]


def _today_utc_midnight(now: datetime | None = None) -> datetime:
    n = now or utcnow()
    return datetime(n.year, n.month, n.day)


def _reset_daily_counter_if_stale(account: Account) -> None:
    today = _today_utc_midnight()
    if account.friend_pings_today_date != today:
        account.friend_pings_sent_today = 0
        account.friend_pings_today_date = today


def can_send_more_today(account: Account) -> tuple[bool, int]:
    _reset_daily_counter_if_stale(account)
    sent = int(account.friend_pings_sent_today or 0)
    return sent < FP_DAILY_SEND_CAP, FP_DAILY_SEND_CAP - sent


def _are_friends(db: Session, a: int, b: int) -> bool:
    rows = db.scalars(
        select(Friendship).where(
            Friendship.account_id.in_((a, b)),
            Friendship.other_account_id.in_((a, b)),
            Friendship.status == FriendshipStatus.ACCEPTED,
        )
    ).all()
    pairs = {(r.account_id, r.other_account_id) for r in rows}
    return (a, b) in pairs and (b, a) in pairs


@dataclass
class PingResult:
    sent: bool
    fp_granted_to_self: int
    fp_granted_to_recipient: int
    reason: str | None = None


def send_ping(db: Session, sender: Account, recipient_id: int) -> PingResult:
    """Send a daily ping to a friend. Both sides receive FP_PER_PING.
    Idempotent per (sender, recipient, UTC date) via DB unique constraint."""
    if recipient_id == sender.id:
        return PingResult(False, 0, 0, "cannot ping yourself")
    if not _are_friends(db, sender.id, recipient_id):
        return PingResult(False, 0, 0, "not friends")
    ok, _ = can_send_more_today(sender)
    if not ok:
        return PingResult(False, 0, 0, f"daily send cap ({FP_DAILY_SEND_CAP}) reached")

    today = _today_utc_midnight()
    ping = FriendPing(
        sender_id=sender.id,
        recipient_id=recipient_id,
        sent_on=today,
        fp_granted=FP_PER_PING,
    )
    db.add(ping)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        return PingResult(False, 0, 0, "already pinged this friend today")

    # Grant FP to both parties.
    recipient = db.get(Account, recipient_id)
    if recipient is None:
        # Race: friend deleted between check and grant.
        return PingResult(False, 0, 0, "recipient account vanished")
    sender.friend_points = int(sender.friend_points or 0) + FP_PER_PING
    recipient.friend_points = int(recipient.friend_points or 0) + FP_PER_PING
    sender.friend_pings_sent_today = int(sender.friend_pings_sent_today or 0) + 1
    return PingResult(True, FP_PER_PING, FP_PER_PING)


def status(db: Session, account: Account) -> dict:
    _reset_daily_counter_if_stale(account)
    sent = int(account.friend_pings_sent_today or 0)
    return {
        "balance": int(account.friend_points or 0),
        "pings_sent_today": sent,
        "pings_remaining_today": max(0, FP_DAILY_SEND_CAP - sent),
        "pings_daily_cap": FP_DAILY_SEND_CAP,
        "fp_per_ping": FP_PER_PING,
        "fp_per_summon": FP_PER_SUMMON,
        "fp_pulls_since_epic": int(account.fp_pulls_since_epic or 0),
        "fp_pity_threshold": FP_PITY_THRESHOLD,
    }


# --- Friend-summon banner --------------------------------------------------


def _roll_fp_rarity(rng: random.Random) -> Rarity:
    r = rng.random()
    acc = 0.0
    for rarity, p in _FP_RATES:
        acc += p
        if r < acc:
            return rarity
    return _FP_RATES[-1][0]


@dataclass
class FpRollResult:
    rarity: Rarity
    pity_triggered: bool
    new_pity: int


def fp_roll(pity: int, rng: random.Random) -> FpRollResult:
    rolled = _roll_fp_rarity(rng)
    triggered = False
    if pity + 1 >= FP_PITY_THRESHOLD and rolled not in (Rarity.EPIC, Rarity.LEGENDARY, Rarity.MYTH):
        rolled = Rarity.EPIC
        triggered = True
    new_pity = 0 if rolled in (Rarity.EPIC, Rarity.LEGENDARY, Rarity.MYTH) else pity + 1
    return FpRollResult(rarity=rolled, pity_triggered=triggered, new_pity=new_pity)


def can_afford_summon(account: Account) -> bool:
    return int(account.friend_points or 0) >= FP_PER_SUMMON
