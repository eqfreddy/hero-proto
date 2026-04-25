"""Read git commit history and format it as patch notes for the website.

Loads commits at module-import time and caches them — git history doesn't
change during a server's runtime. Restart the server to pick up new commits.
"""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class CommitEntry:
    sha: str
    short_sha: str
    date: datetime
    title: str
    body: str
    category: str  # derived from title prefix


# Skip noisy commit categories — chore/test/typo work doesn't belong in
# user-facing patch notes. Keep `feat`, `fix`, the unprefixed sprint commits,
# and anything that looks substantive.
_SKIP_PREFIXES = ("chore:", "ci:", "build:", "style:", "test:", "typo:", "minor:")


def _categorize(title: str) -> str:
    t = title.lower()
    if t.startswith("phase "):
        return "Phase milestone"
    if t.startswith("sprint "):
        return "Sprint"
    if "fix" in t.split(":")[0]:
        return "Fix"
    if t.startswith(("hero art", "art", "events/")):
        return "Content"
    if any(s in t for s in ("crafting", "shard store", "inventory", "event quests", "starter pack")):
        return "Feature"
    if any(s in t for s in ("sound", "ui", "frontend", "summon ui", "roster")):
        return "UI / polish"
    if any(s in t for s in ("docs:", "todo.md", "readme", "prd:")):
        return "Docs"
    return "Update"


def _parse_git_log() -> list[CommitEntry]:
    """Returns commits in newest-first order. Skips the ones in _SKIP_PREFIXES.

    Output format chosen so we can split on a unique multi-byte separator and
    not collide with anything that might appear in commit bodies.
    """
    sep = "\x1e===HP_COMMIT===\x1e"
    fmt = f"%H%x1f%h%x1f%cI%x1f%s%x1f%b{sep}"
    try:
        out = subprocess.check_output(
            ["git", "-C", str(_REPO_ROOT), "log", "-n", "200", f"--pretty=format:{fmt}"],
            stderr=subprocess.DEVNULL,
        ).decode("utf-8", errors="replace")
    except (subprocess.CalledProcessError, FileNotFoundError, OSError):
        return []

    entries: list[CommitEntry] = []
    for raw in out.split(sep):
        raw = raw.strip("\n\r")
        if not raw:
            continue
        parts = raw.split("\x1f")
        if len(parts) < 4:
            continue
        sha, short_sha, iso_date, title = parts[0], parts[1], parts[2], parts[3]
        body = parts[4] if len(parts) > 4 else ""
        title = title.strip()
        # Filter out noise.
        low = title.lower()
        if any(low.startswith(p) for p in _SKIP_PREFIXES):
            continue
        try:
            dt = datetime.fromisoformat(iso_date)
        except ValueError:
            dt = datetime.now(timezone.utc)
        entries.append(CommitEntry(
            sha=sha, short_sha=short_sha, date=dt,
            title=title, body=body.strip(),
            category=_categorize(title),
        ))
    return entries


_CACHED: list[CommitEntry] | None = None


def get_commits(limit: int = 60) -> list[CommitEntry]:
    """Return up to `limit` recent commits (newest first), filtered."""
    global _CACHED
    if _CACHED is None:
        _CACHED = _parse_git_log()
    return _CACHED[:max(1, min(limit, 200))]


def reset_cache() -> None:
    """Test hook — force a re-read on next get_commits()."""
    global _CACHED
    _CACHED = None


def grouped_by_month(commits: list[CommitEntry]) -> list[tuple[str, list[CommitEntry]]]:
    """Group commits by 'YYYY-MM' for the patch-notes view."""
    out: list[tuple[str, list[CommitEntry]]] = []
    current_key: str | None = None
    bucket: list[CommitEntry] = []
    for c in commits:
        key = c.date.strftime("%B %Y")
        if key != current_key:
            if bucket:
                out.append((current_key, bucket))
            current_key = key
            bucket = []
        bucket.append(c)
    if bucket and current_key is not None:
        out.append((current_key, bucket))
    return out


def short_summary(body: str, max_chars: int = 240) -> str:
    """First paragraph of the body, trimmed for the changelog card."""
    if not body:
        return ""
    # First paragraph (until first blank line).
    para = re.split(r"\n\s*\n", body, maxsplit=1)[0].strip()
    # Strip co-author trailers / common footer noise.
    if "Co-Authored-By:" in para:
        para = para.split("Co-Authored-By:")[0].strip()
    if len(para) <= max_chars:
        return para
    return para[: max_chars - 1].rstrip() + "…"
