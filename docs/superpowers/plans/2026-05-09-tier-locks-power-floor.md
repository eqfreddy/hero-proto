# Tier Locks + Power Floor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enforce minimum-team-power floors on NIGHTMARE (50k) and LEGENDARY (100k) tier battles, and surface unlock/clear state per stage via the `/stages` API so the frontend can render lock icons and power-floor warnings.

**Architecture:** Tier-lock CHAIN is already enforced via the existing `Stage.requires_code` field + `load_cleared()` helper (in `app/economy.py`) — that infrastructure shipped before this plan. This plan adds (1) a tier→power-floor lookup and a battle-start guard that rejects under-powered teams with HTTP 400 before energy is consumed, and (2) per-account `unlocked`/`cleared`/`power_floor` fields on the `/stages` response by making the endpoint authenticated and joining against the caller's cleared set.

**Tech Stack:** Python 3.13 + FastAPI + SQLAlchemy 2.0. Tests via `uv run pytest`. No DB schema changes — all state is derived from existing columns.

**Spec:** `docs/superpowers/specs/2026-05-09-tier-locks-power-floor-design.md`

**Reference (grounded codebase facts):**
- `app/models.py:185-196` — `StageDifficulty` enum + `STAGE_TIER_DISPLAY` (subsystem #1 already shipped)
- `app/models.py:216` — `Account.stages_cleared_json` is the source of truth for clear state
- `app/models.py:472` — `Stage.requires_code` set by subsystem #1 seed (HARD→NORMAL, NIGHTMARE→HARD, LEGENDARY→NIGHTMARE)
- `app/economy.py:216` — `load_cleared(account) -> set[str]`
- `app/economy.py:228` — `mark_cleared(account, stage_code) -> bool`
- `app/routers/battles.py:104-109` — existing tier-lock check fires before combat
- `app/routers/battles.py:137` — `team_a = [_unit_from_instance(h, "A", i) for i, h in enumerate(heroes)]`
- `app/combat.py:1105` — `unit_power(u: CombatUnit) -> int`
- `app/routers/stages.py` — currently unauthenticated; Task 3 makes it auth'd
- `app/schemas.py` — `StageOut` (subsystem #1 added `display_name`)

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `app/tiers.py` | NEW — `TIER_POWER_FLOOR` constant + `tier_power_floor(tier)` helper. Keeps tier-policy constants out of `account_level.py` so future tier policy (drop pity, fail pity multipliers) has a clean home. | Create |
| `app/routers/battles.py` | Hoist team-build above `consume_energy`; insert power-floor check; raise HTTP 400 with `required` + `current` on violation. | Modify |
| `app/schemas.py` | Add `unlocked: bool`, `cleared: bool`, `power_floor: int \| None` to `StageOut`. | Modify |
| `app/routers/stages.py` | Switch endpoint to auth'd; compute `unlocked`/`cleared`/`power_floor` per stage from `load_cleared(account)` + tier-floor helper. | Modify |
| `frontend/src/types/index.ts` | Add the 3 new fields to the `Stage` interface. | Modify |
| `frontend/src/routes/Stages.tsx` | Render lock state + power-floor warning on each stage row. | Modify |
| `tests/test_tier_locks.py` | NEW — covers power-floor helper, battle-start rejection, `/stages` field surfacing. | Create |

---

## Task 1: Power-floor constant + helper

**Files:**
- Create: `app/tiers.py`
- Test: `tests/test_tier_locks.py` (create)

- [ ] **Step 1: Write the failing test**

Create `tests/test_tier_locks.py`:

```python
"""Tier-lock + power-floor tests."""
from app.models import StageDifficulty
from app.tiers import TIER_POWER_FLOOR, tier_power_floor


def test_power_floor_constants():
    assert TIER_POWER_FLOOR[StageDifficulty.NIGHTMARE] == 50_000
    assert TIER_POWER_FLOOR[StageDifficulty.LEGENDARY] == 100_000
    # NORMAL and HARD have no floor.
    assert StageDifficulty.NORMAL not in TIER_POWER_FLOOR
    assert StageDifficulty.HARD not in TIER_POWER_FLOOR


def test_tier_power_floor_helper():
    assert tier_power_floor(StageDifficulty.NORMAL) is None
    assert tier_power_floor(StageDifficulty.HARD) is None
    assert tier_power_floor(StageDifficulty.NIGHTMARE) == 50_000
    assert tier_power_floor(StageDifficulty.LEGENDARY) == 100_000
    # String inputs accepted (for symmetry with xp_per_win).
    assert tier_power_floor("NIGHTMARE") == 50_000
    assert tier_power_floor("BOGUS") is None
    assert tier_power_floor("") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tier_locks.py -v`
Expected: FAIL with `ImportError: cannot import name 'TIER_POWER_FLOOR' from 'app.tiers'` (the module doesn't exist yet).

- [ ] **Step 3: Create app/tiers.py**

```python
"""Per-tier policy constants and helpers.

Lives separately from app/account_level.py (which owns XP-only concerns)
so each future progression subsystem (fail pity, drop meter) has a
single home for its tier-keyed knobs.
"""
from __future__ import annotations

from app.models import StageDifficulty

# Minimum team power required to start a battle at the given tier.
# Tiers absent from this dict have no floor.
TIER_POWER_FLOOR: dict[StageDifficulty, int] = {
    StageDifficulty.NIGHTMARE: 50_000,
    StageDifficulty.LEGENDARY: 100_000,
}


def tier_power_floor(tier: StageDifficulty | str) -> int | None:
    """Return the minimum team power for a tier, or None if no floor applies.
    Accepts enum or string. Returns None for unknown tiers."""
    try:
        key = tier if isinstance(tier, StageDifficulty) else StageDifficulty(tier)
    except ValueError:
        return None
    return TIER_POWER_FLOOR.get(key)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_tier_locks.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add app/tiers.py tests/test_tier_locks.py
git commit -m "feat(tier-locks): TIER_POWER_FLOOR constants + helper"
```

---

## Task 2: Battle-start power-floor check

**Files:**
- Modify: `app/routers/battles.py` (the `fight()` endpoint, around lines 100-140)
- Test: `tests/test_tier_locks.py` (append)

**Context:** The current flow in `fight()` is:
1. Load stage (line 100)
2. Check `stage.requires_code` against cleared set — existing tier-lock chain (lines 104-109)
3. Load player team (lines 112-117)
4. Consume energy (line 119)
5. Build `team_a` units (line 137)
6. Simulate combat

We need to insert a power-floor check between steps 3 and 4 — after the team is loaded so we can compute power, but before energy is consumed (rejected battles shouldn't burn energy). To compute power without burning extra cycles, we hoist the `team_a` build (currently step 5) up to right after the team load.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tier_locks.py`:

```python
import json
from fastapi import HTTPException


def test_legendary_battle_rejects_underpowered_team(client, db_session):
    """A LEGENDARY battle with team power < 100k returns HTTP 400 with required+current."""
    from app.models import Account, HeroInstance, HeroTemplate, Rarity, Stage, StageDifficulty
    from app.economy import mark_cleared

    # Set up an account with low-power heroes and a LEGENDARY stage.
    acc = Account(email="floor_test@test.local", password_hash="x")
    db_session.add(acc)
    db_session.flush()

    # Find any LEGENDARY stage in the seeded set.
    from sqlalchemy import select
    leg = db_session.scalar(
        select(Stage).where(Stage.difficulty_tier == StageDifficulty.LEGENDARY).limit(1)
    )
    assert leg is not None, "seed must include LEGENDARY stages"

    # Pre-clear the chain so the requires_code check doesn't block first.
    # LEGENDARY's requires_code points to its NIGHTMARE sibling.
    if leg.requires_code:
        mark_cleared(acc, leg.requires_code)
        # And clear the chain back: NIGHTMARE requires HARD, HARD requires NORMAL.
        nm = db_session.scalar(select(Stage).where(Stage.code == leg.requires_code))
        if nm and nm.requires_code:
            mark_cleared(acc, nm.requires_code)
            hard = db_session.scalar(select(Stage).where(Stage.code == nm.requires_code))
            if hard and hard.requires_code:
                mark_cleared(acc, hard.requires_code)

    # Give the account 5 minimal-power heroes (level 1 commons).
    common_tmpl = db_session.scalar(
        select(HeroTemplate).where(HeroTemplate.rarity == Rarity.COMMON).limit(1)
    )
    assert common_tmpl is not None
    hero_ids: list[int] = []
    for _ in range(5):
        hi = HeroInstance(account_id=acc.id, template_id=common_tmpl.id, level=1, xp=0)
        db_session.add(hi)
        db_session.flush()
        hero_ids.append(hi.id)
    db_session.commit()

    # Authenticate this client as the new account. Use whatever token-issuance
    # helper conftest.py provides — fall back to direct token issuance:
    from app.auth_tokens import issue_token
    token = issue_token(acc.id, acc.token_version)
    r = client.post(
        "/battles",
        headers={"Authorization": f"Bearer {token}"},
        json={"stage_id": leg.id, "team": hero_ids},
    )
    assert r.status_code == 400, r.text
    body = r.json()
    detail = body["detail"]
    # Detail may be a string or a dict — accept either, but require the floor info.
    if isinstance(detail, dict):
        assert detail["required"] == 100_000
        assert detail["current"] < 100_000
    else:
        assert "100" in detail or "power" in detail.lower()
```

> **Note on auth helper:** the import path `app.auth_tokens` may differ — inspect `tests/conftest.py` and other test files (e.g., `tests/test_quests.py`, `tests/test_difficulty_tiers.py`) to see how authenticated requests are issued. Match the existing pattern. If the project provides an `authed_client` fixture, prefer it.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_tier_locks.py::test_legendary_battle_rejects_underpowered_team -v`
Expected: FAIL — likely the battle currently runs without checking power, returning 201.

- [ ] **Step 3: Modify battles.py — hoist team_a build + add power-floor check**

In `app/routers/battles.py`, the current code (around lines 110-140) looks like:

```python
    # Load player team (must all be owned).
    heroes: list[HeroInstance] = []
    for hid in body.team:
        h = db.get(HeroInstance, hid)
        if h is None or h.account_id != account.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"hero {hid} not owned")
        heroes.append(h)

    if not consume_energy(account, stage.energy_cost):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"not enough energy (need {stage.energy_cost})",
        )

    # ... analytics + waves loading ...

    waves = json.loads(stage.waves_json or "[]")
    # Build the persistent player team once; it rolls through all waves keeping HP damage.
    team_a = [_unit_from_instance(h, "A", i) for i, h in enumerate(heroes)]
```

Replace with:

```python
    # Load player team (must all be owned).
    heroes: list[HeroInstance] = []
    for hid in body.team:
        h = db.get(HeroInstance, hid)
        if h is None or h.account_id != account.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"hero {hid} not owned")
        heroes.append(h)

    # Build the persistent player team early so we can compute team power
    # before any energy is consumed; under-powered teams on high-tier stages
    # get rejected upfront.
    team_a = [_unit_from_instance(h, "A", i) for i, h in enumerate(heroes)]

    # Power-floor enforcement on NIGHTMARE/LEGENDARY tiers.
    from app.tiers import tier_power_floor as _tier_floor
    from app.combat import unit_power as _unit_power
    floor = _tier_floor(stage.difficulty_tier)
    if floor is not None:
        team_power = sum(_unit_power(u) for u in team_a)
        if team_power < floor:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                {
                    "detail": "team power below tier floor",
                    "required": floor,
                    "current": team_power,
                },
            )

    if not consume_energy(account, stage.energy_cost):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"not enough energy (need {stage.energy_cost})",
        )

    # ... analytics + waves loading (unchanged) ...

    waves = json.loads(stage.waves_json or "[]")
    # team_a was built above (hoisted for power-floor check).
