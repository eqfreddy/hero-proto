# Stages Page Rebuild — Research Report

**Date:** 2026-05-13
**Author:** Research agent
**Scope:** Board-game-style campaign map for hero-proto, cyberpunk "AI uprise" theme, milestone rewards every 5/10 battles with hidden legendary summon chance.

---

## 1. TL;DR Recommendation

Build hero-proto's stages page as a **vertically-scrolling "datastream"** — a circuit-board trace that flows from the bottom (where the player is) up toward distant servers/bosses, broken into **chapters of ~15 stages** with a **"Milestone Node"** (glowing data-vault icon) every 5 battles and a **"Boss Server" node** every 15. Visually crib from **AFK Arena's vertical chapter scroll** for the long path, **Candy Crush's one-active-node-glows pattern** for clarity of "next step", and **RAID: Shadow Legends' chapter-end loot drop** for milestone reward telegraphing. The cyberpunk twist: stages are not "lands" but **compromised subnets**; clearing a stage flips its node from red→green (player-pwned), and the path is an animated packet-flow trace. The legendary summon chance lives behind a sealed "encrypted drop" icon on the 10/25/50 milestone nodes — the gate is visible, the contents are not, satisfying both Zeigarnik tension and anchoring.

## 2. Layout Patterns

| Pattern | Example | Pros | Cons |
|---|---|---|---|
| **Linear vertical scroll (chaptered)** | AFK Arena, Candy Crush | Trivial mental model, infinite room to grow, scales to chapter-themed art | Can feel grindy with no choice |
| **Chapter chunks w/ themed backdrops** | RAID: Shadow Legends (12 chapters × 7 stages) | Strong narrative beats, easy to gate by character requirement | Requires distinct art per chapter |
| **Circuit-board grid / node graph** | Persona 5 Strikers (Jails), Watch Dogs hack-tree | Theme-perfect for "AI uprise", supports branching | Hard to scale past ~50 nodes without clutter |
| **Branching tree w/ optional sidequests** | MSF campaign nodes, Hearthstone Adventures | Player agency, room for daily/event nodes | Branching paywall feel if monetized poorly |

**Recommendation:** Hybrid — linear vertical spine of chapters (1.1, 1.2 … 12.7 RAID-style numbering), but each chapter zoomed-in renders as a **mini circuit-board sub-map** with the spine path plus 1-2 optional side-nodes for events/dailies. Best of both worlds and matches our existing `stage_id`/`chapter` data shape.

## 3. Milestone Reward Design

**Cadence (recommendation):**
- **Every 5 stages**: small shard pack (10-30 template shards, weighted toward currently-equippable rarities) + gold. Visualized as a **bronze data-cache** node.
- **Every 10 stages**: medium pack + **1 guaranteed Epic shard pull** + **hidden legendary summon roll (~3-5% per node)**. Silver vault.
- **Every 25 stages**: gem chunk (75-150 gems) + **guaranteed Epic hero shard** + higher legendary roll (~8-12%). Gold vault.
- **Every chapter boss (15-stage cadence)**: hero unlock token / faction-locked legendary shards. Boss-server node, distinct art.

**Hidden-reward transparency:** Follow RAID's published-pool model. Show the **possible** rewards on the milestone tooltip ("Contains: 50 shards + chance at Legendary Summon"), keep the **roll outcome** hidden until claim. This dodges loot-box regulatory friction while preserving variable-reward dopamine. Display the rate as a small "?" icon that opens drop-rate sheet — competence + transparency.

**Reward ladder anchor:** The legendary summon should appear on the milestone preview as a *grayed silhouette* with a "???" label and a particle aura. This is the **anchoring artifact** — players see the silhouette from stage 1 and chase it.

## 4. Psychology Hooks (Rule #1)

