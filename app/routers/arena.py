import json
import random
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.arena_constants import ARENA_REWARDS, ARENA_REWARD_JITTER
from app.arena_payout import reset_weekly_counter_if_stale
from app.combat import power_rating, scale_stat, simulate, trim_combat_log
from app.daily import on_arena_attack
from app.economy import consume_arena_ticket, seconds_until_next_ticket
from app.event_state import QUEST_KINDS_ARENA, on_activity as event_on_activity
from app.db import get_db
from app.deps import enforce_arena_rate_limit, get_current_account
from app.gear_logic import gear_bonus_for
from app.models import (
    Account,
    ArenaMatch,
    BattleOutcome,
    DefenseTeam,
    HeroInstance,
    utcnow,
)
from app.routers.battles import _unit_from_instance
from app.routers.heroes import instance_out
from app.schemas import (
    ArenaAttackIn,
    ArenaLeaderboardEntry,
    ArenaMatchOut,
    ArenaOpponentOut,
    BattleParticipant,
    DefenseSetIn,
    HeroInstanceOut,
)

router = APIRouter(prefix="/arena", tags=["arena"])


RATING_WIN = 25
# Matchmaking widens the rating window progressively when the tight pool is sparse.
# Last entry None means "no filter — everyone".
_MATCHMAKING_WINDOWS: tuple[int | None, ...] = (200, 400, 800, None)
# Minutes after attacking a defender where they're excluded from /opponents for
# the attacker. Prevents the "fight the same three faces back-to-back" problem.
# If the exclusion would empty the pool, we fall back to no-exclusion.
ARENA_RECENT_ATTACK_COOLDOWN_MINUTES = 30
RATING_LOSS = -15
MIN_RATING = 0
OPPONENT_SAMPLE_SIZE = 3


def _compute_team_power(heroes: list[HeroInstance]) -> int:
    total = 0
    for h in heroes:
        t = h.template
        hp = scale_stat(t.base_hp, h.level)
        atk = scale_stat(t.base_atk, h.level)
        df = scale_stat(t.base_def, h.level)
        spd = t.base_spd
        bonus = gear_bonus_for(h)
        total += power_rating(hp + bonus["hp"], atk + bonus["atk"], df + bonus["def"], spd + bonus["spd"])
    return total


def _load_heroes(db: Session, account: Account, ids: list[int]) -> list[HeroInstance]:
    heroes: list[HeroInstance] = []
    for hid in ids:
        h = db.get(HeroInstance, hid)
        if h is None or h.account_id != account.id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"hero {hid} not owned")
        heroes.append(h)
    return heroes


