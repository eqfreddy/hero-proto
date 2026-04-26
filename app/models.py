from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Rarity(StrEnum):
    COMMON = "COMMON"
    UNCOMMON = "UNCOMMON"
    RARE = "RARE"
    EPIC = "EPIC"
    LEGENDARY = "LEGENDARY"
    # MYTH is event-only: never in the standard gacha pool, seeded only for
    # special banners (holidays, anniversaries, LiveOps windows). Phase 2
    # surfaces this as a separate rarity tab in the roster; Phase 1 just
    # seeds the data model and one pilot hero (TBFAM) so the tier is real.
    MYTH = "MYTH"


RARITY_ORDER: dict[str, int] = {r: i for i, r in enumerate(Rarity)}


class Faction(StrEnum):
    HELPDESK = "HELPDESK"
    DEVOPS = "DEVOPS"
    EXECUTIVE = "EXECUTIVE"
    ROGUE_IT = "ROGUE_IT"
    LEGACY = "LEGACY"


class Role(StrEnum):
    ATK = "ATK"
    DEF = "DEF"
    SUP = "SUP"


class StatusEffectKind(StrEnum):
    ATK_UP = "ATK_UP"
    DEF_DOWN = "DEF_DOWN"
    POISON = "POISON"
    STUN = "STUN"
    SHIELD = "SHIELD"  # absorbs next hit
    # Skip turn like STUN, but breaks the moment the unit takes damage. Lighter
    # CC than STUN — useful as a follow-up enabler that punishes pile-on play.
    FREEZE = "FREEZE"
    # Stat-independent damage tick at end of actor's turn. Same cadence as
    # POISON; semantics only differ by source flavor + cleanse rules.
    BURN = "BURN"
    # Suppresses inbound healing while active (HEAL specials, lifesteal,
    # CLEANSE-attached heal, REVIVE). Cracks DEF/SUP comp's sustain.
    HEAL_BLOCK = "HEAL_BLOCK"
    # Bounce a fraction of basic/special damage back to the attacker. Reflected
    # damage cannot itself trigger reflect (no recursive ping-pong).
    REFLECT = "REFLECT"


class BattleOutcome(StrEnum):
    WIN = "WIN"
    LOSS = "LOSS"
    DRAW = "DRAW"


class GearSlot(StrEnum):
    WEAPON = "WEAPON"
    HELMET = "HELMET"
    ARMOR = "ARMOR"
    BOOTS = "BOOTS"
    RING = "RING"
    AMULET = "AMULET"


class GearRarity(StrEnum):
    COMMON = "COMMON"
    RARE = "RARE"
    EPIC = "EPIC"
    LEGENDARY = "LEGENDARY"


class GearSet(StrEnum):
    VITAL = "VITAL"          # 2pc: +15% HP
    OFFENSE = "OFFENSE"      # 2pc: +15% ATK
    DEFENSE = "DEFENSE"      # 2pc: +15% DEF
    SWIFT = "SWIFT"          # 2pc: +15% SPD
    VIOLENT = "VIOLENT"      # 4pc: 20% chance of extra turn after acting
    LIFESTEAL = "LIFESTEAL"  # 4pc: heal 30% of damage dealt


class DailyQuestKind(StrEnum):
    WIN_BATTLES = "WIN_BATTLES"          # progress per battle WIN
    SUMMON_HEROES = "SUMMON_HEROES"      # progress per pull
    ARENA_ATTACKS = "ARENA_ATTACKS"      # progress per arena attack regardless of outcome
    CLEAR_STAGE_X = "CLEAR_STAGE_X"      # progress when clearing a specific stage code
    CLEAR_HARD_STAGE = "CLEAR_HARD_STAGE"  # progress per clear of any HARD-tier stage
    RAID_DAMAGE = "RAID_DAMAGE"          # progress per point of damage dealt in raids
    SPEND_GEMS = "SPEND_GEMS"            # progress per gem spent (summons, shop, etc.)


