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
    WIN_BATTLES = "WIN_BATTLES"  # progress per battle WIN
    SUMMON_HEROES = "SUMMON_HEROES"  # progress per pull
    ARENA_ATTACKS = "ARENA_ATTACKS"  # progress per arena attack regardless of outcome
    CLEAR_STAGE_X = "CLEAR_STAGE_X"  # progress when clearing a specific stage code


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
    started_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(), index=True)
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
