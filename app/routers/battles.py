import json
import random
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.combat import CombatUnit, build_unit, simulate, trim_combat_log
from app.daily import on_battle_won, on_hard_stage_clear
from app.db import get_db
from app.deps import enforce_battle_rate_limit, get_current_account
from app.economy import award_rewards, consume_energy, load_cleared, mark_cleared
from app.gear_logic import gear_bonus_for, roll_gear
from app.liveops import gear_drop_bonus, reward_multiplier
from app.models import (
    Account,
    Battle,
    BattleOutcome,
    Gear,
    HeroInstance,
    HeroTemplate,
    Role,
    Stage,
)
from app.schemas import BattleIn, BattleOut, BattleParticipant, SweepIn, SweepOut

router = APIRouter(prefix="/battles", tags=["battles"])


def _unit_from_instance(hero: HeroInstance, side: str, idx: int) -> CombatUnit:
    t = hero.template
    try:
        special = json.loads(t.special_json or "null")
    except json.JSONDecodeError:
        special = None
    return build_unit(
        uid=f"{side}{idx}",
        side=side,
        name=t.name,
        role=Role(t.role) if not isinstance(t.role, Role) else t.role,
        level=hero.level,
        base_hp=t.base_hp, base_atk=t.base_atk,
        base_def=t.base_def, base_spd=t.base_spd,
        basic_mult=t.basic_mult,
        special=special,
        special_cooldown=t.special_cooldown,
        gear_bonus=gear_bonus_for(hero),
        special_level=hero.special_level,
        stars=hero.stars,
    )


def _unit_from_template(t: HeroTemplate, level: int, side: str, idx: int) -> CombatUnit:
    try:
        special = json.loads(t.special_json or "null")
    except json.JSONDecodeError:
        special = None
    return build_unit(
        uid=f"{side}{idx}",
        side=side,
        name=t.name,
        role=Role(t.role) if not isinstance(t.role, Role) else t.role,
        level=level,
        base_hp=t.base_hp, base_atk=t.base_atk,
        base_def=t.base_def, base_spd=t.base_spd,
        basic_mult=t.basic_mult,
        special=special,
        special_cooldown=t.special_cooldown,
    )


