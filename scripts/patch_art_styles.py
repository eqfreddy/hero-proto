"""Patch the design-session SVGs to be standalone-renderable.

The shipped files reference CSS classes (e.g. `class="atk-up-bg"`) but contain
no `<style>` blocks defining them. When loaded via `<img src="...">`, parent-
page CSS can't reach inside the SVG, so shapes fall back to the default black
fill — icons render as solid black, frames as black squares covering portraits.

This script scans each SVG, infers colors for each class name from a set of
heuristic rules + explicit per-file mappings, and injects a `<style>` block
right after the opening `<svg>` tag. Idempotent: files that already contain
`<style>` are left alone.

Run from repo root:
    uv run python -m scripts.patch_art_styles

Review the diff, commit.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATIC = ROOT / "app" / "static"

# Locked design tokens (from docs/BATTLE_UI_HANDOFF.md).
DARK_BG = "#0b0d10"
SKIN = "#d9b38c"
HAIR_DARK = "#3a2818"
METAL = "#c0c4cb"
PAPER = "#f2e8d6"

FACTION_COLOR = {
    "HELPDESK": "#ff7a59",
    "DEVOPS": "#59a0ff",
    "EXECUTIVE": "#c77dff",
    "ROGUE_IT": "#ffd86b",
    "LEGACY": "#6dd39a",
}

ROLE_COLOR = {"ATK": "#ff7a59", "DEF": "#59a0ff", "SUP": "#6dd39a"}

RARITY_COLOR = {
    "COMMON": "#7d8a9c",
    "UNCOMMON": "#6dd39a",
    "RARE": "#59a0ff",
    "EPIC": "#c77dff",
    "LEGENDARY": "#ffd86b",
}

STATUS_COLOR = {
    "ATK_UP": "#ff7a59",
    "DEF_DOWN": "#ff6464",
    "POISON": "#6dd39a",
    "STUN": "#ffd86b",
    "SHIELD": "#59a0ff",
}

TIER_COLOR = {
    "NORMAL": "#7d8a9c",
    "HARD": "#59a0ff",
    "NIGHTMARE": "#ffd86b",
}

# Per hero_code -> faction (mirror of seed.py — kept inline so the script is
# self-contained). Missing = falls back to neutral grey.
HERO_FACTION = {
    "ticket_gremlin": "HELPDESK", "printer_whisperer": "HELPDESK",
    "overnight_janitor": "LEGACY", "jaded_intern": "HELPDESK",
    "sre_on_call": "DEVOPS", "compliance_officer": "EXECUTIVE",
    "security_auditor": "EXECUTIVE", "the_sysadmin": "LEGACY",
    "root_access_janitor": "ROGUE_IT", "vp_of_vibes": "EXECUTIVE",
    "keymaster_gary": "HELPDESK", "the_post_mortem": "DEVOPS",
    "midnight_pager": "DEVOPS", "the_consultant": "EXECUTIVE",
    "the_founder": "EXECUTIVE", "devops_apprentice": "DEVOPS",
    "forgotten_contractor": "ROGUE_IT", "helpdesk_veteran": "HELPDESK",
    "build_engineer": "DEVOPS", "rogue_dba": "ROGUE_IT",
    "oncall_warrior": "DEVOPS", "retired_mainframe_guru": "LEGACY",
    "shadow_it_operator": "ROGUE_IT", "chaos_monkey": "DEVOPS",
    "the_board_member": "EXECUTIVE",
}


def _extract_classes(svg: str) -> list[str]:
    """Returns unique class tokens appearing anywhere in the SVG."""
    classes = set()
    for m in re.finditer(r'class="([^"]+)"', svg):
        for cls in m.group(1).split():
            classes.add(cls)
    return sorted(classes)


def _status_style(stem: str, classes: list[str]) -> dict[str, str]:
    """e.g. ATK_UP: 'atk-up-bg' -> tinted plate, 'atk-up-fg' -> solid color."""
    color = STATUS_COLOR.get(stem, "#7d8a9c")
    rules = {}
    for cls in classes:
        if cls.endswith("-bg"):
            rules[cls] = f"fill: {color}; opacity: 0.3;"
        elif cls.endswith("-fg") or cls.endswith("-star") or cls.endswith("-skull"):
            rules[cls] = f"fill: {color};"
        else:
            rules[cls] = f"fill: {color};"
    return rules


def _frame_style(stem: str, classes: list[str]) -> dict[str, str]:
    """Frames are decorative borders — transparent center so the portrait shows
    through. frame-border -> stroke only, no fill."""
    color = RARITY_COLOR.get(stem, "#7d8a9c")
    rules = {}
    for cls in classes:
        if cls == "frame-border":
            rules[cls] = f"fill: none; stroke: {color}; stroke-width: 3;"
        elif cls == "frame-glow":
            rules[cls] = f"filter: drop-shadow(0 0 4px {color});"
        elif cls == "frame-shimmer":
            # Gold flourishes on LEGENDARY — already has inline fills on the path
            # stars. For other classes, fall back to accent color.
            rules[cls] = f"fill: {color};"
        else:
            rules[cls] = f"fill: {color};"
    return rules


def _faction_style(stem: str, classes: list[str]) -> dict[str, str]:
    color = FACTION_COLOR.get(stem, "#7d8a9c")
    rules = {}
    for cls in classes:
        # Treat background-ish classes as transparent, everything else as the
        # faction color. Bigger icons have named parts like 'headset-ear' +
        # 'cord' — all get the same color for a monochrome glyph.
        if cls.endswith("-bg") or cls == "bg":
            rules[cls] = "fill: none;"
        else:
            rules[cls] = f"fill: {color}; stroke: {color}; stroke-width: 0;"
    return rules


def _role_style(stem: str, classes: list[str]) -> dict[str, str]:
    color = ROLE_COLOR.get(stem, "#7d8a9c")
    rules = {}
    for cls in classes:
        if cls.endswith("-bg") or cls == "bg":
            rules[cls] = "fill: none;"
        else:
            rules[cls] = f"fill: {color};"
    return rules


def _tier_style(stem: str, classes: list[str]) -> dict[str, str]:
    color = TIER_COLOR.get(stem, "#7d8a9c")
    rules = {}
    for cls in classes:
        if cls.endswith("-bg") or cls == "bg":
            rules[cls] = f"fill: {color}; opacity: 0.2;"
        elif cls.endswith("-label") or cls.endswith("-text"):
            rules[cls] = "fill: #ffffff;"
        else:
            rules[cls] = f"fill: {color};"
    return rules


def _hero_style(stem: str, classes: list[str]) -> dict[str, str]:
    """Semantic class mapping for characters. Unknown classes default to the
    hero's faction color so anything unmapped stays visible + on-theme."""
    faction = HERO_FACTION.get(stem, "LEGACY")
    accent = FACTION_COLOR[faction]
    rules = {}
    for cls in classes:
        lower = cls.lower()
        if cls == "bg" or lower.endswith("-bg"):
            # Hero portraits: transparent background so rarity frames show through.
            rules[cls] = "fill: none;"
            continue
        # Skin tones.
        if any(w in lower for w in ("face", "skin", "head", "hand", "arm", "neck")):
            rules[cls] = f"fill: {SKIN};"
            continue
        # Hair / facial hair / dark features.
        if any(w in lower for w in ("hair", "goatee", "beard", "mustache", "eyebrow")):
            rules[cls] = f"fill: {HAIR_DARK};"
            continue
        # Eyes / pupils — dark dots.
        if any(w in lower for w in ("eye", "pupil", "iris")):
            rules[cls] = f"fill: {DARK_BG};"
            continue
        # Metal / electronic props.
        if any(w in lower for w in ("laptop", "screen", "monitor", "keyboard",
                                      "pager", "badge", "tool", "key", "mop",
                                      "metal", "server", "wrench")):
            rules[cls] = f"fill: {METAL};"
            continue
        # Paper / documents / sticky notes.
        if any(w in lower for w in ("paper", "note", "page", "binder", "card",
                                      "sticky", "ticket", "dongle", "floppy",
                                      "punch")):
            rules[cls] = f"fill: {PAPER};"
            continue
        # Suit / shirt / body / clothing — darker faction tint.
        if any(w in lower for w in ("suit", "shirt", "vest", "robe",
                                      "hoodie", "body", "torso", "lapel")):
            rules[cls] = f"fill: {accent}; opacity: 0.75;"
            continue
        # Ties / accents / highlights — bright faction color.
        if any(w in lower for w in ("tie", "accent", "stripe", "lanyard",
                                      "logo", "emblem", "trim", "collar")):
            rules[cls] = f"fill: {accent};"
            continue
        # Coffee / mug / drink -> coffee brown.
        if "coffee" in lower or "mug" in lower or "cup" in lower:
            rules[cls] = "fill: #5a3a1d;"
            continue
        # Floor shadow / shade — very dark.
        if "shadow" in lower or "shade" in lower:
            rules[cls] = "fill: #000000; opacity: 0.3;"
            continue
        # Fall back to the faction color so unrecognized parts still render.
        rules[cls] = f"fill: {accent};"
    return rules


