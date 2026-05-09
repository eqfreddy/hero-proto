# Difficulty Tiers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a 4th difficulty tier (LEGENDARY) to the existing stage system, with tier-keyed XP rewards (12/28/50/60), per-tier display names (Floppy / Hard Disk / RAID-0 / Legen'waitforit'dary), and seed-time generation of LEGENDARY variants for every existing NORMAL stage.

**Architecture:** Extend the `StageDifficulty` enum (string-backed, no DB schema change). Move the hardcoded `XP_PER_BATTLE_WIN = 12` constant into a tier-keyed lookup, called from the two `battles.py` win-XP grant sites. Extend the existing per-stage seed loop in `app/seed.py` to emit `L-<code>` rows alongside the existing `H-` and `N-` rows, using the established level-bump pattern (NORMAL+0 / HARD+10 / NIGHTMARE+20 / **LEGENDARY+30**) and a 3.5× reward multiplier consistent with the 1.5×/2.5× progression. Add a server-side display-name map surfaced via `/stages`.

**Tech Stack:** Python 3.13 + FastAPI + SQLAlchemy 2.0 + Alembic. Tests via `uv run pytest` (configured in `pyproject.toml`). No DB schema migration — `Stage.difficulty_tier` is `String(16)` so adding a new enum value requires no DDL.

**Spec:** `docs/superpowers/specs/2026-05-09-difficulty-tiers-design.md`

**Reference (grounded codebase facts):**
- `app/models.py:185-188` — current `StageDifficulty(NORMAL/HARD/NIGHTMARE)`
- `app/models.py:442-463` — `Stage` model; `code`, `difficulty_tier` (`String(16)`), `requires_code`
- `app/seed.py:1398-1464` — existing per-stage tier emission loop
- `app/account_level.py:24` — `XP_PER_BATTLE_WIN = 12`
- `app/routers/battles.py:272-278` and `:854-855` — two XP-grant sites
- `app/routers/stages.py` — stage list/detail endpoints
- `app/schemas.py` — `StageOut` Pydantic model

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `app/models.py` | Add `LEGENDARY` to `StageDifficulty` enum + add `STAGE_TIER_DISPLAY` dict | Modify |
| `app/account_level.py` | Add `XP_PER_BATTLE_WIN_BY_TIER` lookup; keep `XP_PER_BATTLE_WIN` as backward-compat alias for NORMAL | Modify |
| `app/routers/battles.py` | Replace hardcoded `XP_PER_BATTLE_WIN` use with tier-keyed lookup at both win-XP sites | Modify |
| `app/routers/stages.py` | Surface `display_name` in `StageOut` response | Modify |
| `app/schemas.py` | Add `display_name: str` to `StageOut` | Modify |
| `app/seed.py` | Add LEGENDARY block to per-stage seed loop | Modify |
| `tests/test_difficulty_tiers.py` | New test file covering all 5 surfaces | Create |

---

## Task 1: Add LEGENDARY to StageDifficulty enum + display-name map

**Files:**
- Modify: `app/models.py:185-188`
- Test: `tests/test_difficulty_tiers.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_difficulty_tiers.py`:

