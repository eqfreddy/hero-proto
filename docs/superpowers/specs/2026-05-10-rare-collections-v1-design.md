# Rare Collections v1 — Design Spec

**Goal:** Add a long-term collection-grind layer to hero-proto. 12 themed collections (4 rarities × 3 level brackets), pieces drop from stages/bosses/raids/8-tracks, completion grants tiered rewards. Drives the "feel like getting something accomplished" thread between active gameplay loops.

**Architecture:** New `Collection` + `CollectionPiece` seed tables for static content. Per-account progress lives in a new JSON column on `Account`. New `app/collections.py` module owns drop-roll, dup-handling, completion, and claim logic. Battle-resolve hooks at the existing post-WIN site in `app/routers/battles.py` add a piece-drop step alongside the existing gear-drop. Frontend `/collections` route shows a 12-card grid with progress + claim CTAs.

**Tech Stack:** Python 3.13 + FastAPI + SQLAlchemy 2.0 + Alembic. React/TypeScript SPA. Tests via `uv run pytest`.

**Out of scope (v2 follow-ups):** Legendary set-bonus passive design, Myth tier RNG-gated unlock, buyable 8-tracks via Stripe, random collection pieces in shop catalog rotation.

---

## 1. Data model

### `Collection` (static seed)

| Field | Type | Notes |
|---|---|---|
| `code` | str PK | e.g., `"floppy_boneyard"` |
| `name` | str | "Floppy Drive Boneyard" |
| `theme` | str | Flavor blurb, ~1 sentence |
| `rarity` | str | `UNCOMMON \| RARE \| EPIC \| LEGENDARY` |
| `level_bracket` | str | `"1-20" \| "21-40" \| "41-60"` |
| `pieces_json` | Text | JSON array — see CollectionPiece schema below, embedded |
| `reward_json` | Text | JSON spec of completion reward (see §3) |
| `sort_order` | int | UI ordering |

Pieces are stored as JSON inside `pieces_json` for simplicity (~12 pieces per collection × 12 collections = ~144 rows max — embedding is cheaper than a join table at this scale, and pieces never change after seed).

Piece schema (inside `pieces_json`):
```json
[
  {
    "code": "floppy_525",
    "name": "5.25\" Floppy Disk",
    "icon": "💾",
    "flavor": "Holds 360 KB. Smells like 1986.",
    "is_completion_piece": false
  },
  ...
]
```

Exactly one piece per collection has `is_completion_piece: true`.

### `Account.collection_progress_json` (new column)

```json
{
  "<collection_code>": {
    "pieces": ["floppy_525", "floppy_35"],
    "completed_at": "2026-05-12T14:20:00Z",
    "claimed_at": null
  }
}
```

- Empty/missing entry → no progress yet
- `pieces` is the list of piece codes the player owns
- `completed_at` is set when all pieces collected
- `claimed_at` is set when the reward has been granted

### `Account.eight_tracks` (new column)

`Integer, default 0`. Inventory count of unopened 8-track loot boxes.

---

## 2. Drop pipeline

### Probability table

| Source | Per-event chance | Selection rule |
|---|---|---|
| Stage WIN (regular) | 7% | Bracket-filtered, rarity-weighted, non-completion piece preferred |
| Chapter/stage boss WIN | 20% | Same, but completion-piece allowed when only it remains |
| Raid contribution (per attack) | 5% | Raid-specific collection pool only (separate codes from regular 12) |
| 8-track open | 100% (1–3 pieces) | Includes completion-piece pool; weighted 60/30/10 for 1/2/3 pieces |

### Selection algorithm (`roll_piece_drop`)

