"""One-shot forced-fallback crop for sheets that confuse the column detector."""
import sys, os
from PIL import Image
import numpy as np
from collections import deque

PART_NAMES = ['body', 'head', 'arm_l', 'arm_r', 'prop']
PAD = 12
DARK_THRESH = 35
NEUTRAL_THRESH = 165
OUT_BASE = os.path.join(os.path.dirname(__file__), '..', 'app', 'static', 'heroes', 'sprites')


def extract_art(cell_img):
    arr = np.array(cell_img.convert('RGB'))
    h, w = arr.shape[:2]
    r = arr[:,:,0].astype(int); g = arr[:,:,1].astype(int); b = arr[:,:,2].astype(int)
    neutral = (np.abs(r-g)<22)&(np.abs(g-b)<22)&(np.abs(r-b)<22)&(arr[:,:,0]>NEUTRAL_THRESH)
    very_dark = (arr[:,:,0]<DARK_THRESH)&(arr[:,:,1]<DARK_THRESH)&(arr[:,:,2]<DARK_THRESH)
    bg_candidate = neutral | very_dark
    bg = np.zeros((h, w), dtype=bool)
    q = deque()
    def seed(y, x):
        if not bg[y,x] and bg_candidate[y,x]:
            bg[y,x] = True; q.append((y,x))
    for x in range(w): seed(0,x); seed(h-1,x)
    for y in range(h): seed(y,0); seed(y,w-1)
    while q:
        y, x = q.popleft()
        for dy, dx in [(-1,0),(1,0),(0,-1),(0,1)]:
            ny, nx = y+dy, x+dx
            if 0<=ny<h and 0<=nx<w and not bg[ny,nx] and bg_candidate[ny,nx]:
                bg[ny,nx] = True; q.append((ny,nx))
    art = ~bg
    ys, xs = np.where(art)
    if len(ys) == 0: return None
    y0,y1 = ys.min(),ys.max(); x0,x1 = xs.min(),xs.max()
    cy0=max(0,y0-PAD); cy1=min(h,y1+PAD); cx0=max(0,x0-PAD); cx1=min(w,x1+PAD)
    rgba = np.array(cell_img.convert('RGBA'))[cy0:cy1,cx0:cx1]
    rgba[~art[cy0:cy1,cx0:cx1], 3] = 0
    return Image.fromarray(rgba, 'RGBA')


def main():
    if len(sys.argv) < 3:
        print("Usage: crop_forced.py <input.png> <char1> [char2]")
        sys.exit(1)

    input_path = sys.argv[1]
    char_names = [a.lower() for a in sys.argv[2:]]

    img = Image.open(input_path)
    iw, ih = img.size
    print(f"Sheet: {iw}x{ih}  |  {len(char_names)} character(s)  [forced fallback columns]")

    col_panels = [
        (int(iw*0.005), int(iw*0.221)),
        (int(iw*0.222), int(iw*0.404)),
        (int(iw*0.406), int(iw*0.583)),
        (int(iw*0.584), int(iw*0.758)),
        (int(iw*0.759), int(iw*0.995)),
    ]

    # Auto-detect row bands by dark horizontal lines
    arr = np.array(img.convert('RGB'))
    dark = (arr[:,:,0]<DARK_THRESH)&(arr[:,:,1]<DARK_THRESH)&(arr[:,:,2]<DARK_THRESH)
    frac = dark.mean(axis=1)
    is_div = frac > 0.55
    divs = []
    in_g = False
    for i, v in enumerate(is_div):
        if v and not in_g: start=i; in_g=True
        elif not v and in_g: divs.append((start,i-1)); in_g=False
    if in_g: divs.append((start,ih-1))
    prev=0; row_panels=[]
    for s,e in divs:
        if s>prev: row_panels.append((prev,s-1))
        prev=e+1
    if prev<ih: row_panels.append((prev,ih-1))
    row_panels = [(y0,y1) for y0,y1 in row_panels if (y1-y0)>=ih*0.15]
    print(f"Rows: {row_panels}")

    for row_idx, (y0, y1) in enumerate(row_panels):
        if row_idx >= len(char_names): break
        char = char_names[row_idx]
        out_dir = os.path.join(OUT_BASE, char)
        os.makedirs(out_dir, exist_ok=True)
        print(f"\nCharacter: {char}  (row y={y0}-{y1})")
        saved = 0
        for col_idx, (x0, x1) in enumerate(col_panels):
            part = PART_NAMES[col_idx]
            cell = img.crop((x0, y0, x1, y1))
            art = extract_art(cell)
            if art is None: print(f"  {part}.png -- no art"); continue
            path = os.path.join(out_dir, f'{part}.png')
            art.save(path)
            print(f"  {part}.png ({art.width}x{art.height})")
            saved += 1
        print(f"  >> {saved} parts saved to sprites/{char}/")
    print("\nDone.")


if __name__ == '__main__':
    main()
