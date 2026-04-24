# hero-proto — Product Requirements Document

**Status:** draft for review
**Author:** Claude (on behalf of the hero-proto team)
**Last updated:** 2026-04-24

---

## 1. Why this document exists

We have a working alpha: 22 backend slices, 268 passing tests, a dashboard, a battle replayer, 13-section end-to-end walkthrough green. The roadmap has ~60 candidate items spread across Sprints A–H and speculative work beyond. Without sequencing, we'll stall on "what's next?" every session.

This PRD picks a target, breaks it into phases, and sets acceptance criteria so "done" is unambiguous.

---

## 2. Vision (one paragraph)

hero-proto is a satirical corporate-IT gacha RPG where players collect helpdesk veterans, rogue DBAs, and board members; fight turn-based battles against tickets, audits, and pager storms; join guilds for raids against giant legacy systems; and progress through a monetization model borrowed from Path of Exile 2 — cosmetic and QoL purchases only, never stat-boosting pay-to-win.

**One-line elevator:** AFK Arena meets *The IT Crowd*, with QoL-only monetization.

---

## 3. Audience

- **Primary:** Developers, IT pros, and burnout-adjacent professionals in their late 20s–40s who played mobile gacha in the 2015–2020 wave and want the genre's systems without the dark patterns.
- **Secondary:** Casual mobile gamers who'd enjoy the humor regardless of industry background.

**Not targeted:** whales, core gacha addicts, kids.

---

## 4. Success metrics (per phase, measurable)

Deferred in detail until we have PostHog wired (Phase 2). For now:
- Phase 1 acceptance = feature checklists below pass + 13-section walkthrough still green + no test regressions.
- Phase 2+ unlock quantitative metrics (D1/D7 retention, pull-to-battle funnel, shop CVR).

---

## 5. Phase 0 — Shipped (as of 2026-04-24)

