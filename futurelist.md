# futurelist.md — hero-proto

Forward-looking feature backlog distilled from a 2026-05-28 competitive teardown
(Apple App Store + Google Play top-20 turn-based/gacha RPGs) cross-referenced
against a code-level audit. Companion to `TODO.md` (current work) and
`docs/COMPETITIVE_TEARDOWN_2026-05.md` (full research + sources).

Legend: 🔴 do-regardless table-stakes gap · ⭐ headline bet · 🟡 next-tier · 🔵 long-tail

---

## ⭐ Headline bet — the "extreme great idea"

**Weakness-break reskinned as "System Integrity" + a per-hero "Burnout" meter.**
hero-proto's signature combat mechanic.

- Enemies (outages, audits, legacy systems, Boto) get an **Integrity / Uptime bar**
  only cracked by the right "exploit type" (Network / Database / Security / Hardware /
  Frontend — mapped onto existing roles/factions). Zero it → the system **crashes**:
  bonus damage + skipped turn. (HSR weakness-break, on-theme.)
- **Burnout meter** (Limbus "sanity" steal, reframed): heroes accrue Burnout from
  Limit breaks + taking hits; high Burnout tanks effectiveness but feeds the
  *already-built* ≤5% HP hail-mary into a desperation payoff; managed Burnout = crit bonus.
- **Why it's the move:** both store passes named weakness-break the most-copied combat
  innovation of the era and the thing turn-based games are now judged on. It rescues the
  action-choice combat already shipped (Attack/Skill/Limit is currently cosmetic — Break
  gives every action weight). It's a **pure-function change** to `app/combat.py` (no DB/IO)
  and reuses the Faction axis as "type," so it's mostly config, not a migration.

## 🔴 Table-stakes gaps (cheap, do regardless)

1. **Type-advantage / affinity layer.** Every top title has enemy↔hero RPS (HSR 7 elements,
   Raid Magic/Force/Spirit/Void, AFK factions, Idle Heroes 6 factions). hero-proto's
   `team_faction_synergy` is a *same-faction team buff*, **not** an RPS combat axis. Missing.
2. **Deterministic acquisition** (spark / selector / fusion / targeted banner). #1 anti-churn
   fairness pattern of 2026. Have pity, no "pick your unit after N" and no 50/50 carryover.
   Pairs with the existing shard philosophy.
3. **Daily-rotating boss DPS-race + leaderboard** (AFK Journey *Dream Realm*). Highest
   engagement-per-dev-hour feature in the genre. Tower is static floors — this is the missing
   *daily* competitive hook.
4. **Gear substat grind.** Substats roll once at generation — no enhance/reforge/reroll loop,
   so "farm relics forever" doesn't exist.
5. **(Verify) Fast Rewards instant-accrual purchase** on the AFK loop — Android idle charts
   live on it.
6. **(Verify) In-battle speed multiplier (2x/4x)** + **skippable multi-pull animation** —
   Android reviewers torch games lacking these.

## 🟡 Next-tier steals

- **Real-time PvP draft w/ pick & ban (RTA)** — SW/E7/SWGOH. Deepest whale/competitive endgame.
- **Roguelike endgame** (run-based stacking blessings) — HSR Simulated Universe, Arknights IS.
  Fresh non-gear power axis, near-infinite replay without new art.
- **Support-unit borrow from friends** — FGO/AE/HSR. Cheap social hook + soft conversion funnel.
- **Speed push/pull effects** — lean into the turn-order ribbon already shipped; cheap depth.
- **Spark/exchange currency on every pull** — Brown Dust 2 / FGO / E7 medal shops.

## 🔵 Long-tail / watch

- **Clash combat** (interactive enemy turns) — Limbus Company. Novel, study even if not copied.
- **Costume = skill swap / cosmetics-as-strategy** — Brown Dust 2 (monetize cosmetics + depth).
- **Fusion → guaranteed legendary** events — Raid. Deterministic acquisition hook.
- **Transcendence — multi-tier ascension beyond max stars** — Idle Heroes idle-whale chase.
- **~6-week LiveOps patch cadence + crossover characters** — tier-1 retention heartbeat (P5X).

> Full feature matrices, ranked title lists, and sources: `docs/COMPETITIVE_TEARDOWN_2026-05.md`.

---

## Test accounts (local DB only — SQLite)

Seeded 2026-05-28 via `scripts/seed_player_account.py` (idempotent; re-run to top up).
Login is **email-based** (no username field) — use the full `@hp.test` address.
**Local only** — these do NOT exist on prod (`hero-proto.fly.dev` / `hero-proto.com`).

| login (email)            | password       | id | inventory |
|--------------------------|----------------|----|-----------|
| `kellytesting@hp.test`   | `MouseMouse1!` | 47 | loaded    |
| `brittesting@hp.test`    | `MouseMouse1!` | 48 | loaded    |

Each account: email-verified, 500k gems / 5M coins / 50k shards / 200 free summon credits /
50k friend points / 300 legend-boss shards / 50 arena tickets / 500 energy / all 6 crafting
materials @ 999 / hero-slot cap 500 / gear-slot cap 2000 / 6 starter heroes (lvl 30, 4-star).

To replicate on prod (machines must be awake):
```
fly ssh console -C "uv run python -m scripts.seed_player_account kellytesting@hp.test 'MouseMouse1!'"
```

---

## Basic log notes

- **2026-05-28** — Competitive teardown run (2 agents: Apple App Store 22 titles + Google Play
  20 titles). Findings + code-gap audit captured in `docs/COMPETITIVE_TEARDOWN_2026-05.md`;
  this futurelist distilled from it.
- **2026-05-28** — Seeded loaded local test accounts `kellytesting@hp.test` (id 47) +
  `brittesting@hp.test` (id 48), both pass `MouseMouse1!`, via new
  `scripts/seed_player_account.py`. Verified single instance of each (no dupes).
- **2026-05-28** — Confirmed `hero-proto.com` and `hero-proto.fly.dev` serve the **same build**
  (`built_at` 2026-05-28T21:05:15Z; `.com` is a custom domain on the same Fly app). Flagged:
  `/version` reports `version`/`branch` = `"docker"` (build-arg fallback) — git SHA not baked
  in, so the SPA-vs-API version badge can't do its mismatch check. Fix = pass
  `HEROPROTO_BUILD_VERSION` on `fly deploy`.
