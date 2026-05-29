"""add_template_weakness

Adds weak_to_json + integrity_base to hero_templates. Used by the System
Integrity (weakness-break) combat layer so enemies built from a template can
declare a weakness faction + toughness-bar size. Both default inert (no
weakness, no bar) so heroes and un-tuned enemies behave exactly as before.

Revision ID: c9f1a2b3d4e5
Revises: b7e4d2c1a8f3
Create Date: 2026-05-29 05:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "c9f1a2b3d4e5"
down_revision: Union[str, Sequence[str], None] = "b7e4d2c1a8f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("hero_templates") as b:
        b.add_column(sa.Column(
            "weak_to_json", sa.String(length=128), nullable=False, server_default="[]"
        ))
        b.add_column(sa.Column(
            "integrity_base", sa.Integer(), nullable=False, server_default="0"
        ))


def downgrade() -> None:
    with op.batch_alter_table("hero_templates") as b:
        b.drop_column("integrity_base")
        b.drop_column("weak_to_json")