```python
"""Difficulty tier system — enum, display names, XP table, seed."""
from app.models import StageDifficulty, STAGE_TIER_DISPLAY


def test_legendary_in_enum():
    assert StageDifficulty.LEGENDARY == "LEGENDARY"
    assert {t.value for t in StageDifficulty} == {"NORMAL", "HARD", "NIGHTMARE", "LEGENDARY"}


def test_display_names_cover_all_tiers():
    assert STAGE_TIER_DISPLAY[StageDifficulty.NORMAL] == "Floppy"
    assert STAGE_TIER_DISPLAY[StageDifficulty.HARD] == "Hard Disk"
    assert STAGE_TIER_DISPLAY[StageDifficulty.NIGHTMARE] == "RAID-0"
    assert STAGE_TIER_DISPLAY[StageDifficulty.LEGENDARY] == "Legen'waitforit'dary"
    # Every enum value must have a display name.
    for t in StageDifficulty:
        assert t in STAGE_TIER_DISPLAY
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_difficulty_tiers.py -v`
Expected: FAIL with `ImportError` (LEGENDARY doesn't exist yet) or `AssertionError`.

- [ ] **Step 3: Add LEGENDARY enum value + display map**

In `app/models.py`, replace lines 185-188:

```python
class StageDifficulty(StrEnum):
    NORMAL = "NORMAL"
    HARD = "HARD"
    NIGHTMARE = "NIGHTMARE"
    LEGENDARY = "LEGENDARY"


STAGE_TIER_DISPLAY: dict[StageDifficulty, str] = {
    StageDifficulty.NORMAL:    "Floppy",
    StageDifficulty.HARD:      "Hard Disk",
    StageDifficulty.NIGHTMARE: "RAID-0",
    StageDifficulty.LEGENDARY: "Legen'waitforit'dary",
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_difficulty_tiers.py -v`
Expected: PASS for `test_legendary_in_enum` and `test_display_names_cover_all_tiers`.

- [ ] **Step 5: Commit**

```bash
git add app/models.py tests/test_difficulty_tiers.py
git commit -m "feat(tiers): add LEGENDARY enum + display-name map"
```

---

## Task 2: Tier-keyed XP table in account_level.py

**Files:**
- Modify: `app/account_level.py:24` (the `XP_PER_BATTLE_WIN = 12` line)
- Test: `tests/test_difficulty_tiers.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_difficulty_tiers.py`:

```python
from app.account_level import XP_PER_BATTLE_WIN, XP_PER_BATTLE_WIN_BY_TIER, xp_per_win


def test_xp_table_values():
    assert XP_PER_BATTLE_WIN_BY_TIER[StageDifficulty.NORMAL]    == 12
    assert XP_PER_BATTLE_WIN_BY_TIER[StageDifficulty.HARD]      == 28
    assert XP_PER_BATTLE_WIN_BY_TIER[StageDifficulty.NIGHTMARE] == 50
    assert XP_PER_BATTLE_WIN_BY_TIER[StageDifficulty.LEGENDARY] == 60


def test_xp_per_win_helper():
    assert xp_per_win(StageDifficulty.NORMAL)    == 12
    assert xp_per_win(StageDifficulty.LEGENDARY) == 60
    # Legacy constant kept as NORMAL alias.
    assert XP_PER_BATTLE_WIN == 12
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_difficulty_tiers.py::test_xp_table_values tests/test_difficulty_tiers.py::test_xp_per_win_helper -v`
Expected: FAIL with `ImportError` for `XP_PER_BATTLE_WIN_BY_TIER` / `xp_per_win`.

- [ ] **Step 3: Add the tier table + helper**

In `app/account_level.py`, locate line 24 (`XP_PER_BATTLE_WIN = 12`) and replace with:

```python
from app.models import StageDifficulty

# Tier-keyed XP per battle win.
XP_PER_BATTLE_WIN_BY_TIER: dict[StageDifficulty, int] = {
    StageDifficulty.NORMAL:    12,
    StageDifficulty.HARD:      28,
    StageDifficulty.NIGHTMARE: 50,
    StageDifficulty.LEGENDARY: 60,
}

# Backward-compat alias — equivalent to NORMAL tier.
XP_PER_BATTLE_WIN = XP_PER_BATTLE_WIN_BY_TIER[StageDifficulty.NORMAL]


def xp_per_win(tier: StageDifficulty | str) -> int:
    """Look up XP-per-battle-win for a tier. Accepts enum or string.
    Falls back to NORMAL (12) for unknown tiers — defensive default."""
    try:
        key = tier if isinstance(tier, StageDifficulty) else StageDifficulty(tier)
    except ValueError:
        return XP_PER_BATTLE_WIN_BY_TIER[StageDifficulty.NORMAL]
    return XP_PER_BATTLE_WIN_BY_TIER.get(key, XP_PER_BATTLE_WIN_BY_TIER[StageDifficulty.NORMAL])
```

If `app/account_level.py` already imports anything from `app.models`, just add `StageDifficulty` to the existing import line rather than adding a new line.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_difficulty_tiers.py -v`
Expected: 4 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add app/account_level.py tests/test_difficulty_tiers.py
git commit -m "feat(tiers): tier-keyed XP table (12/28/50/60)"
```

---

## Task 3: Wire tier-keyed XP into battles.py grant sites

**Files:**
- Modify: `app/routers/battles.py:272-278` (first grant site)
- Modify: `app/routers/battles.py:854-855` (second grant site)
- Test: `tests/test_difficulty_tiers.py` (append)

**Context:** Both grant sites currently look like:

```python
from app.account_level import XP_PER_BATTLE_WIN, XP_PER_FIRST_CLEAR, grant_xp as _grant_xp
levelups = _grant_xp(
    db, account,
    XP_PER_BATTLE_WIN + (XP_PER_FIRST_CLEAR if first_clear else 0),
)
```

The change is to use `xp_per_win(stage.difficulty_tier)` instead of the hardcoded `XP_PER_BATTLE_WIN`.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_difficulty_tiers.py`:

```python
def test_xp_grant_lookup_per_tier():
    """Sanity check: tier→XP lookup hits expected values for all four tiers.
    The actual battle-resolve grant sites are covered by the existing battle
    test suite (regression run in Step 5)."""
    from app.account_level import xp_per_win

    for tier, expected in [
        (StageDifficulty.NORMAL,    12),
        (StageDifficulty.HARD,      28),
        (StageDifficulty.NIGHTMARE, 50),
        (StageDifficulty.LEGENDARY, 60),
    ]:
        assert xp_per_win(tier) == expected
```

- [ ] **Step 2: Run the new test**

Run: `uv run pytest tests/test_difficulty_tiers.py::test_xp_grant_lookup_per_tier -v`
Expected: PASS — this test passes immediately because Task 2 already provided `xp_per_win`. It exists to lock the tier→XP contract before we change call sites in `battles.py`.

- [ ] **Step 3: Update first grant site (`battles.py:272-278`)**

Find the block:

```python
from app.account_level import (
    XP_PER_BATTLE_WIN, XP_PER_FIRST_CLEAR,
    grant_xp as _grant_xp,
)
levelups = _grant_xp(
    db, account,
    XP_PER_BATTLE_WIN + (XP_PER_FIRST_CLEAR if first_clear else 0),
)
```

Replace with:

```python
from app.account_level import (
    xp_per_win as _xp_per_win,
    XP_PER_FIRST_CLEAR,
    grant_xp as _grant_xp,
)
levelups = _grant_xp(
    db, account,
    _xp_per_win(stage.difficulty_tier) + (XP_PER_FIRST_CLEAR if first_clear else 0),
)
```

- [ ] **Step 4: Update second grant site (`battles.py:854-855`)**

Find:

```python
from app.account_level import XP_PER_BATTLE_WIN, XP_PER_FIRST_CLEAR, grant_xp as _gxp
levelups = _gxp(db, account, XP_PER_BATTLE_WIN + (XP_PER_FIRST_CLEAR if first_clear else 0))
```

Replace with:

```python
from app.account_level import xp_per_win as _xp_per_win, XP_PER_FIRST_CLEAR, grant_xp as _gxp
levelups = _gxp(db, account, _xp_per_win(stage.difficulty_tier) + (XP_PER_FIRST_CLEAR if first_clear else 0))
```

- [ ] **Step 5: Run full battle suite to verify no regression**

Run: `uv run pytest tests/test_battles.py tests/test_difficulty_tiers.py -v 2>&1 | tail -30`
Expected: All previously-passing battle tests still pass; tier-XP tests pass. NORMAL stages still grant 12 XP.

If a battle test fails, the most likely cause is a fixture stage with no `difficulty_tier` set — confirm `xp_per_win` defaults to NORMAL for `None` or missing values; it's defensive by design.

- [ ] **Step 6: Commit**

```bash
git add app/routers/battles.py tests/test_difficulty_tiers.py
git commit -m "feat(tiers): wire tier-keyed XP into battle resolve"
```

---

## Task 4: Surface display name in /stages API

**Files:**
- Modify: `app/schemas.py` (add field to `StageOut`)
- Modify: `app/routers/stages.py:16-33` (`stage_out` builder)
- Test: `tests/test_difficulty_tiers.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/test_difficulty_tiers.py`:

```python
from fastapi.testclient import TestClient


def test_stages_api_returns_display_name(client: TestClient, db_session):
    """GET /stages includes display_name per row."""
    # The seed already populates stages — make sure the endpoint surfaces names.
    r = client.get("/stages")
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) > 0
    # All four tiers should be representable; check that display_name is present.
    seen = set()
    for row in rows:
        assert "display_name" in row, f"missing display_name on {row.get('code')}"
        seen.add(row["difficulty_tier"])
    assert "NORMAL" in seen, "no NORMAL stages in fixture"
    # Find a NORMAL row, assert its display_name.
    normal = next(r for r in rows if r["difficulty_tier"] == "NORMAL")
    assert normal["display_name"] == "Floppy"
