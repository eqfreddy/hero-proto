"""add guild_invites

Revision ID: 50b27201679e
Revises: 3aa50c822bb6
Create Date: 2026-04-25 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '50b27201679e'
down_revision: Union[str, Sequence[str], None] = '3aa50c822bb6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'guild_invites',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('guild_id', sa.Integer(), nullable=False),
        sa.Column('inviter_id', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=16), nullable=False),
        sa.Column('message', sa.String(length=256), nullable=False, server_default=''),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('decided_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['guild_id'], ['guilds.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['inviter_id'], ['accounts.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_guild_invites_account_id'), 'guild_invites', ['account_id'])
    op.create_index(op.f('ix_guild_invites_guild_id'), 'guild_invites', ['guild_id'])
    op.create_index(op.f('ix_guild_invites_status'), 'guild_invites', ['status'])
    op.create_index(op.f('ix_guild_invites_created_at'), 'guild_invites', ['created_at'])


def downgrade() -> None:
    op.drop_index(op.f('ix_guild_invites_created_at'), table_name='guild_invites')
    op.drop_index(op.f('ix_guild_invites_status'), table_name='guild_invites')
    op.drop_index(op.f('ix_guild_invites_guild_id'), table_name='guild_invites')
    op.drop_index(op.f('ix_guild_invites_account_id'), table_name='guild_invites')
    op.drop_table('guild_invites')
