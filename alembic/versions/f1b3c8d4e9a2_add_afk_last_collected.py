"""add accounts.afk_last_collected_at

Revision ID: f1b3c8d4e9a2
Revises: e8f2d5a9c1b4
Create Date: 2026-05-08 16:35:00.000000

Phase 5 retention — AFK income loop column. NULL = unclaimed; service
treats as registration time when computing first-collection accrual.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1b3c8d4e9a2'
down_revision: Union[str, Sequence[str], None] = 'e8f2d5a9c1b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('afk_last_collected_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.drop_column('afk_last_collected_at')
