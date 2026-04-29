"""Phase 3.2 combat tests: mana resource + target priority."""

from __future__ import annotations

import random

from app.combat import _act, _pick_priority_target, build_unit, simulate
from app.models import BattleOutcome, Role


def _ranged(uid: str, side: str, *, mana_cost: int = 10, mana_regen_per_turn: int = 15):
    return build_unit(
        uid=uid, side=side,
        name="Archer", role=Role.ATK, level=1,
        base_hp=800, base_atk=90, base_def=60, base_spd=95,
        basic_mult=1.0, special=None, special_cooldown=0,
        attack_kind="ranged",
        mana_cost=mana_cost,
        mana_regen_per_turn=mana_regen_per_turn,
    )


def _melee(uid: str, side: str):
    return build_unit(
        uid=uid, side=side,
        name="Warrior", role=Role.ATK, level=1,
        base_hp=800, base_atk=90, base_def=60, base_spd=95,
        basic_mult=1.0, special=None, special_cooldown=0,
        attack_kind="melee",
    )


# ---------------------------------------------------------------------------
# Mana tests
# ---------------------------------------------------------------------------

def test_ranged_hero_starts_with_enough_mana_to_act_turn_1() -> None:
    """build_unit seeds mana at mana_regen_per_turn * 2, so the hero can
    always attack on turn 1 without waiting for regen."""
    hero = _ranged("a0", "A", mana_cost=10, mana_regen_per_turn=15)
    assert hero.attack_kind == "ranged"
    assert hero.mana >= hero.mana_cost, (
        f"hero starts with {hero.mana} mana but needs {hero.mana_cost} to act"
    )


def test_ranged_hero_with_zero_mana_skips_basic_attack() -> None:
    """A ranged hero whose mana falls below mana_cost must skip the basic
    attack and log a MANA_EMPTY event instead of dealing damage."""
    rng = random.Random(0)
    hero = _ranged("a0", "A", mana_cost=10, mana_regen_per_turn=0)
    hero.mana = 0  # drain mana and disable regen
    enemy = _melee("b0", "B")
    enemy_hp_before = enemy.hp

    log: list[dict] = []
    _act(hero, [hero], [enemy], rng, log)

    assert any(e.get("kind") == "MANA_EMPTY" for e in log), "expected MANA_EMPTY in log"
    assert enemy.hp == enemy_hp_before, "enemy took damage despite MANA_EMPTY"


def test_mana_regenerates_each_turn() -> None:
    """MANA_REGEN events fire at the start of each turn for ranged heroes
    when below the mana cap and regen > 0."""
    rng = random.Random(0)
    hero = _ranged("a0", "A", mana_cost=10, mana_regen_per_turn=5)
    hero.mana = 0  # start empty; regen = 5
    enemy = _melee("b0", "B")

    log: list[dict] = []
    _act(hero, [hero], [enemy], rng, log)

    regen_events = [e for e in log if e.get("type") == "MANA_REGEN"]
    assert regen_events, "expected at least one MANA_REGEN event"
    assert regen_events[0]["amount"] == 5


def test_melee_hero_unaffected_by_mana() -> None:
    """Melee heroes have mana=0, mana_cost=0 and never log MANA_EMPTY
    or MANA_REGEN events regardless of how many turns pass."""
    rng = random.Random(0)
    hero = _melee("a0", "A")
    enemy = _melee("b0", "B")

    assert hero.mana == 0
    assert hero.mana_cost == 0

    log: list[dict] = []
    _act(hero, [hero], [enemy], rng, log)

    assert not any(e.get("kind") == "MANA_EMPTY" for e in log)
    assert not any(e.get("type") == "MANA_REGEN" for e in log)
    assert any(e.get("type") == "DAMAGE" for e in log), "melee hero should still attack"


# ---------------------------------------------------------------------------
# Target priority tests
# ---------------------------------------------------------------------------

def _enemies_with_varying_hp():
    """Return three enemies with different HP values for priority testing."""
    low = _melee("b0", "B")
    low.hp = 50
    low.max_hp = 800

    mid = _melee("b1", "B")
    mid.hp = 400
    mid.max_hp = 800

    high = _melee("b2", "B")
    high.hp = 750
    high.max_hp = 800

    return low, mid, high


def test_target_priority_lowest_hp_selects_weakest_enemy() -> None:
    low, mid, high = _enemies_with_varying_hp()
    tgt = _pick_priority_target([low, mid, high], "lowest_hp")
    assert tgt is low, f"expected lowest-HP enemy (hp={low.hp}), got hp={tgt.hp if tgt else None}"


def test_target_priority_highest_threat_selects_strongest_attacker() -> None:
    """highest_threat picks the enemy with the largest effective ATK."""
    weak = build_unit(
        uid="b0", side="B",
        name="Minion", role=Role.ATK, level=1,
        base_hp=800, base_atk=50, base_def=60, base_spd=95,
        basic_mult=1.0, special=None, special_cooldown=0,
    )
    strong = build_unit(
        uid="b1", side="B",
        name="Boss", role=Role.ATK, level=1,
        base_hp=800, base_atk=200, base_def=60, base_spd=95,
        basic_mult=1.0, special=None, special_cooldown=0,
    )
    tgt = _pick_priority_target([weak, strong], "highest_threat")
    assert tgt is strong, (
        f"expected high-ATK enemy (atk={strong.atk}), got atk={tgt.atk if tgt else None}"
    )


def test_simulate_target_priority_lowest_hp_kills_weakest_first() -> None:
    """When target_priority='lowest_hp', the simulator should kill the
    weakest enemy before moving on to tougher ones."""
    rng = random.Random(42)
    team_a = [
        build_unit(
            uid=f"a{i}", side="A",
            name="Hero", role=Role.ATK, level=30,
            base_hp=2000, base_atk=300, base_def=100, base_spd=100,
            basic_mult=1.5, special=None, special_cooldown=0,
        )
        for i in range(3)
    ]
    # One very weak enemy and two strong ones.
    weak = build_unit(
        uid="b0", side="B",
        name="WeakEnemy", role=Role.DEF, level=1,
        base_hp=100, base_atk=10, base_def=10, base_spd=50,
        basic_mult=1.0, special=None, special_cooldown=0,
    )
    strong1 = build_unit(
        uid="b1", side="B",
        name="StrongEnemy", role=Role.DEF, level=30,
        base_hp=3000, base_atk=100, base_def=200, base_spd=50,
        basic_mult=1.0, special=None, special_cooldown=0,
    )
    strong2 = build_unit(
        uid="b2", side="B",
        name="StrongEnemy2", role=Role.DEF, level=30,
        base_hp=3000, base_atk=100, base_def=200, base_spd=50,
        basic_mult=1.0, special=None, special_cooldown=0,
    )
    team_b = [weak, strong1, strong2]

    result = simulate(team_a, team_b, rng, target_priority="lowest_hp")

    # The weak enemy (b0) should be killed before either strong enemy.
    death_events = [e for e in result.log if e.get("type") == "DEATH"]
    if death_events:
        first_death = death_events[0]["unit"]
        assert first_death == "b0", (
            f"expected weak enemy 'b0' to die first, but '{first_death}' died first"
        )
