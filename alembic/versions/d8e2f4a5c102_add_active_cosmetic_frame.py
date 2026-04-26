"""add accounts.active_cosmetic_frame

Revision ID: d8e2f4a5c102
Revises: 3c4a18d7e290
Create Date: 2026-04-26 12:00:00.000000

Phase 2.4 follow-up — owning a cosmetic frame is one thing; *equipping*
it is what actually changes the roster cards. Empty string = no frame
(rarity border fallback).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd8e2f4a5c102'
down_revision: Union[str, Sequence[str], None] = '3c4a18d7e290'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'active_cosmetic_frame', sa.String(length=64), nullable=False,
            server_default='',
        ))


def downgrade() -> None:
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.drop_column('active_cosmetic_frame')
