# System Integrity Data Wiring (Backend) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Wire the Plan-1 resolver mechanics into real data: give enemies a weakness + Integrity bar, surface Integrity / Burnout / Crash / Delete-availability through the interactive API, and accept the `delete` action — so the System Integrity mechanic is reachable in actual battles (still no frontend; that's Plan 3).

**Architecture:** Add `weak_to_json` + `integrity_base` to `HeroTemplate` (migration), seed weaknesses, pass them onto enemy `CombatUnit`s in `_unit_from_template` (heroes stay inert), expand the interactive snapshot + pending-turn schemas with the new fields + delete-availability, and let the interactive `_advance`/submit path accept `action_type="delete"`.

**Tech Stack:** Python 3.13, FastAPI, SQLAlchemy 2 + Alembic, `uv run pytest`. Builds on Plan 1 (`docs/superpowers/plans/2026-05-28-system-integrity-core.md`, merged at `33016e4`).

**Scope:** Plan 2 of 3. Plan 1 = pure resolver (done). Plan 3 = frontend HUD + recycle-bin finisher + Battle3D VFX + p2w monetization. This plan is backend-only and pytest-testable end to end.

**Design source:** `docs/superpowers/specs/battlebuttonsets.md`.

**Resolver API available from Plan 1 (in `app/combat.py`):** `CombatUnit` fields `integrity`, `integrity_max`, `weak_to: list[Faction]`, `burnout`; helpers `_is_weakness`, `_is_crashed`, `_can_delete(actor, target)`; constants `WEAKNESS_BREAK`, `OFF_TYPE_INTEGRITY_FACTOR`, `BURNOUT_MAX`, `DELETE_EXECUTE_HP_FRAC`, etc.; `_act(..., action_type="delete", forced_target_uid=...)` resolves a Deleted execute.

---

### Task 1: HeroTemplate gains `weak_to_json` + `integrity_base` (+ migration)

**Files:**
- Modify: `app/models.py` (`HeroTemplate`)
- Create: `alembic/versions/<rev>_add_template_weakness.py`
- Test: `tests/test_system_integrity_wiring.py` (create)

- [ ] **Step 1: Read context.** Read the `HeroTemplate` class in `app/models.py` (find existing JSON-column patterns, e.g. `special_json`, `variance`-style columns) and the latest alembic head (`uv run alembic heads`). Match the existing column + migration style exactly.

- [ ] **Step 2: Write the failing test**

```python
# tests/test_system_integrity_wiring.py
from app.db import SessionLocal
from app.models import HeroTemplate


def test_herotemplate_has_weakness_columns():
    db = SessionLocal()
    try:
        t = db.query(HeroTemplate).first()
        assert t is not None, "seed must have run"
        # Columns exist and are readable (defaults: no weakness, no bar).
        assert hasattr(t, "weak_to_json")
        assert hasattr(t, "integrity_base")
        assert isinstance(t.integrity_base, int)
    finally:
        db.close()
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_system_integrity_wiring.py -v`
Expected: FAIL — `AttributeError` (columns missing).

