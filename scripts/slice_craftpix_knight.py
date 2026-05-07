"""Slice CraftPix knight sprite sheets into individual numbered PNGs.

Input layout (from CraftPix free knight pack):
    Knight_1/Idle.png        (e.g. 512x128, 4 frames @ 128px each)
    Knight_1/Attack 1.png    (640x128, 5 frames)
    Knight_1/Hurt.png        (256x128, 2 frames)
    Knight_1/Dead.png        (768x128, 6 frames)
    Knight_1/Run.png         (896x128, 7 frames)

Output layout (matches existing battle-rigs pipeline):
    app/static/battle-assets/characters/knight-1/idle/knight1-idle_00.png ... _03.png
    app/static/battle-assets/characters/knight-1/attack/knight1-attack_00.png ... _04.png
    ...

Run from repo root:
    uv run python scripts/slice_craftpix_knight.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

SRC_ROOT = Path(
    "C:/Users/User/.claude/mmorpg/mmorpg-main/Craftpics/"
    "craftpix-net-803217-free-knight-character-sprites-pixel-art"
)
DEST_ROOT = Path(__file__).resolve().parents[1] / "app/static/battle-assets/characters"

# Map CraftPix sheet names → our animation slot names. Only these animations
# get sliced; the rest of the pack (Walk, Jump, Defend, Protect, Run+Attack)
# is ignored unless we extend the registry.
SHEET_MAP = {
    "Idle.png":     "idle",
    "Attack 1.png": "attack",
    "Hurt.png":     "hurt",
    "Dead.png":     "die",
    "Run.png":      "run",
}

FRAME_HEIGHT = 128  # CraftPix knights are 128px tall, square frames


def slice_sheet(src: Path, dest_dir: Path, prefix: str) -> int:
    """Cut `src` into individual frames, write to `dest_dir/<prefix>_NN.png`."""
    img = Image.open(src)
    width, height = img.size
    if height != FRAME_HEIGHT:
        raise SystemExit(f"unexpected height {height}px in {src} (expected {FRAME_HEIGHT})")
    frame_count = width // FRAME_HEIGHT
    if frame_count == 0:
        raise SystemExit(f"{src} too narrow for any frames")

    dest_dir.mkdir(parents=True, exist_ok=True)
    for i in range(frame_count):
        left = i * FRAME_HEIGHT
        frame = img.crop((left, 0, left + FRAME_HEIGHT, FRAME_HEIGHT))
        frame.save(dest_dir / f"{prefix}_{i:02d}.png")
    return frame_count


def main() -> None:
    if not SRC_ROOT.exists():
        raise SystemExit(f"source directory missing: {SRC_ROOT}")

    summary: dict[str, dict[str, int]] = {}
    for knight_dir_name in ("Knight_1", "Knight_2", "Knight_3"):
        src_knight = SRC_ROOT / knight_dir_name
        if not src_knight.is_dir():
            print(f"skip: {src_knight} not found")
            continue

        # knight-1, knight-2, knight-3
        slug = knight_dir_name.lower().replace("_", "-")
        # knight1, knight2, knight3 (used in frame filename prefix)
        flat = knight_dir_name.lower().replace("_", "")
        knight_summary: dict[str, int] = {}

        for sheet_name, anim_slot in SHEET_MAP.items():
            src_sheet = src_knight / sheet_name
            if not src_sheet.is_file():
                print(f"skip: {src_sheet} missing")
                continue
            dest_dir = DEST_ROOT / slug / anim_slot
            prefix = f"{flat}-{anim_slot}"
            count = slice_sheet(src_sheet, dest_dir, prefix)
            knight_summary[anim_slot] = count
            print(f"  {slug}/{anim_slot}: {count} frames -> {dest_dir}")

        summary[slug] = knight_summary

    print("\n=== summary ===")
    for slug, anims in summary.items():
        print(f"{slug}: {anims}")


if __name__ == "__main__":
    main()
