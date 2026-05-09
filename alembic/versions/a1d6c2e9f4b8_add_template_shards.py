"""add accounts.template_shards_json

Revision ID: a1d6c2e9f4b8
Revises: d9e4f1a8c5b3
Create Date: 2026-05-08 18:15:00.000000

Phase 5 retention — Hero Ascension via Template Shards. Per-template
currency earned from duplicate pulls; alternative ascend currency to
in-kind hero fodder.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1d6c2e9f4b8'
down_revision: Union[str, Sequence[str], None] = 'd9e4f1a8c5b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'template_shards_json', sa.String(length=8192),
            nullable=False, server_default='{}',
        ))


def downgrade() -> None:
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.drop_column('template_shards_json')
