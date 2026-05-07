# Arena Tickets, Drip Rewards, Weekly Payout, and Countdowns Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a per-day arena ticket resource, drip rewards on each attack, a weekly leaderboard payout, and live countdown timers for energy + arena tickets + daily reset.

**Architecture:** Mirror the existing energy regen pattern (`energy_stored` + `energy_last_tick_at`) for arena tickets. Add a new `ArenaWeeklyPayout` table with `(week_key, account_id)` PK as an idempotency lock. Lazily distribute payouts on `/me` hits; client-side ticking via a `useCountdown` hook.

**Tech Stack:** FastAPI · SQLAlchemy 2.x · Alembic · React · React Query · TypeScript · Vitest · pytest

**Spec:** `docs/superpowers/specs/2026-05-06-arena-tickets-and-countdowns-design.md`

---

## File Structure

**Backend — new files:**
- `app/arena_constants.py` — reward tables, payout brackets, frame code constant
- `app/arena_payout.py` — week-key helpers, `distribute_pending`, `reset_weekly_counter_if_stale`
- `alembic/versions/a4e1c5d2b8f9_arena_tickets_and_weekly_payouts.py` — schema migration
- `tests/test_arena_economy.py` — ticket regen, drip rewards, attack-endpoint gating
- `tests/test_arena_payout.py` — distributor, idempotency, payout brackets, week reset

**Backend — modified files:**
- `app/models.py` — Account fields + `ArenaWeeklyPayout` ORM class
- `app/config.py` — `arena_tickets_cap`, `arena_tickets_regen_seconds` settings
- `app/economy.py` — `compute_arena_tickets`, `consume_arena_ticket`, `seconds_until_next_energy`, `seconds_until_next_ticket`
- `app/schemas.py` — `MeOut` new fields, `ArenaMatchOut.rewards`, `PendingArenaReward` BaseModel
- `app/routers/arena.py` — ticket gate + drip + weekly counter increment + `/weekly/acknowledge` endpoint
- `app/routers/me.py` — flush regen + call distributor + return new fields

**Frontend — new files:**
- `frontend/src/hooks/useCountdown.ts` — generic countdown hook
- `frontend/src/hooks/useDailyResetCountdown.ts` — midnight UTC countdown
- `frontend/src/components/Arena/TicketHeader.tsx` — arena ticket count + timer
- `frontend/src/components/Me/RecurringResources.tsx` — full timer panel
- `frontend/src/components/PendingArenaReward.tsx` — weekly payout modal
- `frontend/src/test/useCountdown.test.ts`
- `frontend/src/test/useDailyResetCountdown.test.ts`

**Frontend — modified files:**
- `frontend/src/types/index.ts` — `Me` new fields, `ArenaMatch.rewards`
- `frontend/src/components/Layout/CurrencyBar.tsx` — inline timers
- `frontend/src/api/arena.ts` (or wherever attack lives) — return rewards in match shape
- `frontend/src/routes/Arena.tsx` — embed `TicketHeader`, gate attack buttons
- `frontend/src/routes/Me.tsx` — embed `RecurringResources`
- `frontend/src/components/Layout/Shell.tsx` — embed `<PendingArenaReward />`

---

## Task 1: Schema Migration — New Account Columns + ArenaWeeklyPayout Table

**Files:**
- Create: `alembic/versions/a4e1c5d2b8f9_arena_tickets_and_weekly_payouts.py`

- [ ] **Step 1: Create the migration file**

```python
"""arena_tickets_and_weekly_payouts

Revision ID: a4e1c5d2b8f9
Revises: db7eac125e36
Create Date: 2026-05-06 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a4e1c5d2b8f9'
down_revision: Union[str, Sequence[str], None] = 'db7eac125e36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'accounts',
        sa.Column('arena_tickets_stored', sa.Integer(), nullable=False, server_default='5'),
    )
    op.add_column(
        'accounts',
        sa.Column('arena_tickets_last_tick_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.add_column(
        'accounts',
        sa.Column('arena_weekly_wins', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'accounts',
        sa.Column('arena_weekly_key', sa.String(length=10), nullable=False, server_default=''),
    )

    op.create_table(
        'arena_weekly_payouts',
        sa.Column('week_key', sa.String(length=10), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('gems', sa.Integer(), nullable=False),
        sa.Column('eligible_wins', sa.Integer(), nullable=False),
        sa.Column('granted_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('week_key', 'account_id'),
    )
    op.create_index(
        'ix_arena_weekly_payouts_account_id',
        'arena_weekly_payouts',
        ['account_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_arena_weekly_payouts_account_id', table_name='arena_weekly_payouts')
    op.drop_table('arena_weekly_payouts')
    op.drop_column('accounts', 'arena_weekly_key')
    op.drop_column('accounts', 'arena_weekly_wins')
    op.drop_column('accounts', 'arena_tickets_last_tick_at')
    op.drop_column('accounts', 'arena_tickets_stored')
```

- [ ] **Step 2: Run migration up + down + up to verify roundtrip**

Run: `cd C:/Users/User/.claude/mmorpg/hero-proto && uv run alembic upgrade head`
Expected: migration applies cleanly, `INFO ... -> a4e1c5d2b8f9, arena_tickets_and_weekly_payouts`

Run: `uv run alembic downgrade -1`
Expected: cleanly reverses to `db7eac125e36`.

Run: `uv run alembic upgrade head`
Expected: re-applies cleanly.

- [ ] **Step 3: Commit**

```bash
git add alembic/versions/a4e1c5d2b8f9_arena_tickets_and_weekly_payouts.py
git commit -m "feat(arena): migration — ticket columns + arena_weekly_payouts table"
```

---

## Task 2: Account Model Fields + ArenaWeeklyPayout ORM Class

**Files:**
- Modify: `app/models.py`

- [ ] **Step 1: Add the four new columns to `class Account`**

Find the section near `energy_stored` / `energy_last_tick_at` (around line 201). Add immediately after the existing `pulls_since_epic` column or grouped with `arena_rating` / `arena_wins` / `arena_losses` (whichever block reads cleanest):

```python
    # Arena tickets — gate on attacks. Mirrors the energy regen pattern.
    arena_tickets_stored: Mapped[int] = mapped_column(Integer, default=5)
    arena_tickets_last_tick_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)

    # Weekly arena counter — resets at the ISO week boundary. Used by the
    # leaderboard payout distributor to filter parked accounts (must have
    # at least 1 win this week to be eligible for top-50 rewards).
    arena_weekly_wins: Mapped[int] = mapped_column(Integer, default=0)
    arena_weekly_key: Mapped[str] = mapped_column(String(10), default="")
```

- [ ] **Step 2: Add the new `ArenaWeeklyPayout` model**

At the end of `app/models.py` (after the last existing class), add:

```python
class ArenaWeeklyPayout(Base):
    """Idempotent ledger of weekly arena leaderboard payouts.

    Compound PK (week_key, account_id) is the idempotency lock — re-running
    the distributor for the same week is a no-op via INSERT ... ON CONFLICT
    DO NOTHING (or its driver-equivalent path).

    `acknowledged_at` is set when the player clicks "Claim" on the modal.
    Frontend uses null-acknowledged rows to populate `pending_arena_rewards`
    on `/me`.
    """
    __tablename__ = "arena_weekly_payouts"

    week_key: Mapped[str] = mapped_column(String(10), primary_key=True)
    account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    rank: Mapped[int] = mapped_column(Integer)
    gems: Mapped[int] = mapped_column(Integer)
    eligible_wins: Mapped[int] = mapped_column(Integer)
    granted_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
```

Make sure `String`, `Integer`, `DateTime`, `ForeignKey`, `Mapped`, `mapped_column`, `Base`, `utcnow` are already imported at the top of the file (they are — used by the existing `Quest`/`AccountQuest` models).

- [ ] **Step 3: Run pytest to confirm the model imports cleanly**

Run: `cd C:/Users/User/.claude/mmorpg/hero-proto && uv run pytest tests/test_arena.py -x -q`
Expected: existing arena tests still pass (no schema-related import errors).

