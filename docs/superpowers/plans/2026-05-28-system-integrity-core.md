# System Integrity Core (Resolver) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the weakness-break ("System Integrity"), Crash, and Burnout combat mechanics to the pure resolver in `app/combat.py`, fully unit-tested, with zero DB/UI changes.

**Architecture:** Extend the `CombatUnit` dataclass with an Integrity bar, a `weak_to` faction list, and a Burnout meter. Weakness-matching hits drain Integrity fast (off-type at 15%); zeroing it triggers a Crash (STUN + new VULNERABLE status + a faction-flavored debuff). Burnout accrues from hits/skills/limits, sheds on Defend, and shifts crit/damage at thresholds. A new `delete` action executes a Crashed, low-HP enemy. All logic lives in pure functions resolvable in pytest with no database.

**Tech Stack:** Python 3.13, `uv run pytest`, existing `app/combat.py` + `app/models.py` enums.

**Scope:** This is Plan 1 of 3. Plan 2 = data wiring (enemy `weak_to` seeding, `_unit_from_instance`, `InteractiveStateOut`) + HUD. Plan 3 = p2w monetization. This plan deliberately touches only `app/combat.py`, `app/models.py` (one enum), and a new test file.

**Design source:** `docs/superpowers/specs/battlebuttonsets.md` (esp. §6 starting values, §7 p2w route → off-type = 15%).

---

### Task 1: Constants, CombatUnit fields, VULNERABLE status

**Files:**
- Modify: `app/models.py` (StatusEffectKind enum)
- Modify: `app/combat.py` (constants block near top + CombatUnit dataclass ~line 79-138)
- Test: `tests/test_system_integrity.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_system_integrity.py
from app.combat import CombatUnit, WEAKNESS_BREAK, OFF_TYPE_INTEGRITY_FACTOR, BURNOUT_MAX
from app.models import Faction, StatusEffectKind


def _mk(uid="e0", side="B", **kw):
    base = dict(
        uid=uid, side=side, name="t", role=__import__("app.models", fromlist=["Role"]).Role.ATK,
        level=10, max_hp=1000, hp=1000, atk=100, def_=50, spd=50, basic_mult=1.0,
        special=None, special_cooldown_max=0, base_atk=100, base_def=50,
    )
    base.update(kw)
    return CombatUnit(**base)


def test_combatunit_has_integrity_and_burnout_fields():
    u = _mk(integrity=150, integrity_max=150, weak_to=[Faction.HELPDESK], burnout=0)
    assert u.integrity == 150
    assert u.integrity_max == 150
    assert u.weak_to == [Faction.HELPDESK]
    assert u.burnout == 0


def test_vulnerable_status_enum_exists():
    assert StatusEffectKind.VULNERABLE == "VULNERABLE"


def test_tuning_constants_present():
    assert WEAKNESS_BREAK > 0
    assert 0 < OFF_TYPE_INTEGRITY_FACTOR < 1
    assert BURNOUT_MAX == 100
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_system_integrity.py -v`
Expected: FAIL — `ImportError` (constants not defined) / `AttributeError` (VULNERABLE).

- [ ] **Step 3: Add the VULNERABLE enum value**

In `app/models.py`, in `class StatusEffectKind(StrEnum)`, after `HEAL_BLOCK = "HEAL_BLOCK"`:

```python
    # Crash mechanic: a Crashed enemy takes amplified incoming damage for the
    # vulnerability window. value = damage-taken multiplier bonus (e.g. 0.30 = +30%).
    VULNERABLE = "VULNERABLE"
```

- [ ] **Step 4: Add tuning constants in `app/combat.py`**

After `COMBAT_LOG_MAX_ENTRIES = 200` (~line 40), add:

```python
# --- System Integrity (weakness-break) + Burnout tuning (battlebuttonsets.md §6) ---
WEAKNESS_BREAK = 50          # Integrity removed by a weakness-matching damaging hit.
OFF_TYPE_INTEGRITY_FACTOR = 0.15  # Off-faction hits remove this fraction of WEAKNESS_BREAK.
CRASH_STUN_TURNS = 1
CRASH_VULNERABLE_TURNS = 2
CRASH_VULNERABLE_VALUE = 0.30     # +30% damage taken while Crashed.
BURNOUT_MAX = 100
BURNOUT_PER_HIT = 5
BURNOUT_PER_SKILL = 10
BURNOUT_PER_LIMIT = 25
BURNOUT_DEFEND_SHED = 30
BURNOUT_HIGH = 75            # >= this: damage/accuracy penalty + desperation unlocked.
BURNOUT_LOW = 25            # <= this: crit bonus.
BURNOUT_HIGH_DMG_PENALTY = 0.15
BURNOUT_LOW_CRIT_BONUS = 0.10
DELETE_EXECUTE_HP_FRAC = 0.25  # Crashed enemy at/below this HP fraction is Deletable (mode 1).
```

