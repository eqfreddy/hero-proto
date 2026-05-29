from datetime import datetime, timezone
from enum import StrEnum

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, text
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
    # Default narrative faction for new players — "haven't picked a side yet" in
    # the bigger Corp story. Phase 3's level-50 alignment fork transitions a
    # player out of EXILE into either RESISTANCE or CORP_GREED. Until then it's
    # purely cosmetic; combat synergy treats EXILE like any other faction (so a
    # team of 5 EXILE heroes gets the 5-of-faction synergy bonus).
    EXILE = "EXILE"
    # Phase 3.5 alignment factions — chosen at level 50, one-time irreversible
    # (gem-sink reset exists but is discouraged). RESISTANCE takes down the Corp;
    # CORP_GREED becomes it. Both unlock exclusive epic story chapters + a unique hero.
    RESISTANCE = "RESISTANCE"
    CORP_GREED = "CORP_GREED"


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
    # Player-chosen DEFEND action. 1 turn duration. Reduces incoming damage
    # by 50% and credits +25 limit gauge on apply. Cleared at start of the
    # defender's next turn (so it covers exactly one enemy attack cycle).
    DEFENDING = "DEFENDING"
    # Crash mechanic: a Crashed enemy takes amplified incoming damage for the
    # vulnerability window. value = damage-taken multiplier bonus (e.g. 0.30 = +30%).
    VULNERABLE = "VULNERABLE"


class BattleOutcome(StrEnum):
    WIN = "WIN"
    LOSS = "LOSS"
    DRAW = "DRAW"


class GearSlot(StrEnum):
    WEAPON = "WEAPON"
    # Six armor slots — head to toe.
    HEAD = "HEAD"      # was HELMET
    CHEST = "CHEST"    # was ARMOR
    HANDS = "HANDS"    # gloves/gauntlets
    WRIST = "WRIST"    # bracers/wristbands
    LEGS = "LEGS"      # greaves/cargo pants
    FEET = "FEET"      # was BOOTS
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
    # Phase 2.2 — limited-time summon banner that lets players pull a single
    # specified hero (MYTH-tier event hero — Applecrumb, etc.) outside the
    # standard pool. Payload: {"hero_template_code": str, "shard_cost": int,
    # "per_account_cap": int}. Active window is the event's starts_at/ends_at.
    EVENT_BANNER = "EVENT_BANNER"


class ShopProductKind(StrEnum):
    GEM_PACK = "GEM_PACK"
    SHARD_PACK = "SHARD_PACK"
    ACCESS_CARD_PACK = "ACCESS_CARD_PACK"
    COIN_PACK = "COIN_PACK"
    STARTER_BUNDLE = "STARTER_BUNDLE"
    WEEKLY_BUNDLE = "WEEKLY_BUNDLE"
    SEASONAL_BUNDLE = "SEASONAL_BUNDLE"
    BATTLE_PASS = "BATTLE_PASS"
    SUBSCRIPTION_CARD = "SUBSCRIPTION_CARD"


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
    LEGENDARY = "LEGENDARY"