```

CRITICAL: keep the rest of the function identical. The only changes are:
1. Move `team_a = [...]` from after `waves = ...` to right after the heroes loop.
2. Add the `from app.tiers import ...` + `from app.combat import ...` + `floor = ...` block right after `team_a` is built.
3. Remove the duplicate `team_a = [...]` line that previously came after `waves = json.loads(...)`.

Read carefully before editing — make sure you don't end up with two `team_a` assignments.

- [ ] **Step 4: Run the test**

Run: `uv run pytest tests/test_tier_locks.py::test_legendary_battle_rejects_underpowered_team -v`
Expected: PASS.

- [ ] **Step 5: Run battle suite for regression**

Run: `uv run pytest tests/test_battles.py tests/test_combat.py 2>&1 | tail -10`
Expected: previously-passing tests still pass. The hoist of `team_a` should be transparent to existing tests.

If any test fails because it built a low-power team to fight a non-NORMAL stage, that test was relying on the absence of a floor — these failures are LEGITIMATE and indicate the feature is working. Update the test to either give the test team enough power or to fight a NORMAL stage. Note any such adjustments in your report.

- [ ] **Step 6: Commit**

```bash
git add app/routers/battles.py tests/test_tier_locks.py
git commit -m "feat(tier-locks): power-floor check at battle start (NIGHTMARE 50k / LEGENDARY 100k)"
```

---

## Task 3: Surface unlocked/cleared/power_floor in /stages API

**Files:**
- Modify: `app/schemas.py` — add 3 fields to `StageOut`
- Modify: `app/routers/stages.py` — make endpoint auth'd, compute the 3 fields per stage
- Test: `tests/test_tier_locks.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_tier_locks.py`:

```python
def test_stages_api_includes_unlock_state(client, db_session):
    """GET /stages returns unlocked/cleared/power_floor per row, scoped to the caller."""
    from app.models import Account, StageDifficulty
    from app.economy import mark_cleared
    from app.auth_tokens import issue_token

    acc = Account(email="stage_state@test.local", password_hash="x")
    db_session.add(acc)
    db_session.flush()
    db_session.commit()

    token = issue_token(acc.id, acc.token_version)
    r = client.get("/stages", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) > 0

    for row in rows:
        assert "unlocked" in row, f"missing unlocked on {row['code']}"
        assert "cleared" in row, f"missing cleared on {row['code']}"
        assert "power_floor" in row, f"missing power_floor on {row['code']}"

    # Spot checks:
    # - NORMAL stages should be unlocked, not cleared, no power floor.
    normal = next(r for r in rows if r["difficulty_tier"] == "NORMAL")
    assert normal["unlocked"] is True
    assert normal["cleared"] is False
    assert normal["power_floor"] is None

    # - HARD stages should be locked (NORMAL not cleared), no floor.
    hard = next(r for r in rows if r["difficulty_tier"] == "HARD")
    assert hard["unlocked"] is False
    assert hard["power_floor"] is None

    # - NIGHTMARE / LEGENDARY have power floors.
    nightmare = next(r for r in rows if r["difficulty_tier"] == "NIGHTMARE")
    assert nightmare["power_floor"] == 50_000
    legendary = next(r for r in rows if r["difficulty_tier"] == "LEGENDARY")
    assert legendary["power_floor"] == 100_000


