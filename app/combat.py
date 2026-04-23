"""Turn-based combat resolver. Pure: no DB, no I/O.

A unit's turn meter fills by `spd` per tick; first unit to hit 100 acts.

Specials are described as JSON dicts on the HeroTemplate:

    {
      "name": "...",
      "type": "DAMAGE|HEAL|BUFF|DEBUFF|REVIVE|SHIELD|MULTIHIT|AOE_DAMAGE|CLEANSE",
      "mult": 1.5,                   # damage multiplier (if applicable)
      "hits": 1,                     # multi-hit count
      "aoe": false,
      "target": "enemy_lowest_hp" | "ally_lowest_hp" | "self" | "all_enemies" | "all_allies",
      "effect": {"kind": "POISON", "turns": 2, "value": 0.15},  # optional
      "self_effect": {...}           # optional side effect on self
    }

The resolver is intentionally simple but gives a recognisable hero-collector feel.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from typing import Any

from app.models import BattleOutcome, Role, StatusEffectKind


# Stat scaling: stats at level L are base * (1 + 0.1 * (L - 1)). Linear & predictable.
STAT_SCALE_PER_LEVEL = 0.10
STAR_SCALE_PER_STAR = 0.15  # +15% per star above 1

# Combat log cap — Battle.log_json / ArenaMatch.log_json are String(65536).
# Long AoE teams can produce 300+ entries; trim the middle to stay well under the cap.
COMBAT_LOG_MAX_ENTRIES = 200


def trim_combat_log(log: list[dict]) -> list[dict]:
    """Cap log length. Keeps first/last entries and inserts a single marker if truncated."""
    if len(log) <= COMBAT_LOG_MAX_ENTRIES:
        return log
    head = COMBAT_LOG_MAX_ENTRIES // 2
    tail = COMBAT_LOG_MAX_ENTRIES - head - 1  # leave room for marker
    return [
        *log[:head],
        {"type": "log_truncated", "skipped": len(log) - head - tail},
        *log[-tail:],
    ]


def scale_stat(base: int, level: int, stars: int = 1) -> int:
    level_mult = 1.0 + STAT_SCALE_PER_LEVEL * (level - 1)
    star_mult = 1.0 + STAR_SCALE_PER_STAR * (stars - 1)
    return int(round(base * level_mult * star_mult))


def level_cap_for_stars(stars: int) -> int:
    # 1* = 10, 2* = 15, 3* = 20, 4* = 25, 5* = 30
    return 10 + 5 * max(1, min(5, stars))


def power_rating(hp: int, atk: int, def_: int, spd: int) -> int:
    # Coarse power score for display / matchmaking.
    return int(hp * 0.25 + atk * 1.0 + def_ * 0.8 + spd * 2.0)


@dataclass
class StatusEffect:
    kind: StatusEffectKind
    turns_left: int
    value: float = 0.0  # e.g. poison tick fraction or buff multiplier


@dataclass
class CombatUnit:
    uid: str  # "a0", "a1", ..., "e0", "e1" (distinct within a battle)
    side: str  # "A" or "B"
    name: str
    role: Role
    level: int
    max_hp: int
    hp: int
    atk: int
    def_: int
    spd: int
    basic_mult: float
    special: dict | None
    special_cooldown_max: int
    special_cooldown_left: int = 0
    turn_meter: float = 0.0
    statuses: list[StatusEffect] = field(default_factory=list)
    dead: bool = False
    shielded: bool = False
    special_level: int = 1  # 1-5; scales special damage/effect values
    has_violent: bool = False
    has_lifesteal: bool = False

    # True base for buff/debuff computation.
    base_atk: int = 0
    base_def: int = 0


def _special_scale(level: int) -> float:
    # +10% per level beyond 1 (level 5 = 1.4x).
    return 1.0 + 0.10 * max(0, level - 1)


def _effective_atk(u: CombatUnit) -> int:
    mult = 1.0
    for s in u.statuses:
        if s.kind == StatusEffectKind.ATK_UP:
            mult *= 1.0 + s.value
    return max(1, int(round(u.base_atk * mult)))


def _effective_def(u: CombatUnit) -> int:
    mult = 1.0
    for s in u.statuses:
        if s.kind == StatusEffectKind.DEF_DOWN:
            mult *= max(0.3, 1.0 - s.value)
    return max(1, int(round(u.base_def * mult)))


def _damage(attacker: CombatUnit, defender: CombatUnit, multiplier: float, rng: random.Random) -> int:
    atk = _effective_atk(attacker)
    df = _effective_def(defender)
    raw = atk * multiplier * (1.0 - df / (df + 1000.0))
    variance = rng.uniform(0.85, 1.15)
    crit = rng.random() < 0.05
    dmg = raw * variance * (1.5 if crit else 1.0)
    return max(1, int(round(dmg))), crit


def _apply_damage(defender: CombatUnit, amount: int) -> int:
    if defender.shielded:
        defender.shielded = False
        return 0
    defender.hp = max(0, defender.hp - amount)
    if defender.hp == 0:
        defender.dead = True
    return amount


def _pick_target(actor: CombatUnit, allies: list[CombatUnit], enemies: list[CombatUnit], selector: str) -> CombatUnit | None:
    pool_live = [u for u in (enemies if selector.startswith("enemy") else allies) if not u.dead]
    if selector == "self":
        return actor
    if not pool_live:
        return None
    if selector in ("enemy_lowest_hp", "ally_lowest_hp"):
        return min(pool_live, key=lambda u: (u.hp, u.uid))
    if selector == "enemy_random":
        return pool_live[0]  # deterministic; randomness lives in roll_rng
    if selector in ("all_enemies", "all_allies"):
        # Caller handles AOE.
        return pool_live[0]
    return pool_live[0]


def _pick_aoe_targets(actor: CombatUnit, allies: list[CombatUnit], enemies: list[CombatUnit], selector: str) -> list[CombatUnit]:
    if selector == "all_enemies":
        return [u for u in enemies if not u.dead]
    if selector == "all_allies":
        return [u for u in allies if not u.dead]
    return []


def _tick_statuses(unit: CombatUnit, log: list[dict]) -> None:
    # End-of-turn status tick: poisons apply, durations decrement.
    new_statuses: list[StatusEffect] = []
    for s in unit.statuses:
        if s.kind == StatusEffectKind.POISON and not unit.dead:
            tick_dmg = max(1, int(unit.max_hp * s.value))
            unit.hp = max(0, unit.hp - tick_dmg)
            if unit.hp == 0:
                unit.dead = True
            log.append({"type": "DAMAGE", "target": unit.uid, "amount": tick_dmg, "source": "POISON"})
            if unit.dead:
                log.append({"type": "DEATH", "unit": unit.uid})
        s.turns_left -= 1
        if s.turns_left > 0:
            new_statuses.append(s)
        else:
            log.append({"type": "STATUS_EXPIRED", "unit": unit.uid, "kind": str(s.kind)})
    unit.statuses = new_statuses


def _apply_effect(target: CombatUnit, effect: dict, log: list[dict]) -> None:
    kind = StatusEffectKind(effect["kind"])
    turns = int(effect.get("turns", 2))
    value = float(effect.get("value", 0.25))
    if kind == StatusEffectKind.SHIELD:
        target.shielded = True
        log.append({"type": "STATUS_APPLIED", "unit": target.uid, "kind": "SHIELD", "turns": 1, "value": 1.0})
        return
    target.statuses.append(StatusEffect(kind=kind, turns_left=turns, value=value))
    log.append({"type": "STATUS_APPLIED", "unit": target.uid, "kind": str(kind), "turns": turns, "value": value})


def _is_stunned(u: CombatUnit) -> bool:
    return any(s.kind == StatusEffectKind.STUN for s in u.statuses)


@dataclass
class CombatResult:
    outcome: BattleOutcome
    log: list[dict]
    survivors_a: list[str]
    survivors_b: list[str]
    ticks: int

    @property
    def log_hash(self) -> str:
        h = hashlib.sha256(json.dumps(self.log, sort_keys=True, default=str).encode("utf-8"))
        return h.hexdigest()[:16]


def _lifesteal(actor: CombatUnit, damage_dealt: int, log: list[dict]) -> None:
    if not actor.has_lifesteal or damage_dealt <= 0 or actor.dead:
        return
    heal = max(1, int(round(damage_dealt * 0.30)))
    new_hp = min(actor.max_hp, actor.hp + heal)
    if new_hp != actor.hp:
        actor.hp = new_hp
        log.append({"type": "LIFESTEAL", "unit": actor.uid, "amount": heal, "hp": actor.hp})


def _act(actor: CombatUnit, allies: list[CombatUnit], enemies: list[CombatUnit], rng: random.Random, log: list[dict]) -> int:
    """Execute one action. Returns total damage the actor dealt (for lifesteal accounting)."""
    damage_dealt = 0

    if _is_stunned(actor):
        log.append({"type": "STUNNED", "unit": actor.uid})
        return damage_dealt

    # Prefer special if ready, else basic.
    use_special = actor.special is not None and actor.special_cooldown_left == 0
    if use_special:
        spec = actor.special
        stype = spec.get("type", "DAMAGE")
        selector = spec.get("target", "enemy_lowest_hp")
        scale = _special_scale(actor.special_level)
        log.append({"type": "SPECIAL", "unit": actor.uid, "name": spec.get("name", "special"), "sl": actor.special_level})

        def _scaled_effect(eff: dict) -> dict:
            """Return a copy of an effect with `value` bumped by special_level."""
            return {**eff, "value": float(eff.get("value", 0.25)) * scale}

        if stype == "DAMAGE":
            tgt = _pick_target(actor, allies, enemies, selector)
            if tgt is not None:
                hits = int(spec.get("hits", 1))
                mult = float(spec.get("mult", actor.basic_mult * 1.5)) * scale
                for _ in range(hits):
                    if tgt.dead:
                        break
                    dmg, crit = _damage(actor, tgt, mult / max(1, hits), rng)
                    dealt = _apply_damage(tgt, dmg)
                    damage_dealt += dealt
                    log.append({
                        "type": "DAMAGE", "source": actor.uid, "target": tgt.uid,
                        "amount": dealt, "crit": crit, "via": "SPECIAL",
                    })
                    if tgt.dead:
                        log.append({"type": "DEATH", "unit": tgt.uid})
                        break
                if "effect" in spec and not tgt.dead:
                    _apply_effect(tgt, _scaled_effect(spec["effect"]), log)

        elif stype == "AOE_DAMAGE":
            targets = _pick_aoe_targets(actor, allies, enemies, "all_enemies")
            mult = float(spec.get("mult", actor.basic_mult * 0.6)) * scale
            for tgt in targets:
                dmg, crit = _damage(actor, tgt, mult, rng)
                dealt = _apply_damage(tgt, dmg)
                damage_dealt += dealt
                log.append({
                    "type": "DAMAGE", "source": actor.uid, "target": tgt.uid,
                    "amount": dealt, "crit": crit, "via": "AOE",
                })
                if tgt.dead:
                    log.append({"type": "DEATH", "unit": tgt.uid})
                elif "effect" in spec:
                    _apply_effect(tgt, _scaled_effect(spec["effect"]), log)

        elif stype == "HEAL":
            tgt = _pick_target(actor, allies, enemies, selector)
            if tgt is not None:
                amount = max(1, int(tgt.max_hp * float(spec.get("frac", 0.25))))
                tgt.hp = min(tgt.max_hp, tgt.hp + amount)
                log.append({"type": "HEAL", "source": actor.uid, "target": tgt.uid, "amount": amount})

        elif stype == "BUFF":
            tgt = _pick_target(actor, allies, enemies, selector)
            if tgt is not None:
                _apply_effect(tgt, _scaled_effect(spec["effect"]), log)

        elif stype == "AOE_BUFF":
            for tgt in _pick_aoe_targets(actor, allies, enemies, "all_allies"):
                _apply_effect(tgt, _scaled_effect(spec["effect"]), log)

        elif stype == "DEBUFF":
            tgt = _pick_target(actor, allies, enemies, selector)
            if tgt is not None:
                _apply_effect(tgt, _scaled_effect(spec["effect"]), log)

        elif stype == "AOE_DEBUFF":
            for tgt in _pick_aoe_targets(actor, allies, enemies, "all_enemies"):
                _apply_effect(tgt, _scaled_effect(spec["effect"]), log)

        elif stype == "SHIELD":
            tgt = _pick_target(actor, allies, enemies, selector)
            if tgt is not None:
                tgt.shielded = True
                log.append({"type": "STATUS_APPLIED", "unit": tgt.uid, "kind": "SHIELD", "turns": 1, "value": 1.0})

        elif stype == "CLEANSE":
            tgt = _pick_target(actor, allies, enemies, selector)
            if tgt is not None:
                before = len(tgt.statuses)
                tgt.statuses = [
                    s for s in tgt.statuses
                    if s.kind not in (StatusEffectKind.POISON, StatusEffectKind.DEF_DOWN, StatusEffectKind.STUN)
                ]
                log.append({"type": "CLEANSE", "unit": tgt.uid, "removed": before - len(tgt.statuses)})
                if "heal_frac" in spec:
                    amount = max(1, int(tgt.max_hp * float(spec["heal_frac"])))
                    tgt.hp = min(tgt.max_hp, tgt.hp + amount)
                    log.append({"type": "HEAL", "source": actor.uid, "target": tgt.uid, "amount": amount})

        elif stype == "REVIVE":
            # Pick first dead ally; resurrect at frac HP.
            target = next((a for a in allies if a.dead), None)
            if target is not None:
                frac = float(spec.get("frac", 0.3))
                target.dead = False
                target.hp = max(1, int(target.max_hp * frac))
                log.append({"type": "REVIVE", "source": actor.uid, "target": target.uid, "hp": target.hp})

        # Side effect on self.
        if "self_effect" in spec:
            _apply_effect(actor, spec["self_effect"], log)

        actor.special_cooldown_left = actor.special_cooldown_max
    else:
        # Basic attack: damage enemy_lowest_hp.
        tgt = _pick_target(actor, allies, enemies, "enemy_lowest_hp")
        if tgt is None:
            return damage_dealt
        dmg, crit = _damage(actor, tgt, actor.basic_mult, rng)
        dealt = _apply_damage(tgt, dmg)
        damage_dealt += dealt
        log.append({
            "type": "DAMAGE", "source": actor.uid, "target": tgt.uid,
            "amount": dealt, "crit": crit, "via": "BASIC",
        })
        if tgt.dead:
            log.append({"type": "DEATH", "unit": tgt.uid})

    return damage_dealt


def simulate(team_a: list[CombatUnit], team_b: list[CombatUnit], rng: random.Random) -> CombatResult:
    log: list[dict] = []
    max_ticks = 400
    ticks = 0

    for u in team_a + team_b:
        u.base_atk = u.atk
        u.base_def = u.def_

    def alive(team: list[CombatUnit]) -> bool:
        return any(not u.dead for u in team)

    while ticks < max_ticks and alive(team_a) and alive(team_b):
        # Advance turn meters simultaneously.
        for u in team_a + team_b:
            if not u.dead:
                u.turn_meter += u.spd
        # Actors that have accumulated enough go in order of highest meter.
        ready = sorted(
            (u for u in team_a + team_b if not u.dead and u.turn_meter >= 100),
            key=lambda u: (-u.turn_meter, u.uid),
        )
        for actor in ready:
            if actor.dead:
                continue
            if not (alive(team_a) and alive(team_b)):
                break
            log.append({"type": "TURN", "unit": actor.uid, "hp": actor.hp, "meter": round(actor.turn_meter, 2)})
            dealt = _act(
                actor,
                allies=team_a if actor.side == "A" else team_b,
                enemies=team_b if actor.side == "A" else team_a,
                rng=rng,
                log=log,
            )
            actor.turn_meter -= 100
            _lifesteal(actor, dealt, log)
            # End-of-turn tick for the actor only (keeps log shorter).
            _tick_statuses(actor, log)
            # Cooldowns on the actor only.
            if actor.special_cooldown_left > 0:
                actor.special_cooldown_left -= 1
            # VIOLENT: 20% chance of an extra turn — grant 100 meter, re-sort next pass.
            if actor.has_violent and not actor.dead and rng.random() < 0.20:
                actor.turn_meter += 100
                log.append({"type": "VIOLENT_TURN", "unit": actor.uid})
        ticks += 1

    if alive(team_a) and not alive(team_b):
        outcome = BattleOutcome.WIN
    elif alive(team_b) and not alive(team_a):
        outcome = BattleOutcome.LOSS
    else:
        outcome = BattleOutcome.DRAW

    log.append({"type": "END", "outcome": str(outcome), "ticks": ticks})
    return CombatResult(
        outcome=outcome,
        log=log,
        survivors_a=[u.uid for u in team_a if not u.dead],
        survivors_b=[u.uid for u in team_b if not u.dead],
        ticks=ticks,
    )


# -- Convenience builder used by both the battles router and the deterministic test. --


def build_unit(
    uid: str,
    side: str,
    *,
    name: str,
    role: Role,
    level: int,
    base_hp: int,
    base_atk: int,
    base_def: int,
    base_spd: int,
    basic_mult: float,
    special: dict | None,
    special_cooldown: int,
    gear_bonus: dict | None = None,
    special_level: int = 1,
    stars: int = 1,
) -> CombatUnit:
    hp = scale_stat(base_hp, level, stars)
    atk = scale_stat(base_atk, level, stars)
    df = scale_stat(base_def, level, stars)
    spd = base_spd  # SPD isn't scaled by level in this MVP.
    if gear_bonus:
        hp += int(gear_bonus.get("hp", 0))
        atk += int(gear_bonus.get("atk", 0))
        df += int(gear_bonus.get("def", 0))
        spd += int(gear_bonus.get("spd", 0))
        # Percentage bonuses from completed gear sets.
        pct = gear_bonus.get("pct", {})
        if pct:
            hp = int(round(hp * (1.0 + pct.get("hp", 0.0))))
            atk = int(round(atk * (1.0 + pct.get("atk", 0.0))))
            df = int(round(df * (1.0 + pct.get("def", 0.0))))
            spd = int(round(spd * (1.0 + pct.get("spd", 0.0))))
    active = (gear_bonus or {}).get("active", {}) if gear_bonus else {}
    return CombatUnit(
        uid=uid,
        side=side,
        name=name,
        role=role,
        level=level,
        max_hp=hp,
        hp=hp,
        atk=atk,
        def_=df,
        spd=spd,
        basic_mult=basic_mult,
        special=special,
        special_cooldown_max=special_cooldown,
        special_cooldown_left=0,
        turn_meter=0.0,
        base_atk=atk,
        base_def=df,
        special_level=special_level,
        has_violent=bool(active.get("violent")),
        has_lifesteal=bool(active.get("lifesteal")),
    )


def unit_power(u: CombatUnit) -> int:
    return power_rating(u.max_hp, u.atk, u.def_, u.spd)
