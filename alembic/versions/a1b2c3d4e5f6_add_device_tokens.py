"""add_device_tokens

Revision ID: a1b2c3d4e5f6
Revises: 06604894e633
Create Date: 2026-04-29 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '06604894e633'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'device_tokens',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('account_id', sa.Integer(), sa.ForeignKey('accounts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('token', sa.String(512), nullable=False, unique=True),
        sa.Column('platform', sa.String(16), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_device_tokens_account_id', 'device_tokens', ['account_id'])
    op.create_index('ix_device_tokens_token', 'device_tokens', ['token'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_device_tokens_token', 'device_tokens')
    op.drop_index('ix_device_tokens_account_id', 'device_tokens')
    op.drop_table('device_tokens')