class DailyQuestStatus(StrEnum):
    ACTIVE = "ACTIVE"
    COMPLETE = "COMPLETE"
    CLAIMED = "CLAIMED"


class GuildRole(StrEnum):
    LEADER = "LEADER"
    OFFICER = "OFFICER"
    MEMBER = "MEMBER"


class GuildApplicationStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"


class LiveOpsKind(StrEnum):
    DOUBLE_REWARDS = "DOUBLE_REWARDS"      # multiplies coins/gems/shards/xp on wins
    BONUS_GEAR_DROPS = "BONUS_GEAR_DROPS"  # raises drop chance


class ShopProductKind(StrEnum):
    GEM_PACK = "GEM_PACK"
    SHARD_PACK = "SHARD_PACK"
    ACCESS_CARD_PACK = "ACCESS_CARD_PACK"
    STARTER_BUNDLE = "STARTER_BUNDLE"
    WEEKLY_BUNDLE = "WEEKLY_BUNDLE"
    SEASONAL_BUNDLE = "SEASONAL_BUNDLE"


class PurchaseState(StrEnum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    REFUNDED = "REFUNDED"
    FAILED = "FAILED"


class LedgerDirection(StrEnum):
    GRANT = "GRANT"       # currency/items given to player on purchase
    REFUND = "REFUND"     # clawback on chargeback/refund


class RaidState(StrEnum):
    ACTIVE = "ACTIVE"
    DEFEATED = "DEFEATED"
    EXPIRED = "EXPIRED"


class RaidTier(StrEnum):
    T1 = "T1"
    T2 = "T2"
    T3 = "T3"


class StageDifficulty(StrEnum):
    NORMAL = "NORMAL"
    HARD = "HARD"
    NIGHTMARE = "NIGHTMARE"


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))

    gems: Mapped[int] = mapped_column(Integer, default=0)
    coins: Mapped[int] = mapped_column(Integer, default=0)
    shards: Mapped[int] = mapped_column(Integer, default=0)
    # Premium character-pack currency. Drops rarely in-game; main sink for the store.
    access_cards: Mapped[int] = mapped_column(Integer, default=0)
    energy_stored: Mapped[int] = mapped_column(Integer, default=0)
    energy_last_tick_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)

    pulls_since_epic: Mapped[int] = mapped_column(Integer, default=0)
    stages_cleared_json: Mapped[str] = mapped_column(String(1024), default="[]")

    arena_rating: Mapped[int] = mapped_column(Integer, default=1000, index=True)
    arena_wins: Mapped[int] = mapped_column(Integer, default=0)
    arena_losses: Mapped[int] = mapped_column(Integer, default=0)

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    banned_reason: Mapped[str] = mapped_column(String(256), default="")
    # NULL = permanent ban. If set, worker/deps auto-clear once now >= banned_until.
    banned_until: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    # Bumped on ban/demote to invalidate all outstanding JWTs for this account.
    # JWTs embed the token_version at issue; deps rejects any with a stale tv.
    token_version: Mapped[int] = mapped_column(Integer, default=0)

    # Daily login bonus state. streak counts consecutive days claimed; claiming
    # after a >48h gap resets to 1. cycle is 7 days, big gem payout on day 7.
    last_daily_claim_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    daily_streak: Mapped[int] = mapped_column(Integer, default=0)

    # Energy refills spent today (UTC day key). Resets on first refill of a new day.
    # Exists to cap refills-per-day so gems aren't a direct energy firehose.
    refills_today_key: Mapped[str] = mapped_column(String(10), default="")
    refills_today_count: Mapped[int] = mapped_column(Integer, default=0)

    # Free x1 summon tokens — consumed by /summon/x1 before shards. Granted by
    # first-time events (tutorial completion, starter pack, LiveOps). Can stack.
    free_summon_credits: Mapped[int] = mapped_column(Integer, default=0)

    # Shard-store usage tracking (gems → shards exchange). Mirrors the energy
    # refill counter shape: a UTC day key + a counter. Reset on first
    # exchange of a new day. Caps total per-day batches so a player can't
    # nuke their gem balance into shards faster than the gacha pacing intends.
    shard_exchanges_today_key: Mapped[str] = mapped_column(String(10), default="")
    shard_exchanges_today_count: Mapped[int] = mapped_column(Integer, default=0)

    # Inventory caps. Default values come from settings on Account creation.
    # Soft-enforced: a drop over cap doesn't vanish, it spills into
    # mailbox_overflow_json (a JSON list of {kind, payload, ts} entries that
    # the player redeems via the inventory tab once they make room).
    hero_slot_cap: Mapped[int] = mapped_column(Integer, default=50)
    gear_slot_cap: Mapped[int] = mapped_column(Integer, default=200)
    mailbox_overflow_json: Mapped[str] = mapped_column(String(8192), default="[]")

    # Per-event progression state. Keyed by event id (matches LiveOpsEvent.name's
    # slugified form), value is a dict containing:
    #   currency: int             — accumulated event currency balance
    #   quests:   {code: int}     — per-quest progress
    #   claimed_quests: [code]    — quests whose reward was already claimed
    #   redeemed_milestones: [int] — indices of milestones already redeemed
    # Empty dict for new players. Stored as JSON because event configs come
    # from JSON specs and we don't want a new table per event kind.
    event_state_json: Mapped[str] = mapped_column(String(8192), default="{}")

    # Achievements unlocked by this account. JSON dict keyed by achievement
    # code with value = ISO timestamp of unlock. Catalog lives in
    # app/achievements.py — content-as-code, not DB-driven.
    achievements_json: Mapped[str] = mapped_column(String(4096), default="{}")

    # Account-level progression — separate from per-hero levels. Battle wins,
    # summon pulls, and raid attacks all grant account XP. Level-ups grant
    # rewards from app.account_level.LEVEL_REWARDS. Gates story chapters and
    # (Phase 3) the alignment fork at level 50.
    account_level: Mapped[int] = mapped_column(Integer, default=1)
    account_xp: Mapped[int] = mapped_column(Integer, default=0)

    # Story state — JSON dict tracking which chapter cutscenes the player has
    # already seen. Keyed by "chapter_code:beat_index" with timestamp values.
    # Lets the client hide already-seen cutscenes on replay.
    story_state_json: Mapped[str] = mapped_column(String(2048), default="{}")

    # Progression flag: have we granted the tutorial-clear reward for this
    # account yet? Prevents double-dipping via delete + re-register loops on
    # the same email address in SQLite dev setups. Stage clears themselves are
    # tracked in stages_cleared_json; this separate bit records that the
    # one-time reward was paid out.
    tutorial_reward_granted: Mapped[bool] = mapped_column(Boolean, default=False)

    # Email verification state. Unverified accounts can still play, but endpoints
    # that require verification (trading, big gem purchases, recovery) can gate
    # on this via deps.get_verified_account. Timestamp is set when verified.
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    # TOTP (RFC 6238) two-factor auth. totp_secret is the Base32-encoded shared
    # key (stored plain — acceptable for alpha; DB-at-rest encryption is a
    # separate concern). totp_enabled is flipped once the user confirms their
    # first valid code during enrollment.
    totp_secret: Mapped[str] = mapped_column(String(64), default="")
    totp_enabled: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)

    heroes: Mapped[list["HeroInstance"]] = relationship(
        back_populates="account", cascade="all,delete-orphan"
    )