def test_stages_api_unlocks_after_clear(client, db_session):
    """After clearing a NORMAL stage, its HARD sibling becomes unlocked."""
    from app.models import Account, Stage, StageDifficulty
    from app.economy import mark_cleared
    from app.auth_tokens import issue_token
    from sqlalchemy import select

    acc = Account(email="unlock_test@test.local", password_hash="x")
    db_session.add(acc)
    db_session.flush()

    # Find a NORMAL stage and its HARD sibling.
    normal = db_session.scalar(
        select(Stage).where(Stage.difficulty_tier == StageDifficulty.NORMAL).limit(1)
    )
    hard = db_session.scalar(select(Stage).where(Stage.code == f"H-{normal.code}"))
    assert hard is not None

    mark_cleared(acc, normal.code)
    db_session.commit()

    token = issue_token(acc.id, acc.token_version)
    r = client.get("/stages", headers={"Authorization": f"Bearer {token}"})
    rows = r.json()

    normal_row = next(r for r in rows if r["code"] == normal.code)
    hard_row = next(r for r in rows if r["code"] == hard.code)

    assert normal_row["cleared"] is True
    assert hard_row["unlocked"] is True
    assert hard_row["cleared"] is False
```

- [ ] **Step 2: Run tests — expect failure**

Run: `uv run pytest tests/test_tier_locks.py -k "stages_api" -v`
Expected: FAIL — fields don't exist on the response yet.

- [ ] **Step 3: Add fields to StageOut**

In `app/schemas.py`, find the `StageOut` model. Append three new fields at the end of the field list:

```python
    unlocked: bool = True
    cleared: bool = False
    power_floor: int | None = None