- [ ] **Step 4: Commit**

```bash
git add app/models.py
git commit -m "feat(arena): Account ticket fields + ArenaWeeklyPayout model"
```

---

## Task 3: Configuration Constants

**Files:**
- Modify: `app/config.py`
- Create: `app/arena_constants.py`

- [ ] **Step 1: Add settings to `app/config.py`**

Find the existing `energy_cap: int = 100` / `energy_regen_seconds: int = 360` lines (around line 194). Add immediately after:

```python
    arena_tickets_cap: int = 5
    arena_tickets_regen_seconds: int = 14400  # 4 hours
```

- [ ] **Step 2: Create `app/arena_constants.py`**

```python
"""Constants for arena rewards and weekly leaderboard payouts.

Kept separate from config.Settings because these are flat tables, not
tunable knobs. Editing values here is a balance change requiring a code
review, not an environment-variable override.
"""
from __future__ import annotations

ARENA_REWARDS: dict[str, dict[str, int]] = {
    "win":  {"coins": 75, "shards": 3, "gems": 5},
    "loss": {"coins": 25, "shards": 0, "gems": 0},
    "draw": {"coins": 25, "shards": 0, "gems": 0},
}

# ±20% jitter on the coin reward only (matches stage-clear coin variance).
ARENA_REWARD_JITTER: float = 0.20

# (rank_lo, rank_hi, gems) — top 50 paid out at the Monday 00:00 UTC boundary.
ARENA_WEEKLY_PAYOUT: list[tuple[int, int, int]] = [
    (1, 1, 500),
    (2, 5, 250),
    (6, 20, 100),
    (21, 50, 50),
]

# Cosmetic frame granted to rank 1 only (idempotent — already-held is a no-op).
ARENA_CHAMPION_FRAME: str = "arena_champion"
```

- [ ] **Step 3: Commit**

```bash
git add app/config.py app/arena_constants.py
git commit -m "feat(arena): config knobs + arena_constants module"
```

---

## Task 4: Economy Helpers — Ticket Regen + Seconds-Until-Next

**Files:**
- Modify: `app/economy.py`
- Create: `tests/test_arena_economy.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_arena_economy.py`:

```python
"""Arena ticket regen helpers — pure-function tests."""
from __future__ import annotations

from datetime import timedelta

from app.config import settings
from app.economy import (
    compute_arena_tickets,
    consume_arena_ticket,
    seconds_until_next_energy,
    seconds_until_next_ticket,
)
from app.models import Account, utcnow


def _account(stored: int = 0, seconds_ago: int = 0) -> Account:
    a = Account(
        email="t@t",
        password_hash="x",
        coins=0,
        gems=0,
        shards=0,
        arena_tickets_stored=stored,
        arena_tickets_last_tick_at=utcnow() - timedelta(seconds=seconds_ago),
    )
    return a


def test_compute_arena_tickets_below_cap_ticks_correctly():
    a = _account(stored=0, seconds_ago=settings.arena_tickets_regen_seconds * 2)
    assert compute_arena_tickets(a) == 2


def test_compute_arena_tickets_caps_at_max():
    a = _account(stored=3, seconds_ago=settings.arena_tickets_regen_seconds * 99)
    assert compute_arena_tickets(a) == settings.arena_tickets_cap


def test_compute_arena_tickets_at_cap_returns_cap_unchanged():
    a = _account(stored=settings.arena_tickets_cap, seconds_ago=10)
    assert compute_arena_tickets(a) == settings.arena_tickets_cap


def test_consume_arena_ticket_returns_false_at_zero():
    a = _account(stored=0, seconds_ago=0)
    assert consume_arena_ticket(a) is False
    assert a.arena_tickets_stored == 0


def test_consume_arena_ticket_decrements_on_success():
    a = _account(stored=3, seconds_ago=0)
    assert consume_arena_ticket(a) is True
    assert a.arena_tickets_stored == 2


def test_consume_arena_ticket_flushes_regen_first():
    # 1 stored, regen produces 2 more → consume → 2 left.
    a = _account(stored=1, seconds_ago=settings.arena_tickets_regen_seconds * 2)
    assert consume_arena_ticket(a) is True
    assert a.arena_tickets_stored == 2


def test_seconds_until_next_ticket_at_cap_is_zero():
    a = _account(stored=settings.arena_tickets_cap, seconds_ago=0)
    assert seconds_until_next_ticket(a) == 0


def test_seconds_until_next_ticket_below_cap():
    # Just ticked, so the full regen interval remains.
    a = _account(stored=0, seconds_ago=0)
    assert seconds_until_next_ticket(a) == settings.arena_tickets_regen_seconds


def test_seconds_until_next_ticket_partial():
    a = _account(stored=0, seconds_ago=settings.arena_tickets_regen_seconds // 4)
    expected = settings.arena_tickets_regen_seconds - settings.arena_tickets_regen_seconds // 4
    # Allow ±2 seconds of clock slop.
    assert abs(seconds_until_next_ticket(a) - expected) <= 2


def test_seconds_until_next_energy_at_cap_is_zero():
    a = Account(
        email="e@e", password_hash="x", coins=0, gems=0, shards=0,
        energy_stored=settings.energy_cap,
        energy_last_tick_at=utcnow(),
    )
    assert seconds_until_next_energy(a) == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd C:/Users/User/.claude/mmorpg/hero-proto && uv run pytest tests/test_arena_economy.py -v`
Expected: FAIL — `ImportError: cannot import name 'compute_arena_tickets' from 'app.economy'`

- [ ] **Step 3: Add the helpers to `app/economy.py`**

Append after the existing `consume_energy` function (around line 44):

```python
# --- Arena tickets ----------------------------------------------------------


def compute_arena_tickets(account: Account, now: datetime | None = None) -> int:
    """Mirror of compute_energy: flushes regen, returns current ticket count.

    Read-only by intent — does NOT mutate the account. Use consume_arena_ticket
    when actually spending one (it flushes + spends + persists the new
    last_tick_at).
    """
    now = now or utcnow()
    elapsed = (now - account.arena_tickets_last_tick_at).total_seconds()
    if elapsed < 0:
        elapsed = 0
    gained = int(elapsed // settings.arena_tickets_regen_seconds)
    if account.arena_tickets_stored >= settings.arena_tickets_cap:
        return account.arena_tickets_stored
    return min(settings.arena_tickets_cap, account.arena_tickets_stored + gained)


def consume_arena_ticket(account: Account, now: datetime | None = None) -> bool:
    """Atomically flush regen + spend 1 ticket. Returns False if at 0.

    On success, also realigns last_tick_at so partial-regen accumulation
    isn't lost when we drop below cap.
    """
    now = now or utcnow()
    current = compute_arena_tickets(account, now)
    if current <= 0:
        # Refresh the snapshot so phantom tickets don't accumulate later.
        account.arena_tickets_stored = current
        account.arena_tickets_last_tick_at = now
        return False
    account.arena_tickets_stored = current - 1
    # Snap last_tick_at to now so the next regen interval is full-length.
    # This is intentional: spending mid-regen costs the partial accumulation,
    # same way energy works.
    account.arena_tickets_last_tick_at = now
    return True


def seconds_until_next_energy(account: Account, now: datetime | None = None) -> int:
    """Seconds remaining until the next +1 energy tick. Returns 0 at cap."""
    now = now or utcnow()
    if compute_energy(account, now) >= settings.energy_cap:
        return 0
    elapsed = (now - account.energy_last_tick_at).total_seconds()
    if elapsed < 0:
        elapsed = 0
    remainder = elapsed % settings.energy_regen_seconds
    return max(0, int(settings.energy_regen_seconds - remainder))


def seconds_until_next_ticket(account: Account, now: datetime | None = None) -> int:
    """Seconds remaining until the next +1 arena ticket. Returns 0 at cap."""
    now = now or utcnow()
    if compute_arena_tickets(account, now) >= settings.arena_tickets_cap:
        return 0
    elapsed = (now - account.arena_tickets_last_tick_at).total_seconds()
    if elapsed < 0:
        elapsed = 0
    remainder = elapsed % settings.arena_tickets_regen_seconds
    return max(0, int(settings.arena_tickets_regen_seconds - remainder))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_arena_economy.py -v`