@router.put("/defense", response_model=dict)
def set_defense(
    body: DefenseSetIn,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    heroes = _load_heroes(db, account, body.team)
    power = _compute_team_power(heroes)
    dt = db.get(DefenseTeam, account.id)
    now = utcnow()
    if dt is None:
        dt = DefenseTeam(
            account_id=account.id,
            hero_ids_json=json.dumps(body.team),
            power=power,
            updated_at=now,
        )
        db.add(dt)
    else:
        dt.hero_ids_json = json.dumps(body.team)
        dt.power = power
        dt.updated_at = now
    db.commit()
    return {"team": body.team, "power": power}


@router.get("/defense", response_model=dict)
def get_defense(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    dt = db.get(DefenseTeam, account.id)
    if dt is None:
        return {"team": [], "power": 0}
    try:
        team = json.loads(dt.hero_ids_json)
    except json.JSONDecodeError:
        team = []
    return {"team": team, "power": dt.power}


@router.get("/opponents", response_model=list[ArenaOpponentOut])
def list_opponents(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> list[ArenaOpponentOut]:
    """Rating-proximity matchmaking: start with defenders within ±200 rating of the
    caller and widen the window until we have at least OPPONENT_SAMPLE_SIZE candidates.
    Banned accounts are excluded, as are defenders the caller fought in the last
    ARENA_RECENT_ATTACK_COOLDOWN_MINUTES. Final list is shuffled within the
    selected window so consecutive calls don't always return the same three faces.
    """
    rng = random.Random()
    my_rating = account.arena_rating

    # Who've we attacked recently? Exclude them from the pool if possible.
    from datetime import timedelta as _td
    recent_cutoff = utcnow() - _td(minutes=ARENA_RECENT_ATTACK_COOLDOWN_MINUTES)
    recent_ids = set(
        db.scalars(
            select(ArenaMatch.defender_id)
            .where(
                ArenaMatch.attacker_id == account.id,
                ArenaMatch.created_at >= recent_cutoff,
            )
        )
    )

    # Soft same-alignment preference: RESISTANCE/CORP_GREED players prefer
    # opponents of the same faction (lore flavour). EXILE players skip this.
    # We try the aligned pool first; if too thin, fall back to any faction.
    my_faction = str(account.faction or "EXILE")
    same_faction_filter = my_faction not in ("EXILE", "")

    def _build_stmt(window: int | None, faction_filter: bool):
        stmt = (
            select(DefenseTeam.account_id)
            .join(Account, Account.id == DefenseTeam.account_id)
            .where(
                DefenseTeam.account_id != account.id,
                Account.is_banned.is_(False),
            )
        )
        if window is not None:
            stmt = stmt.where(
                Account.arena_rating >= my_rating - window,
                Account.arena_rating <= my_rating + window,
            )
        if faction_filter:
            stmt = stmt.where(Account.faction == my_faction)
        return stmt

    chosen: list[int] = []
    for window in _MATCHMAKING_WINDOWS:
        for use_faction in ([True, False] if same_faction_filter else [False]):
            base_stmt = _build_stmt(window, use_faction)
            # First try with the recent-exclusion. If that empties the pool inside
            # this window, drop the exclusion (would rather show a repeat opponent
            # than nothing at all when the server is small).
            pool_with_exclusion = [
                aid for aid in db.scalars(base_stmt) if aid not in recent_ids
            ] if recent_ids else list(db.scalars(base_stmt))
            if len(pool_with_exclusion) >= OPPONENT_SAMPLE_SIZE or (
                window is None and not use_faction and pool_with_exclusion
            ):
                rng.shuffle(pool_with_exclusion)
                chosen = pool_with_exclusion[:OPPONENT_SAMPLE_SIZE]
                break
        if chosen:
            break

    # Dead-last fallback: ignore the recent-exclusion across all windows.
    if not chosen:
        for window in _MATCHMAKING_WINDOWS:
            pool_ids = list(db.scalars(_build_stmt(window, False)))
            if len(pool_ids) >= OPPONENT_SAMPLE_SIZE or window is None:
                rng.shuffle(pool_ids)
                chosen = pool_ids[:OPPONENT_SAMPLE_SIZE]
                break

    if not chosen:
        return []
    # Safety: dedup in case the query somehow returned repeats.
    chosen = list(dict.fromkeys(chosen))

    out: list[ArenaOpponentOut] = []
    for acct_id in chosen:
        opp = db.get(Account, acct_id)
        dt = db.get(DefenseTeam, acct_id)
        if opp is None or dt is None:
            continue
        try:
            ids = json.loads(dt.hero_ids_json)
        except json.JSONDecodeError:
            continue
        hero_out: list[HeroInstanceOut] = []
        for hid in ids:
            h = db.get(HeroInstance, hid)
            if h is None or h.account_id != acct_id:
                continue
            hero_out.append(instance_out(h))
        if not hero_out:
            continue
        out.append(ArenaOpponentOut(
            account_id=opp.id,
            name=opp.email.split("@")[0],
            arena_rating=opp.arena_rating,
            team_power=dt.power,
            team=hero_out,
        ))
    return out


@router.post("/attack", response_model=ArenaMatchOut, status_code=status.HTTP_201_CREATED)
def attack(
    body: ArenaAttackIn,
    account: Annotated[Account, Depends(enforce_arena_rate_limit)],
    db: Annotated[Session, Depends(get_db)],
) -> ArenaMatchOut:
    if body.defender_account_id == account.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot attack self")
    defender = db.get(Account, body.defender_account_id)
    if defender is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "defender not found")
    dt = db.get(DefenseTeam, defender.id)
    if dt is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "defender has no defense team set")

    # Ticket gate — game economy resource (separate from anti-spam rate limit).
    if not consume_arena_ticket(account):
        retry_after = max(1, seconds_until_next_ticket(account))
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"out of arena tickets — next in {retry_after}s",
            headers={"Retry-After": str(retry_after)},
        )

    attackers = _load_heroes(db, account, body.team)
    try:
        def_ids = json.loads(dt.hero_ids_json)
    except json.JSONDecodeError:
        def_ids = []
    defenders: list[HeroInstance] = []
    for hid in def_ids:
        h = db.get(HeroInstance, hid)
        if h is None or h.account_id != defender.id:
            continue
        defenders.append(h)
    if not defenders:
        raise HTTPException(status.HTTP_409_CONFLICT, "defender team is empty or invalid")

    team_a = [_unit_from_instance(h, "A", i) for i, h in enumerate(attackers)]
    team_b = [_unit_from_instance(h, "B", i) for i, h in enumerate(defenders)]

    # Snapshot participants before simulate mutates HP — same shape as Battle so
    # the replay viewer works unchanged for arena matches.
    participants = [
        {"uid": u.uid, "side": "A", "name": u.name, "role": str(u.role),
         "level": u.level, "max_hp": u.max_hp,
         "template_code": attackers[i].template.code,
         "rarity": str(attackers[i].template.rarity),
         "faction": str(attackers[i].template.faction)}
        for i, u in enumerate(team_a)
    ]
    participants.extend(
        {"uid": u.uid, "side": "B", "name": u.name, "role": str(u.role),
         "level": u.level, "max_hp": u.max_hp,
         "template_code": defenders[i].template.code,
         "rarity": str(defenders[i].template.rarity),
         "faction": str(defenders[i].template.faction)}
        for i, u in enumerate(team_b)
    )

    rng = random.Random()
    result = simulate(team_a, team_b, rng)

    if result.outcome == BattleOutcome.WIN:
        delta = RATING_WIN
        account.arena_wins += 1
        defender.arena_losses += 1
    elif result.outcome == BattleOutcome.LOSS:
        delta = RATING_LOSS
        account.arena_losses += 1
        defender.arena_wins += 1
    else:
        delta = 0

    account.arena_rating = max(MIN_RATING, account.arena_rating + delta)
    defender.arena_rating = max(MIN_RATING, defender.arena_rating - delta)

    # Drip rewards — outcome-driven, ±20% jitter on coins only.
    outcome_key = (
        "win" if result.outcome == BattleOutcome.WIN
        else "loss" if result.outcome == BattleOutcome.LOSS
        else "draw"
    )
    reward_set = ARENA_REWARDS[outcome_key]
    jitter_mult = 1.0 + rng.uniform(-ARENA_REWARD_JITTER, ARENA_REWARD_JITTER)
    coins = max(1, int(round(reward_set["coins"] * jitter_mult)))
    shards = reward_set["shards"]
    gems = reward_set["gems"]
    account.coins = (account.coins or 0) + coins
    account.shards = (account.shards or 0) + shards
    account.gems = (account.gems or 0) + gems
    rewards_out = {"coins": coins, "shards": shards, "gems": gems}

    # Weekly counter — increment only on wins, after stale-key reset so the
    # increment lands on the current week's bucket.
    if result.outcome == BattleOutcome.WIN:
        reset_weekly_counter_if_stale(account)
        account.arena_weekly_wins = (account.arena_weekly_wins or 0) + 1

    on_arena_attack(db, account)
    event_on_activity(db, account, "arena_attack", quest_kinds=QUEST_KINDS_ARENA)

    match = ArenaMatch(
        attacker_id=account.id,
        defender_id=defender.id,
        outcome=result.outcome,
        rating_delta=delta,
        attacker_rating_after=account.arena_rating,
        defender_rating_after=defender.arena_rating,
        log_json=json.dumps(trim_combat_log(result.log)),
        participants_json=json.dumps(participants),
    )
    db.add(match)
    if result.outcome == BattleOutcome.WIN:
        from app.quest_service import record_event as _rq
        _rq(db, account, "ARENA_WIN")
    db.commit()
    db.refresh(match)

    from app.analytics import track as _track
    _track("arena_attack", account.id, {
        "outcome": str(result.outcome),
        "won": result.outcome == BattleOutcome.WIN,
        "rating_delta": delta,
        "rating_after": account.arena_rating,
    })

    return ArenaMatchOut(
        id=match.id,
        attacker_id=match.attacker_id,
        defender_id=match.defender_id,
        outcome=result.outcome,
        rating_delta=delta,
        attacker_rating_after=account.arena_rating,
        defender_rating_after=defender.arena_rating,
        log=result.log,
        participants=[BattleParticipant(**p) for p in participants],
        created_at=match.created_at,
        rewards=rewards_out,
    )