class HeroTemplate(Base):
    __tablename__ = "hero_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    rarity: Mapped[Rarity] = mapped_column(String(16), index=True)
    faction: Mapped[Faction] = mapped_column(String(16))
    role: Mapped[Role] = mapped_column(String(8))

    base_hp: Mapped[int] = mapped_column(Integer)
    base_atk: Mapped[int] = mapped_column(Integer)
    base_def: Mapped[int] = mapped_column(Integer)
    base_spd: Mapped[int] = mapped_column(Integer)

    basic_mult: Mapped[float] = mapped_column(Float, default=1.0)
    special_json: Mapped[str] = mapped_column(String(1024), default="null")
    special_cooldown: Mapped[int] = mapped_column(Integer, default=0)


class HeroInstance(Base):
    __tablename__ = "hero_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    template_id: Mapped[int] = mapped_column(
        ForeignKey("hero_templates.id", ondelete="RESTRICT"), index=True
    )
    level: Mapped[int] = mapped_column(Integer, default=1)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    special_level: Mapped[int] = mapped_column(Integer, default=1)
    stars: Mapped[int] = mapped_column(Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)

    account: Mapped[Account] = relationship(back_populates="heroes")
    template: Mapped[HeroTemplate] = relationship()
    gear: Mapped[list["Gear"]] = relationship(
        back_populates="equipped_on", foreign_keys="Gear.hero_instance_id"
    )


