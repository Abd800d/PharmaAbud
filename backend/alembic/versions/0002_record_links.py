"""record_links table (§11 equivalents, §16/§111 duplicate-link review)

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-14
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'record_links',
        sa.Column('link_type', sa.String(length=32), nullable=False),
        sa.Column('entity_a_type', sa.String(length=32), nullable=False),
        sa.Column('entity_a_id', sa.String(length=36), nullable=False),
        sa.Column('entity_b_type', sa.String(length=32), nullable=False),
        sa.Column('entity_b_id', sa.String(length=36), nullable=False),
        sa.Column('status', sa.String(length=32), nullable=False),
        sa.Column('why', sa.Text(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=False),
        sa.Column('linked_by', sa.String(length=36), nullable=True),
        sa.Column('checked_by', sa.String(length=36), nullable=True),
        sa.Column('approved_by', sa.String(length=36), nullable=True),
        sa.Column('approval_date', sa.DateTime(), nullable=True),
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(['linked_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['checked_by'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['approved_by'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('link_type', 'entity_a_id', 'entity_b_id', name='uq_record_link'),
    )
    op.create_index('ix_record_links_link_type', 'record_links', ['link_type'])
    op.create_index('ix_record_links_entity_a_id', 'record_links', ['entity_a_id'])
    op.create_index('ix_record_links_entity_b_id', 'record_links', ['entity_b_id'])
    op.create_index('ix_record_links_status', 'record_links', ['status'])


def downgrade() -> None:
    op.drop_index('ix_record_links_status', table_name='record_links')
    op.drop_index('ix_record_links_entity_b_id', table_name='record_links')
    op.drop_index('ix_record_links_entity_a_id', table_name='record_links')
    op.drop_index('ix_record_links_link_type', table_name='record_links')
    op.drop_table('record_links')
