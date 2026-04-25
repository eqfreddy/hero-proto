"""GDPR art. 20 — full account data export.

Returns a single JSON dict containing every row tied to the account that we
hold. Sensitive material (password_hash, TOTP secret, raw refresh tokens)
is excluded. Tokens that are *hashes* of secrets (refresh, reset, verify)
are replaced with `"<redacted>"` since they can't be reversed but also have
no value to the user.

Output is bounded by per-table caps to keep the response under ~10MB even
for old accounts. The user can re-call with the cursor params to page
through long histories — but for an MVP we just truncate with a warning
field documenting how many rows were omitted.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import (
    Account,
    AdminAuditLog,
    ArenaMatch,
    Battle,
    CraftLog,
    DailyQuest,
    DefenseTeam,
    DirectMessage,
    DirectMessageReport,
    Friendship,
    GachaRecord,
    Gear,
    GuildApplication,
    GuildMember,
    GuildMessage,
    HeroInstance,
    Notification,
    Purchase,
    RaidAttempt,
    TeamPreset,
)


# Per-table row caps. Battles + gacha records dominate by volume on any
# established account; everything else stays small naturally.
_MAX_ROWS = {
    "battles": 1000,
    "arena_matches": 500,
    "gacha_records": 1000,
    "daily_quests": 500,
    "raid_attempts": 500,
    "guild_messages_sent": 500,
    "direct_messages": 1000,
    "notifications": 500,
    "craft_log": 500,
}


def _try_json(s: str | None, default: Any = None) -> Any:
    if not s:
        return default
    try:
        return json.loads(s)
    except (json.JSONDecodeError, TypeError):
        return default


def _account_dict(a: Account) -> dict:
    """Account row, sans secrets. Hash columns kept as `<redacted>` so the
    user can prove the row exists without leaking attack-useful material."""
    return {
        "id": a.id,
        "email": a.email,
        "password_hash": "<redacted>",
        "gems": a.gems,
        "coins": a.coins,
        "shards": a.shards,
        "access_cards": a.access_cards,
        "energy_stored": a.energy_stored,
        "energy_last_tick_at": a.energy_last_tick_at,
        "pulls_since_epic": a.pulls_since_epic,
        "stages_cleared": _try_json(a.stages_cleared_json, []),
        "arena_rating": a.arena_rating,
        "arena_wins": a.arena_wins,
        "arena_losses": a.arena_losses,
        "is_admin": a.is_admin,
        "is_banned": a.is_banned,
        "banned_reason": a.banned_reason,
        "banned_until": a.banned_until,
        "token_version": a.token_version,
        "last_daily_claim_at": a.last_daily_claim_at,
        "daily_streak": a.daily_streak,
        "free_summon_credits": a.free_summon_credits,
        "hero_slot_cap": a.hero_slot_cap,
        "gear_slot_cap": a.gear_slot_cap,
        "mailbox_overflow": _try_json(a.mailbox_overflow_json, []),
        "event_state": _try_json(a.event_state_json, {}),
        "achievements": _try_json(a.achievements_json, {}),
        "account_level": a.account_level,
        "account_xp": a.account_xp,
        "story_state": _try_json(a.story_state_json, {}),
        "tutorial_reward_granted": a.tutorial_reward_granted,
        "email_verified": a.email_verified,
        "email_verified_at": a.email_verified_at,
        "totp_enabled": a.totp_enabled,
        "totp_secret": "<redacted>" if a.totp_enabled else None,
    }


def _hero_dict(h: HeroInstance) -> dict:
    return {
        "id": h.id,
        "template_code": h.template.code if h.template else None,
        "level": h.level,
        "xp": h.xp,
        "stars": h.stars,
        "special_level": h.special_level,
        "created_at": getattr(h, "created_at", None),
    }


def _gear_dict(g: Gear) -> dict:
    return {
        "id": g.id,
        "slot": str(g.slot),
        "rarity": str(g.rarity),
        "set": str(g.set_code),
        "stats": _try_json(g.stats_json, {}),
        "equipped_on_hero_id": g.hero_instance_id,
    }


def _battle_dict(b: Battle) -> dict:
    return {
        "id": b.id,
        "stage_id": b.stage_id,
        "outcome": str(b.outcome),
        "first_clear": bool(b.first_clear),
        "team_hero_ids": _try_json(b.team_json, []),
        "rewards": _try_json(b.rewards_json, {}),
        "created_at": b.created_at,
    }


def _arena_dict(m: ArenaMatch) -> dict:
    return {
        "id": m.id,
        "attacker_id": m.attacker_id,
        "defender_id": m.defender_id,
        "outcome": str(m.outcome),
        "rating_delta": m.rating_delta,
        "attacker_rating_after": m.attacker_rating_after,
        "defender_rating_after": m.defender_rating_after,
        "created_at": m.created_at,
    }


def _dm_dict(d: DirectMessage) -> dict:
    return {
        "id": d.id,
        "sender_id": d.sender_id,
        "recipient_id": d.recipient_id,
        "body": d.body,
        "created_at": d.created_at,
        "read_at": d.read_at,
    }


def _purchase_dict(p: Purchase) -> dict:
    return {
        "id": p.id,
        "sku": p.sku,
        "title_snapshot": p.title_snapshot,
        "processor": p.processor,
        "processor_ref": p.processor_ref,
        "state": str(p.state),
        "price_cents_paid": p.price_cents_paid,
        "currency_code": p.currency_code,
        "created_at": p.created_at,
        "completed_at": p.completed_at,
    }


def _notification_dict(n: Notification) -> dict:
    return {
        "id": n.id,
        "kind": n.kind,
        "title": n.title,
        "body": n.body,
        "link": n.link,
        "icon": n.icon,
        "read_at": n.read_at,
        "created_at": n.created_at,
    }


def _preset_dict(p: TeamPreset) -> dict:
    return {
        "id": p.id,
        "name": p.name,
        "team_hero_ids": _try_json(p.hero_ids_json, []),
        "created_at": getattr(p, "created_at", None),
    }


def _friendship_dict(f: Friendship) -> dict:
    return {
        "id": f.id,
        "account_id": f.account_id,
        "other_account_id": f.other_account_id,
        "status": str(f.status),
        "created_at": f.created_at,
    }


def _quest_dict(q: DailyQuest) -> dict:
    return {
        "id": q.id,
        "day_key": q.day_key,
        "kind": str(q.kind),
        "status": str(q.status),
        "target_key": q.target_key,
        "goal": q.goal,
        "progress": q.progress,
        "reward_gems": q.reward_gems,
        "reward_coins": q.reward_coins,
        "reward_shards": q.reward_shards,
        "created_at": q.created_at,
        "completed_at": q.completed_at,
        "claimed_at": q.claimed_at,
    }


def _raid_attempt_dict(a: RaidAttempt) -> dict:
    return {
        "id": a.id,
        "raid_id": a.raid_id,
        "damage_dealt": a.damage_dealt,
        "created_at": a.created_at,
    }


def _gacha_dict(g: GachaRecord) -> dict:
    return {
        "id": g.id,
        "rarity": str(g.rarity),
        "template_id": g.template_id,
        "pity_before": g.pity_before,
        "pulled_at": g.pulled_at,
    }


def _craft_dict(c: CraftLog) -> dict:
    return {
        "id": c.id,
        "recipe_code": c.recipe_code,
        "inputs": _try_json(c.inputs_json, {}),
        "output_summary": c.output_summary,
        "created_at": c.created_at,
    }


def _guild_msg_dict(m: GuildMessage) -> dict:
    return {
        "id": m.id,
        "guild_id": m.guild_id,
        "body": m.body,
        "created_at": m.created_at,
    }


def _audit_dict(e: AdminAuditLog) -> dict:
    return {
        "id": e.id,
        "action": e.action,
        "target_account_id": e.target_id,
        "payload": _try_json(e.payload_json, {}),
        "created_at": e.created_at,
    }


def _bounded_query(db: Session, query, key: str, mapper) -> tuple[list[dict], int]:
    """Run query, cap at _MAX_ROWS[key], report how many were omitted."""
    cap = _MAX_ROWS.get(key, 1000)
    rows = list(db.scalars(query.limit(cap + 1)))
    omitted = max(0, len(rows) - cap)
    return [mapper(r) for r in rows[:cap]], omitted


def export_account(db: Session, account: Account) -> dict:
    """Build the GDPR export blob for the given account."""
    omitted: dict[str, int] = {}

    heroes, _ = _bounded_query(
        db,
        select(HeroInstance).where(HeroInstance.account_id == account.id).order_by(HeroInstance.id),
        "heroes",
        _hero_dict,
    )

    gear, _ = _bounded_query(
        db,
        select(Gear).where(Gear.account_id == account.id).order_by(Gear.id),
        "gear",
        _gear_dict,
    )

    battles, om_b = _bounded_query(
        db,
        select(Battle).where(Battle.account_id == account.id).order_by(Battle.id.desc()),
        "battles",
        _battle_dict,
    )
    if om_b:
        omitted["battles"] = om_b

    arena, om_a = _bounded_query(
        db,
        select(ArenaMatch)
        .where((ArenaMatch.attacker_id == account.id) | (ArenaMatch.defender_id == account.id))
        .order_by(ArenaMatch.id.desc()),
        "arena_matches",
        _arena_dict,
    )
    if om_a:
        omitted["arena_matches"] = om_a

    gacha, om_g = _bounded_query(
        db,
        select(GachaRecord).where(GachaRecord.account_id == account.id).order_by(GachaRecord.id.desc()),
        "gacha_records",
        _gacha_dict,
    )
    if om_g:
        omitted["gacha_records"] = om_g

    quests, _ = _bounded_query(
        db,
        select(DailyQuest).where(DailyQuest.account_id == account.id).order_by(DailyQuest.id.desc()),
        "daily_quests",
        _quest_dict,
    )

    raid_attempts, _ = _bounded_query(
        db,
        select(RaidAttempt).where(RaidAttempt.account_id == account.id).order_by(RaidAttempt.id.desc()),
        "raid_attempts",
        _raid_attempt_dict,
    )

    presets = [
        _preset_dict(p)
        for p in db.scalars(select(TeamPreset).where(TeamPreset.account_id == account.id))
    ]

    friendships = [
        _friendship_dict(f)
        for f in db.scalars(select(Friendship).where(Friendship.account_id == account.id))
    ]

    dms, om_d = _bounded_query(
        db,
        select(DirectMessage)
        .where((DirectMessage.sender_id == account.id) | (DirectMessage.recipient_id == account.id))
        .order_by(DirectMessage.id.desc()),
        "direct_messages",
        _dm_dict,
    )
    if om_d:
        omitted["direct_messages"] = om_d

    notifs, om_n = _bounded_query(
        db,
        select(Notification).where(Notification.account_id == account.id).order_by(Notification.id.desc()),
        "notifications",
        _notification_dict,
    )
    if om_n:
        omitted["notifications"] = om_n

    purchases = [
        _purchase_dict(p)
        for p in db.scalars(select(Purchase).where(Purchase.account_id == account.id))
    ]

    guild_memberships = [
        {
            "guild_id": gm.guild_id,
            "role": str(gm.role),
            "joined_at": gm.joined_at,
        }
        for gm in db.scalars(select(GuildMember).where(GuildMember.account_id == account.id))
    ]

    guild_apps = [
        {
            "id": a.id,
            "guild_id": a.guild_id,
            "status": str(a.status),
            "created_at": a.created_at,
        }
        for a in db.scalars(select(GuildApplication).where(GuildApplication.account_id == account.id))
    ]

    guild_msgs, om_gm = _bounded_query(
        db,
        select(GuildMessage)
        .where(GuildMessage.author_id == account.id)
        .order_by(GuildMessage.id.desc()),
        "guild_messages_sent",
        _guild_msg_dict,
    )
    if om_gm:
        omitted["guild_messages_sent"] = om_gm

    craft_log, om_c = _bounded_query(
        db,
        select(CraftLog).where(CraftLog.account_id == account.id).order_by(CraftLog.id.desc()),
        "craft_log",
        _craft_dict,
    )
    if om_c:
        omitted["craft_log"] = om_c

    defense_team = db.get(DefenseTeam, account.id)

    abuse_reports_filed = [
        {
            "id": r.id,
            "message_id": r.message_id,
            "reason": r.reason,
            "created_at": r.created_at,
        }
        for r in db.scalars(
            select(DirectMessageReport).where(DirectMessageReport.reporter_id == account.id)
        )
    ]

    audit_log_admin_actions = [
        _audit_dict(e)
        for e in db.scalars(
            select(AdminAuditLog)
            .where(AdminAuditLog.actor_id == account.id)
            .order_by(AdminAuditLog.id.desc())
            .limit(500)
        )
    ] if account.is_admin else []

    return {
        "schema_version": 1,
        "exported_at": _try_json(None) or _iso_now(),
        "rows_omitted_by_cap": omitted,
        "account": _account_dict(account),
        "heroes": heroes,
        "gear": gear,
        "team_presets": presets,
        "battles": battles,
        "arena_matches": arena,
        "gacha_records": gacha,
        "daily_quests": quests,
        "raid_attempts": raid_attempts,
        "friendships": friendships,
        "direct_messages": dms,
        "abuse_reports_filed": abuse_reports_filed,
        "notifications": notifs,
        "purchases": purchases,
        "guild_memberships": guild_memberships,
        "guild_applications": guild_apps,
        "guild_messages_sent": guild_msgs,
        "craft_log": craft_log,
        "defense_team": (
            {
                "team_hero_ids": _try_json(defense_team.hero_ids_json, []),
                "power": defense_team.power,
                "updated_at": defense_team.updated_at,
            } if defense_team else None
        ),
        "admin_actions_taken": audit_log_admin_actions,
    }


def _iso_now() -> str:
    from app.models import utcnow as _u
    return _u().isoformat()