class Stage(Base):
    __tablename__ = "stages"
    __table_args__ = (UniqueConstraint("code"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), index=True)
    name: Mapped[str] = mapped_column(String(128))
    order: Mapped[int] = mapped_column(Integer, index=True)
    energy_cost: Mapped[int] = mapped_column(Integer, default=5)
    recommended_power: Mapped[int] = mapped_column(Integer, default=0)
    waves_json: Mapped[str] = mapped_column(String(4096))
    coin_reward: Mapped[int] = mapped_column(Integer, default=100)
    first_clear_gems: Mapped[int] = mapped_column(Integer, default=25)
    first_clear_shards: Mapped[int] = mapped_column(Integer, default=1)
    # Campaign tier. Higher tiers share the waves of their NORMAL counterpart but
    # with scaled enemy levels + rewards. HARD gated on NORMAL clear.
    difficulty_tier: Mapped[StageDifficulty] = mapped_column(
        String(16), default=StageDifficulty.NORMAL, index=True
    )
    # For HARD+ tiers: the code of the NORMAL stage whose clear unlocks this one.
    # Empty string means "no prerequisite" (NORMAL tier stages).
    requires_code: Mapped[str] = mapped_column(String(64), default="")


class Battle(Base):
    __tablename__ = "battles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    stage_id: Mapped[int] = mapped_column(ForeignKey("stages.id"), index=True)
    team_json: Mapped[str] = mapped_column(String(1024))
    outcome: Mapped[BattleOutcome] = mapped_column(String(8))
    log_json: Mapped[str] = mapped_column(String(65536))
    # Snapshot of each uid's side/name/role/level/max_hp — lets replay reconstruct
    # the roster without re-simulating or dereferencing potentially-changed heroes.
    participants_json: Mapped[str] = mapped_column(String(4096), default="[]")
    rewards_json: Mapped[str] = mapped_column(String(1024))
    first_clear: Mapped[bool] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)


class GachaRecord(Base):
    __tablename__ = "gacha_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    template_id: Mapped[int] = mapped_column(ForeignKey("hero_templates.id"))
    rarity: Mapped[Rarity] = mapped_column(String(16))
    pity_before: Mapped[int] = mapped_column(Integer)
    pulled_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)


class Gear(Base):
    __tablename__ = "gear"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    slot: Mapped[GearSlot] = mapped_column(String(16))
    rarity: Mapped[GearRarity] = mapped_column(String(16))
    set_code: Mapped[GearSet] = mapped_column(String(16), default=GearSet.VITAL)
    # Flat-bonus stat map, e.g. {"atk": 30, "hp": 120}.
    stats_json: Mapped[str] = mapped_column(String(512), default="{}")
    hero_instance_id: Mapped[int | None] = mapped_column(
        ForeignKey("hero_instances.id", ondelete="SET NULL"), nullable=True, index=True
    )
    obtained_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)

    equipped_on: Mapped[HeroInstance | None] = relationship(
        back_populates="gear", foreign_keys=[hero_instance_id]
    )


