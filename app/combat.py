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

from collections import Counter

from app.models import BattleOutcome, Faction, Role, StatusEffectKind


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
    faction: Faction | None = None
    # Hail-mary fires at end of own turn the first time HP drops to ≤5%.
    # One-shot per battle — flag flips when the desperation effect resolves
    # (whether it dealt damage, healed, or did nothing for lack of targets).
    has_used_hail_mary: bool = False

    # True base for buff/debuff computation.
    base_atk: int = 0
    base_def: int = 0

    # Phase 3.1 — attack channel. "melee" or "ranged". Phase 3.2 (active
    # combat UI) will use this to gate which units a player can target;
    # for now the resolver echoes it on every basic-attack log entry so
    # the replay viewer can render melee-lunge vs ranged-projectile
    # animations differently.
    attack_kind: str = "melee"


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


def _apply_damage(
    defender: CombatUnit,
    amount: int,
    *,
    attacker: CombatUnit | None = None,
    log: list[dict] | None = None,
    can_reflect: bool = True,
) -> int:
    """Apply `amount` to defender; return amount actually dealt (0 if shielded).

    On a hit:
      - SHIELD absorbs the entire blow (lost on use).
      - FREEZE on the defender breaks immediately — fire/melee thaw the target.
      - REFLECT on the defender bounces a fraction of dealt damage back to
        the attacker. Reflected damage cannot itself reflect (`can_reflect=False`)
        so a REFLECT mirror never recurses into a ping-pong.
    """
    if defender.shielded:
        defender.shielded = False
        return 0
    defender.hp = max(0, defender.hp - amount)
    if defender.hp == 0:
        defender.dead = True
    if amount > 0 and any(s.kind == StatusEffectKind.FREEZE for s in defender.statuses):
        defender.statuses = [s for s in defender.statuses if s.kind != StatusEffectKind.FREEZE]
        if log is not None:
            log.append({"type": "STATUS_BROKEN", "unit": defender.uid, "kind": "FREEZE", "reason": "damaged"})
    if can_reflect and amount > 0 and attacker is not None and not attacker.dead and log is not None:
        reflect_value = max(
            (s.value for s in defender.statuses if s.kind == StatusEffectKind.REFLECT),
            default=0.0,
        )
        if reflect_value > 0:
            reflected = max(1, int(round(amount * reflect_value)))
            actual = _apply_damage(attacker, reflected, attacker=None, log=log, can_reflect=False)
            log.append({"type": "REFLECT", "source": defender.uid, "target": attacker.uid, "amount": actual})
            if attacker.dead:
                log.append({"type": "DEATH", "unit": attacker.uid})
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
    """End-of-actor-turn status tick: damage-over-time fires, durations decrement.

    POISON and BURN both deal max_hp * value as a tick. They differ in source/
    cleanse semantics — CLEANSE removes POISON but not BURN by default — so the
    same DoT machinery handles both.
    """
    new_statuses: list[StatusEffect] = []
    for s in unit.statuses:
        if s.kind in (StatusEffectKind.POISON, StatusEffectKind.BURN) and not unit.dead:
            tick_dmg = max(1, int(unit.max_hp * s.value))
            unit.hp = max(0, unit.hp - tick_dmg)
            if unit.hp == 0:
                unit.dead = True
            log.append({"type": "DAMAGE", "target": unit.uid, "amount": tick_dmg, "source": str(s.kind)})
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


def _is_frozen(u: CombatUnit) -> bool:
    return any(s.kind == StatusEffectKind.FREEZE for s in u.statuses)


def _is_heal_blocked(u: CombatUnit) -> bool:
    return any(s.kind == StatusEffectKind.HEAL_BLOCK for s in u.statuses)