STAGE_TIER_DISPLAY: dict[StageDifficulty, str] = {
    StageDifficulty.NORMAL:    "Floppy",
    StageDifficulty.HARD:      "Hard Disk",
    StageDifficulty.NIGHTMARE: "RAID-0",
    StageDifficulty.LEGENDARY: "Legen'waitforit'dary",
}


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
    # Per (stage_code, difficulty_tier) consecutive-loss counter for fail pity.
    # Shape: {"<stage_code>:<TIER>": int, "<stage_code>:<TIER>:_consumed": bool}.
    # Hidden from players — drives a one-shot 0.9× enemy HP discount after 3 losses.
    stage_pity_json: Mapped[str] = mapped_column(String(2048), default="{}", server_default="{}")
    # Per (stage_code, difficulty_tier) gear-drop meter for guaranteed RARE+ drops.
    # Shape: {"<stage_code>:<TIER>": int}.  Resets to 0 when the cap (20) fires.
    # See app/drop_meter.py for the increment + rarity-roll logic.
    stage_drop_pity_json: Mapped[str] = mapped_column(String(2048), default="{}", server_default="{}")

    # Per-account rare-collection progress.
    # Shape: {"<collection_code>": {"pieces": [...], "completed_at": "...", "claimed_at": "..."}}
    # See app/collections.py for the roll/award/complete/claim logic.
    collection_progress_json: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")

    # 8-track loot box inventory count. Earned via weekly chest, tower floor 50,
    # raid top-10%. v2 will add a buyable Stripe SKU.
    eight_tracks: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    arena_rating: Mapped[int] = mapped_column(Integer, default=1000, index=True)
    arena_wins: Mapped[int] = mapped_column(Integer, default=0)
    arena_losses: Mapped[int] = mapped_column(Integer, default=0)

    # Arena tickets — gate on attacks. Mirrors the energy regen pattern.
    arena_tickets_stored: Mapped[int] = mapped_column(Integer, default=5)
    arena_tickets_last_tick_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)

    # Weekly arena counter — resets at the ISO week boundary. Used by the
    # leaderboard payout distributor to filter parked accounts (must have
    # at least 1 win this week to be eligible for top-50 rewards).
    arena_weekly_wins: Mapped[int] = mapped_column(Integer, default=0)
    arena_weekly_key: Mapped[str] = mapped_column(String(10), default="")

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    banned_reason: Mapped[str] = mapped_column(String(256), default="")
    # NULL = permanent ban. If set, worker/deps auto-clear once now >= banned_until.
    banned_until: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    # Bumped on ban/demote to invalidate all outstanding JWTs for this account.
    # JWTs embed the token_version at issue; deps rejects any with a stale tv.
    token_version: Mapped[int] = mapped_column(Integer, default=0)

    # Brute-force lockout. Incremented on each wrong password; reset on success.
    # At LOGIN_LOCKOUT_ATTEMPTS failures, login_locked_until is set and all
    # further attempts return 401 until the window passes or password is reset.
    login_failed_attempts: Mapped[int] = mapped_column(Integer, default=0)
    login_locked_until: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    # Daily login bonus state. streak counts consecutive days claimed; claiming
    # after a >48h gap resets to 1. cycle is 7 days, big gem payout on day 7.
    last_daily_claim_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    daily_streak: Mapped[int] = mapped_column(Integer, default=0)

    # Consecutive-days battle-win streak. Used by the Stages header pill for
    # loss-aversion framing. Incremented on the first PvE win each UTC day;
    # a gap day resets to 1 on the next win.
    win_streak_days: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    win_streak_last_date: Mapped[str] = mapped_column(String(10), default="", server_default="")

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

    # Phase 2.4 — QoL unlocks owned by the player. JSON dict keyed by
    # unlock code (e.g. "auto_battle", "extra_team_presets") with value =
    # ISO timestamp of grant. Catalog of valid codes lives in app.store
    # alongside grant logic. Cosmetic frames are tracked separately below
    # so they're cheap to render in roster lists without parsing this.
    qol_unlocks_json: Mapped[str] = mapped_column(String(2048), default="{}")
    # Monthly Card subscription. End date is extended on purchase (stacks).
    # last_drip_at is a UTC date — "what calendar day did we last grant the
    # daily drip on" — used as idempotency lock so a single day grants once.
    monthly_card_ends_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    monthly_card_last_drip_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    # AFK income loop. NULL = never claimed; service treats as registration time.
    # Accrual capped at AFK_MAX_HOURS regardless of how long ago last claim was.
    afk_last_collected_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    # Rest XP — 2x XP multiplier on banked offline time.
    # Bank ticks down at 2x wallclock during active sessions, accumulates while offline.
    # Capped at 12h (43,200s). See app/rest_xp.py for the tick logic.
    rest_xp_banked_seconds: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rest_xp_last_tick_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, server_default=text("CURRENT_TIMESTAMP"))
    # VIP tier — cumulative-spend XP. 1 USD cent of paid purchases = 1 VIP XP.
    # Level resolved from VIP_TIERS table; perks are read-only derivations.
    vip_xp: Mapped[int] = mapped_column(Integer, default=0)
    vip_last_drip_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    # Friend Points — earned by daily ping send/receive between friends.
    # Spent on the friend-summon banner. Daily send-ping count (per UTC day)
    # tracked in friend_pings_today + friend_pings_today_date for cap enforcement.
    friend_points: Mapped[int] = mapped_column(Integer, default=0)
    friend_pings_sent_today: Mapped[int] = mapped_column(Integer, default=0)
    friend_pings_today_date: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    # Friend-summon banner has its own pity counter; standard banner unaffected.
    fp_pulls_since_epic: Mapped[int] = mapped_column(Integer, default=0)
    # Template shards — per-hero-template currency. Earned automatically on
    # duplicate gacha pulls; spent on hero ascension instead of fodder.
    # JSON dict keyed by HeroTemplate.code, value = int shard count.
    template_shards_json: Mapped[str] = mapped_column(String(8192), default="{}")
    # Tower of Trials — endless solo climb. tower_floor advances on win,
    # never decreases mid-season. Monthly reset returns floor → 1 but keeps
    # tower_best_floor as the all-time PB. attempts/today caps daily plays.
    tower_floor: Mapped[int] = mapped_column(Integer, default=1)
    tower_best_floor: Mapped[int] = mapped_column(Integer, default=0)
    tower_attempts_today: Mapped[int] = mapped_column(Integer, default=0)
    tower_attempts_today_date: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    tower_season_key: Mapped[str] = mapped_column(String(8), default="")
    # Cosmetic frame codes the player owns. JSON list of strings — frames
    # are pure visual flair on hero cards, no power. PoE2-style: cosmetics
    # are the recurring spend, never stat-boosting items.
    cosmetic_frames_json: Mapped[str] = mapped_column(String(2048), default="[]")
    # Currently-equipped cosmetic frame code. Must be in cosmetic_frames_json
    # or empty. Empty string means "no frame" — fallback to the rarity-
    # colored border on hero cards.
    active_cosmetic_frame: Mapped[str] = mapped_column(String(64), default="")

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

    # Player's narrative faction. Defaults to EXILE for all new accounts —
    # "not yet aligned" in the bigger Corp-vs-Resistance story. Phase 3's
    # level-50 fork flips this to RESISTANCE / CORP_GREED. No mechanical
    # weight pre-fork; surfaced on the profile + roster header so it reads
    # like an identity choice the player will make later.
    faction: Mapped[Faction] = mapped_column(String(16), default=Faction.EXILE)
    # Set when the player makes the level-50 alignment choice. NULL = still EXILE.
    # Used to prevent re-choosing without the gem-sink reset flow.
    alignment_chosen_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    # Story state — JSON dict tracking which chapter cutscenes the player has
    # already seen. Keyed by "chapter_code:beat_index" with timestamp values.
    # Lets the client hide already-seen cutscenes on replay.
    story_state_json: Mapped[str] = mapped_column(String(2048), default="{}")

    # Milestone rewards — see app/milestones.py for service logic.
    # legend_boss_shards: cross-template currency earned from milestone rolls.
    # milestone_legend_pity: consecutive non-award claims; resets to 0 on award.
    legend_boss_shards: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    milestone_legend_pity: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

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
    # Phase 3.1 — melee / ranged attack split. Heroes have one of two
    # basic-attack channels:
    #   "melee"  — close-range, no targeting cost, default for ATK/DEF.
    #   "ranged" — line-of-sight, can ignore frontline, default for
    #              ranged-flavored ATK/SUP heroes (mages, snipers).
    # Phase 3.2 will add a player-controlled targeting layer that
    # consumes this; for now the resolver routes basic damage through
    # one channel or the other so balance work can start.
    attack_kind: Mapped[str] = mapped_column(String(8), default="melee")
    mana_cost: Mapped[int] = mapped_column(Integer, default=10)
    mana_regen_per_turn: Mapped[int] = mapped_column(Integer, default=15)
    rig: Mapped[str] = mapped_column(String(64), default="stick-figure")
    # Milestone legend-boss summon pool. Only MYTH-rarity templates with this
    # flag set are eligible for the legend-boss summon (30 legend_boss_shards).
    is_legend_boss_pool: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")


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
    # Phase 2.2 — per-stat variance percentage rolled when this instance is
    # a *duplicate* summon (the player already owns ≥1 copy of the template).
    # First copy stays vanilla so seeded / starter heroes are deterministic.
    # Format: JSON dict with float values in [-VARIANCE_MAX, +VARIANCE_MAX]
    # for keys hp/atk/def/spd. Empty {} means "no variance applied" (first
    # copy or pre-Phase-2.2 hero).
    variance_pct_json: Mapped[str] = mapped_column(String(128), default="{}")
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