class DefenseTeam(Base):
    __tablename__ = "defense_teams"

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    hero_ids_json: Mapped[str] = mapped_column(String(256))
    power: Mapped[int] = mapped_column(Integer, default=0, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)


class FriendshipStatus(StrEnum):
    PENDING = "PENDING"     # request sent, not yet accepted
    ACCEPTED = "ACCEPTED"
    BLOCKED = "BLOCKED"     # one direction — blocker hides messages from blockee


class Friendship(Base):
    """Directed friendship/block edge.

    Two-row pattern: when A and B both accept, rows (A→B, ACCEPTED) and
    (B→A, ACCEPTED) exist. Pending request: only requester→recipient.
    Block: single-direction row.
    """
    __tablename__ = "friendships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    other_account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[FriendshipStatus] = mapped_column(String(16), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)

    __table_args__ = (
        UniqueConstraint("account_id", "other_account_id", name="uq_friendship_pair"),
    )


class DirectMessage(Base):
    """1:1 message between two accounts. Read state tracked on the recipient
    side via read_at. Cascade-deletes when either account is removed.
    """
    __tablename__ = "direct_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sender_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    recipient_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    body: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True, index=True)
    # Soft-delete by the sender. Row stays so reports/audit still resolve, but
    # /dm/threads + /dm/with/* surface the body as "[deleted]" once set.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class DirectMessageReport(Base):
    """Abuse-report row. Player flags a DM; admin reviews via /admin/reports.
    Doesn't delete the message — preserves evidence."""
    __tablename__ = "direct_message_reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    reporter_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    message_id: Mapped[int] = mapped_column(
        ForeignKey("direct_messages.id", ondelete="CASCADE"), index=True
    )
    reason: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class Notification(Base):
    """In-app notification stream. Backs the bell icon + unread count badge.

    Examples: tutorial reward dropped, mailbox item available, achievement
    unlocked, daily reset, friend joined guild. read_at NULL = unread.
    Worker can prune rows older than ~30d in bulk.
    """
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32), index=True)
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(String(512), default="")
    link: Mapped[str] = mapped_column(String(256), default="")
    icon: Mapped[str] = mapped_column(String(8), default="🔔")
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True, index=True)


class CraftMaterial(Base):
    """Per-account inventory of a crafting material.

    Materials drop from battles + raids and are spent on `CraftRecipe`s. We
    track quantity-per-account-per-code rather than a row per dropped item:
    materials are stackable and identical, so one row per (account, code)
    keeps query cost flat and avoids 50,000-row inventory pages.

    Material codes are defined in app/crafting.py — there's no separate
    CraftMaterialTemplate table; the catalog is content-as-code so balance
    edits go through the normal review flow.
    """
    __tablename__ = "craft_materials"

    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    code: Mapped[str] = mapped_column(String(48), primary_key=True)
    quantity: Mapped[int] = mapped_column(Integer, default=0)


class CraftLog(Base):
    """Audit row per successful craft. Used by analytics + refund flows + the
    'recently crafted' history widget. Cheap to index by account/created_at.
    """
    __tablename__ = "craft_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    recipe_code: Mapped[str] = mapped_column(String(64), index=True)
    inputs_json: Mapped[str] = mapped_column(String(512), default="{}")  # snapshot of materials spent
    output_summary: Mapped[str] = mapped_column(String(256), default="")  # human-readable
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)


class TeamPreset(Base):
    """Named team saved for quick-pick on Battle / Arena / Raid tabs.

    Up to MAX_TEAM_PRESETS per account (enforced in the router). The stored
    hero_ids_json is a JSON array of HeroInstance ids; ownership is re-
    validated every time the preset is used — if a hero was sold or fed as
    ascension fodder, it's filtered out on read.
    """
    __tablename__ = "team_presets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(32))
    hero_ids_json: Mapped[str] = mapped_column(String(256))
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)

    __table_args__ = (UniqueConstraint("account_id", "name", name="uq_preset_per_account"),)


