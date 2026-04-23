"""Admin bootstrap CLI.

Usage:
    uv run python -m app.admin promote <email>
    uv run python -m app.admin demote  <email>
    uv run python -m app.admin list
    uv run python -m app.admin audit [--limit 20]

Runs against whatever database HEROPROTO_DATABASE_URL points at. Intended for
one-off ops: making the first admin without shelling into the DB, or quickly
reviewing recent admin actions.
"""

from __future__ import annotations

import argparse
import json
import sys

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Account, AdminAuditLog


def _cmd_promote(email: str) -> int:
    with SessionLocal() as db:
        a = db.scalar(select(Account).where(Account.email == email))
        if a is None:
            print(f"no account with email {email!r}", file=sys.stderr)
            return 2
        if a.is_admin:
            print(f"{email} is already admin")
            return 0
        a.is_admin = True
        db.add(
            AdminAuditLog(
                actor_id=None, action="promote", target_id=a.id,
                payload_json=json.dumps({"via": "cli"}),
            )
        )
        db.commit()
        print(f"promoted {email} (id={a.id}) to admin")
    return 0


def _cmd_demote(email: str) -> int:
    with SessionLocal() as db:
        a = db.scalar(select(Account).where(Account.email == email))
        if a is None:
            print(f"no account with email {email!r}", file=sys.stderr)
            return 2
        if not a.is_admin:
            print(f"{email} is not admin")
            return 0
        a.is_admin = False
        a.token_version = (a.token_version or 0) + 1  # revoke outstanding JWTs
        db.add(
            AdminAuditLog(
                actor_id=None, action="demote", target_id=a.id,
                payload_json=json.dumps({"via": "cli"}),
            )
        )
        db.commit()
        print(f"demoted {email} (id={a.id})")
    return 0


def _cmd_list() -> int:
    with SessionLocal() as db:
        admins = list(db.scalars(select(Account).where(Account.is_admin.is_(True)).order_by(Account.id)))
        if not admins:
            print("(no admins)")
            return 0
        print(f"{'id':>4}  {'email':<40}  banned")
        for a in admins:
            print(f"{a.id:>4}  {a.email:<40}  {a.is_banned}")
    return 0


def _cmd_audit(limit: int) -> int:
    with SessionLocal() as db:
        rows = list(
            db.scalars(
                select(AdminAuditLog).order_by(AdminAuditLog.id.desc()).limit(limit)
            )
        )
        if not rows:
            print("(no audit entries)")
            return 0
        for e in rows:
            print(
                f"#{e.id} {e.created_at.isoformat(timespec='seconds')} "
                f"actor={e.actor_id} {e.action} target={e.target_id} {e.payload_json}"
            )
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="python -m app.admin")
    sub = p.add_subparsers(dest="cmd", required=True)
    prom = sub.add_parser("promote", help="grant admin to an account by email")
    prom.add_argument("email")
    dem = sub.add_parser("demote", help="revoke admin from an account by email")
    dem.add_argument("email")
    sub.add_parser("list", help="list current admins")
    audit = sub.add_parser("audit", help="show recent admin audit entries")
    audit.add_argument("--limit", type=int, default=20)

    args = p.parse_args(argv)
    match args.cmd:
        case "promote":
            return _cmd_promote(args.email)
        case "demote":
            return _cmd_demote(args.email)
        case "list":
            return _cmd_list()
        case "audit":
            return _cmd_audit(args.limit)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
