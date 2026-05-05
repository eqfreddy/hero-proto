"""Named gear catalog — story / raid / event reward pieces.

These are LEGENDARY armor with fixed (not RNG-rolled) stats, named flavor,
and a one-line backstory. They drop from milestones, not loot tables, so
players who reach them get something tangible the RNG can't match.

Each chapter of the story script grants one piece of the **Veteran IT Set**
— a 6-piece armor set built across the player's career. Two pieces are
gated behind the level-50 Alignment Fork, so picking RESISTANCE vs
CORP_GREED gives you a different signature glove. Everyone who beats the
endgame ends up with all six.

The set bonus is the same regardless of alignment — the lore differs but
the math doesn't, so neither path is mechanically advantaged.

Stats are in the Legendary band (~upper end of the RNG roll table) but
deliberately not best-in-slot — the named pieces are *guaranteed great*,
the very-top rolls are still rare drops to chase.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models import GearRarity, GearSet, GearSlot


@dataclass(frozen=True)
class NamedGear:
    code: str                 # stable id: matches stats_json key in story_state for grant idempotency
    name: str                 # display name
    flavor: str               # one-line backstory shown on the gear card
    icon: str                 # emoji
    slot: GearSlot
    set_code: GearSet
    stats: dict[str, int]     # fixed flat stats — bypasses gear_logic RNG
    rarity: GearRarity = GearRarity.LEGENDARY


# ── The Veteran IT Set (6 pieces, head to toe) ──────────────────────────────
#
# Three pre-fork chapters grant universal pieces; two are alignment-specific
# at the Chapter 4 fork; LEGS lands at the level-50 alignment-choice moment
# so EVERY player gets it (the moment they pick a side).

NAMED_GEAR: dict[str, NamedGear] = {

    # Chapter 1 — Onboarding closer reward
    "help_desk_headset": NamedGear(
        code="help_desk_headset",
        name="Help Desk Headset",
        flavor="One earcup is louder than the other. The mute button is sticky. It has logged more screams than your therapist.",
        icon="🎧",
        slot=GearSlot.HEAD,
        set_code=GearSet.VITAL,
        stats={"hp": 520, "def": 35, "atk": 18},
    ),

    # Chapter 2 — Middle Management closer reward
    "power_suit_jacket": NamedGear(
        code="power_suit_jacket",
        name="Power-Suit Jacket",
        flavor="Tailored on the company dime. The shoulder pads remember every reorg. The lining is reinforced with old org charts.",
        icon="🧥",
        slot=GearSlot.CHEST,
        set_code=GearSet.DEFENSE,
        stats={"def": 75, "hp": 380, "atk": 22},
    ),

    # Chapter 3 — Executive Floor closer reward
    "all_terrain_loafers": NamedGear(
        code="all_terrain_loafers",
        name="All-Terrain Loafers",
        flavor="Italian leather, German soles. Quiet on carpet, silent on linoleum, devastating in a stand-up.",
        icon="👞",
        slot=GearSlot.FEET,
        set_code=GearSet.SWIFT,
        stats={"spd": 12, "atk": 28, "hp": 240},
    ),

    # Level-50 Alignment Fork reward — every player gets this when they pick a side
    "cargo_pants_of_many_tabs": NamedGear(
        code="cargo_pants_of_many_tabs",
        name="Cargo Pants of Many Tabs",
        flavor="Six pockets. One has a screwdriver. Three have USB drives. One has a granola bar from 2019. The last one is empty and you don't know why.",
        icon="👖",
        slot=GearSlot.LEGS,
        set_code=GearSet.VITAL,
        stats={"hp": 480, "def": 40, "spd": 6},
    ),

    # Chapter 4 RESISTANCE closer reward
    "burner_phone_wristband": NamedGear(
        code="burner_phone_wristband",
        name="Burner Phone Wristband",
        flavor="Replaced every ninety days. The signal handler insists. You're starting to insist back.",
        icon="📡",
        slot=GearSlot.WRIST,
        set_code=GearSet.SWIFT,
        stats={"spd": 14, "atk": 32, "hp": 200},
    ),

    # Chapter 4 CORP_GREED closer reward
    "signing_gauntlets": NamedGear(
        code="signing_gauntlets",
        name="Signing Gauntlets",
        flavor="Hand-stitched from the upholstery of the boardroom chairs you've outlasted. The right one has a custom signet for fast NDAs.",
        icon="🥊",
        slot=GearSlot.HANDS,
        set_code=GearSet.OFFENSE,
        stats={"atk": 78, "def": 30, "hp": 220},
    ),
}


# ── Lookup helpers ──────────────────────────────────────────────────────────

def by_code(code: str) -> NamedGear | None:
    return NAMED_GEAR.get(code)


def all_codes() -> list[str]:
    return list(NAMED_GEAR.keys())


# ── Grant helper ────────────────────────────────────────────────────────────

def grant_named_gear(db, account, code: str) -> bool:
    """Idempotently grant a named piece to `account`. Returns True if the
    piece was newly created, False if the player already has it.

    Equipped status is unchanged — players choose what to wear.
    """
    import json
    from app.models import Gear

    spec = NAMED_GEAR.get(code)
    if spec is None:
        return False

    # Flush any pending grants in this transaction so idempotency holds across
    # multiple grant_named_gear() calls before commit.
    db.flush()

    # Idempotency: check by (account_id, name) pair.
    existing = (
        db.query(Gear)
        .filter(Gear.account_id == account.id, Gear.name == spec.name)
        .first()
    )
    if existing is not None:
        return False

    db.add(Gear(
        account_id=account.id,
        slot=spec.slot,
        rarity=spec.rarity,
        set_code=spec.set_code,
        stats_json=json.dumps(spec.stats, separators=(",", ":")),
        name=spec.name,
        flavor=spec.flavor,
    ))
    return True
