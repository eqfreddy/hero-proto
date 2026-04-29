"""In-memory session store for interactive (turn-by-turn) combat.

Each session drives a simulate_interactive() generator for one stage fight or
one raid attack. The session lives for SESSION_TTL seconds then expires.

Single-worker only. If this ever scales to multiple processes, replace
_sessions with a Redis hash.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any

from app.combat import (
    BattleOutcome,
    CombatResult,
    CombatUnit,
    simulate_interactive,
)

SESSION_TTL = 30 * 60  # 30 minutes


@dataclass
class InteractiveSession:
    session_id: str
    account_id: int
    kind: str  # "stage" | "raid"
    context_id: int  # stage_id or raid_id

    # Combat state — generator drives team_a/wave_teams_b in place
    team_a: list[CombatUnit]
    wave_teams_b: list[list[CombatUnit]]  # one sub-list per wave
    wave_idx: int
    rng: Any  # random.Random

    # Shared log — generator appends directly; session tracks cursor
    combined_log: list[dict]
    log_cursor: int  # events already delivered to client

    # Running generator for the current wave
    gen: Any  # Generator[dict, str | None, CombatResult]
    wave_result: CombatResult | None  # set when a wave ends

    # State machine
    pending: dict | None  # last PLAYER_TURN yield dict, or None
    turn_number: int
    status: str  # "WAITING" | "DONE"

    # Context for route-layer finalization
    hero_ids: list[int]
    target_priority: str
    participants: list[dict]

    # Raid-specific: initial boss HP for damage calculation
    boss_start_hp: int = 0

    # Final outcome — set when status == "DONE"
    outcome: BattleOutcome | None = None

    created_at: float = field(default_factory=time.time)


# Session store — keyed by session_id
_sessions: dict[str, InteractiveSession] = {}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cleanup() -> None:
    now = time.time()
    expired = [sid for sid, s in _sessions.items() if now - s.created_at > SESSION_TTL]
    for sid in expired:
        del _sessions[sid]


def _unit_snapshot(u: CombatUnit) -> dict:
    return {
        "uid": u.uid,
        "name": u.name,
        "side": u.side,
        "role": str(u.role),
        "hp": u.hp,
        "max_hp": u.max_hp,
        "dead": u.dead,
        "shielded": u.shielded,
        "limit_gauge": u.limit_gauge,
        "limit_gauge_max": u.limit_gauge_max,
    }


def _advance(session: InteractiveSession, target_uid: str | None = None) -> None:
    """Drive the generator one step.

    If target_uid is given, resume from the current PLAYER_TURN yield via
    gen.send(). Otherwise prime the generator with next().

    On StopIteration (wave over): transitions to the next wave or marks DONE.
    Mutates session in place.
    """
    gen = session.gen
    try:
        pause_event: dict = gen.send(target_uid) if target_uid is not None else next(gen)
        # Generator paused — waiting for player's target choice
        session.pending = pause_event
        session.turn_number = pause_event["turn_number"]
        session.status = "WAITING"
    except StopIteration as exc:
        result: CombatResult = exc.value
        session.wave_result = result

        next_wave = session.wave_idx + 1
        if result.outcome == BattleOutcome.WIN and next_wave < len(session.wave_teams_b):
            # More waves — reset team_a and start next wave generator
            for u in session.team_a:
                u.statuses.clear()
                u.turn_meter = 0.0
                u.special_cooldown_left = 0
                u.shielded = False
            session.wave_idx = next_wave
            session.combined_log.append({
                "type": "WAVE_START",
                "wave": next_wave + 1,
                "enemies": [u.uid for u in session.wave_teams_b[next_wave]],
            })
            session.gen = simulate_interactive(
                session.team_a,
                session.wave_teams_b[next_wave],
                session.rng,
                session.combined_log,
                session.target_priority,
            )
            session.pending = None
            _advance(session)  # recurse into new wave (depth = wave count, ≤ ~3)
        else:
            session.status = "DONE"
            session.pending = None
            session.outcome = result.outcome


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_session(session_id: str) -> InteractiveSession | None:
    _cleanup()
    return _sessions.get(session_id)


def create_stage_session(
    *,
    account_id: int,
    stage_id: int,
    hero_ids: list[int],
    team_a: list[CombatUnit],
    wave_teams_b: list[list[CombatUnit]],
    rng: Any,
    participants: list[dict],
    target_priority: str = "default",
) -> InteractiveSession:
    _cleanup()
    sid = str(uuid.uuid4())
    log: list[dict] = []
    log.append({
        "type": "WAVE_START",
        "wave": 1,
        "enemies": [u.uid for u in wave_teams_b[0]],
    })
    gen = simulate_interactive(team_a, wave_teams_b[0], rng, log, target_priority)
    session = InteractiveSession(
        session_id=sid,
        account_id=account_id,
        kind="stage",
        context_id=stage_id,
        team_a=team_a,
        wave_teams_b=wave_teams_b,
        wave_idx=0,
        rng=rng,
        combined_log=log,
        log_cursor=0,
        gen=gen,
        wave_result=None,
        pending=None,
        turn_number=0,
        status="WAITING",
        hero_ids=hero_ids,
        target_priority=target_priority,
        participants=participants,
    )
    _advance(session)  # prime to first PLAYER_TURN
    _sessions[sid] = session
    return session


def create_raid_session(
    *,
    account_id: int,
    raid_id: int,
    hero_ids: list[int],
    team_a: list[CombatUnit],
    boss_unit: CombatUnit,
    rng: Any,
    participants: list[dict],
    target_priority: str = "default",
) -> InteractiveSession:
    _cleanup()
    sid = str(uuid.uuid4())
    log: list[dict] = []
    log.append({"type": "WAVE_START", "wave": 1, "enemies": [boss_unit.uid]})
    gen = simulate_interactive(team_a, [boss_unit], rng, log, target_priority)
    session = InteractiveSession(
        session_id=sid,
        account_id=account_id,
        kind="raid",
        context_id=raid_id,
        team_a=team_a,
        wave_teams_b=[[boss_unit]],
        wave_idx=0,
        rng=rng,
        combined_log=log,
        log_cursor=0,
        gen=gen,
        wave_result=None,
        pending=None,
        turn_number=0,
        status="WAITING",
        hero_ids=hero_ids,
        target_priority=target_priority,
        participants=participants,
        boss_start_hp=boss_unit.hp,
    )
    _advance(session)
    _sessions[sid] = session
    return session


def advance_session(
    session: InteractiveSession,
    *,
    turn_number: int,
    target_uid: str,
) -> None:
    """Validate turn_number, then resume the generator with the player's choice."""
    if session.status == "DONE":
        return
    if turn_number != session.turn_number:
        raise ValueError(
            f"stale turn: expected {session.turn_number}, got {turn_number}"
        )
    _advance(session, target_uid if target_uid else None)


def session_log_delta(session: InteractiveSession) -> list[dict]:
    """Return events added since last call, then advance the cursor."""
    delta = session.combined_log[session.log_cursor:]
    session.log_cursor = len(session.combined_log)
    return delta