```
1. If account_level <= 20: bracket = "1-20"
   elif <= 40: bracket = "21-40"
   elif <= 60: bracket = "41-60"
   else: bracket = any
2. candidates = collections in bracket where progress.completed_at is None
3. if not candidates: return None
4. weight = {UNCOMMON: 0.50, RARE: 0.30, EPIC: 0.15, LEGENDARY: 0.05}
5. pick collection from candidates by rarity weight
6. unowned_pieces = collection.pieces - account.collection_progress.pieces
7. if not unowned_pieces: return None  (defensive — completed but completed_at not set yet)
8. if source != "boss" and len(unowned_pieces) == 1 and that piece is_completion_piece:
       try to find a regular collection-with-non-completion-pieces-remaining instead
       (fallback: drop the completion piece anyway)
9. else: pick uniformly from unowned non-completion pieces; if none, take the completion piece
10. return CollectionDrop(collection_code, piece_code, name, icon, is_completion_piece)
```

### Award & dup handling (`award_piece`)

```
piece in progress.pieces? → DUPLICATE: account.coins += 5; return "duplicate"
not in progress.pieces?    → NEW: progress.pieces.append(piece); return "new"
```

### Completion detection (`try_complete`)

```
if len(progress.pieces) >= len(collection.pieces) and progress.completed_at is None:
    progress.completed_at = utcnow()
    return True
return False
```

### Claim (`claim_reward`)

```
progress.completed_at is None  → 400 "not complete"
progress.claimed_at is not None → 400 "already claimed"
grant reward per collection.reward_json (see §3)
progress.claimed_at = utcnow()
return granted dict
```

---

## 3. Reward ladder

Per-collection reward spec lives in `Collection.reward_json` so balance is data-driven.

| Rarity | Reward | Spec shape |
|---|---|---|
| Uncommon | Cosmetic frame | `{"kind": "frame", "frame_code": "<code>"}` → append to `account.cosmetic_frames_json` |
| Rare | Currency bundle | `{"kind": "currency", "coins": 500, "gems": 50, "shards": 10}` |
| Epic | Hero-template shards | `{"kind": "hero_shards", "amount": 30, "rarity": "EPIC"}` → grant 30 shards of a random Epic-rarity hero from player's roster (mutate `account.template_shards_json`) |
| Legendary | **v1 placeholder** | `{"kind": "currency", "gems": 200, "frame_code": "legen_waitforit_dary_hoarder"}` — v2 replaces this with set-bonus passive |

For Epic shard grants: if player has no Epic-rarity heroes in roster, fall back to the highest-rarity hero they do own.

---

## 4. 8-track loot boxes (earned-only in v1)

### Earning sources

- **Weekly chest** — players earn 1 per week via existing weekly cycle
- **Tower of Trials milestone** — reach floor 50 → grant 1 (one-time)
- **Raid top-10% contribution** — top contributors get 1 per raid

### Open mechanic (`POST /collections/8-track/open`)

```
account.eight_tracks <= 0 → 400 "no 8-tracks"
account.eight_tracks -= 1
piece_count = weighted_pick([(1, 0.6), (2, 0.3), (3, 0.1)])
pieces = []
for _ in range(piece_count):
    drop = roll_piece_drop(account, source="8-track", ...)
    if drop is None: continue  # all complete
    award_piece(account, drop.piece_code)
    pieces.append(drop)
    try_complete(account, drop.collection_code)
return pieces
```