def _background_style(stem: str, classes: list[str]) -> dict[str, str]:
    """Stage backgrounds are big decorative panels. Without ground truth, we
    give each named class a role-plausible flat color using name hints."""
    rules = {}
    for cls in classes:
        lower = cls.lower()
        if cls == "bg" or lower.endswith("-bg") or "sky" in lower:
            rules[cls] = "fill: #14202b;"
        elif "floor" in lower or "ground" in lower:
            rules[cls] = "fill: #1b2430;"
        elif "wall" in lower or "panel" in lower:
            rules[cls] = "fill: #2d3847;"
        elif "window" in lower or "glass" in lower:
            rules[cls] = "fill: #59a0ff; opacity: 0.2;"
        elif "light" in lower or "glow" in lower:
            rules[cls] = "fill: #ffd86b; opacity: 0.4;"
        elif "screen" in lower or "monitor" in lower:
            rules[cls] = "fill: #ff6b4a; opacity: 0.6;"
        elif "desk" in lower or "table" in lower or "chair" in lower:
            rules[cls] = "fill: #3a2818;"
        elif "cable" in lower or "wire" in lower:
            rules[cls] = "fill: #c0c4cb;"
        else:
            rules[cls] = "fill: #3a4555;"
    return rules


def _render_style(rules: dict[str, str]) -> str:
    """Turn rules dict into a CSS block wrapped in <style>."""
    lines = []
    for cls, decl in sorted(rules.items()):
        lines.append(f"    .{cls} {{ {decl} }}")
    body = "\n".join(lines)
    return f"  <style>\n{body}\n  </style>\n"


