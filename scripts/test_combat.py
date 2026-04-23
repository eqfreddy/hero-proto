"""Deterministic combat unit test — no server required.

Seeds a fixed RNG, runs a known matchup, asserts outcome. The log hash is
printed but not asserted — content will drift when balance changes.
"""

from __future__ import annotations

import random
import sys

from app.combat import build_unit, simulate
from app.models import BattleOutcome, Role


def make_gremlin(uid: str, side: str, level: int = 1):
    return build_unit(
        uid=uid, side=side,
        name="Ticket Gremlin", role=Role.ATK, level=level,
        base_hp=800, base_atk=90, base_def=60, base_spd=95,
        basic_mult=1.0, special=None, special_cooldown=0,
    )


def make_sysadmin(uid: str, side: str, level: int = 3):
    return build_unit(
        uid=uid, side=side,
        name="The Sysadmin", role=Role.DEF, level=level,
        base_hp=1800, base_atk=85, base_def=150, base_spd=85,
        basic_mult=1.0,
        special={"name": "sudo !!", "type": "SHIELD", "target": "self"},
        special_cooldown=4,
    )


def make_keymaster(uid: str, side: str, level: int = 5):
    return build_unit(
        uid=uid, side=side,
        name="Keymaster (Gary)", role=Role.ATK, level=level,
        base_hp=1250, base_atk=150, base_def=80, base_spd=105,
        basic_mult=1.1,
        special={
            "name": "I AM the Keymaster", "type": "DAMAGE",
            "mult": 2.4, "target": "enemy_lowest_hp",
        },
        special_cooldown=4,
    )


def main() -> int:
    rng = random.Random(1312)

    team_a = [
        make_sysadmin("a0", "A"),
        make_keymaster("a1", "A"),
    ]
    team_b = [make_gremlin(f"b{i}", "B") for i in range(3)]

    result = simulate(team_a, team_b, rng)
    print(f"outcome={result.outcome} ticks={result.ticks} log_len={len(result.log)} hash={result.log_hash}")

    assert result.outcome == BattleOutcome.WIN, f"expected WIN, got {result.outcome}"
    assert result.survivors_a, "team A wiped — balance regression"
    assert not result.survivors_b, f"team B somehow survived: {result.survivors_b}"

    # At least one SPECIAL should have fired (Keymaster cooldown starts at 0).
    assert any(e.get("type") == "SPECIAL" for e in result.log), "no SPECIAL events in log"
    assert any(e.get("type") == "BASIC" or e.get("via") == "BASIC" for e in result.log), "no basic attacks"
    assert result.log[-1]["type"] == "END"

    print("TEST COMBAT OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
