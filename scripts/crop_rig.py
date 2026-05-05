#!/usr/bin/env python3
"""
crop_rig.py — Auto-crops a light rig reference sheet into named sprite parts.

Usage (1 character per sheet):
  python scripts/crop_rig.py <input.png> <character_name>

Usage (2 characters on one sheet, top first):
  python scripts/crop_rig.py <input.png> <char1_name> <char2_name>

Examples:
  python scripts/crop_rig.py "C:/Users/User/Downloads/agile_coach_rig.png" agile_coach
  python scripts/crop_rig.py "C:/Users/User/Downloads/sheet.png" agile_coach blue_team_lead

Parts named: body, head, arm_l, arm_r, prop  (left to right)
Output: app/static/heroes/sprites/<character_name>/
"""

import sys
import os
from PIL import Image
import numpy as np
from collections import deque

PART_NAMES = ['body', 'head', 'arm_l', 'arm_r', 'prop']
PAD = 12
DARK_THRESH = 35
NEUTRAL_THRESH = 165

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_BASE = os.path.join(SCRIPT_DIR, '..', 'app', 'static', 'heroes', 'sprites')


def dark_mask(arr):
    return (arr[:, :, 0] < DARK_THRESH) & \
           (arr[:, :, 1] < DARK_THRESH) & \
           (arr[:, :, 2] < DARK_THRESH)


def find_divider_bands(dark, axis, min_frac=0.25):
    """Find bands of consecutive lines where dark fraction exceeds min_frac."""
    frac = dark.mean(axis=axis)
    is_div = frac > min_frac
    groups = []
    in_g = False
    for i, v in enumerate(is_div):
        if v and not in_g:
            start = i; in_g = True
        elif not v and in_g:
            groups.append((start, i - 1)); in_g = False
    if in_g:
        groups.append((start, len(is_div) - 1))
    return groups


def gaps_between(dividers, total):
    gaps = []
    prev = 0
    for s, e in dividers:
        if s > prev:
            gaps.append((prev, s - 1))
        prev = e + 1
    if prev < total:
        gaps.append((prev, total - 1))
    return gaps


def find_true_col_dividers(arr, row_div_bands):
    """
    True column dividers must be dark in EVERY content row (gaps between
    horizontal dividers). Local dark elements (e.g. dark clothing on one
    character) only appear in one row and are filtered out.
    """
    dark = dark_mask(arr)
    h, w = arr.shape[:2]

    # Content rows = gaps between horizontal divider bands
    content_rows = gaps_between(row_div_bands, h)
    content_rows = [(y0, y1) for y0, y1 in content_rows if (y1 - y0) >= h * 0.08]

    if len(content_rows) < 2:
        # Fallback: just use full-height dark fraction
        frac = dark.mean(axis=0)
        is_div = frac > 0.25
    else:
        # Must be dark (>10%) in ALL content rows
        col_is_div = np.ones(w, dtype=bool)
        for (y0, y1) in content_rows:
            frac = dark[y0:y1 + 1, :].mean(axis=0)
            col_is_div &= (frac > 0.45)
        is_div = col_is_div

    groups = []
    in_g = False
    for i, v in enumerate(is_div):
        if v and not in_g:
            start = i; in_g = True
        elif not v and in_g:
            groups.append((start, i - 1)); in_g = False
    if in_g:
        groups.append((start, w - 1))
    return groups