```

> **Note on fixture name:** if `tests/conftest.py` provides a `client` fixture, use it. Otherwise inspect another test like `tests/test_api_core.py` to mirror the existing client setup. Match exactly.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_difficulty_tiers.py::test_stages_api_returns_display_name -v`
Expected: FAIL with `assert "display_name" in row`.

- [ ] **Step 3: Add `display_name` field to `StageOut` schema**

In `app/schemas.py`, find the `StageOut` class. Add a `display_name: str` field at the end:

```python
class StageOut(BaseModel):
    id: int
    code: str
    name: str
    order: int
    energy_cost: int
    recommended_power: int
    waves: list
    coin_reward: int
    first_clear_gems: int
    first_clear_shards: int
    difficulty_tier: str
    requires_code: str
    display_name: str    # NEW
```

(If `StageOut` is structured differently in the actual file, add `display_name: str` as an additional field — preserve existing field order otherwise.)

- [ ] **Step 4: Populate `display_name` in `stage_out` builder**

In `app/routers/stages.py`, modify `stage_out`:

```python
from app.models import Stage, StageDifficulty, STAGE_TIER_DISPLAY

def stage_out(s: Stage) -> StageOut:
    try:
        waves = json.loads(s.waves_json or "[]")
    except json.JSONDecodeError:
        waves = []
    # Resolve display name; fall back to enum string if tier is unknown.
    try:
        tier_enum = StageDifficulty(s.difficulty_tier) if not isinstance(s.difficulty_tier, StageDifficulty) else s.difficulty_tier
        display = STAGE_TIER_DISPLAY.get(tier_enum, str(s.difficulty_tier))
    except ValueError:
        display = str(s.difficulty_tier)
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
    )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_difficulty_tiers.py -v`
