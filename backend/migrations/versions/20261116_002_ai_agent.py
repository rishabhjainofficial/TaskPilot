"""ai_agent_tables

Revision ID: 002_ai_agent
Revises: 001_initial
Create Date: 2026-11-16 01:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from app.db.rls import enable_rls_sql, disable_rls_sql

revision = '002_ai_agent'
down_revision = '001_initial'
branch_labels = None
depends_on = None

AI_TABLES = [
    "ai_conversations",
    "ai_messages",
    "ai_proposals",
    "ai_usage",
]


def upgrade() -> None:
    # 1. AI Conversations
    op.create_table(
        'ai_conversations',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_ai_conversations_org_id', 'ai_conversations', ['org_id'])
    op.create_index('ix_ai_conversations_project_id', 'ai_conversations', ['project_id'])
    op.create_index('ix_ai_conversations_user_id', 'ai_conversations', ['user_id'])

    # 2. AI Messages
    op.create_table(
        'ai_messages',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ai_conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('role', sa.String(20), nullable=False),
        sa.Column('content', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_ai_messages_org_id', 'ai_messages', ['org_id'])
    op.create_index('ix_ai_messages_conversation_id', 'ai_messages', ['conversation_id'])

    # 3. AI Proposals
    op.create_table(
        'ai_proposals',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('conversation_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('ai_conversations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('project_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('projects.id', ondelete='CASCADE'), nullable=False),
        sa.Column('actions', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column('explanation', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('result', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index('ix_ai_proposals_org_id', 'ai_proposals', ['org_id'])
    op.create_index('ix_ai_proposals_conversation_id', 'ai_proposals', ['conversation_id'])
    op.create_index('ix_ai_proposals_status', 'ai_proposals', ['status'])

    # 4. AI Usage
    op.create_table(
        'ai_usage',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('feature', sa.String(30), nullable=False),
        sa.Column('model', sa.String(50), nullable=False),
        sa.Column('input_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('output_tokens', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('cost_usd', sa.Numeric(10, 6), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_ai_usage_org_id', 'ai_usage', ['org_id'])
    op.create_index('ix_ai_usage_created_at', 'ai_usage', ['created_at'])

    # Enable RLS on all AI tables
    for table in AI_TABLES:
        op.execute(enable_rls_sql(table))


def downgrade() -> None:
    for table in reversed(AI_TABLES):
        op.execute(disable_rls_sql(table))

    op.drop_table('ai_usage')
    op.drop_table('ai_proposals')
    op.drop_table('ai_messages')
    op.drop_table('ai_conversations')
