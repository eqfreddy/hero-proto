"""Pad ninja-monk and ninja-peasant frames from 96x96 to 128x128.

Source CraftPix sheets for these two ninjas are 96px square; peers (knights,
werewolves, etc.) are 128px. When both upscale into the same 250x250 wrap
the 96px frames render proportionally smaller and sit visually low against
the baseline. Padding the top with 32px of transparent pixels brings them
up to the same canvas size so the upscale ratio matches and the feet line
up with the rest of the roster.

Idempotent: skips frames that are already 128x128.

Run from repo root:
    python scripts/pad_ninja_frames.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1] / "app/static/battle-assets/characters"
TARGETS = ["ninja-monk", "ninja-peasant"]
TARGET_SIZE = 128


def pad_frame(p: Path) -> bool:
    img = Image.open(p)
    if img.size == (TARGET_SIZE, TARGET_SIZE):
        return False
    if img.size[0] != img.size[1]:
        print(f"  skip {p.name}: non-square {img.size}")
        return False
    if img.size[0] >= TARGET_SIZE:
        return False
    canvas = Image.new("RGBA", (TARGET_SIZE, TARGET_SIZE), (0, 0, 0, 0))
    # Anchor to bottom-center so feet stay on the floor.
    x = (TARGET_SIZE - img.width) // 2
    y = TARGET_SIZE - img.height
    canvas.paste(img.convert("RGBA"), (x, y), img.convert("RGBA"))
    canvas.save(p)
    return True


def main() -> None:
    for slug in TARGETS:
        char_dir = ROOT / slug
        if not char_dir.is_dir():
            print(f"skip {slug}: missing")
            continue
        print(f"=== {slug} ===")
        padded = 0
        for png in char_dir.rglob("*.png"):
            if pad_frame(png):
                padded += 1
        print(f"  padded {padded} frames")


if __name__ == "__main__":
    main()