class Collection(Base):
    __tablename__ = "collections"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    theme: Mapped[str] = mapped_column(String(255), default="")
    rarity: Mapped[str] = mapped_column(String(16))           # UNCOMMON | RARE | EPIC | LEGENDARY
    level_bracket: Mapped[str] = mapped_column(String(8))     # "1-20" | "21-40" | "41-60"
    pieces_json: Mapped[str] = mapped_column(Text, default="[]")
    reward_json: Mapped[str] = mapped_column(Text, default="{}")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)


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
    # Optional name + flavor for "named" pieces — story rewards, raid drops,
    # etc. Regular RNG drops leave both null and the UI shows the slot name.
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    flavor: Mapped[str | None] = mapped_column(String(255), nullable=True)
    hero_instance_id: Mapped[int | None] = mapped_column(
        ForeignKey("hero_instances.id", ondelete="SET NULL"), nullable=True, index=True
    )
    locked: Mapped[bool] = mapped_column(Boolean, default=False, server_default="0")
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


class FriendPing(Base):
    """Daily ping log between friends. PK enforces 'one ping per (sender,
    recipient, UTC date)' so spam-pings can't farm Friend Points."""

    __tablename__ = "friend_pings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sender_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    recipient_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    sent_on: Mapped[datetime] = mapped_column(DateTime(), index=True)
    fp_granted: Mapped[int] = mapped_column(Integer, default=5)

    __table_args__ = (
        UniqueConstraint("sender_id", "recipient_id", "sent_on", name="uq_friend_pings_per_day"),
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


class DeviceToken(Base):
    """Push-notification device token for a logged-in account.

    One row per (account, token) pair. Platform is 'fcm' (Android/web) or
    'apns' (iOS). Tokens are upserted on registration and deleted on logout
    or explicit unregister. Rows older than 90 days are pruned by the worker.
    """

    __tablename__ = "device_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    token: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    platform: Mapped[str] = mapped_column(String(16))  # 'fcm' | 'apns'
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)


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