def extract_art(cell_img):
    """
    Edge-flood-fill to remove background (neutral gray/white + dark borders),
    then return a transparent-bg RGBA crop of just the character art.
    """
    arr = np.array(cell_img.convert('RGB'))
    h, w = arr.shape[:2]
    r = arr[:, :, 0].astype(int)
    g = arr[:, :, 1].astype(int)
    b = arr[:, :, 2].astype(int)

    neutral = (
        (np.abs(r - g) < 22) & (np.abs(g - b) < 22) & (np.abs(r - b) < 22)
        & (arr[:, :, 0] > NEUTRAL_THRESH)
    )
    very_dark = (arr[:, :, 0] < DARK_THRESH) & (arr[:, :, 1] < DARK_THRESH) & (arr[:, :, 2] < DARK_THRESH)
    bg_candidate = neutral | very_dark

    bg = np.zeros((h, w), dtype=bool)
    q = deque()

    def seed(y, x):
        if not bg[y, x] and bg_candidate[y, x]:
            bg[y, x] = True
            q.append((y, x))

    for x in range(w):
        seed(0, x); seed(h - 1, x)
    for y in range(h):
        seed(y, 0); seed(y, w - 1)

    while q:
        y, x = q.popleft()
        for dy, dx in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            ny, nx = y + dy, x + dx
            if 0 <= ny < h and 0 <= nx < w and not bg[ny, nx] and bg_candidate[ny, nx]:
                bg[ny, nx] = True
                q.append((ny, nx))

    art = ~bg
    ys, xs = np.where(art)
    if len(ys) == 0:
        return None

    y0, y1 = ys.min(), ys.max()
    x0, x1 = xs.min(), xs.max()

    cy0 = max(0, y0 - PAD)
    cy1 = min(h, y1 + PAD)
    cx0 = max(0, x0 - PAD)
    cx1 = min(w, x1 + PAD)

    rgba = np.array(cell_img.convert('RGBA'))[cy0:cy1, cx0:cx1]
    art_crop = art[cy0:cy1, cx0:cx1]
    rgba[~art_crop, 3] = 0

    return Image.fromarray(rgba, 'RGBA')


def process_sheet(img, char_names):
    arr = np.array(img.convert('RGB'))
    h, w = arr.shape[:2]
    dark = dark_mask(arr)

    # Horizontal dividers — require high dark fraction (>0.55) to avoid
    # catching character header text bands which are only partially dark
    row_div_bands = find_divider_bands(dark, axis=1, min_frac=0.55)
    row_gaps = gaps_between(row_div_bands, h)
    row_panels = [(y0, y1) for y0, y1 in row_gaps if (y1 - y0) >= h * 0.15]

    # True column dividers — must be dark across all horizontal zones
    col_div_bands = find_true_col_dividers(arr, row_div_bands)
    col_gaps = gaps_between(col_div_bands, w)
    col_panels = [(x0, x1) for x0, x1 in col_gaps if (x1 - x0) >= w * 0.04]

    # Fallback: if fewer than 5 cols detected, use known proportional positions
    # (all sheets are 1536px wide with consistent 5-column layout)
    if len(col_panels) < 5:
        print(f"  Column auto-detect found {len(col_panels)} — using fallback positions")
        col_panels = [
            (int(w * 0.005), int(w * 0.221)),
            (int(w * 0.222), int(w * 0.404)),
            (int(w * 0.406), int(w * 0.583)),
            (int(w * 0.584), int(w * 0.758)),
            (int(w * 0.759), int(w * 0.995)),
        ]

    print(f"Grid: {len(col_panels)} col x {len(row_panels)} row")
    print(f"  Columns: {col_panels}")
    print(f"  Rows:    {row_panels}")

    for row_idx, (y0, y1) in enumerate(row_panels):
        if row_idx >= len(char_names):
            break
        char_name = char_names[row_idx]
        out_dir = os.path.join(OUT_BASE, char_name)
        os.makedirs(out_dir, exist_ok=True)
        print(f"\nCharacter: {char_name}  (row y={y0}-{y1})")

        saved = 0
        for col_idx, (x0, x1) in enumerate(col_panels):
            if col_idx >= len(PART_NAMES):
                break
            part_name = PART_NAMES[col_idx]
            cell = img.crop((x0, y0, x1, y1))
            art = extract_art(cell)
            if art is None:
                print(f"    {part_name}.png  -- no art found")
                continue
            path = os.path.join(out_dir, f'{part_name}.png')
            art.save(path)
            print(f"    {part_name}.png  ({art.width}x{art.height})")
            saved += 1

        print(f"  >> {saved} parts saved to sprites/{char_name}/")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)

    input_path = sys.argv[1]
    names = [a.lower().replace(' ', '_') for a in sys.argv[2:]]

    img = Image.open(input_path)
    print(f"Sheet: {img.width}x{img.height}  |  {len(names)} character(s)")

    process_sheet(img, names)
    print("\nDone.")


if __name__ == '__main__':
    main()