class DailyQuest(Base):
    __tablename__ = "daily_quests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    day_key: Mapped[str] = mapped_column(String(10), index=True)  # "YYYY-MM-DD" (UTC)
    kind: Mapped[DailyQuestKind] = mapped_column(String(24))
    status: Mapped[DailyQuestStatus] = mapped_column(String(16), default=DailyQuestStatus.ACTIVE, index=True)
    target_key: Mapped[str] = mapped_column(String(64), default="")  # e.g. stage code
    goal: Mapped[int] = mapped_column(Integer, default=1)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    reward_gems: Mapped[int] = mapped_column(Integer, default=0)
    reward_coins: Mapped[int] = mapped_column(Integer, default=0)
    reward_shards: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class LiveOpsEvent(Base):
    __tablename__ = "liveops_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[LiveOpsKind] = mapped_column(String(32), index=True)
    name: Mapped[str] = mapped_column(String(128))
    starts_at: Mapped[datetime] = mapped_column(DateTime(), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(), index=True)
    # Per-kind config, e.g. {"multiplier": 2.0} or {"chance_add": 0.3}
    payload_json: Mapped[str] = mapped_column(String(512), default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)


class Guild(Base):
    __tablename__ = "guilds"
    __table_args__ = (UniqueConstraint("name"), UniqueConstraint("tag"))

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(32))
    tag: Mapped[str] = mapped_column(String(6))
    description: Mapped[str] = mapped_column(String(256), default="")
    created_by: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)


class GuildMember(Base):
    __tablename__ = "guild_members"

    # Each account can be in at most one guild — account_id is the primary key.
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    guild_id: Mapped[int] = mapped_column(
        ForeignKey("guilds.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[GuildRole] = mapped_column(String(16), default=GuildRole.MEMBER)
    joined_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)


class GuildApplication(Base):
    __tablename__ = "guild_applications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    guild_id: Mapped[int] = mapped_column(
        ForeignKey("guilds.id", ondelete="CASCADE"), index=True
    )
    status: Mapped[GuildApplicationStatus] = mapped_column(
        String(16), default=GuildApplicationStatus.PENDING, index=True
    )
    message: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )


class GuildInvite(Base):
    """Guild-initiated counterpart to GuildApplication: leader/officer asks a
    specific player to join. The invitee accepts (joins) or rejects. Same
    PENDING/ACCEPTED/REJECTED/WITHDRAWN lifecycle as applications, just
    inverted: `inviter_id` is the officer who issued it, `account_id` is the
    target player.

    A player can have multiple PENDING invites from different guilds — first
    accept wins, the rest auto-reject when the player gains a guild membership.
    """

    __tablename__ = "guild_invites"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    # Target player (the one who decides).
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    guild_id: Mapped[int] = mapped_column(
        ForeignKey("guilds.id", ondelete="CASCADE"), index=True
    )
    # Officer/leader who issued the invite. SET NULL on delete so the audit
    # trail outlives the inviter's account.
    inviter_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[GuildApplicationStatus] = mapped_column(
        String(16), default=GuildApplicationStatus.PENDING, index=True
    )
    message: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class GuildMessage(Base):
    __tablename__ = "guild_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(
        ForeignKey("guilds.id", ondelete="CASCADE"), index=True
    )
    author_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    body: Mapped[str] = mapped_column(String(512))
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)