class LocationChallengeToken(Base):
    """Single-use challenge issued when a login arrives from an unrecognised IP
    prefix. The raw token is emailed to the account owner; only the SHA-256 hash
    is stored. Clicking the link in the email calls /auth/approve-login which
    validates the token and issues real access + refresh tokens.
    """

    __tablename__ = "location_challenge_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(), index=True)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    login_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(256), nullable=True)


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


class OfferBundle(Base):
    """Premium offer bundles — distinct from ShopProduct catalog items.

    Bundles use USD float pricing (not cents) and have their own purchase
    path (/shop/bundles/{code}/purchase) with built-in velocity limiting.
    They do NOT use ShopProduct.sku — the `code` field is the identifier
    passed in the URL.
    """

    __tablename__ = "offer_bundles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(512), default="")
    price_usd: Mapped[float] = mapped_column(Float)
    gems: Mapped[int] = mapped_column(Integer, default=0)
    shards: Mapped[int] = mapped_column(Integer, default=0)
    coins: Mapped[int] = mapped_column(Integer, default=0)
    access_cards: Mapped[int] = mapped_column(Integer, default=0)
    # Optional hero grant — null means no hero included.
    hero_template_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    # When True, a player can purchase this bundle at most once (enforced at runtime).
    one_per_account: Mapped[bool] = mapped_column(Boolean, default=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    # NULL bounds = always available while active.
    available_from: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    available_until: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)


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


