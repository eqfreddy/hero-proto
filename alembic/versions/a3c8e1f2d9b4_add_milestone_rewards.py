"""add_milestone_rewards

Adds legend_boss_shards + milestone_legend_pity to accounts,
creates stage_milestones and account_milestone_claims tables,
seeds the 8-milestone reward ladder, and adds is_legend_boss_pool
to hero_templates.

Revision ID: a3c8e1f2d9b4
Revises: f9fcd159c6dd
Create Date: 2026-05-13 06:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "a3c8e1f2d9b4"
down_revision: Union[str, Sequence[str], None] = "f9fcd159c6dd"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. New scalar columns on accounts (batch_alter for SQLite safety).
    with op.batch_alter_table("accounts") as b:
        b.add_column(sa.Column(
            "legend_boss_shards", sa.Integer(), nullable=False, server_default="0"
        ))
        b.add_column(sa.Column(
            "milestone_legend_pity", sa.Integer(), nullable=False, server_default="0"
        ))

    # 2. stage_milestones — static reward config table seeded below.
    op.create_table(
        "stage_milestones",
        sa.Column("id",                  sa.Integer(), primary_key=True),
        sa.Column("stage_count",         sa.Integer(), nullable=False, unique=True),
        sa.Column("template_shards",     sa.Integer(), nullable=False),
        sa.Column("legend_shard_chance", sa.Float(),   nullable=False),
        sa.Column("label",               sa.String(64), nullable=False, server_default=""),
    )
    op.create_index(
        "ix_stage_milestones_stage_count", "stage_milestones", ["stage_count"]
    )

    # 3. account_milestone_claims — per-account claim records.
    op.create_table(
        "account_milestone_claims",
        sa.Column("id",                      sa.Integer(), primary_key=True),
        sa.Column(
            "account_id", sa.Integer(),
            sa.ForeignKey("accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "milestone_id", sa.Integer(),
            sa.ForeignKey("stage_milestones.id"),
            nullable=False,
        ),
        sa.Column("claimed_at",              sa.DateTime(), nullable=False),
        sa.Column("template_shards_granted", sa.Integer(), nullable=False),
        sa.Column(
            "legend_shards_granted", sa.Integer(), nullable=False, server_default="0"
        ),
        sa.UniqueConstraint("account_id", "milestone_id", name="uq_amc_account_milestone"),
    )
    op.create_index("ix_amc_account_id", "account_milestone_claims", ["account_id"])

    # 4. is_legend_boss_pool column on hero_templates.
    with op.batch_alter_table("hero_templates") as b:
        b.add_column(sa.Column(
            "is_legend_boss_pool", sa.Boolean(), nullable=False, server_default="0"
        ))

    # 5. Seed milestone rows (safe to run on non-empty DBs — UNIQUE on stage_count
    #    guards against re-runs, so we use INSERT OR IGNORE for SQLite / postgres compat).
    bind = op.get_bind()
    rows = [
        (5,  20,  0.05, "Ticket Clerk"),
        (10, 35,  0.08, "On-Call Warrior"),
        (15, 50,  0.10, "Change Window"),
        (20, 70,  0.12, "Incident Commander"),
        (25, 90,  0.15, "The Root Cause"),
        (30, 115, 0.18, "Post-Mortem Legend"),
        (40, 150, 0.22, "Zero-Day Survivor"),
        (50, 200, 0.28, "The BOFH"),
    ]
    dialect = bind.dialect.name
    if dialect == "sqlite":
        insert_sql = sa.text(
            "INSERT OR IGNORE INTO stage_milestones "
            "(stage_count, template_shards, legend_shard_chance, label) "
            "VALUES (:sc, :ts, :lc, :lb)"
        )
    else:
        # PostgreSQL
        insert_sql = sa.text(
            "INSERT INTO stage_milestones "
            "(stage_count, template_shards, legend_shard_chance, label) "
            "VALUES (:sc, :ts, :lc, :lb) "
            "ON CONFLICT (stage_count) DO NOTHING"
        )
    for stage_count, shards, chance, label in rows:
        bind.execute(insert_sql, {"sc": stage_count, "ts": shards, "lc": chance, "lb": label})


def downgrade() -> None:
    # Remove is_legend_boss_pool from hero_templates.
    with op.batch_alter_table("hero_templates") as b:
        b.drop_column("is_legend_boss_pool")

    op.drop_index("ix_amc_account_id", table_name="account_milestone_claims")
    op.drop_table("account_milestone_claims")

    op.drop_index("ix_stage_milestones_stage_count", table_name="stage_milestones")
    op.drop_table("stage_milestones")

    with op.batch_alter_table("accounts") as b:
        b.drop_column("legend_boss_shards")
        b.drop_column("milestone_legend_pity")