class Raid(Base):
    __tablename__ = "raids"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(
        ForeignKey("guilds.id", ondelete="CASCADE"), index=True
    )
    boss_template_id: Mapped[int] = mapped_column(ForeignKey("hero_templates.id"))
    boss_level: Mapped[int] = mapped_column(Integer, default=20)
    max_hp: Mapped[int] = mapped_column(Integer)
    remaining_hp: Mapped[int] = mapped_column(Integer)
    state: Mapped[RaidState] = mapped_column(String(16), default=RaidState.ACTIVE, index=True)
    # Difficulty tier: T1 (easy, always on for new guilds) → T3 (elite).
    tier: Mapped[RaidTier] = mapped_column(String(8), default=RaidTier.T1, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(), index=True)
    # NULL started_by means the worker auto-rotated this raid in rather than a player.
    started_by: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )


class RaidAttempt(Base):
    __tablename__ = "raid_attempts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    raid_id: Mapped[int] = mapped_column(
        ForeignKey("raids.id", ondelete="CASCADE"), index=True
    )
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    damage_dealt: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)


class ArenaMatch(Base):
    __tablename__ = "arena_matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    attacker_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    defender_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    outcome: Mapped[BattleOutcome] = mapped_column(String(8))
    rating_delta: Mapped[int] = mapped_column(Integer, default=0)
    attacker_rating_after: Mapped[int] = mapped_column(Integer, default=1000)
    defender_rating_after: Mapped[int] = mapped_column(Integer, default=1000)
    log_json: Mapped[str] = mapped_column(String(65536))
    # Same snapshot shape as Battle.participants_json so the Phaser replay view
    # works unchanged: [{uid, side, name, role, level, max_hp, template_code}].
    participants_json: Mapped[str] = mapped_column(String(4096), default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)