1. **Zeigarnik (incomplete tasks):** Next-available stage node **pulses with a packet-flow animation**; all completed nodes are static green. Brain itches to close the loop. Plus a persistent "Chapter 3: 7/15 nodes pwned" header.
2. **Variable reward:** Milestone vault rolls hidden legendary summon — outcome unknown until claim animation. Classic VR schedule (Candy Crush striped-candy logic).
3. **Anticipation of reward:** Permanent **"4 stages to next vault"** counter under the active node. AFK Arena uses chapter-completion bars; we do per-milestone.
4. **Competence / mastery:** RAID-style **3-star rating per stage** (win, no deaths, under N turns). Re-runs become skill expression, not just farming.
5. **Loss aversion:** **Win-streak counter** in the header (e.g., "Win streak: 12 — break it and milestone roll resets to base odds"). Stretch goal — add a "perfect chapter" badge that demands no retries.
6. **Anchoring:** Legendary silhouette on the 25-node vault preview, visible from far below. Players chase the highest visible prize.
7. **Endowed progress:** Start chapter 1 with stages 1.1-1.2 **already shown as cleared** (the tutorial), so the player feels mid-chapter on arrival.

## 5. Visual References

1. **AFK Arena world map** — vertical scroll, chapter-themed biomes, node glow on next stage. https://afk-arena.fandom.com/wiki/The_World_Map
2. **AFK Arena Game UI Database entry** — actual screenshots of campaign UI. https://www.gameuidatabase.com/gameData.php?id=1316
3. **RAID: Shadow Legends campaign** — 12 chapters × 7 stages, 3-star ratings, chapter-end loot bag, difficulty tiers (Normal/Hard/Brutal/Nightmare). https://raidshadowlegends.fandom.com/wiki/Campaign
4. **Candy Crush sugar trail** — single highlighted next-node, completed nodes show stars (1-3), gates every ~15 levels. (Search "Candy Crush map screenshot")
5. **Cyberpunk 2077 inventory & map UI** — blue circuit-trace aesthetic, hex-grid overlays. https://interfaceingame.com/articles/cyberpunk-2077-ux-ui-critique/
6. **Persona 5 Strikers — Jail maps** — node-based corruption mapping, perfect tonal match for "compromised subnet" framing.
7. **Watch Dogs 2 / Legion — hacking minigame UI** — packet-flow animations along traces; steal directly for the active-node pulse.
8. **System Shock / Citadel Station maps** — deck-by-deck progression, retro-cyberpunk grid maps.
9. **Hearthstone Adventures (Karazhan, League of Explorers)** — chapter-as-room layout with boss icons; useful for our chapter-boss node treatment.
10. **Clash Royale chest queue** — best-in-class hidden-reward telegraphing; vault contents unknown but slot is visible and timed.

## 6. Open Questions for the Implementation Agent

- **Data model:** Do existing `Stage` rows carry a `chapter` field, and is there room for `is_milestone` / `milestone_tier` flags, or do we compute milestones client-side from `stage_id % 5 == 0`?
- **Legendary pool composition:** Which heroes count as "legendary summon" eligible — only ones already in the gacha, or a separate milestone-exclusive pool? Affects FOMO economy.
- **Auto-progress / sweep:** Does the milestone-vault claim flow gate auto-clear? RAID lets you raid-skip a cleared stage; we need to decide if sweeping a chapter still triggers vault animations or batches them.
- **Server vs. client roll:** Hidden legendary summon roll **must be server-authoritative** (anti-cheat + drop-rate compliance). API shape likely `POST /stages/{id}/claim-milestone` returning roll result.
- **Difficulty tiers:** Do we ship with one difficulty or scaffold for Normal/Hard/Brutal at launch? Affects map art budget.
- **Mobile vs. desktop scroll feel:** Touch-friendly vertical scroll vs. desktop pan/zoom — pick one as primary, the other adapts.
- **Win-streak penalty design:** Loss aversion is potent but can feel punitive. A/B test "streak boosts odds" vs. "broken streak resets odds".
- **Art pipeline:** 12 chapter biomes × cyberpunk dressings is a lot. Can we procgen the circuit-board paths from stage coordinates and only hand-author the chapter boss tableaux?

---

**Sources:**
- AFK Arena Wiki — Campaign / World Map
- AFK Arena Game UI Database
- RAID: Shadow Legends Wiki — Campaign + drop tables
- Empyrean Rule RAID campaign guide
- Medium — Zeigarnik effect in video game design (Komad)
- yukaichou.com — Candy Crush mechanics deconstruction
- Cyberpunk 2077 UX/UI critique — interfaceingame.com
- Marvel Strike Force Wiki — Campaigns
- gamedeveloper.com — metagame design in mobile RPGs
- Medium / Rakesh Roy — Designing reward loops without manipulation