- [ ] **Step 5: Add fields to the `CombatUnit` dataclass**

In `app/combat.py`, after the `limit_gauge_max: int = 100` field (~line 138), add:

```python
    # --- System Integrity (weakness-break). integrity_max == 0 means "no bar"
    # (heroes, weaknessless enemies). weak_to lists the factions that drain the
    # bar at full rate; off-type hits drain OFF_TYPE_INTEGRITY_FACTOR of that.
    integrity: int = 0
    integrity_max: int = 0
    weak_to: list[Faction] = field(default_factory=list)
    # --- Burnout meter (0..BURNOUT_MAX). Battle-scoped. High = penalty +
    # desperation; low = crit bonus. Sheds on Defend.
    burnout: int = 0
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_system_integrity.py -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add app/models.py app/combat.py tests/test_system_integrity.py
git commit -m "feat(combat): integrity + burnout fields + VULNERABLE status"
```

---

### Task 2: Weakness detection + Integrity depletion helper

**Files:**
- Modify: `app/combat.py` (new helpers after `_is_heal_blocked` ~line 342)
- Test: `tests/test_system_integrity.py`

- [ ] **Step 1: Write the failing test**

```python
from app.combat import _is_weakness, _deplete_integrity


def test_is_weakness_true_when_attacker_faction_in_weak_to():
    atk = _mk(uid="a0", side="A", faction=Faction.HELPDESK)
    dfn = _mk(integrity=150, integrity_max=150, weak_to=[Faction.HELPDESK])
    assert _is_weakness(atk, dfn) is True


def test_is_weakness_false_for_off_type_or_no_bar():
    atk = _mk(uid="a0", side="A", faction=Faction.DEVOPS)
    dfn = _mk(integrity=150, integrity_max=150, weak_to=[Faction.HELPDESK])
    assert _is_weakness(atk, dfn) is False
    nobar = _mk(faction=Faction.HELPDESK)  # integrity_max defaults 0
    assert _is_weakness(atk, nobar) is False


def test_weakness_hit_drains_full_break():
    atk = _mk(uid="a0", side="A", faction=Faction.HELPDESK)
    dfn = _mk(integrity=150, integrity_max=150, weak_to=[Faction.HELPDESK])
    log = []
    _deplete_integrity(atk, dfn, log)
    assert dfn.integrity == 100  # 150 - WEAKNESS_BREAK(50)
    assert any(e["type"] == "INTEGRITY" for e in log)


def test_off_type_hit_drains_reduced():
    atk = _mk(uid="a0", side="A", faction=Faction.DEVOPS)
    dfn = _mk(integrity=150, integrity_max=150, weak_to=[Faction.HELPDESK])
    log = []
    _deplete_integrity(atk, dfn, log)
    assert dfn.integrity == 150 - int(50 * 0.15)  # 150 - 7 = 143


def test_no_bar_enemy_unaffected():
    atk = _mk(uid="a0", side="A", faction=Faction.HELPDESK)
    dfn = _mk()  # integrity_max 0
    log = []
    _deplete_integrity(atk, dfn, log)
    assert dfn.integrity == 0
    assert log == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_system_integrity.py -k "weakness or integrity or off_type or no_bar" -v`
Expected: FAIL — `_is_weakness`/`_deplete_integrity` not defined.

- [ ] **Step 3: Implement the helpers**

In `app/combat.py`, after `_is_heal_blocked` (~line 342), add:

