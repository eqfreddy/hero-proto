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
    utcnow,
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
    # Inventory cap status — drives the "Inventory" card on /me with usage
    # bars + expansion + mailbox.
    from app.inventory import gear_usage as _gu, hero_usage as _hu, list_mailbox
    h_use = _hu(db, account)
    g_use = _gu(db, account)
    inv_status = {
        "hero": {"used": h_use.used, "cap": h_use.cap, "full": h_use.full},
        "gear": {"used": g_use.used, "cap": g_use.cap, "full": g_use.full},
        "mailbox_count": len(list_mailbox(account)),
        "expansion_step": settings.slot_expansion_step,
        "expansion_cost_gems": settings.slot_expansion_cost_gems,
        "cap_max": settings.slot_cap_max,
    }
    return templates.TemplateResponse(
        request, "partials/me.html",
        {
            "me": me, "guild": guild,
            "announcements": announcements, "daily_bonus": daily_bonus,
            "next_step": _next_step(account, db),
            "inv": inv_status,
        },
    )


def _hero_row(h: HeroInstance) -> dict:
    t = h.template
    bonus = gear_bonus_for(h)
    # Apply Phase 2.2 variance to base stats before gear, matching the
    # combat resolver's order. Empty dict means "first copy, no variance".
    from app.gacha import parse_variance
    variance = parse_variance(getattr(h, "variance_pct_json", "") or "")
    hp_base = scale_stat(t.base_hp, h.level, h.stars)
    atk_base = scale_stat(t.base_atk, h.level, h.stars)
    def_base = scale_stat(t.base_def, h.level, h.stars)
    spd_base = scale_stat(t.base_spd, h.level, h.stars)
    if variance:
        hp_base = int(round(hp_base * (1.0 + variance.get("hp", 0.0))))
        atk_base = int(round(atk_base * (1.0 + variance.get("atk", 0.0))))
        def_base = int(round(def_base * (1.0 + variance.get("def", 0.0))))
        spd_base = int(round(spd_base * (1.0 + variance.get("spd", 0.0))))
    hp = hp_base + bonus.get("hp", 0)
    atk = atk_base + bonus.get("atk", 0)
    def_ = def_base + bonus.get("def", 0)
    spd = spd_base + bonus.get("spd", 0)
    return {
        "id": h.id,
        "code": t.code,
        "name": t.name,
        "rarity": str(t.rarity),
        "role": str(t.role),
        "faction": str(t.faction),
        "level": h.level,
        "stars": h.stars,
        "special_level": h.special_level,
        "hp": hp, "atk": atk, "def_": def_, "spd": spd,
        "power": power_rating(hp, atk, def_, spd),
        # Phase 2.2 — sum-of-variance for the grid badge ("hot rolls"
        # on a roster card). Net positive shows green, net negative red.
        "variance_net": round(sum(variance.values()), 4) if variance else 0.0,
        "has_variance": bool(variance),
    }