class Quest(Base):
    __tablename__ = "quests"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(512), default="")
    tasks_json: Mapped[str] = mapped_column(String(8192), default="[]")
    reward_json: Mapped[str] = mapped_column(String(2048), default="{}")
    sort_order: Mapped[int] = mapped_column(Integer, default=0)


class AccountQuest(Base):
    __tablename__ = "account_quests"
    __table_args__ = (UniqueConstraint("account_id", "quest_id", name="uq_account_quests_account_quest"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(Integer, ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    quest_id: Mapped[str] = mapped_column(String(64), ForeignKey("quests.id"))
    progress_json: Mapped[str] = mapped_column(String(4096), default="{}")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    claim_choice: Mapped[str | None] = mapped_column(String(16), nullable=True)
    dismissed: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)


class BattlePassSeason(Base):
    """A 30-day Battle Pass season. Seeded on startup; one ACTIVE row at a time.

    `tracks_json` stores the full reward table as:
      {"free": [{"tier": 1, "kind": "coins", "amount": 500}, ...],
       "premium": [{"tier": 1, "kind": "gems", "amount": 50}, ...]}
    Every tier appears in both tracks; missing entries = no reward at that tier.
    `xp_per_tier` * 50 = total XP needed for the final tier.
    """

    __tablename__ = "battle_pass_seasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(512), default="")
    starts_at: Mapped[datetime] = mapped_column(DateTime(), index=True)
    ends_at: Mapped[datetime] = mapped_column(DateTime(), index=True)
    max_tier: Mapped[int] = mapped_column(Integer, default=50)
    xp_per_tier: Mapped[int] = mapped_column(Integer, default=200)
    premium_price_cents: Mapped[int] = mapped_column(Integer, default=999)
    tracks_json: Mapped[str] = mapped_column(String(16384), default='{"free":[],"premium":[]}')
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)


class AccountBattlePass(Base):
    """One row per (account, season). Created lazily on first XP grant or GET.

    `claimed_free_json` / `claimed_premium_json` are JSON lists of tier ints
    already redeemed — prevents double-claim. `premium_purchased_at` is set
    when the player buys the premium track for this season; the original
    Purchase row remains the audit/refund source of truth.
    """

    __tablename__ = "account_battle_pass"
    __table_args__ = (UniqueConstraint("account_id", "season_id", name="uq_account_battle_pass"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), index=True
    )
    season_id: Mapped[int] = mapped_column(
        ForeignKey("battle_pass_seasons.id", ondelete="CASCADE"), index=True
    )
    xp_total: Mapped[int] = mapped_column(Integer, default=0)
    claimed_free_json: Mapped[str] = mapped_column(String(2048), default="[]")
    claimed_premium_json: Mapped[str] = mapped_column(String(2048), default="[]")
    premium_purchased_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)


