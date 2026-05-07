"""arena_tickets_and_weekly_payouts

Revision ID: a4e1c5d2b8f9
Revises: db7eac125e36
Create Date: 2026-05-06 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a4e1c5d2b8f9'
down_revision: Union[str, Sequence[str], None] = 'db7eac125e36'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'accounts',
        sa.Column('arena_tickets_stored', sa.Integer(), nullable=False, server_default='5'),
    )
    op.add_column(
        'accounts',
        sa.Column('arena_tickets_last_tick_at', sa.DateTime(), nullable=False, server_default='CURRENT_TIMESTAMP'),
    )
    op.add_column(
        'accounts',
        sa.Column('arena_weekly_wins', sa.Integer(), nullable=False, server_default='0'),
    )
    op.add_column(
        'accounts',
        sa.Column('arena_weekly_key', sa.String(length=10), nullable=False, server_default=''),
    )

    op.create_table(
        'arena_weekly_payouts',
        sa.Column('week_key', sa.String(length=10), nullable=False),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('rank', sa.Integer(), nullable=False),
        sa.Column('gems', sa.Integer(), nullable=False),
        sa.Column('eligible_wins', sa.Integer(), nullable=False),
        sa.Column('granted_at', sa.DateTime(), nullable=False, server_default='CURRENT_TIMESTAMP'),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('week_key', 'account_id'),
    )
    op.create_index(
        'ix_arena_weekly_payouts_account_id',
        'arena_weekly_payouts',
        ['account_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_arena_weekly_payouts_account_id', table_name='arena_weekly_payouts')
    op.drop_table('arena_weekly_payouts')
    op.drop_column('accounts', 'arena_weekly_key')
    op.drop_column('accounts', 'arena_weekly_wins')
    op.drop_column('accounts', 'arena_tickets_last_tick_at')
    op.drop_column('accounts', 'arena_tickets_stored')