def _revive(actor: CombatUnit | None, target: CombatUnit, frac: float, log: list[dict]) -> bool:
    """Bring `target` back at `frac` of max HP. HEAL_BLOCK suppresses the rez —
    a heal-block on a corpse means it stays down. Returns True if revived."""
    if not target.dead:
        return False
    if _is_heal_blocked(target):
        log.append({"type": "REVIVE_BLOCKED", "target": target.uid})
        return False
    target.dead = False
    target.hp = max(1, int(target.max_hp * frac))
    entry = {"type": "REVIVE", "target": target.uid, "hp": target.hp}
    if actor is not None:
        entry["source"] = actor.uid
    log.append(entry)
    return True


def _heal(actor: CombatUnit | None, target: CombatUnit, amount: int, log: list[dict], source: str = "HEAL") -> int:
    """Heal `target` for `amount` HP, respecting HEAL_BLOCK. Returns amount healed (0 if blocked)."""
    if amount <= 0 or target.dead:
        return 0
    if _is_heal_blocked(target):
        log.append({"type": "HEAL_BLOCKED", "target": target.uid, "would_have": amount, "source": source})
        return 0
    new_hp = min(target.max_hp, target.hp + amount)
    healed = new_hp - target.hp
    target.hp = new_hp
    if healed > 0:
        entry = {"type": "HEAL", "target": target.uid, "amount": healed, "source": source}
        if actor is not None:
            entry["source_unit"] = actor.uid
        log.append(entry)
    return healed


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
    healed = _heal(actor, actor, heal, log, source="LIFESTEAL")
    if healed > 0:
        log.append({"type": "LIFESTEAL", "unit": actor.uid, "amount": healed, "hp": actor.hp})


