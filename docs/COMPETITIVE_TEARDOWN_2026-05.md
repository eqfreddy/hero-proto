# Competitive Teardown — Turn-Based / Gacha RPGs vs. hero-proto

**Date:** 2026-05-28
**Method:** Two research passes — Apple App Store (22 titles) + Google Play (20 titles) — cross-referenced against a code-level audit of hero-proto's current systems. Store data is composite/directional (live Sensor Tower + GACHAREVENUE numeric tables were not scrapable; rankings are "what's charting + frequently cited," not a verified numeric order). Sources listed at bottom.

> **Bottom line:** In 2026 the genre's **combat depth** has converged on *weakness-break + speed manipulation + ultimate gauge*. **Monetization fairness** has converged on *visible soft/hard pity + 50/50 carryover + dupe-power + spark/selector*. **Retention** has converged on *daily-competitive-boss + tower + RTA + roguelike + ~6-week LiveOps*. hero-proto already covers most retention/monetization table-stakes; its biggest real gaps are **no type-advantage layer** and **no combat depth verb**.

---

## 1. What hero-proto already has (code-confirmed)

So we don't "add" what exists:

- Soft + hard pity with ramp (`app/gacha.py`) — **visible pity, table-stakes met**
- Sweep / instant-clear of farmed stages (`POST /sweep/{stage_id}`)
- Auto-battle as a QoL unlock (`qol_unlocks_json`)
- Seasonal **Tower of Trials** + leaderboard (`app/routers/tower.py`)
- AFK / idle accrual loop (`app/afk.py`, capped) + Rest XP bank
- Battle pass, monthly card, VIP, friend points + friend-summon banner
- Collections, achievements, guild achievements, milestones, crafting
- Async arena ladder w/ tickets + weekly bracket payouts
- Async guild raids (BOSS_PHASE specials)
- Gear with **main-stat + substats + set bonuses** (`app/gear_logic.py`, `named_gear.py`)
- Dupe → power via **template shards** ascension (no fodder)
- Player action choice (attack / skill / limit / defend) + turn-order ribbon + faction synergy team buff
- Server-authoritative per-turn timer, hail-mary at ≤5% HP

## 2. Confirmed TABLE-STAKES GAPS (cheap, do regardless)

1. **No type-advantage / affinity layer.** Every top title has enemy-vs-hero RPS (HSR 7 elements, Raid Magic/Force/Spirit/Void, Epic Seven, AFK factions, Idle Heroes 6 factions). hero-proto's `team_faction_synergy` is a *same-faction team buff*, **not** an RPS combat axis. Reviewers expect "bring the right type." Missing entirely.
2. **No deterministic-acquisition path** (spark / selector / fusion / targeted banner). Both agents flagged this as the #1 anti-churn fairness pattern of 2026. hero-proto has pity but no "pick your unit after N" and no 50/50-carryover guarantee. Pairs naturally with the existing shard philosophy.
3. **No daily-rotating boss DPS-race + leaderboard** (AFK Journey *Dream Realm*). Both agents independently called this the highest engagement-per-dev-hour feature in the genre. Tower is static floors; this is the missing *daily* competitive hook.
4. **Gear substats roll once** — no enhance / reforge / reroll grind loop, so "farm relics forever" doesn't exist.
5. **(Android-specific) Verify "Fast Rewards" instant-accrual purchase** exists on the AFK loop — Android idle charts live on it.
6. **(Verify) In-battle speed multiplier (2x/4x)** and **skippable multi-pull animation** — Android reviewers torch games that lack these.

---

## 3. THE EXTREME GREAT IDEA

### Weakness-break reskinned as "System Integrity," fused with a per-hero "Burnout" meter — hero-proto's signature mechanic.

**Why this is the move (and not a me-too HSR clone):**

- **Highest-leverage combat addition in the genre.** Both store passes named weakness-break (HSR) the most-copied combat innovation of the era and the thing turn-based games are now judged against.
- **It rescues the action-choice combat already shipped.** Right now Attack vs Skill vs Limit is cosmetic — no reason to pick one. Break gives every action weight overnight.
- **It's a pure-function change.** `app/combat.py` is pure (no DB / IO), and the Faction axis already exists as the "type" data — so the weakness mapping is mostly config, not a migration.
- **The IT theme makes it unique.** Enemies (outages, audits, legacy systems, Boto) get an **Integrity / Uptime bar** only cracked by the right "exploit type" (Network / Database / Security / Hardware / Frontend, mapped onto roles/factions). Zero it → the system **crashes**: bonus damage + its turn is skipped. That's HSR break, but on-brand.
- **The twist nobody else has: a per-hero Burnout meter** (the Limbus Company "sanity" steal, reframed). Heroes accrue Burnout from Limit breaks and taking hits; high Burnout tanks effectiveness but feeds the *already-built* ≤5% HP hail-mary into a desperation payoff; managed Burnout = crit bonus. A self-balancing risk/reward layer that is thematically perfect for an oncall / IT game — a genuine differentiator.

**Net:** one combat sprint converts combat from "spectator with buttons" into a type-puzzle + resource-management loop with a signature identity — reusing Faction + hail-mary + action-choice that already shipped.

### Honorable mentions (next tier)

- **Dream-Realm-style daily damage boss + leaderboard** — cheapest evergreen daily-return hook; pairs with break as the "show off your tech stack" mode.
- **Spark / selector banner** — fastest anti-churn monetization-fairness win.
- **Idle "Fast Rewards" instant-accrual** — Android retention engine; confirm/add to AFK loop.
- **Support-unit borrow from friends** — cheap social hook + soft conversion funnel (lets F2P "try" unowned heroes).

---

## 4. Ranked title lists (directional, not verified numeric)

