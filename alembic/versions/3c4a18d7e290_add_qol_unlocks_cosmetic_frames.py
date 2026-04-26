"""add accounts.qol_unlocks_json + accounts.cosmetic_frames_json

Revision ID: 3c4a18d7e290
Revises: b41cc2b1aa07
Create Date: 2026-04-26 10:00:00.000000

Phase 2.4 — PoE2-style QoL + cosmetic catalog. Both columns default to
empty containers so existing accounts read empty rather than NULL.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '3c4a18d7e290'
down_revision: Union[str, Sequence[str], None] = 'b41cc2b1aa07'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'qol_unlocks_json', sa.String(length=2048), nullable=False,
            server_default='{}',
        ))
        batch_op.add_column(sa.Column(
            'cosmetic_frames_json', sa.String(length=2048), nullable=False,
            server_default='[]',
        ))


def downgrade() -> None:
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.drop_column('cosmetic_frames_json')
        batch_op.drop_column('qol_unlocks_json')