def _act(actor: CombatUnit, allies: list[CombatUnit], enemies: list[CombatUnit], rng: random.Random, log: list[dict]) -> int:
    """Execute one action. Returns total damage the actor dealt (for lifesteal accounting)."""
    damage_dealt = 0

    if _is_stunned(actor):
        log.append({"type": "STUNNED", "unit": actor.uid})
        return damage_dealt
    if _is_frozen(actor):
        log.append({"type": "FROZEN", "unit": actor.uid})
        return damage_dealt

    # Prefer special if ready, else basic.
    use_special = actor.special is not None and actor.special_cooldown_left == 0
    if use_special:
        spec = actor.special
        stype = spec.get("type", "DAMAGE")
        selector = spec.get("target", "enemy_lowest_hp")
        scale = _special_scale(actor.special_level)
        # `kind` carries the special's type (DAMAGE / AOE_DAMAGE / HEAL / etc.)
        # so the replay viewer can pick a presentation per kind — boss specials
        # in particular get a phase-change cinematic instead of the standard
        # yellow caption used for hero specials.
        log.append({
            "type": "SPECIAL",
            "unit": actor.uid,
            "name": spec.get("name", "special"),
            "sl": actor.special_level,
            "kind": stype,
        })

        def _scaled_effect(eff: dict) -> dict:
            """Return a copy of an effect with `value` bumped by special_level."""
            return {**eff, "value": float(eff.get("value", 0.25)) * scale}

        if stype == "DAMAGE":
            tgt = _pick_target(actor, allies, enemies, selector)
            if tgt is not None:
                hits = int(spec.get("hits", 1))
                mult = float(spec.get("mult", actor.basic_mult * 1.5)) * scale
                for _ in range(hits):
                    if tgt.dead or actor.dead:
                        break
                    dmg, crit = _damage(actor, tgt, mult / max(1, hits), rng)
                    dealt = _apply_damage(tgt, dmg, attacker=actor, log=log)
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
                if actor.dead:
                    break
                dmg, crit = _damage(actor, tgt, mult, rng)
                dealt = _apply_damage(tgt, dmg, attacker=actor, log=log)
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
                _heal(actor, tgt, amount, log)

        elif stype == "AOE_HEAL":
            # Heal every live ally for `frac` of their max_hp. Optional `effect`
            # is applied to each ally as well (e.g. ATK_UP), letting one cast
            # both top up the team AND buff them — a fitting support signature.
            for tgt in _pick_aoe_targets(actor, allies, enemies, "all_allies"):
                amount = max(1, int(tgt.max_hp * float(spec.get("frac", 0.20))))
                _heal(actor, tgt, amount, log)
                if "effect" in spec:
                    _apply_effect(tgt, _scaled_effect(spec["effect"]), log)

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
                _CLEANSABLE = (
                    StatusEffectKind.POISON,
                    StatusEffectKind.BURN,
                    StatusEffectKind.DEF_DOWN,
                    StatusEffectKind.STUN,
                    StatusEffectKind.FREEZE,
                    StatusEffectKind.HEAL_BLOCK,
                )
                before = len(tgt.statuses)
                tgt.statuses = [s for s in tgt.statuses if s.kind not in _CLEANSABLE]
                log.append({"type": "CLEANSE", "unit": tgt.uid, "removed": before - len(tgt.statuses)})
                if "heal_frac" in spec:
                    amount = max(1, int(tgt.max_hp * float(spec["heal_frac"])))
                    _heal(actor, tgt, amount, log, source="CLEANSE")

        elif stype == "REVIVE":
            # Pick first dead ally; resurrect at frac HP. HEAL_BLOCK on the
            # corpse blocks the rez (lifelock specials counter rez comp).
            target = next((a for a in allies if a.dead), None)
            if target is not None:
                _revive(actor, target, float(spec.get("frac", 0.3)), log)

        elif stype == "BOSS_PHASE":
            # Raid-boss signature move. Combines an AOE strike with multiple
            # statuses on enemies + self-buffs in a single cast — a "phase
            # change" feel that hero specials don't have. Schema:
            #   {
            #     "type": "BOSS_PHASE",
            #     "name": "...",
            #     "mult": 1.5,
            #     "effects":      [<status>, ...],   # applied to every live enemy
            #     "self_effects": [<status>, ...],   # applied to the boss itself
            #   }
            # Only intended for raid-boss templates. Status `value` is scaled
            # by special_level the same way other specials are.
            targets = _pick_aoe_targets(actor, allies, enemies, "all_enemies")
            mult = float(spec.get("mult", actor.basic_mult * 1.0)) * scale
            for tgt in targets:
                if actor.dead:
                    break
                dmg, crit = _damage(actor, tgt, mult, rng)
                dealt = _apply_damage(tgt, dmg, attacker=actor, log=log)
                damage_dealt += dealt
                log.append({
                    "type": "DAMAGE", "source": actor.uid, "target": tgt.uid,
                    "amount": dealt, "crit": crit, "via": "BOSS_PHASE",
                })
                if tgt.dead:
                    log.append({"type": "DEATH", "unit": tgt.uid})
                else:
                    for eff in spec.get("effects", []):
                        _apply_effect(tgt, _scaled_effect(eff), log)
            for self_eff in spec.get("self_effects", []):
                _apply_effect(actor, _scaled_effect(self_eff), log)

        elif stype == "AOE_REVIVE":
            # Resurrect every dead ally at frac HP. Strong but expensive — meant
            # to be paired with high cooldowns (4-6) on the template's special.
            frac = float(spec.get("frac", 0.25))
            for ally in allies:
                if ally.dead:
                    _revive(actor, ally, frac, log)

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
        dealt = _apply_damage(tgt, dmg, attacker=actor, log=log)
        damage_dealt += dealt
        log.append({
            "type": "DAMAGE", "source": actor.uid, "target": tgt.uid,
            "amount": dealt, "crit": crit, "via": "BASIC",
            # Phase 3.1 — replay viewer renders melee-lunge vs ranged-
            # projectile differently. Defaults to melee for backwards
            # compat with pre-Phase-3 combat logs.
            "channel": getattr(actor, "attack_kind", "melee"),
        })
        if tgt.dead:
            log.append({"type": "DEATH", "unit": tgt.uid})

    return damage_dealt