@router.get("/matches/{match_id}", response_model=ArenaMatchOut)
def get_match(
    match_id: int,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> ArenaMatchOut:
    """Read-only fetch of a stored arena match. Viewable by attacker or defender only —
    matches you weren't in return 404 (don't leak existence across accounts)."""
    m = db.get(ArenaMatch, match_id)
    if m is None or account.id not in (m.attacker_id, m.defender_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "arena match not found")
    try:
        log = json.loads(m.log_json or "[]")
    except json.JSONDecodeError:
        log = []
    try:
        participants_raw = json.loads(m.participants_json or "[]")
    except json.JSONDecodeError:
        participants_raw = []
    return ArenaMatchOut(
        id=m.id,
        attacker_id=m.attacker_id,
        defender_id=m.defender_id,
        outcome=m.outcome,
        rating_delta=m.rating_delta,
        attacker_rating_after=m.attacker_rating_after,
        defender_rating_after=m.defender_rating_after,
        log=log,
        participants=[BattleParticipant(**p) for p in participants_raw if isinstance(p, dict)],
        created_at=m.created_at,
    )


@router.get("/leaderboard", response_model=list[ArenaLeaderboardEntry])
def leaderboard(db: Annotated[Session, Depends(get_db)]) -> list[ArenaLeaderboardEntry]:
    rows = db.execute(
        select(Account.id, Account.email, Account.arena_rating, Account.arena_wins, Account.arena_losses)
        .order_by(desc(Account.arena_rating), Account.id)
        .limit(20)
    )
    return [
        ArenaLeaderboardEntry(
            account_id=r[0], email=r[1], arena_rating=r[2], arena_wins=r[3], arena_losses=r[4]
        )
        for r in rows
    ]
