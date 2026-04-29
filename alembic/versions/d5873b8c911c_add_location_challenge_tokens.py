"""add location challenge tokens

Revision ID: d5873b8c911c
Revises: 64ba583fcd80
Create Date: 2026-04-28 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd5873b8c911c'
down_revision: Union[str, Sequence[str], None] = '64ba583fcd80'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('location_challenge_tokens',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('account_id', sa.Integer(), nullable=False),
    sa.Column('token_hash', sa.String(length=64), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('used_at', sa.DateTime(), nullable=True),
    sa.Column('login_ip', sa.String(length=64), nullable=True),
    sa.Column('user_agent', sa.String(length=256), nullable=True),
    sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    with op.batch_alter_table('location_challenge_tokens', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_location_challenge_tokens_account_id'), ['account_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_location_challenge_tokens_created_at'), ['created_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_location_challenge_tokens_expires_at'), ['expires_at'], unique=False)
        batch_op.create_index(batch_op.f('ix_location_challenge_tokens_token_hash'), ['token_hash'], unique=True)


def downgrade() -> None:
    with op.batch_alter_table('location_challenge_tokens', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_location_challenge_tokens_token_hash'))
        batch_op.drop_index(batch_op.f('ix_location_challenge_tokens_expires_at'))
        batch_op.drop_index(batch_op.f('ix_location_challenge_tokens_created_at'))
        batch_op.drop_index(batch_op.f('ix_location_challenge_tokens_account_id'))

    op.drop_table('location_challenge_tokens')