def team_faction_synergy(team: list[CombatUnit]) -> dict | None:
    """Compute the faction synergy bonus a team earns from running 3+ heroes
    of the same faction. Returns None if no synergy applies.

    Tiers (per dominant faction count):
      3 → +10% ATK
      4 → +15% ATK, +5% DEF
      5 → +20% ATK, +10% DEF

    Heroes of the *non-dominant* factions on the team don't get the bonus —
    the synergy rewards faction-pure builds, not the team as a whole. With
    a 3-3 split (impossible at 5 slots, possible if team size ever grows)
    the larger group wins; ties resolve to whichever faction enum-orders first.
    """
    counts = Counter(u.faction for u in team if u.faction is not None)
    if not counts:
        return None
    # most_common uses insertion order on ties; sort explicitly for determinism.
    dominant, count = max(counts.items(), key=lambda kv: (kv[1], -list(Faction).index(kv[0])))
    if count < 3:
        return None
    if count == 3:
        atk_pct, def_pct = 0.10, 0.0
    elif count == 4:
        atk_pct, def_pct = 0.15, 0.05
    else:
        atk_pct, def_pct = 0.20, 0.10
    return {"faction": dominant, "count": count, "atk_pct": atk_pct, "def_pct": def_pct}


def _apply_team_synergy(team: list[CombatUnit], log: list[dict]) -> dict | None:
    """Mutate `team` in-place to bake in the faction synergy bonus, then log
    the bonus once so the replay viewer can label it."""
    syn = team_faction_synergy(team)
    if syn is None:
        return None
    for u in team:
        if u.faction != syn["faction"]:
            continue
        if syn["atk_pct"] > 0:
            u.atk = max(1, int(round(u.atk * (1.0 + syn["atk_pct"]))))
        if syn["def_pct"] > 0:
            u.def_ = max(1, int(round(u.def_ * (1.0 + syn["def_pct"]))))
    log.append({
        "type": "FACTION_SYNERGY",
        "side": team[0].side if team else None,
        "faction": str(syn["faction"]),
        "count": syn["count"],
        "atk_pct": syn["atk_pct"],
        "def_pct": syn["def_pct"],
    })
    return syn


# Hail-mary HP threshold. Below this fraction of max_hp, the desperation
# move triggers on the unit's next end-of-turn — once per battle. Tuned at
# 5% so it lands near death but not so low that random crit kills outpace it.
HAIL_MARY_THRESHOLD = 0.05


