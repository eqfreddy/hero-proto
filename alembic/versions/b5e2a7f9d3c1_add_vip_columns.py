"""add accounts.vip_xp + vip_last_drip_at

Revision ID: b5e2a7f9d3c1
Revises: f1b3c8d4e9a2
Create Date: 2026-05-08 17:05:00.000000

Phase 5 retention — VIP tiers. Cumulative-spend XP grants permanent QoL
perks; daily-drip lock prevents double-claim.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b5e2a7f9d3c1'
down_revision: Union[str, Sequence[str], None] = 'f1b3c8d4e9a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('vip_xp', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('vip_last_drip_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.drop_column('vip_last_drip_at')
        batch_op.drop_column('vip_xp')
