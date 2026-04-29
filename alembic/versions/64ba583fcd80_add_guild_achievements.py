"""add_guild_achievements

Revision ID: 64ba583fcd80
Revises: 2f6344973e63
Create Date: 2026-04-27 00:08:14.099775

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '64ba583fcd80'
down_revision: Union[str, Sequence[str], None] = '2f6344973e63'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'guild_achievements',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(64), nullable=False),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('description', sa.String(256), nullable=False, server_default=''),
        sa.Column('category', sa.String(32), nullable=False, server_default=''),
        sa.Column('metric', sa.String(64), nullable=False),
        sa.Column('target_value', sa.Integer(), nullable=False),
        sa.Column('reward_gems', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('reward_coins', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_index('ix_guild_achievements_code', 'guild_achievements', ['code'], unique=True)

    op.create_table(
        'guild_achievement_progress',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('guild_id', sa.Integer(), nullable=False),
        sa.Column('achievement_code', sa.String(64), nullable=False),
        sa.Column('current_value', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('reward_claimed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['guild_id'], ['guilds.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('guild_id', 'achievement_code', name='uq_guild_achievement_progress'),
    )
    op.create_index('ix_guild_achievement_progress_guild_id', 'guild_achievement_progress', ['guild_id'])
    op.create_index('ix_guild_achievement_progress_achievement_code', 'guild_achievement_progress', ['achievement_code'])


def downgrade() -> None:
    op.drop_index('ix_guild_achievement_progress_achievement_code', table_name='guild_achievement_progress')
    op.drop_index('ix_guild_achievement_progress_guild_id', table_name='guild_achievement_progress')
    op.drop_table('guild_achievement_progress')
    op.drop_index('ix_guild_achievements_code', table_name='guild_achievements')
    op.drop_table('guild_achievements')
