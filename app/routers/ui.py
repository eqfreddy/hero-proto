"""UI router — serves the React SPA and placeholder hero SVGs."""
from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import HeroTemplate

router = APIRouter(prefix="/app", tags=["ui"], include_in_schema=False)

_SPA_DIR = Path(__file__).resolve().parents[1] / "static" / "spa"
_INDEX = _SPA_DIR / "index.html"


# --- Placeholder portraits ---------------------------------------------------
# IMPORTANT: must be declared BEFORE the catch-all spa_shell route so FastAPI
# evaluates this specific path first.

_ROLE_COLORS = {"ATK": "#ff7a59", "DEF": "#59a0ff", "SUP": "#6dd39a"}
_RARITY_FRAMES = {
    "COMMON": "#9ca7b3", "UNCOMMON": "#6dd39a",
    "RARE": "#59a0ff", "EPIC": "#c97aff", "LEGENDARY": "#ffd86b",
}


def _initials(name: str, n: int = 2) -> str:
    words = [w for w in (name or "").strip().split() if w]
    if not words:
        return "?"
    if len(words) == 1:
        return words[0][:n].upper()
    return "".join(w[0] for w in words[:n]).upper()


@router.get("/placeholder/hero/{code}.svg", response_class=Response, include_in_schema=False)
def placeholder_hero(
    code: str,
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    tmpl = db.scalar(select(HeroTemplate).where(HeroTemplate.code == code))
    if tmpl is None:
        role_color = "#7d8a9c"
        frame_color = "#2d3847"
        initials = code[:2].upper() if code else "??"
    else:
        role_color = _ROLE_COLORS.get(str(tmpl.role), "#7d8a9c")
        frame_color = _RARITY_FRAMES.get(str(tmpl.rarity), "#2d3847")
        initials = _initials(tmpl.name)

    svg = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 128 128">'
        f'<rect width="128" height="128" rx="12" ry="12" fill="#14202b" stroke="{frame_color}" stroke-width="3"/>'
        f'<circle cx="64" cy="50" r="26" fill="{role_color}" opacity="0.85"/>'
        f'<path d="M20 120 Q20 78 64 78 Q108 78 108 120 Z" fill="{role_color}" opacity="0.6"/>'
        f'<text x="64" y="60" text-anchor="middle" font-family="system-ui, sans-serif" '
        f'font-weight="800" font-size="22" fill="#0b0d10">{initials}</text>'
        '</svg>'
    )
    return Response(content=svg, media_type="image/svg+xml", headers={"Cache-Control": "public, max-age=3600"})


# --- SPA catch-all -----------------------------------------------------------

@router.get("/{full_path:path}", response_class=FileResponse)
def spa_shell(full_path: str) -> FileResponse:
    """Catch-all: serve the SPA index for all /app/* routes."""
    return FileResponse(str(_INDEX))
