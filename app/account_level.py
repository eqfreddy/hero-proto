"""Account-level progression: XP grants, level-up rewards, story chapter
unlocks. Story catalog (chapters + cutscene beats) lives at the bottom of
the file, content-as-code.

Curve: triangular — level N→N+1 needs N×100 XP. Level 50 is the alignment
fork (Phase 3); cap is 100. Battle WIN = 12 XP, summon pull = 4 XP, raid
attack = 8 XP, daily-bonus claim = 25 XP. Tuned so a casual session of
~10 min puts you ~1 level forward in the early game.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy.orm import Session

from app.models import Account


# --- XP curve --------------------------------------------------------------


XP_PER_BATTLE_WIN = 12
XP_PER_SUMMON_PULL = 4
XP_PER_RAID_ATTACK = 8
XP_PER_DAILY_BONUS = 25
XP_PER_FIRST_CLEAR = 30  # bonus on first clear of any stage

ACCOUNT_LEVEL_CAP = 100


def xp_to_next(level: int) -> int:
    """XP needed to go from `level` → `level + 1`. Triangular curve."""
    return max(1, int(level)) * 100


# --- Level-up rewards -------------------------------------------------------
#
# Most levels grant a small currency bump; round-number levels grant a free
# summon credit. Level 25, 50, 75, 100 are bigger milestones.

def reward_for_level(new_level: int) -> dict:
    """Reward dict for hitting `new_level`. Same shape as shop contents."""
    if new_level == 50:
        # The alignment fork. Big payout to mark the moment.
        return {"gems": 500, "shards": 100, "access_cards": 5, "free_summon_credits": 5}
    if new_level == 100:
        return {"gems": 2000, "shards": 500, "access_cards": 25, "free_summon_credits": 20}
    if new_level % 25 == 0:
        return {"gems": 200, "shards": 50, "free_summon_credits": 2}
    if new_level % 10 == 0:
        return {"gems": 100, "shards": 20, "free_summon_credits": 1}
    if new_level % 5 == 0:
        return {"gems": 50, "shards": 10}
    return {"gems": 25, "coins": 100}


_GRANTABLE = ("gems", "shards", "coins", "access_cards", "free_summon_credits")


def _apply_reward(account: Account, reward: dict) -> dict:
    granted: dict = {}
    for kind in _GRANTABLE:
        amount = int(reward.get(kind, 0) or 0)
        if amount <= 0:
            continue
        setattr(account, kind, (getattr(account, kind) or 0) + amount)
        granted[kind] = amount
    return granted


def grant_xp(db: Session, account: Account, amount: int) -> list[dict]:
    """Add XP and roll any level-ups. Returns a list of {level, granted}
    dicts for each level gained — usually empty or 1 entry, occasionally
    multiple if a big single grant pushes through several thresholds.
    """
    if amount <= 0 or (account.account_level or 1) >= ACCOUNT_LEVEL_CAP:
        return []
    account.account_xp = int(account.account_xp or 0) + int(amount)

    levelups: list[dict] = []
    while (account.account_level or 1) < ACCOUNT_LEVEL_CAP:
        need = xp_to_next(account.account_level)
        if account.account_xp < need:
            break
        account.account_xp -= need
        account.account_level += 1
        granted = _apply_reward(account, reward_for_level(account.account_level))
        levelups.append({"level": account.account_level, "granted": granted})
        # Drop a notification so the bell fires.
        from app.notifications import notify as _notify
        bits = [f"+{v} {k.replace('_', ' ')}" for k, v in granted.items() if isinstance(v, int) and v > 0]
        _notify(
            db, account,
            kind="account_level",
            title=f"Level up! Account level {account.account_level}",
            body="Reward: " + ", ".join(bits) if bits else "",
            link="/app/partials/me",
            icon="✨",
        )
    if (account.account_level or 1) >= ACCOUNT_LEVEL_CAP:
        # Cap the XP bar at 0 so the UI doesn't show silly overflow.
        account.account_xp = 0
    return levelups


# --- Story catalog ---------------------------------------------------------


@dataclass(frozen=True)
class Cutscene:
    """One text-driven beat between waves or at chapter start/end."""
    speaker: str        # "Narrator" / hero name / "The Corp"
    text: str
    icon: str = "💬"


@dataclass(frozen=True)
class StoryStage:
    code: str
    name: str
    cutscene_intro: Cutscene | None
    cutscene_outro: Cutscene | None


@dataclass(frozen=True)
class Chapter:
    code: str
    title: str
    blurb: str
    unlock_level: int          # account level required to start
    icon: str
    stages: list[StoryStage]


# Three opening chapters. Each has 5 stages; cutscenes use existing seeded
# stages where possible (no new combat content for now — Phase 3 expands
# the actual battle data). Chapter-level gating is by account level.

STORY_CHAPTERS: list[Chapter] = [
    Chapter(
        code="onboarding_arc",
        title="Chapter 1 — Onboarding",
        blurb="The first 90 days. Welcome aboard. The wifi password is at the bottom of the desk drawer (somewhere).",
        unlock_level=1,
        icon="📋",
        stages=[
            StoryStage(
                code="tutorial_first_ticket",
                name="First Ticket",
                cutscene_intro=Cutscene(
                    speaker="Narrator",
                    text="Day one. You have a chair. You have a laptop. You have eighteen tabs open in Confluence. The phone rings. You pick up.",
                    icon="📞",
                ),
                cutscene_outro=Cutscene(
                    speaker="Narrator",
                    text="The Ticket Gremlin retreats. Your monitor stops blinking. For a moment, nothing is on fire.",
                ),
            ),
            StoryStage(
                code="onboarding_day",
                name="Onboarding Day",
                cutscene_intro=Cutscene(
                    speaker="The Sysadmin",
                    text="You're new. I'm not. Don't touch the production servers. Don't ask why we still run Windows Server 2008 R2. The answer is sad.",
                    icon="⚙️",
                ),
                cutscene_outro=None,
            ),
            StoryStage(
                code="first_outage",
                name="First Outage",
                cutscene_intro=Cutscene(
                    speaker="Narrator",
                    text="A Slack notification. Then ten more. Then the email. Then the bridge call. The phrase 'incident commander' enters your vocabulary today.",
                    icon="🚨",
                ),
                cutscene_outro=Cutscene(
                    speaker="The Post-Mortem",
                    text="The 'five whys' will be ready by Wednesday. The blameless culture will hold for approximately 72 hours.",
                ),
            ),
            StoryStage(
                code="quarterly_audit",
                name="Quarterly Audit",
                cutscene_intro=Cutscene(
                    speaker="Compliance Officer",
                    text="I have flagged seventeen items on this checklist. Eleven of them are about password expiration policies. The other six are also about password expiration policies.",
                    icon="📋",
                ),
                cutscene_outro=Cutscene(
                    speaker="Compliance Officer",
                    text="Acceptable. For now.",
                ),
            ),
            StoryStage(
                code="legacy_server_room",
                name="Legacy Server Room",
                cutscene_intro=Cutscene(
                    speaker="Overnight Janitor",
                    text="The hum behind that door has been there since '03. It used to be louder. Don't ask what's in there. The tape library remembers things you don't want it to.",
                    icon="🗄️",
                ),
                cutscene_outro=Cutscene(
                    speaker="Narrator",
                    text="Chapter 1 closes. You've passed orientation. Most of your hairline made it. The Corp logs another successful onboarding. You haven't seen the Corp yet — but it's already seen you.",
                ),
            ),
        ],
    ),

    Chapter(
        code="middle_management_arc",
        title="Chapter 2 — Middle Management",
        blurb="You've been promoted. They added 'Senior' to your title and a fourth standing meeting to your week.",
        unlock_level=10,
        icon="📈",
        stages=[
            StoryStage(
                code="ceos_one_on_one",
                name="The CEO's 1:1",
                cutscene_intro=Cutscene(
                    speaker="The Consultant",
                    text="The CEO has a unique vision for digital transformation. I have prepared a 47-slide deliverables deck. We will synergize. You will say 'absolutely' a lot.",
                    icon="💼",
                ),
                cutscene_outro=Cutscene(
                    speaker="The CEO",
                    text="Great touchbase. Let's circle back next quarter.",
                ),
            ),
            StoryStage(
                code="reorg_announcement",
                name="The Reorg Announcement",
                cutscene_intro=Cutscene(
                    speaker="VP of Vibes",
                    text="Big news. We're realigning the org around outcomes, not tickets. Your manager is now your manager's manager. You will report to a tool. The tool reports to the cloud.",
                    icon="🎺",
                ),
                cutscene_outro=Cutscene(
                    speaker="Narrator",
                    text="Three managers later, your work is unchanged. The org chart is now hyperbolic.",
                ),
            ),
            StoryStage(
                code="migration_weekend",
                name="Migration Weekend",
                cutscene_intro=Cutscene(
                    speaker="Build Engineer",
                    text="Friday at 6 PM. Coffee is black. Coffee is plentiful. The runbook is two thousand lines. We start in five.",
                    icon="🛠️",
                ),
                cutscene_outro=Cutscene(
                    speaker="Build Engineer",
                    text="Sunday at 2 AM. Green build. The new system runs. The old system runs. We can't turn off the old system. That's a Q3 problem.",
                ),
            ),
            StoryStage(
                code="pager_storm",
                name="The Pager Storm",
                cutscene_intro=Cutscene(
                    speaker="Midnight Pager",
                    text="P1. P1. P2. P1. P0. The cascade has begun. I'd like to formally lodge a complaint about being awake.",
                    icon="📟",
                ),
                cutscene_outro=Cutscene(
                    speaker="The Post-Mortem",
                    text="Root cause: a single semicolon. The semicolon will not be punished. The semicolon was just doing its job.",
                ),
            ),
            StoryStage(
                code="hostile_acquisition",
                name="Hostile Acquisition",
                cutscene_intro=Cutscene(
                    speaker="The Founder",
                    text="I'm not here to manage. I'm here to acquire. The legal team has been very busy. They look tired. They are tired.",
                    icon="🦈",
                ),
                cutscene_outro=Cutscene(
                    speaker="Narrator",
                    text="Chapter 2 closes. The Corp is no longer abstract — it has shareholders, an org chart, and a seven-figure consulting bill. You've started recognizing names.",
                ),
            ),
        ],
    ),

    Chapter(
        code="exec_floor_arc",
        title="Chapter 3 — The Executive Floor",
        blurb="The wifi up here is faster. The coffee is single-origin. Nobody knows how SSH works.",
        unlock_level=20,
        icon="🏢",
        stages=[
            StoryStage(
                code="the_singularity",
                name="The Singularity",
                cutscene_intro=Cutscene(
                    speaker="Narrator",
                    text="Someone in marketing just discovered LLMs. Within 72 hours, every internal tool has 'AI-powered' in its name. Three of them just call ChatGPT. The fourth is a shell script.",
                    icon="🤖",
                ),
                cutscene_outro=None,
            ),
            StoryStage(
                code="tape_room_breach",
                name="Tape Room Breach",
                cutscene_intro=Cutscene(
                    speaker="Tape Library Ghost",
                    text="They forgot us. They moved to the cloud. They told everyone the migration was complete. They were wrong. We remember everything.",
                    icon="👻",
                ),
                cutscene_outro=Cutscene(
                    speaker="Retired Mainframe Guru",
                    text="Some debts cannot be migrated.",
                ),
            ),
            StoryStage(
                code="boardroom_coup",
                name="The Boardroom Coup",
                cutscene_intro=Cutscene(
                    speaker="The Board Member",
                    text="The motion to sunset the engineering org has been tabled. It will be untabled in Q4. We have decided to outsource the deciding.",
                    icon="🏛️",
                ),
                cutscene_outro=None,
            ),
            StoryStage(
                code="prod_is_down",
                name="Prod Is Down",
                cutscene_intro=Cutscene(
                    speaker="Chaos Monkey",
                    text="It's not me this time. I have an alibi. Several alibis. None of them check out, but several.",
                    icon="🐒",
                ),
                cutscene_outro=Cutscene(
                    speaker="On-Call Warrior",
                    text="It was the certificate. It is always the certificate. We've been here before. We will be here again.",
                ),
            ),
            StoryStage(
                code="the_unauthorized_tool",
                name="The Unauthorized Tool",
                cutscene_intro=Cutscene(
                    speaker="Shadow IT Operator",
                    text="It's not unauthorized. It's pre-authorized. By me. To myself. We're calling it 'cloud-native' because nobody has reviewed it.",
                    icon="🕶️",
                ),
                cutscene_outro=Cutscene(
                    speaker="Narrator",
                    text="Chapter 3 closes. You're approaching the executive floor. The view is incredible. The smell of new carpet is overpowering. The Corp has noticed you. It has plans.",
                ),
            ),
        ],
    ),
]


def chapter_by_code(code: str) -> Chapter | None:
    for c in STORY_CHAPTERS:
        if c.code == code:
            return c
    return None


def stage_belongs_to_chapter(stage_code: str) -> Chapter | None:
    for c in STORY_CHAPTERS:
        if any(s.code == stage_code for s in c.stages):
            return c
    return None


# --- Per-account story state (cutscene seen-flags) -------------------------


def _state(account: Account) -> dict:
    try:
        data = json.loads(account.story_state_json or "{}")
        return data if isinstance(data, dict) else {}
    except json.JSONDecodeError:
        return {}


def _save(account: Account, data: dict) -> None:
    account.story_state_json = json.dumps(data, separators=(",", ":"))


def has_seen(account: Account, key: str) -> bool:
    return key in _state(account)


def mark_seen(account: Account, key: str) -> None:
    """Record that the player has seen a cutscene beat (e.g. 'onboarding_arc:0:intro')."""
    from app.models import utcnow
    s = _state(account)
    s[key] = utcnow().isoformat()
    _save(account, s)


# --- Chapter availability helper -------------------------------------------


# --- Chapter-end rewards ---------------------------------------------------
#
# When a player clears the last stage of a chapter, grant a one-time bundle.
# Idempotency: tracked on story_state_json under a `chapter_rewards_claimed`
# key. Caller (battles router) calls maybe_grant_chapter_reward(...) on every
# win — it no-ops unless the just-cleared stage was the last in its chapter.

CHAPTER_END_REWARDS: dict[str, dict] = {
    "onboarding_arc": {
        "gems": 200, "shards": 50, "free_summon_credits": 2,
    },
    "middle_management_arc": {
        "gems": 400, "shards": 100, "access_cards": 3, "free_summon_credits": 3,
    },
    "exec_floor_arc": {
        "gems": 800, "shards": 200, "access_cards": 5, "free_summon_credits": 5,
    },
}


def _chapter_rewards_claimed(account: Account) -> set[str]:
    """Returns the set of chapter codes the player has already claimed
    end-rewards for. Stored as a list under story_state_json's
    'chapter_rewards_claimed' key."""
    s = _state(account)
    raw = s.get("chapter_rewards_claimed") or []
    if not isinstance(raw, list):
        return set()
    return {str(c) for c in raw}


def maybe_grant_chapter_reward(
    db: Session, account: Account, just_cleared_stage_code: str,
) -> dict | None:
    """If `just_cleared_stage_code` was the LAST stage in some chapter and
    every stage in that chapter is now cleared, grant the chapter-end
    reward bundle. Idempotent: returns None on a re-trigger.

    Returns: {chapter_code, chapter_title, granted: {gems, shards, ...}}
    or None when nothing was granted.
    """
    chapter = stage_belongs_to_chapter(just_cleared_stage_code)
    if chapter is None:
        return None
    # Last-stage gate: only fire when the just-cleared stage is the chapter's
    # final stage. Cheap fast-path to avoid recomputing on every win.
    if chapter.stages[-1].code != just_cleared_stage_code:
        return None

    claimed = _chapter_rewards_claimed(account)
    if chapter.code in claimed:
        return None

    # Every stage cleared? (Players might clear a chapter out-of-order in
    # principle, though sequential gating in chapter_status_for_account
    # discourages it. Belt-and-suspenders check.)
    try:
        cleared_arr = json.loads(account.stages_cleared_json or "[]")
        cleared = {str(c) for c in cleared_arr} if isinstance(cleared_arr, list) else set()
    except json.JSONDecodeError:
        cleared = set()
    if not all(s.code in cleared for s in chapter.stages):
        return None

    reward = CHAPTER_END_REWARDS.get(chapter.code, {})
    granted = _apply_reward(account, reward)

    # Persist the claim flag.
    s = _state(account)
    arr = s.get("chapter_rewards_claimed") or []
    if not isinstance(arr, list):
        arr = []
    arr.append(chapter.code)
    s["chapter_rewards_claimed"] = arr
    _save(account, s)

    # Bell notification — chapter completion is a moment players should
    # see in the UI.
    from app.notifications import notify as _notify
    bits = [f"+{v} {k.replace('_', ' ')}" for k, v in granted.items() if isinstance(v, int) and v > 0]
    _notify(
        db, account,
        kind="chapter_complete",
        title=f"{chapter.title} — complete",
        body=("Reward: " + ", ".join(bits)) if bits else "Story chapter complete.",
        link="/app/partials/story",
        icon=chapter.icon or "📖",
    )

    return {
        "chapter_code": chapter.code,
        "chapter_title": chapter.title,
        "granted": granted,
    }


def chapter_status_for_account(account: Account) -> list[dict]:
    """Returns a list of chapters with locked/unlocked + per-stage cleared
    flags computed from account.account_level + stages_cleared_json. Used by
    the UI to render the story tab."""
    cleared = set(json.loads(account.stages_cleared_json or "[]") if isinstance(account.stages_cleared_json, str) else [])
    out = []
    level = int(account.account_level or 1)
    for ch in STORY_CHAPTERS:
        unlocked = level >= ch.unlock_level
        stages = []
        prev_cleared = True  # gate sequentially within a chapter
        for s in ch.stages:
            stage_unlocked = unlocked and prev_cleared
            stages.append({
                "code": s.code,
                "name": s.name,
                "unlocked": stage_unlocked,
                "cleared": s.code in cleared,
                "intro": {
                    "speaker": s.cutscene_intro.speaker, "text": s.cutscene_intro.text,
                    "icon": s.cutscene_intro.icon,
                } if s.cutscene_intro else None,
                "outro": {
                    "speaker": s.cutscene_outro.speaker, "text": s.cutscene_outro.text,
                    "icon": s.cutscene_outro.icon,
                } if s.cutscene_outro else None,
            })
            prev_cleared = s.code in cleared
        completed = all(s["cleared"] for s in stages)
        out.append({
            "code": ch.code,
            "title": ch.title,
            "blurb": ch.blurb,
            "icon": ch.icon,
            "unlock_level": ch.unlock_level,
            "unlocked": unlocked,
            "stages": stages,
            "completion_pct": int(round(100 * sum(1 for s in stages if s["cleared"]) / max(1, len(stages)))),
            "completed": completed,
            "reward_claimed": ch.code in _chapter_rewards_claimed(account),
            "end_reward": CHAPTER_END_REWARDS.get(ch.code, {}),
        })
    return out