Expected: PASS for `test_stages_api_returns_display_name`.

- [ ] **Step 6: Commit**

```bash
git add app/schemas.py app/routers/stages.py tests/test_difficulty_tiers.py
git commit -m "feat(tiers): expose display_name in /stages API"
```

---

## Task 5: Add LEGENDARY tier seed for every stage

**Files:**
- Modify: `app/seed.py:1398-1464` (extend the per-stage seed loop)
- Test: `tests/test_difficulty_tiers.py` (append)

**Context:** The existing seed loop already produces NORMAL, HARD (`H-`), and NIGHTMARE (`N-`) variants for each stage. We're adding a LEGENDARY (`L-`) variant immediately after the NIGHTMARE block, following the same pattern: +30 levels, 3.5× rewards, gated on the NIGHTMARE clear.

- [ ] **Step 1: Write the failing test**

Append to `tests/test_difficulty_tiers.py`:

```python
def test_seed_emits_four_tiers_per_stage(db_session):
    """After seed runs, every NORMAL stage has H-, N-, and L- siblings."""
    from sqlalchemy import select
    from app.models import Stage

    normals = db_session.scalars(
        select(Stage).where(Stage.difficulty_tier == StageDifficulty.NORMAL)
    ).all()
    assert len(normals) > 0, "seed produced no NORMAL stages"

    for n in normals:
        for prefix, tier in [("H-", StageDifficulty.HARD),
                             ("N-", StageDifficulty.NIGHTMARE),
                             ("L-", StageDifficulty.LEGENDARY)]:
            sibling = db_session.scalar(
                select(Stage).where(Stage.code == f"{prefix}{n.code}")
            )
            assert sibling is not None, f"missing {prefix}{n.code}"
            assert sibling.difficulty_tier == tier
            # LEGENDARY chain: L- requires N-
            if prefix == "L-":
                assert sibling.requires_code == f"N-{n.code}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_difficulty_tiers.py::test_seed_emits_four_tiers_per_stage -v`