@router.get("/partials/crafting", response_class=HTMLResponse)
def partial_crafting(
    request: Request,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    """Crafting tab — material inventory across the top, recipe grid below.
    Recipe craftability is computed server-side (same logic as the JSON
    endpoint) so the template doesn't have to re-derive it."""
    from app.crafting import (
        MATERIALS as _MATS,
        all_materials as _all_mats,
        list_recipe_dicts as _recipes,
    )
    inv = _all_mats(db, account)
    materials = []
    for m in _MATS.values():
        materials.append({
            "code": m.code, "name": m.name, "rarity": m.rarity,
            "description": m.description, "icon": m.icon,
            "quantity": inv.get(m.code, 0),
        })
    recipes = []
    for r in _recipes():
        reason = None
        for code, qty in r["materials"].items():
            have = inv.get(code, 0)
            if have < qty:
                reason = f"need {qty - have} more {_MATS[code].name if code in _MATS else code}"
                break
        if reason is None and account.coins < r["coin_cost"]:
            reason = f"need {r['coin_cost'] - account.coins} more coins"
        if reason is None and account.gems < r["gem_cost"]:
            reason = f"need {r['gem_cost'] - account.gems} more gems"
        recipes.append({**r, "craftable": reason is None, "blocking_reason": reason})
    return templates.TemplateResponse(
        request, "partials/crafting.html",
        {"me": _me_dict(account), "materials": materials, "recipes": recipes,
         "material_lookup": {m["code"]: m for m in materials}},
    )


@router.get("/partials/friends", response_class=HTMLResponse)
def partial_friends(
    request: Request,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    """Friends + DMs tab. All data fetched client-side after first render —
    keeps the partial cheap and lets the client poll for unread DMs."""
    return templates.TemplateResponse(request, "partials/friends.html", {})


@router.get("/partials/account", response_class=HTMLResponse)
def partial_account(
    request: Request,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    """Account / security panel: active sessions, GDPR data export, 2FA
    status, password change. All data fetched client-side from /me/sessions
    + /me + /me/export so the partial itself is just shell + JS."""
    return templates.TemplateResponse(request, "partials/account.html", {})


@router.get("/partials/raids", response_class=HTMLResponse)
def partial_raids(
    request: Request,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    """Guild raids tab. Surfaces /raids/mine (active raid for caller's guild)
    and /raids/leaderboard (top contributors this week). Empty states cover
    not-in-guild and no-active-raid (auto-rotation kicks in within 24h of
    the previous raid ending)."""
    return templates.TemplateResponse(request, "partials/raids.html", {})


@router.get("/partials/story", response_class=HTMLResponse)
def partial_story(
    request: Request,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    from app.account_level import chapter_status_for_account, xp_to_next as _xpn
    return templates.TemplateResponse(
        request, "partials/story.html",
        {
            "account_level": int(account.account_level or 1),
            "account_xp": int(account.account_xp or 0),
            "account_xp_to_next": _xpn(account.account_level or 1),
            "chapters": chapter_status_for_account(account),
        },
    )


@router.get("/partials/achievements", response_class=HTMLResponse)
def partial_achievements(
    request: Request,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    from app.achievements import HARDCORE_ACHIEVEMENTS, unlock_progress as _up
    items = _up(db, account)
    unlocked = sum(1 for i in items if i["unlocked"])
    return templates.TemplateResponse(
        request, "partials/achievements.html",
        {
            "items": items, "unlocked": unlocked, "total": len(items),
            "hardcore": HARDCORE_ACHIEVEMENTS,
        },
    )


@router.get("/partials/event", response_class=HTMLResponse)
def partial_event(
    request: Request,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    """Active-event tab. Renders empty when no event is live so the link
    in the nav can be hidden via {% if event %} in the shell.
    """
    from app.event_state import (
        active_event_spec,
        currency_balance,
        is_claimed,
        quest_progress,
        redeemed_milestones,
    )
    spec = active_event_spec()
    if spec is None:
        return templates.TemplateResponse(
            request, "partials/event.html", {"event": None},
        )

    balance = currency_balance(account, spec.id)
    quests = []
    for q in spec.quests:
        prog = quest_progress(account, spec.id, q["code"])
        goal = int(q.get("goal", 1))
        quests.append({
            "code": q["code"],
            "title": q.get("title", q["code"]),
            "goal": goal,
            "progress": min(prog, goal),
            "currency_reward": int(q.get("currency_reward", 0)),
            "completed": prog >= goal,
            "claimed": is_claimed(account, spec.id, q["code"]),
        })
    redeemed = set(redeemed_milestones(account, spec.id))
    milestones = []
    for idx, m in enumerate(spec.milestones):
        cost = int(m.get("cost", 0))
        milestones.append({
            "idx": idx,
            "title": m.get("title", f"Milestone {idx + 1}"),
            "cost": cost,
            "contents": m.get("contents", {}),
            "redeemed": idx in redeemed,
            "affordable": balance >= cost,
        })

    return templates.TemplateResponse(
        request, "partials/event.html",
        {
            "event": {
                "id": spec.id,
                "display_name": spec.display_name,
                "currency_name": spec.currency_name or "currency",
                "currency_emoji": spec.currency_emoji or "★",
                "currency_balance": balance,
                "ends_at": spec.ends_at.isoformat() + "Z",
                "drops": spec.drops,
                "quests": quests,
                "milestones": milestones,
            },
        },
    )


@router.get("/partials/summon", response_class=HTMLResponse)
def partial_summon(
    request: Request,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> HTMLResponse:
    """Dedicated Summon tab — banner header, pity counter, recent-pulls
    feed, standard banner card with x1/x10 buttons. Starter-pack offer card
    surfaces here (Phase 1.5) when eligible.
    """
    from app.models import GachaRecord
    # Recent pulls — last 10 across all banners.
    recent_rows = list(db.execute(
        select(
            GachaRecord.id, GachaRecord.template_id, GachaRecord.rarity,
            GachaRecord.pulled_at, HeroTemplate.name, HeroTemplate.faction,
        )
        .join(HeroTemplate, HeroTemplate.id == GachaRecord.template_id)
        .where(GachaRecord.account_id == account.id)
        .order_by(desc(GachaRecord.id))
        .limit(10)
    ))
    recent = [
        {
            "id": int(r[0]),
            "template_id": int(r[1]),
            "rarity": str(r[2]),
            "pulled_at": r[3].isoformat() if r[3] else "",
            "name": r[4],
            "faction": str(r[5]),
        }
        for r in recent_rows
    ]
    # Pity progress — pulls_since_epic out of 50.
    pity_current = account.pulls_since_epic or 0
    PITY_CAP = 50
    pulls_to_pity = max(0, PITY_CAP - pity_current)

    # Starter-pack eligibility (Phase 1.5 surfaces the card here).
    from datetime import datetime as _dt, timedelta as _td
    starter_sku = "starter_jumpahead"
    starter_product = db.scalar(select(ShopProduct).where(ShopProduct.sku == starter_sku))
    starter_eligible = False
    starter_expires_at: _dt | None = None
    if starter_product is not None:
        already_purchased = count_account_purchases(db, account.id, starter_sku) > 0
        seven_day_window = account.created_at + _td(days=7) if getattr(account, "created_at", None) else None
        still_in_window = seven_day_window is None or seven_day_window > _dt.utcnow()
        starter_eligible = (not already_purchased) and still_in_window
        starter_expires_at = seven_day_window

    # QoL: quick_summon collapses the post-pull animation/refresh delay.
    import json as _json_su
    try:
        _qol = _json_su.loads(account.qol_unlocks_json or "{}")
        has_quick_summon = isinstance(_qol, dict) and "quick_summon" in _qol
    except _json_su.JSONDecodeError:
        has_quick_summon = False
    return templates.TemplateResponse(
        request, "partials/summon.html",
        {
            "me": _me_dict(account),
            "recent": recent,
            "pity_current": pity_current,
            "pity_cap": PITY_CAP,
            "pulls_to_pity": pulls_to_pity,
            "starter_product": starter_product,
            "starter_eligible": starter_eligible,
            "starter_expires_at": starter_expires_at,
            "has_quick_summon": has_quick_summon,
        },
    )


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
    # Group by template_code so duplicates collapse into a single card with
    # count badge. For the detail overlay, retain the strongest instance's id
    # so click-through lands on the highest-power copy by default.
    from collections import defaultdict as _dd
    groups: dict[str, list[dict]] = _dd(list)
    for r in rows:
        groups[r["code"]].append(r)
    grouped = []
    for code, instances in groups.items():
        best = max(instances, key=lambda x: x["power"])
        grouped.append({
            **best,
            "dupe_count": len(instances),
            "instance_ids": [i["id"] for i in instances],
        })
    grouped.sort(key=lambda x: x["power"], reverse=True)
    # Bust thumbnail path — resolved at render; fallback chain is in the template.
    import os as _os
    bust_dir = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
        "static", "heroes", "busts",
    )
    has_bust = set()
    try:
        has_bust = {f.rsplit(".", 1)[0] for f in _os.listdir(bust_dir) if f.endswith(".png")}
    except FileNotFoundError:
        pass
    card_dir = _os.path.join(
        _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))),
        "static", "heroes", "cards",
    )
    has_card = set()
    try:
        has_card = {f.rsplit(".", 1)[0] for f in _os.listdir(card_dir) if f.endswith(".png")}
    except FileNotFoundError:
        pass
    for g in grouped:
        g["has_bust"] = g["code"] in has_bust
        g["has_card"] = g["code"] in has_card
    # Phase 2.4 — equipped cosmetic frame, if any. Empty string means
    # vanilla rarity-colored borders. Frame codes map 1:1 to CSS classes
    # in the partial: `frame-frame_neon_cubicle` etc.
    active_frame = (account.active_cosmetic_frame or "").strip()
    # QoL: roster_sort_advanced unlocks extra sort/filter chips.
    import json as _json_ru
    try:
        _qol = _json_ru.loads(account.qol_unlocks_json or "{}")
        has_advanced_sort = isinstance(_qol, dict) and "roster_sort_advanced" in _qol
    except _json_ru.JSONDecodeError:
        has_advanced_sort = False
    return templates.TemplateResponse(
        request, "partials/roster.html",
        {
            "heroes": grouped, "total": len(rows),
            "active_frame": active_frame,
            "has_advanced_sort": has_advanced_sort,
        },
    )


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
    # Phase 2 follow-up (bug #7): summary stats + claimable count so the
    # tab leads with what's actionable instead of starting with a list.
    completed_unclaimed = sum(1 for r in rows if r["status"] == "COMPLETE")
    in_progress = sum(1 for r in rows if r["status"] == "ACTIVE")
    total_claimable_coins = sum(r["reward_coins"] for r in rows if r["status"] == "COMPLETE")
    total_claimable_gems = sum(r["reward_gems"] for r in rows if r["status"] == "COMPLETE")
    total_claimable_shards = sum(r["reward_shards"] for r in rows if r["status"] == "COMPLETE")
    # Daily-bonus claim status — same surface as /me but cheaper to check
    # here since we already have the account.
    from app.daily_bonus import can_claim as _can_claim, preview_next_streak as _peek
    can_claim_bonus = _can_claim(account)
    next_streak = _peek(account)
    return templates.TemplateResponse(
        request, "partials/daily.html",
        {
            "quests": rows,
            "completed_unclaimed": completed_unclaimed,
            "in_progress": in_progress,
            "total_claimable": {
                "coins": total_claimable_coins,
                "gems": total_claimable_gems,
                "shards": total_claimable_shards,
            },
            "can_claim_bonus": can_claim_bonus,
            "next_streak": next_streak,
            "account_energy": account.energy_stored,
            "account_energy_cap": settings.energy_cap,
            "account_gems": account.gems,
            "account_shards": account.shards,
        },
    )


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

    # Shard exchange status for the in-game gems → shards exchange UI block.
    today_key = utcnow().strftime("%Y-%m-%d")
    sx_used = (account.shard_exchanges_today_count
               if account.shard_exchanges_today_key == today_key else 0)
    shard_exchange = {
        "gems_per_batch": settings.shard_exchange_gems_per_batch,
        "shards_per_batch": settings.shard_exchange_shards_per_batch,
        "max_per_day": settings.shard_exchange_max_per_day,
        "used_today": sx_used,
        "remaining_today": max(0, settings.shard_exchange_max_per_day - sx_used),
    }

    return templates.TemplateResponse(
        request, "partials/shop.html",
        {
            "me": _me_dict(account),
            "products": products, "starter": starter, "history": history,
            "shard_exchange": shard_exchange,
        },
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
