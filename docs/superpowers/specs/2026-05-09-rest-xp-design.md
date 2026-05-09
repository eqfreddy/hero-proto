# Rest XP — 2× Multiplier on Banked Offline Time

**Goal:** Returning players accumulate a bank of "rested time" while offline; XP grants (account + hero) are doubled while the bank has time remaining. Bank caps at 12 hours of offline accumulation; bank ticks down at 2× wallclock during active sessions.

**Architecture:** Two columns on `Account`: `rest_xp_banked_seconds` (int) and `rest_xp_last_tick_at` (datetime). On every authenticated request, the bank is updated based on elapsed time since `last_tick_at`: offline time accumulates (capped at 12h cumulative), active time burns at 2× wallclock. The `grant_xp` helper consults the bank: if seconds remain, grant 2× XP and burn `xp_grant_seconds_cost` from the bank.

**Tech Stack:** SQLAlchemy columns + Alembic migration; lightweight helper module `app/rest_xp.py`; integration into existing `grant_xp` call sites.

**Depends on:** Nothing structural. Can ship before or after subsystems #1–#3, but interacts with #1's tier XP table (the multiplier applies to whatever base XP the tier system grants).

---

## 1. Storage

New columns on `Account`:

```python
rest_xp_banked_seconds: Mapped[int] = mapped_column(Integer, default=0)
rest_xp_last_tick_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
```

Migration: additive, defaults `0` and `now()` for existing rows.

## 2. Constants

```python
REST_XP_BANK_CAP_SECONDS = 12 * 3600        # 12 h
REST_XP_OFFLINE_RATE = 1.0                  # 1 banked second per offline second
REST_XP_BURN_RATE = 2.0                     # bank ticks down at 2× wallclock when active
ACTIVE_IDLE_THRESHOLD_SECONDS = 5 * 60      # 5 min — past this, treat as offline
REST_XP_MULTIPLIER = 2.0                    # XP grants doubled while bank > 0
```

## 3. Tick Function

`app/rest_xp.py`:

```python
def update_bank(account: Account, now: datetime) -> None:
    """Update banked seconds based on elapsed time since last tick.
    Mutates account in place; caller commits."""
    elapsed = (now - account.rest_xp_last_tick_at).total_seconds()
    if elapsed <= 0:
        account.rest_xp_last_tick_at = now
        return
    if elapsed > ACTIVE_IDLE_THRESHOLD_SECONDS:
        # Treat as offline period — accumulate.
        account.rest_xp_banked_seconds = min(
            REST_XP_BANK_CAP_SECONDS,
            account.rest_xp_banked_seconds + int(elapsed * REST_XP_OFFLINE_RATE),
        )
    else:
        # Active session — burn the bank at 2× wallclock.
        burn = int(elapsed * REST_XP_BURN_RATE)
        account.rest_xp_banked_seconds = max(0, account.rest_xp_banked_seconds - burn)
    account.rest_xp_last_tick_at = now
```

Called once per authenticated request via a FastAPI dependency:

```python
def get_current_account_with_rest(...) -> Account:
    account = get_current_account(...)
    update_bank(account, utcnow())
    return account
```

## 4. XP Grant Integration

Wherever XP is granted (account or hero):

```python
def grant_xp(account: Account, base_xp: int, *, kind: str = "account") -> int:
    """Returns the actual XP granted (after rest multiplier)."""
    multiplier = 1.0
    if account.rest_xp_banked_seconds > 0:
        multiplier = REST_XP_MULTIPLIER
    granted = int(round(base_xp * multiplier))
    return granted
```

The bank itself is burned by the per-request tick (subsection 3), not per-grant. This keeps grant logic simple — grant just reads the bank's current state.

## 5. Player Visibility

**XP bar badge:** When `rest_xp_banked_seconds > 0`, the account-XP bar (and hero-XP bar on the hero card) shows a small "Rested ×2" pill or icon.

**Tooltip:** Hovering shows the remaining banked time in human-readable form: "Rested XP: 2h 14m remaining."

**Toast on first XP grant of a session:** Optional. *"Welcome back — XP doubled while rested."*

## 6. Edge Cases

- **First-ever login:** `rest_xp_last_tick_at` defaults to account creation time. If the player creates an account and immediately battles, `elapsed` is small and active — no bank accumulated. Correct.
- **Multi-device:** Bank is per-account, not per-session. If user logs in on phone and PC simultaneously, both update the same account row; concurrent ticks are racy but harmless (each tick is a small idempotent update). Acceptable for v1.
- **Server clock skew / restart:** `last_tick_at` is server-authored UTC. Restarts don't matter (bank state is in DB). Clock changes >> hours could over-grant; ignore for v1.
- **Closed-tab inactivity vs. logout:** No way to distinguish reliably. Anything past 5 min idle is treated as offline → starts accumulating. This is generous (player gets bank back from leaving the tab open), but not exploitable in any meaningful way (cap is 12h).

## 7. Testing

- Unit: `update_bank` accumulates correctly across an offline gap, capped at 12h.
- Unit: `update_bank` burns at 2× wallclock during active session.
- Unit: `grant_xp(base=12)` with bank > 0 returns 24; with bank = 0 returns 12.
- Integration: a request after a 4h offline gap accumulates 4h to the bank; a battle right after grants 2× XP.
- Integration: spamming the same battle endpoint within seconds correctly burns the bank at 2× wallclock.

## 8. Out of Scope

- Premium boosters that increase the cap (12h → 24h) — backlog.
- Per-grant cost in seconds (`grant_xp` burning bank seconds itself) — rejected in favor of pure wallclock burn.
- Hero-XP-only or account-XP-only mode — both share the multiplier.