class ArenaWeeklyPayout(Base):
    """Idempotent ledger of weekly arena leaderboard payouts.

    Compound PK (week_key, account_id) is the idempotency lock — re-running
    the distributor for the same week is a no-op via INSERT ... ON CONFLICT
    DO NOTHING (or its driver-equivalent path).

    `acknowledged_at` is set when the player clicks "Claim" on the modal.
    Frontend uses null-acknowledged rows to populate `pending_arena_rewards`
    on `/me`.
    """
    __tablename__ = "arena_weekly_payouts"

    week_key: Mapped[str] = mapped_column(String(10), primary_key=True)
    account_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("accounts.id", ondelete="CASCADE"),
        primary_key=True,
        index=True,
    )
    rank: Mapped[int] = mapped_column(Integer)
    gems: Mapped[int] = mapped_column(Integer)
    eligible_wins: Mapped[int] = mapped_column(Integer)
    granted_at: Mapped[datetime] = mapped_column(DateTime(), default=utcnow)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)


class GuildAchievement(Base):
    """Definition row for a guild achievement. Seeded once; not user-created.

    `metric` names the counter key that `_update_guild_achievement` increments
    (e.g. "members_joined", "raids_completed"). `target_value` is the threshold
    at which `GuildAchievementProgress.completed_at` gets set.
    """

    __tablename__ = "guild_achievements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    code: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(String(256), default="")
    category: Mapped[str] = mapped_column(String(32), default="")
    metric: Mapped[str] = mapped_column(String(64))
    target_value: Mapped[int] = mapped_column(Integer)
    reward_gems: Mapped[int] = mapped_column(Integer, default=0)
    reward_coins: Mapped[int] = mapped_column(Integer, default=0)


class GuildAchievementProgress(Base):
    """Per-guild progress row for each achievement definition.

    Created on-demand the first time `_update_guild_achievement` fires for a
    (guild_id, achievement_code) pair. `current_value` is the running counter;
    `completed_at` is set (once) when current_value >= target_value.
    `reward_claimed_at` is set when a LEADER/OFFICER calls the claim endpoint.
    """

    __tablename__ = "guild_achievement_progress"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    guild_id: Mapped[int] = mapped_column(
        ForeignKey("guilds.id", ondelete="CASCADE"), index=True
    )
    achievement_code: Mapped[str] = mapped_column(String(64), index=True)
    current_value: Mapped[int] = mapped_column(Integer, default=0)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)
    reward_claimed_at: Mapped[datetime | None] = mapped_column(DateTime(), nullable=True)

    __table_args__ = (
        UniqueConstraint("guild_id", "achievement_code", name="uq_guild_achievement_progress"),
    )


# ---------------------------------------------------------------------------
# Milestone rewards — see docs/milestone-rewards-spec-2026-05-13.md
# ---------------------------------------------------------------------------


class StageMilestone(Base):
    """Static reward configuration row for each milestone threshold.
    Content-as-data so rewards can be adjusted without a code deploy.
    Seeded by the a3c8e1f2d9b4 migration.
    """

    __tablename__ = "stage_milestones"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    stage_count: Mapped[int] = mapped_column(Integer, nullable=False, unique=True, index=True)
    template_shards: Mapped[int] = mapped_column(Integer, nullable=False)
    legend_shard_chance: Mapped[float] = mapped_column(Float, nullable=False)
    label: Mapped[str] = mapped_column(String(64), default="")

    claims: Mapped[list["AccountMilestoneClaim"]] = relationship(back_populates="milestone")


class AccountMilestoneClaim(Base):
    """Per-account record of a claimed milestone. The UNIQUE constraint on
    (account_id, milestone_id) enforces idempotency at the DB level.
    """

    __tablename__ = "account_milestone_claims"
    __table_args__ = (
        UniqueConstraint("account_id", "milestone_id", name="uq_amc_account_milestone"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    account_id: Mapped[int] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    milestone_id: Mapped[int] = mapped_column(
        ForeignKey("stage_milestones.id"), nullable=False
    )
    claimed_at: Mapped[datetime] = mapped_column(DateTime(), nullable=False)
    template_shards_granted: Mapped[int] = mapped_column(Integer, nullable=False)
    legend_shards_granted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    milestone: Mapped[StageMilestone] = relationship(back_populates="claims")