- [ ] **Step 4: Add the columns** to `HeroTemplate` in `app/models.py` (match the file's existing `Mapped[...] = mapped_column(...)` style and `server_default` conventions used by other added columns):

```python
    # System Integrity (weakness-break). weak_to_json is a JSON list of Faction
    # values an enemy built from this template is weak to; integrity_base is the
    # toughness-bar size when used as an enemy (0 = no bar). Both default inert so
    # heroes and un-tuned enemies behave exactly as before.
    weak_to_json: Mapped[str] = mapped_column(String(128), default="[]", server_default="[]")
    integrity_base: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
```

- [ ] **Step 5: Generate + edit the migration**

Run: `uv run alembic revision -m "add template weakness columns"`
Edit the generated file's `upgrade()`/`downgrade()` to add/drop both columns with the same server defaults (cross-DB safe — nullable or server_default, NOT raw CURRENT_TIMESTAMP). Follow the pattern of a recent additive migration in `alembic/versions/`.

- [ ] **Step 6: Apply + verify**

Run: `uv run alembic upgrade head && uv run pytest tests/test_system_integrity_wiring.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/models.py alembic/versions/ tests/test_system_integrity_wiring.py
git commit -m "feat(combat): HeroTemplate weak_to_json + integrity_base columns"
```

---

### Task 2: Seed weaknesses + integrity onto enemy-capable templates

**Files:**
- Modify: `app/seed.py`
- Test: `tests/test_system_integrity_wiring.py`

- [ ] **Step 1: Read context.** Read `app/seed.py` to find where `HeroTemplate` rows are created/reconciled (the seed reconciles on every run). Identify the existing per-template loop and how `rig`/faction are assigned.

- [ ] **Step 2: Write the failing test**

```python
import json
from app.db import SessionLocal
from app.models import HeroTemplate


def test_seed_assigns_weaknesses_and_integrity():
    db = SessionLocal()
    try:
        templates = db.query(HeroTemplate).all()
        # At least most templates should declare a non-empty weakness + a bar,
        # so any enemy team has crashable members.
        with_weakness = [t for t in templates if json.loads(t.weak_to_json or "[]")]
        with_bar = [t for t in templates if t.integrity_base > 0]
        assert len(with_weakness) >= len(templates) // 2
        assert len(with_bar) >= len(templates) // 2
        # Every weakness value must be a valid Faction string.
        from app.models import Faction
        valid = {f.value for f in Faction}
        for t in with_weakness:
            for w in json.loads(t.weak_to_json):
                assert w in valid
    finally:
        db.close()
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_system_integrity_wiring.py -k seed -v`
Expected: FAIL — weaknesses not seeded (all empty).

- [ ] **Step 4: Implement seeding.** In `app/seed.py`, in the template reconcile loop, assign a weakness + integrity to each template deterministically. Use a fixed faction-rotation so it's reproducible and every faction is represented as a weakness somewhere. Add near the per-template assignment (adapt variable names to the actual loop):

```python
    # System Integrity: give each template a single weakness faction (rotated)
    # and an integrity bar sized by rarity, so enemies built from templates are
    # crashable. Deterministic + idempotent (re-seed overwrites to same values).
    _WEAK_ROTATION = [
        Faction.HELPDESK, Faction.DEVOPS, Faction.EXECUTIVE,
        Faction.ROGUE_IT, Faction.LEGACY,
    ]
    _INTEGRITY_BY_RARITY = {
        Rarity.COMMON: 50, Rarity.UNCOMMON: 75, Rarity.RARE: 100,
        Rarity.EPIC: 150, Rarity.LEGENDARY: 200, Rarity.MYTH: 250,
    }
    # ... inside the loop, per template `t` at index `i`:
    weak = _WEAK_ROTATION[i % len(_WEAK_ROTATION)]
    t.weak_to_json = json.dumps([weak.value])
    t.integrity_base = _INTEGRITY_BY_RARITY.get(t.rarity, 100)
```

Ensure `json`, `Faction`, `Rarity` are imported in `seed.py` (add if missing). Confirm the loop has a stable index `i` (use `enumerate(...)` if it doesn't).

- [ ] **Step 5: Re-seed + verify**

Run: `uv run python -c "from app.seed import seed; seed()" && uv run pytest tests/test_system_integrity_wiring.py -k seed -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/seed.py tests/test_system_integrity_wiring.py
git commit -m "feat(combat): seed template weaknesses + integrity by rarity"
```

---

### Task 3: Enemy CombatUnits carry weakness + Integrity; heroes stay inert

**Files:**
- Modify: `app/routers/battles.py` (`_unit_from_template`; possibly `build_unit` call)
- Test: `tests/test_system_integrity_wiring.py`

- [ ] **Step 1: Read context.** Read `build_unit` (the factory `_unit_from_template`/`_unit_from_instance` call — find its definition via `grep -rn "def build_unit" app/`). Confirm whether it accepts `weak_to` / `integrity_max` kwargs or whether the CombatUnit must be post-populated after construction. Read `_unit_from_template` (`app/routers/battles.py:94`) and `_unit_from_instance` (`:65`).

- [ ] **Step 2: Write the failing test**

```python
import json
from app.db import SessionLocal
from app.models import HeroTemplate
from app.routers.battles import _unit_from_template, _unit_from_instance


def test_enemy_unit_gets_integrity_and_weakness():
    db = SessionLocal()
    try:
        t = db.query(HeroTemplate).filter(HeroTemplate.integrity_base > 0).first()
        assert t is not None
        u = _unit_from_template(t, level=10, side="B", idx=0)
        assert u.integrity_max == t.integrity_base
        assert u.integrity == t.integrity_base  # starts full
        assert [f.value for f in u.weak_to] == json.loads(t.weak_to_json)
    finally:
        db.close()
```

(If `_unit_from_instance` is reachable without a full HeroInstance fixture, also assert a hero unit has `integrity_max == 0`. Otherwise rely on the default — heroes never get integrity wired here.)

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_system_integrity_wiring.py -k enemy_unit -v`
Expected: FAIL — `integrity_max == 0`.

- [ ] **Step 4: Implement.** In `_unit_from_template` (`app/routers/battles.py`), after the `build_unit(...)` call, populate the new fields on the returned unit (post-population avoids touching `build_unit`'s signature; if `build_unit` already accepts kwargs cleanly, pass them instead — implementer's call based on Step 1):

```python
    from app.models import Faction
    import json as _json
    unit = build_unit(  # existing call, unchanged
        ...
    )
    weak = [Faction(w) for w in _json.loads(getattr(t, "weak_to_json", "[]") or "[]")]
    integ = int(getattr(t, "integrity_base", 0) or 0)
    unit.weak_to = weak
    unit.integrity_max = integ
    unit.integrity = integ  # bar starts full
    return unit
```

Leave `_unit_from_instance` (heroes) UNCHANGED — heroes keep `integrity_max == 0` (inert).

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_system_integrity_wiring.py -k enemy_unit -v`
Expected: PASS.

- [ ] **Step 6: Regression**

Run: `uv run pytest tests/ -k "battle or combat or raid or arena" 2>&1 | tail -8`
Expected: 0 failures (enemies now have bars, but no existing test asserts enemy integrity).

- [ ] **Step 7: Commit**

```bash
git add app/routers/battles.py tests/test_system_integrity_wiring.py
git commit -m "feat(combat): enemy units carry weakness + integrity bar"
```

---

### Task 4: Surface Integrity / Burnout / Crash in the interactive schemas

**Files:**
- Modify: `app/schemas.py` (`UnitSnapshot`, `PendingTurnOut`)
- Test: `tests/test_system_integrity_wiring.py`

- [ ] **Step 1: Read context.** Read `UnitSnapshot` (referenced by `InteractiveStateOut.team_a/team_b`; find it via `grep -rn "UnitSnapshot" app/schemas.py`) and `PendingTurnOut` (`app/schemas.py:532`). Note their existing fields so additions match style and stay backward-compatible (all new fields default-valued).

- [ ] **Step 2: Write the failing test**

```python
from app.schemas import UnitSnapshot, PendingTurnOut


def test_unitsnapshot_has_integrity_burnout_fields():
    # All new fields are optional/defaulted so construction with old kwargs still works.
    f = UnitSnapshot.model_fields
    assert "integrity" in f and "integrity_max" in f
    assert "burnout" in f and "crashed" in f


def test_pendingturn_exposes_delete_action_and_targets():
    f = PendingTurnOut.model_fields
    assert "valid_delete_targets" in f  # list[str] of deletable enemy uids
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_system_integrity_wiring.py -k "unitsnapshot or pendingturn" -v`
Expected: FAIL — fields missing.

- [ ] **Step 4: Implement.** Add to `UnitSnapshot` (backward-compatible defaults):

```python
    integrity: int = 0
    integrity_max: int = 0
    burnout: int = 0
    crashed: bool = False
```

Add to `PendingTurnOut`:

```python
    # Enemy uids the acting unit may "Delete" this turn (Crashed + low-HP, or
    # any Crashed enemy if the actor is in burnout-dump range). Empty when none.
    valid_delete_targets: list[str] = []
```

The `actions` dict on `PendingTurnOut` already keys attack/skill/limit/defend; the snapshot builder (Task 5) will add a `"delete"` key when `valid_delete_targets` is non-empty.

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_system_integrity_wiring.py -k "unitsnapshot or pendingturn" -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/schemas.py tests/test_system_integrity_wiring.py
git commit -m "feat(combat): interactive schemas expose integrity/burnout/crash + delete targets"
```

---

### Task 5: Populate snapshots + delete-availability; accept the `delete` action

**Files:**
- Modify: `app/interactive.py` (snapshot builder, pending-turn builder, action submit/`_advance`)
- Test: `tests/test_system_integrity_wiring.py`

- [ ] **Step 1: Read context.** Read `app/interactive.py` fully enough to find: (a) where a `UnitSnapshot` is built from a `CombatUnit` (the snapshot helper), (b) where `PendingTurnOut` is built (the `actions` dict + actor resolution), and (c) the submit/`_advance` path (~line 299) that validates `action_type` and passes it to `_act`. Note the current allowed `action_type` set.

- [ ] **Step 2: Write the failing test** (drive the resolver through a Crash → delete via the interactive layer; adapt session setup to the existing interactive test helpers in `tests/`):

```python
from app.combat import _is_crashed, _can_delete, CombatUnit, StatusEffect
from app.models import StatusEffectKind, Faction, Role


def _enemy(uid="B0"):
    return CombatUnit(
        uid=uid, side="B", name="e", role=Role.ATK, level=10,
        max_hp=1000, hp=200, atk=100, def_=50, spd=50, basic_mult=1.0,
        special=None, special_cooldown_max=0, base_atk=100, base_def=50,
        integrity=0, integrity_max=150, weak_to=[Faction.HELPDESK],
        statuses=[StatusEffect(kind=StatusEffectKind.VULNERABLE, turns_left=2, value=0.30)],
    )


def test_snapshot_builder_marks_crashed():
    from app.interactive import _unit_snapshot  # confirm actual helper name in Step 1
    snap = _unit_snapshot(_enemy())
    assert snap.crashed is True
    assert snap.integrity_max == 150


def test_delete_in_allowed_action_types():
    # Confirm the submit path accepts "delete" (read the actual validator in Step 1;
    # assert against the allowed set or a constant the implementer exposes).
    import app.interactive as interactive
    assert "delete" in interactive.ALLOWED_ACTION_TYPES  # add this constant if absent
```

NOTE: the exact helper/constant names depend on Step 1's reading. If the snapshot helper has a different name or the allowed set is inline, adapt the test to the real symbols — keep the *behavior* asserted (snapshot marks crashed; submit accepts "delete").

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest tests/test_system_integrity_wiring.py -k "snapshot_builder or delete_in_allowed" -v`
Expected: FAIL.

- [ ] **Step 4: Implement.**
  1. In the snapshot helper, set `integrity`, `integrity_max`, `burnout` from the unit, and `crashed=_is_crashed(unit)` (import from `app.combat`).
  2. In the pending-turn builder, compute `valid_delete_targets = [e.uid for e in live_enemies if _can_delete(actor, e)]` (import `_can_delete`); if non-empty, add `actions["delete"] = {"enabled": True, "reason": None}` (else `{"enabled": False, "reason": "no crashed target"}`).
  3. In the submit/`_advance` validator, add `"delete"` to the allowed `action_type` set (introduce a module-level `ALLOWED_ACTION_TYPES = {None, "attack", "skill", "limit", "defend", "delete"}` if one doesn't already exist, and validate against it). The resolver already handles `action_type="delete"` with `forced_target_uid`.

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest tests/test_system_integrity_wiring.py -v`
Expected: PASS (all wiring tests).

- [ ] **Step 6: Regression**

Run: `uv run pytest tests/ -k "interactive or battle or combat or raid or arena" 2>&1 | tail -10`
Expected: 0 failures.

- [ ] **Step 7: Commit**

```bash
git add app/interactive.py tests/test_system_integrity_wiring.py
git commit -m "feat(combat): interactive snapshots + delete action availability"
```

---

### Task 6: Full-suite regression + acceptance smoke

**Files:** none (verification only)

- [ ] **Step 1: Full backend suite**

Run: `uv run pytest 2>&1 | tail -15`
Expected: green except the known nondeterministic `test_phase1_acceptance` gacha-dupe flake (re-run it alone to confirm: `uv run pytest tests/test_phase1_acceptance.py::test_phase1_end_to_end`). If any OTHER test regresses, investigate — most likely an enemy now Crashing changes a seeded interactive battle outcome; if so, the affected test asserts an exact combat outcome and should be made robust to the new mechanic (consult before weakening).

- [ ] **Step 2: Interactive smoke against a live server (optional but recommended).** Start the server, run a stage in interactive mode, and confirm `InteractiveStateOut` now includes integrity/burnout on team_b units and a `valid_delete_targets` list once an enemy is Crashed. (See `scripts/client_walkthrough.py` for the interactive flow pattern.)

- [ ] **Step 3: Commit any fixes; otherwise done.**

```bash
git add -A
git restore --staged uv.lock 2>/dev/null; git checkout -- uv.lock 2>/dev/null
git commit -m "test(combat): system integrity data wiring green" --allow-empty
```

---

## Self-review notes

- **Spec coverage:** enemy weakness axis + Integrity bar (T1-3), Crash reachable in real battles (T3 via resolver), Burnout/Integrity/Crash surfaced to the API (T4-5), Delete action accepted (T5). Deferred to Plan 3 (noted): all frontend (HUD bars, recycle-bin finisher, Battle3D VFX), Deleted bonus loot/multipliers, and the p2w monetization hooks (universal banner, Composure gear, consumables).
- **Inertness:** heroes keep `integrity_max == 0` (only `_unit_from_template` wires enemies); all schema additions are default-valued (backward compatible).
- **Read-first steps:** Tasks 3/4/5 begin by reading `build_unit`, `UnitSnapshot`, and the `interactive.py` helpers because their exact signatures weren't captured at plan time — the edits themselves are specified; only the symbol names need confirming.
- **Migration safety:** additive columns with `server_default` (cross-DB safe; auto-runs on Fly per `app/main.py`).