Expected: FAIL with `assert sibling is not None` for `L-1-1` (or whichever the first stage code is).

- [ ] **Step 3: Add LEGENDARY block to the seed loop**

In `app/seed.py`, locate the NIGHTMARE block (around lines 1440-1464). Immediately after it, before the closing `for s in STAGE_SEEDS:` indent boundary, add:

```python
            # --- LEGENDARY tier: same waves, enemies +30 levels, 3.5x rewards, gated on NIGHTMARE clear.
            legendary_code = f"L-{s['code']}"
            if legendary_code not in existing_stage_codes:
                lg_waves = []
                for w in s["waves"]:
                    lg_waves.append({
                        "enemies": [
                            {"template_code": e["template_code"], "level": int(e.get("level", 1)) + 30}
                            for e in w.get("enemies", [])
                        ]
                    })
                db.add(Stage(
                    code=legendary_code,
                    name=f"{s['name']} (Legendary)",
                    order=s["order"] + 300,   # keeps NIGHTMARE sorted before LEGENDARY
                    energy_cost=s["energy_cost"] + 3,
                    recommended_power=s["recommended_power"] * 4,
                    waves_json=json.dumps(lg_waves),
                    coin_reward=int(s["coin_reward"] * 3.5),
                    first_clear_gems=s["first_clear_gems"] * 4,
                    first_clear_shards=s["first_clear_shards"] * 4,
                    difficulty_tier=StageDifficulty.LEGENDARY,
                    requires_code=nightmare_code,
                ))
                added_s += 1
```

Match the indentation of the surrounding HARD and NIGHTMARE blocks exactly.

- [ ] **Step 4: Run seed-affected tests**

Run: `uv run pytest tests/test_difficulty_tiers.py::test_seed_emits_four_tiers_per_stage -v`
Expected: PASS. Every NORMAL stage now has H-, N-, L- siblings.

- [ ] **Step 5: Run the full suite for regression check**

Run: `uv run pytest 2>&1 | tail -10`
Expected: all previously-passing tests still pass; new tier tests pass. Pay attention to any test that counts stages (e.g., "expected 32 stages, got 128") — those need updating to reflect the new tier count.

If the run reports a count mismatch in an existing test, find that test and update its expected stage count to `4 × N` where `N` is the number of NORMAL stages (typically 32 → expect 128). Re-run.

- [ ] **Step 6: Commit**

```bash
git add app/seed.py tests/test_difficulty_tiers.py
git commit -m "feat(tiers): seed LEGENDARY variant for every stage"
```

---

## Task 6: Frontend — surface display name in stage list

**Files:**
- Modify: `frontend/src/api/stages.ts` (or wherever `Stage` type is defined) — add `display_name: string`
- Modify: `frontend/src/routes/Stages.tsx` — render `display_name` instead of `difficulty_tier` enum string
- Test: existing Vitest setup if present, otherwise manual smoke

- [ ] **Step 1: Inspect existing frontend types and rendering**