```

Defaults are chosen for safety: if `stage_out` ever skips populating them, the response says "unlocked, not cleared, no floor" — the most permissive default.

- [ ] **Step 4: Make /stages auth'd and compute new fields**

Replace the contents of `app/routers/stages.py`. Read the current file first to preserve any imports / decorators. The new logic:

```python
import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import get_current_account
from app.economy import load_cleared
from app.models import Account, Stage, StageDifficulty, STAGE_TIER_DISPLAY
from app.schemas import StageOut
from app.tiers import tier_power_floor

router = APIRouter(prefix="/stages", tags=["stages"])


def _stage_out(s: Stage, cleared: set[str]) -> StageOut:
    try:
        waves = json.loads(s.waves_json or "[]")
    except json.JSONDecodeError:
        waves = []
    # Resolve display name; fall back to enum string if tier is unknown.
    try:
        tier_enum = s.difficulty_tier if isinstance(s.difficulty_tier, StageDifficulty) else StageDifficulty(s.difficulty_tier)
        display = STAGE_TIER_DISPLAY.get(tier_enum, str(s.difficulty_tier))
    except ValueError:
        display = str(s.difficulty_tier)
    # Lock state: a stage is unlocked when it has no prereq, OR its prereq is cleared.
    unlocked = (not s.requires_code) or (s.requires_code in cleared)
    is_cleared = s.code in cleared
    floor = tier_power_floor(s.difficulty_tier)
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
    )


