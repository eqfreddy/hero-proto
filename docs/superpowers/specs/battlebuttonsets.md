# battlebuttonsets — System Integrity + Crash + "Deleted" + Burnout

**Date:** 2026-05-28
**Status:** Brainstorm output (design draft, NOT yet approved → no plan yet).
**Origin:** Competitive teardown headline bet (`docs/COMPETITIVE_TEARDOWN_2026-05.md`, `futurelist.md`).
**Companion cutoff file:** `keldev-finish-brain.md` (open questions awaiting Kel's answers).

This is the design for hero-proto's signature combat layer + the battle action-button
set that drives it. It reuses the existing Faction axis, the limit gauge, mana, the
≤5% hail-mary, and the already-shipped `action_type` flow (attack/skill/limit/defend).

---

## 1. The three pillars

### A. System Integrity (weakness-break)
Every enemy carries an **Integrity bar** (a toughness bar) layered over its HP.

- **Weakness axis = Faction.** Each enemy declares `weak_to` = one or
  more of the 5 IT factions (HELPDESK / DEVOPS / EXECUTIVE / ROGUE_IT / LEGACY).
  - Some bosses have **no weakness** or **multiple weaknesses** (boss-design texture).
  - **No universal-exploit heroes** — pure faction-matching (decided 2026-05-28).
- **Depletion:** a weakness-matching hit drains Integrity in full; an off-type hit drains
  a reduced fraction (**25%**). That 25% is the **anti-wall valve**: a player with no
  on-faction hero can still Crash, just ~4x slower — keep it > 0 so pure-faction never
  hard-walls a thin roster.
- **Crash (zeroing Integrity):** the enemy is **Crashed** — it loses its next turn (STUN),
  takes increased damage for the vulnerability window, **and** takes a per-faction flavored
  debuff (decided 2026-05-28, **flavored from the start**):
    HELPDESK→STUN (extend), LEGACY→BURN, DEVOPS→DEF_DOWN, ROGUE_IT→POISON, EXECUTIVE→HEAL_BLOCK.
  All five reuse existing `StatusEffectKind`s.
- Integrity refills after the Crash window ends → re-crash is possible.
- **Scope:** every enemy has a bar. Trash mobs = small bars (crash fast). Elites/bosses =
  large bars, bosses per-phase.

### B. "Deleted" finisher (the execute)
Our deadpan answer to a Mortal Kombat fatality. No gore — you send the enemy to the bin.

- **Trigger (v1 = mode 1, others are swappable placeholders):**
  - **Mode 1 (default):** enemy is Crashed **AND** below the execute HP threshold (~25%).
  - *Mode 2 (placeholder):* bin pops on **any** Crash; drag deletes trash outright,
    chunks (caps on) bosses.
  - *Mode 3 (placeholder):* recycle-bin ceremony reserved for **Crashed elites/bosses** only.
  - Trigger is a config enum (`DELETE_TRIGGER_MODE`) so we flip it without a rewrite.
- **The input — drag-to-recycle-bin:** a recycle-bin / trash icon pops up at a
  **randomized screen position** each time (so the thumb can't autopilot it). Flick/drag
  the Crashed enemy into the bin → `DELETED` callout + finisher anim.
- **Flourish, not a gate (hard rule):** the Crash already earned the kill. Nailing the
  drag grants **all of: Burnout shed + bonus loot/mats (small, economy-capped) + a "DELETED"
  style/killcount stat + faster anim** (decided 2026-05-28); a miss or timeout **still
  Deletes**, just plain (no bonus). The finisher never blocks progress and never fails the kill.
- **Timing — inside the turn clock (decided 2026-05-28):** the drag has a short window
  within the actor's turn; if not completed before the window / the server per-turn timer,
  it auto-resolves to a plain delete. No separate "finisher pending" server state needed.
- **Auto-battle / sweep:** auto-resolve at base success — no player input required. Keeps
  the QoL unlock honest and the mechanic accessible (psychology / SDT design rule #1).
- **Burnout-dump variant:** at high Burnout a hero can Delete a Crashed enemy **regardless
  of HP** (bosses: capped phase-chunk, no one-shot). See pillar C.

### C. Burnout meter (double-edged tension)
Per-hero, **battle-scoped** (resets each fight — does not punish progression). Distinct
from limit (earned offense, want it full) and mana (spell resource): Burnout is something
you want **low-to-mid**, pushed high only for a clutch payoff.

- **Builds from:** taking hits (+small), using a Skill (+small), using a Limit (+large).
- **High Burnout (≥ high threshold):** effectiveness drops (reduced damage / accuracy)
  **BUT** unlocks the desperation payoff:
  - powers up the existing **≤5% HP hail-mary**, and
  - enables the **Burnout-dump "Deleted"** (execute a Crashed enemy ignoring HP threshold).
- **Low / managed Burnout (≤ low threshold):** small **crit bonus** (fresh & sharp).
- **Shedding:** the **Defend** action sheds Burnout (gives Defend a real job beyond the
  existing damage-halve), and SUP heroes can clear it. (Defend-balance TBD.)

---

## 2. The battle button set (action bar)

The HUD action bar extends the shipped set. Each button maps to an `action_type` in
`app/combat.py::_act` (which already accepts attack/skill/limit/defend).

| Button | State / gating | Effect |
|---|---|---|
| **Attack** | always | basic hit; weakness-match drains Integrity |
| **Skill** | mana ready | special; +small Burnout; weakness-match drains Integrity harder |
| **Limit** | gauge full | signature move; +large Burnout |
| **Defend** | always | halve incoming (existing DEFENDING status) **+ sheds Burnout** |
| **Delete** | contextual — lights only when a valid Deleted target exists (Crashed + threshold per mode) | triggers the recycle-bin drag finisher; accessible/auto fallback path |

- **Delete** is the accessible button equivalent of the drag gesture: tapping it performs
  the finisher at base success; the **drag-to-bin** is the optional flourish layered on top
  for the bonus. Auto-battle uses the button path silently.
- Contextual visibility keeps the bar clean — Delete is hidden until earned.

---

## 3. Where it touches the code (orientation, not a plan)

- `app/combat.py` — **pure resolver.** Add: `integrity`/`integrity_max` + `weak_to` on the
  enemy `CombatUnit`; `burnout` on every unit; Crash state (reuse STUN + a vulnerability
  flag); Integrity depletion in the damage path; Burnout accrual/threshold hooks in `_act`;
  Delete resolution. New `StatusEffectKind` only if the vulnerability can't ride DEF_DOWN.
- `app/models.py` — enemy templates need `weak_to` (+ universal-exploit hero flag). Likely a
  column on `HeroTemplate` / stage-enemy seed; Integrity sizing derivable from rarity/role.
- `app/interactive.py` — surface Integrity / Burnout / Crash / valid-Delete in the state-out
  so the HUD can render bars + light the Delete button; accept the Delete action + finisher
  result. Finisher runs **inside the turn clock**: short drag window, auto-resolve to plain
  delete on timeout — no separate "finisher pending" server state.
- `frontend` — `BattleHUD.tsx` action bar (+Delete), Integrity bar + Burnout meter per unit,
  Crash VFX, the randomized recycle-bin drag overlay + `DELETED` callout; Battle3D crash/glitch
  reaction.
- **Rollout order:** interactive battles → auto/sweep auto-resolve → arena/raids inherit.

---

## 4. Why this is the bet

- Weakness-break is the single most-judged combat axis in 2026 (both store teardowns).
- It **rescues the already-shipped action choice** — Attack vs Skill vs Limit is currently
  cosmetic; Integrity + Burnout + Delete give every button weight.
- It closes the #1 table-stakes gap (type advantage) and delivers the headline differentiator
  in **one workstream**, mostly as a **pure-function** change reusing existing systems.
- "Deleted" + the randomized drag finisher answers the genre's "auto-battle is passive /
  it gets boring" complaint with a light, optional, on-theme arcade input.

---

## 5. Decisions locked in this brainstorm

1. Weakness axis = **Faction**. Some no/multi-weakness bosses; **no universal-exploit heroes** (pure faction). Off-type hits still chip Integrity 25% (anti-wall).
2. Crash = **stun + vulnerability + per-faction flavored debuff, flavored from the start** (HELPDESK→STUN, LEGACY→BURN, DEVOPS→DEF_DOWN, ROGUE_IT→POISON, EXECUTIVE→HEAL_BLOCK).
3. **"Deleted"** finisher exists (deadpan execute, not gore).
4. Finisher input = **drag into a randomly-positioned recycle bin**; flourish not gate; auto-resolves under auto-battle.
5. Delete trigger v1 = **Crashed + low HP** (mode 1); modes 2/3 are config placeholders.
6. Burnout = **double-edged tension meter**, per-hero, battle-scoped; Defend sheds it; high unlocks desperation (hail-mary + HP-ignoring Delete); low = crit bonus.
7. Rollout = **interactive battles first**.
8. Nailing the drag grants **Burnout shed + bonus loot/mats (capped) + "DELETED" style stat + faster anim**; miss/auto = plain delete.
9. Finisher runs **inside the turn clock** with a short drag window; timeout → plain delete. No "finisher pending" server state.

## 6. Starting values (all playtest-tunable — defaults, not gospel)

| Knob | Starting value |
|---|---|
| Off-type Integrity depletion | 25% of a weakness hit |
| Integrity bar size | trash ≈ 1-2 weakness hits · elite ≈ 3-4 · boss ≈ 5-6 per phase |
| Crash: turns skipped | 1 (STUN) |
| Crash: vulnerability | +30% damage taken, 2 turns |
| Delete execute threshold | ≤25% HP (mode 1) |
| Burnout build | +5 per hit taken · +10 per Skill · +25 per Limit (0-100 scale) |
| Burnout HIGH (penalty + desperation) | ≥75 → -15% damage/accuracy, unlocks hail-mary boost + HP-ignoring Delete |
| Burnout LOW (sharp) | ≤25 → +10% crit |
| Defend Burnout shed | -30 |
| Burnout persistence | battle-scoped reset |
| Finisher drag window | ~2-3s inside turn |
| Bin spawn | random within a safe zone (inset from edges, off the action bar) |
| Input parity | touch = drag · desktop = click-drag · Delete button = accessible/auto path |

Remaining creative vetoes (art / VFX / callout treatment) tracked in `keldev-finish-brain.md`.

## 7. Monetization route — p2w-leaning (chosen 2026-05-28)

> **Direction conflict flagged:** this overrides the documented "F2P viable / never direct
> power / PoE2 cosmetic model" guardrail (PRD, CLAUDE.md, memory rule #1). Chosen deliberately
> by the operator. F2p is kept *viable, not equal* — every paid lever has a slower free path.

The mechanic is p2w **by construction**: power → faster crashes → more Deletes → more
(multiplier-boosted) loot. On top of that, these decisions are flipped/added to lean p2w:

| Lever | p2w decision |
|---|---|
| **Universal-exploit heroes** | **Exist**, gated behind premium / limited gacha (the whale chase). Overrides §5.1 "nobody." |
| **Off-type Integrity chip** | **15%** (down from 25%) — slower off-faction, more pull pressure. Still > 0 (anti-wall). |
| **Crash debuffs** | Flavored + **premium heroes get stronger crash debuffs**. |
| **Deleted bonus loot** | All four bonuses + **VIP / monthly-card / event multipliers** on the loot roll + premium currency in the Deleted drop table. |
| **Burnout** | Add a monetizable mitigation axis: premium **"Composure" gear substat** (reduces build) + **VIP burnout-reduction** + **paid mid-fight burnout-reset consumable**. Defend-shed skill path stays for f2p. |
| **Finisher** | Inside-clock auto-resolve + **paid "auto-perfect finisher"** QoL (always banks the bonus, no input). |

**Added paid hooks (the 100%-p2w stack):**
- Universal-exploit **limited banner** (rotating whale chase).
- **Integrity-break booster** + **burnout-reset** consumables (gems).
- **VIP / monthly multipliers** on Deleted drops.
- **Composure** burnout-reduction gear substat (premium gear pool).
- **Auto-perfect finisher** QoL unlock.
- **Rotating faction-weakness content** → forces owning breakers for all 5 factions (collection/gacha pressure).

**F2p non-clash valves (do NOT remove):**
- Off-type Integrity chip stays > 0 → no hard wall on a thin roster.
- Skill paths (Defend-shed, the drag flourish, base auto-resolve) always pay the **base** reward.
