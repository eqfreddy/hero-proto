from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models import (
    BattleOutcome,
    DailyQuestKind,
    DailyQuestStatus,
    Faction,
    GearRarity,
    GearSet,
    GearSlot,
    GuildRole,
    RaidState,
    Rarity,
    Role,
)


class BattleParticipant(BaseModel):
    """Snapshot of a unit in a recorded fight. Shared by BattleOut and ArenaMatchOut
    so the replay viewer handles both the same way.
    """

    uid: str
    side: str  # "A" = player, "B" = enemy
    name: str
    role: str
    level: int
    max_hp: int
    template_code: str = ""  # for portrait lookup; empty on legacy rows before this field landed
    # Cosmetic metadata for the replay viewer (rarity frame + faction badge).
    # Default empty strings keep legacy Battle.participants_json rows deserializable.
    rarity: str = ""
    faction: str = ""


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    # Long-lived rotation credential. Emitted by /auth/register, /auth/login,
    # /auth/refresh. Clients hang on to this; swap it for a fresh access token
    # via POST /auth/refresh when the old access token expires.
    refresh_token: str | None = None


class MeOut(BaseModel):
    id: int
    email: EmailStr
    gems: int
    coins: int
    shards: int
    access_cards: int
    # Free x1 summon tokens (tutorial reward, starter pack, LiveOps).
    free_summon_credits: int = 0
    energy: int
    energy_cap: int
    pulls_since_epic: int
    stages_cleared: list[str]
    # First-session progression flags — drives the "Next step" CTA card
    # on the dashboard. Clients use these to know which CTA to show.
    tutorial_cleared: bool = False
    has_summoned: bool = False
    has_battled: bool = False


class HeroTemplateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    rarity: Rarity
    faction: Faction
    role: Role
    base_hp: int
    base_atk: int
    base_def: int
    base_spd: int
    basic_mult: float
    special_cooldown: int
    # Decoded special payload (can be None for basic-only heroes).
    special: dict | None = None


class HeroInstanceOut(BaseModel):
    id: int
    template: HeroTemplateOut
    level: int
    level_cap: int
    xp: int
    special_level: int
    stars: int
    # Computed effective stats at current level (including equipped gear bonuses).
    hp: int
    atk: int
    def_: int = Field(alias="def")
    spd: int
    power: int
    equipped_gear_ids: list[int] = []
    active_sets: dict[str, int] = {}

    model_config = ConfigDict(populate_by_name=True)


class GearOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    slot: GearSlot
    rarity: GearRarity
    set: GearSet
    stats: dict[str, int]
    equipped_on: int | None


class AscendIn(BaseModel):
    fodder_ids: list[int] = Field(min_length=1, max_length=5)


class SweepIn(BaseModel):
    team: list[int] = Field(min_length=1, max_length=3)
    count: int = Field(ge=1, le=10)


class SweepOut(BaseModel):
    count: int
    wins: int
    losses: int
    energy_spent: int
    rewards_total: dict[str, int]
    gear_ids: list[int]
    completed_daily_quest_ids: list[int]


class EquipIn(BaseModel):
    hero_instance_id: int


class SkillUpIn(BaseModel):
    fodder_ids: list[int] = Field(min_length=1, max_length=4)


class DefenseSetIn(BaseModel):
    team: list[int] = Field(min_length=1, max_length=3)


class ArenaOpponentOut(BaseModel):
    account_id: int
    name: str
    arena_rating: int
    team_power: int
    team: list[HeroInstanceOut]


class ArenaAttackIn(BaseModel):
    defender_account_id: int
    team: list[int] = Field(min_length=1, max_length=3)


class ArenaMatchOut(BaseModel):
    id: int
    attacker_id: int
    defender_id: int
    outcome: BattleOutcome
    rating_delta: int
    attacker_rating_after: int
    defender_rating_after: int
    log: list[dict]
    # Same shape as BattleOut.participants so the Phaser replay works unchanged.
    participants: list[BattleParticipant] = []
    created_at: datetime


class ArenaLeaderboardEntry(BaseModel):
    account_id: int
    email: str
    arena_rating: int
    arena_wins: int
    arena_losses: int


class DailyQuestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    day_key: str
    kind: DailyQuestKind
    status: DailyQuestStatus
    target_key: str
    goal: int
    progress: int
    reward_gems: int
    reward_coins: int
    reward_shards: int


class GuildCreateIn(BaseModel):
    name: str = Field(min_length=3, max_length=32)
    tag: str = Field(min_length=2, max_length=6)
    description: str = Field(default="", max_length=256)


class GuildUpdateIn(BaseModel):
    description: str = Field(max_length=256)


class GuildMemberOut(BaseModel):
    account_id: int
    name: str
    role: GuildRole
    arena_rating: int


class GuildOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    tag: str
    description: str
    member_count: int


class GuildDetailOut(GuildOut):
    members: list[GuildMemberOut]


class GuildApplicationIn(BaseModel):
    message: str = Field(default="", max_length=256)


class GuildApplicationOut(BaseModel):
    id: int
    guild_id: int
    account_id: int
    applicant_name: str
    status: str
    message: str
    created_at: datetime
    reviewed_at: datetime | None
    reviewed_by: int | None


class GuildMessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=512)


class GuildMessageOut(BaseModel):
    id: int
    guild_id: int
    author_id: int | None
    author_name: str
    body: str
    created_at: datetime


class RaidStartIn(BaseModel):
    boss_template_code: str
    boss_level: int = Field(ge=1, le=60, default=20)
    duration_hours: float = Field(gt=0, le=72, default=24.0)
    tier: str = Field(default="T1", pattern="^T[123]$")


class RaidContributor(BaseModel):
    account_id: int
    name: str
    damage_dealt: int


class RaidOut(BaseModel):
    id: int
    guild_id: int
    boss_name: str
    boss_level: int
    max_hp: int
    remaining_hp: int
    state: RaidState
    tier: str = "T1"
    starts_at: datetime
    ends_at: datetime
    contributors: list[RaidContributor] = []


class RaidAttackIn(BaseModel):
    team: list[int] = Field(min_length=1, max_length=3)


class RaidAttackOut(BaseModel):
    damage_dealt: int
    boss_remaining_hp: int
    boss_defeated: bool
    rewards: dict | None = None


class StageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
    order: int
    energy_cost: int
    recommended_power: int
    waves: list[dict]
    coin_reward: int
    first_clear_gems: int
    first_clear_shards: int
    difficulty_tier: str = "NORMAL"
    requires_code: str = ""


class TeamMember(BaseModel):
    hero_instance_id: int


class TeamPresetIn(BaseModel):
    name: str = Field(min_length=1, max_length=32)
    team: list[int] = Field(min_length=1, max_length=3)


class TeamPresetOut(BaseModel):
    id: int
    name: str
    team: list[int]
    created_at: datetime
    updated_at: datetime


class LastTeamOut(BaseModel):
    team: list[int]
    source: str  # "battle" | "arena" | "raid" | "preset:<name>" | "empty"


class BattleIn(BaseModel):
    stage_id: int
    team: list[int] = Field(min_length=1, max_length=3)




class BattleOut(BaseModel):
    id: int
    stage_id: int
    outcome: BattleOutcome
    first_clear: bool
    log: list[dict]
    participants: list[BattleParticipant] = []
    rewards: dict[str, Any]
    created_at: datetime


class SummonOut(BaseModel):
    hero: HeroInstanceOut
    rarity: Rarity
    pulled_epic_pity: bool
    pulls_since_epic_after: int