```python
def _is_weakness(attacker: CombatUnit, defender: CombatUnit) -> bool:
    """True when the attacker's faction is one the defender is weak to AND the
    defender actually has an Integrity bar."""
    return (
        defender.integrity_max > 0
        and attacker.faction is not None
        and attacker.faction in defender.weak_to
    )


def _deplete_integrity(attacker: CombatUnit, defender: CombatUnit, log: list[dict]) -> None:
    """Drain the defender's Integrity from a damaging hit. Weakness-matching hits
    remove WEAKNESS_BREAK; off-type hits remove OFF_TYPE_INTEGRITY_FACTOR of that
    (the anti-wall valve). No-op on a unit with no bar or one already Crashed
    (integrity already 0, in the Crash window). Triggers _apply_crash on reaching 0."""
    if defender.integrity_max <= 0 or defender.integrity <= 0:
        return
    weakness = _is_weakness(attacker, defender)
    amt = WEAKNESS_BREAK if weakness else int(WEAKNESS_BREAK * OFF_TYPE_INTEGRITY_FACTOR)
    defender.integrity = max(0, defender.integrity - amt)
    log.append({
        "type": "INTEGRITY", "unit": defender.uid,
        "integrity": defender.integrity, "max": defender.integrity_max,
        "weakness": weakness,
    })
    if defender.integrity == 0:
        _apply_crash(attacker, defender, log)
```

