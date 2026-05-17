# Battle redesign roadmap — 2026-05-17

## Why

Combat passes tests and animates correctly, but feels thin in the hand: the
player's only verb is "click target." Resolver supports skills/limits/statuses
internally; the surface doesn't expose them. Five phases close the gap.

## Phase A — Action choice  (foundation, ~2 days)

The keystone. Without this, every visual polish is lipstick.

- **Backend**
  - `InteractiveActIn.action_type: Literal['attack', 'skill', 'limit', 'defend'] = 'attack'`
  - Branch in `simulate_interactive`:
    - `attack` — existing path
    - `skill` — spend 30 mana; signature move keyed by `(archetype, role)`. v1 = role default (ATK=AOE strike, DEF=shield-all-allies, SUP=heal lowest-HP ally)
    - `limit` — spend full Limit gauge; 2× damage + new `LIMIT_BREAK` event
    - `defend` — queue `defending` state 1 turn: −50% incoming damage, +10 mana
  - Mana model: units start 50, regen 10/turn, cap 100. Cleanly maps onto existing `MANA_EMPTY` event.
  - New combat events: `SKILL_USED`, `LIMIT_BREAK`, `DEFEND`
- **Frontend**
  - HUD bottom bar per active actor: `[Attack] [Skill ✦ 30] [Limit ▲ N/M] [Defend]`
  - Disabled state when resource short
  - Existing target picker still drives `attack`; new buttons set `action_type` before `onAct`
- **Tests** — `test_battle_actions.py`: each action type respected, resources deducted, defend reduces next incoming hit by 50%

**Confidence:** HIGH — narrow API extension, resolver internals already handle most state.

## Phase B — Visual juice  (~2 days)

- Floating damage numbers in 3D space (HTML overlay layer or SpriteText). Fade up 1.2s. Crits red + larger; heals green.
- Status icon strip beneath HP bar: poison drop, burn flame, shield star, buff up-arrow. Reads 8 existing statuses.
- Camera shake on CRIT only (small, 120ms).
- Action-cam zoom on `LIMIT_BREAK` events (1.2s pause-and-frame).
- Per-archetype hit VFX: knight sparks, mage purple flash, ranger arrow trail, rogue afterimage. Existing `flashWhite` is the hook point.

**Confidence:** HIGH — purely additive, no resolver changes.

## Phase C — Character identity  (~3 days)

- Each of 33 templates gets ONE quip line, fired once per battle on first action.
  Examples: SysAdmin "Compiling…", The Whistleblower "git blame!", Ticket Gremlin "ack!".
- Top ~15 templates override archetype-default signature move with a named one:
  - SysAdmin → "Rollback" (cleanse self + 1 ally)
  - The Whistleblower → "Disclosure" (debuff all enemies −20% DEF)
  - Ticket Gremlin → "Backlog Bomb" (AOE physical)
  - Etc.
- Hero-detail page surfaces signature move + flavor.
- Battle log + new `QUIP` event renders quip inline.

**Confidence:** MEDIUM — design work per template. Best done in batches; could ship 6 heroes/day.

## Phase D — Team-builder synergy preview  (~1 day)

- Setup screen tag row above team slots:
  - `RESISTANCE × 3 → +10% ATK`
  - `4-MELEE TEAM → no ranged synergy`
- Live recompute as slots fill. Reuses `team_faction_synergy()` logic (move to a `synergy_preview()` helper that doesn't mutate stats).
- Power-vs-rec delta tag already exists — slot synergy chips beside it.

**Confidence:** HIGH — pure UI, backend logic already there.

## Phase E — Turn-order timeline  (~1 day)

- Top-of-screen ribbon, 6 portrait chips showing next 6 turns.
- Server computes turn order from SPD + status; expose in `InteractiveStateOut.turn_order[: 6]`.
- Player sees consequence chains: "Mage acts after Boss → I should taunt."

**Confidence:** MEDIUM — depends on resolver exposing peek-ahead; doable but touches the loop.

---

## Total: ~9-10 focused days

Order: A → B → D → E → C  (foundation, then juice, then synergy, then timeline, then character flavor in batches).

## Out of scope (intentional)

- Wave-swap mid-battle (single-wave is current contract)
- Weapon mesh attachment (TODO #210 — separate ~2hr task)
- 2D legacy replay animation choreography (path is being phased out; 3D is canonical)
- Element system (currently no elements; adding one is a bigger design swing)

## Risk

- **API extension breaks raids.** Raid interactive shares the `act` endpoint. Phase A must keep `action_type` defaulted so raids continue working without UI change.
- **Skill design imbalance.** v1 ships role-defaults; balance pass needed after live play. Acceptable for an alpha.
- **Mana introduction.** New resource; existing tuning assumes basic attacks only. Phase A acceptance test: 5-stage walkthrough shows no regression in win rate vs. current.
