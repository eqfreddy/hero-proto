"""Per-account event progression state.

Schema lives on `Account.event_state_json` as a single JSON dict keyed by
event id. Per-event substate looks like:

    {
        "currency": 250,
        "quests": {"win_battles": 6, "summon_x10": 1},
        "claimed_quests": ["summon_x10"],
        "redeemed_milestones": [0, 1]
    }

This module is the only thing that reads/writes that blob — keep schema
churn in one place. Everywhere else uses these helpers.

Event specs (the JSON files in `events/`) define the quests + milestones;
this module just tracks per-account progress against them.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, LiveOpsEvent, utcnow

_EVENTS_DIR = Path(__file__).resolve().parents[1] / "events"


# --- Spec loading -------------------------------------------------------------


@dataclass(frozen=True)
class EventSpec:
    """Parsed JSON event spec, only the bits that drive per-account state."""

    id: str
    display_name: str
    starts_at: datetime
    ends_at: datetime
    currency_name: str            # e.g. "Sparks"
    currency_emoji: str           # e.g. "⚡"
    drops: dict[str, int]         # activity → currency per event of that activity
    quests: list[dict]            # {code, title, kind, goal, currency_reward}
    milestones: list[dict]        # {cost, title, contents}

    def quest_by_code(self, code: str) -> dict | None:
        for q in self.quests:
            if q.get("code") == code:
                return q
        return None


def _parse_iso(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is not None:
        dt = dt.astimezone(tz=None).replace(tzinfo=None)
    return dt


def load_event_spec(path: Path) -> EventSpec:
    """Parse an event JSON file. Defaults the quest/milestone/drops fields
    to empty so plain LiveOps events (Canada Day pack with no quests) load
    without crashing."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    return EventSpec(
        id=raw["id"],
        display_name=raw.get("display_name", raw["id"]),
        starts_at=_parse_iso(raw["starts_at"]),
        ends_at=_parse_iso(raw["ends_at"]),
        currency_name=raw.get("currency_name", ""),
        currency_emoji=raw.get("currency_emoji", ""),
        drops=raw.get("drops", {}),
        quests=raw.get("quests", []),
        milestones=raw.get("milestones", []),
    )


def list_event_specs() -> list[EventSpec]:
    """All event specs in events/. Ignores _template.json."""
    specs: list[EventSpec] = []
    for p in sorted(_EVENTS_DIR.glob("*.json")):
        if p.name.startswith("_"):
            continue
        try:
            specs.append(load_event_spec(p))
        except (KeyError, ValueError, json.JSONDecodeError):
            # Skip malformed; tests will catch the format breakage.
            continue
    return specs


def active_event_spec(now: datetime | None = None) -> EventSpec | None:
    """Return the first event spec whose window contains `now`. If multiple
    overlap, the one starting soonest first wins (deterministic by sorted
    file name).
    """
    when = now or utcnow()
    for spec in list_event_specs():
        if spec.starts_at <= when < spec.ends_at:
            return spec
    return None


# --- Per-account state read/write --------------------------------------------


def _state(account: Account) -> dict:
    try:
        return json.loads(account.event_state_json or "{}")
    except json.JSONDecodeError:
        return {}


def _save_state(account: Account, state: dict) -> None:
    account.event_state_json = json.dumps(state, separators=(",", ":"))


def _event_substate(state: dict, event_id: str) -> dict:
    sub = state.setdefault(event_id, {})
    sub.setdefault("currency", 0)
    sub.setdefault("quests", {})
    sub.setdefault("claimed_quests", [])
    sub.setdefault("redeemed_milestones", [])
    return sub


def currency_balance(account: Account, event_id: str) -> int:
    sub = _state(account).get(event_id) or {}
    return int(sub.get("currency", 0))


def grant_currency(account: Account, event_id: str, amount: int) -> int:
    """Add to the player's event currency balance. Returns new balance."""
    if amount <= 0:
        return currency_balance(account, event_id)
    state = _state(account)
    sub = _event_substate(state, event_id)
    sub["currency"] = int(sub["currency"]) + amount
    _save_state(account, state)
    return int(sub["currency"])