Reference only. See [TODO.md shipped index](../TODO.md#-shipped--reference-index) for the full list. Summary by system:

| System | State |
|---|---|
| **Auth** | JWT + refresh rotation + reuse detection, password reset, email verify, TOTP 2FA + recovery codes |
| **Gacha** | x1/x10, 50-pull pity, 6 rarity tiers, 35 heroes across 5 factions |
| **Combat** | Deterministic turn-based resolver, 5 status effects, 2 active sets, 200-entry log cap |
| **Progression** | Gear equip/unequip, hero ascension (stars 1–5), skill-up via fodder, sweep |
| **Content** | 32 stages (tutorial + 10 normal + 10 hard + 5 endgame + 5 endgame-hard), 3 raid-boss templates |
| **Social** | Guilds (apply/accept/reject/transfer/promote), chat w/ keyset pagination, raids (tier scaling, cooldown, leaderboard), arena (matchmaking + replays) |
| **Economy** | Daily quests (6 kinds), daily login streak, 2 LiveOps event types, Stripe + mock-payments, purchase ledger + refunds |
| **Admin** | Ban (timed + permanent), audit log, analytics overview, announcement broadcast, CLI |
| **Anti-cheat** | Per-account rate limits (battle / arena / guild chat), JWT token-version on ban, ownership checks verified |
| **Ops** | Prometheus metrics, JSON logs, request IDs, Sentry, Redis rate-limit backend, worker supervisor + health, DB backup script, graceful-shutdown docs |
| **Client** | HTMX dashboard, Phaser battle replayer, PWA installable (manifest + service worker), 50 SVGs with standalone render |
| **Test** | 268 pytest, startup_check script, 13-section client_walkthrough, Postgres compose smoke script |

---

## 6. Phase 1 — "First 10 minutes feel good" *(quick win)*

**Duration:** 1–2 weeks single-developer.
**Ship criterion:** a new player registers, does 10 actions, and ends up *wanting* to come back tomorrow.

### Problem
The backend is solid. The *new player experience* isn't:
- Tutorial stage exists in the DB (`tutorial_first_ticket`, order 0) but nothing guides the player to it.
- Roster is a JSON-ish list. Player can't tell which hero is best or what to chase.
- Team picker on the Battle tab requires typing comma-separated IDs. Nobody will do that twice.
- x1 summon bug shipped as late as this week — signal that the click paths aren't rehearsed.

### Scope (locked)

**1.1 Guided first-session flow**
- [ ] `/me` partial shows a persistent **"Next step"** card until the player clears tutorial + first real stage + first summon. Each step has a one-click CTA ("Start tutorial", "Do your first summon", etc.).
- [ ] Tutorial stage auto-links a pre-populated team (first 1–3 heroes owned) so players don't have to pick IDs the first time.
- [ ] Post-tutorial victory screen shows "You earned: X coins, Y shards. Spend shards on your first summon →" as a clickable path.

**1.2 Roster visualization (minimum viable)**
- [ ] Roster tab becomes a grid of rarity-bordered cards (not a list), sorted by power desc.
- [ ] Each card: portrait, name, rarity, role, faction, level, stars, power.
- [ ] Filter chips at top: All / COMMON / UNCOMMON / RARE / EPIC / LEGENDARY. (Myth deferred — no content yet.)
- [ ] Duplicate heroes collapse into a single card with a count badge ("Jaded Intern ×3").
- [ ] Click a card → modal showing the single-hero detail (stats, gear loadout, signature move, star-up progress). *Read-only this phase; upgrade actions stay on existing endpoints.*

**1.3 Team picker QoL**
- [ ] `POST /me/team-presets` + `GET /me/team-presets` — named preset (Campaign / Arena / Raid / custom, up to 5 presets per account).
- [ ] Stages/Battle/Arena/Raid tabs get a preset dropdown: "Use preset…" replaces the comma-separated ID input.
- [ ] "Use last team" one-click button everywhere a team is needed — pulls from the most recent successful `Battle` for that player.
- [ ] Battle result screen adds "Save as preset…" button.

**1.4 Quick fixes**
- [ ] Fix any lingering static/index.html vs templates/partials inconsistencies — we hit one this week.
- [ ] Consolidate "signed in as X" display across the dashboard so the pill header matches /me partial.
- [ ] Add a visible "shards left" counter on the Summon button.

### Out of scope for Phase 1
- Real combat control (player targeting, turn pause) — Phase 3.
- Any art/animation work beyond what designers deliver unprompted.
- Capacitor wrapping or store submission — Phase 4.
- Weapon/armor split — Phase 2.
- PostHog integration — Phase 2.
- Myth-tier / event-only heroes — Phase 2.

### Tools adopted in Phase 1
- **None.** All Phase 1 work is in-house HTML/CSS/JS + new FastAPI routes. No new deps.

### Acceptance criteria (the "done" test)
A new user from empty DB can:
1. Register and land on /app/.
2. See a "Start tutorial" CTA card without navigating.
3. Click it, battle auto-team, see the victory screen.
4. Click "Do your first summon" from the victory screen, get a card-grid result.
5. Open Roster, see at least one hero as a card, click it, see the detail modal.
6. Save their roster as a preset named "main".
7. Use the preset on the Battle tab without typing IDs.
8. `client_walkthrough.py` still passes all 13 sections.

---

## 7. Phase 2 — "Feels like a real game" *(medium lift)*

**Duration:** 3–4 weeks.

### Goals
- Players have reasons to come back daily beyond login bonus.
- We measure what players actually do so decisions stop being guesses.
- IAP pipeline becomes store-ready so Phase 4 is plumbing only.

### Scope

**2.1 Hero detail depth** — promote Phase 1's modal to a full route
- Weapon / armor / accessory slots (breaking down the abstract `Gear` table into slot-aware subclasses).
- Skill tree UI for `special_level` progression (currently just a number).
- Star-up flow with "which copies to use" selection.
- Visible next-upgrade previews ("+10% power with one more copy").

**2.2 Event content**
- Myth-tier hero category wired end-to-end — seed 1 event hero, gated on `LiveOpsEvent.kind=EVENT_BANNER` (new kind).
- Scheduled future LiveOps events (`starts_at` in the future, preview endpoint).
- Stat variance (±X%) on duplicate summons so owned copies aren't identical.

**2.3 Analytics — PostHog self-hosted**
- Deploy PostHog on its own host (Docker).
- Instrument 12 events: `register`, `login`, `summon_x1`, `summon_x10`, `stage_start`, `stage_clear`, `first_clear`, `purchase_start`, `purchase_complete`, `arena_attack`, `raid_attack`, `daily_bonus_claim`.
- Funnels: register → first battle → first purchase.
- Dashboard published internally.

**2.4 Store expansion**
- PoE2-style product catalog: QoL packs (auto-battle unlock, extra preset slots, roster sort options), cosmetic frames, monthly/weekly passes.
- Apple StoreKit 2 receipt validation (app-store-server-library).
- Google Play Billing receipt validation (google-play-billing-validator).
- Abstract `PaymentAdapter` interface so Stripe / Apple / Google share the `ShopProduct` table.

**2.5 Balance tooling**
- Jupyter notebook in `analytics/` with numpy + pandas + matplotlib.
- Simulators: gacha EV / pity distribution, 10k-pull histogram, arena rating convergence, DPS curves by team comp.
- YAML balance config read by seed.py so designers can tune without touching Python.

### Tools adopted in Phase 2
- **PostHog** (self-hosted OSS, event analytics)
- **app-store-server-library** (official Apple Python SDK, StoreKit 2)
- **google-play-billing-validator** (or RevenueCat SDK if we want to buy time)
- **numpy / pandas / Jupyter** (balance notebook — no production path)
- **transitions** (optional, for raid + battle state machines if they grow unruly)

### Acceptance criteria
- New hero detail page passes a dedicated Playwright smoke.
- Myth-tier event hero is summonable during active event window only, verified in a test.
- PostHog dashboard shows live events from a staging walkthrough run.
- A mock Apple IAP + mock Google Play receipt each grant contents via the shop router, ledger reflects it, refund works.
- Balance notebook produces a gacha-EV chart checked into the repo.

---

## 8. Phase 3 — "Combat depth" *(design-heavy, the biggest fun bet)*

**Duration:** 4–6 weeks, multiple design iterations expected.

### Goals
- Player can win a hard fight by playing well, not just by stats.
- Auto-battle becomes a paid QoL unlock, never the default — monetizes without pay-to-win.
- Battle viewer has animated actors instead of static portraits.

### Scope

**3.1 Combat model changes (backend)**
- Split `basic_mult` into `melee_mult` + `ranged_mult`. Templates declare which they use; role/faction defaults on seed.
- New resource: `mana` or `focus`, regenerated per turn for ranged/magic heroes.
- "Hail-mary" ability at ≤5% HP — one-shot special, role-flavored (ATK burst, DEF revive, SUP heal-all).
- Targeting hints in the combat log (player will be able to pick targets; log now identifies valid ones).

**3.2 Active combat UI**
- Turn pause on player input; auto-pause when any hero's special is off cooldown.
- Click enemy card to focus a target; player's next special hits that target.
- Auto-battle toggle (paid QoL; free accounts get the old "simulate → result" flow).
- Skip / speed controls (2×, 4× on replay; 1× for active play).

**3.3 Animated actor layer**
- Rive integration for 2D animated stick-figure actors.
- 3 rigs (ATK / DEF / SUP), 5 states each (idle / melee / ranged / hit / death).
- Battle viewer renders Rive above a CSS stage background.
- Hero portraits stay for out-of-battle; Rive rigs only appear in active fights.

### Tools adopted in Phase 3
- **Rive** (OSS runtime, MIT) — animated actors.
- Possibly **Kaplay** if Phaser's scene graph gets awkward for the new combat UI.

### Risks
- **Design cost.** This is the first sprint where design work is on the critical path. Without a designer (AI or human) producing Rive files, this phase stalls.
- **Scope creep.** Must-not-do: new rarities, new factions, new hero types. Phase 3 is combat only.

### Acceptance criteria
- A 1-minute demo video of a player winning a battle by picking targets + timing specials.
- Rive file for at least one rig committed + rendered in battle viewer.
- Auto-battle toggle gated behind a `shop.unlock.auto_battle` product entry.

---

## 9. Phase 4 — "In the stores" *(capstone)*

**Duration:** 3–4 weeks once design sign-off on branding.

### Goals
- App live in Google Play + Apple App Store.
- Push notifications drive retention (raid ending, daily reset, guild @mention).

### Scope

**4.1 Capacitor wrap**
- Wrap `/app/` in a Capacitor project (separate repo or `mobile/` subdir).
- Native splash + icon pipelines (we have the keyboard-sword icon).
- `@capacitor/push-notifications` + server-side push (FCM for Android, APNs for iOS).

**4.2 Store compliance**
- Privacy policy + ToS pages (HTML routes).
- Kids age-gate (block under-13 signup, per store policy).
- Data deletion flow (already exists via `DELETE /me`; needs a UI surface in the app).
- Screenshots, descriptions, keywords for both stores.

**4.3 First deploy target**
- Hosted backend on Fly.io or Railway (TLS mandatory for PWA SW to register on real phones anyway).
- Production Stripe + Apple + Google keys rotated in.
- Run `scripts/postgres_stack_validate.sh` green against the hosted DB.
- `scripts/backup_db.sh` scheduled nightly on the host.

### Tools adopted in Phase 4
- **Capacitor** + `@capacitor-community/in-app-purchases` + `@capacitor/push-notifications`.
- **Fly.io** or **Railway** (pick one; Fly edges ahead for worker + Postgres colocation).
- Optional: **RevenueCat SDK** to offload IAP receipt complexity.

### Acceptance criteria
- Test build available via Google Play Internal Test + TestFlight.
- One push notification delivered to a real phone end-to-end.
- Public URL served with valid TLS, hitting `/healthz` → 200.

---

## 10. Not planned (and why)

| Thing | Reason |
|---|---|
| Real-time multiplayer combat | Async turn-based is the genre's selling point — removing it is a different game |
| Chat voice/video | Store-compliance nightmare, no gameplay benefit |
| NFT / web3 integration | Irrelevant to audience, legally hostile in many jurisdictions |
| Full SPA rewrite (React/Svelte) | HTMX works for this scope; revisit only if Phase 3 UI outgrows it |
| Procedurally generated content | The hand-crafted IT-satire tone is the product |
| LLM-generated hero lore in-game | Fine as a tool for us; too gimmicky as a player feature |

---

## 11. OSS landscape summary

Pulled from a research sweep 2026-04-24. Full notes retained in session history; concrete bets:

1. **Rive** — top pick for animated actors. Unblocks Phase 3.
2. **PostHog self-hosted** — analytics solved in Phase 2.
3. **Apple app-store-server-library + google-play-billing-validator** (or RevenueCat) — IAP in Phase 2/4.
4. **Jupyter balance notebook** — designer-tunable numbers in Phase 2.
5. **Official Stripe / Sentry / PostHog MCP servers** — developer velocity, adopt anytime.

**Dead ends flagged:** no worthwhile OSS gacha backend exists (we've already passed the useful ones by size). Grasscutter/LunarCore/etc. are reverse-engineered private servers — borrow schema ideas only. `pygame-server`, `aiogame` are abandoned. Commercial Spine replaced by DragonBones if we ever need skeletal animation; Rive is the better bet.

---

## 12. Open questions for review

1. **Phase 1 scope feel right for 1–2 weeks?** Or shorter if we cut the team-presets endpoint and do "use last team" only.
2. **When to start Phase 4 prep?** Store-compliance work can kick off in parallel with Phase 2 if we want to be in-store faster.
3. **Designer source.** Phase 3 assumes design-AI or human delivers Rive files. If neither is available on schedule, Phase 3 reverts to stick-figure placeholders (cheaper but less polished).
4. **Monetization SKU list.** PoE2-style is the tone; concrete SKUs for Phase 2.4 still need writing. Want a mini-PRD on just that?

---

**Review prompt for the reader:**
Mark `[x]` next to anything you approve as-is. Add comments on anything you want changed. Strike-through anything to drop. I'll revise and re-post. Once Phase 1 is locked, I'll open the sprint.
