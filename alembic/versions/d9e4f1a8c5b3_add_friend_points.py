"""add friend points columns + friend_pings table

Revision ID: d9e4f1a8c5b3
Revises: b5e2a7f9d3c1
Create Date: 2026-05-08 18:05:00.000000

Phase 5 retention — Friend Points + friend-summon banner. New currency
on accounts + per-day ping log table for daily-cap idempotency.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd9e4f1a8c5b3'
down_revision: Union[str, Sequence[str], None] = 'b5e2a7f9d3c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.add_column(sa.Column('friend_points', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('friend_pings_sent_today', sa.Integer(), nullable=False, server_default='0'))
        batch_op.add_column(sa.Column('friend_pings_today_date', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('fp_pulls_since_epic', sa.Integer(), nullable=False, server_default='0'))

    op.create_table(
        'friend_pings',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('sender_id', sa.Integer(), nullable=False),
        sa.Column('recipient_id', sa.Integer(), nullable=False),
        sa.Column('sent_on', sa.DateTime(), nullable=False),
        sa.Column('fp_granted', sa.Integer(), nullable=False, server_default='5'),
        sa.ForeignKeyConstraint(['sender_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['recipient_id'], ['accounts.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('sender_id', 'recipient_id', 'sent_on', name='uq_friend_pings_per_day'),
    )
    op.create_index('ix_friend_pings_sender_id', 'friend_pings', ['sender_id'])
    op.create_index('ix_friend_pings_recipient_id', 'friend_pings', ['recipient_id'])
    op.create_index('ix_friend_pings_sent_on', 'friend_pings', ['sent_on'])


def downgrade() -> None:
    op.drop_index('ix_friend_pings_sent_on', table_name='friend_pings')
    op.drop_index('ix_friend_pings_recipient_id', table_name='friend_pings')
    op.drop_index('ix_friend_pings_sender_id', table_name='friend_pings')
    op.drop_table('friend_pings')
    with op.batch_alter_table('accounts', schema=None) as batch_op:
        batch_op.drop_column('fp_pulls_since_epic')
        batch_op.drop_column('friend_pings_today_date')
        batch_op.drop_column('friend_pings_sent_today')
        batch_op.drop_column('friend_points')