def spend_currency(account: Account, event_id: str, amount: int) -> bool:
    """Deduct currency. Returns True if successful, False if insufficient."""
    state = _state(account)
    sub = _event_substate(state, event_id)
    if int(sub["currency"]) < amount:
        return False
    sub["currency"] = int(sub["currency"]) - amount
    _save_state(account, state)
    return True


def quest_progress(account: Account, event_id: str, code: str) -> int:
    sub = _state(account).get(event_id) or {}
    return int((sub.get("quests") or {}).get(code, 0))


def advance_quest(account: Account, event_id: str, code: str, amount: int = 1) -> int:
    """Increment a quest's progress counter. Returns new value."""
    if amount <= 0:
        return quest_progress(account, event_id, code)
    state = _state(account)
    sub = _event_substate(state, event_id)
    sub["quests"][code] = int(sub["quests"].get(code, 0)) + amount
    _save_state(account, state)
    return int(sub["quests"][code])


def claim_quest(account: Account, event_id: str, code: str) -> bool:
    """Mark a quest as claimed (idempotent). Returns True on first claim."""
    state = _state(account)
    sub = _event_substate(state, event_id)
    if code in sub["claimed_quests"]:
        return False
    sub["claimed_quests"].append(code)
    _save_state(account, state)
    return True


def is_claimed(account: Account, event_id: str, code: str) -> bool:
    sub = _state(account).get(event_id) or {}
    return code in (sub.get("claimed_quests") or [])


def redeem_milestone(account: Account, event_id: str, idx: int) -> bool:
    """Mark a milestone redeemed (idempotent). Returns True on first redeem."""
    state = _state(account)
    sub = _event_substate(state, event_id)
    if idx in sub["redeemed_milestones"]:
        return False
    sub["redeemed_milestones"].append(int(idx))
    _save_state(account, state)
    return True


def redeemed_milestones(account: Account, event_id: str) -> list[int]:
    sub = _state(account).get(event_id) or {}
    return list(sub.get("redeemed_milestones") or [])


# --- Activity hook (drops + quest advance in one call) -----------------------


# Quest kinds are short strings the spec uses to describe what an activity
# advances. Keep this in sync with the spec format docs in events/README.md.
QUEST_KINDS_BATTLE_WIN = ("WIN_BATTLES",)
QUEST_KINDS_SUMMON = ("SUMMON_PULLS",)
QUEST_KINDS_ARENA = ("ARENA_ATTACKS",)
QUEST_KINDS_RAID = ("RAID_ATTACKS",)
QUEST_KINDS_GUILD_MSG = ("GUILD_MESSAGES",)


def on_activity(
    db: Session,
    account: Account,
    activity: str,
    *,
    amount: int = 1,
    quest_kinds: Iterable[str] = (),
) -> dict[str, int] | None:
    """Single hook fired by routers when a tracked activity completes.

    Looks up the active event spec; if any of its `drops` matches `activity`,
    the player gets that much event currency. Quest progress is advanced for
    every spec quest whose `kind` is in `quest_kinds`.

    Returns a dict {currency, quests_advanced} on a hit, else None.
    """
    spec = active_event_spec()
    if spec is None:
        return None

    # Cross-check the LiveOpsEvent row exists (i.e. activate_event.py was run).
    # Specs without an active LiveOpsEvent are pre-staged, not live.
    live = db.scalar(
        select(LiveOpsEvent).where(
            LiveOpsEvent.starts_at <= utcnow(),
            LiveOpsEvent.ends_at > utcnow(),
        )
    )
    if live is None:
        return None

    out: dict[str, int] = {}
    drop_amount = int(spec.drops.get(activity, 0)) * max(1, amount)
    if drop_amount > 0:
        out["currency"] = grant_currency(account, spec.id, drop_amount)

    advanced = 0
    for q in spec.quests:
        if q.get("kind") in quest_kinds:
            advance_quest(account, spec.id, q["code"], amount=amount)
            advanced += 1
    if advanced:
        out["quests_advanced"] = advanced

    return out or None
