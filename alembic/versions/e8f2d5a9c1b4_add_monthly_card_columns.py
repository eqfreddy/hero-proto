"""add accounts.monthly_card_ends_at + monthly_card_last_drip_at

Revision ID: e8f2d5a9c1b4
Revises: d3f8b1c2a4e7
Create Date: 2026-05-08 15:42:00.000000

Phase 5 retention work — Monthly Card subscription columns. Both nullable;
existing accounts default to no-card (NULL ends_at = inactive).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e8f2d5a9c1b4'
down_revision: Union[str, Sequence[str], None] = 'd3f8b1c2a4e7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('monthly_card_ends_at', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('monthly_card_last_drip_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.drop_column('monthly_card_last_drip_at')
        batch_op.drop_column('monthly_card_ends_at')
