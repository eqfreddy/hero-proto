"""add_win_streak_days

Adds win_streak_days + win_streak_last_date scalars to accounts. Used by
the Stages header pill (loss-aversion / consecutive-days framing).

Revision ID: b7e4d2c1a8f3
Revises: a3c8e1f2d9b4
Create Date: 2026-05-13 16:20:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b7e4d2c1a8f3"
down_revision: Union[str, Sequence[str], None] = "a3c8e1f2d9b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("accounts") as b:
        b.add_column(sa.Column(
            "win_streak_days", sa.Integer(), nullable=False, server_default="0"
        ))
        b.add_column(sa.Column(
            "win_streak_last_date", sa.String(length=10), nullable=False, server_default=""
        ))


def downgrade() -> None:
    with op.batch_alter_table("accounts") as b:
        b.drop_column("win_streak_last_date")
        b.drop_column("win_streak_days")