Expected: PASS — all 9 tests green.

- [ ] **Step 5: Commit**

```bash
git add app/economy.py tests/test_arena_economy.py
git commit -m "feat(arena): ticket regen helpers + seconds-until-next math"
```

---

## Task 5: Week-Key Helpers + Per-Account Counter Reset

**Files:**
- Create: `app/arena_payout.py`
- Create: `tests/test_arena_payout.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_arena_payout.py`:

```python
"""Arena weekly payout distributor — week-key math, reset, distribution."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.arena_payout import (
    current_week_key,
    previous_week_key,
    reset_weekly_counter_if_stale,
)
from app.models import Account, utcnow


def test_current_week_key_format_iso():
    # 2026-01-05 is a Monday → ISO week 2 of 2026.
    d = datetime(2026, 1, 5, 12, 0, tzinfo=timezone.utc)
    assert current_week_key(d) == "2026-W02"


def test_current_week_key_year_boundary():
    # 2026-01-01 (Thursday) is still ISO week 1 of 2026.
    d = datetime(2026, 1, 1, 12, 0, tzinfo=timezone.utc)
    assert current_week_key(d) == "2026-W01"


def test_previous_week_key_simple():
    d = datetime(2026, 1, 12, 0, 0, tzinfo=timezone.utc)  # ISO week 3
    assert previous_week_key(d) == "2026-W02"


def test_previous_week_key_year_rollover():
    d = datetime(2026, 1, 5, 0, 0, tzinfo=timezone.utc)  # ISO week 2 → prev = W01 of 2026
    assert previous_week_key(d) == "2026-W01"


def test_reset_weekly_counter_if_stale_zeros_wins_and_bumps_key():
    a = Account(email="r@r", password_hash="x", coins=0, gems=0, shards=0,
                arena_weekly_wins=7, arena_weekly_key="2026-W01")
    now = datetime(2026, 1, 12, 0, 0, tzinfo=timezone.utc)  # week 3
    reset_weekly_counter_if_stale(a, now)
    assert a.arena_weekly_wins == 0
    assert a.arena_weekly_key == "2026-W03"


def test_reset_weekly_counter_no_op_within_same_week():
    a = Account(email="r@r", password_hash="x", coins=0, gems=0, shards=0,
                arena_weekly_wins=4, arena_weekly_key="2026-W03")
    now = datetime(2026, 1, 14, 0, 0, tzinfo=timezone.utc)  # still week 3
    reset_weekly_counter_if_stale(a, now)
    assert a.arena_weekly_wins == 4
    assert a.arena_weekly_key == "2026-W03"


def test_reset_weekly_counter_initializes_empty_key():
    a = Account(email="r@r", password_hash="x", coins=0, gems=0, shards=0,
                arena_weekly_wins=0, arena_weekly_key="")
    now = datetime(2026, 1, 12, 0, 0, tzinfo=timezone.utc)
    reset_weekly_counter_if_stale(a, now)
    assert a.arena_weekly_key == "2026-W03"
    assert a.arena_weekly_wins == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_arena_payout.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.arena_payout'`

- [ ] **Step 3: Create `app/arena_payout.py` with week-key helpers + reset**

```python
"""Arena weekly leaderboard payout — distributor, week-key math, reset.

The distributor is intentionally lazy: it runs on `/me` hits via
`distribute_pending(db)`. Idempotency is enforced by the
`(week_key, account_id)` composite primary key on `arena_weekly_payouts`.
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.arena_constants import (
    ARENA_CHAMPION_FRAME,
    ARENA_WEEKLY_PAYOUT,
)
from app.models import Account, ArenaWeeklyPayout, utcnow


def current_week_key(now: datetime | None = None) -> str:
    """ISO week key, e.g. '2026-W19'. Always uses the date's ISO calendar."""
    n = now or utcnow()
    iso_year, iso_week, _ = n.isocalendar()
    return f"{iso_year:04d}-W{iso_week:02d}"


def previous_week_key(now: datetime | None = None) -> str:
    """Week key for 7 days before `now`. Subtracting a week and re-keying is
    safer than week_number - 1 (which breaks across year boundaries)."""
    from datetime import timedelta as _td
    n = now or utcnow()
    return current_week_key(n - _td(days=7))


def reset_weekly_counter_if_stale(account: Account, now: datetime | None = None) -> None:
    """Bump the per-account weekly key + zero its wins counter if the stored
    key is stale or empty. Cheap (string compare) — call freely.
    """
    key = current_week_key(now)
    if account.arena_weekly_key != key:
        account.arena_weekly_wins = 0
        account.arena_weekly_key = key
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_arena_payout.py -v`
Expected: PASS — all 7 week-key/reset tests green.

- [ ] **Step 5: Commit**

```bash
git add app/arena_payout.py tests/test_arena_payout.py
git commit -m "feat(arena): week-key helpers + per-account counter reset"
```

---

## Task 6: Distributor — `distribute_pending`

**Files:**
- Modify: `app/arena_payout.py`
- Modify: `tests/test_arena_payout.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_arena_payout.py`:

```python
def _make_account(db, email, rating, weekly_wins, weekly_key):
    from app.models import Account
    from app.security import hash_password
    a = Account(
        email=email,
        password_hash=hash_password("hunter22"),
        coins=0, gems=0, shards=0,
        arena_rating=rating,
        arena_weekly_wins=weekly_wins,
        arena_weekly_key=weekly_key,
    )
    db.add(a)
    db.flush()
    return a


def test_distribute_pending_pays_top_50_by_rating(client):
    """Distributor ranks accounts by arena_rating and pays per bracket."""
    from app.db import SessionLocal
    from app.arena_payout import distribute_pending, previous_week_key
    from datetime import timezone

    # Pin "now" to a Monday so previous_week is unambiguous.
    now = datetime(2026, 1, 12, 0, 30, tzinfo=timezone.utc)  # week 3
    prev_key = previous_week_key(now)

    db = SessionLocal()
    try:
        # 4 accounts with different ratings, all eligible (1+ weekly_wins last week).
        a1 = _make_account(db, "rank1@x", 2000, 5, prev_key)
        a2 = _make_account(db, "rank2@x", 1800, 3, prev_key)
        a3 = _make_account(db, "rank3@x", 1600, 1, prev_key)
        # Ineligible: rating high but 0 wins.
        a4 = _make_account(db, "rank4@x", 1900, 0, prev_key)
        db.commit()

        n = distribute_pending(db, now)
        assert n == 3  # only the 3 eligible accounts paid

        db.refresh(a1)
        db.refresh(a2)
        db.refresh(a3)
        db.refresh(a4)
        # Rank 1 → 500 gems; rank 2-5 → 250; rank 6-20 → 100; rank 21-50 → 50
        assert a1.gems == 500
        assert a2.gems == 250
        assert a3.gems == 250  # rank 3 falls in 2-5 bracket
        assert a4.gems == 0  # ineligible
    finally:
        db.close()


def test_distribute_pending_idempotent(client):
    """Running the distributor twice for the same week is a no-op the second time."""
    from app.db import SessionLocal
    from app.arena_payout import distribute_pending, previous_week_key
    from datetime import timezone

    now = datetime(2026, 1, 12, 0, 30, tzinfo=timezone.utc)
    prev_key = previous_week_key(now)
    db = SessionLocal()
    try:
        _make_account(db, "idemp@x", 2000, 5, prev_key)
        db.commit()
        first = distribute_pending(db, now)
        second = distribute_pending(db, now)
        assert first == 1
        assert second == 0
    finally:
        db.close()


def test_distribute_pending_grants_champion_frame_to_rank_1(client):
    from app.db import SessionLocal
    from app.arena_payout import distribute_pending, previous_week_key
    from app.arena_constants import ARENA_CHAMPION_FRAME
    from datetime import timezone

    now = datetime(2026, 1, 12, 0, 30, tzinfo=timezone.utc)
    prev_key = previous_week_key(now)
    db = SessionLocal()
    try:
        a1 = _make_account(db, "champ@x", 2500, 7, prev_key)
        a2 = _make_account(db, "second@x", 2400, 5, prev_key)
        db.commit()
        distribute_pending(db, now)
        db.refresh(a1)
        db.refresh(a2)
        a1_frames = json.loads(a1.cosmetic_frames_json or "[]")
        a2_frames = json.loads(a2.cosmetic_frames_json or "[]")
        assert ARENA_CHAMPION_FRAME in a1_frames
        assert ARENA_CHAMPION_FRAME not in a2_frames
    finally:
        db.close()
```