def patch_file(path: Path) -> tuple[bool, str]:
    """Returns (modified, note). modified=False if already had a <style> block
    or no classes to style."""
    svg = path.read_text(encoding="utf-8")
    if "<style" in svg:
        return False, "already has <style>"

    classes = _extract_classes(svg)
    if not classes:
        return False, "no class attributes"

    # Route to the right style generator based on parent directory.
    category = path.parent.name
    stem = path.stem
    dispatch = {
        "status": _status_style,
        "frames": _frame_style,
        "factions": _faction_style,
        "roles": _role_style,
        "tiers": _tier_style,
        "heroes": _hero_style,
        "backgrounds": _background_style,
    }
    gen = dispatch.get(category)
    if gen is None:
        return False, f"unknown category '{category}'"

    rules = gen(stem, classes)
    if not rules:
        return False, "no rules generated"

    style_block = _render_style(rules)
    # Inject after the opening <svg ...> tag.
    new_svg = re.sub(
        r"(<svg[^>]*>\s*)",
        lambda m: m.group(1) + style_block,
        svg,
        count=1,
    )
    path.write_text(new_svg, encoding="utf-8")
    return True, f"{len(classes)} classes -> {len(rules)} rules"


def main() -> int:
    targets = list(STATIC.glob("*/*.svg"))
    if not targets:
        print(f"no SVGs found under {STATIC}", file=sys.stderr)
        return 1
    modified = 0
    skipped = 0
    for p in sorted(targets):
        rel = p.relative_to(ROOT)
        changed, note = patch_file(p)
        if changed:
            modified += 1
            print(f"  patched {rel} — {note}")
        else:
            skipped += 1
            print(f"  skipped {rel} — {note}")
    print(f"\ndone: {modified} patched, {skipped} skipped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
