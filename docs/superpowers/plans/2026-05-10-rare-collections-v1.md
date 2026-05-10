# Rare Collections v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the v1 rare-collection system — 12 themed collections (4 rarities × 3 level brackets), pieces drop from stages/bosses/raids/8-tracks, completion grants tiered rewards (Uncommon=cosmetic / Rare=currency / Epic=hero shards / Legendary=v1 placeholder).

**Architecture:** New `Collection` seed table holds static content (pieces embedded as JSON). Per-account state lives in two new `Account` columns (`collection_progress_json` + `eight_tracks`). New `app/collections.py` module owns all roll/award/complete/claim logic. Three battle-resolve hooks in `app/routers/battles.py` call into it alongside the existing gear-drop. New `/collections` route + loot popup on frontend.

**Tech Stack:** Python 3.13 + FastAPI + SQLAlchemy 2.0 + Alembic. React 18 + TypeScript + Vite. Tests via `uv run pytest`.

**Spec:** `docs/superpowers/specs/2026-05-10-rare-collections-v1-design.md`

**Reference (grounded codebase facts):**
- `app/models.py:191` — `Account` model location
- `app/models.py:216` — JSON column pattern (`stages_cleared_json: String(1024)`)
- `app/account_level.py:163` — `STORY_CHAPTERS: list[Chapter]` (last stage of each chapter = boss for the 20% drop bonus)
- `app/routers/battles.py:349-383` — main `fight()` gear-drop block (subsystem #5 already added drop-meter + `roll_gear_targeted` here)
- `app/routers/battles.py:728-739` — sweep endpoint gear-drop block
- `app/routers/battles.py:867-882` — auto-resolve gear-drop block
- `app/economy.py` — existing reward pipeline patterns
- `app/security.py:issue_token` — auth helper for tests
- `tests/conftest.py` — has `db_session` + `client` fixtures
- `app/static/spa/` — built SPA artifacts
- `frontend/src/components/CoachMark.tsx` — existing coach-mark infra (subsystem #2 used `localStorage` + the component)

---

## File Structure

| File | Responsibility | Action |
|---|---|---|
| `alembic/versions/<rev>_add_collections.py` | Migration: add 2 columns to `accounts` + create `collections` table. | Create |
| `app/models.py` | Add `Account.collection_progress_json` + `Account.eight_tracks`. Add `Collection` model. | Modify |
| `app/collections.py` | NEW — all collection logic: read progress, roll drop, award piece, detect completion, claim reward, open 8-track, `is_boss_stage` helper. Constants for drop probabilities + rarity weights + 8-track piece-count distribution. | Create |
| `app/seed.py` | Seed the 12 collections (embedded pieces) on startup. | Modify |
| `app/routers/collections.py` | NEW — `/collections` router: `GET ""`, `POST {code}/claim`, `POST 8-track/open`. | Create |
| `app/routers/battles.py` | At each of 3 gear-drop sites: also call `roll_piece_drop` + `award_piece` + `try_complete`. Add the hook for raid contributions in raids router (separate from battles). | Modify |
| `app/routers/raids.py` | Add piece-drop hook to raid attack endpoint (5% rate, raid-pool only). | Modify |
| `app/routers/daily.py` (or wherever weekly chest cycles) | Grant 1 8-track per week. | Modify |
| `app/routers/tower.py` | Grant 1 8-track on first reach of floor 50. | Modify |
| `app/main.py` | Register `/collections` router. | Modify |
| `frontend/src/api/collections.ts` | NEW — TS API client. | Create |
| `frontend/src/types/index.ts` | Add `Collection`, `CollectionPiece`, `CollectionDrop` interfaces + extend `Me` with `eight_tracks`. | Modify |
| `frontend/src/routes/Collections.tsx` | NEW — collections grid route. | Create |
| `frontend/src/components/CollectionLootPopup.tsx` | NEW — loot popup overlay. | Create |
| `frontend/src/components/Layout/Shell.tsx` | Add `/collections` nav entry + coach-mark wrapper. | Modify |
| `frontend/src/App.tsx` | Add route. | Modify |
| `tests/test_collections.py` | NEW — full unit + integration coverage. | Create |

---

## Task 1: Schema + migration + Collection model

**Files:**
- Modify: `app/models.py` — add 2 columns to `Account`, add `Collection` class
- Create: `alembic/versions/<rev>_add_collections.py`
- Test: `tests/test_collections.py` (create)

- [ ] **Step 1: Inspect a recent multi-column / multi-table migration**

Run: `cat alembic/versions/c4f7d8a3e2b9_add_tower_of_trials_columns_to_accounts.py`
Run: `cat alembic/versions/97b78f46b105_add_accounts_stage_drop_pity_json.py`

These show: batch_alter_table for column adds, single-column server_default JSON pattern.

- [ ] **Step 2: Write failing test**

Create `tests/test_collections.py`:

```python
"""Rare-collection v1 tests."""
import json

from app.models import Account, Collection


def test_account_has_collection_columns(db_session):
    """New accounts get an empty collection_progress_json blob and 0 eight_tracks."""
    acc = Account(email="coll_default@example.com", password_hash="x")
    db_session.add(acc)
    db_session.flush()
    db_session.refresh(acc)
    assert acc.collection_progress_json == "{}"
    assert json.loads(acc.collection_progress_json) == {}
    assert acc.eight_tracks == 0


def test_collection_model_exists(db_session):
    """Collection table can store a row with required fields."""
    c = Collection(
        code="test_floppy",
        name="Test Floppy",
        theme="testing",
        rarity="UNCOMMON",
        level_bracket="1-20",
        pieces_json=json.dumps([{"code": "p1", "name": "P1", "icon": "💾", "flavor": "x", "is_completion_piece": False}]),
        reward_json=json.dumps({"kind": "frame", "frame_code": "test"}),
        sort_order=0,
    )
    db_session.add(c)
    db_session.flush()
    db_session.refresh(c)
    assert c.code == "test_floppy"
    assert c.rarity == "UNCOMMON"
```

- [ ] **Step 3: Run test — expect failure**

`uv run pytest tests/test_collections.py -v`
Expected: column-missing or table-missing error.

- [ ] **Step 4: Add columns + Collection model in app/models.py**

In the `Account` class, near the existing JSON columns (e.g., next to `stage_drop_pity_json`), add:

```python
    # Per-account rare-collection progress.
    # Shape: {"<collection_code>": {"pieces": [...], "completed_at": "...", "claimed_at": "..."}}
    # See app/collections.py for the roll/award/complete/claim logic.
    collection_progress_json: Mapped[str] = mapped_column(Text, default="{}", server_default="{}")

    # 8-track loot box inventory count. Earned via weekly chest, tower floor 50,
    # raid top-10%. v2 will add a buyable Stripe SKU.
    eight_tracks: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
```

Then add a new top-level model class (anywhere after `Stage` is fine):

```python
class Collection(Base):
    __tablename__ = "collections"

    code: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    theme: Mapped[str] = mapped_column(String(255), default="")
    rarity: Mapped[str] = mapped_column(String(16))           # UNCOMMON | RARE | EPIC | LEGENDARY
    level_bracket: Mapped[str] = mapped_column(String(8))     # "1-20" | "21-40" | "41-60"
    pieces_json: Mapped[str] = mapped_column(Text, default="[]")
    reward_json: Mapped[str] = mapped_column(Text, default="{}")
    sort_order: Mapped[int] = mapped_column(Integer, default=0, index=True)
```

Make sure `Text` and `Integer` are already imported from sqlalchemy at the top of the file (they should be).

- [ ] **Step 5: Generate Alembic migration**

`uv run alembic revision -m "add collections table + account columns"`

Open the generated file. Replace `upgrade()` and `downgrade()`:

```python
def upgrade() -> None:
    op.create_table(
        "collections",
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("theme", sa.String(length=255), nullable=False, server_default=""),
        sa.Column("rarity", sa.String(length=16), nullable=False),
        sa.Column("level_bracket", sa.String(length=8), nullable=False),
        sa.Column("pieces_json", sa.Text(), nullable=False, server_default="[]"),
        sa.Column("reward_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("code"),
    )
    op.create_index("ix_collections_sort_order", "collections", ["sort_order"])

    with op.batch_alter_table("accounts") as batch_op:
        batch_op.add_column(
            sa.Column("collection_progress_json", sa.Text(), nullable=False, server_default="{}"),
        )
        batch_op.add_column(
            sa.Column("eight_tracks", sa.Integer(), nullable=False, server_default="0"),
        )


def downgrade() -> None:
    with op.batch_alter_table("accounts") as batch_op:
        batch_op.drop_column("eight_tracks")
        batch_op.drop_column("collection_progress_json")
    op.drop_index("ix_collections_sort_order", table_name="collections")
    op.drop_table("collections")
```

Keep auto-generated revision IDs.

- [ ] **Step 6: Verify**

`uv run pytest tests/test_collections.py -v` → 2 PASS
`uv run pytest 2>&1 | tail -5` → 770+ pass with 1 pre-existing failure tolerated

- [ ] **Step 7: Commit**

```bash
git add app/models.py alembic/versions/ tests/test_collections.py
git commit -m "feat(collections): add Collection table + account columns"
```

---

## Task 2: Seed 12 collections

**Files:**
- Modify: `app/seed.py` — add `seed_collections(db)` and call it from the main `seed()` function
- Test: `tests/test_collections.py` (append)

- [ ] **Step 1: Append failing test**

```python
def test_seed_produces_12_collections(db_session):
    """Seed loop creates the 12 v1 collections, 4 rarities × 3 brackets."""
    from sqlalchemy import select
    rows = db_session.scalars(select(Collection)).all()
    rarities = {r.rarity for r in rows}
    brackets = {r.level_bracket for r in rows}
    assert len(rows) == 12, f"expected 12 collections, got {len(rows)}"
    assert rarities == {"UNCOMMON", "RARE", "EPIC", "LEGENDARY"}
    assert brackets == {"1-20", "21-40", "41-60"}
    # Each collection has at least 5 pieces, at most 12.
    for c in rows:
        pieces = json.loads(c.pieces_json)
        assert 5 <= len(pieces) <= 12, f"{c.code}: {len(pieces)} pieces out of range"
        completion_pieces = [p for p in pieces if p["is_completion_piece"]]
        assert len(completion_pieces) == 1, f"{c.code}: must have exactly 1 completion piece"
```

- [ ] **Step 2: Run test — expect FAIL**

Likely fails with 0 rows since the seed isn't wired yet (or will pass coincidentally if conftest ran the existing seed which doesn't populate collections — confirm by inspecting).

`uv run pytest tests/test_collections.py::test_seed_produces_12_collections -v`

- [ ] **Step 3: Add seed function to app/seed.py**

In `app/seed.py`, near the other `seed_*` helpers, add:

```python
def seed_collections(db: Session) -> int:
    """Upsert the 12 v1 collections. Idempotent."""
    from app.models import Collection

    DEFS = [
        # ── 1-20 bracket ──────────────────────────────────────────────────
        {
            "code": "cubicle_detritus",
            "name": "Cubicle Detritus",
            "theme": "The pile under the keyboard.",
            "rarity": "UNCOMMON", "level_bracket": "1-20", "sort_order": 1,
            "pieces": _piece_set([
                ("paperclip_red",   "Red Paperclip",   "📎"),
                ("paperclip_silver","Silver Paperclip","📎"),
                ("postit_yellow",   "Yellow Post-it",  "📒"),
                ("postit_pink",     "Pink Post-it",    "📒"),
                ("rubber_band",     "Rubber Band",     "⭕"),
                ("staple_box",      "Stapler Refill",  "📎"),
                ("pen_chewed",      "Chewed Pen",      "🖊️"),
                ("desk_dust_bunny", "Desk Dust Bunny", "💨"),  # completion
            ], completion_idx=7),
            "reward": {"kind": "frame", "frame_code": "cubicle_archaeologist"},
        },
        {
            "code": "onboarding_kit",
            "name": "Onboarding Kit",
            "theme": "Day-one swag that never quite fits.",
            "rarity": "RARE", "level_bracket": "1-20", "sort_order": 2,
            "pieces": _piece_set([
                ("badge_laminated", "Laminated Badge",  "🪪"),
                ("lanyard_logo",    "Logo Lanyard",     "🎗️"),
                ("welcome_mug",     "Welcome Mug",      "☕"),
                ("stress_ball",     "Stress Ball",      "🎾"),
                ("cable_bagged",    "Bagged USB Cable", "🔌"),
                ("notebook_blank",  "Blank Notebook",   "📔"),
                ("benefits_pdf",    "Benefits PDF (printed)", "📄"),
                ("welcome_keys",    "Welcome Keychain", "🔑"),  # completion
            ], completion_idx=7),
            "reward": {"kind": "currency", "coins": 500, "gems": 50, "shards": 10},
        },
        {
            "code": "helpdesk_starter",
            "name": "Help Desk Starter Pack",
            "theme": "Survival kit for the first three weeks.",
            "rarity": "EPIC", "level_bracket": "1-20", "sort_order": 3,
            "pieces": _piece_set([
                ("spare_kb",       "Spare Keyboard",      "⌨️"),
                ("password_sticky","Password Sticky-note","🔓"),
                ("energy_drink",   "Energy Drink Can",    "🥤"),
                ("ticket_dump",    "Ticket Queue Dump",   "🎫"),
                ("hold_music",     "On-Hold Music CD",    "💿"),
                ("escalation_doc", "Escalation Path PDF", "📋"),
                ("mouse_dirty",    "Crumby Mouse",        "🖱️"),
                ("aspirin_bottle", "Aspirin Bottle",      "💊"),
                ("kvm_switch",     "Old KVM Switch",      "🔀"),
                ("pager_dead",     "Dead Pager",          "📟"),  # completion
            ], completion_idx=9),
            "reward": {"kind": "hero_shards", "amount": 30, "rarity": "EPIC"},
        },
        {
            "code": "y2k_relics",
            "name": "Y2K Survival Relics",
            "theme": "What we hoarded under our desks in 1999.",
            "rarity": "LEGENDARY", "level_bracket": "1-20", "sort_order": 4,
            "pieces": _piece_set([
                ("y2k_bunker_log",  "Bunker Watch Log",     "📓"),
                ("canned_goods",    "Canned Soup Stockpile","🥫"),
                ("battery_pack",    "Battery Pack",         "🔋"),
                ("paper_compliance","Paper Compliance Cert","📜"),
                ("clock_resync",    "Manual Clock Resync",  "⏰"),
                ("backup_tape_dat", "DAT Backup Tape",      "📼"),
                ("flannel_emergency","Emergency Flannel",   "👕"),
                ("noaa_radio",      "NOAA Weather Radio",   "📻"),
                ("disc_install_bsd","BSD Install CD",       "💿"),
                ("pager_text",      "Pager 'all clear' Text","📟"),
                ("y2k_tshirt",      "Limited Y2K T-shirt",  "👕"),
                ("midnight_audit",  "Midnight Audit Receipt","🧾"),  # completion
            ], completion_idx=11),
            "reward": {"kind": "currency", "gems": 200, "frame_code": "legen_waitforit_dary_hoarder"},
        },
        # ── 21-40 bracket ─────────────────────────────────────────────────
        {
            "code": "floppy_boneyard",
            "name": "Floppy Drive Boneyard",
            "theme": "Discs that nobody can read anymore.",
            "rarity": "UNCOMMON", "level_bracket": "21-40", "sort_order": 5,
            "pieces": _piece_set([
                ("floppy_525_blue","5.25\" Floppy (Blue)","💾"),
                ("floppy_525_red","5.25\" Floppy (Red)", "💾"),
                ("floppy_35_black","3.5\" Floppy (Black)","💾"),
                ("floppy_35_color","3.5\" Floppy (Rainbow)","💾"),
                ("zip_disk_100",  "Zip Disk 100MB",      "💽"),
                ("jaz_disk_1gb",  "Jaz Disk 1GB",        "💽"),
                ("ls120_super",   "LS-120 SuperDisk",    "💽"),
                ("floppy_label_handwritten","Handwritten Label Floppy","📝"),  # completion
            ], completion_idx=7),
            "reward": {"kind": "frame", "frame_code": "floppy_whisperer"},
        },
        {
            "code": "paperclip_anthology",
            "name": "Themed Paperclip Anthology",
            "theme": "Curated by someone who clearly had time.",
            "rarity": "RARE", "level_bracket": "21-40", "sort_order": 6,
            "pieces": _piece_set([
                ("clip_butterfly", "Butterfly Clip",   "🦋"),
                ("clip_owl",       "Owl Clip",         "🦉"),
                ("clip_jumbo_gold","Jumbo Gold Clip",  "📎"),
                ("clip_neon_green","Neon Green Clip",  "📎"),
                ("clip_glitter",   "Glitter Clip",     "✨"),
                ("clip_skull",     "Skull Clip",       "💀"),
                ("clip_holiday",   "Limited Holiday Clip","🎄"),
                ("clip_handmade",  "Handmade Beaded Clip","💎"),  # completion
            ], completion_idx=7),
            "reward": {"kind": "currency", "coins": 800, "gems": 80, "shards": 20},
        },
        {
            "code": "server_closet_archaeology",
            "name": "Server Closet Archaeology",
            "theme": "Whatever's been back there since the office moved.",
            "rarity": "EPIC", "level_bracket": "21-40", "sort_order": 7,
            "pieces": _piece_set([
                ("cat5_bent",      "Bent CAT5 Cable",     "🔌"),
                ("ups_dead",       "Dead UPS Battery",    "🔋"),
                ("kvm_old",        "Yellowing KVM",       "🔀"),
                ("dust_bunny_giant","Giant Dust Bunny",   "💨"),
                ("rack_screw",     "Stripped Rack Screw", "🔩"),
                ("ethernet_orange","Orange Crossover",    "🔌"),
                ("label_maker_tape","Old Label Tape Roll","🏷️"),
                ("zip_tie_jungle", "Zip-tie Jungle Cluster","🌿"),
                ("cd_unmarked",    "Unmarked CD-R",       "💿"),
                ("doc_post_it_tower","Tower of Post-its", "📒"),  # completion
            ], completion_idx=9),
            "reward": {"kind": "hero_shards", "amount": 30, "rarity": "EPIC"},
        },
        {
            "code": "legendary_rolodex",
            "name": "The Legendary Rolodex",
            "theme": "Index cards from sysadmins past.",
            "rarity": "LEGENDARY", "level_bracket": "21-40", "sort_order": 8,
            "pieces": _piece_set([
                ("card_dba_pete",   "DBA Pete's Card",      "🗂️"),
                ("card_unix_dave",  "Unix Dave's Card",     "🗂️"),
                ("card_security_lin","Security Lin's Card", "🗂️"),
                ("card_helpdesk_kim","Helpdesk Kim's Card", "🗂️"),
                ("card_vendor_acme","Vendor: ACME Card",    "🗂️"),
                ("card_dev_anita",  "Dev Anita's Card",     "🗂️"),
                ("card_oncall_rota","On-call Rotation Card","🗂️"),
                ("card_consultant", "$300/hr Consultant",   "🗂️"),
                ("card_recruiter",  "External Recruiter",   "🗂️"),
                ("card_unknown",    "Card with No Name",    "🗂️"),
                ("card_legend",     "The 'Just Call Mike'", "🗂️"),
                ("card_origin",     "Founder Card (Original)","🗂️"),  # completion
            ], completion_idx=11),
            "reward": {"kind": "currency", "gems": 200, "frame_code": "rolodex_keeper"},
        },
        # ── 41-60 bracket ─────────────────────────────────────────────────
        {
            "code": "cassette_oddities",
            "name": "Cassette & 8-track Oddities",
            "theme": "The format wars never really ended.",
            "rarity": "UNCOMMON", "level_bracket": "41-60", "sort_order": 9,
            "pieces": _piece_set([
                ("eight_track_clean","Clean 8-track",     "📼"),
                ("eight_track_warped","Warped 8-track",   "📼"),
                ("cassette_metal",  "Type IV Cassette",   "📼"),
                ("cassette_dat",    "DAT Cassette",       "📼"),
                ("vhs_training",    "VHS Training Tape",  "📼"),
                ("betamax_mystery", "Betamax (Unmarked)", "📼"),
                ("microcassette",   "Microcassette",      "📼"),
                ("reel_to_reel",    "Reel-to-reel Spool", "📼"),  # completion
            ], completion_idx=7),
            "reward": {"kind": "frame", "frame_code": "tape_curator"},
        },
        {
            "code": "patch_tuesday_memorial",
            "name": "Patch Tuesday Memorial KBs",
            "theme": "Articles from the long Tuesdays.",
            "rarity": "RARE", "level_bracket": "41-60", "sort_order": 10,
            "pieces": _piece_set([
                ("kb_3024815", "KB3024815 (Reboots)",   "📄"),
                ("kb_4023057", "KB4023057 (Updates)",   "📄"),
                ("kb_legacy",  "KB Legacy 'do not run'","📄"),
                ("kb_hotfix",  "Out-of-band Hotfix",    "📄"),
                ("kb_recall",  "Recalled KB",           "📄"),
                ("kb_security","Critical Security KB",  "📄"),
                ("kb_winter",  "Winter Patch Notes",    "📄"),
                ("kb_orig",    "First Patch Tuesday Memo","📄"),  # completion
            ], completion_idx=7),
            "reward": {"kind": "currency", "coins": 1200, "gems": 100, "shards": 30},
        },
        {
            "code": "forbidden_codebase",
            "name": "The Forbidden Codebase",
            "theme": "Don't touch any of this.",
            "rarity": "EPIC", "level_bracket": "41-60", "sort_order": 11,
            "pieces": _piece_set([
                ("cobol_listing",   "COBOL Listing (Yellow)","📜"),
                ("fortran_card",    "Fortran Punch Card",    "🃏"),
                ("perl_oneliner",   "Perl Oneliner (Sacred)","🐪"),
                ("vb6_form",        "VB6 .frm File",         "🪟"),
                ("delphi_pas",      "Delphi .pas Module",    "📜"),
                ("regex_unholy",    "300-char Regex Print",  "📃"),
                ("makefile_cursed", "Cursed Makefile",       "📜"),
                ("classic_asp",     "Classic ASP File",      "📜"),
                ("xslt_template",   "XSLT Transform",        "📜"),
                ("source_locked",   "Locked .tgz Archive",   "📦"),  # completion
            ], completion_idx=9),
            "reward": {"kind": "hero_shards", "amount": 30, "rarity": "EPIC"},
        },
        {
            "code": "founders_garage",
            "name": "Founder's Garage",
            "theme": "Original prototype hardware.",
            "rarity": "LEGENDARY", "level_bracket": "41-60", "sort_order": 12,
            "pieces": _piece_set([
                ("pcb_original",    "Original PCB",         "🔧"),
                ("breadboard_jumper","Jumper-wire Tangle",  "🧵"),
                ("schematic_napkin","Napkin Schematic",     "📐"),
                ("scope_polaroid",  "Oscilloscope Polaroid","📸"),
                ("solder_iron_old", "Old Soldering Iron",   "🔥"),
                ("ide_floppy_dev",  "Dev IDE on Floppy",    "💾"),
                ("voltmeter_taped", "Taped Voltmeter",      "🧰"),
                ("chip_unmarked",   "Unmarked DIP Chip",    "🔲"),
                ("fan_homemade",    "Homemade CPU Fan",     "🌀"),
                ("logo_first_sketch","First Logo Sketch",   "✏️"),
                ("press_release_v1","V1 Press Release",     "📰"),
                ("garage_key",      "Garage Front-door Key","🗝️"),  # completion
            ], completion_idx=11),
            "reward": {"kind": "currency", "gems": 200, "frame_code": "founders_friend"},
        },
    ]

    added = 0
    for d in DEFS:
        existing = db.get(Collection, d["code"])
        if existing is None:
            db.add(Collection(
                code=d["code"], name=d["name"], theme=d["theme"],
                rarity=d["rarity"], level_bracket=d["level_bracket"],
                pieces_json=json.dumps(d["pieces"]),
                reward_json=json.dumps(d["reward"]),
                sort_order=d["sort_order"],
            ))
            added += 1
        else:
            # Upsert: refresh fields so designer iteration on theme/reward
            # propagates without a manual migration.
            existing.name = d["name"]
            existing.theme = d["theme"]
            existing.rarity = d["rarity"]
            existing.level_bracket = d["level_bracket"]
            existing.pieces_json = json.dumps(d["pieces"])
            existing.reward_json = json.dumps(d["reward"])
            existing.sort_order = d["sort_order"]
    db.commit()
    return added


def _piece_set(items: list[tuple[str, str, str]], *, completion_idx: int) -> list[dict]:
    out = []
    for i, (code, name, icon) in enumerate(items):
        out.append({
            "code": code, "name": name, "icon": icon,
            "flavor": "",
            "is_completion_piece": (i == completion_idx),
        })
    return out
```

- [ ] **Step 4: Wire seed_collections into the main seed() function**

In `app/seed.py`, find the main `seed()` function (line ~1369). Near the end, before `db.commit()` if it exists or before the print, add:

```python
        added_c = seed_collections(db)
```

Add `added_c` to the printed status line at the end of `seed()`:

```python
print(f"seeded heroes+={added_h} stages+={added_s} liveops+={added_l} products+={added_p} offer_bundles+={added_b} guild_achievements+={added_g} collections+={added_c}")
```

(Match the existing print exactly — there's a similar status line.)

- [ ] **Step 5: Run test**

`uv run pytest tests/test_collections.py -v`
Expected: 3 PASS (1 from Task 1 + 1 schema + 1 seed test).

If conftest doesn't auto-run seed, the test may need the existing fixture to call `seed_collections(db_session)` directly. Inspect `tests/conftest.py` to see how other seeded data (heroes, stages) becomes available. If they call `seed()` once per session, the seed will populate the test DB automatically.

If the seed doesn't run automatically: add a fixture-scoped trigger in the test:

```python
@pytest.fixture(autouse=True)
def _seed_collections(db_session):
    from app.seed import seed_collections
    seed_collections(db_session)
```

Place at module level in `tests/test_collections.py`. Re-run.

- [ ] **Step 6: Commit**

```bash
git add app/seed.py tests/test_collections.py
git commit -m "feat(collections): seed 12 themed collections (4 rarities × 3 brackets)"
```

---

## Task 3: app/collections.py helper module

**Files:**
- Create: `app/collections.py`
- Test: `tests/test_collections.py` (append)

- [ ] **Step 1: Append failing tests**

```python
import random
from datetime import datetime

from app.collections import (
    DROP_CHANCE_REGULAR, DROP_CHANCE_BOSS, DROP_CHANCE_RAID,
    EIGHT_TRACK_PIECE_WEIGHTS, RARITY_WEIGHTS,
    bracket_for_level,
    is_boss_stage,
    read_progress,
    award_piece,
    try_complete,
    roll_piece_drop,
    open_eight_track,
    claim_reward,
)


def _make_account(db_session, level=10, eight_tracks=0):
    n = db_session.info.get("counter", 0)
    db_session.info["counter"] = n + 1
    acc = Account(
        email=f"coll_{n}@example.com", password_hash="x",
        account_level=level,
        eight_tracks=eight_tracks,
    )
    db_session.add(acc); db_session.flush()
    return acc


def test_constants():
    assert DROP_CHANCE_REGULAR == 0.07
    assert DROP_CHANCE_BOSS == 0.20
    assert DROP_CHANCE_RAID == 0.05
    assert RARITY_WEIGHTS == {"UNCOMMON": 0.50, "RARE": 0.30, "EPIC": 0.15, "LEGENDARY": 0.05}
    # 8-track piece-count distribution sums to 1.0 within float tolerance
    s = sum(EIGHT_TRACK_PIECE_WEIGHTS.values())
    assert abs(s - 1.0) < 0.001


def test_bracket_for_level():
    assert bracket_for_level(1) == "1-20"
    assert bracket_for_level(20) == "1-20"
    assert bracket_for_level(21) == "21-40"
    assert bracket_for_level(40) == "21-40"
    assert bracket_for_level(41) == "41-60"
    assert bracket_for_level(60) == "41-60"
    assert bracket_for_level(75) == "any"


def test_is_boss_stage():
    """Last stage of any chapter in STORY_CHAPTERS is a boss."""
    from app.account_level import STORY_CHAPTERS
    for chapter in STORY_CHAPTERS:
        if chapter.stages:
            last = chapter.stages[-1].code
            first = chapter.stages[0].code if len(chapter.stages) > 1 else None
            assert is_boss_stage(last) is True, f"last stage of {chapter.code} should be boss"
            if first and first != last:
                assert is_boss_stage(first) is False, f"first stage of {chapter.code} should NOT be boss"
    # Unknown stage codes are not bosses.
    assert is_boss_stage("nonexistent_stage") is False


def test_read_progress_default_empty(db_session):
    acc = _make_account(db_session)
    p = read_progress(acc, "cubicle_detritus")
    assert p["pieces"] == []
    assert p["completed_at"] is None
    assert p["claimed_at"] is None


def test_award_piece_new(db_session):
    from app.seed import seed_collections
    seed_collections(db_session)
    acc = _make_account(db_session)
    status = award_piece(acc, "cubicle_detritus", "paperclip_red")
    assert status == "new"
    p = read_progress(acc, "cubicle_detritus")
    assert "paperclip_red" in p["pieces"]


def test_award_piece_duplicate(db_session):
    from app.seed import seed_collections
    seed_collections(db_session)
    acc = _make_account(db_session)
    award_piece(acc, "cubicle_detritus", "paperclip_red")
    status = award_piece(acc, "cubicle_detritus", "paperclip_red")
    assert status == "duplicate"
    p = read_progress(acc, "cubicle_detritus")
    assert p["pieces"].count("paperclip_red") == 1


def test_try_complete(db_session):
    from app.seed import seed_collections
    from app.models import Collection
    seed_collections(db_session)
    acc = _make_account(db_session)
    c = db_session.get(Collection, "cubicle_detritus")
    pieces = [p["code"] for p in json.loads(c.pieces_json)]
    for code in pieces[:-1]:
        award_piece(acc, "cubicle_detritus", code)
    assert try_complete(acc, "cubicle_detritus") is False  # not yet
    award_piece(acc, "cubicle_detritus", pieces[-1])
    assert try_complete(acc, "cubicle_detritus") is True
    p = read_progress(acc, "cubicle_detritus")
    assert p["completed_at"] is not None


def test_roll_piece_drop_returns_none_with_no_collections_in_bracket(db_session):
    """If the player has no incomplete collections in their bracket, returns None."""
    # Don't seed — DB has no collections — return None.
    acc = _make_account(db_session, level=10)
    rng = random.Random(0)
    drop = roll_piece_drop(db_session, acc, source="stage", rng=rng)
    assert drop is None


def test_roll_piece_drop_picks_from_player_bracket(db_session):
    from app.seed import seed_collections
    seed_collections(db_session)
    acc = _make_account(db_session, level=10)  # bracket 1-20
    rng = random.Random(7)
    drop = roll_piece_drop(db_session, acc, source="stage", rng=rng)
    assert drop is not None
    assert drop.collection_code in {
        "cubicle_detritus", "onboarding_kit", "helpdesk_starter", "y2k_relics",
    }


def test_roll_piece_drop_skips_completed_collections(db_session):
    from app.seed import seed_collections
    from app.models import Collection
    seed_collections(db_session)
    acc = _make_account(db_session, level=10)
    # Force-complete one collection
    c = db_session.get(Collection, "cubicle_detritus")
    pieces = [p["code"] for p in json.loads(c.pieces_json)]
    for code in pieces:
        award_piece(acc, "cubicle_detritus", code)
    try_complete(acc, "cubicle_detritus")
    # Roll 50 times — none should land in cubicle_detritus
    rng = random.Random(0)
    seen = set()
    for _ in range(50):
        drop = roll_piece_drop(db_session, acc, source="stage", rng=rng)
        if drop:
            seen.add(drop.collection_code)
    assert "cubicle_detritus" not in seen


def test_claim_reward_currency(db_session):
    from app.seed import seed_collections
    from app.models import Collection
    seed_collections(db_session)
    acc = _make_account(db_session, level=10)
    initial_coins = acc.coins or 0
    initial_gems = acc.gems or 0
    # Force-complete onboarding_kit (RARE → currency reward)
    c = db_session.get(Collection, "onboarding_kit")
    for p in json.loads(c.pieces_json):
        award_piece(acc, "onboarding_kit", p["code"])
    try_complete(acc, "onboarding_kit")
    granted = claim_reward(db_session, acc, "onboarding_kit")
    assert granted["kind"] == "currency"
    assert acc.coins == initial_coins + 500
    assert acc.gems == initial_gems + 50
    # Second claim raises
    import pytest
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        claim_reward(db_session, acc, "onboarding_kit")


def test_open_eight_track_consumes_inventory(db_session):
    from app.seed import seed_collections
    seed_collections(db_session)
    acc = _make_account(db_session, level=10, eight_tracks=2)
    rng = random.Random(0)
    pieces = open_eight_track(db_session, acc, rng=rng)
    assert acc.eight_tracks == 1
    # Returns 1-3 pieces (or fewer if all complete in bracket)
    assert 1 <= len(pieces) <= 3 or len(pieces) == 0  # 0 only if nothing to drop
    # Second open
    open_eight_track(db_session, acc, rng=rng)
    assert acc.eight_tracks == 0
    # Third open raises
    import pytest
    from fastapi import HTTPException
    with pytest.raises(HTTPException):
        open_eight_track(db_session, acc, rng=rng)
```

- [ ] **Step 2: Run tests — expect ImportError**

`uv run pytest tests/test_collections.py -v`
Expected: ImportError on `app.collections`.

- [ ] **Step 3: Create app/collections.py**

```python
"""Rare-collection v1 engine.

State lives on Account.collection_progress_json:
  {"<collection_code>": {"pieces": [...], "completed_at": "...", "claimed_at": "..."}}

8-track inventory lives on Account.eight_tracks (Integer).

Public API:
- bracket_for_level(level) -> str
- is_boss_stage(stage_code) -> bool
- read_progress(account, collection_code) -> dict
- award_piece(account, collection_code, piece_code) -> "new" | "duplicate"
- try_complete(account, collection_code) -> bool
- roll_piece_drop(db, account, *, source, rng) -> CollectionDrop | None
- open_eight_track(db, account, *, rng) -> list[CollectionDrop]
- claim_reward(db, account, collection_code) -> dict (granted)

Helpers do not commit — the caller (battle resolver, API endpoint) owns the
transaction. Defensive _load returns {} on corrupt JSON.
"""
from __future__ import annotations

import json
import logging
import random
from dataclasses import dataclass
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Account, Collection, HeroInstance, HeroTemplate, Rarity, utcnow

log = logging.getLogger(__name__)

DROP_CHANCE_REGULAR = 0.07
DROP_CHANCE_BOSS = 0.20
DROP_CHANCE_RAID = 0.05

RARITY_WEIGHTS: dict[str, float] = {
    "UNCOMMON": 0.50,
    "RARE":     0.30,
    "EPIC":     0.15,
    "LEGENDARY": 0.05,
}

# 8-track piece count distribution.
EIGHT_TRACK_PIECE_WEIGHTS: dict[int, float] = {1: 0.6, 2: 0.3, 3: 0.1}

# Mid-pursuit dup → small currency drip.
DUP_COIN_AWARD = 5


@dataclass
class CollectionDrop:
    collection_code: str
    piece_code: str
    name: str
    icon: str
    is_completion_piece: bool


def bracket_for_level(level: int) -> str:
    if level <= 20:
        return "1-20"
    if level <= 40:
        return "21-40"
    if level <= 60:
        return "41-60"
    return "any"


def is_boss_stage(stage_code: str) -> bool:
    """True if this stage is the final stage of any narrative chapter."""
    from app.account_level import STORY_CHAPTERS
    for chapter in STORY_CHAPTERS:
        if chapter.stages and chapter.stages[-1].code == stage_code:
            return True
    return False


def _load_all(account: Account) -> dict:
    try:
        return json.loads(account.collection_progress_json or "{}")
    except (json.JSONDecodeError, TypeError):
        log.warning("collection_progress_json corrupt for account=%s; resetting", account.id)
        return {}


def _save_all(account: Account, data: dict) -> None:
    account.collection_progress_json = json.dumps(data)


def read_progress(account: Account, collection_code: str) -> dict:
    """Return the per-collection progress dict. Defaults to empty shape."""
    data = _load_all(account)
    entry = data.get(collection_code) or {}
    return {
        "pieces":      list(entry.get("pieces", [])),
        "completed_at": entry.get("completed_at"),
        "claimed_at":   entry.get("claimed_at"),
    }


def _set_progress(account: Account, collection_code: str, progress: dict) -> None:
    data = _load_all(account)
    data[collection_code] = progress
    _save_all(account, data)


def award_piece(account: Account, collection_code: str, piece_code: str) -> Literal["new", "duplicate"]:
    progress = read_progress(account, collection_code)
    if piece_code in progress["pieces"]:
        # Duplicate — caller handles dup coin trickle.
        return "duplicate"
    progress["pieces"].append(piece_code)
    _set_progress(account, collection_code, progress)
    return "new"


def try_complete(account: Account, collection_code: str) -> bool:
    """Mark completed if all pieces collected. Idempotent."""
    progress = read_progress(account, collection_code)
    if progress["completed_at"] is not None:
        return False  # already completed
    # Look up total piece count from the seed data.
    # We avoid an extra DB roundtrip by caching in a module-level dict; but
    # the simplest correct path is to re-query — Collection.pieces_json is
    # cheap to deserialize.
    from sqlalchemy.orm import object_session
    sess = object_session(account)
    if sess is None:
        return False
    c = sess.get(Collection, collection_code)
    if c is None:
        return False
    total = len(json.loads(c.pieces_json))
    if len(progress["pieces"]) >= total:
        progress["completed_at"] = utcnow().isoformat()
        _set_progress(account, collection_code, progress)
        return True
    return False


def roll_piece_drop(
    db: Session,
    account: Account,
    *,
    source: Literal["stage", "boss", "raid", "8-track"],
    rng: random.Random,
    raid_pool_only: bool = False,
) -> CollectionDrop | None:
    """Pick a random unowned piece for the player. Returns None if nothing eligible."""
    bracket = bracket_for_level(int(account.account_level or 1))

    # Filter candidate collections: in player bracket, incomplete.
    q = select(Collection)
    if bracket != "any":
        q = q.where(Collection.level_bracket == bracket)
    candidates = list(db.scalars(q).all())
    if not candidates:
        return None

    progress_all = _load_all(account)
    candidates = [
        c for c in candidates
        if (progress_all.get(c.code) or {}).get("completed_at") is None
    ]
    if not candidates:
        return None

    # Rarity-weighted pick.
    weights = [RARITY_WEIGHTS.get(c.rarity, 0.01) for c in candidates]
    chosen = rng.choices(candidates, weights=weights, k=1)[0]

    pieces = json.loads(chosen.pieces_json)
    owned = set((progress_all.get(chosen.code) or {}).get("pieces", []))
    unowned = [p for p in pieces if p["code"] not in owned]
    if not unowned:
        return None  # defensive — shouldn't happen if completed_at correctly tracks

    # Completion-piece bias: regular stage source skips completion piece if
    # other pieces remain.
    if source == "stage" and len(unowned) > 1:
        non_completion = [p for p in unowned if not p["is_completion_piece"]]
        if non_completion:
            unowned = non_completion

    chosen_piece = rng.choice(unowned)
    return CollectionDrop(
        collection_code=chosen.code,
        piece_code=chosen_piece["code"],
        name=chosen_piece["name"],
        icon=chosen_piece["icon"],
        is_completion_piece=chosen_piece["is_completion_piece"],
    )


def open_eight_track(
    db: Session,
    account: Account,
    *,
    rng: random.Random,
) -> list[CollectionDrop]:
    """Consume 1 8-track, roll 1-3 pieces. Raises if no inventory."""
    if (account.eight_tracks or 0) <= 0:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "no 8-tracks")
    account.eight_tracks -= 1

    # Weighted piece-count pick.
    counts = list(EIGHT_TRACK_PIECE_WEIGHTS.keys())
    weights = list(EIGHT_TRACK_PIECE_WEIGHTS.values())
    n = rng.choices(counts, weights=weights, k=1)[0]

    drops: list[CollectionDrop] = []
    for _ in range(n):
        drop = roll_piece_drop(db, account, source="8-track", rng=rng)
        if drop is None:
            continue
        status_str = award_piece(account, drop.collection_code, drop.piece_code)
        if status_str == "duplicate":
            account.coins = (account.coins or 0) + DUP_COIN_AWARD
        else:
            try_complete(account, drop.collection_code)
            drops.append(drop)
    return drops


def claim_reward(db: Session, account: Account, collection_code: str) -> dict:
    """Grant the per-collection reward. Raises 400 if not complete or already claimed."""
    progress = read_progress(account, collection_code)
    if progress["completed_at"] is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "collection not complete")
    if progress["claimed_at"] is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "already claimed")

    c = db.get(Collection, collection_code)
    if c is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "collection not found")
    reward = json.loads(c.reward_json)

    granted: dict = {"kind": reward.get("kind")}

    if reward.get("kind") == "frame":
        frame_code = reward["frame_code"]
        try:
            frames = json.loads(account.cosmetic_frames_json or "[]")
        except Exception:
            frames = []
        if frame_code not in frames:
            frames.append(frame_code)
            account.cosmetic_frames_json = json.dumps(frames)
        granted["frame_code"] = frame_code

    elif reward.get("kind") == "currency":
        if "coins" in reward:
            account.coins = (account.coins or 0) + int(reward["coins"])
            granted["coins"] = int(reward["coins"])
        if "gems" in reward:
            account.gems = (account.gems or 0) + int(reward["gems"])
            granted["gems"] = int(reward["gems"])
        if "shards" in reward:
            account.shards = (account.shards or 0) + int(reward["shards"])
            granted["shards"] = int(reward["shards"])
        if "frame_code" in reward:
            try:
                frames = json.loads(account.cosmetic_frames_json or "[]")
            except Exception:
                frames = []
            if reward["frame_code"] not in frames:
                frames.append(reward["frame_code"])
                account.cosmetic_frames_json = json.dumps(frames)
            granted["frame_code"] = reward["frame_code"]

    elif reward.get("kind") == "hero_shards":
        amount = int(reward.get("amount", 0))
        target_rarity = reward.get("rarity", "EPIC")
        # Find an Epic-rarity hero in player's roster; fallback to highest available.
        owned_templates = db.scalars(
            select(HeroTemplate)
            .join(HeroInstance, HeroInstance.template_id == HeroTemplate.id)
            .where(HeroInstance.account_id == account.id)
            .distinct()
        ).all()
        target = next((t for t in owned_templates if t.rarity == target_rarity), None)
        if target is None:
            # Fallback: highest-rarity owned hero.
            rarity_order = {"COMMON": 0, "RARE": 1, "EPIC": 2, "LEGENDARY": 3, "MYTH": 4}
            owned_templates_sorted = sorted(
                owned_templates,
                key=lambda t: rarity_order.get(t.rarity, -1),
                reverse=True,
            )
            target = owned_templates_sorted[0] if owned_templates_sorted else None
        if target is None:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "no heroes to grant shards for; try again after summoning",
            )
        try:
            shards_map = json.loads(account.template_shards_json or "{}")
        except Exception:
            shards_map = {}
        shards_map[target.code] = int(shards_map.get(target.code, 0)) + amount
        account.template_shards_json = json.dumps(shards_map)
        granted["template_code"] = target.code
        granted["amount"] = amount

    progress["claimed_at"] = utcnow().isoformat()
    _set_progress(account, collection_code, progress)
    return granted
```

- [ ] **Step 4: Run tests**

`uv run pytest tests/test_collections.py -v`
Expected: 13+ PASS (1 schema + 1 seed + ~11 helper tests).

- [ ] **Step 5: Commit**

```bash
git add app/collections.py tests/test_collections.py
git commit -m "feat(collections): collection engine (read/award/complete/claim/8-track)"
```

---

## Task 4: Wire into 3 battle drop sites

**Files:**
- Modify: `app/routers/battles.py` — at gear-drop blocks ~349, ~728, ~867
- Test: `tests/test_collections.py` (append integration tests)

The wiring shape mirrors the drop-meter integration from subsystem #5 (commit `9ab3530`). At each WIN-gated block, after the existing drop-meter logic, also roll for collection pieces.

- [ ] **Step 1: Append failing integration test**

```python
def test_battle_win_can_drop_collection_piece(client, db_session):
    """A battle WIN occasionally fires a collection_drop in rewards_extra."""
    from sqlalchemy import select
    from app.models import Account, HeroInstance, HeroTemplate, Rarity, Stage, StageDifficulty
    from app.security import issue_token
    from app.seed import seed_collections

    seed_collections(db_session)
    acc = Account(email="coll_battle@example.com", password_hash="x", account_level=5)
    db_session.add(acc); db_session.flush()

    normal = db_session.scalar(
        select(Stage).where(Stage.difficulty_tier == StageDifficulty.NORMAL).limit(1)
    )
    epic_tmpl = db_session.scalar(
        select(HeroTemplate).where(HeroTemplate.rarity == Rarity.EPIC).limit(1)
    ) or db_session.scalar(select(HeroTemplate).limit(1))

    hero_ids: list[int] = []
    for _ in range(3):
        hi = HeroInstance(account_id=acc.id, template_id=epic_tmpl.id, level=50, xp=0, stars=5)
        db_session.add(hi); db_session.flush()
        hero_ids.append(hi.id)
    db_session.commit()

    token = issue_token(acc.id, acc.token_version)
    # Run battles until we see a collection_drop or hit a sane upper bound (drop is 7%).
    saw_drop = False
    for _ in range(60):
        r = client.post(
            "/battles",
            headers={"Authorization": f"Bearer {token}"},
            json={"stage_id": normal.id, "team": hero_ids},
        )
        body = r.json()
        if r.status_code == 201 and body.get("rewards", {}).get("collection_drop"):
            saw_drop = True
            break
    # 60 trials at 7% = ~98% probability of at least one drop.
    assert saw_drop, "no collection drop after 60 battles — drop wiring may be broken"
```

- [ ] **Step 2: Run test — expect FAIL**

`uv run pytest tests/test_collections.py::test_battle_win_can_drop_collection_piece -v`
Expected: FAIL — battles.py doesn't roll collection pieces yet.

- [ ] **Step 3: Wire site 1 (main fight, lines ~349-383)**

Read the current main `fight()` gear-drop block. At its end (after the existing gear `if do_drop:` block from subsystem #5), add:

```python
        # Collection piece roll — independent of gear/drop-meter logic.
        from app.collections import (
            roll_piece_drop as _coll_roll,
            award_piece as _coll_award,
            try_complete as _coll_complete,
            is_boss_stage as _coll_is_boss,
            DROP_CHANCE_REGULAR as _COLL_PR,
            DROP_CHANCE_BOSS as _COLL_PB,
            DUP_COIN_AWARD as _COLL_DUP,
        )
        _coll_p = _COLL_PB if _coll_is_boss(stage.code) else _COLL_PR
        if rng.random() < _coll_p:
            src = "boss" if _coll_is_boss(stage.code) else "stage"
            _drop = _coll_roll(db, account, source=src, rng=rng)
            if _drop is not None:
                _status = _coll_award(account, _drop.collection_code, _drop.piece_code)
                if _status == "duplicate":
                    account.coins = (account.coins or 0) + _COLL_DUP
                    rewards_extra["collection_dup_coins"] = _COLL_DUP
                else:
                    rewards_extra["collection_drop"] = {
                        "collection_code": _drop.collection_code,
                        "piece_code":      _drop.piece_code,
                        "name":            _drop.name,
                        "icon":            _drop.icon,
                        "is_completion_piece": _drop.is_completion_piece,
                    }
                    if _coll_complete(account, _drop.collection_code):
                        rewards_extra["collection_completed"] = _drop.collection_code
```

Place this block inside the existing `if outcome == BattleOutcome.WIN:` guard, right after the gear-drop block ends.

- [ ] **Step 4: Wire site 2 (sweep, lines ~728-739)**

Find the sweep endpoint's gear-drop block. After the existing `do_drop` block, add the same pattern (using `rng` since sweep uses local rng):

```python
            # Collection piece roll (sweep).
            from app.collections import (
                roll_piece_drop as _coll_roll,
                award_piece as _coll_award,
                try_complete as _coll_complete,
                is_boss_stage as _coll_is_boss,
                DROP_CHANCE_REGULAR as _COLL_PR,
                DROP_CHANCE_BOSS as _COLL_PB,
                DUP_COIN_AWARD as _COLL_DUP,
            )
            _coll_p = _COLL_PB if _coll_is_boss(stage.code) else _COLL_PR
            if rng.random() < _coll_p:
                src = "boss" if _coll_is_boss(stage.code) else "stage"
                _drop = _coll_roll(db, account, source=src, rng=rng)
                if _drop is not None:
                    _status = _coll_award(account, _drop.collection_code, _drop.piece_code)
                    if _status == "duplicate":
                        account.coins = (account.coins or 0) + _COLL_DUP
                    else:
                        if _coll_complete(account, _drop.collection_code):
                            pass  # sweep doesn't surface a popup; UI can detect via /collections poll
```

Sweep's response shape doesn't have a `rewards_extra` per battle, so collection drops are silently awarded — the player will see them in the /collections route.

- [ ] **Step 5: Wire site 3 (auto-resolve, lines ~867-882)**

Same pattern as site 1 but use `session.rng` and write into the auto-resolve `rewards_extra`:

```python
        # Collection piece roll (auto-resolve).
        from app.collections import (
            roll_piece_drop as _coll_roll,
            award_piece as _coll_award,
            try_complete as _coll_complete,
            is_boss_stage as _coll_is_boss,
            DROP_CHANCE_REGULAR as _COLL_PR,
            DROP_CHANCE_BOSS as _COLL_PB,
            DUP_COIN_AWARD as _COLL_DUP,
        )
        _coll_p = _COLL_PB if _coll_is_boss(stage.code) else _COLL_PR
        if session.rng.random() < _coll_p:
            src = "boss" if _coll_is_boss(stage.code) else "stage"
            _drop = _coll_roll(db, account, source=src, rng=session.rng)
            if _drop is not None:
                _status = _coll_award(account, _drop.collection_code, _drop.piece_code)
                if _status == "duplicate":
                    account.coins = (account.coins or 0) + _COLL_DUP
                    rewards_extra["collection_dup_coins"] = _COLL_DUP
                else:
                    rewards_extra["collection_drop"] = {
                        "collection_code": _drop.collection_code,
                        "piece_code":      _drop.piece_code,
                        "name":            _drop.name,
                        "icon":            _drop.icon,
                        "is_completion_piece": _drop.is_completion_piece,
                    }
                    if _coll_complete(account, _drop.collection_code):
                        rewards_extra["collection_completed"] = _drop.collection_code
```

- [ ] **Step 6: Wire raid contributions (separate file)**

In `app/routers/raids.py`, find the attack endpoint where raid contributions are recorded (look for `RAID_CONTRIBUTED` event already wired). Right after the contribution succeeds (and only on WIN-equivalent), add a 5%-rate roll calling `roll_piece_drop` with `source="raid"`. Raid-pool restriction (raid-only collections) is **out of scope for v1** — v1 uses the same 12 collections; v2 will partition raid-specific ones. Document the deferral with a comment.

```python
# Raid-attack collection drop (5% rate). v1 uses the regular 12 collections;
# v2 will partition raid-specific collections via a `is_raid_pool` flag on
# Collection. Defer until raid collection content exists.
import random as _rand
_raid_rng = _rand.Random()
if _raid_rng.random() < 0.05:
    from app.collections import (
        roll_piece_drop as _coll_roll,
        award_piece as _coll_award,
        try_complete as _coll_complete,
        DUP_COIN_AWARD as _COLL_DUP,
    )
    _drop = _coll_roll(db, account, source="raid", rng=_raid_rng)
    if _drop is not None:
        _status = _coll_award(account, _drop.collection_code, _drop.piece_code)
        if _status == "duplicate":
            account.coins = (account.coins or 0) + _COLL_DUP
        else:
            _coll_complete(account, _drop.collection_code)
```

- [ ] **Step 7: Run integration test**

`uv run pytest tests/test_collections.py::test_battle_win_can_drop_collection_piece -v`
Expected: PASS within 60 trials.

- [ ] **Step 8: Run regression sweep**

`uv run pytest tests/test_battles.py tests/test_combat.py tests/test_collections.py 2>&1 | tail -10`
`uv run pytest 2>&1 | tail -5`
Expected: 770+ pass with 1 pre-existing failure tolerated.

- [ ] **Step 9: Commit**

```bash
git add app/routers/battles.py app/routers/raids.py tests/test_collections.py
git commit -m "feat(collections): wire piece drops into 3 battle sites + raid contributions"
```

---

## Task 5: /collections API + router registration

**Files:**
- Create: `app/routers/collections.py`
- Modify: `app/main.py` to register the router
- Modify: `app/schemas.py` to add response schemas (optional — can also use plain dicts)
- Test: `tests/test_collections.py` (append)

- [ ] **Step 1: Append failing tests**

```python
def test_collections_api_returns_progress(client, db_session):
    from app.models import Account
    from app.security import issue_token
    from app.seed import seed_collections

    seed_collections(db_session)
    acc = Account(email="coll_api@example.com", password_hash="x", account_level=10)
    db_session.add(acc); db_session.commit()

    token = issue_token(acc.id, acc.token_version)
    r = client.get("/collections", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    rows = r.json()
    assert len(rows) == 12
    sample = next(r for r in rows if r["code"] == "cubicle_detritus")
    assert sample["name"] == "Cubicle Detritus"
    assert sample["rarity"] == "UNCOMMON"
    assert sample["level_bracket"] == "1-20"
    assert sample["owned_count"] == 0
    assert sample["total_count"] >= 5
    assert sample["claimable"] is False
    # Pieces array hides flavor on un-owned silhouettes (still has code/name/icon)
    for p in sample["pieces"]:
        assert "code" in p and "name" in p and "icon" in p
        assert "owned" in p


def test_collections_claim_grants_reward(client, db_session):
    from app.models import Account, Collection
    from app.security import issue_token
    from app.seed import seed_collections
    from app.collections import award_piece, try_complete

    seed_collections(db_session)
    acc = Account(email="coll_claim@example.com", password_hash="x", account_level=10, coins=0, gems=0)
    db_session.add(acc); db_session.flush()
    # Force-complete onboarding_kit (RARE → currency)
    c = db_session.get(Collection, "onboarding_kit")
    for p in json.loads(c.pieces_json):
        award_piece(acc, "onboarding_kit", p["code"])
    try_complete(acc, "onboarding_kit")
    db_session.commit()

    token = issue_token(acc.id, acc.token_version)
    r = client.post("/collections/onboarding_kit/claim", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["granted"]["kind"] == "currency"
    assert body["granted"]["coins"] == 500

    # Second claim returns 400.
    r2 = client.post("/collections/onboarding_kit/claim", headers={"Authorization": f"Bearer {token}"})
    assert r2.status_code == 400


def test_collections_8track_requires_inventory(client, db_session):
    from app.models import Account
    from app.security import issue_token
    from app.seed import seed_collections

    seed_collections(db_session)
    acc = Account(email="coll_8t@example.com", password_hash="x", account_level=10, eight_tracks=0)
    db_session.add(acc); db_session.commit()

    token = issue_token(acc.id, acc.token_version)
    r = client.post("/collections/8-track/open", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 400
    assert "no 8-tracks" in r.json().get("detail", "").lower()


def test_collections_8track_consumes_and_returns_pieces(client, db_session):
    from app.models import Account
    from app.security import issue_token
    from app.seed import seed_collections

    seed_collections(db_session)
    acc = Account(email="coll_8t2@example.com", password_hash="x", account_level=10, eight_tracks=1)
    db_session.add(acc); db_session.commit()

    token = issue_token(acc.id, acc.token_version)
    r = client.post("/collections/8-track/open", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200, r.text
    body = r.json()
    # 0-3 pieces returned (0 only if all candidate collections complete — not the case here)
    assert "pieces" in body
    # Inventory consumed regardless.
    db_session.refresh(acc)
    assert acc.eight_tracks == 0
```

- [ ] **Step 2: Run tests — expect 404**

`uv run pytest tests/test_collections.py -k "api or claim or 8track" -v`
Expected: 404 routes don't exist yet.

- [ ] **Step 3: Create app/routers/collections.py**

```python
"""Collections endpoints.

GET  /collections                     — all 12 collections + per-account progress
POST /collections/{code}/claim         — claim completed reward
POST /collections/8-track/open         — consume 1 8-track, return 1-3 pieces
"""
from __future__ import annotations

import json
import random
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.collections import (
    claim_reward, open_eight_track, read_progress,
)
from app.db import get_db
from app.deps import get_current_account
from app.models import Account, Collection

router = APIRouter(prefix="/collections", tags=["collections"])


def _summarize_reward(reward: dict) -> str:
    kind = reward.get("kind")
    if kind == "frame":
        return f"Cosmetic frame: {reward.get('frame_code', '?')}"
    if kind == "currency":
        bits = []
        if reward.get("coins"): bits.append(f"{reward['coins']} coins")
        if reward.get("gems"): bits.append(f"{reward['gems']} gems")
        if reward.get("shards"): bits.append(f"{reward['shards']} shards")
        if reward.get("frame_code"): bits.append(f"frame: {reward['frame_code']}")
        return ", ".join(bits) or "currency"
    if kind == "hero_shards":
        return f"{reward.get('amount', 0)} hero shards ({reward.get('rarity', 'EPIC')})"
    return "?"


@router.get("")
def list_collections(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> list[dict]:
    rows = list(db.scalars(select(Collection).order_by(Collection.sort_order)).all())
    out = []
    for c in rows:
        pieces_def = json.loads(c.pieces_json)
        progress = read_progress(account, c.code)
        owned = set(progress["pieces"])
        out.append({
            "code": c.code,
            "name": c.name,
            "theme": c.theme,
            "rarity": c.rarity,
            "level_bracket": c.level_bracket,
            "pieces": [
                {
                    "code": p["code"],
                    "name": p["name"],
                    "icon": p["icon"],
                    "owned": p["code"] in owned,
                    "is_completion_piece": p["is_completion_piece"],
                }
                for p in pieces_def
            ],
            "owned_count": len(owned),
            "total_count": len(pieces_def),
            "completed_at": progress["completed_at"],
            "claimed_at":   progress["claimed_at"],
            "claimable":    progress["completed_at"] is not None and progress["claimed_at"] is None,
            "reward_summary": _summarize_reward(json.loads(c.reward_json)),
        })
    return out


@router.post("/{code}/claim")
def claim_collection(
    code: str,
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    if db.get(Collection, code) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "collection not found")
    granted = claim_reward(db, account, code)
    db.commit()
    return {"granted": granted}


@router.post("/8-track/open")
def open_8track_endpoint(
    account: Annotated[Account, Depends(get_current_account)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    rng = random.SystemRandom()
    drops = open_eight_track(db, account, rng=rng)
    db.commit()
    return {
        "pieces": [
            {
                "collection_code": d.collection_code,
                "piece_code":      d.piece_code,
                "name":            d.name,
                "icon":            d.icon,
                "is_completion_piece": d.is_completion_piece,
            }
            for d in drops
        ]
    }
```

- [ ] **Step 4: Register router in app/main.py**

In `app/main.py`, find where other routers are imported/registered (search for `from app.routers import`). Add:

```python
from app.routers import collections as collections_router
...
app.include_router(collections_router.router)
```

Match the existing import + include style.

- [ ] **Step 5: Run tests**

`uv run pytest tests/test_collections.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add app/routers/collections.py app/main.py tests/test_collections.py
git commit -m "feat(collections): /collections API + claim + 8-track open"
```

---

## Task 6: 8-track grant sources

**Files:**
- Modify: weekly chest source (likely `app/routers/daily.py` or `app/worker.py`'s daily reset hook)
- Modify: `app/routers/tower.py` — grant 1 8-track on first reach of floor 50
- Modify: raid contribution top-10% — likely a periodic `app/worker.py` task that closes raids

These are 3 small drop-in additions. Investigate each existing flow carefully; the "weekly chest" may not exist yet as a named thing — check the daily/weekly reward cycle in `app/routers/daily.py`.

- [ ] **Step 1: Find weekly chest and tower-floor and raid-close hooks**

Run: `grep -rnE "weekly|week_chest|chest_grant" app/ --include="*.py" | head -10`
Run: `grep -nE "tower.*floor|floor.*reached|TOWER_FLOOR_MILESTONE" app/routers/tower.py | head`
Run: `grep -rnE "raid.*close|finalize_raid|raid_complete" app/ --include="*.py" | head -10`

Document what you find and pick the right hook point per flow.

- [ ] **Step 2: Append integration test**

```python
def test_tower_floor_50_grants_eight_track(client, db_session):
    """First time the player records floor 50 in tower, they get 1 8-track."""
    from app.models import Account
    from app.security import issue_token
    from app.seed import seed_collections

    seed_collections(db_session)
    acc = Account(
        email="coll_tower@example.com", password_hash="x",
        account_level=70, eight_tracks=0,
        tower_best_floor=49,
    )
    db_session.add(acc); db_session.commit()

    # Simulate floor-50 reach via the existing tower API.
    # The exact endpoint depends on how tower records floor reaches —
    # check app/routers/tower.py and adapt.
    # For this test, force the state and call the grant helper directly:
    from app.collections import grant_eight_track  # we'll add this helper
    grant_eight_track(acc, source="tower_floor_50")
    db_session.commit()
    db_session.refresh(acc)
    assert acc.eight_tracks == 1

    # Idempotent: can't claim twice.
    grant_eight_track(acc, source="tower_floor_50")
    db_session.refresh(acc)
    assert acc.eight_tracks == 1, "second floor-50 grant should not stack"
```

- [ ] **Step 3: Add `grant_eight_track` idempotency helper to app/collections.py**

```python
def grant_eight_track(account: Account, *, source: str) -> bool:
    """Grant 1 8-track to the account if this `source` hasn't already paid out
    for this player. Returns True if granted, False if already granted.

    Idempotency tracked under account.collection_progress_json["_eight_track_grants"]
    (a list of source codes already claimed). For repeating sources (weekly chest)
    the source code should include the period — e.g., "weekly_2026_w19".
    """
    data = _load_all(account)
    granted = data.setdefault("_eight_track_grants", [])
    if source in granted:
        return False
    granted.append(source)
    data["_eight_track_grants"] = granted
    _save_all(account, data)
    account.eight_tracks = (account.eight_tracks or 0) + 1
    return True
```

- [ ] **Step 4: Wire grant_eight_track into 3 sources**

**Tower floor 50** — in `app/routers/tower.py`, find where `account.tower_best_floor` is updated. Add:

```python
if int(account.tower_best_floor or 0) < 50 and new_floor >= 50:
    from app.collections import grant_eight_track
    grant_eight_track(account, source="tower_floor_50")
```

**Weekly chest** — find the daily/weekly cycle code. The pattern `daily_streak`, `last_daily_claim_at` exists; weekly is likely an addition. If no explicit weekly chest exists yet, create one with the source key `f"weekly_{iso_year}_{iso_week}"` derived from `utcnow()`. Add it inside the existing daily-bonus claim endpoint:

```python
# After the existing daily-streak grant block:
from datetime import date as _date
year, week, _ = _date.today().isocalendar()
weekly_key = f"weekly_{year}_w{week:02d}"
from app.collections import grant_eight_track
grant_eight_track(account, source=weekly_key)
```

**Raid top-10%** — in `app/worker.py`'s raid-close logic (or wherever raid finalization happens), after computing the per-attacker contribution percentile:

```python
# Top 10% of contributors get an 8-track.
top_threshold = sorted_contribs[int(len(sorted_contribs) * 0.1) or 1].damage
for contrib in sorted_contribs:
    if contrib.damage >= top_threshold:
        from app.collections import grant_eight_track
        grant_eight_track(contrib.account, source=f"raid_{raid.id}")
```

Adapt to the actual data structure exposed by raid finalization.

- [ ] **Step 5: Run tests**

`uv run pytest tests/test_collections.py -v`
`uv run pytest tests/test_tower.py tests/test_raids.py tests/test_daily*.py 2>&1 | tail -10`
Expected: regression suite still green.

- [ ] **Step 6: Commit**

```bash
git add app/collections.py app/routers/tower.py app/routers/daily.py app/worker.py tests/test_collections.py
git commit -m "feat(collections): grant 8-tracks from weekly chest, tower floor 50, raid top 10%"
```

(Add only the files you actually modified — the worker.py wire-up may live elsewhere.)

---

## Task 7: Frontend — types, API, route, popup, nav

**Files:**
- Modify: `frontend/src/types/index.ts` — add Collection, CollectionPiece, CollectionDrop interfaces; extend Me with `eight_tracks`
- Create: `frontend/src/api/collections.ts`
- Create: `frontend/src/routes/Collections.tsx`
- Create: `frontend/src/components/CollectionLootPopup.tsx`
- Modify: `frontend/src/components/Layout/Shell.tsx` — add nav entry + coach mark
- Modify: `frontend/src/App.tsx` — register route
- Modify: `app/routers/me.py` + `app/schemas.py` — surface `eight_tracks` in /me response

- [ ] **Step 1: Surface eight_tracks via /me**

In `app/schemas.py`, add `eight_tracks: int = 0` to MeOut.

In `app/routers/me.py`, add `eight_tracks=account.eight_tracks or 0` to the MeOut construction.

Append a backend test:

```python
def test_me_includes_eight_tracks(client, db_session):
    from app.models import Account
    from app.security import issue_token
    acc = Account(email="me_8t@example.com", password_hash="x", eight_tracks=3)
    db_session.add(acc); db_session.commit()
    token = issue_token(acc.id, acc.token_version)
    r = client.get("/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["eight_tracks"] == 3
```

Run: `uv run pytest tests/test_collections.py::test_me_includes_eight_tracks -v`
Expected: PASS.

- [ ] **Step 2: Add TS interfaces**

In `frontend/src/types/index.ts`, find the `Me` interface. Append:

```typescript
eight_tracks: number;
```

At the end of the file, add:

```typescript
export interface CollectionPiece {
  code: string;
  name: string;
  icon: string;
  owned: boolean;
  is_completion_piece: boolean;
}

export interface Collection {
  code: string;
  name: string;
  theme: string;
  rarity: 'UNCOMMON' | 'RARE' | 'EPIC' | 'LEGENDARY';
  level_bracket: '1-20' | '21-40' | '41-60';
  pieces: CollectionPiece[];
  owned_count: number;
  total_count: number;
  completed_at: string | null;
  claimed_at: string | null;
  claimable: boolean;
  reward_summary: string;
}

export interface CollectionDrop {
  collection_code: string;
  piece_code: string;
  name: string;
  icon: string;
  is_completion_piece: boolean;
}
```

If `frontend/src/test/types.test.ts` has fixtures for `Me`, add `eight_tracks: 0` to them (mirrors how subsystem #4 patched the fixture).

- [ ] **Step 3: Create frontend/src/api/collections.ts**

```typescript
import { apiGet, apiPost } from './client';
import type { Collection, CollectionDrop } from '../types';

export const fetchCollections = (): Promise<Collection[]> =>
  apiGet<Collection[]>('/collections');

export const claimCollection = (code: string): Promise<{ granted: Record<string, unknown> }> =>
  apiPost<{ granted: Record<string, unknown> }>(`/collections/${code}/claim`, {});

export const openEightTrack = (): Promise<{ pieces: CollectionDrop[] }> =>
  apiPost<{ pieces: CollectionDrop[] }>('/collections/8-track/open', {});
```

(Match the project's existing apiGet/apiPost helper signatures from another `frontend/src/api/*.ts` file.)

- [ ] **Step 4: Create frontend/src/routes/Collections.tsx**

```tsx
import { useState } from 'react';
import { useQuery, useQueryClient, useMutation } from '@tanstack/react-query';
import { fetchCollections, claimCollection, openEightTrack } from '../api/collections';
import { useMe } from '../hooks/useMe';
import { toast } from '../store/ui';
import type { Collection } from '../types';

const RARITY_ORDER: Collection['rarity'][] = ['UNCOMMON', 'RARE', 'EPIC', 'LEGENDARY'];
const RARITY_COLOR: Record<Collection['rarity'], string> = {
  UNCOMMON: '#9ad36a', RARE: '#5fb1ff', EPIC: '#c878ff', LEGENDARY: '#f5c842',
};

export default function CollectionsRoute() {
  const { data: me } = useMe();
  const qc = useQueryClient();
  const [filter, setFilter] = useState<'all' | Collection['rarity'] | 'completed'>('all');

  const { data: collections, isLoading } = useQuery({
    queryKey: ['collections'],
    queryFn: fetchCollections,
  });

  const claim = useMutation({
    mutationFn: claimCollection,
    onSuccess: (res, code) => {
      toast.success(`Claimed: ${JSON.stringify(res.granted)}`);
      qc.invalidateQueries({ queryKey: ['collections'] });
      qc.invalidateQueries({ queryKey: ['me'] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Claim failed'),
  });

  const open8 = useMutation({
    mutationFn: openEightTrack,
    onSuccess: (res) => {
      const n = res.pieces.length;
      toast.success(n > 0 ? `Got ${n} piece(s) from 8-track` : '8-track contained dust');
      qc.invalidateQueries({ queryKey: ['collections'] });
      qc.invalidateQueries({ queryKey: ['me'] });
    },
    onError: (e) => toast.error(e instanceof Error ? e.message : 'Open failed'),
  });

  if (isLoading) return <div className="muted" style={{ padding: 16 }}>Loading…</div>;
  if (!collections) return null;

  const filtered = collections.filter(c =>
    filter === 'all' ? true
    : filter === 'completed' ? c.completed_at !== null
    : c.rarity === filter
  );

  // Group by bracket, then by rarity within bracket.
  const grouped = new Map<string, Collection[]>();
  for (const c of filtered) {
    const arr = grouped.get(c.level_bracket) ?? [];
    arr.push(c);
    grouped.set(c.level_bracket, arr);
  }

  return (
    <div style={{ padding: 16, maxWidth: 1100, margin: '0 auto' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 16 }}>
        <h2 style={{ margin: 0 }}>Collections</h2>
        <span className="muted" style={{ fontSize: 13 }}>
          🎵 8-tracks: <strong>{me?.eight_tracks ?? 0}</strong>
        </span>
        <button
          className="primary"
          disabled={(me?.eight_tracks ?? 0) <= 0 || open8.isPending}
          onClick={() => open8.mutate()}
          style={{ marginLeft: 'auto' }}
        >
          {open8.isPending ? '…' : 'Open 8-track'}
        </button>
      </div>

      <div style={{ display: 'flex', gap: 8, marginBottom: 16, flexWrap: 'wrap' }}>
        {(['all', ...RARITY_ORDER, 'completed'] as const).map(f => (
          <button
            key={f}
            className={filter === f ? 'primary' : 'secondary'}
            onClick={() => setFilter(f)}
            style={{ fontSize: 12, padding: '4px 10px' }}
          >
            {f === 'all' ? 'All' : f === 'completed' ? 'Show completed' : f}
          </button>
        ))}
      </div>

      {[...grouped.entries()].sort().map(([bracket, items]) => (
        <div key={bracket} style={{ marginBottom: 24 }}>
          <h3 style={{ marginBottom: 12 }}>Level {bracket}</h3>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: 12 }}>
            {items.map(c => (
              <div
                key={c.code}
                style={{
                  border: `2px solid ${RARITY_COLOR[c.rarity]}`,
                  borderRadius: 'var(--radius)',
                  padding: 14,
                  background: 'var(--panel)',
                  position: 'relative',
                }}
              >
                <div style={{ display: 'flex', alignItems: 'baseline', gap: 8 }}>
                  <strong>{c.name}</strong>
                  <span style={{ fontSize: 11, color: RARITY_COLOR[c.rarity], fontWeight: 700 }}>
                    {c.rarity}
                  </span>
                </div>
                <div className="muted" style={{ fontSize: 12, margin: '4px 0 10px' }}>{c.theme}</div>
                <div style={{ fontSize: 12, marginBottom: 8 }}>
                  {c.owned_count} / {c.total_count}
                </div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginBottom: 10 }}>
                  {c.pieces.map(p => (
                    <span
                      key={p.code}
                      title={p.owned ? p.name : '???'}
                      style={{
                        width: 28, height: 28,
                        display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                        background: p.owned ? 'var(--bg-inset)' : 'transparent',
                        border: `1px solid ${p.owned ? 'var(--border)' : 'var(--muted)'}`,
                        borderRadius: 4,
                        fontSize: 16,
                        opacity: p.owned ? 1 : 0.25,
                      }}
                    >
                      {p.owned ? p.icon : '·'}
                    </span>
                  ))}
                </div>
                <div className="muted" style={{ fontSize: 11, marginBottom: 8 }}>
                  Reward: {c.reward_summary}
                </div>
                {c.claimable && (
                  <button
                    className="primary"
                    onClick={() => claim.mutate(c.code)}
                    disabled={claim.isPending}
                    style={{ width: '100%', background: '#f5c842', color: '#0b0d10' }}
                  >
                    {claim.isPending ? '…' : 'Claim Reward'}
                  </button>
                )}
                {c.claimed_at && (
                  <div style={{ fontSize: 11, color: '#9ad36a' }}>✓ Claimed</div>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 5: Create frontend/src/components/CollectionLootPopup.tsx**

```tsx
import type { CollectionDrop } from '../types';

interface Props {
  drop: CollectionDrop;
  progress: { owned: number; total: number };
  onInspect: () => void;
  onClose: () => void;
}

export function CollectionLootPopup({ drop, progress, onInspect, onClose }: Props) {
  const isCompletion = drop.is_completion_piece;
  return (
    <div style={{
      position: 'fixed', bottom: 24, left: 0, right: 0, display: 'flex', justifyContent: 'center', zIndex: 1100,
      pointerEvents: 'none',
    }}>
      <div style={{
        background: 'linear-gradient(135deg, #0b0d10 0%, #1a1f24 100%)',
        border: `2px solid ${isCompletion ? '#f5c842' : '#7ad6ff'}`,
        borderRadius: 12,
        padding: '14px 20px',
        minWidth: 340, maxWidth: 480,
        boxShadow: '0 12px 28px rgba(0,0,0,0.5), 0 0 24px rgba(245,200,66,0.2)',
        pointerEvents: 'auto',
        animation: 'collection-pop 0.4s ease-out',
      }}>
        <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1.5, color: isCompletion ? '#f5c842' : '#7ad6ff', marginBottom: 8 }}>
          {isCompletion ? '⭐ COMPLETION PIECE' : '📜 COLLECTION FIND'}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
          <span style={{ fontSize: 32 }}>{drop.icon}</span>
          <div style={{ flex: 1 }}>
            <div style={{ fontWeight: 700 }}>{drop.name}</div>
            <div className="muted" style={{ fontSize: 11 }}>{drop.collection_code}</div>
            <div style={{ height: 6, background: 'var(--bg-inset)', borderRadius: 3, marginTop: 6, overflow: 'hidden' }}>
              <div style={{
                height: '100%',
                width: `${(progress.owned / progress.total) * 100}%`,
                background: isCompletion ? '#f5c842' : '#7ad6ff',
                transition: 'width 0.4s ease-out',
              }} />
            </div>
            <div className="muted" style={{ fontSize: 11, marginTop: 2 }}>
              {progress.owned} / {progress.total}
            </div>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8, marginTop: 12 }}>
          <button className="secondary" onClick={onInspect} style={{ fontSize: 12 }}>
            Inspect Collection
          </button>
          <button className="primary" onClick={onClose} style={{ fontSize: 12, marginLeft: 'auto' }}>
            Continue
          </button>
        </div>
      </div>
    </div>
  );
}

// Inline keyframe (or move to global CSS):
const styleEl = typeof document !== 'undefined' ? document.createElement('style') : null;
if (styleEl && !document.getElementById('collection-popup-style')) {
  styleEl.id = 'collection-popup-style';
  styleEl.textContent = `
    @keyframes collection-pop {
      0%   { transform: translateY(100%); opacity: 0; }
      100% { transform: translateY(0);    opacity: 1; }
    }
  `;
  document.head.appendChild(styleEl);
}
```

- [ ] **Step 6: Wire CollectionLootPopup into the battle replay flow**

In whichever component reads `rewards_extra` from the battle response (likely `BattleReplayRoute.tsx` or `BattlePlayRoute.tsx`), check for `collection_drop`:

```tsx
const drop = battle.rewards?.collection_drop as CollectionDrop | undefined;
const completed = battle.rewards?.collection_completed as string | undefined;

// Render <CollectionLootPopup> when drop is present.
// On completed, also render a small banner: "Collection complete — claim your reward"
// with a deep link to `/collections`.
```

For the loot popup's progress bar, the easiest approach: trigger a `/collections` refetch on receipt and pull the matching collection's `owned_count`/`total_count` from there. Since the popup is non-blocking, this is cheap.

- [ ] **Step 7: Add nav entry + coach mark in Shell.tsx**

In `frontend/src/components/Layout/Shell.tsx`, find the nav block. Add a new nav item:

```tsx
{ label: 'Collections', icon: '📜', path: '/collections', section: 'gear' /* or similar */ }
```

Match the existing nav item structure exactly.

For the coach mark: add a `<CoachMark>` wrapper around the Collections nav item, gated by `localStorage.getItem('heroproto_coachmark_collections')`. Mirror the pattern from subsystem onboarding-quest's coach marks (Stages, Roster, etc.). The coach mark fires on first mount of any page that has the nav, AFTER the player has at least 1 piece in any collection. Read `me?.eight_tracks > 0 || /* heuristic */` is too cheap; the cleanest signal is "does /collections have any non-zero progress?" — fetch lazily on mount.

For v1 simplicity: trigger the coach mark the first time the player views ANY page after a battle that returned `collection_drop`. Set `localStorage.heroproto_coachmark_collections = 'seen'` on first dismiss.

- [ ] **Step 8: Register route in App.tsx**

In `frontend/src/App.tsx`, add the route:

```tsx
import CollectionsRoute from './routes/Collections';
...
<Route path="collections" element={<CollectionsRoute />} />
```

Match the existing route registration style.

- [ ] **Step 9: Build**

`cd frontend && npm run build 2>&1 | tail -10`
Expected: success.

If `frontend/src/test/types.test.ts` (or similar fixture) declares Me without the new field, add `eight_tracks: 0`.

- [ ] **Step 10: Commit**

```bash
git add app/routers/me.py app/schemas.py frontend/ tests/test_collections.py
git commit -m "feat(collections): /collections route + loot popup + nav coach mark + /me eight_tracks"
```

---

## Task 8: Final verification + push + TODO update

- [ ] **Step 1: Full backend suite**

`uv run pytest 2>&1 | tail -10`
Expected: 780+ pass with 1 pre-existing failure tolerated.

- [ ] **Step 2: Manual probe — full collection cycle on a fresh DB**

```bash
uv run python -c "
import os, tempfile, json, random
db_path = tempfile.mktemp(suffix='.db')
os.environ['DATABASE_URL'] = f'sqlite:///{db_path}'
from app.db import Base, engine, SessionLocal
Base.metadata.create_all(bind=engine)
from app.seed import seed_collections
db = SessionLocal()
n = seed_collections(db)
print(f'seeded {n} collections')
from app.models import Account, Collection
from app.collections import roll_piece_drop, award_piece, try_complete, claim_reward
acc = Account(email='probe@example.com', password_hash='x', account_level=10, coins=0)
db.add(acc); db.flush()
rng = random.Random(0)
# 50 stage rolls
collected = {}
for _ in range(50):
    d = roll_piece_drop(db, acc, source='stage', rng=rng)
    if d:
        s = award_piece(acc, d.collection_code, d.piece_code)
        collected[d.collection_code] = collected.get(d.collection_code, 0) + (1 if s == 'new' else 0)
        try_complete(acc, d.collection_code)
print('after 50 stage rolls:', collected)
print('coins (from dups):', acc.coins)
"
```

Expected output: roughly 50 pieces distributed across 4 collections in the 1-20 bracket, weighted toward UNCOMMON.

- [ ] **Step 3: Push**

`git push 2>&1 | tail -3`

- [ ] **Step 4: Update TODO.md**

Edit `TODO.md`. Find the line:

```markdown
### Rare collections (5–12 piece sets)
- [ ] Loot-screen popup on stage clear / boss / wherever a piece drops
...
```

Replace the section with:

```markdown
### Rare collections v1 ✅ shipped 2026-05-10
- [x] 12 collections seeded (4 rarities × 3 brackets)
- [x] Drop pipeline wired in 3 battle sites + raid contributions
- [x] /collections API + claim + 8-track open
- [x] 8-track grants from weekly chest, tower floor 50, raid top 10%
- [x] Frontend route + loot popup + nav coach mark
- [ ] **v2 follow-ups**: Legendary set-bonus passive, Myth tier RNG unlock, buyable 8-tracks (Stripe SKU), shop random piece rotation. Spec deferrals listed in `2026-05-10-rare-collections-v1-design.md` §11.
```

Commit + push:

```bash
git add TODO.md
git commit -m "docs(todo): mark rare collections v1 shipped"
git push 2>&1 | tail -3
```

---

## Out-of-scope reminders (DO NOT implement here)

- Legendary set-bonus passive design — placeholder reward (200 gems + frame) ships in v1; v2 designs the passive.
- Myth tier RNG unlock — completion of a Legendary may spawn a Myth track. v2.
- Buyable 8-tracks — Stripe SKU. v2 catalog addition.
- Shop random rotation — pieces appearing in shop's daily slot. v2.
- Hero-template-tied collections — collect a hero's lore artifacts. v2 / future.

If you find yourself touching code unrelated to the collection drop / claim / 8-track / API / frontend surface, stop and re-read this plan.