(Add `import json` at the top of the test file.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_arena_payout.py -v`
Expected: FAIL — `ImportError: cannot import name 'distribute_pending'`.

- [ ] **Step 3: Add `distribute_pending` to `app/arena_payout.py`**

Append:

```python
def _gems_for_rank(rank: int) -> int:
    """Map a 1-indexed rank to gems via ARENA_WEEKLY_PAYOUT brackets. 0 if unranked."""
    for lo, hi, gems in ARENA_WEEKLY_PAYOUT:
        if lo <= rank <= hi:
            return gems
    return 0


def _max_paid_rank() -> int:
    return max(hi for _, hi, _ in ARENA_WEEKLY_PAYOUT)


def distribute_pending(db: Session, now: datetime | None = None) -> int:
    """Distribute prior-week payouts. Returns count of new payout rows inserted.

    Idempotent: if any ArenaWeeklyPayout row exists for the prior week, this
    is a no-op (returns 0).

    Algorithm:
      1. Compute previous_week_key from `now`.
      2. Check existing rows for that week_key — if any, return 0.
      3. Snapshot top-N (N = max paid rank) accounts by arena_rating where
         arena_weekly_wins >= 1 AND arena_weekly_key == previous_week_key.
      4. For each, INSERT ArenaWeeklyPayout, credit gems, grant champion frame
         to rank 1 if not already held.
      5. Commit.
    """
    n = now or utcnow()
    prev_key = previous_week_key(n)

    # Idempotency check: if any payout row exists for prev_key, bail.
    existing = db.execute(
        select(ArenaWeeklyPayout.account_id)
        .where(ArenaWeeklyPayout.week_key == prev_key)
        .limit(1)
    ).first()
    if existing is not None:
        return 0

    eligible = list(db.execute(
        select(Account)
        .where(
            Account.arena_weekly_wins >= 1,
            Account.arena_weekly_key == prev_key,
        )
        .order_by(Account.arena_rating.desc(), Account.id.asc())
        .limit(_max_paid_rank())
    ).scalars())

    inserted = 0
    for idx, account in enumerate(eligible):
        rank = idx + 1
        gems = _gems_for_rank(rank)
        if gems == 0:
            continue
        payout = ArenaWeeklyPayout(
            week_key=prev_key,
            account_id=account.id,
            rank=rank,
            gems=gems,
            eligible_wins=account.arena_weekly_wins,
        )
        db.add(payout)
        try:
            db.flush()
        except IntegrityError:
            # Another caller raced us. Roll back this row only and continue.
            db.rollback()
            continue
        account.gems = (account.gems or 0) + gems
        if rank == 1:
            try:
                frames = json.loads(account.cosmetic_frames_json or "[]")
            except json.JSONDecodeError:
                frames = []
            if ARENA_CHAMPION_FRAME not in frames:
                frames.append(ARENA_CHAMPION_FRAME)
                account.cosmetic_frames_json = json.dumps(frames)
        inserted += 1

    db.commit()
    return inserted
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_arena_payout.py -v`
Expected: PASS — all distributor tests green.

- [ ] **Step 5: Commit**

```bash
git add app/arena_payout.py tests/test_arena_payout.py
git commit -m "feat(arena): distribute_pending — idempotent weekly payout"
```

---

## Task 7: Schemas — Update `MeOut`, `ArenaMatchOut`, Add `PendingArenaReward`

**Files:**
- Modify: `app/schemas.py`

- [ ] **Step 1: Add `PendingArenaReward` near other Arena schemas**

Find `class ArenaLeaderboardEntry(BaseModel):` (around line 229). Add after it:

```python
class PendingArenaReward(BaseModel):
    """Unacknowledged weekly arena payout. Cleared by /arena/weekly/acknowledge."""
    week_key: str
    rank: int
    gems: int
```

- [ ] **Step 2: Add the new fields to `MeOut`**

Find `class MeOut(BaseModel):` (around line 69). Add to the body, after `energy_cap`:

```python
    energy_next_tick_in: int = 0
    arena_tickets: int = 0
    arena_tickets_cap: int = 0
    arena_tickets_next_tick_in: int = 0
    arena_weekly_wins: int = 0
    pending_arena_rewards: list[PendingArenaReward] = []
```

- [ ] **Step 3: Add `rewards` field to `ArenaMatchOut`**

Find `class ArenaMatchOut(BaseModel):`. Add to the body:

```python
    rewards: dict[str, int] = {}  # {"coins": 75, "shards": 3, "gems": 5}
```

- [ ] **Step 4: Run import smoke check**

Run: `uv run python -c "from app.schemas import MeOut, ArenaMatchOut, PendingArenaReward; print('ok')"`
Expected: prints `ok`.

- [ ] **Step 5: Commit**

```bash
git add app/schemas.py
git commit -m "feat(arena): schema fields for tickets, rewards, weekly payouts"
```

---

## Task 8: Wire Ticket Gate + Drip Rewards into `/arena/attack`

**Files:**
- Modify: `app/routers/arena.py`
- Modify: `tests/test_arena_economy.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_arena_economy.py`:

```python
def _register(client, email):
    r = client.post("/auth/register", json={"email": email, "password": "hunter22"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _setup_attacker_and_defender(client, prefix):
    """Returns (atk_hdr, def_id, atk_team)."""
    import random
    def_email = f"{prefix}-def-{random.randint(100000, 999999)}@x"
    def_hdr = _register(client, def_email)
    client.post("/summon/x10", headers=def_hdr)
    def_roster = sorted(
        client.get("/heroes/mine", headers=def_hdr).json(),
        key=lambda h: h["power"], reverse=True,
    )
    def_team = [h["id"] for h in def_roster[:3]]
    def_id = client.get("/me", headers=def_hdr).json()["id"]
    client.put("/arena/defense", json={"team": def_team}, headers=def_hdr)

    atk_email = f"{prefix}-atk-{random.randint(100000, 999999)}@x"
    atk_hdr = _register(client, atk_email)
    client.post("/summon/x10", headers=atk_hdr)
    atk_roster = sorted(
        client.get("/heroes/mine", headers=atk_hdr).json(),
        key=lambda h: h["power"], reverse=True,
    )
    atk_team = [h["id"] for h in atk_roster[:3]]
    return atk_hdr, def_id, atk_team


def test_arena_attack_returns_429_when_no_tickets(client):
    from app.db import SessionLocal
    from app.models import Account
    atk_hdr, def_id, atk_team = _setup_attacker_and_defender(client, "tix")
    me = client.get("/me", headers=atk_hdr).json()

    # Drain tickets directly via DB.
    db = SessionLocal()
    try:
        a = db.get(Account, me["id"])
        a.arena_tickets_stored = 0
        a.arena_tickets_last_tick_at = utcnow()
        db.commit()
    finally:
        db.close()

    r = client.post(
        "/arena/attack",
        json={"defender_account_id": def_id, "team": atk_team},
        headers=atk_hdr,
    )
    assert r.status_code == 429, r.text
    assert "Retry-After" in r.headers


def test_arena_attack_drips_rewards(client):
    """Attacker receives coins/shards/gems based on outcome."""
    atk_hdr, def_id, atk_team = _setup_attacker_and_defender(client, "drip")
    me_before = client.get("/me", headers=atk_hdr).json()

    r = client.post(
        "/arena/attack",
        json={"defender_account_id": def_id, "team": atk_team},
        headers=atk_hdr,
    )
    assert r.status_code == 201
    match = r.json()
    assert "rewards" in match
    assert match["rewards"]["coins"] >= 20  # loss=25 ±20%, win=75 ±20% — both above 20

    me_after = client.get("/me", headers=atk_hdr).json()
    assert me_after["coins"] >= me_before["coins"] + match["rewards"]["coins"]
    assert me_after["shards"] >= me_before["shards"] + match["rewards"]["shards"]
    assert me_after["gems"] >= me_before["gems"] + match["rewards"]["gems"]


def test_arena_attack_decrements_tickets(client):
    atk_hdr, def_id, atk_team = _setup_attacker_and_defender(client, "decr")
    before = client.get("/me", headers=atk_hdr).json()["arena_tickets"]

    r = client.post(
        "/arena/attack",
        json={"defender_account_id": def_id, "team": atk_team},
        headers=atk_hdr,
    )
    assert r.status_code == 201

    after = client.get("/me", headers=atk_hdr).json()["arena_tickets"]
    assert after == before - 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_arena_economy.py -v`
Expected: FAIL — endpoint either ignores tickets (test_arena_attack_returns_429 fails: got 201) or doesn't return rewards (KeyError).

- [ ] **Step 3: Update `app/routers/arena.py` `attack` endpoint**

Add imports near the top:

```python
import random as _rng_module

from app.arena_constants import ARENA_REWARDS, ARENA_REWARD_JITTER
from app.arena_payout import reset_weekly_counter_if_stale
from app.economy import consume_arena_ticket, seconds_until_next_ticket
```

Replace the attack endpoint signature + body (around line 227) — these are surgical edits, keep the existing simulate / rating / persistence code:

After the line `if dt is None: raise HTTPException(...)` (the defender team check, around line 240), and **before** `attackers = _load_heroes(...)`:

```python
    # Ticket gate — game economy resource (separate from anti-spam rate limit).
    if not consume_arena_ticket(account):
        retry_after = max(1, seconds_until_next_ticket(account))
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"out of arena tickets — next in {retry_after}s",
            headers={"Retry-After": str(retry_after)},
        )
```

After the existing rating-delta block (after `account.arena_rating = max(...)`, `defender.arena_rating = max(...)` ~line 293), and **before** `on_arena_attack(db, account)`:

```python
    # Drip rewards — outcome-driven, ±20% jitter on coins only.
    outcome_key = (
        "win" if result.outcome == BattleOutcome.WIN
        else "loss" if result.outcome == BattleOutcome.LOSS
        else "draw"
    )
    reward_set = ARENA_REWARDS[outcome_key]
    jitter_mult = 1.0 + rng.uniform(-ARENA_REWARD_JITTER, ARENA_REWARD_JITTER)
    coins = max(1, int(round(reward_set["coins"] * jitter_mult)))
    shards = reward_set["shards"]
    gems = reward_set["gems"]
    account.coins = (account.coins or 0) + coins
    account.shards = (account.shards or 0) + shards
    account.gems = (account.gems or 0) + gems
    rewards_out = {"coins": coins, "shards": shards, "gems": gems}

    # Weekly counter — increment only on wins, after stale-key reset so the
    # increment lands on the current week's bucket.
    if result.outcome == BattleOutcome.WIN:
        reset_weekly_counter_if_stale(account)
        account.arena_weekly_wins = (account.arena_weekly_wins or 0) + 1
```

Update the final `return ArenaMatchOut(...)` call to include the new field (find the existing return, append `rewards=rewards_out`):

```python
    return ArenaMatchOut(
        id=match.id,
        attacker_id=match.attacker_id,
        defender_id=match.defender_id,
        outcome=result.outcome,
        rating_delta=delta,
        attacker_rating_after=account.arena_rating,
        defender_rating_after=defender.arena_rating,
        log=result.log,
        participants=[BattleParticipant(**p) for p in participants],
        created_at=match.created_at,
        rewards=rewards_out,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_arena_economy.py tests/test_arena.py -v`
Expected: PASS — new tests green, existing arena tests still pass.

- [ ] **Step 5: Commit**

```bash
git add app/routers/arena.py tests/test_arena_economy.py
git commit -m "feat(arena): ticket gate + drip rewards on /arena/attack"
```

---

## Task 9: `/arena/weekly/acknowledge` Endpoint

**Files:**
- Modify: `app/routers/arena.py`
- Modify: `tests/test_arena_payout.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_arena_payout.py`:

```python
def test_acknowledge_marks_all_pending(client):
    """POST /arena/weekly/acknowledge sets acknowledged_at on unacknowledged rows."""
    from app.db import SessionLocal
    from app.models import Account, ArenaWeeklyPayout
    from sqlalchemy import select as _select

    # Register an account, then write a pending payout for it directly.
    r = client.post("/auth/register", json={"email": "ack@x", "password": "hunter22"})
    hdr = {"Authorization": f"Bearer {r.json()['access_token']}"}
    me_id = client.get("/me", headers=hdr).json()["id"]

    db = SessionLocal()
    try:
        db.add(ArenaWeeklyPayout(
            week_key="2026-W19",
            account_id=me_id,
            rank=3,
            gems=250,
            eligible_wins=4,
        ))
        db.commit()
    finally:
        db.close()

    # /me should surface it.
    me = client.get("/me", headers=hdr).json()
    assert len(me["pending_arena_rewards"]) == 1
    assert me["pending_arena_rewards"][0]["rank"] == 3

    # Acknowledge.
    r = client.post("/arena/weekly/acknowledge", headers=hdr)
    assert r.status_code == 200

    # /me should now report empty.
    me2 = client.get("/me", headers=hdr).json()
    assert me2["pending_arena_rewards"] == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_arena_payout.py::test_acknowledge_marks_all_pending -v`
Expected: FAIL — `405 Method Not Allowed` (endpoint doesn't exist) or `KeyError: 'pending_arena_rewards'` if /me isn't populated yet.

- [ ] **Step 3: Add the endpoint to `app/routers/arena.py`**

Add the import near the top (alongside other model imports):

```python
from app.models import ArenaWeeklyPayout
```

At the end of the router file, append:

```python
@router.post("/weekly/acknowledge", response_model=dict)
def acknowledge_weekly_rewards(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Mark all unacknowledged weekly arena payouts for this account as seen.

    Idempotent — re-calling with no pending rows returns {acknowledged: 0}.
    """
    rows = db.query(ArenaWeeklyPayout).filter(
        ArenaWeeklyPayout.account_id == account.id,
        ArenaWeeklyPayout.acknowledged_at.is_(None),
    ).all()
    now = utcnow()
    for r in rows:
        r.acknowledged_at = now
    db.commit()
    return {"acknowledged": len(rows)}
```

(Do not implement /me changes yet — Task 10 covers that. The test will still fail at the /me assertion until Task 10 lands.)

- [ ] **Step 4: Skip /me assertion verification until Task 10**

Run: `uv run pytest tests/test_arena_payout.py::test_acknowledge_marks_all_pending -v`
Expected: still FAIL on the /me assertion (`KeyError` or `pending_arena_rewards` is `[]` because /me doesn't yet populate it). This is expected — the endpoint is in place; /me wiring comes next.

- [ ] **Step 5: Commit**

```bash
git add app/routers/arena.py tests/test_arena_payout.py
git commit -m "feat(arena): POST /arena/weekly/acknowledge endpoint"
```

---

## Task 10: `/me` — Flush Regen, Run Distributor, Return New Fields

**Files:**
- Modify: `app/routers/me.py`

- [ ] **Step 1: Update the `/me` GET handler**

Add these imports at the top of `app/routers/me.py` (near the existing `from app.economy import compute_energy, load_cleared`):

```python
from app.arena_payout import distribute_pending, reset_weekly_counter_if_stale
from app.economy import (
    compute_arena_tickets,
    compute_energy,
    load_cleared,
    seconds_until_next_energy,
    seconds_until_next_ticket,
)
from app.models import Account, ArenaWeeklyPayout, Battle, Faction, Guild, GuildMember, GuildRole, HeroInstance, Purchase
```

(Existing `compute_energy` / `load_cleared` line is replaced by the expanded import above; existing `Account` etc. already imported.)

Insert at the start of the handler body, **after** the `import json as _json` line:

```python
    # Side effects on every /me hit (cheap):
    #   1. Reset per-account weekly counter if the ISO week rolled over.
    #   2. Run the global distributor — idempotent on (week_key) PK.
    reset_weekly_counter_if_stale(account)
    distribute_pending(db)
```

Replace the existing `MeOut(...)` constructor (around line 45). Find the existing call and add the new fields. The full updated return looks like:

```python
    pending_payouts = db.query(ArenaWeeklyPayout).filter(
        ArenaWeeklyPayout.account_id == account.id,
        ArenaWeeklyPayout.acknowledged_at.is_(None),
    ).all()
    pending_out = [
        {"week_key": p.week_key, "rank": p.rank, "gems": p.gems}
        for p in pending_payouts
    ]

    return MeOut(
        id=account.id,
        email=account.email,
        gems=account.gems,
        coins=account.coins,
        shards=account.shards,
        access_cards=account.access_cards,
        free_summon_credits=account.free_summon_credits or 0,
        energy=compute_energy(account),
        energy_cap=settings.energy_cap,
        energy_next_tick_in=seconds_until_next_energy(account),
        arena_tickets=compute_arena_tickets(account),
        arena_tickets_cap=settings.arena_tickets_cap,
        arena_tickets_next_tick_in=seconds_until_next_ticket(account),
        arena_weekly_wins=account.arena_weekly_wins or 0,
        pending_arena_rewards=pending_out,
        pulls_since_epic=account.pulls_since_epic,
        stages_cleared=sorted(cleared),
        tutorial_cleared="tutorial_first_ticket" in cleared,
        has_summoned=has_summoned,
        has_battled=has_battled,
        account_level=account.account_level or 1,
        account_xp=account.account_xp or 0,
        account_xp_to_next=_xp_to_next(account.account_level or 1),
        faction=Faction(account.faction) if not isinstance(account.faction, Faction) else account.faction,
        alignment_chosen_at=account.alignment_chosen_at,
        qol_unlocks=qol_codes,
        cosmetic_frames=frame_codes,
        active_cosmetic_frame=account.active_cosmetic_frame or "",
        arena_rating=account.arena_rating or 1000,
        arena_wins=account.arena_wins or 0,
        arena_losses=account.arena_losses or 0,
        hero_slot_cap=account.hero_slot_cap or 50,
        gear_slot_cap=account.gear_slot_cap or 200,
        is_admin=bool(account.is_admin),
        email_verified=bool(account.email_verified),
        totp_enabled=bool(account.totp_enabled),
    )
```

- [ ] **Step 2: Run the full backend test suite**

Run: `uv run pytest tests/test_arena_payout.py tests/test_arena_economy.py tests/test_arena.py tests/test_quests.py -v`
Expected: all PASS — including `test_acknowledge_marks_all_pending` which was waiting on /me wiring.

- [ ] **Step 3: Commit**

```bash
git add app/routers/me.py
git commit -m "feat(arena): /me flushes regen, runs distributor, returns ticket + payout fields"
```

---

## Task 11: Frontend — `useCountdown` and `useDailyResetCountdown` Hooks

**Files:**
- Create: `frontend/src/hooks/useCountdown.ts`
- Create: `frontend/src/hooks/useDailyResetCountdown.ts`
- Create: `frontend/src/test/useCountdown.test.ts`
- Create: `frontend/src/test/useDailyResetCountdown.test.ts`

- [ ] **Step 1: Write `useCountdown` failing tests**

Create `frontend/src/test/useCountdown.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useCountdown } from '../hooks/useCountdown'

describe('useCountdown', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('formats below 1 hour as M:SS', () => {
    const { result } = renderHook(() => useCountdown(222))  // 3:42
    expect(result.current).toBe('3:42')
  })

  it('formats above 1 hour as H:MM:SS', () => {
    const { result } = renderHook(() => useCountdown(8070))  // 2:14:30
    expect(result.current).toBe('2:14:30')
  })

  it('ticks down once per second', () => {
    const { result } = renderHook(() => useCountdown(10))
    expect(result.current).toBe('0:10')
    act(() => { vi.advanceTimersByTime(1000) })
    expect(result.current).toBe('0:09')
    act(() => { vi.advanceTimersByTime(3000) })
    expect(result.current).toBe('0:06')
  })

  it('returns 0:00 at zero and stops', () => {
    const { result } = renderHook(() => useCountdown(2))
    act(() => { vi.advanceTimersByTime(5000) })
    expect(result.current).toBe('0:00')
  })

  it('resets when source seconds change', () => {
    const { result, rerender } = renderHook(
      ({ s }: { s: number }) => useCountdown(s),
      { initialProps: { s: 60 } },
    )
    expect(result.current).toBe('1:00')
    act(() => { vi.advanceTimersByTime(10_000) })
    expect(result.current).toBe('0:50')
    rerender({ s: 300 })
    expect(result.current).toBe('5:00')
  })

  it('returns 0:00 immediately for non-positive input', () => {
    const { result } = renderHook(() => useCountdown(0))
    expect(result.current).toBe('0:00')
  })

  it('calls onZero exactly once when crossing to 0', () => {
    const onZero = vi.fn()
    renderHook(() => useCountdown(2, onZero))
    act(() => { vi.advanceTimersByTime(2500) })
    expect(onZero).toHaveBeenCalledTimes(1)
  })
})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd frontend && npx vitest run src/test/useCountdown.test.ts`
Expected: FAIL — `Cannot find module '../hooks/useCountdown'`.

- [ ] **Step 3: Implement `frontend/src/hooks/useCountdown.ts`**

```typescript
import { useEffect, useRef, useState } from 'react'

function format(seconds: number): string {
  if (seconds <= 0) return '0:00'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = seconds % 60
  if (h > 0) return `${h}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  return `${m}:${String(s).padStart(2, '0')}`
}

export function useCountdown(seconds: number, onZero?: () => void): string {
  const [remaining, setRemaining] = useState(Math.max(0, Math.floor(seconds)))
  const firedRef = useRef(false)

  useEffect(() => {
    setRemaining(Math.max(0, Math.floor(seconds)))
    firedRef.current = false
  }, [seconds])

  useEffect(() => {
    if (remaining <= 0) {
      if (!firedRef.current && onZero) {
        firedRef.current = true
        onZero()
      }
      return
    }
    const id = setInterval(() => {
      setRemaining(prev => Math.max(0, prev - 1))
    }, 1000)
    return () => clearInterval(id)
  }, [remaining, onZero])

  return format(remaining)
}
```

- [ ] **Step 4: Run useCountdown tests to verify they pass**

Run: `npx vitest run src/test/useCountdown.test.ts`
Expected: PASS — all 7 tests green.

- [ ] **Step 5: Write `useDailyResetCountdown` failing tests**

Create `frontend/src/test/useDailyResetCountdown.test.ts`:

```typescript
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useDailyResetCountdown } from '../hooks/useDailyResetCountdown'

describe('useDailyResetCountdown', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('returns time until next 00:00 UTC at noon UTC', () => {
    vi.setSystemTime(new Date('2026-05-06T12:00:00Z'))
    const { result } = renderHook(() => useDailyResetCountdown())
    expect(result.current).toBe('12:00:00')  // 12 hours
  })

  it('returns under-1h format when close to midnight', () => {
    vi.setSystemTime(new Date('2026-05-06T23:30:00Z'))
    const { result } = renderHook(() => useDailyResetCountdown())
    expect(result.current).toBe('30:00')  // 30 minutes
  })

  it('returns ~24h just after midnight UTC', () => {
    vi.setSystemTime(new Date('2026-05-06T00:00:30Z'))
    const { result } = renderHook(() => useDailyResetCountdown())
    // 23:59:30 remaining
    expect(result.current).toBe('23:59:30')
  })
})
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `npx vitest run src/test/useDailyResetCountdown.test.ts`
Expected: FAIL — module not found.

- [ ] **Step 7: Implement `frontend/src/hooks/useDailyResetCountdown.ts`**

```typescript
import { useCountdown } from './useCountdown'

function secondsUntilNextMidnightUTC(): number {
  const now = new Date()
  const tomorrow = new Date(Date.UTC(
    now.getUTCFullYear(),
    now.getUTCMonth(),
    now.getUTCDate() + 1,
    0, 0, 0, 0,
  ))
  return Math.floor((tomorrow.getTime() - now.getTime()) / 1000)
}

export function useDailyResetCountdown(): string {
  return useCountdown(secondsUntilNextMidnightUTC())
}
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `npx vitest run src/test/useDailyResetCountdown.test.ts`
Expected: PASS — all 3 tests green.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/hooks/useCountdown.ts frontend/src/hooks/useDailyResetCountdown.ts frontend/src/test/useCountdown.test.ts frontend/src/test/useDailyResetCountdown.test.ts
git commit -m "feat(frontend): useCountdown + useDailyResetCountdown hooks"
```

---

## Task 12: Update `Me` Type + CurrencyBar Inline Timers

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/components/Layout/CurrencyBar.tsx`

- [ ] **Step 1: Add new fields to `Me` interface**

In `frontend/src/types/index.ts`, find `interface Me { ... }` and add (after `energy_cap`):

```typescript
  energy_next_tick_in: number
  arena_tickets: number
  arena_tickets_cap: number
  arena_tickets_next_tick_in: number
  arena_weekly_wins: number
  pending_arena_rewards: PendingArenaReward[]
```

At the end of the file, add:

```typescript
export interface PendingArenaReward {
  week_key: string
  rank: number
  gems: number
}
```

- [ ] **Step 2: Update `CurrencyBar.tsx`**

Find the existing energy display block (around line 16-70). Add at the top of the component, after `me` is destructured:

```tsx
import { useCountdown } from '../../hooks/useCountdown'
```

Inside the component body, after `const energyColor = ...`:

```tsx
  const energyTimer = useCountdown(me.energy_next_tick_in)
  const ticketTimer = useCountdown(me.arena_tickets_next_tick_in)
  const showEnergyTimer = me.energy < me.energy_cap
  const showTicketTimer = me.arena_tickets < me.arena_tickets_cap
```

Find the existing `<span>⚡ {me.energy}/{me.energy_cap}</span>` line. Append a sibling timer span:

```tsx
        <span style={{ position: 'relative' }}>⚡ {me.energy}/{me.energy_cap}</span>
        {showEnergyTimer && (
          <span style={{ marginLeft: 6, color: 'var(--muted)', fontSize: 10 }}>
            +1 in {energyTimer}
          </span>
        )}
```

Add a parallel block for arena tickets next to it (in the same container as the energy block — use whatever existing layout pattern the file already has):

```tsx
      <span title={`${me.arena_tickets} of ${me.arena_tickets_cap} arena tickets`}>
        🎯 {me.arena_tickets}/{me.arena_tickets_cap}
        {showTicketTimer && (
          <span style={{ marginLeft: 6, color: 'var(--muted)', fontSize: 10 }}>
            +1 in {ticketTimer}
          </span>
        )}
      </span>
```

(Place this immediately after the energy span; adapt styling to match the existing `.currency-row` pattern.)

- [ ] **Step 3: Run frontend tests**

Run: `cd frontend && npx vitest run`
Expected: PASS — existing tests still green; new types/imports compile.

- [ ] **Step 4: Build to confirm no TS errors**

Run: `npm run build`
Expected: build completes cleanly.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/components/Layout/CurrencyBar.tsx
git commit -m "feat(frontend): inline energy + arena ticket countdowns in CurrencyBar"
```

---

## Task 13: Arena Page Ticket Header + Attack Button Gating

**Files:**
- Create: `frontend/src/components/Arena/TicketHeader.tsx`
- Modify: `frontend/src/routes/Arena.tsx` (or whichever route renders the arena UI)

- [ ] **Step 1: Create `TicketHeader.tsx`**

```tsx
import type { Me } from '../../types'
import { useCountdown } from '../../hooks/useCountdown'

interface Props {
  me: Pick<Me, 'arena_tickets' | 'arena_tickets_cap' | 'arena_tickets_next_tick_in'>
}

export function TicketHeader({ me }: Props) {
  const nextIn = useCountdown(me.arena_tickets_next_tick_in)
  const missing = Math.max(0, me.arena_tickets_cap - me.arena_tickets)
  const fullSeconds = missing === 0
    ? 0
    : me.arena_tickets_next_tick_in + Math.max(0, missing - 1) * (4 * 3600)
  const fullIn = useCountdown(fullSeconds)
  const atCap = me.arena_tickets >= me.arena_tickets_cap

  return (
    <div style={{
      padding: '10px 14px',
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 8,
      marginBottom: 12,
      fontSize: 13,
    }}>
      <div style={{ fontWeight: 700 }}>
        🎯 Tickets: {me.arena_tickets} / {me.arena_tickets_cap}
      </div>
      {!atCap && (
        <div style={{ color: 'var(--muted)', fontSize: 11, marginTop: 4 }}>
          Next ticket in {nextIn}
          {missing > 1 && <> · full in {fullIn}</>}
        </div>
      )}
      {atCap && (
        <div style={{ color: 'var(--good)', fontSize: 11, marginTop: 4 }}>
          Tickets full
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Embed `TicketHeader` in the arena route**

In the file that renders the arena opponents page (likely `frontend/src/routes/Arena.tsx`), add:

```tsx
import { TicketHeader } from '../components/Arena/TicketHeader'
```

Place `<TicketHeader me={me} />` near the top of the rendered content, above the opponents list. (Locate the existing me query usage — the route already fetches `me`.)

For each Attack button on opponent cards, gate it on tickets:

```tsx
const noTickets = (me?.arena_tickets ?? 0) <= 0
// ... on the button:
<button
  className="primary"
  disabled={noTickets || /* existing disable conditions */}
  title={noTickets ? 'Out of tickets — wait for regen' : undefined}
  onClick={...}
>
  Attack
</button>
```

- [ ] **Step 3: Build to confirm no TS errors**

Run: `cd frontend && npm run build`
Expected: build completes cleanly.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Arena/TicketHeader.tsx frontend/src/routes/Arena.tsx
git commit -m "feat(frontend): arena ticket header + attack button gating"
```

---

## Task 14: Recurring Resources Panel on Me Page

**Files:**
- Create: `frontend/src/components/Me/RecurringResources.tsx`
- Modify: `frontend/src/routes/Me.tsx`

- [ ] **Step 1: Create `RecurringResources.tsx`**

```tsx
import type { Me } from '../../types'
import { useCountdown } from '../../hooks/useCountdown'
import { useDailyResetCountdown } from '../../hooks/useDailyResetCountdown'

interface Props {
  me: Me
}

export function RecurringResources({ me }: Props) {
  const energyTimer = useCountdown(me.energy_next_tick_in)
  const ticketTimer = useCountdown(me.arena_tickets_next_tick_in)
  const dailyTimer = useDailyResetCountdown()
  const energyAtCap = me.energy >= me.energy_cap
  const ticketsAtCap = me.arena_tickets >= me.arena_tickets_cap

  const Row = ({ icon, label, value, timer, atCap }: {
    icon: string; label: string; value: string; timer: string; atCap: boolean
  }) => (
    <div style={{
      display: 'flex', alignItems: 'baseline', gap: 8, padding: '6px 0',
      fontSize: 13,
    }}>
      <span style={{ width: 100, color: 'var(--muted)' }}>{icon} {label}</span>
      <span style={{ width: 90, fontWeight: 600 }}>{value}</span>
      <span style={{ color: atCap ? 'var(--good)' : 'var(--muted)', fontSize: 11 }}>
        {atCap ? 'full' : `+1 in ${timer}`}
      </span>
    </div>
  )

  return (
    <div style={{
      padding: 14,
      background: 'var(--bg-card)',
      border: '1px solid var(--border)',
      borderRadius: 8,
      marginTop: 16,
    }}>
      <div style={{ fontWeight: 700, marginBottom: 8 }}>Recurring Resources</div>
      <Row icon="⚡" label="Energy" value={`${me.energy} / ${me.energy_cap}`}
           timer={energyTimer} atCap={energyAtCap} />
      <Row icon="🎯" label="Arena" value={`${me.arena_tickets} / ${me.arena_tickets_cap}`}
           timer={ticketTimer} atCap={ticketsAtCap} />
      <div style={{ display: 'flex', alignItems: 'baseline', gap: 8, padding: '6px 0', fontSize: 13 }}>
        <span style={{ width: 100, color: 'var(--muted)' }}>📅 Daily reset</span>
        <span style={{ width: 90 }}></span>
        <span style={{ color: 'var(--muted)', fontSize: 11 }}>in {dailyTimer}</span>
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Embed in `Me.tsx`**

In `frontend/src/routes/Me.tsx`, add:

```tsx
import { RecurringResources } from '../components/Me/RecurringResources'
```

Place `<RecurringResources me={me} />` near the existing currency / energy display block (find the section that renders currencies and add it directly below).

- [ ] **Step 3: Build**

Run: `cd frontend && npm run build`
Expected: clean build.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/Me/RecurringResources.tsx frontend/src/routes/Me.tsx
git commit -m "feat(frontend): RecurringResources panel on Me page"
```

---

## Task 15: Arena Match Result Rewards Display

**Files:**
- Modify: `frontend/src/api/arena.ts` (or wherever the `ArenaMatch` type lives)
- Modify: arena attack result rendering (likely `frontend/src/routes/Arena.tsx` or a result modal)

- [ ] **Step 1: Add `rewards` to the arena match TypeScript type**

Find the file that defines the arena attack response shape (search for `participants` and `rating_delta`). Add:

```typescript
export interface ArenaMatchRewards {
  coins: number
  shards: number
  gems: number
}

// In whichever interface has rating_delta + participants:
  rewards: ArenaMatchRewards
```

- [ ] **Step 2: Render the reward line in the result view**

Find where the arena attack result is rendered (search for `rating_delta` in `routes/`). Add below the existing rating display:

```tsx
{match.rewards && (
  <div style={{ marginTop: 6, color: 'var(--good)', fontSize: 13 }}>
    +{match.rewards.coins} coins
    {match.rewards.shards > 0 && <> · +{match.rewards.shards} shards</>}
    {match.rewards.gems > 0 && <> · +{match.rewards.gems} gems</>}
  </div>
)}
```

- [ ] **Step 3: Build**

Run: `cd frontend && npm run build`
Expected: clean build.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/api/arena.ts frontend/src/routes/Arena.tsx
git commit -m "feat(frontend): show arena drip rewards on attack result"
```

---

## Task 16: Pending Arena Reward Modal

**Files:**
- Create: `frontend/src/components/PendingArenaReward.tsx`
- Modify: `frontend/src/components/Layout/Shell.tsx`
- Modify: `frontend/src/api/arena.ts` (add `acknowledgeWeeklyRewards`)

- [ ] **Step 1: Add API function**

In `frontend/src/api/arena.ts` (or wherever arena API lives):

```typescript
import { apiPost } from './client'

export const acknowledgeWeeklyRewards = (): Promise<{ acknowledged: number }> =>
  apiPost('/arena/weekly/acknowledge', {})
```

- [ ] **Step 2: Create the modal component**

```tsx
import { useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { useAuthStore } from '../store/auth'
import { fetchMe } from '../api/me'
import { acknowledgeWeeklyRewards } from '../api/arena'
import { toast } from '../store/ui'

export function PendingArenaReward() {
  const jwt = useAuthStore(s => s.jwt)
  const qc = useQueryClient()
  const [acking, setAcking] = useState(false)

  const { data: me } = useQuery({
    queryKey: ['me'],
    queryFn: fetchMe,
    enabled: !!jwt,
  })

  const reward = me?.pending_arena_rewards?.[0]
  if (!jwt || !reward) return null

  const isChampion = reward.rank === 1

  async function handleClaim() {
    setAcking(true)
    try {
      await acknowledgeWeeklyRewards()
      qc.invalidateQueries({ queryKey: ['me'] })
    } catch (e) {
      toast.error(e instanceof Error ? e.message : 'Failed to claim')
    } finally {
      setAcking(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 500,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'rgba(0,0,0,0.6)',
    }}>
      <div style={{
        background: 'var(--bg-card)',
        border: `2px solid ${isChampion ? 'var(--warn)' : 'var(--accent)'}`,
        borderRadius: 12, padding: 24, minWidth: 320, maxWidth: '90vw',
        textAlign: 'center',
      }}>
        <div style={{ fontSize: 22, fontWeight: 700, marginBottom: 6 }}>
          🏆 Arena Week Complete
        </div>
        <div style={{ color: 'var(--muted)', marginBottom: 14 }}>
          You finished rank #{reward.rank} last week
        </div>
        <div style={{ fontSize: 28, fontWeight: 700, color: 'var(--gem)', marginBottom: 6 }}>
          +{reward.gems} gems
        </div>
        {isChampion && (
          <div style={{ fontSize: 13, color: 'var(--warn)', marginBottom: 12 }}>
            Cosmetic frame unlocked: Arena Champion
          </div>
        )}
        <button
          className="primary"
          disabled={acking}
          onClick={handleClaim}
          style={{ marginTop: 14, padding: '8px 24px', fontSize: 14 }}
        >
          {acking ? '...' : 'Claim'}
        </button>
      </div>
    </div>
  )
}
```

- [ ] **Step 3: Embed in Shell**

In `frontend/src/components/Layout/Shell.tsx`:

```tsx
import { PendingArenaReward } from '../PendingArenaReward'
```

Add `<PendingArenaReward />` inside the Shell render — alongside `<QuestWidget />`:

```tsx
<QuestWidget />
<PendingArenaReward />
<VersionTag />
```

- [ ] **Step 4: Build**

Run: `cd frontend && npm run build`
Expected: clean build.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/PendingArenaReward.tsx frontend/src/components/Layout/Shell.tsx frontend/src/api/arena.ts
git commit -m "feat(frontend): weekly arena reward modal"
```

---

## Final Verification

- [ ] **Step 1: Run full backend test suite**

Run: `cd C:/Users/User/.claude/mmorpg/hero-proto && uv run pytest -x -q`
Expected: all PASS, including new `test_arena_economy.py` and `test_arena_payout.py`.

- [ ] **Step 2: Run frontend tests + build**

Run: `cd frontend && npx vitest run && npm run build`
Expected: tests PASS, build completes cleanly.

- [ ] **Step 3: Manual smoke test (local)**

Run: `cd C:/Users/User/.claude/mmorpg/hero-proto && uv run uvicorn app.main:app --reload`

In a browser at `http://localhost:8000/spa/`:
1. Register a new account.
2. Verify `/me` response includes `arena_tickets`, `arena_tickets_cap`, `arena_tickets_next_tick_in`, `energy_next_tick_in`, `arena_weekly_wins`, `pending_arena_rewards`.
3. CurrencyBar shows energy timer + ticket count.
4. Me page shows the Recurring Resources panel with all three timers ticking.
5. Arena page shows the TicketHeader and Attack button works.
6. Drain tickets via 5 attacks; 6th attack returns 429.

- [ ] **Step 4: Hand off to finishing-a-development-branch**

Use the `superpowers:finishing-a-development-branch` skill to choose merge / PR / keep / discard.