@router.post("", response_model=BattleOut, status_code=status.HTTP_201_CREATED)
def fight(
    body: BattleIn,
    account: Annotated[Account, Depends(enforce_battle_rate_limit)],
    db: Annotated[Session, Depends(get_db)],
) -> BattleOut:
    stage = db.get(Stage, body.stage_id)
    if stage is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "stage not found")

    # Higher tiers gate on their NORMAL prerequisite being cleared.
    if stage.requires_code and stage.requires_code not in load_cleared(account):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"locked: clear {stage.requires_code!r} on NORMAL first",
        )

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

    waves = json.loads(stage.waves_json or "[]")
    # Build the persistent player team once; it rolls through all waves keeping HP damage.
    team_a = [_unit_from_instance(h, "A", i) for i, h in enumerate(heroes)]

    rng = random.Random()
    combined_log: list[dict] = []
    outcome = BattleOutcome.WIN

    participants: list[dict] = [
        {"uid": u.uid, "side": "A", "name": u.name, "role": str(u.role),
         "level": u.level, "max_hp": u.max_hp,
         "template_code": heroes[i].template.code,
         "rarity": str(heroes[i].template.rarity),
         "faction": str(heroes[i].template.faction)}
        for i, u in enumerate(team_a)
    ]

    # Index enemy ids across waves so logs can disambiguate.
    enemy_counter = 0
    for wave_idx, wave in enumerate(waves):
        team_b: list[CombatUnit] = []
        for spec in wave.get("enemies", []):
            code = spec["template_code"]
            lvl = int(spec.get("level", 1))
            tmpl = db.scalar(select(HeroTemplate).where(HeroTemplate.code == code))
            if tmpl is None:
                raise HTTPException(
                    status.HTTP_500_INTERNAL_SERVER_ERROR,
                    f"stage references missing template {code!r}",
                )
            enemy_unit = _unit_from_template(tmpl, lvl, "B", enemy_counter)
            team_b.append(enemy_unit)
            participants.append({
                "uid": enemy_unit.uid, "side": "B", "name": enemy_unit.name,
                "role": str(enemy_unit.role), "level": enemy_unit.level,
                "max_hp": enemy_unit.max_hp,
                "template_code": tmpl.code,
                "rarity": str(tmpl.rarity),
                "faction": str(tmpl.faction),
            })
            enemy_counter += 1

        combined_log.append({"type": "WAVE_START", "wave": wave_idx + 1, "enemies": [u.uid for u in team_b]})

        result = simulate(team_a, team_b, rng)
        combined_log.extend(result.log)

        if result.outcome != BattleOutcome.WIN:
            outcome = result.outcome
            break

        # Heroes carry over with whatever HP they have left (and statuses cleared between waves).
        for u in team_a:
            u.statuses.clear()
            u.turn_meter = 0.0
            u.special_cooldown_left = 0
            u.shielded = False

    first_clear = mark_cleared(account, stage.code) if outcome == BattleOutcome.WIN else False
    rewards = award_rewards(
        account=account,
        stage=stage,
        heroes_on_team=heroes,
        won=outcome == BattleOutcome.WIN,
        first_clear=first_clear,
        rng=rng,
        liveops_multiplier=reward_multiplier(db),
    )

    # Tutorial completion reward: grant one free summon token on the first
    # successful clear of the tutorial stage. Gated by tutorial_reward_granted
    # so delete+re-register loops don't re-award it.
    tutorial_reward_payload: dict | None = None
    if (
        outcome == BattleOutcome.WIN
        and stage.code == "tutorial_first_ticket"
        and not account.tutorial_reward_granted
    ):
        account.free_summon_credits = (account.free_summon_credits or 0) + 1
        account.tutorial_reward_granted = True
        tutorial_reward_payload = {"free_summon_credits": 1}

    # Daily quest progression on wins (per-battle + stage-specific + hard-tier).
    completed_dailies: list[int] = []
    if outcome == BattleOutcome.WIN:
        completed_dailies = [q.id for q in on_battle_won(db, account, stage.code)]
        from app.models import StageDifficulty as _SD
        if stage.difficulty_tier == _SD.HARD:
            completed_dailies += [q.id for q in on_hard_stage_clear(db, account)]

    # Gear drop: 35% chance on win, 70% on first clear.
    rewards_extra = rewards.as_json()
    rewards_extra["gear"] = None
    rewards_extra["completed_daily_quest_ids"] = completed_dailies
    if tutorial_reward_payload is not None:
        rewards_extra["tutorial_reward"] = tutorial_reward_payload
    if outcome == BattleOutcome.WIN:
        drop_chance = 0.70 if first_clear else 0.35
        drop_chance += gear_drop_bonus(db)
        if rng.random() < drop_chance:
            slot, rarity, set_code, stats = roll_gear(rng, stage.order)
            gear = Gear(
                account_id=account.id,
                slot=slot,
                rarity=rarity,
                set_code=set_code,
                stats_json=json.dumps(stats),
                hero_instance_id=None,
            )
            db.add(gear)
            db.flush()
            rewards_extra["gear"] = {
                "id": gear.id,
                "slot": str(slot),
                "rarity": str(rarity),
                "set": str(set_code),
                "stats": stats,
            }

    trimmed_log = trim_combat_log(combined_log)
    battle = Battle(
        account_id=account.id,
        stage_id=stage.id,
        team_json=json.dumps([h.id for h in heroes]),
        outcome=outcome,
        log_json=json.dumps(trimmed_log),
        participants_json=json.dumps(participants),
        rewards_json=json.dumps(rewards_extra),
        first_clear=1 if rewards.first_clear else 0,
    )
    db.add(battle)
    db.commit()
    db.refresh(battle)

    return BattleOut(
        id=battle.id,
        stage_id=stage.id,
        outcome=outcome,
        first_clear=rewards.first_clear,
        log=combined_log,
        participants=[BattleParticipant(**p) for p in participants],
        rewards=rewards_extra,
        created_at=battle.created_at,
    )