### Apple App Store (composite)
1. Honkai: Star Rail · 2. Genshin (action, adj.) · 3. Zenless Zone Zero (adj.) · 4. Wuthering Waves (adj.) · 5. AFK Journey · 6. Summoners War: Sky Arena · 7. Epic Seven · 8. Persona 5: The Phantom X · 9. Raid: Shadow Legends · 10. Watcher of Realms · 11. Fate/Grand Order *(EOS March 2026 — reference only)* · 12. Marvel Strike Force · 13. Dragon Ball Legends (adj.) · 14. Seven Deadly Sins: Grand Cross · 15. Arknights (TD gacha) · 16. Reverse: 1999 · 17. Another Eden · 18. Octopath Traveler: CotC · 19. Brown Dust 2 · 20. Limbus Company · ~ AFK Arena, Counter:Side, Last Cloudia, Etheria.

### Google Play (composite — Android skews **idle/AFK-heavy** vs iOS)
1. Honkai: Star Rail · 2. AFK Journey · 3. Persona 5: The Phantom X · 4. Summoners War · 5. Epic Seven · 6. Raid: Shadow Legends · 7. Star Wars: Galaxy of Heroes · 8. Marvel Strike Force · 9. Watcher of Realms · 10. Idle Heroes · 11. Reverse: 1999 · 12. Brown Dust 2 · 13. AFK Arena · 14. Hero Wars · 15. Mythic Heroes · 16. Seven Knights Re:BIRTH · 17. Eversoul · 18. Dragon Ball Legends (adj.) · 19. Empires & Puzzles (match-3 hybrid) · 20. FF VII: Ever Crisis.

> **Android reality:** premium cinematic turn-based (HSR, P5X) grosses globally, but the *count* of charting Android RPGs is dominated by idle hero-collectors. If targeting GP, the AFK loop (offline accrual + cap + fast rewards) is more chart-relevant than combat depth.

---

## 5. Top-10 table-stakes (a new turn-based RPG is judged against these)

1. Auto-battle + speed-up (2x/3x/4x) — *all*
2. Sweep / skip tickets on farmed stages — *E7, SW, Raid, AFK, Arknights*
3. Visible pity counter + hard-pity guarantee — *HSR 90, ZZZ 180, WuWa 160, E7 120, WoR 200, Reverse 70, AK 99*
4. Soft-pity ramp + featured-unit guarantee (50/50 carryover) — *HoYo standard*
5. Dupe → power conversion (Eidolon / Constellation / imprint / ascension) — *every roster game*
6. Ultimate / burst gauge as combat centerpiece — *HSR energy, E7 souls, Reverse moxie, P5X highlight*
7. Tower / abyss endgame climb — *HSR MoC, Raid Doom Tower, E7 Abyss, WoR*
8. Guild + co-op / raid layer — *SW, Raid clan boss, MSF alliance war*
9. PvP arena (async minimum) — *SW, E7, Raid, MSF, AFK*
10. Battle pass + daily/weekly loop + ~6-week LiveOps cadence (+ animated ult cut-ins & voice for tier-1)

## 6. Top-10 features worth stealing (innovation / retention)

1. **Weakness-break / toughness bar** — HSR, Octopath CotC *(see §3)*
2. **Daily competitive damage boss + server leaderboard** — AFK Journey Dream Realm
3. **Real-time PvP draft w/ pick & ban (RTA)** — Summoners War, Epic Seven, SWGOH GAC
4. **Speed-stat as master variable + turn-push/pull** — SW, E7, HSR (you already shipped the turn-order ribbon)
5. **Roguelike endgame (run-based stacking blessings)** — HSR Simulated Universe, Arknights IS
6. **Clash combat (interactive enemy turns)** — Limbus Company
7. **Costume = skill swap / cosmetics-as-strategy** — Brown Dust 2
8. **Spark / exchange currency on every pull** — Brown Dust 2, FGO, E7 medal shops
9. **Sanity / morale combat resource** — Limbus Company *(the Burnout steal in §3)*
10. **Support-unit borrow from friends** — FGO, Another Eden, HSR
11. *(bonus)* **Fusion / collect-and-fuse → guaranteed legendary** — Raid Fusion events
12. *(bonus)* **Transcendence — multi-tier ascension beyond max stars** — Idle Heroes (idle-whale vertical chase)

---

## Sources

**Apple pass:** Pocket Gamer (best iOS gacha), PCGamesN, GameSpot, Beebom, Eneba; Prydwen (HSR/AFK/Reverse), Fandom/wiki.gg (E7/SW/Limbus/Brown Dust 2/FGO/Arknights), Game8 (P5X), GamePress (FGO), AyumiLove (Raid Doom Tower), Wikipedia (Octopath CotC, FGO EOS), AttackOfTheFanboy (Reverse pity), BitTopup/dotesports (WuWa/ZZZ pity), Scopely (MSF Alliance War). Sensor Tower + GACHAREVENUE numeric tables not scrapable.

**Google Play pass:** Pocket Gamer (best Android gacha), Pocket Tactics, GACHAREVENUE/ennead.cc, ixbt.games (gacha revenue Mar 2026), HSR Toughness wiki, Prydwen (AFK Dream Realm), playafkjourney, SW Guild Battle wiki, vortexgaming (E7 New Era), AyumiLove (Doom Tower), swgoh.gg (community update 4-27-2026), Game8 (Brown Dust 2), allclash (Watcher of Realms), Dexerto (P5X pity), game-maps (Idle Heroes), theriagames (MSF ISO-8).

**Flagged facts:** Fate/Grand Order announced service end (Jan 29 2026, EOS ~March 2026) — included for mechanic reference only. Several action-adjacent titles (Genshin, ZZZ, Wuthering Waves, DB Legends) are chart neighbors that set QoL/presentation expectations but are not turn-based.