@router.get("", response_model=list[StageOut])
def list_stages(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> list[StageOut]:
    cleared = load_cleared(account)
    return [_stage_out(s, cleared) for s in db.scalars(select(Stage).order_by(Stage.order))]


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
    return _stage_out(s, cleared)
```

Notes:
- The existing top-level `stage_out` (without underscore) is replaced by `_stage_out` (private to this module) since it now requires per-account context. Anything outside this file that imported `stage_out` will break — search the codebase for `from app.routers.stages import stage_out` and check.
- Both endpoints now require auth. If any frontend code currently calls `/stages` without a token, it will start getting 401s — that's expected for the new contract.

- [ ] **Step 5: Search for external uses of the old stage_out**

Run: `grep -rn "from app.routers.stages import\|stages.stage_out\|stages\.stage_out" --include="*.py" .`

If any other module imported `stage_out`, update them to use the new `_stage_out` (and pass a `cleared` set) OR move `_stage_out` back to a public name and accept the new signature. Most likely: nothing imports it — the function is only used inside the router.

- [ ] **Step 6: Run tests**

Run: `uv run pytest tests/test_tier_locks.py tests/test_difficulty_tiers.py -v 2>&1 | tail -20`
Expected: all PASS, including the existing `test_stages_api_returns_display_name` from subsystem #1 (which uses the `client` fixture — verify it still works with the auth requirement; if it now fails with 401, update that single test to send a token).

- [ ] **Step 7: Run a regression sweep**

Run: `uv run pytest tests/ -k "stage" 2>&1 | tail -10`
Expected: stage-related tests pass. If anything fails because it called `/stages` unauthenticated, update those tests to authenticate.

- [ ] **Step 8: Commit**

```bash
git add app/schemas.py app/routers/stages.py tests/test_tier_locks.py
git commit -m "feat(tier-locks): surface unlocked/cleared/power_floor in /stages API"
```

If you had to update other tests for the new auth requirement, include them in the same commit and note in the report.

---

## Task 4: Frontend — render lock state + power-floor warning

**Files:**
- Modify: `frontend/src/types/index.ts` — extend `Stage` interface with `unlocked: boolean; cleared: boolean; power_floor: number | null;`
- Modify: `frontend/src/routes/Stages.tsx` — render lock icon + power-floor warning per row
- Test: existing build + smoke

- [ ] **Step 1: Read current Stages.tsx**

Run: `cd frontend/src/routes && grep -n "stage" Stages.tsx | head -20`

Find the per-row rendering — particularly the Battle button and any existing "locked" / "tier" affordances.

- [ ] **Step 2: Add fields to Stage TS type**

In `frontend/src/types/index.ts`, find the `Stage` interface (added `display_name` in subsystem #1). Append:

```typescript
unlocked: boolean;
cleared: boolean;
power_floor: number | null;
```

at the end of the field list, preserving order.

- [ ] **Step 3: Render lock state and power-floor warning**

In `frontend/src/routes/Stages.tsx`, near the per-stage row rendering, gate the Battle button on `stage.unlocked` AND `team_power >= stage.power_floor (if set)`. The team-power computation likely already happens elsewhere — find where the Battle button is rendered and wrap it.

Minimal change pattern (adapt to actual JSX):

```tsx
const teamPower = computeTeamPower(currentTeam);  // reuse existing fn
const lockReason = !stage.unlocked
  ? `Clear ${stage.requires_code} first`
  : stage.power_floor && teamPower < stage.power_floor
    ? `Need ${stage.power_floor.toLocaleString()} power (you have ${teamPower.toLocaleString()})`
    : null;

// In the row JSX:
{lockReason ? (
  <span className="stage-lock" title={lockReason}>🔒 {lockReason}</span>
) : (
  <button onClick={() => fight(stage)}>Battle</button>
)}
```

If `computeTeamPower` doesn't exist with that exact name, look for the existing power calculation in the frontend (probably in `frontend/src/store/` or a hook). Use whatever the existing code uses.

If team-power calculation is too far afield, simplify Step 3 to ONLY gate on `stage.unlocked` and show the power-floor as a SOFT badge ("Min 100k power") rather than a hard pre-flight check — server enforcement is the safety net. Note in your report which approach you took.

- [ ] **Step 4: TypeScript build check**

Run: `cd frontend && npm run build 2>&1 | tail -10`
Expected: success.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/routes/Stages.tsx
git commit -m "feat(tier-locks): render lock state + power-floor on stage rows"
```

If you touched additional frontend files (e.g., a TierBadge tweak, a power-calc helper), add them here.

---

## Task 5: Final verification + push

**Files:** none (verification only)

- [ ] **Step 1: Full backend suite**

Run: `uv run pytest 2>&1 | tail -10`
Expected: 731+/732+ pass (1 pre-existing unrelated failure in `test_event_quests` is OK).

- [ ] **Step 2: Manual /stages probe**

Run:
```bash
uv run python -c "
import os, tempfile
db_path = tempfile.mktemp(suffix='.db')
os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'
from app.db import Base, engine, SessionLocal
Base.metadata.create_all(bind=engine)
from app.seed import seed
seed()
from sqlalchemy import select
from app.models import Account, Stage, StageDifficulty
from app.economy import load_cleared
from app.tiers import tier_power_floor
db = SessionLocal()
acc = Account(email='probe@test.local', password_hash='x')
db.add(acc); db.flush()
cleared = load_cleared(acc)
for tier in StageDifficulty:
    s = db.scalar(select(Stage).where(Stage.difficulty_tier == tier).limit(1))
    if s is None: continue
    unlocked = (not s.requires_code) or (s.requires_code in cleared)
    floor = tier_power_floor(s.difficulty_tier)
    print(f'{tier.value}: code={s.code!r} requires={s.requires_code!r} unlocked={unlocked} floor={floor}')
"
```

Expected output:
```
NORMAL: code='1-1' requires='' unlocked=True floor=None
HARD: code='H-1-1' requires='1-1' unlocked=False floor=None
NIGHTMARE: code='N-1-1' requires='H-1-1' unlocked=False floor=50000
LEGENDARY: code='L-1-1' requires='N-1-1' unlocked=False floor=100000
```

(Stage codes will match whatever the first seeded stage is. Important: `floor` matches the spec for NIGHTMARE/LEGENDARY, and `unlocked` correctly reflects the chain.)

- [ ] **Step 3: Push**

```bash
git push 2>&1 | tail -3
```

---

## Out-of-scope reminders (DO NOT implement here)

- Fail pity (subsystem #3)
- Rest XP (subsystem #4)
- Drop meter (subsystem #5)
- Auto-unlock toast notifications (backlog)
- Per-stage power floor (rejected during brainstorming — global thresholds chosen)

If you find yourself touching code unrelated to power-floor enforcement or `/stages` field surfacing, stop and re-read this plan.
