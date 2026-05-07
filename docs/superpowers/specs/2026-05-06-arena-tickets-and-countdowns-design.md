# Recurring Resource Countdowns + Arena Economy

**Status:** Approved 2026-05-06
**Author:** Gary

## Goal

Two related improvements ship together:

1. **Countdown timers** on the recurring resources players already track (energy, arena tickets, daily reset). Right now energy regenerates silently on the server — the frontend has no idea when the next tick lands. Surface that.
2. **Arena economy.** The arena currently rewards nothing material — only a rating delta and a daily-quest tick. Add per-attack drip rewards, gate attacks behind a new ticket resource (5/day, regen 4h), and add a weekly leaderboard payout.

Bundling: the ticket system and the reward drip both hit the arena attack endpoint, and both want UI surface area on the same screens — keeping them in one spec avoids two passes through the same files.

## Non-Goals

- No ladder reset. `arena_rating` carries forever; the weekly payout is a snapshot, not a reset.
- No PvP defense rewards (defending against an attack does not earn drip — only the attacker earns).
- No gem-purchase ticket refill (YAGNI — players can already buy gems and there's no proven demand).
- No real-time websocket countdown sync — pure client-side ticking off the latest `/me` payload.

## Architecture

```
┌─────────────────────────┐         ┌────────────────────────────────┐
│ Account model           │         │ ArenaWeeklyPayout (new)        │
│  + arena_tickets_stored │         │  PK: (week_key, account_id)    │
│  + arena_tickets_last_  │         │  rank, gems, eligible_wins,    │
│    tick_at              │         │  granted_at                    │
│  + arena_weekly_wins    │         └────────────────────────────────┘
│  + arena_weekly_key     │                       ▲
└─────────────────────────┘                       │ inserted by
              │                                   │
              │ read/mutated by                   │
              ▼                                   │
┌─────────────────────────┐         ┌────────────────────────────────┐
│ app/economy.py          │         │ app/arena_payout.py (new)      │
│  compute_arena_tickets  │         │  distribute_pending(db)        │
│  consume_arena_ticket   │         │   - called from /me            │
└─────────────────────────┘         │   - lazy, idempotent on PK     │
                                    └────────────────────────────────┘
              │                                   │
              ▼                                   ▼
┌──────────────────────────────────────────────────────────────────┐
│ POST /arena/attack                                               │
│   1. consume_arena_ticket → 429 if 0                             │
│   2. simulate                                                    │
│   3. apply rating delta                                          │
│   4. drip rewards (coins/shards/gems by outcome)                 │
│   5. on win: arena_weekly_wins += 1                              │
│   6. return ArenaMatchOut + rewards                              │
└──────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│ GET /me                                                          │
│   - flushes energy + arena ticket regen                          │
│   - calls distribute_pending(db) → weekly payout if needed       │
│   - returns: energy_next_tick_in, arena_tickets,                 │
│     arena_tickets_cap, arena_tickets_next_tick_in,               │
│     arena_weekly_wins, pending_arena_rewards                     │
└─────────────────────────────────────────────────────────────────┘
              │
              ▼
┌─────────────────────────────────────────────────────────────────┐
│ Frontend                                                         │
│   useCountdown(seconds) — live ticking display                   │
│   useDailyResetCountdown() — client-computed midnight UTC        │
│   CurrencyBar — energy + arena timers inline                     │
│   Arena/TicketHeader — ticket count + next-tick                  │
│   Me/RecurringResources — full panel                             │
│   PendingArenaReward — modal for weekly payout                   │
└─────────────────────────────────────────────────────────────────┘
```

## Data Model

### New columns on `accounts`

```python
arena_tickets_stored:      Mapped[int]      = mapped_column(Integer, default=5)
arena_tickets_last_tick_at:Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
arena_weekly_wins:         Mapped[int]      = mapped_column(Integer, default=0)
arena_weekly_key:          Mapped[str]      = mapped_column(String(10), default="")
```

`arena_weekly_key` holds an ISO week string like `"2026-W19"`. When the account hits any auth'd endpoint after the week boundary, it's compared to the current week — if different, `arena_weekly_wins` is reset to 0 and the key is bumped.

### New table `arena_weekly_payouts`

```python
class ArenaWeeklyPayout(Base):
    __tablename__ = "arena_weekly_payouts"
    week_key:       Mapped[str]      = mapped_column(String(10), primary_key=True)
    account_id:     Mapped[int]      = mapped_column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True)
    rank:           Mapped[int]      = mapped_column(Integer)
    gems:           Mapped[int]      = mapped_column(Integer)
    eligible_wins:  Mapped[int]      = mapped_column(Integer)
    granted_at:     Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    acknowledged_at:Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
```

The compound PK `(week_key, account_id)` is the idempotency lock. Distribution uses an upsert that fails silently on conflict, so two requests racing the distributor never double-grant.

`acknowledged_at` is set when the player clicks "Claim" on the modal — frontend uses null-acknowledged rows to populate `pending_arena_rewards`.

## Configuration

```python
# app/config.py additions
arena_tickets_cap:           int = 5
arena_tickets_regen_seconds: int = 14400  # 4 hours

# app/arena_constants.py (new file)
ARENA_REWARDS = {
    "win":  {"coins": 75, "shards": 3, "gems": 5},
    "loss": {"coins": 25, "shards": 0, "gems": 0},
    "draw": {"coins": 25, "shards": 0, "gems": 0},
}
ARENA_REWARD_JITTER = 0.20  # ±20% on coins only

# (rank_lo, rank_hi, gems) — top 50 paid out
ARENA_WEEKLY_PAYOUT = [
    (1, 1, 500),
    (2, 5, 250),
    (6, 20, 100),
    (21, 50, 50),
]
ARENA_CHAMPION_FRAME = "arena_champion"
```

## Backend Components

### `app/economy.py` additions

```python
def compute_arena_tickets(account: Account, now: datetime | None = None) -> int:
    """Mirror of compute_energy: flushes regen ticks, returns current count."""

def consume_arena_ticket(account: Account, now: datetime | None = None) -> bool:
    """Atomically flush regen + spend 1. Returns False if at 0."""
```

Both follow the exact pattern of `compute_energy` / `consume_energy` so the next reader has zero new concepts to learn.

### `app/arena_payout.py` (new module)

```python
def current_week_key(now: datetime | None = None) -> str: ...
def previous_week_key(now: datetime | None = None) -> str: ...

def distribute_pending(db: Session, now: datetime | None = None) -> int:
    """Idempotently distribute the prior week's payouts.

    Returns the number of payouts inserted (0 if already distributed for this week).

    Algorithm:
      1. SELECT FOR UPDATE on a sentinel row keyed by week_key (creates if missing).
      2. If any ArenaWeeklyPayout row exists for prev_week_key, return 0.
      3. SELECT top 50 accounts by arena_rating where arena_weekly_wins >= 1
         and arena_weekly_key == prev_week_key.
      4. For each, compute rank → gems via ARENA_WEEKLY_PAYOUT brackets.
      5. INSERT ArenaWeeklyPayout, credit account.gems, grant
         arena_champion frame to rank 1 if not already held.
      6. Commit.

    Eligibility filter (arena_weekly_wins >= 1) excludes parked accounts.
    """

def reset_weekly_counter_if_stale(account: Account, now: datetime | None = None) -> None:
    """Bumps arena_weekly_key + zeroes arena_weekly_wins if account's key is stale.
    Called per-account on every /me hit (cheap — string compare)."""
```

### `app/routers/arena.py` changes

Inside the existing `attack` endpoint:

```python
# After defender validation, before simulate:
if not consume_arena_ticket(account):
    raise HTTPException(429, "out of arena tickets — next in N seconds",
                        headers={"Retry-After": str(seconds_until_next_ticket(account))})

# After rating delta is applied:
reward_set = ARENA_REWARDS[outcome_key]  # "win" | "loss" | "draw"
coins = jitter(reward_set["coins"], ARENA_REWARD_JITTER, rng)
account.coins  += coins
account.shards += reward_set["shards"]
account.gems   += reward_set["gems"]

if outcome == BattleOutcome.WIN:
    reset_weekly_counter_if_stale(account)
    account.arena_weekly_wins += 1
```

`ArenaMatchOut` schema gains `rewards: dict[str, int]` so the client can render `"+75 coins +3 shards +5 gems"`.

### `app/routers/me.py` changes

```python
# Top of /me handler:
reset_weekly_counter_if_stale(account)
distribute_pending(db)  # idempotent; cheap when already distributed

# In response:
energy_next_tick_in:        seconds_until_next_energy(account)
arena_tickets:              compute_arena_tickets(account)
arena_tickets_cap:          settings.arena_tickets_cap
arena_tickets_next_tick_in: seconds_until_next_ticket(account)
arena_weekly_wins:          account.arena_weekly_wins
pending_arena_rewards:      [
    {"week_key": p.week_key, "rank": p.rank, "gems": p.gems}
    for p in unacknowledged_payouts(db, account)
]
```

`seconds_until_next_*` helpers return 0 when at cap.

### New endpoint `POST /arena/weekly/acknowledge`

```python
@router.post("/weekly/acknowledge")
def acknowledge_weekly_rewards(account, db) -> dict:
    """Sets acknowledged_at on all unacknowledged ArenaWeeklyPayout rows for
    this account. Idempotent. No body."""
```

## Frontend Components

### `frontend/src/hooks/useCountdown.ts`

```typescript
export function useCountdown(seconds: number, onZero?: () => void): string
```

- Holds local `remaining` state initialised from `seconds`
- `setInterval(1000)` decrements until 0
- Resets when `seconds` prop changes (so a /me refetch resets the timer)
- Calls `onZero` once when crossing to 0 (used to invalidate the `me` query)
- Returns `"M:SS"` under 1 hour, `"H:MM:SS"` otherwise
- Returns `"0:00"` when `seconds <= 0`

### `frontend/src/hooks/useDailyResetCountdown.ts`

```typescript
export function useDailyResetCountdown(): string
```

Computes seconds until next `00:00 UTC` from `Date.now()`. Same return format. No server input — purely client-side.

### CurrencyBar update (`components/Layout/CurrencyBar.tsx`)

Add inline timer text after the existing values. Shown only when below cap:

```
⚡ 45/100 · +1 in 3:42      🎯 3/5 · +1 in 2:14
```

### `components/Arena/TicketHeader.tsx` (new)

Shown above the opponents list on the Arena route:

```
🎯 Tickets: 3 / 5
   Next ticket in 2:14:30 · full in 8:14:30
```

`full in` = `next_tick_in + (cap - tickets - 1) * regen_seconds`.

Attack buttons throughout the arena route disable when `me.arena_tickets === 0` with tooltip "out of tickets — next in M:SS".

### `components/Me/RecurringResources.tsx` (new)

Shown on the Me page below the existing currency block:

```
Recurring Resources
  ⚡ Energy        45 / 100   +1 in 3:42
  🎯 Arena         3 / 5      +1 in 2:14:30
  📅 Daily reset              in 6:42:11
```

### `routes/arena/AttackResult.tsx` update

Existing match result view appends a rewards line driven by `match.rewards`:

```
+75 coins · +3 shards · +5 gems
```

### `components/PendingArenaReward.tsx` (new)

Reads `me.pending_arena_rewards`. If non-empty, shows a one-shot modal on next page load:

```
🏆 Arena Week Complete
You finished rank #4 last week
+250 gems
[ Claim ]
```

"Claim" → `POST /arena/weekly/acknowledge`, then invalidates `me`. Modal closes.

Rank 1 modal additionally shows the cosmetic frame grant.

## Error Handling

- **Out of tickets:** `429` with `Retry-After` header carrying seconds until next ticket. Frontend disables attack buttons preemptively when `arena_tickets === 0`.
- **Distributor race:** `SELECT ... FOR UPDATE` on a sentinel row keyed by `week_key` serialises any two requests trying to distribute the same week. Compound PK on `arena_weekly_payouts` is the second line of defence — if the lock somehow fails, the duplicate INSERT will conflict and the granting code path won't run.
- **Migration on existing accounts:** All current accounts get `arena_tickets_stored = 5`, `arena_tickets_last_tick_at = NOW()`, `arena_weekly_wins = 0`, `arena_weekly_key = ""`. The empty `arena_weekly_key` is intentional — `reset_weekly_counter_if_stale` will bump it to the current week on first /me hit.
- **Arena rate limit still applies:** the existing `_arena_bucket` per-account anti-hammer gate stays in place. Tickets are the game-economy gate; the bucket is the abuse gate. Both must pass.
- **Frontend timer drift:** if a `useCountdown` hits 0 but the next /me hasn't refetched yet, it stays at "0:00" until the natural refetch (every 30s via React Query). The `onZero` hook can trigger an immediate refetch for snappier feel.

## Test Plan

### Backend (`tests/test_arena_economy.py`)

- `test_compute_arena_tickets_ticks_correctly` — fast-forward time, verify count.
- `test_compute_arena_tickets_caps_at_max` — well past full regen, count stays at 5.
- `test_consume_ticket_returns_false_at_zero` — drained account.
- `test_attack_429_when_no_tickets` — full integration via TestClient.
- `test_attack_drips_rewards_on_win` — coins/shards/gems incremented within jitter range.
- `test_attack_drips_consolation_on_loss` — coins only, no shards/gems.
- `test_attack_increments_weekly_wins_on_win_only` — loss does not.
- `test_attack_returns_rewards_in_response` — `ArenaMatchOut.rewards` populated.

### `tests/test_arena_payout.py`

- `test_distribute_pending_pays_top_50_by_rating` — populate ratings, run, assert ranks/amounts.
- `test_distribute_pending_filters_by_eligible_wins` — accounts with `arena_weekly_wins == 0` excluded even if rating is high.
- `test_distribute_pending_idempotent` — running twice grants once (PK conflict).
- `test_distribute_pending_grants_champion_frame_to_rank_1` — and only to rank 1.
- `test_distribute_pending_no_op_within_same_week` — two calls inside one ISO week → 0 inserts.
- `test_distribute_pending_handles_concurrent_calls` — simulate via threading two SessionLocal sessions, exactly one distribution succeeds.
- `test_reset_weekly_counter_bumps_key_and_zeroes_wins` — stale key triggers reset.
- `test_acknowledge_endpoint_marks_all_pending` — POST /arena/weekly/acknowledge clears pending list on next /me.

### `tests/test_migrations.py`

- Roundtrip migration: upgrade → downgrade → upgrade, verify schema matches.

### Frontend (`frontend/src/test/`)

- `useCountdown.test.ts` — counts down, resets on prop change, formats below/above 1h, fires `onZero` exactly once.
- `useDailyResetCountdown.test.ts` — mock `Date.now()` at various UTC hours, verify seconds.
- `CurrencyBar.test.tsx` — timer text rendered below cap, hidden at cap.
- `PendingArenaReward.test.tsx` — modal renders only when payload non-empty, "Claim" calls endpoint and invalidates query.

## Out of Scope (For Future Specs)

- Gem-purchase arena ticket refills.
- Defense rewards (winning while being attacked).
- Tournament-style brackets, separate ranked seasons.
- Public weekly payout history UI (top-N hall of fame).
- Push notifications when tickets fill up.
