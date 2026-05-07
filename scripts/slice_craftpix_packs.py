"""Generalized CraftPix sprite-sheet slicer.

Walks every `craftpix-net-*` pack under the source root, finds each character
sub-folder, and slices their animation sheets into individual numbered PNGs
matching the existing `app/static/battle-assets/characters/<slug>/<anim>/` layout.

Frame height is always 128px (CraftPix standard for these packs); frame width
matches height (square frames). Frame count = sheet_width / 128.

Animation matching is fuzzy: the script tries a list of candidate filenames
for each slot (idle/attack/hurt/die/run) and uses the first match. Packs that
are dialogue-avatar-only (single portrait, no Idle.png) are skipped.

Run from repo root:
    python scripts/slice_craftpix_packs.py
"""
from __future__ import annotations

import re
from pathlib import Path

from PIL import Image

SRC_ROOT = Path("C:/Users/User/.claude/mmorpg/mmorpg-main/Craftpics")
DEST_ROOT = Path(__file__).resolve().parents[1] / "app/static/battle-assets/characters"

FRAME_HEIGHT = 128

# Animation slot → ordered list of filename candidates (case-insensitive match).
# First match wins. None of these are required — a character can ship without
# every animation; the registry just won't have that slot.
SLOT_CANDIDATES: dict[str, list[str]] = {
    "idle":   ["idle.png", "idle_1.png"],
    "attack": ["attack_1.png", "attack 1.png", "attack.png"],
    "hurt":   ["hurt.png"],
    "die":    ["dead.png", "death.png", "die.png"],
    "run":    ["run.png", "walk.png"],
}


def slugify(name: str) -> str:
    """Black_Werewolf → black-werewolf · 'Fire Wizard' → fire-wizard"""
    s = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return s


def flat(name: str) -> str:
    """Black_Werewolf → blackwerewolf · 'Fire Wizard' → firewizard.

    Used in PNG filename prefix. Avoids dashes/underscores in the prefix so
    `<flat>-<anim>_<NN>.png` never has visually-confusing double dashes.
    """
    return re.sub(r"[^a-z0-9]", "", name.lower())


def find_sheet(char_dir: Path, candidates: list[str]) -> Path | None:
    actual = {p.name.lower(): p for p in char_dir.iterdir() if p.is_file()}
    for cand in candidates:
        if cand in actual:
            return actual[cand]
    return None


def slice_sheet(src: Path, dest_dir: Path, prefix: str) -> int:
    """Slice a horizontal sprite strip. Frames are assumed square: each frame's
    width equals the sheet's height. Frame count = sheet_width / sheet_height.
    """
    img = Image.open(src)
    width, height = img.size
    frame_size = height
    if width % frame_size != 0:
        print(f"  warn {src.name}: width {width} not divisible by height {height}")
    frame_count = width // frame_size
    if frame_count == 0:
        return 0

    dest_dir.mkdir(parents=True, exist_ok=True)
    for i in range(frame_count):
        left = i * frame_size
        frame = img.crop((left, 0, left + frame_size, frame_size))
        frame.save(dest_dir / f"{prefix}_{i:02d}.png")
    return frame_count


def process_character(char_dir: Path, slug: str, flat_prefix: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for slot, candidates in SLOT_CANDIDATES.items():
        sheet = find_sheet(char_dir, candidates)
        if sheet is None:
            continue
        dest_dir = DEST_ROOT / slug / slot
        prefix = f"{flat_prefix}-{slot}"
        n = slice_sheet(sheet, dest_dir, prefix)
        if n:
            counts[slot] = n
    return counts


def main() -> None:
    if not SRC_ROOT.exists():
        raise SystemExit(f"missing source: {SRC_ROOT}")

    summary: dict[str, dict[str, int]] = {}
    for pack_dir in sorted(SRC_ROOT.iterdir()):
        if not pack_dir.is_dir():
            continue
        if not pack_dir.name.startswith("craftpix-net-"):
            continue

        # Each pack has 1+ character subfolders. Skip __MACOSX, PSD, Licens.txt etc.
        for child in sorted(pack_dir.iterdir()):
            if not child.is_dir():
                continue
            if child.name.lower() in {"__macosx", "psd", "psds"}:
                continue

            # Skip if no Idle.png — likely a dialogue-avatar pack we don't handle.
            if find_sheet(child, SLOT_CANDIDATES["idle"]) is None:
                continue

            slug = slugify(child.name)
            flat_prefix = flat(child.name)
            counts = process_character(child, slug, flat_prefix)
            if counts:
                summary[slug] = counts
                print(f"{slug:25s} {counts}")

    print(f"\n=== {len(summary)} characters sliced ===")
    for slug in sorted(summary):
        print(f"  {slug}")


if __name__ == "__main__":
    main()
