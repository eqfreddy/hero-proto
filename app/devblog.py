"""Devblog post loader.

Posts live as markdown files in `app/devblog/posts/<slug>.md` with a small
frontmatter block at the top. Loaded eagerly at module import — devblog
edits require a server restart, same as changelog.

Frontmatter format (between two `---` lines, YAML-ish key/value):

    ---
    title: A post about a thing
    date: 2026-04-25
    summary: One sentence describing the post for the index card.
    author: hero-proto dev
    ---

    # Markdown body starts here.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import markdown as md

_POSTS_DIR = Path(__file__).resolve().parent / "devblog" / "posts"
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.S)


@dataclass(frozen=True)
class DevPost:
    slug: str
    title: str
    date: date
    summary: str
    author: str
    body_md: str
    body_html: str


def _parse_frontmatter(raw: str) -> tuple[dict[str, str], str]:
    m = _FRONTMATTER_RE.match(raw)
    if not m:
        return {}, raw
    head, body = m.group(1), m.group(2)
    fields: dict[str, str] = {}
    for line in head.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        fields[key.strip().lower()] = value.strip()
    return fields, body


def _slug_from_filename(p: Path) -> str:
    return p.stem


def _render_body(text: str) -> str:
    return md.markdown(
        text,
        extensions=["fenced_code", "tables", "smarty", "sane_lists"],
        output_format="html5",
    )


def _load_one(p: Path) -> DevPost | None:
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError:
        return None
    fields, body = _parse_frontmatter(raw)
    title = fields.get("title", _slug_from_filename(p).replace("-", " ").title())
    summary = fields.get("summary", "")
    author = fields.get("author", "hero-proto dev")
    date_str = fields.get("date", "")
    try:
        post_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
    except ValueError:
        post_date = date.today()
    return DevPost(
        slug=_slug_from_filename(p),
        title=title,
        date=post_date,
        summary=summary,
        author=author,
        body_md=body,
        body_html=_render_body(body),
    )


def _load_all() -> list[DevPost]:
    if not _POSTS_DIR.is_dir():
        return []
    posts: list[DevPost] = []
    for p in _POSTS_DIR.glob("*.md"):
        post = _load_one(p)
        if post is not None:
            posts.append(post)
    posts.sort(key=lambda p: p.date, reverse=True)
    return posts


_CACHED: list[DevPost] | None = None


def all_posts() -> list[DevPost]:
    global _CACHED
    if _CACHED is None:
        _CACHED = _load_all()
    return _CACHED


def post_by_slug(slug: str) -> DevPost | None:
    for p in all_posts():
        if p.slug == slug:
            return p
    return None


def reset_cache() -> None:
    """Test hook — force re-read on next access."""
    global _CACHED
    _CACHED = None
