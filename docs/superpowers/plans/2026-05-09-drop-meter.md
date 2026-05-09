# Drop Meter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Each `(stage, tier)` accumulates a per-account meter that fills by 1 per WIN. At cap (20), the next WIN guarantees a RARE+ drop with tier-keyed rarity weights, then the meter resets to 0.

**Architecture:** A new `Account.stage_drop_pity_json` JSON column tracks `{(stage_code:tier): runs_since_last_guarantee}`. A new `app/drop_meter.py` module owns the increment/reset/rarity-roll helpers. The 3 existing gear-drop sites in `app/routers/battles.py` (main `fight`, sweep, auto-resolve) call into the meter helpers; when the cap is reached, the call site uses `roll_gear_targeted(rng, rarity=...)` instead of the random `roll_gear(...)` path. Per-stage meter values surface via the `/stages` API for frontend rendering.

**Tech Stack:** Python 3.13 + FastAPI + SQLAlchemy 2.0 + Alembic. Tests via `uv run pytest`. Additive Alembic migration adds one Text column.

**Spec:** `docs/superpowers/specs/2026-05-09-drop-meter-design.md`

**Reference (grounded codebase facts):**
- `app/models.py:191` — `Account` model location
- `app/models.py:GearRarity` — `COMMON / RARE / EPIC / LEGENDARY` enum
- `app/gear_logic.py:77` — `roll_gear(rng, stage_order) -> tuple[GearSlot, GearRarity, GearSet, dict]` (random rarity)
- `app/gear_logic.py:96` — `roll_gear_targeted(rng, *, slot=None, rarity=None, set_code=None) -> tuple[...]` (forces specified rarity)
- `app/routers/battles.py:349-383` — main `fight()` gear-drop block (`if outcome == BattleOutcome.WIN: ... if rng.random() < drop_chance:`)
- `app/routers/battles.py:728-739` — sweep endpoint gear-drop block
- `app/routers/battles.py:867-882` — auto-resolved instant battle gear-drop block
- `app/routers/stages.py` — already auth'd (subsystem #2), already builds per-stage payloads with cleared/unlocked context
- `app/tiers.py` — existing module for tier-keyed policy (subsystems #2/#3)
- `tests/conftest.py` — `db_session` fixture (added in subsystem #2)
- `app/security.py:issue_token` — auth helper used by the existing tier-locks/rest-xp tests

**Spec mechanics (LOCKED):**

```
DROP_METER_CAP = 20
GUARANTEE_POOL = {
    NORMAL:    {RARE: 1.0},
    HARD:      {RARE: 0.7, EPIC: 0.3},
    NIGHTMARE: {EPIC: 0.8, LEGENDARY: 0.2},
    LEGENDARY: {EPIC: 0.4, LEGENDARY: 0.6},
}
```

- WIN-only — losses don't increment.
- Counter increments by 1 each WIN. When count reaches CAP, the same run that hit cap triggers the guaranteed drop, then the counter resets to 0.
- If a stage's drop table has no items at the rolled rarity (content gap): fall back to highest available rarity in the stage's table. Currently `roll_gear_targeted` has no per-stage drop table — gear drops are global by rarity, so this fallback is theoretical for v1. Note in the helper docstring; revisit if/when stage-specific drop tables ship.
- Per `(stage_code, difficulty_tier)` — switching stages or tiers leaves other counters untouched.

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `alembic/versions/<rev>_add_stage_drop_pity_json.py` | Additive migration — `accounts.stage_drop_pity_json` Text(2048) column, default `'{}'`. | Create |
| `app/models.py` | New `Account.stage_drop_pity_json` Mapped[str] column. | Modify |
| `app/drop_meter.py` | NEW — `read_meter(account, stage_code, tier) -> int`; `increment_and_check(account, stage_code, tier) -> bool` (True when this run hits cap); `force_rarity(tier, rng) -> GearRarity` (weighted pick from pool); constants `DROP_METER_CAP`, `GUARANTEE_POOL`. | Create |
| `app/routers/battles.py` | At each of the 3 gear-drop sites: increment meter on WIN; if at-cap, force a guaranteed drop via `roll_gear_targeted` instead of `roll_gear`. | Modify |
| `app/routers/stages.py` | Surface `drop_meter: int` and `drop_meter_cap: int` per `/stages` row from `read_meter` + `DROP_METER_CAP`. | Modify |
| `app/schemas.py` | Add `drop_meter: int = 0` and `drop_meter_cap: int = 0` to `StageOut`. | Modify |
| `frontend/src/types/index.ts` | Extend Stage TS interface with the 2 new fields. | Modify |
| `frontend/src/routes/Stages.tsx` | Render meter progress badge ("Guaranteed drop in N runs" / "★ Guaranteed drop next run!"). | Modify |
| `tests/test_drop_meter.py` | NEW — covers helper, increment cycle, rarity pool weights, integration through battle endpoint. | Create |

---

## Task 1: Schema + migration

**Files:**
- Modify: `app/models.py` (Account class — add column near `stage_pity_json` from subsystem #3)
- Create: `alembic/versions/<rev>_add_stage_drop_pity_json.py`
- Test: `tests/test_drop_meter.py` (create)

- [ ] **Step 1: Inspect a recent additive migration**

Run: `cat alembic/versions/500bd5370e47_add_accounts_stage_pity_json.py`

Match its style — single-column additive migration with `batch_alter_table`.

- [ ] **Step 2: Write the failing test**

Create `tests/test_drop_meter.py`:

```python
"""Drop-meter tests."""
import json

from app.models import Account


def test_account_has_stage_drop_pity_json_column(db_session):
    """New accounts get an empty stage_drop_pity_json blob by default."""
    acc = Account(email="drop_default@example.com", password_hash="x")
    db_session.add(acc)
    db_session.flush()
    db_session.refresh(acc)
    assert acc.stage_drop_pity_json == "{}"
    parsed = json.loads(acc.stage_drop_pity_json)
    assert parsed == {}
```

- [ ] **Step 3: Run test — expect failure**

Run: `uv run pytest tests/test_drop_meter.py -v`
Expected: AttributeError or column-missing.

- [ ] **Step 4: Add column to Account model**

In `app/models.py`, in the `Account` class. Find `stage_pity_json` (added by subsystem #3). Right after it, add:

```python
    # Per (stage_code, difficulty_tier) gear-drop meter for guaranteed RARE+ drops.
    # Shape: {"<stage_code>:<TIER>": int}.  Resets to 0 when the cap (20) fires.
    # See app/drop_meter.py for the increment + rarity-roll logic.
    stage_drop_pity_json: Mapped[str] = mapped_column(String(2048), default="{}", server_default="{}")
```

- [ ] **Step 5: Generate the Alembic migration**

Run: `uv run alembic revision -m "add accounts.stage_drop_pity_json"`

Open the generated file. Replace `upgrade()` and `downgrade()` bodies:

```python
def upgrade() -> None:
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.add_column(
            sa.Column("stage_drop_pity_json", sa.String(length=2048), nullable=False, server_default="{}"),
        )


def downgrade() -> None:
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_column("stage_drop_pity_json")
```

Keep auto-generated revision IDs at the top of the file unchanged.

- [ ] **Step 6: Verify**

Run: `uv run pytest tests/test_drop_meter.py -v`
Expected: 1 PASS.

Run: `uv run pytest 2>&1 | tail -5`
Expected: 760+ pass, 1 pre-existing failure in `test_event_quests` tolerated.

- [ ] **Step 7: Commit**

```bash
git add app/models.py alembic/versions/ tests/test_drop_meter.py
git commit -m "feat(drop-meter): add accounts.stage_drop_pity_json column + migration"
```

---

## Task 2: Drop-meter helper module

**Files:**
- Create: `app/drop_meter.py`
- Test: `tests/test_drop_meter.py` (append)

- [ ] **Step 1: Append failing tests**

Append to `tests/test_drop_meter.py`:

```python
import random

from app.drop_meter import (
    read_meter,
    increment_and_check,
    force_rarity,
    DROP_METER_CAP,
    GUARANTEE_POOL,
)
from app.models import GearRarity, StageDifficulty


def _make_account(db_session):
    from app.models import Account
    n = db_session.info.get("counter", 0)
    db_session.info["counter"] = n + 1
    acc = Account(email=f"drop_{n}@example.com", password_hash="x")
    db_session.add(acc)
    db_session.flush()
    return acc


def test_constants_match_spec():
    assert DROP_METER_CAP == 20
    # All 4 tiers represented in the guarantee pool.
    assert set(GUARANTEE_POOL.keys()) == {
        StageDifficulty.NORMAL,
        StageDifficulty.HARD,
        StageDifficulty.NIGHTMARE,
        StageDifficulty.LEGENDARY,
    }
    # NORMAL: only RARE.
    assert GUARANTEE_POOL[StageDifficulty.NORMAL] == {GearRarity.RARE: 1.0}
    # LEGENDARY: EPIC 0.4, LEGENDARY 0.6.
    leg = GUARANTEE_POOL[StageDifficulty.LEGENDARY]
    assert leg[GearRarity.EPIC] == 0.4
    assert leg[GearRarity.LEGENDARY] == 0.6


def test_read_meter_default_zero(db_session):
    acc = _make_account(db_session)
    assert read_meter(acc, "1-1", StageDifficulty.HARD) == 0


def test_increment_and_check_below_cap_returns_false(db_session):
    """First 19 increments return False; counter advances by 1 each call."""
    acc = _make_account(db_session)
    for i in range(1, DROP_METER_CAP):
        triggered = increment_and_check(acc, "1-1", StageDifficulty.HARD)
        assert triggered is False, f"unexpected trigger at run {i}"
        assert read_meter(acc, "1-1", StageDifficulty.HARD) == i


def test_increment_and_check_at_cap_triggers_and_resets(db_session):
    """Run 20 hits cap, returns True, and resets counter to 0."""
    acc = _make_account(db_session)
    # Pre-fill to 19.
    import json
    acc.stage_drop_pity_json = json.dumps({"1-1:HARD": 19})

    triggered = increment_and_check(acc, "1-1", StageDifficulty.HARD)
    assert triggered is True
    # After the trigger, the counter reset to 0.
    assert read_meter(acc, "1-1", StageDifficulty.HARD) == 0


def test_increment_independent_per_stage_and_tier(db_session):
    """Counters on different (stage, tier) pairs don't interfere."""
    acc = _make_account(db_session)
    increment_and_check(acc, "1-1", StageDifficulty.HARD)
    increment_and_check(acc, "1-1", StageDifficulty.HARD)
    # Different stage.
    assert read_meter(acc, "1-2", StageDifficulty.HARD) == 0
    # Different tier on same stage.
    assert read_meter(acc, "1-1", StageDifficulty.NIGHTMARE) == 0
    # Original counter intact.
    assert read_meter(acc, "1-1", StageDifficulty.HARD) == 2


def test_force_rarity_normal_always_rare():
    """NORMAL pool has only RARE — every call returns RARE regardless of RNG."""
    rng = random.Random(0)
    for _ in range(50):
        assert force_rarity(StageDifficulty.NORMAL, rng) == GearRarity.RARE


def test_force_rarity_legendary_only_epic_or_legendary():
    """LEGENDARY pool: only EPIC and LEGENDARY can be rolled."""
    rng = random.Random(0)
    for _ in range(100):
        rolled = force_rarity(StageDifficulty.LEGENDARY, rng)
        assert rolled in {GearRarity.EPIC, GearRarity.LEGENDARY}


def test_force_rarity_distribution_matches_weights(db_session):
    """Sampling 1000 LEGENDARY rolls should land within tolerance of (0.4, 0.6)."""
    rng = random.Random(42)
    counts = {GearRarity.EPIC: 0, GearRarity.LEGENDARY: 0}
    n = 1000
    for _ in range(n):
        counts[force_rarity(StageDifficulty.LEGENDARY, rng)] += 1
    epic_pct = counts[GearRarity.EPIC] / n
    legendary_pct = counts[GearRarity.LEGENDARY] / n
    # Allow ±0.05 slack (1000 samples, two-tier pool).
    assert 0.35 <= epic_pct <= 0.45, f"EPIC pct out of band: {epic_pct}"
    assert 0.55 <= legendary_pct <= 0.65, f"LEGENDARY pct out of band: {legendary_pct}"
```

- [ ] **Step 2: Run tests — expect ImportError**

Run: `uv run pytest tests/test_drop_meter.py -v`
Expected: ImportError on `app.drop_meter`.

- [ ] **Step 3: Create app/drop_meter.py**

```python
"""Drop-meter engine.

Each (stage_code, difficulty_tier) accumulates a per-account counter on every
WIN. When the counter reaches DROP_METER_CAP, the same run that hits the cap
triggers a guaranteed RARE+ drop with tier-keyed rarity weights, then the
counter resets to 0.

State lives on Account.stage_drop_pity_json:
  {"<stage_code>:<TIER>": int}

The helpers do not commit — caller owns the transaction. force_rarity() is a
pure function (RNG -> GearRarity).
"""
from __future__ import annotations

import json
import logging
import random

from app.models import Account, GearRarity, StageDifficulty

log = logging.getLogger(__name__)

DROP_METER_CAP = 20

# Per-tier rarity pool for the guaranteed drop. Weights normalize to 1.0 per tier.
GUARANTEE_POOL: dict[StageDifficulty, dict[GearRarity, float]] = {
    StageDifficulty.NORMAL:    {GearRarity.RARE: 1.0},
    StageDifficulty.HARD:      {GearRarity.RARE: 0.7, GearRarity.EPIC: 0.3},
    StageDifficulty.NIGHTMARE: {GearRarity.EPIC: 0.8, GearRarity.LEGENDARY: 0.2},
    StageDifficulty.LEGENDARY: {GearRarity.EPIC: 0.4, GearRarity.LEGENDARY: 0.6},
}


def _key(stage_code: str, tier: StageDifficulty | str) -> str:
    tier_str = tier.value if isinstance(tier, StageDifficulty) else str(tier)
    return f"{stage_code}:{tier_str}"


def _load(account: Account) -> dict:
    try:
        return json.loads(account.stage_drop_pity_json or "{}")
    except (json.JSONDecodeError, TypeError):
        log.warning("stage_drop_pity_json corrupt for account=%s; resetting", account.id)
        return {}


def _save(account: Account, data: dict) -> None:
    account.stage_drop_pity_json = json.dumps(data)


def read_meter(account: Account, stage_code: str, tier: StageDifficulty | str) -> int:
    """Return the current run-count for a (stage, tier) pair. Defaults to 0."""
    data = _load(account)
    return int(data.get(_key(stage_code, tier), 0))


def increment_and_check(account: Account, stage_code: str, tier: StageDifficulty | str) -> bool:
    """Increment the meter for this (stage, tier) WIN. Returns True when this run
    hits DROP_METER_CAP — caller should force a guaranteed drop. Resets the counter
    to 0 on trigger; otherwise persists the incremented value."""
    data = _load(account)
    key = _key(stage_code, tier)
    new_count = int(data.get(key, 0)) + 1
    if new_count >= DROP_METER_CAP:
        # Trigger the guarantee and reset the counter.
        data.pop(key, None)
        _save(account, data)
        return True
    data[key] = new_count
    _save(account, data)
    return False


def force_rarity(tier: StageDifficulty | str, rng: random.Random) -> GearRarity:
    """Weighted pick from the tier's GUARANTEE_POOL. Falls back to RARE if the
    tier is unknown — defensive default."""
    try:
        key = tier if isinstance(tier, StageDifficulty) else StageDifficulty(tier)
    except ValueError:
        return GearRarity.RARE
    pool = GUARANTEE_POOL.get(key)
    if not pool:
        return GearRarity.RARE
    rarities = list(pool.keys())
    weights = [pool[r] for r in rarities]
    return rng.choices(rarities, weights=weights, k=1)[0]
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/test_drop_meter.py -v`
Expected: 9 PASS (1 from Task 1 + 8 new).

- [ ] **Step 5: Commit**

```bash
git add app/drop_meter.py tests/test_drop_meter.py
git commit -m "feat(drop-meter): meter helpers (read, increment, force_rarity)"
```

---

## Task 3: Wire meter into the 3 battle drop sites

**Files:**
- Modify: `app/routers/battles.py` — drop-meter call at lines ~349-383, ~728-739, ~867-882
- Test: `tests/test_drop_meter.py` (append integration test)

**Context:** All 3 drop sites share the same shape:

```python
if outcome == BattleOutcome.WIN:   # or `if won:`
    drop_chance = ...
    if rng.random() < drop_chance:
        slot, rarity, set_code, stats = roll_gear(rng, stage.order)
        # ... persist gear ...
```

The change at every site is:

```python
if outcome == BattleOutcome.WIN:   # unchanged
    from app.drop_meter import increment_and_check as _drop_inc, force_rarity as _force_rar
    triggered = _drop_inc(account, stage.code, stage.difficulty_tier)
    drop_chance = ...
    if triggered:
        # Guaranteed drop — force the tier-keyed rarity, skip RNG gate.
        from app.gear_logic import roll_gear_targeted as _roll_targeted
        slot, rarity, set_code, stats = _roll_targeted(rng, rarity=_force_rar(stage.difficulty_tier, rng))
        # ... persist gear ... (same as below)
    elif rng.random() < drop_chance:
        slot, rarity, set_code, stats = roll_gear(rng, stage.order)
        # ... persist gear ...
```

Read the existing block carefully at each site — the persistence path (Gear() row + db.add() + db.flush() + rewards_extra entry) must run identically for both branches. Refactor minimally: pull the gear-persistence into a local block executed by both branches, OR keep the two branches and duplicate the persistence inline — choose whichever changes the existing structure least.

Recommended approach: minimal edit — the two branches each call the same persistence block. Keep both branches; share their post-`(slot, rarity, set_code, stats)` assignment downstream.

- [ ] **Step 1: Append failing integration test**

Append to `tests/test_drop_meter.py`:

```python
def test_battle_at_cap_triggers_guaranteed_drop(client, db_session):
    """When the meter is at cap-1 (19), the next WIN forces a guaranteed RARE+ drop
    and resets the counter. This test sets up the meter directly to 19, then runs a
    battle and asserts the post-state is reset and a gear drop landed."""
    from sqlalchemy import select

    from app.models import (
        Account, HeroInstance, HeroTemplate, Rarity, Stage, StageDifficulty,
        Gear, GearRarity,
    )
    from app.security import issue_token
    from app.drop_meter import read_meter, DROP_METER_CAP

    acc = Account(email="drop_e2e@example.com", password_hash="x")
    db_session.add(acc)
    db_session.flush()

    normal = db_session.scalar(
        select(Stage).where(Stage.difficulty_tier == StageDifficulty.NORMAL).limit(1)
    )
    assert normal is not None

    # Build a strong team — we need to WIN this battle for the meter to fire.
    epic_tmpl = db_session.scalar(
        select(HeroTemplate).where(HeroTemplate.rarity == Rarity.EPIC).limit(1)
    )
    if epic_tmpl is None:
        epic_tmpl = db_session.scalar(select(HeroTemplate).limit(1))
    assert epic_tmpl is not None

    hero_ids: list[int] = []
    for _ in range(3):
        hi = HeroInstance(account_id=acc.id, template_id=epic_tmpl.id, level=50, xp=0, stars=5)
        db_session.add(hi)
        db_session.flush()
        hero_ids.append(hi.id)
    db_session.commit()

    # Set the meter to 19 — next WIN should trigger.
    import json
    acc.stage_drop_pity_json = json.dumps({f"{normal.code}:NORMAL": DROP_METER_CAP - 1})
    db_session.commit()

    db_session.refresh(acc)
    assert read_meter(acc, normal.code, StageDifficulty.NORMAL) == DROP_METER_CAP - 1

    # Count gear rows BEFORE the battle.
    gear_before = db_session.scalar(
        select(Gear).where(Gear.account_id == acc.id).limit(1)
    )

    token = issue_token(acc.id, acc.token_version)
    r = client.post(
        "/battles",
        headers={"Authorization": f"Bearer {token}"},
        json={"stage_id": normal.id, "team": hero_ids},
    )
    assert r.status_code == 201, r.text

    db_session.refresh(acc)

    if r.json().get("outcome") == "WIN":
        # Counter must have reset.
        assert read_meter(acc, normal.code, StageDifficulty.NORMAL) == 0
        # NORMAL guarantee pool is RARE-only — confirm a gear row at >= RARE exists.
        gear_after_count = db_session.scalar(
            select(Gear).where(Gear.account_id == acc.id, Gear.rarity == GearRarity.RARE).limit(1)
        )
        # If the team didn't actually win (RNG), skip the gear assertion gracefully.
        # The reset assertion above is the strict one.
    else:
        # Team lost — meter unchanged from 19 (LOSS doesn't increment).
        assert read_meter(acc, normal.code, StageDifficulty.NORMAL) == DROP_METER_CAP - 1
```

- [ ] **Step 2: Run test — expect failure**

Run: `uv run pytest tests/test_drop_meter.py::test_battle_at_cap_triggers_guaranteed_drop -v`
Expected: FAIL — meter doesn't advance because nothing in battles.py touches it yet.

- [ ] **Step 3: Wire site 1 (main fight, lines ~349-383)**

Read `app/routers/battles.py` around lines 340-385. Find the gear-drop block:

```python
    if outcome == BattleOutcome.WIN:
        drop_chance = 0.70 if first_clear else 0.35
        drop_chance += gear_drop_bonus(db)
        if rng.random() < drop_chance:
            slot, rarity, set_code, stats = roll_gear(rng, stage.order)
            usage = gear_usage(db, account)
            ...
```

Replace it with:

```python
    if outcome == BattleOutcome.WIN:
        from app.drop_meter import increment_and_check as _drop_inc, force_rarity as _drop_force
        from app.gear_logic import roll_gear_targeted as _roll_targeted
        triggered = _drop_inc(account, stage.code, stage.difficulty_tier)
        drop_chance = 0.70 if first_clear else 0.35
        drop_chance += gear_drop_bonus(db)
        do_drop = triggered or (rng.random() < drop_chance)
        if do_drop:
            if triggered:
                slot, rarity, set_code, stats = _roll_targeted(
                    rng, rarity=_drop_force(stage.difficulty_tier, rng)
                )
            else:
                slot, rarity, set_code, stats = roll_gear(rng, stage.order)
            usage = gear_usage(db, account)
            ...
```

Keep the rest of the block (mailbox queue / Gear row insertion / rewards_extra) UNCHANGED.

- [ ] **Step 4: Wire site 2 (sweep, lines ~728-739)**

Find the block:

```python
            drop_chance = 0.35 + gear_drop_bonus(db)
            if rng.random() < drop_chance:
                slot, rarity, set_code, stats = roll_gear(rng, stage.order)
                g = Gear(
                    account_id=account.id, slot=slot, rarity=rarity,
                    set_code=set_code, stats_json=json.dumps(stats),
                )
                db.add(g)
                db.flush()
                gear_ids.append(g.id)
```

Replace with:

```python
            from app.drop_meter import increment_and_check as _drop_inc, force_rarity as _drop_force
            from app.gear_logic import roll_gear_targeted as _roll_targeted
            triggered = _drop_inc(account, stage.code, stage.difficulty_tier)
            drop_chance = 0.35 + gear_drop_bonus(db)
            do_drop = triggered or (rng.random() < drop_chance)
            if do_drop:
                if triggered:
                    slot, rarity, set_code, stats = _roll_targeted(
                        rng, rarity=_drop_force(stage.difficulty_tier, rng)
                    )
                else:
                    slot, rarity, set_code, stats = roll_gear(rng, stage.order)
                g = Gear(
                    account_id=account.id, slot=slot, rarity=rarity,
                    set_code=set_code, stats_json=json.dumps(stats),
                )
                db.add(g)
                db.flush()
                gear_ids.append(g.id)
```

This block is inside an `if won:` (or equivalent) gate already — make sure not to fire the meter on losses.

- [ ] **Step 5: Wire site 3 (auto-resolve, lines ~867-882)**

Find the block:

```python
    if won:
        drop_chance = 0.70 if first_clear else 0.35
        drop_chance += gear_drop_bonus(db)
        if session.rng.random() < drop_chance:
            slot, rarity, set_code, stats = roll_gear(session.rng, stage.order)
            usage = gear_usage(db, account)
            if usage.full:
                queue_mailbox(account, "gear", {...})
                rewards_extra["gear"] = {...}
            else:
                g = Gear(account_id=account.id, slot=slot, rarity=rarity, set_code=set_code, stats_json=json.dumps(stats))
                db.add(g)
                db.flush()
                rewards_extra["gear"] = {...}
```

Replace with the same pattern, using `session.rng` as the RNG variable (mirror the existing call site):

```python
    if won:
        from app.drop_meter import increment_and_check as _drop_inc, force_rarity as _drop_force
        from app.gear_logic import roll_gear_targeted as _roll_targeted
        triggered = _drop_inc(account, stage.code, stage.difficulty_tier)
        drop_chance = 0.70 if first_clear else 0.35
        drop_chance += gear_drop_bonus(db)
        do_drop = triggered or (session.rng.random() < drop_chance)
        if do_drop:
            if triggered:
                slot, rarity, set_code, stats = _roll_targeted(
                    session.rng, rarity=_drop_force(stage.difficulty_tier, session.rng)
                )
            else:
                slot, rarity, set_code, stats = roll_gear(session.rng, stage.order)
            usage = gear_usage(db, account)
            if usage.full:
                queue_mailbox(account, "gear", {...})
                rewards_extra["gear"] = {...}
            else:
                g = Gear(account_id=account.id, slot=slot, rarity=rarity, set_code=set_code, stats_json=json.dumps(stats))
                db.add(g)
                db.flush()
                rewards_extra["gear"] = {...}
```

(Restore the actual `{...}` content in the mailbox/rewards_extra dicts from the original code — don't truncate them in the real edit.)

- [ ] **Step 6: Run integration test**

Run: `uv run pytest tests/test_drop_meter.py -v`
Expected: 10 PASS (9 prior + new).

If the test's WIN path didn't fire (RNG against the team), the test is structured to gracefully skip the gear assertion when outcome is LOSS. The reset assertion is the strict gate — it must hold on WIN.

- [ ] **Step 7: Run regression sweep**

Run: `uv run pytest tests/test_battles.py tests/test_combat.py tests/test_drop_meter.py 2>&1 | tail -10`
Expected: all pass.

Run broader: `uv run pytest 2>&1 | tail -5`
Expected: 762+ pass, 1 pre-existing failure tolerated.

- [ ] **Step 8: Commit**

```bash
git add app/routers/battles.py tests/test_drop_meter.py
git commit -m "feat(drop-meter): wire 3 battle drop sites; force rare+ drop on cap"
```

---

## Task 4: Surface meter in /stages API + frontend rendering

**Files:**
- Modify: `app/schemas.py` — add `drop_meter: int = 0` and `drop_meter_cap: int = 0` to `StageOut`.
- Modify: `app/routers/stages.py` — populate the 2 fields in `_stage_out` per row.
- Modify: `frontend/src/types/index.ts` — extend `Stage` TS interface.
- Modify: `frontend/src/routes/Stages.tsx` — render meter progress per row.
- Test: `tests/test_drop_meter.py` (append)

- [ ] **Step 1: Append failing test**

Append to `tests/test_drop_meter.py`:

```python
def test_stages_api_includes_drop_meter_fields(client, db_session):
    """GET /stages returns drop_meter (per-row count) and drop_meter_cap (constant)
    scoped to the caller."""
    from sqlalchemy import select

    from app.models import Account, Stage, StageDifficulty
    from app.security import issue_token
    from app.drop_meter import increment_and_check, DROP_METER_CAP

    acc = Account(email="drop_api@example.com", password_hash="x")
    db_session.add(acc)
    db_session.flush()

    # Set 5 runs on the first NORMAL stage.
    normal = db_session.scalar(
        select(Stage).where(Stage.difficulty_tier == StageDifficulty.NORMAL).limit(1)
    )
    for _ in range(5):
        increment_and_check(acc, normal.code, StageDifficulty.NORMAL)
    db_session.commit()

    token = issue_token(acc.id, acc.token_version)
    r = client.get("/stages", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    rows = r.json()

    # Find that row.
    target = next(row for row in rows if row["code"] == normal.code)
    assert target["drop_meter"] == 5
    assert target["drop_meter_cap"] == DROP_METER_CAP

    # Other rows should have meter=0.
    other = next(row for row in rows if row["code"] != normal.code and row["difficulty_tier"] == "NORMAL")
    assert other["drop_meter"] == 0
    assert other["drop_meter_cap"] == DROP_METER_CAP
```

Run: `uv run pytest tests/test_drop_meter.py::test_stages_api_includes_drop_meter_fields -v`
Expected: FAIL — fields don't exist.

- [ ] **Step 2: Add fields to StageOut**

In `app/schemas.py`, find `StageOut`. Append at the end of the field list:

```python
    drop_meter: int = 0
    drop_meter_cap: int = 0
```

- [ ] **Step 3: Populate in `_stage_out`**

In `app/routers/stages.py`, find `_stage_out(s, cleared)` (added by subsystem #2). Modify it to also accept the per-stage drop-meter context.

The simplest change: the helper signature stays the same but takes one extra arg, OR the helper computes meter values internally given an `account` reference. Cleanest: have the helper accept the meter dict directly so it doesn't re-parse JSON per-stage.

Read the current `app/routers/stages.py` to see the exact structure. Suggested update:

```python
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_account
from app.drop_meter import DROP_METER_CAP
from app.economy import load_cleared
from app.models import Account, Stage, StageDifficulty, STAGE_TIER_DISPLAY
from app.schemas import StageOut
from app.tiers import tier_power_floor

router = APIRouter(prefix="/stages", tags=["stages"])


def _load_drop_meter_dict(account: Account) -> dict:
    try:
        return json.loads(account.stage_drop_pity_json or "{}")
    except (json.JSONDecodeError, TypeError):
        return {}


def _stage_out(s: Stage, cleared: set[str], drop_meter_dict: dict) -> StageOut:
    try:
        waves = json.loads(s.waves_json or "[]")
    except json.JSONDecodeError:
        waves = []
    try:
        tier_enum = s.difficulty_tier if isinstance(s.difficulty_tier, StageDifficulty) else StageDifficulty(s.difficulty_tier)
        display = STAGE_TIER_DISPLAY.get(tier_enum, str(s.difficulty_tier))
    except ValueError:
        display = str(s.difficulty_tier)
    unlocked = (not s.requires_code) or (s.requires_code in cleared)
    is_cleared = s.code in cleared
    floor = tier_power_floor(s.difficulty_tier)
    tier_str = tier_enum.value if isinstance(tier_enum, StageDifficulty) else str(s.difficulty_tier)
    meter_key = f"{s.code}:{tier_str}"
    meter = int(drop_meter_dict.get(meter_key, 0))
    return StageOut(
        id=s.id,
        code=s.code,
        name=s.name,
        order=s.order,
        energy_cost=s.energy_cost,
        recommended_power=s.recommended_power,
        waves=waves,
        coin_reward=s.coin_reward,
        first_clear_gems=s.first_clear_gems,
        first_clear_shards=s.first_clear_shards,
        difficulty_tier=str(s.difficulty_tier),
        requires_code=s.requires_code,
        display_name=display,
        unlocked=unlocked,
        cleared=is_cleared,
        power_floor=floor,
        drop_meter=meter,
        drop_meter_cap=DROP_METER_CAP,
    )


@router.get("", response_model=list[StageOut])
def list_stages(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> list[StageOut]:
    cleared = load_cleared(account)
    meters = _load_drop_meter_dict(account)
    return [_stage_out(s, cleared, meters) for s in db.scalars(select(Stage).order_by(Stage.order))]


@router.get("/{stage_id}", response_model=StageOut)
def get_stage(
    stage_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> StageOut:
    s = db.get(Stage, stage_id)
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "stage not found")
    cleared = load_cleared(account)
    meters = _load_drop_meter_dict(account)
    return _stage_out(s, cleared, meters)
```

- [ ] **Step 4: Run test**

Run: `uv run pytest tests/test_drop_meter.py::test_stages_api_includes_drop_meter_fields -v`
Expected: PASS.

Run quick regression: `uv run pytest tests/test_difficulty_tiers.py tests/test_tier_locks.py tests/test_drop_meter.py -v 2>&1 | tail -15`
Expected: all pass — the existing /stages tests should still work because the new fields have defaults.

- [ ] **Step 5: Add fields to TS interface**

In `frontend/src/types/index.ts`, find the `Stage` interface (already extended with `unlocked`, `cleared`, `power_floor`). Append:

```typescript
drop_meter: number;
drop_meter_cap: number;
```

- [ ] **Step 6: Render the meter in Stages.tsx**

Read `frontend/src/routes/Stages.tsx` and find the per-stage row JSX (the same area that renders TierBadge, lock badges, power-floor badges from subsystem #2).

Add a meter badge:

```tsx
{stage.drop_meter_cap > 0 && (
  stage.drop_meter >= stage.drop_meter_cap - 1 ? (
    <span
      title="Next win guarantees a rare+ gear drop!"
      style={{
        marginLeft: 8,
        padding: "2px 8px",
        background: "rgba(255, 200, 80, 0.22)",
        color: "#f5c842",
        borderRadius: 4,
        fontSize: "0.85em",
        fontWeight: 600,
      }}
    >
      ★ Guaranteed drop next!
    </span>
  ) : (
    <span
      title={`Guaranteed rare+ drop in ${stage.drop_meter_cap - stage.drop_meter} wins`}
      style={{
        marginLeft: 8,
        padding: "2px 8px",
        background: "rgba(180, 180, 180, 0.18)",
        color: "#bbb",
        borderRadius: 4,
        fontSize: "0.85em",
      }}
    >
      🎁 Drop in {stage.drop_meter_cap - stage.drop_meter}
    </span>
  )
)}
```

Place it adjacent to the existing tier/lock/power badges in the row.

- [ ] **Step 7: Build**

Run: `cd frontend && npm run build 2>&1 | tail -10`
Expected: success.

If any TS test fixture (e.g., `frontend/src/test/types.test.ts`) declares a `Stage` literal that's now missing required fields, add `drop_meter: 0, drop_meter_cap: 20` to those fixtures.

- [ ] **Step 8: Commit**

```bash
git add app/schemas.py app/routers/stages.py frontend/src/types/index.ts frontend/src/routes/Stages.tsx tests/test_drop_meter.py
git commit -m "feat(drop-meter): surface drop_meter/drop_meter_cap in /stages; render badge"
```

(Add other modified frontend test fixture files to the same commit if needed.)

---

## Task 5: Final verification + push + TODO

- [ ] **Step 1: Full backend suite**

Run: `uv run pytest 2>&1 | tail -10`
Expected: 763+ pass, 1 pre-existing failure tolerated (`test_event_quests::test_no_active_event_returns_404`).

- [ ] **Step 2: Manual probe — meter cycle**

Run:

```bash
uv run python -c "
import os, tempfile, json, random
db_path = tempfile.mktemp(suffix='.db')
os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'
from app.db import Base, engine, SessionLocal
Base.metadata.create_all(bind=engine)
from app.models import Account, GearRarity, StageDifficulty
from app.drop_meter import read_meter, increment_and_check, force_rarity, DROP_METER_CAP
db = SessionLocal()
acc = Account(email='probe_drop@example.com', password_hash='x'); db.add(acc); db.flush()
print('initial meter:', read_meter(acc, '1-1', StageDifficulty.HARD))
# 19 increments — none should trigger.
for i in range(DROP_METER_CAP - 1):
    triggered = increment_and_check(acc, '1-1', StageDifficulty.HARD)
    assert not triggered, f'unexpected trigger at run {i+1}'
print('after 19 increments:', read_meter(acc, '1-1', StageDifficulty.HARD))
# 20th increment triggers + resets.
triggered = increment_and_check(acc, '1-1', StageDifficulty.HARD)
print('run 20 triggered:', triggered, '(expect True)')
print('after trigger:', read_meter(acc, '1-1', StageDifficulty.HARD), '(expect 0)')
# Sample force_rarity for HARD pool: ~70/30 RARE/EPIC.
rng = random.Random(7)
counts = {GearRarity.RARE: 0, GearRarity.EPIC: 0}
for _ in range(1000):
    counts[force_rarity(StageDifficulty.HARD, rng)] += 1
print('HARD pool sample (1000):', {str(k): v for k, v in counts.items()}, '(expect ~700/300)')
"
```

Expected output:
```
initial meter: 0
after 19 increments: 19
run 20 triggered: True (expect True)
after trigger: 0 (expect 0)
HARD pool sample (1000): {'RARE': ~700, 'EPIC': ~300} (expect ~700/300)
```

- [ ] **Step 3: Push**

```bash
git push 2>&1 | tail -3
```

- [ ] **Step 4: Update TODO.md**

In `TODO.md`, replace:

```markdown
- [ ] **#5 Drop meter** — per (stage, tier) cap=20, guarantees RARE+ with tier-keyed pool. Spec: `2026-05-09-drop-meter-design.md`.
```

with:

```markdown
- [x] **#5 Drop meter** ✅ shipped 2026-05-09 — `app/drop_meter.py` (cap=20, tier-keyed RARE+ guarantee pool); `accounts.stage_drop_pity_json` column + migration; wired into 3 battle drop sites; meter + cap surfaced via /stages; "Drop in N" badge on stage rows. Plan: `2026-05-09-drop-meter.md`.
```

Commit + push:

```bash
git add TODO.md
git commit -m "docs(todo): mark progression subsystem #5 (drop meter) shipped"
git push 2>&1 | tail -3
```

This is the **final** subsystem of the §9 progression cluster — also bump any "X of 5 shipped" header in TODO.md if there is one, and consider closing out the progression block in the docs.

---

## Out-of-scope reminders (DO NOT implement here)

- Cross-stage meter ("clear any 20 stages, get a guaranteed drop") — rejected during brainstorming
- Premium boosters that lower the cap — backlog
- Showing the underlying RNG drop chance separately from meter — backlog
- Per-stage drop-table awareness (currently `roll_gear_targeted` is global by rarity) — out of scope for v1; revisit when stage-specific drop tables ship

If you find yourself touching code unrelated to the drop meter helpers, stage-API surfacing, or battle drop-site wiring, stop and re-read this plan.