Run: `cd frontend && cat src/api/stages.ts && echo "---" && grep -nE "difficulty_tier|tier" src/routes/Stages.tsx | head -10`

Identify where `difficulty_tier` is rendered. The pattern is to add a sibling `display_name: string` field to the TypeScript interface and prefer it over the raw enum in JSX.

- [ ] **Step 2: Add `display_name` to the TS interface**

In `frontend/src/api/stages.ts`, find the stage interface (likely `StageOut` or similar). Add:

```typescript
export interface StageOut {
  id: number;
  code: string;
  name: string;
  order: number;
  energy_cost: number;
  recommended_power: number;
  waves: unknown[];
  coin_reward: number;
  first_clear_gems: number;
  first_clear_shards: number;
  difficulty_tier: string;
  requires_code: string;
  display_name: string;    // NEW
}
```

(Match the existing field set — only add `display_name`. Don't reorder.)

- [ ] **Step 3: Render `display_name` in Stages.tsx**

Find the JSX that renders the tier label. Common patterns:

```tsx
{stage.difficulty_tier !== 'NORMAL' && <span>{stage.difficulty_tier}</span>}
```

Replace the rendered string with `{stage.display_name}`. Keep any conditional wrappers (e.g., "only show if not NORMAL") intact unless that's clearly broken.

- [ ] **Step 4: Build the frontend**

Run: `cd frontend && npm run build 2>&1 | tail -10`
Expected: Build succeeds. TypeScript catches any missed `difficulty_tier`-as-display references.

- [ ] **Step 5: Smoke-test in dev**

Run: `cd frontend && npm run dev` in one shell and `uv run uvicorn app.main:app --reload` in another. Open the browser to the stages list. Verify:

- NORMAL stages either don't show a tier badge or show "Floppy"
- HARD stages show "Hard Disk"
- NIGHTMARE stages show "RAID-0"
- LEGENDARY stages show "Legen'waitforit'dary"

If you can't run the dev server (e.g., no DB), this step is a manual checkpoint — note "smoke deferred" and proceed.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/api/stages.ts frontend/src/routes/Stages.tsx
git commit -m "feat(tiers): render tier display names in stage list"
```

---

## Task 7: Final verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend suite**

Run: `uv run pytest 2>&1 | tail -10`
Expected: All tests pass. New `tests/test_difficulty_tiers.py` contributes 5+ tests, all green.

- [ ] **Step 2: Verify the seed produces 4 tiers in a fresh DB**

Run:
```bash
uv run python -c "
from app.db import SessionLocal
from app.seed import run_seed
from sqlalchemy import select, func
from app.models import Stage, StageDifficulty
db = SessionLocal()
counts = {}
for t in StageDifficulty:
    counts[t.value] = db.scalar(select(func.count()).select_from(Stage).where(Stage.difficulty_tier == t))
print(counts)
"
```

Expected output (numbers will match your seed):
```
{'NORMAL': 32, 'HARD': 32, 'NIGHTMARE': 32, 'LEGENDARY': 32}
```

If the function name `run_seed` differs from what's in `app/seed.py`, look up the actual entry-point and use it.

- [ ] **Step 3: Verify XP grant via a real battle path**

Pick an existing battle smoke test (e.g., `scripts/smoke_hero.py` or similar) and run it against a HARD stage. Observe the account XP delta is 28, not 12.

If no smoke script touches HARD stages directly, this step is covered by the unit tests in Task 2/3 — note "covered by unit tests" and proceed.

- [ ] **Step 4: Push**

```bash
git push 2>&1 | tail -3
```

Expected: clean push to `origin/master`.

---

## Out-of-scope reminders (DO NOT implement here)

These are part of subsystems #2–#5, not this plan:
- Tier locks beyond the existing `requires_code` mechanism (subsystem #2)
- Power floor enforcement (subsystem #2)
- Fail pity mechanics (subsystem #3)
- Rest XP multiplier on the granted XP value (subsystem #4)
- Drop meter (subsystem #5)

If you find yourself thinking about any of those, stop and re-read the spec for this plan.