class TotpRecoveryCode(Base):
    """Single-use backup codes for 2FA. Generated at /auth/2fa/confirm and
    /auth/2fa/regenerate-codes, returned to the user exactly once (hash stays in
    DB). If they lose their authenticator, one code substitutes for a TOTP at
    /auth/2fa/verify; it's marked used and can't be reused.
    """

    __tablename__ = "totp_recovery_codes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    code_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class RefreshToken(Base):
    """Long-lived credential used to mint fresh access tokens without re-login.

    Hash-only storage (same as password reset / verification tokens).
    On each successful refresh the token is rotated: the old row gets
    `replaced_by_id` + `revoked_at`, a new row is issued. Reuse-detection:
    if a client presents a token whose `replaced_by_id` is set (i.e. it was
    rotated out), we treat it as a theft signal and revoke the entire
    account's refresh chain via a token_version bump.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), index=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    # Set to the new token id when this token is rotated. If a caller presents
    # a token row with replaced_by_id set, it means they're replaying an old
    # token — possible theft, so we revoke the chain.
    replaced_by_id: Mapped[int | None] = mapped_column(
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"), nullable=True
    )
    # Captured at issue time for the active-sessions list. Optional because
    # historical rows pre-date the columns. user_agent is truncated to 256 chars
    # at the call site so we don't carry pathological strings around.
    created_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(256), nullable=True)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    # SHA-256 of (user_agent | "|" | ip) at issue time. Compared against the
    # caller's fingerprint on every refresh; mismatches are logged + counted
    # but NOT auto-revoked (UAs change with browser updates, IPs flip across
    # mobile→wifi). Detection signal, not an enforcement gate. NULL on rows
    # issued before this column was added.
    fingerprint_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)


class EmailVerificationToken(Base):
    """Single-use email verification token. Same hash-only storage policy as password
    reset: raw token exists only in the verification URL, server stores sha256."""

    __tablename__ = "email_verification_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class PasswordResetToken(Base):
    """Single-use password reset token. Stores a SHA-256 hash of the token so the
    raw value is never persisted (if the DB leaks, attackers can't impersonate resets).
    Client sends the raw token from the reset URL; server hashes + compares.
    """

    __tablename__ = "password_reset_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)  # sha256 hex
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class AdminAnnouncement(Base):
    """Server-wide message shown to all players. Think patch notes, outage headsup,
    "2x weekend incoming" teaser. Supports time-windowed visibility so a banner can
    auto-disappear after an event. Multiple can be active at once; client sorts by
    priority desc then id desc."""

    __tablename__ = "admin_announcements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(String(128))
    body: Mapped[str] = mapped_column(String(2048))
    priority: Mapped[int] = mapped_column(Integer, default=0, index=True)  # higher pins to top
    starts_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)


class AdminAuditLog(Base):
    """Append-only record of admin actions. Referenced accounts nulled on delete so
    the audit trail survives account deletion."""

    __tablename__ = "admin_audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("accounts.id", ondelete="SET NULL"), index=True, nullable=True
    )
    action: Mapped[str] = mapped_column(String(32), index=True)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    payload_json: Mapped[str] = mapped_column(String(2048), default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)


class ShopProduct(Base):
    """Purchasable product in the in-game store. Catalog entry — independent of any sale."""

    __tablename__ = "shop_products"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    title: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(512), default="")
    kind: Mapped[ShopProductKind] = mapped_column(String(32), index=True)
    # Price in USD cents. NULL currency_code == "USD".
    price_cents: Mapped[int] = mapped_column(Integer)
    currency_code: Mapped[str] = mapped_column(String(8), default="USD")
    # Maps to a Price object in the Stripe dashboard. Products without a price_id
    # can only be purchased via the mock processor (dev).
    stripe_price_id: Mapped[str] = mapped_column(String(64), default="")
    # What the purchase grants. JSON: {"gems": N, "shards": N, "access_cards": N, "coins": N,
    # "hero_template_code": "..."}. All fields optional.
    contents_json: Mapped[str] = mapped_column(String(1024), default="{}")
    sort_order: Mapped[int] = mapped_column(Integer, default=100, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    # Timed availability. NULL = always on when is_active.
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    # 0 = unlimited. 1 = one-time (starter packs). N = per-account cap.
    per_account_limit: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)


class Purchase(Base):
    """A completed or pending sale. Records the full context needed for refunds and audits."""

    __tablename__ = "purchases"
    # (processor, processor_ref) is the idempotency key — duplicate webhooks no-op.
    __table_args__ = (UniqueConstraint("processor", "processor_ref"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    sku: Mapped[str] = mapped_column(String(64), index=True)
    title_snapshot: Mapped[str] = mapped_column(String(128))
    price_cents_paid: Mapped[int] = mapped_column(Integer)
    currency_code: Mapped[str] = mapped_column(String(8), default="USD")
    processor: Mapped[str] = mapped_column(String(32), index=True)  # "mock", "stripe", "apple", "google"
    processor_ref: Mapped[str] = mapped_column(String(128), index=True)  # e.g. stripe charge id
    state: Mapped[PurchaseState] = mapped_column(
        String(16), default=PurchaseState.PENDING, index=True
    )
    # What was granted — snapshot so refund can reverse exactly what was given.
    contents_snapshot_json: Mapped[str] = mapped_column(String(1024), default="{}")
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    refunded_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    refund_reason: Mapped[str] = mapped_column(String(256), default="")


class PurchaseLedger(Base):
    """Audit-only: every paid-currency grant and refund debit. Never exposed to players;
    used for reconciliation and customer-support tooling.

    Example rows after a $4.99 gem purchase that grants 500 gems:
      - (purchase=17, kind='gems', amount=500, direction='GRANT')
    After admin refund:
      - (purchase=17, kind='gems', amount=500, direction='REFUND')
    """

    __tablename__ = "purchase_ledger"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_id: Mapped[int] = mapped_column(
        ForeignKey("purchases.id", ondelete="CASCADE"), index=True
    )
    kind: Mapped[str] = mapped_column(String(32), index=True)  # "gems", "shards", "access_cards", "coins", "hero"
    amount: Mapped[int] = mapped_column(Integer)
    direction: Mapped[LedgerDirection] = mapped_column(String(16), index=True)
    note: Mapped[str] = mapped_column(String(256), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)
