"""phases_4_to_7
Document-to-Plan AI Generation, Notifications, and advanced collaboration.

Revision ID: 005_phases_4_to_7
Revises: 004_phase3_teams_and_collaboration
Create Date: 2026-11-18 11:30:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from app.db.rls import enable_rls_sql, disable_rls_sql

revision = '005_phases_4_to_7'
down_revision = '004_phase3_teams_and_collaboration'
branch_labels = None
depends_on = None

NEW_TABLES = [
    "project_documents",
    "notifications",
]


def upgrade() -> None:
    # 1. Project Documents (Phase 4 Document-to-Plan)
    op.create_table(
        'project_documents',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('storage_key', sa.String(500), nullable=False, unique=True),
        sa.Column('content_type', sa.String(100), nullable=False, server_default='text/plain'),
        sa.Column('file_size', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(20), nullable=False, server_default='uploaded'),
        sa.Column('extracted_text', sa.Text(), nullable=True),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('proposal_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ai_proposals.id', ondelete='SET NULL'), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_project_documents_org_id', 'project_documents', ['org_id'])
    op.create_index('idx_project_docs_org_project', 'project_documents', ['org_id', 'project_id', sa.text('created_at DESC')])

    # 2. Notifications (Phase 7 Real-Time & Activity)
    op.create_table(
        'notifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('type', sa.String(50), nullable=False, server_default='system'),
        sa.Column('title', sa.String(150), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('link', sa.String(500), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_notifications_org_id', 'notifications', ['org_id'])
    op.create_index('idx_notifications_org_user_unread', 'notifications', ['org_id', 'user_id', 'is_read', sa.text('created_at DESC')])

    # 3. Apply RLS
    for table in NEW_TABLES:
        op.execute(enable_rls_sql(table))


def downgrade() -> None:
    for table in reversed(NEW_TABLES):
        op.execute(disable_rls_sql(table))

    op.drop_table('notifications')
    op.drop_table('project_documents')
