"""shard_remap_collapse_dupes

Collapse all duplicate HeroInstance rows into a single canonical row
per (account, template), crediting the deletions to that account's
template-shard balance.

Rip-and-replace migration — see docs/superpowers/plans/2026-05-12-shard-remap.md.
No safety-net rollback. Gear stays in the player's inventory because
`Gear.hero_instance_id` is ON DELETE SET NULL.

Tie-break for canonical row: highest variance_net (sum of all four stat
offsets), then lowest id (oldest pull). Deterministic so reruns on the
same data converge.

Revision ID: f9fcd159c6dd
Revises: 7cf6318a80f4
Create Date: 2026-05-12 11:44:44.671774

"""
from __future__ import annotations

import json
from collections import defaultdict
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "f9fcd159c6dd"
down_revision: Union[str, Sequence[str], None] = "7cf6318a80f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _variance_net(blob: str | None) -> float:
    if not blob:
        return 0.0
    try:
        data = json.loads(blob)
    except (json.JSONDecodeError, TypeError):
        return 0.0
    if not isinstance(data, dict):
        return 0.0
    total = 0.0
    for s in ("hp", "atk", "def", "spd"):
        v = data.get(s)
        if isinstance(v, (int, float)):
            total += float(v)
    return total


def upgrade() -> None:
    bind = op.get_bind()

    # Pull every hero instance and the templates we need for shard credits.
    rows = bind.execute(sa.text(
        "SELECT id, account_id, template_id, variance_pct_json "
        "FROM hero_instances ORDER BY account_id, template_id, id"
    )).fetchall()

    template_codes = {
        r[0]: r[1]
        for r in bind.execute(sa.text(
            "SELECT id, code FROM hero_templates"
        )).fetchall()
    }

    # Group: (account_id, template_id) -> list of (id, variance_net)
    groups: dict[tuple[int, int], list[tuple[int, float]]] = defaultdict(list)
    for hid, account_id, template_id, variance_blob in rows:
        groups[(account_id, template_id)].append((hid, _variance_net(variance_blob)))

    # For each group: keep best, delete rest, credit shards.
    delete_ids: list[int] = []
    # account_id -> {template_code: shards_to_add}
    shard_credits: dict[int, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for (account_id, template_id), members in groups.items():
        if len(members) <= 1:
            continue  # nothing to collapse
        # Sort: variance_net desc, id asc — first element wins.
        members.sort(key=lambda m: (-m[1], m[0]))
        keep_id = members[0][0]
        for hid, _ in members[1:]:
            delete_ids.append(hid)
        code = template_codes.get(template_id)
        if code is None:
            continue  # orphaned row — should not happen
        shard_credits[account_id][code] += len(members) - 1
        _ = keep_id  # explicitly noted for readers

    # Apply shard credits — merge into each account's template_shards_json.
    if shard_credits:
        existing = bind.execute(sa.text(
            "SELECT id, template_shards_json FROM accounts WHERE id IN :ids"
        ).bindparams(sa.bindparam("ids", expanding=True)), {"ids": list(shard_credits.keys())}).fetchall()
        current: dict[int, dict[str, int]] = {}
        for acct_id, blob in existing:
            try:
                parsed = json.loads(blob) if blob else {}
            except (json.JSONDecodeError, TypeError):
                parsed = {}
            if not isinstance(parsed, dict):
                parsed = {}
            current[acct_id] = {k: int(v) for k, v in parsed.items() if isinstance(v, (int, float))}

        for acct_id, credits in shard_credits.items():
            balance = current.get(acct_id, {})
            for code, count in credits.items():
                balance[code] = balance.get(code, 0) + count
            bind.execute(
                sa.text("UPDATE accounts SET template_shards_json = :blob WHERE id = :id"),
                {"blob": json.dumps(balance, separators=(",", ":")), "id": acct_id},
            )

    # Bulk-delete the collapsed rows. Gear FK is ON DELETE SET NULL so
    # equipped gear quietly returns to inventory.
    if delete_ids:
        bind.execute(
            sa.text("DELETE FROM hero_instances WHERE id IN :ids")
                .bindparams(sa.bindparam("ids", expanding=True)),
            {"ids": delete_ids},
        )

    print(
        f"[shard-remap] collapsed {len(delete_ids)} duplicate hero rows; "
        f"credited shards to {len(shard_credits)} accounts."
    )


def downgrade() -> None:
    """No-op. Lost duplicates can't be reconstructed — locked decision
    per docs/superpowers/plans/2026-05-12-shard-remap.md (rollback is
    forward-only)."""
    pass
