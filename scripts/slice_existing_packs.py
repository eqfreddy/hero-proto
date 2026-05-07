"""Slice the existing orc/soldier sheets that pre-date the CraftPix imports.

These sheets live IN the destination already (under
`app/static/battle-assets/characters/<slug>/<filename>.png`). The slicer reads
them in place and writes per-frame PNGs into `<slug>/<anim>/<flat>-<anim>_NN.png`,
matching the CraftPix layout so the same rig system handles them.

Skeleton is intentionally skipped — its frames are 32px tall with non-square
proportions, which would need a different slicer.

Run from repo root:
    python scripts/slice_existing_packs.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1] / "app/static/battle-assets/characters"

# slug → (flat_prefix, sheet_name → anim_slot)
PACKS = {
    "orc": ("orc", {
        "Orc-Idle.png":      "idle",
        "Orc-Attack01.png":  "attack",
        "Orc-Hurt.png":      "hurt",
        "Orc-Death.png":     "die",
        "Orc-Walk.png":      "run",
    }),
    "soldier": ("soldier", {
        "Soldier-Idle.png":     "idle",
        "Soldier-Attack01.png": "attack",
        "Soldier-Hurt.png":     "hurt",
        "Soldier-Death.png":    "die",
        "Soldier-Walk.png":     "run",
    }),
}


def slice_sheet(src: Path, dest_dir: Path, prefix: str) -> int:
    img = Image.open(src)
    width, height = img.size
    # Square frame, side = sheet height.
    frame_size = height
    frame_count = width // frame_size
    if frame_count == 0:
        return 0
    dest_dir.mkdir(parents=True, exist_ok=True)
    for i in range(frame_count):
        left = i * frame_size
        frame = img.crop((left, 0, left + frame_size, frame_size))
        frame.save(dest_dir / f"{prefix}_{i:02d}.png")
    return frame_count


def main() -> None:
    for slug, (flat, sheet_map) in PACKS.items():
        char_dir = ROOT / slug
        if not char_dir.is_dir():
            print(f"skip: {char_dir} missing")
            continue
        print(f"=== {slug} ===")
        for sheet_name, anim_slot in sheet_map.items():
            src = char_dir / sheet_name
            if not src.is_file():
                print(f"  skip {sheet_name}: missing")
                continue
            dest = char_dir / anim_slot
            n = slice_sheet(src, dest, f"{flat}-{anim_slot}")
            print(f"  {anim_slot}: {n} frames -> {dest.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