def _maybe_hail_mary(
    actor: CombatUnit,
    *,
    allies: list[CombatUnit],
    enemies: list[CombatUnit],
    rng: random.Random,
    log: list[dict],
) -> None:
    """End-of-turn check for desperation. Fires once per battle per unit when
    HP dips to ≤5% (the threshold above). Per-role flavor:
      ATK → 'Last Stand': 3.0× basic single-target nuke vs. lowest-HP enemy.
            Fits the channel's "I'm out of patience" rage moment.
      DEF → 'Hold The Line': AOE strike at 0.8× basic_mult applying STUN
            for 1 turn to every survivor — bought time for the team to act.
      SUP → 'You're Welcome': AOE_HEAL the team for 25% of each ally's
            max HP and apply ATK_UP +20% for 3 turns. The clutch revive of
            tempo without the corpse-rez problem.

    Side-specific flavor (per faction or per template) can override these
    later by storing a `hail_mary` dict on the template alongside `special`.
    For now the role default is in. The whole thing is a one-shot — flag
    flips even if no targets are alive (no infinite-fire on stalemate).
    """
    if actor.dead or actor.has_used_hail_mary:
        return
    if actor.max_hp <= 0:
        return
    if actor.hp / actor.max_hp > HAIL_MARY_THRESHOLD:
        return
    actor.has_used_hail_mary = True
    name_by_role = {
        Role.ATK: "Last Stand",
        Role.DEF: "Hold The Line",
        Role.SUP: "You're Welcome",
    }
    role = actor.role if isinstance(actor.role, Role) else Role(actor.role)
    log.append({
        "type": "HAIL_MARY",
        "unit": actor.uid,
        "role": str(role),
        "name": name_by_role.get(role, "Hail Mary"),
        "hp_pct": round(actor.hp / actor.max_hp, 3),
    })

    if role == Role.ATK:
        # Single-target burst at the lowest-HP live enemy.
        live = [u for u in enemies if not u.dead]
        if not live:
            return
        tgt = min(live, key=lambda u: (u.hp, u.uid))
        dmg, crit = _damage(actor, tgt, actor.basic_mult * 3.0, rng)
        dealt = _apply_damage(tgt, dmg, attacker=actor, log=log)
        log.append({
            "type": "DAMAGE", "source": actor.uid, "target": tgt.uid,
            "amount": dealt, "crit": crit, "via": "HAIL_MARY",
        })
        if tgt.dead:
            log.append({"type": "DEATH", "unit": tgt.uid})

    elif role == Role.DEF:
        # AOE strike + STUN to every surviving enemy.
        for tgt in [u for u in enemies if not u.dead]:
            dmg, crit = _damage(actor, tgt, actor.basic_mult * 0.8, rng)
            dealt = _apply_damage(tgt, dmg, attacker=actor, log=log)
            log.append({
                "type": "DAMAGE", "source": actor.uid, "target": tgt.uid,
                "amount": dealt, "crit": crit, "via": "HAIL_MARY",
            })
            if tgt.dead:
                log.append({"type": "DEATH", "unit": tgt.uid})
            else:
                _apply_effect(tgt, {"kind": "STUN", "turns": 1, "value": 1.0}, log)

    else:  # SUP
        # AOE_HEAL + ATK_UP for the team. _heal respects HEAL_BLOCK natively.
        for tgt in [u for u in allies if not u.dead]:
            amount = max(1, int(tgt.max_hp * 0.25))
            _heal(actor, tgt, amount, log, source="HAIL_MARY")
            _apply_effect(tgt, {"kind": "ATK_UP", "turns": 3, "value": 0.20}, log)


def simulate(team_a: list[CombatUnit], team_b: list[CombatUnit], rng: random.Random) -> CombatResult:
    log: list[dict] = []
    max_ticks = 400
    ticks = 0

    _apply_team_synergy(team_a, log)
    _apply_team_synergy(team_b, log)

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
            # Hail-mary check: if the actor's HP just crossed the 5% threshold
            # (or a DoT tick took them there), fire the desperation move once.
            # Order matters — runs after _tick_statuses so a POISON tick that
            # pushes the unit into the threshold still triggers the hail-mary.
            _maybe_hail_mary(
                actor,
                allies=team_a if actor.side == "A" else team_b,
                enemies=team_b if actor.side == "A" else team_a,
                rng=rng,
                log=log,
            )
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
    faction: Faction | None = None,
    variance_pct: dict[str, float] | None = None,
    attack_kind: str = "melee",
) -> CombatUnit:
    hp = scale_stat(base_hp, level, stars)
    atk = scale_stat(base_atk, level, stars)
    df = scale_stat(base_def, level, stars)
    spd = base_spd  # SPD isn't scaled by level in this MVP.
    # Phase 2.2 — duplicate-summon variance applied before gear so a +10% atk
    # roll feels equally meaningful at level 1 and level 60. Empty / None
    # means first copy (no variance).
    if variance_pct:
        hp = int(round(hp * (1.0 + float(variance_pct.get("hp", 0.0) or 0.0))))
        atk = int(round(atk * (1.0 + float(variance_pct.get("atk", 0.0) or 0.0))))
        df = int(round(df * (1.0 + float(variance_pct.get("def", 0.0) or 0.0))))
        spd = int(round(spd * (1.0 + float(variance_pct.get("spd", 0.0) or 0.0))))
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
        faction=faction,
        attack_kind=attack_kind if attack_kind in ("melee", "ranged") else "melee",
    )


def unit_power(u: CombatUnit) -> int:
    return power_rating(u.max_hp, u.atk, u.def_, u.spd)