(Note: `_apply_crash` is defined in Task 3. Until then this raises `NameError` only if integrity reaches 0 — the Task 2 tests stop above zero, so they pass. Task 3 adds the function and the zero-crossing test.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_system_integrity.py -k "weakness or integrity or off_type or no_bar" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/combat.py tests/test_system_integrity.py
git commit -m "feat(combat): weakness detection + integrity depletion"
```

---

### Task 3: Crash application (STUN + VULNERABLE + faction-flavored debuff)

**Files:**
- Modify: `app/combat.py` (FACTION_CRASH_DEBUFF map + `_apply_crash` after `_deplete_integrity`)
- Test: `tests/test_system_integrity.py`

- [ ] **Step 1: Write the failing test**

```python
from app.combat import _apply_crash, FACTION_CRASH_DEBUFF


def test_crash_applies_stun_and_vulnerable():
    atk = _mk(uid="a0", side="A", faction=Faction.HELPDESK)
    dfn = _mk(integrity=0, integrity_max=150, weak_to=[Faction.HELPDESK])
    log = []
    _apply_crash(atk, dfn, log)
    kinds = {s.kind for s in dfn.statuses}
    assert StatusEffectKind.STUN in kinds
    assert StatusEffectKind.VULNERABLE in kinds
    assert any(e["type"] == "CRASH" for e in log)


def test_crash_flavored_debuff_matches_breaker_faction():
    # LEGACY breaker -> BURN per FACTION_CRASH_DEBUFF
    atk = _mk(uid="a0", side="A", faction=Faction.LEGACY)
    dfn = _mk(integrity=0, integrity_max=150, weak_to=[Faction.LEGACY])
    log = []
    _apply_crash(atk, dfn, log)
    assert any(s.kind == FACTION_CRASH_DEBUFF[Faction.LEGACY] for s in dfn.statuses)


def test_full_debuff_map_covers_five_factions():
    for f in (Faction.HELPDESK, Faction.DEVOPS, Faction.EXECUTIVE,
              Faction.ROGUE_IT, Faction.LEGACY):
        assert f in FACTION_CRASH_DEBUFF
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_system_integrity.py -k "crash or debuff_map" -v`
Expected: FAIL — `_apply_crash`/`FACTION_CRASH_DEBUFF` not defined.

- [ ] **Step 3: Implement the debuff map + `_apply_crash`**

In `app/combat.py`, immediately before `_deplete_integrity`, add the map:

```python
# Crash debuff flavored by the breaker's faction (battlebuttonsets.md §5.2).
FACTION_CRASH_DEBUFF: dict[Faction, StatusEffectKind] = {
    Faction.HELPDESK: StatusEffectKind.STUN,      # extend the stun
    Faction.LEGACY: StatusEffectKind.BURN,
    Faction.DEVOPS: StatusEffectKind.DEF_DOWN,
    Faction.ROGUE_IT: StatusEffectKind.POISON,
    Faction.EXECUTIVE: StatusEffectKind.HEAL_BLOCK,
}
```

After `_deplete_integrity`, add:

```python
def _apply_crash(attacker: CombatUnit, defender: CombatUnit, log: list[dict]) -> None:
    """Crash the defender: skip its next turn (STUN), open a vulnerability window
    (VULNERABLE amps incoming damage), and apply a debuff flavored by the breaker's
    faction. Integrity refills when the VULNERABLE window expires (see _tick_statuses)."""
    defender.statuses.append(StatusEffect(kind=StatusEffectKind.STUN, turns_left=CRASH_STUN_TURNS, value=0.0))
    defender.statuses.append(StatusEffect(kind=StatusEffectKind.VULNERABLE, turns_left=CRASH_VULNERABLE_TURNS, value=CRASH_VULNERABLE_VALUE))
    flavored = FACTION_CRASH_DEBUFF.get(attacker.faction) if attacker.faction else None
    if flavored is not None:
        defender.statuses.append(StatusEffect(kind=flavored, turns_left=2, value=0.20))
    log.append({
        "type": "CRASH", "unit": defender.uid,
        "by": attacker.uid, "faction": str(attacker.faction) if attacker.faction else None,
        "debuff": str(flavored) if flavored else None,
    })
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_system_integrity.py -k "crash or debuff_map" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/combat.py tests/test_system_integrity.py
git commit -m "feat(combat): crash applies stun + vulnerable + flavored debuff"
```

---

### Task 4: Integrity refill when the Crash window ends

**Files:**
- Modify: `app/combat.py` (`_tick_statuses` ~line 267-289)
- Test: `tests/test_system_integrity.py`

- [ ] **Step 1: Write the failing test**

```python
from app.combat import _tick_statuses, StatusEffect


def test_integrity_refills_when_vulnerable_expires():
    dfn = _mk(integrity=0, integrity_max=150, weak_to=[Faction.HELPDESK])
    # VULNERABLE with 1 turn left -> expires this tick.
    dfn.statuses.append(StatusEffect(kind=StatusEffectKind.VULNERABLE, turns_left=1, value=0.30))
    log = []
    _tick_statuses(dfn, log)
    assert dfn.integrity == 150  # refilled to max
    assert not any(s.kind == StatusEffectKind.VULNERABLE for s in dfn.statuses)


def test_integrity_not_refilled_while_vulnerable_persists():
    dfn = _mk(integrity=0, integrity_max=150, weak_to=[Faction.HELPDESK])
    dfn.statuses.append(StatusEffect(kind=StatusEffectKind.VULNERABLE, turns_left=2, value=0.30))
    _tick_statuses(dfn, [])
    assert dfn.integrity == 0  # still crashed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_system_integrity.py -k "refill" -v`
Expected: FAIL — integrity stays 0 after expiry.

- [ ] **Step 3: Implement the refill in `_tick_statuses`**

In `app/combat.py`, in `_tick_statuses`, replace the final line `unit.statuses = new_statuses` with:

```python
    # If the Crash window (VULNERABLE) just ended, refill Integrity so the
    # enemy can be Crashed again later.
    had_vulnerable = any(s.kind == StatusEffectKind.VULNERABLE for s in unit.statuses)
    still_vulnerable = any(s.kind == StatusEffectKind.VULNERABLE for s in new_statuses)
    if had_vulnerable and not still_vulnerable and unit.integrity_max > 0:
        unit.integrity = unit.integrity_max
        log.append({"type": "INTEGRITY_RESTORED", "unit": unit.uid, "integrity": unit.integrity})
    unit.statuses = new_statuses
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_system_integrity.py -k "refill" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/combat.py tests/test_system_integrity.py
git commit -m "feat(combat): refill integrity when crash window ends"
```

---

### Task 5: Wire depletion + vulnerability amp into `_apply_damage`

**Files:**
- Modify: `app/combat.py` (`_apply_damage` ~line 172-224)
- Test: `tests/test_system_integrity.py`

- [ ] **Step 1: Write the failing test**

```python
from app.combat import _apply_damage


def test_vulnerable_amps_incoming_damage():
    dfn = _mk(hp=1000, max_hp=1000)
    dfn.statuses.append(StatusEffect(kind=StatusEffectKind.VULNERABLE, turns_left=2, value=0.30))
    dealt = _apply_damage(dfn, 100, attacker=None, log=[])
    assert dealt == 130  # +30%


def test_damaging_hit_depletes_integrity_then_crashes():
    atk = _mk(uid="a0", side="A", faction=Faction.HELPDESK)
    dfn = _mk(hp=1000, max_hp=1000, integrity=50, integrity_max=150, weak_to=[Faction.HELPDESK])
    log = []
    _apply_damage(dfn, 100, attacker=atk, log=log)  # weakness hit removes 50 -> 0 -> crash
    assert dfn.integrity == 0
    assert any(e["type"] == "CRASH" for e in log)


def test_no_integrity_change_when_no_attacker():
    dfn = _mk(hp=1000, max_hp=1000, integrity=150, integrity_max=150, weak_to=[Faction.HELPDESK])
    _apply_damage(dfn, 100, attacker=None, log=[])
    assert dfn.integrity == 150  # DoT / reflect (no attacker) doesn't break integrity
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_system_integrity.py -k "vulnerable_amps or depletes or no_integrity_change" -v`
Expected: FAIL — no amp, no depletion.

- [ ] **Step 3: Add the vulnerability amp**

In `app/combat.py`, in `_apply_damage`, right after the DEFENDING block (after line 195, before `defender.hp = max(0, ...)`), add:

```python
    vuln = max((s.value for s in defender.statuses if s.kind == StatusEffectKind.VULNERABLE), default=0.0)
    if vuln > 0:
        amount = max(1, int(round(amount * (1.0 + vuln))))
```

- [ ] **Step 4: Add the integrity depletion call**

In `_apply_damage`, just before the final `return amount`, add:

```python
    if amount > 0 and attacker is not None and not defender.dead:
        _deplete_integrity(attacker, defender, log if log is not None else [])
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_system_integrity.py -k "vulnerable_amps or depletes or no_integrity_change" -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/combat.py tests/test_system_integrity.py
git commit -m "feat(combat): integrity depletion + vulnerability amp in damage path"
```

---

### Task 6: Burnout accrual (hit / skill / limit / defend)

**Files:**
- Modify: `app/combat.py` (`_apply_damage` for hits; `_act` for skill/limit/defend)
- Test: `tests/test_system_integrity.py`

- [ ] **Step 1: Write the failing test**

```python
def test_taking_a_hit_builds_burnout():
    dfn = _mk(hp=1000, max_hp=1000, burnout=0)
    _apply_damage(dfn, 100, attacker=None, log=[])
    assert dfn.burnout == 5  # BURNOUT_PER_HIT


def test_burnout_caps_at_max():
    dfn = _mk(hp=100000, max_hp=100000, burnout=98)
    _apply_damage(dfn, 10, attacker=None, log=[])
    assert dfn.burnout == 100  # capped at BURNOUT_MAX


def test_defend_sheds_burnout():
    from app.combat import _act
    import random
    actor = _mk(uid="a0", side="A", burnout=50, limit_gauge_max=100)
    _act(actor, allies=[actor], enemies=[_mk()], rng=random.Random(1),
         log=[], action_type="defend")
    assert actor.burnout == 20  # 50 - BURNOUT_DEFEND_SHED(30)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_system_integrity.py -k "burnout" -v`
Expected: FAIL — burnout unchanged.

- [ ] **Step 3: Build burnout on taking a hit**

In `_apply_damage`, immediately after `defender.hp = max(0, defender.hp - amount)`, add:

```python
    if amount > 0:
        defender.burnout = min(BURNOUT_MAX, defender.burnout + BURNOUT_PER_HIT)
```

- [ ] **Step 4: Shed burnout on Defend**

In `_act`, inside the `if action_type == "defend":` block, before `log.append({"type": "DEFEND", ...})`, add:

```python
        actor.burnout = max(0, actor.burnout - BURNOUT_DEFEND_SHED)
```

- [ ] **Step 5: Build burnout on Skill and Limit**

In `_act`, inside the limit-break branch (after `damage_dealt = _do_limit_break(...)`, before `actor.limit_gauge = 0`), add:

```python
        actor.burnout = min(BURNOUT_MAX, actor.burnout + BURNOUT_PER_LIMIT)
```

In `_act`, inside `if use_special:`, right after the `log.append({"type": "SPECIAL", ...})` call, add:

```python
        actor.burnout = min(BURNOUT_MAX, actor.burnout + BURNOUT_PER_SKILL)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `uv run pytest tests/test_system_integrity.py -k "burnout" -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add app/combat.py tests/test_system_integrity.py
git commit -m "feat(combat): burnout accrual on hit/skill/limit + shed on defend"
```

---

### Task 7: Burnout effects on damage (high penalty, low crit bonus)

**Files:**
- Modify: `app/combat.py` (`_damage` ~line 162-169)
- Test: `tests/test_system_integrity.py`

- [ ] **Step 1: Write the failing test**

```python
import random
from app.combat import _damage


def test_low_burnout_raises_crit_chance():
    atk = _mk(uid="a0", side="A", burnout=0, base_atk=100)
    dfn = _mk(base_def=0, def_=0)
    # Seed where base 5% would miss crit but +10% (low burnout) lands it.
    # Deterministic: with many rolls, low-burnout crit-rate > high-burnout crit-rate.
    rng = random.Random(7)
    low_crits = sum(_damage(atk, dfn, 1.0, rng)[1] for _ in range(2000))
    atk_hi = _mk(uid="a1", side="A", burnout=90, base_atk=100)
    rng2 = random.Random(7)
    hi_crits = sum(_damage(atk_hi, dfn, 1.0, rng2)[1] for _ in range(2000))
    assert low_crits > hi_crits


def test_high_burnout_reduces_damage():
    dfn = _mk(base_def=0, def_=0)
    atk_lo = _mk(uid="a0", side="A", burnout=0, base_atk=1000)
    atk_hi = _mk(uid="a1", side="A", burnout=90, base_atk=1000)
    # Same seed: high-burnout attacker deals less (penalty applied).
    d_lo = _damage(atk_lo, dfn, 1.0, random.Random(3))[0]
    d_hi = _damage(atk_hi, dfn, 1.0, random.Random(3))[0]
    assert d_hi < d_lo
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_system_integrity.py -k "burnout and (crit or reduces)" -v`
Expected: FAIL — burnout doesn't affect `_damage` yet.

- [ ] **Step 3: Apply burnout to `_damage`**

In `app/combat.py`, replace the body of `_damage` (lines ~163-169) with:

```python
    atk = _effective_atk(attacker)
    df = _effective_def(defender)
    raw = atk * multiplier * (1.0 - df / (df + 1000.0))
    variance = rng.uniform(0.85, 1.15)
    crit_chance = 0.05
    if attacker.burnout <= BURNOUT_LOW:
        crit_chance += BURNOUT_LOW_CRIT_BONUS
    crit = rng.random() < crit_chance
    dmg = raw * variance * (1.5 if crit else 1.0)
    if attacker.burnout >= BURNOUT_HIGH:
        dmg *= (1.0 - BURNOUT_HIGH_DMG_PENALTY)
    return max(1, int(round(dmg))), crit
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_system_integrity.py -k "burnout and (crit or reduces)" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add app/combat.py tests/test_system_integrity.py
git commit -m "feat(combat): burnout shifts crit (low) and damage (high)"
```

---

### Task 8: "Deleted" execute action

**Files:**
- Modify: `app/combat.py` (`_act` — new `delete` branch + `_can_delete` helper)
- Test: `tests/test_system_integrity.py`

- [ ] **Step 1: Write the failing test**

```python
import random
from app.combat import _act, _can_delete


def _crashed(uid="e0", hp=200, max_hp=1000, integrity_max=150):
    d = _mk(uid=uid, hp=hp, max_hp=max_hp, integrity=0, integrity_max=integrity_max,
            weak_to=[Faction.HELPDESK])
    d.statuses.append(StatusEffect(kind=StatusEffectKind.VULNERABLE, turns_left=2, value=0.30))
    return d


def test_can_delete_requires_crashed_and_low_hp():
    actor = _mk(uid="a0", side="A", burnout=0)
    low = _crashed(hp=200)   # 20% <= 25% threshold
    high = _crashed(hp=900)  # 90% > threshold
    assert _can_delete(actor, low) is True
    assert _can_delete(actor, high) is False


def test_high_burnout_can_delete_any_hp():
    actor = _mk(uid="a0", side="A", burnout=90)
    high = _crashed(hp=900)
    assert _can_delete(actor, high) is True  # burnout-dump ignores HP threshold


def test_delete_action_kills_target_and_logs():
    actor = _mk(uid="a0", side="A", faction=Faction.HELPDESK, burnout=0)
    tgt = _crashed(uid="e0", hp=200)
    log = []
    _act(actor, allies=[actor], enemies=[tgt], rng=random.Random(1),
         log=log, action_type="delete", forced_target_uid="e0")
    assert tgt.dead is True
    assert tgt.hp == 0
    assert any(e["type"] == "DELETED" for e in log)


def test_delete_falls_through_when_invalid():
    actor = _mk(uid="a0", side="A", faction=Faction.HELPDESK, basic_mult=1.0, burnout=0)
    tgt = _crashed(uid="e0", hp=900)  # too healthy, low burnout -> not deletable
    log = []
    _act(actor, allies=[actor], enemies=[tgt], rng=random.Random(1),
         log=log, action_type="delete", forced_target_uid="e0")
    assert tgt.dead is False  # fell through to a basic attack
    assert not any(e["type"] == "DELETED" for e in log)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_system_integrity.py -k "delete or can_delete" -v`
Expected: FAIL — `_can_delete` / delete branch not defined.

- [ ] **Step 3: Add the `_can_delete` helper**

In `app/combat.py`, after `_needs_target_choice` (~line 412), add:

```python
def _is_crashed(u: CombatUnit) -> bool:
    """A unit is Crashed while its vulnerability window is open."""
    return any(s.kind == StatusEffectKind.VULNERABLE for s in u.statuses)


def _can_delete(actor: CombatUnit, target: CombatUnit) -> bool:
    """Mode 1 (battlebuttonsets.md §5.5): target must be Crashed and at/below the
    execute HP fraction. High-burnout actors bypass the HP gate (burnout-dump)."""
    if target.dead or not _is_crashed(target):
        return False
    if actor.burnout >= BURNOUT_HIGH:
        return True
    return target.hp <= int(target.max_hp * DELETE_EXECUTE_HP_FRAC)
```

- [ ] **Step 4: Add the `delete` branch in `_act`**

In `_act`, immediately after the DEFEND block (after line 459 `return 0`), add:

```python
    # DELETE: player chose the finisher. Valid only on a Crashed, low-HP enemy
    # (or any Crashed enemy if the actor is in burnout-dump range). Falls through
    # to a normal action if invalid so the turn isn't wasted.
    if action_type == "delete":
        tgt = next((u for u in enemies if u.uid == forced_target_uid and not u.dead), None)
        if tgt is not None and _can_delete(actor, tgt):
            tgt.hp = 0
            tgt.dead = True
            if actor.burnout >= BURNOUT_HIGH:
                actor.burnout = max(0, actor.burnout - BURNOUT_DEFEND_SHED)
            log.append({"type": "DELETED", "source": actor.uid, "target": tgt.uid})
            log.append({"type": "DEATH", "unit": tgt.uid})
            return 0
        action_type = None  # invalid finisher -> fall through to normal action cascade
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_system_integrity.py -k "delete or can_delete" -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app/combat.py tests/test_system_integrity.py
git commit -m "feat(combat): Deleted execute action (crash + low-HP / burnout-dump)"
```

---

### Task 9: Full-suite regression + final commit

**Files:** none (verification only)

- [ ] **Step 1: Run the full backend suite**

Run: `uv run pytest 2>&1 | tail -15`
Expected: all green except the known pre-existing `rest_xp` timing flake. The new `tests/test_system_integrity.py` adds ~20 passing tests. If any EXISTING test regresses (e.g. a combat test asserting exact damage now shifted by burnout), investigate: heroes must default `burnout=0`, `integrity_max=0`, `weak_to=[]`, so existing battles are unaffected — a regression means a default leaked. Fix the default, do not weaken the test.

- [ ] **Step 2: Confirm hero defaults are inert**

Run: `uv run pytest tests/ -k "combat or battle or arena or raid" 2>&1 | tail -15`
Expected: PASS. Confirms the new fields are no-ops for units that don't opt in (integrity_max 0, burnout 0).

- [ ] **Step 3: Final commit**

```bash
git add -A
git restore --staged uv.lock 2>/dev/null; git checkout -- uv.lock 2>/dev/null
git commit -m "test(combat): system integrity core green against full suite" --allow-empty
```

---

## Self-review notes

- **Spec coverage:** Integrity bar + weakness axis (T1-2,5), off-type 15% (T2, §7), Crash = stun+vulnerable+flavored (T3), integrity refill (T4), Burnout double-edged (T6-7), Defend shed (T6), Deleted mode-1 + burnout-dump (T8). Deferred to Plan 2/3 (noted): enemy `weak_to` seeding, `InteractiveStateOut` surfacing, HUD, the recycle-bin input, Deleted bonus loot/multipliers, universal-exploit banner, Composure gear.
- **Type consistency:** `_damage` returns `(int, bool)` everywhere (matches existing callers). New statuses use existing `StatusEffect`/`StatusEffectKind`. `_can_delete`/`_is_crashed`/`_is_weakness` signatures stable across tasks.
- **Inertness:** all new `CombatUnit` fields default to no-op values so existing battles/tests are unaffected — verified in Task 9.
- **Placeholders:** none — every code/test step is concrete.
