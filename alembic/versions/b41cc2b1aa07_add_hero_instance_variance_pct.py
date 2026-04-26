"""add hero_instances.variance_pct_json

Revision ID: b41cc2b1aa07
Revises: 7a91c0e21f4d
Create Date: 2026-04-26 09:30:00.000000

Phase 2.2 — per-stat variance % rolled on duplicate summons. JSON dict
{"hp":±x, "atk":±x, "def":±x, "spd":±x}. Empty {} for first-copy or
pre-Phase-2.2 heroes.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b41cc2b1aa07'
down_revision: Union[str, Sequence[str], None] = '7a91c0e21f4d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('hero_instances', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'variance_pct_json', sa.String(length=128), nullable=False,
            server_default='{}',
        ))


def downgrade() -> None:
    with op.batch_alter_table('hero_instances', schema=None) as batch_op:
        batch_op.drop_column('variance_pct_json')
