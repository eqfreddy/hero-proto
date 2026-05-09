"""add tower-of-trials columns to accounts

Revision ID: c4f7d8a3e2b9
Revises: a1d6c2e9f4b8
Create Date: 2026-05-08 18:35:00.000000

Phase 5 retention — Tower of Trials endless solo mode.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c4f7d8a3e2b9'
down_revision: Union[str, Sequence[str], None] = 'a1d6c2e9f4b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tower_floor', sa.Integer(), nullable=False, server_default='1'))
        batch_op.add_column(sa.Column('tower_best_floor', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('tower_attempts_today', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('tower_attempts_today_date', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('tower_season_key', sa.String(length=8), nullable=False, server_default=''))


def downgrade() -> None:
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.drop_column('tower_season_key')
        batch_op.drop_column('tower_attempts_today_date')
        batch_op.drop_column('tower_attempts_today')
        batch_op.drop_column('tower_best_floor')
        batch_op.drop_column('tower_floor')