8-tracks include completion pieces in the pool (no completion-piece-bias dance — they're the consolidated catch-up mechanic).

---

## 5. API surface

### New endpoints

| Method | Path | Description |
|---|---|---|
| `GET` | `/collections` | All 12 collections + per-account progress + claimable status |
| `POST` | `/collections/{code}/claim` | Claim completed reward. 400 if not complete or already claimed. |
| `POST` | `/collections/8-track/open` | Consume 1 8-track, return 1–3 pieces. 400 if `eight_tracks <= 0`. |

### `/collections` response shape

```json
[
  {
    "code": "floppy_boneyard",
    "name": "Floppy Drive Boneyard",
    "rarity": "UNCOMMON",
    "level_bracket": "21-40",
    "theme": "...",
    "pieces": [
      {"code": "floppy_525", "name": "...", "icon": "...", "owned": true,  "is_completion_piece": false},
      {"code": "floppy_35",  "name": "...", "icon": "...", "owned": false, "is_completion_piece": false},
      ...
    ],
    "owned_count": 3,
    "total_count": 8,
    "completed_at": null,
    "claimed_at": null,
    "claimable": false,
    "reward_summary": "Cosmetic frame: Floppy Whisperer"
  },
  ...
]
```

### Battle-resolve `rewards_extra` additions

Existing `rewards_extra` dict (returned in battle response) gets new optional keys:

```json
{
  "collection_drop": {
    "collection_code": "floppy_boneyard",
    "piece_code": "floppy_525",
    "name": "5.25\" Floppy Disk",
    "icon": "💾",
    "is_completion_piece": false
  },
  "collection_dup_coins": 5,
  "collection_completed": "floppy_boneyard"
}
```

Frontend reads these to render the loot popup.

---

## 6. Frontend

### New route `/collections`

- Grid: 12 cards (4 rarities × 3 brackets)
- Card content: name, theme blurb, progress bar `N/M`, piece silhouettes (revealed on collect)
- Filter bar: All / Uncommon / Rare / Epic / Legendary / Show completed
- Claimable cards: gold pulse + "Claim Reward" button
- Claimed cards: lock icon + reward summary

### Loot popup (battle-end overlay)

On battle-WIN response containing `rewards_extra.collection_drop`:

```
┌─────────────────────────────────────────┐
│  📜  COLLECTION FIND                    │
│                                         │
│   [icon]  3.5" Floppy Disk             │
│           Floppy Drive Boneyard         │
│           ▓▓▓▓▓▓▓░░░  7/10              │
│                                         │
│   [Inspect Collection]    [Continue]    │
└─────────────────────────────────────────┘
```

- Distinct gold sparkle animation
- If `is_completion_piece: true` — swap header to `"⭐ COMPLETION PIECE"` and progress bar fills to 100% with a gold flash
- If `rewards_extra.collection_completed` is set — queue an additional banner *"Collection complete — claim your reward"* deep-linking to `/collections`

### Discovery

First time a player gets ANY piece (`collection_drop` is set in their battle response), fire a one-shot coach mark on the `/collections` nav button: *"You found a collection piece — track your sets here."* Reuses existing `<CoachMark>` infra. Stored in `localStorage` per the existing pattern.

### Stage row drop indicator (optional polish)

Stage rows in `/stages` show a small icon badge if the player is mid-pursuit on a collection that the stage's bracket can drop pieces for. Defer to implementation pass — not blocking.

---

## 7. Seed content (v1)

Final names + flavor are designer pass. Spec ships the structure:

| Bracket | Uncommon | Rare | Epic | Legendary |
|---|---|---|---|---|
| 1–20 | Cubicle Detritus (8 pcs) | Onboarding Kit (8 pcs) | Help Desk Starter Pack (10 pcs) | Y2K Survival Relics (12 pcs) |
| 21–40 | Floppy Drive Boneyard (8 pcs) | Themed Paperclips (8 pcs) | Server Closet Archaeology (10 pcs) | The Legendary Rolodex (12 pcs) |
| 41–60 | Cassette/8-track Oddities (8 pcs) | Patch Tuesday Memorial (8 pcs) | The Forbidden Codebase (10 pcs) | Founder's Garage (12 pcs) |

Total pieces: 4 brackets × (8+8+10+12) ≈ 114 pieces seeded.

Reward content per collection lives in `reward_json` per §3.

---

## 8. Error handling

- Invalid collection code on claim → 404
- Claim on incomplete → 400 `"collection not complete"`
- Claim twice → 400 `"already claimed"`
- 8-track open with 0 inventory → 400 `"no 8-tracks"`
- Drop roll on player past bracket 60 → fallback selects from any bracket
- Drop roll where no incomplete collections exist → returns None silently (player completed everything; no error surfaced — congratulations on going full set, see you in v2)
- `Account.collection_progress_json` corrupt → log warning, treat as `{}` (defensive _load pattern from fail_pity / drop_meter modules)

---

## 9. Migration

Single Alembic migration adds 2 columns:

```python
op.add_column("accounts", sa.Column("collection_progress_json", sa.Text(), nullable=False, server_default="{}"))
op.add_column("accounts", sa.Column("eight_tracks", sa.Integer(), nullable=False, server_default="0"))
```

Plus 1 new table `collections`. Seed runs at startup like existing seed loops; collection pieces embedded in `pieces_json` so no separate piece table.

Backfill: existing accounts get `'{}'` and `0` via server_default — no data migration needed.

---

## 10. Testing

### Unit (`tests/test_collections.py`)

- Bracket filter selects from correct level range
- Rarity weighting hits ~50/30/15/5 over 10k samples within ±3% slack
- Completion-piece bias: regular stage source skips completion piece when other pieces remain
- Boss source allows completion piece even if other pieces also exist
- Dup handling: existing piece → coin trickle, no list mutation
- Completion detection: all pieces collected → `completed_at` set
- Claim once: second claim returns 400
- 8-track piece count distribution: 60/30/10 within ±3% over 1000 samples
- Drop roll on all-complete account returns None (no error)

### Integration

- Full battle-WIN flow: response contains `collection_drop` when RNG fires
- Mid-pursuit dup awards 5 coins
- Boss WIN biases toward completion piece
- 8-track open consumes inventory and grants pieces
- `/collections` API surfaces correct progress per account
- Cosmetic-frame reward (Uncommon) appended to `account.cosmetic_frames_json`
- Currency bundle reward (Rare) credits coins/gems/shards
- Hero-shard reward (Epic) credits to `account.template_shards_json`
- Legendary placeholder grants 200 gems + frame
- `try_complete` doesn't double-fire on subsequent piece drops post-completion (defensive)

### Manual

- Trigger a fresh-account battle loop in dev — observe loot popup on first collection drop
- Trigger collection completion — observe claim CTA + reward grant
- Open an 8-track with 1 piece needed remaining — verify completion piece can roll

---

## 11. Out of scope (deferred to v2)

- **Legendary set-bonus passive design** — current Legendary reward is a placeholder (200 gems + frame). v2 designs the passive (e.g., "+1% gold from stage clears while collection is owned"). Power-creep risk per DO/DON'T rules — needs careful design pass.
- **Myth tier RNG unlock** — completing a Legendary collection has a chance to spawn a hidden Myth track. Item content TBD.
- **Buyable 8-tracks** — Stripe SKU. v2 catalog addition.
- **Shop random rotation** — individual collection pieces appearing in the shop's daily rotation. Requires shop-catalog plumbing.
- **Hero-template-tied collections** — earlier user direction had "1 per character" later resolved to "one-shot pursuit per player." A future variant could tie collections to specific hero templates (collect their lore artifacts) — not in v1.

---

## 12. Summary of new surfaces

| Surface | Type | New |
|---|---|---|
| `Account.collection_progress_json` | DB column (Text, default '{}') | ✓ |
| `Account.eight_tracks` | DB column (Integer, default 0) | ✓ |
| `Collection` table | DB table (seeded) | ✓ |
| `app/collections.py` | Module | ✓ |
| `GET /collections` | Endpoint | ✓ |
| `POST /collections/{code}/claim` | Endpoint | ✓ |
| `POST /collections/8-track/open` | Endpoint | ✓ |
| `frontend/src/api/collections.ts` | TS API client | ✓ |
| `frontend/src/routes/Collections.tsx` | Route | ✓ |
| `frontend/src/components/CollectionLootPopup.tsx` | Component | ✓ |
| Battle-resolve hook in `app/routers/battles.py` | Modification (3 sites: fight / sweep / auto-resolve) | ✓ |
| Weekly chest cycle (existing) | Modification — grant 1 8-track | Light |
| Tower of Trials floor-50 milestone | Modification — grant 1 8-track | Light |
| Raid contribution top-10% | Modification — grant 1 8-track | Light |
| Coach mark on `/collections` nav | One-shot, reuses CoachMark infra | Light |