@router.get("/{battle_id}", response_model=BattleOut)
def get_battle(
    battle_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> BattleOut:
    b = db.get(Battle, battle_id)
    if b is None or b.account_id != account.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "battle not found")
    try:
        log = json.loads(b.log_json or "[]")
    except json.JSONDecodeError:
        log = []
    try:
        participants = json.loads(b.participants_json or "[]")
    except json.JSONDecodeError:
        participants = []
    try:
        rewards = json.loads(b.rewards_json or "{}")
    except json.JSONDecodeError:
        rewards = {}
    return BattleOut(
        id=b.id,
        stage_id=b.stage_id,
        outcome=b.outcome,
        first_clear=bool(b.first_clear),
        log=log,
        participants=[BattleParticipant(**p) for p in participants if isinstance(p, dict)],
        rewards=rewards,
        created_at=b.created_at,
    )


@router.post("/sweep/{stage_id}", response_model=SweepOut, status_code=status.HTTP_201_CREATED)
def sweep(
    stage_id: int,
    body: SweepIn,
    account: Annotated[Account, Depends(enforce_battle_rate_limit)],
    db: Annotated[Session, Depends(get_db)],
) -> SweepOut:
    stage = db.get(Stage, stage_id)
    if stage is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "stage not found")
    if stage.code not in load_cleared(account):
        raise HTTPException(status.HTTP_409_CONFLICT, "stage not yet cleared — win it the slow way first")
    total_energy = stage.energy_cost * body.count
    if not consume_energy(account, total_energy):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"not enough energy (need {total_energy})",
        )

    heroes = []
    for hid in body.team:
        h = db.get(HeroInstance, hid)
        if h is None or h.account_id != account.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"hero {hid} not owned")
        heroes.append(h)

    waves = json.loads(stage.waves_json or "[]")
    rng = random.Random()
    wins = losses = 0
    totals = {"coins": 0, "gems": 0, "shards": 0, "xp": 0}
    gear_ids: list[int] = []
    daily_ids: set[int] = set()

    for _ in range(body.count):
        team_a = [_unit_from_instance(h, "A", i) for i, h in enumerate(heroes)]
        outcome = BattleOutcome.WIN
        enemy_counter = 0
        for wave in waves:
            team_b: list[CombatUnit] = []
            for spec in wave.get("enemies", []):
                tmpl = db.scalar(select(HeroTemplate).where(HeroTemplate.code == spec["template_code"]))
                if tmpl is None:
                    continue
                team_b.append(_unit_from_template(tmpl, int(spec.get("level", 1)), "B", enemy_counter))
                enemy_counter += 1
            result = simulate(team_a, team_b, rng)
            if result.outcome != BattleOutcome.WIN:
                outcome = result.outcome
                break
            for u in team_a:
                u.statuses.clear()
                u.turn_meter = 0.0
                u.special_cooldown_left = 0
                u.shielded = False

        if outcome == BattleOutcome.WIN:
            wins += 1
            rewards = award_rewards(
                account, stage, heroes,
                won=True, first_clear=False, rng=rng,
                liveops_multiplier=reward_multiplier(db),
            )
            totals["coins"] += rewards.coins
            totals["gems"] += rewards.gems
            totals["shards"] += rewards.shards
            totals["xp"] += rewards.xp_per_hero
            for qid in (q.id for q in on_battle_won(db, account, stage.code)):
                daily_ids.add(qid)
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
        else:
            losses += 1
            rewards = award_rewards(account, stage, heroes, won=False, first_clear=False, rng=rng, liveops_multiplier=1.0)
            totals["coins"] += rewards.coins

    db.commit()
    return SweepOut(
        count=body.count,
        wins=wins,
        losses=losses,
        energy_spent=total_energy,
        rewards_total=totals,
        gear_ids=gear_ids,
        completed_daily_quest_ids=sorted(daily_ids),
    )


@router.get("/{battle_id}", response_model=BattleOut)
def get_battle(
    battle_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> BattleOut:
    b = db.get(Battle, battle_id)
    if b is None or b.account_id != account.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "battle not found")
    try:
        log = json.loads(b.log_json)
    except json.JSONDecodeError:
        log = []
    try:
        rewards = json.loads(b.rewards_json)
    except json.JSONDecodeError:
        rewards = {}
    return BattleOut(
        id=b.id,
        stage_id=b.stage_id,
        outcome=b.outcome,
        first_clear=bool(b.first_clear),
        log=log,
        rewards=rewards,
        created_at=b.created_at,
    )
