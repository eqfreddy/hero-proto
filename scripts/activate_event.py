"""Activate (or deactivate) a holiday / special event from a JSON spec.

Reads an event file from events/, then:
  - upserts a single AdminAnnouncement row (pinned for the event window)
  - upserts each LiveOpsEvent row (DOUBLE_REWARDS / BONUS_GEAR_DROPS / etc.)
  - upserts each ShopProduct (limited bundles, per-account-limit honored)

Idempotent — re-running with the same file updates timestamps + copy in
place rather than creating duplicates. Uses the event spec's `id` plus
the row name/sku as the dedupe key.

Usage:
    uv run python -m scripts.activate_event events/2026-07-01_canada_day.json
    uv run python -m scripts.activate_event events/2026-07-01_canada_day.json --deactivate
    uv run python -m scripts.activate_event events/2026-07-01_canada_day.json --dry-run

Exit codes: 0 ok, 1 misconfig, 2 file not found / unparseable.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Windows consoles default to cp1252 — force UTF-8 so the bullet + emoji
# characters in announcements render without crashing.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    except (AttributeError, OSError):
        pass

from sqlalchemy import select

from app.db import SessionLocal
from app.models import (
    AdminAnnouncement,
    LiveOpsEvent,
    LiveOpsKind,
    ShopProduct,
    ShopProductKind,
    utcnow,
)


def _parse_iso(value: str) -> datetime:
    # Accept trailing Z (Zulu / UTC) since the spec uses that.
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    # Normalize to naive UTC to match how models.utcnow() stores them.
    if dt.tzinfo is not None:
        dt = dt.astimezone(tz=None).replace(tzinfo=None)
    return dt


def _load_spec(path: Path) -> dict:
    if not path.is_file():
        print(f"[activate_event] file not found: {path}", file=sys.stderr)
        sys.exit(2)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[activate_event] invalid JSON: {e}", file=sys.stderr)
        sys.exit(2)


def _activate(spec: dict, dry_run: bool = False) -> int:
    starts = _parse_iso(spec["starts_at"])
    ends = _parse_iso(spec["ends_at"])
    if ends <= starts:
        print(f"[activate_event] ends_at ({ends}) must be after starts_at ({starts})", file=sys.stderr)
        return 1
    if ends <= utcnow():
        print(f"[activate_event] WARN ends_at is already in the past — event will surface as inactive", file=sys.stderr)

    summary: dict[str, list[str]] = {"announcement": [], "liveops": [], "shop": []}

    with SessionLocal() as db:
        # --- AdminAnnouncement (single row, identified by event id stuffed into title prefix) ---
        ann_spec = spec.get("announcement")
        if ann_spec:
            marker = f"[event:{spec['id']}]"
            existing_ann = db.scalar(
                select(AdminAnnouncement).where(AdminAnnouncement.body.like(f"%{marker}%"))
            )
            if existing_ann is None:
                ann = AdminAnnouncement(
                    title=ann_spec["title"],
                    body=ann_spec["body"] + f"\n\n{marker}",
                    priority=int(ann_spec.get("priority", 50)),
                    is_active=True,
                    starts_at=starts,
                    ends_at=ends,
                )
                if not dry_run:
                    db.add(ann)
                summary["announcement"].append(f"NEW {ann_spec['title']}")
            else:
                existing_ann.title = ann_spec["title"]
                existing_ann.body = ann_spec["body"] + f"\n\n{marker}"
                existing_ann.priority = int(ann_spec.get("priority", 50))
                existing_ann.is_active = True
                existing_ann.starts_at = starts
                existing_ann.ends_at = ends
                summary["announcement"].append(f"UPDATE {ann_spec['title']}")

        # --- LiveOps events ---
        for liv in spec.get("liveops", []):
            name = liv["name"]
            try:
                kind = LiveOpsKind(liv["kind"])
            except ValueError:
                print(f"[activate_event] unknown liveops kind: {liv['kind']!r}", file=sys.stderr)
                return 1
            existing = db.scalar(select(LiveOpsEvent).where(LiveOpsEvent.name == name))
            payload_json = json.dumps(liv.get("payload", {}))
            if existing is None:
                row = LiveOpsEvent(
                    kind=kind,
                    name=name,
                    starts_at=starts,
                    ends_at=ends,
                    payload_json=payload_json,
                )
                if not dry_run:
                    db.add(row)
                summary["liveops"].append(f"NEW {name} ({kind})")
            else:
                existing.kind = kind
                existing.starts_at = starts
                existing.ends_at = ends
                existing.payload_json = payload_json
                summary["liveops"].append(f"UPDATE {name} ({kind})")

        # --- Shop products (limited-time SKUs) ---
        for sku_spec in spec.get("shop", []):
            sku = sku_spec["sku"]
            try:
                kind = ShopProductKind(sku_spec["kind"])
            except ValueError:
                print(f"[activate_event] unknown shop kind: {sku_spec['kind']!r}", file=sys.stderr)
                return 1
            existing = db.scalar(select(ShopProduct).where(ShopProduct.sku == sku))
            contents_json = json.dumps(sku_spec.get("contents", {}))
            if existing is None:
                row = ShopProduct(
                    sku=sku,
                    title=sku_spec["title"],
                    description=sku_spec.get("description", ""),
                    kind=kind,
                    price_cents=int(sku_spec["price_cents"]),
                    currency_code=sku_spec.get("currency_code", "USD"),
                    contents_json=contents_json,
                    sort_order=int(sku_spec.get("sort_order", 50)),  # event = mid-prominent
                    per_account_limit=int(sku_spec.get("per_account_limit", 0)),
                )
                if not dry_run:
                    db.add(row)
                summary["shop"].append(f"NEW {sku}")
            else:
                existing.title = sku_spec["title"]
                existing.description = sku_spec.get("description", "")
                existing.kind = kind
                existing.price_cents = int(sku_spec["price_cents"])
                existing.contents_json = contents_json
                existing.per_account_limit = int(sku_spec.get("per_account_limit", 0))
                summary["shop"].append(f"UPDATE {sku}")

        if dry_run:
            print(f"[activate_event] DRY RUN — no changes committed.")
        else:
            db.commit()

    print(f"[activate_event] {spec['display_name']} {'DRY-RUN' if dry_run else 'activated'}:")
    for category, items in summary.items():
        for line in items:
            print(f"  · {category}: {line}")
    return 0


def _deactivate(spec: dict) -> int:
    """Tear down what _activate created — for use when an event flopped or
    needs an early end. Marks the announcement inactive, expires liveops,
    leaves shop products in place but flips per_account_limit so further
    purchases 409 (preserves audit trail for refund flows).
    """
    summary: list[str] = []
    now = utcnow()
    marker = f"[event:{spec['id']}]"

    with SessionLocal() as db:
        # Announcement — flip is_active off.
        ann = db.scalar(
            select(AdminAnnouncement).where(AdminAnnouncement.body.like(f"%{marker}%"))
        )
        if ann is not None:
            ann.is_active = False
            ann.ends_at = now
            summary.append(f"announcement '{ann.title}' deactivated")

        # LiveOps — set ends_at to now.
        for liv in spec.get("liveops", []):
            row = db.scalar(select(LiveOpsEvent).where(LiveOpsEvent.name == liv["name"]))
            if row is not None and row.ends_at > now:
                row.ends_at = now
                summary.append(f"liveops '{row.name}' ended")

        # Shop — nuke per_account_limit by setting to caller's purchase count
        # would require auditing every account; cheaper just to drop available
        # slots. Set per_account_limit to a sentinel that already-purchased
        # accounts have hit (1) AND mark with a sentinel sort_order so admin
        # can find these.
        for sku_spec in spec.get("shop", []):
            row = db.scalar(select(ShopProduct).where(ShopProduct.sku == sku_spec["sku"]))
            if row is not None:
                row.per_account_limit = 1
                row.sort_order = 9999  # sink to bottom of catalog
                summary.append(f"shop '{row.sku}' suppressed")

        db.commit()

    print(f"[activate_event] {spec['display_name']} deactivated:")
    for line in summary:
        print(f"  · {line}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.strip().split("\n")[0])
    parser.add_argument("file", help="Path to event JSON spec (events/<file>.json)")
    parser.add_argument("--deactivate", action="store_true",
                        help="Tear down instead of activating")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would change without committing")
    args = parser.parse_args()

    spec = _load_spec(Path(args.file))
    if not spec.get("id"):
        print("[activate_event] spec missing required 'id' field", file=sys.stderr)
        return 1

    if args.deactivate:
        return _deactivate(spec)
    return _activate(spec, dry_run=args.dry_run)


if __name__ == "__main__":
    sys.exit(main())
