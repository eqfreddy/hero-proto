"""HTMX UI router.

Serves an HTML shell at /app and Jinja-rendered partials at /app/partials/*.
Partials are HTML fragments returned in response to hx-get calls from the shell.
Authentication reuses the same JWT bearer flow — the client-side script in
base.html attaches the token from localStorage on every htmx request.

This router returns HTML fragments; the existing JSON API under /me, /heroes,
etc. is untouched. HTMX callers are expected to hit these UI routes for
rendered HTML, and the JSON API for anything programmatic.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.deps import get_current_account
from app.economy import compute_energy, load_cleared
from app.gear_logic import gear_bonus_for
from app.combat import power_rating, scale_stat
from app.models import (
    Account,
    AdminAnnouncement,
    DailyQuest,
    HeroTemplate,
    DailyQuestStatus,
    Guild,
    GuildApplication,
    GuildApplicationStatus,
    GuildMember,
    GuildMessage,
    GuildRole,
    HeroInstance,
    Purchase,
    ShopProduct,
    Stage,
)
from app.store import product_contents, count_account_purchases

_TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATE_DIR))

router = APIRouter(prefix="/app", tags=["ui"], include_in_schema=False)


def _me_dict(account: Account) -> dict:
    return {
        "id": account.id,
        "email": account.email,
        "coins": account.coins,
        "gems": account.gems,
        "shards": account.shards,
        "access_cards": account.access_cards,
        "free_summon_credits": account.free_summon_credits or 0,
        "energy": compute_energy(account),
        "energy_cap": settings.energy_cap,
        "pulls_since_epic": account.pulls_since_epic,
        "stages_cleared": sorted(load_cleared(account)),
        "arena_rating": account.arena_rating,
        "arena_wins": account.arena_wins,
        "arena_losses": account.arena_losses,
    }


def _next_step(account: Account, db: Session) -> dict | None:
    """Compute the first unmet onboarding milestone for the Next-Step CTA card.
    Returns None once all early-game milestones are hit so the card self-dismisses.

    Milestones (ordered; earliest-unmet wins):
      1. Clear the tutorial stage
      2. Do your first summon
      3. Win your first real-campaign battle (post-tutorial)
      4. Claim your daily login bonus if available
    """
    from app.models import Battle, HeroInstance, Stage

    cleared = load_cleared(account)

    if "tutorial_first_ticket" not in cleared:
        return {
            "key": "tutorial",
            "title": "Start the tutorial",
            "body": "First Ticket — a gentle introduction. We pick the team for you; just click Battle.",
            "cta": "Start tutorial",
            "href": "/app/partials/stages",
            "auto_battle_stage": "tutorial_first_ticket",
        }

    # Post-tutorial: prompt for the first gacha pull. Starter heroes don't
    # count — we want the player to experience the summon loop.
    summons_done = db.query(HeroInstance).filter(
        HeroInstance.account_id == account.id,
    ).count()
    if summons_done <= 3:  # still only starter team
        credit = account.free_summon_credits or 0
        body = (
            f"You have {credit} free summon token" + ("s" if credit != 1 else "") + "."
            if credit > 0
            else f"Spend 1 shard ({account.shards} available) to pull your first hero."
        )
        return {
            "key": "summon",
            "title": "Do your first summon",
            "body": body,
            "cta": "Open Summon",
            "href": "/app/partials/summon",
        }

    has_real_battle = db.query(Battle).join(Stage).filter(
        Battle.account_id == account.id,
        Stage.code != "tutorial_first_ticket",
    ).limit(1).first() is not None
    if not has_real_battle:
        return {
            "key": "first_battle",
            "title": "Win your first real battle",
            "body": "The tutorial's done. Take a team into the main campaign.",
            "cta": "Open Stages",
            "href": "/app/partials/stages",
        }

    # All onboarding milestones hit — no CTA.
    return None


@router.get("", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
def shell(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "shell.html", {})


@router.get("/partials/login", response_class=HTMLResponse)
def partial_login(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "partials/login.html", {})


@router.get("/partials/me", response_class=HTMLResponse)
def partial_me(
    request: Request,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    me = _me_dict(account)
    # Guild name for the badge, if any.
    membership = db.get(GuildMember, account.id)
    guild = db.get(Guild, membership.guild_id) if membership else None
    # Daily bonus status for the claim card.
    from app.daily_bonus import can_claim, preview_next_streak, reward_for_streak
    daily_can, daily_next_at = can_claim(account)
    daily_next_streak = preview_next_streak(account)
    daily_reward = reward_for_streak(daily_next_streak)
    daily_bonus = {
        "can_claim": daily_can,
        "next_claim_at": daily_next_at.isoformat() if daily_next_at else None,
        "current_streak": account.daily_streak,
        "next_streak": daily_next_streak,
        "reward": {
            "coins": daily_reward.coins, "gems": daily_reward.gems,
            "shards": daily_reward.shards, "access_cards": daily_reward.access_cards,
        },
    }
    # Active announcements, highest-priority first.
    from datetime import datetime as _dt
    now = _dt.utcnow()
    announcements = [
        {"id": a.id, "title": a.title, "body": a.body, "priority": a.priority}
        for a in db.scalars(
            select(AdminAnnouncement)
            .where(AdminAnnouncement.is_active.is_(True), AdminAnnouncement.starts_at <= now)
            .order_by(desc(AdminAnnouncement.priority), desc(AdminAnnouncement.id))
            .limit(5)
        )
        if a.ends_at is None or a.ends_at > now
    ]
    return templates.TemplateResponse(
        request, "partials/me.html",
        {
            "me": me, "guild": guild,
            "announcements": announcements, "daily_bonus": daily_bonus,
            "next_step": _next_step(account, db),
        },
    )


def _hero_row(h: HeroInstance) -> dict:
    t = h.template
    bonus = gear_bonus_for(h)
    hp = scale_stat(t.base_hp, h.level, h.stars) + bonus.get("hp", 0)
    atk = scale_stat(t.base_atk, h.level, h.stars) + bonus.get("atk", 0)
    def_ = scale_stat(t.base_def, h.level, h.stars) + bonus.get("def", 0)
    spd = scale_stat(t.base_spd, h.level, h.stars) + bonus.get("spd", 0)
    return {
        "id": h.id,
        "name": t.name,
        "rarity": str(t.rarity),
        "role": str(t.role),
        "faction": str(t.faction),
        "level": h.level,
        "stars": h.stars,
        "hp": hp, "atk": atk, "def_": def_, "spd": spd,
        "power": power_rating(hp, atk, def_, spd),
    }


@router.get("/partials/roster", response_class=HTMLResponse)
def partial_roster(
    request: Request,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    heroes = list(
        db.scalars(
            select(HeroInstance)
            .where(HeroInstance.account_id == account.id)
            .order_by(HeroInstance.id.desc())
        )
    )
    rows = sorted((_hero_row(h) for h in heroes), key=lambda r: r["power"], reverse=True)
    return templates.TemplateResponse(request, "partials/roster.html", {"heroes": rows})


@router.get("/partials/stages", response_class=HTMLResponse)
def partial_stages(
    request: Request,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    cleared = load_cleared(account)
    rows = []
    for s in db.scalars(select(Stage).order_by(Stage.order)):
        locked = bool(s.requires_code) and s.requires_code not in cleared
        rows.append({
            "id": s.id, "code": s.code, "name": s.name, "order": s.order,
            "energy_cost": s.energy_cost,
            "recommended_power": s.recommended_power,
            "coin_reward": s.coin_reward,
            "first_clear_gems": s.first_clear_gems,
            "first_clear_shards": s.first_clear_shards,
            "cleared": s.code in cleared,
            "difficulty_tier": str(s.difficulty_tier),
            "requires_code": s.requires_code,
            "locked": locked,
        })
    normal = [r for r in rows if r["difficulty_tier"] == "NORMAL"]
    hard = [r for r in rows if r["difficulty_tier"] == "HARD"]
    nightmare = [r for r in rows if r["difficulty_tier"] == "NIGHTMARE"]
    return templates.TemplateResponse(
        request, "partials/stages.html",
        {"normal": normal, "hard": hard, "nightmare": nightmare, "me": _me_dict(account)},
    )


@router.get("/partials/daily", response_class=HTMLResponse)
def partial_daily(
    request: Request,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    quests = list(
        db.scalars(
            select(DailyQuest)
            .where(
                DailyQuest.account_id == account.id,
                DailyQuest.status != DailyQuestStatus.CLAIMED,
            )
            .order_by(DailyQuest.id)
        )
    )
    rows = [
        {
            "id": q.id, "kind": str(q.kind), "status": str(q.status),
            "target_key": q.target_key, "goal": q.goal, "progress": q.progress,
            "reward_coins": q.reward_coins, "reward_gems": q.reward_gems,
            "reward_shards": q.reward_shards, "day_key": q.day_key,
        }
        for q in quests
    ]
    return templates.TemplateResponse(request, "partials/daily.html", {"quests": rows})


@router.get("/partials/arena", response_class=HTMLResponse)
def partial_arena(
    request: Request,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    from app.models import DefenseTeam
    # Opponents: up to 10 accounts with defense teams, excluding self.
    pool = list(
        db.scalars(
            select(DefenseTeam.account_id, DefenseTeam.power)
            .where(DefenseTeam.account_id != account.id)
            .limit(10)
        )
    )
    opponents = []
    for def_team in db.execute(
        select(DefenseTeam.account_id, DefenseTeam.power, Account.email, Account.arena_rating)
        .join(Account, Account.id == DefenseTeam.account_id)
        .where(DefenseTeam.account_id != account.id)
        .order_by(desc(Account.arena_rating))
        .limit(10)
    ):
        opponents.append({
            "account_id": def_team[0], "defense_power": def_team[1],
            "name": def_team[2].split("@")[0], "arena_rating": def_team[3],
        })
    # Leaderboard: top 20 by rating.
    leaderboard = [
        {"account_id": r[0], "name": r[1].split("@")[0], "arena_rating": r[2], "wins": r[3], "losses": r[4]}
        for r in db.execute(
            select(Account.id, Account.email, Account.arena_rating, Account.arena_wins, Account.arena_losses)
            .order_by(desc(Account.arena_rating), Account.id)
            .limit(20)
        )
    ]
    # Recent matches involving this account (attacker or defender), newest first.
    from app.models import ArenaMatch
    recent_matches_rows = db.execute(
        select(
            ArenaMatch.id, ArenaMatch.attacker_id, ArenaMatch.defender_id,
            ArenaMatch.outcome, ArenaMatch.rating_delta, ArenaMatch.created_at,
        )
        .where((ArenaMatch.attacker_id == account.id) | (ArenaMatch.defender_id == account.id))
        .order_by(desc(ArenaMatch.id))
        .limit(10)
    )
    recent_matches = []
    for row in recent_matches_rows:
        mid, att_id, def_id, outcome, delta, created = row
        # Resolve the opponent's display name for context.
        other_id = def_id if att_id == account.id else att_id
        other = db.get(Account, other_id)
        recent_matches.append({
            "id": mid,
            "outcome": str(outcome),
            "rating_delta": delta,
            "created_at": created,
            "role": "attacker" if att_id == account.id else "defender",
            "opponent_name": other.email.split("@")[0] if other else "[gone]",
        })
    return templates.TemplateResponse(
        request, "partials/arena.html",
        {"me": _me_dict(account), "opponents": opponents, "leaderboard": leaderboard,
         "recent_matches": recent_matches},
    )


@router.get("/partials/guild", response_class=HTMLResponse)
def partial_guild(
    request: Request,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    membership = db.get(GuildMember, account.id)
    if membership is None:
        all_guilds = [
            {"id": g.id, "name": g.name, "tag": g.tag, "description": g.description,
             "member_count": db.query(GuildMember).filter_by(guild_id=g.id).count()}
            for g in db.scalars(select(Guild).order_by(Guild.id))
        ]
        return templates.TemplateResponse(
            request, "partials/guild.html",
            {"guild": None, "me": _me_dict(account), "all_guilds": all_guilds,
             "is_leader": False, "is_officer_or_leader": False},
        )

    guild = db.get(Guild, membership.guild_id)
    members_rows = db.execute(
        select(Account.id, Account.email, GuildMember.role, Account.arena_rating)
        .join(GuildMember, GuildMember.account_id == Account.id)
        .where(GuildMember.guild_id == guild.id)
        .order_by(Account.arena_rating.desc(), Account.id)
    )
    members = [
        {"account_id": row[0], "name": row[1].split("@")[0], "role": str(row[2]), "arena_rating": row[3]}
        for row in members_rows
    ]
    guild_obj = {
        "id": guild.id, "name": guild.name, "tag": guild.tag,
        "description": guild.description,
        "member_count": len(members), "members": members,
    }

    is_leader = membership.role == GuildRole.LEADER
    is_officer_or_leader = membership.role in (GuildRole.LEADER, GuildRole.OFFICER)

    applications = []
    if is_officer_or_leader:
        for a in db.scalars(
            select(GuildApplication)
            .where(
                GuildApplication.guild_id == guild.id,
                GuildApplication.status == GuildApplicationStatus.PENDING,
            )
            .order_by(GuildApplication.created_at.desc())
        ):
            applicant = db.get(Account, a.account_id)
            applications.append({
                "id": a.id, "applicant_name": applicant.email.split("@")[0] if applicant else "[gone]",
                "message": a.message,
            })

    messages = list(
        db.execute(
            select(GuildMessage.id, GuildMessage.author_id, Account.email, GuildMessage.body, GuildMessage.created_at)
            .outerjoin(Account, Account.id == GuildMessage.author_id)
            .where(GuildMessage.guild_id == guild.id)
            .order_by(desc(GuildMessage.id))
            .limit(20)
        )
    )
    msg_rows = [
        {"id": m[0], "author_name": (m[2].split("@")[0] if m[2] else "[gone]"),
         "body": m[3], "created_at": m[4]}
        for m in messages
    ]

    return templates.TemplateResponse(
        request, "partials/guild.html",
        {
            "guild": guild_obj,
            "me": _me_dict(account),
            "my_role": str(membership.role),
            "is_leader": is_leader,
            "is_officer_or_leader": is_officer_or_leader,
            "applications": applications,
            "messages": msg_rows,
            "all_guilds": [],
        },
    )


@router.get("/partials/shop", response_class=HTMLResponse)
def partial_shop(
    request: Request,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    from datetime import datetime as _dt
    now = _dt.utcnow()
    products = []
    starter = None
    for p in db.scalars(
        select(ShopProduct)
        .where(ShopProduct.is_active.is_(True))
        .order_by(ShopProduct.sort_order, ShopProduct.id)
    ):
        # Timed filter: skip not-yet-started and already-ended products.
        if p.starts_at is not None and now < p.starts_at:
            continue
        if p.ends_at is not None and now >= p.ends_at:
            continue
        # Skip products the account has already maxed out on per_account_limit.
        if p.per_account_limit:
            owned = count_account_purchases(db, account.id, p.sku)
            if owned >= p.per_account_limit:
                continue
        row = {
            "sku": p.sku, "title": p.title, "description": p.description,
            "kind": str(p.kind), "price_cents": p.price_cents,
            "currency_code": p.currency_code,
            "contents": product_contents(p),
            "has_stripe": bool(p.stripe_price_id),
        }
        if p.kind == "STARTER_BUNDLE" and starter is None:
            starter = row
        else:
            products.append(row)

    # Recent purchase history (most recent 8) with short granted summary.
    history_rows = list(
        db.scalars(
            select(Purchase)
            .where(Purchase.account_id == account.id)
            .order_by(Purchase.id.desc())
            .limit(8)
        )
    )
    history = []
    for pr in history_rows:
        try:
            granted = json.loads(pr.contents_snapshot_json or "{}")
        except json.JSONDecodeError:
            granted = {}
        short_bits = []
        for k, v in granted.items():
            if isinstance(v, int) and v:
                short_bits.append(f"+{v} {k}")
        history.append({
            "id": pr.id, "title": pr.title_snapshot, "sku": pr.sku,
            "state": str(pr.state), "price_cents": pr.price_cents_paid,
            "created_at": pr.created_at, "granted_short": ", ".join(short_bits),
        })

    return templates.TemplateResponse(
        request, "partials/shop.html",
        {"me": _me_dict(account), "products": products, "starter": starter, "history": history},
    )


# --- Placeholder portraits ---------------------------------------------------

_ROLE_COLORS = {"ATK": "#ff7a59", "DEF": "#59a0ff", "SUP": "#6dd39a"}
_RARITY_FRAMES = {
    "COMMON": "#9ca7b3", "UNCOMMON": "#6dd39a",
    "RARE": "#59a0ff", "EPIC": "#c97aff", "LEGENDARY": "#ffd86b",
}


def _initials(name: str, n: int = 2) -> str:
    words = [w for w in (name or "").strip().split() if w]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:n].upper()
    return "".join(w[0] for w in words[:n]).upper()


@router.get("/placeholder/hero/{code}.svg", response_class=Response, include_in_schema=False)
def placeholder_hero(
    code: str,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    """On-the-fly role-tinted SVG silhouette with hero initials. Used as portrait
    fallback when there's no art in /app/static/heroes/<code>.svg yet."""
    tmpl = db.scalar(select(HeroTemplate).where(HeroTemplate.code == code))
    if tmpl is None:
        role_color = "#7d8a9c"
        frame_color = "#2d3847"
        initials = code[:2].upper() if code else "??"
    else:
        role_color = _ROLE_COLORS.get(str(tmpl.role), "#7d8a9c")
        frame_color = _RARITY_FRAMES.get(str(tmpl.rarity), "#2d3847")
        initials = _initials(tmpl.name)

    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">'
        f'<rect width="128" height="128" rx="12" ry="12" fill="#14202b" stroke="{frame_color}" stroke-width="3"/>'
        f'<circle cx="64" cy="50" r="26" fill="{role_color}" opacity="0.85"/>'
        f'<path d="M20 120 Q20 78 64 78 Q108 78 108 120 Z" fill="{role_color}" opacity="0.6"/>'
        f'<text x="64" y="60" text-anchor="middle" font-family="system-ui, sans-serif" '
        f'font-weight="800" font-size="22" fill="#0b0d10">{initials}</text>'
        '</svg>'
    )
    return Response(content=svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=3600"})
