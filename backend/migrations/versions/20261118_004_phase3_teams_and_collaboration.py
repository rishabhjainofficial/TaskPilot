"""phase3_teams_and_collaboration

Revision ID: 004_phase3_teams_and_collaboration
Revises: 003_multi_tenant_hardening
Create Date: 2026-11-18 11:00:00

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from app.db.rls import enable_rls_sql, disable_rls_sql

revision = '004_phase3_teams_and_collaboration'
down_revision = '003_multi_tenant_hardening'
branch_labels = None
depends_on = None

PHASE3_TABLES = [
    "teams",
    "team_members",
    "task_comments",
    "attachments",
    "time_logs",
]


def upgrade() -> None:
    # 1. Teams
    op.create_table(
        'teams',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.String(100), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint('org_id', 'name', name='uq_team_org_name'),
    )
    op.create_index('ix_teams_org_id', 'teams', ['org_id'])

    # 2. Team Members
    op.create_table(
        'team_members',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('team_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('teams.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('team_role', sa.String(20), nullable=False, server_default='member'),
        sa.Column('job_title', sa.String(100), nullable=True),
        sa.Column('joined_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint("team_role IN ('lead', 'member')", name='ck_team_member_role'),
        sa.UniqueConstraint('team_id', 'user_id', name='uq_team_member_team_user'),
    )
    op.create_index('ix_team_members_org_id', 'team_members', ['org_id'])
    op.create_index('ix_team_members_team_id', 'team_members', ['team_id'])
    op.create_index('ix_team_members_user_id', 'team_members', ['user_id'])
    op.create_index('idx_team_members_org_user', 'team_members', ['org_id', 'user_id'])
    op.create_index('idx_team_one_lead', 'team_members', ['team_id'], unique=True, postgresql_where=sa.text("team_role = 'lead'"))

    # 3. Task Comments
    op.create_table(
        'task_comments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('parent_comment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('task_comments.id', ondelete='CASCADE'), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_task_comments_org_id', 'task_comments', ['org_id'])
    op.create_index('ix_task_comments_task_id', 'task_comments', ['task_id'])
    op.create_index('ix_task_comments_user_id', 'task_comments', ['user_id'])
    op.create_index('idx_task_comments_org_task_created', 'task_comments', ['org_id', 'task_id', 'created_at'])

    # 4. Attachments
    op.create_table(
        'attachments',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('comment_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('task_comments.id', ondelete='SET NULL'), nullable=True),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('filename', sa.String(255), nullable=False),
        sa.Column('storage_key', sa.Text(), nullable=False, unique=True),
        sa.Column('content_type', sa.String(100), nullable=False),
        sa.Column('size_bytes', sa.BigInteger(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_attachments_org_id', 'attachments', ['org_id'])
    op.create_index('ix_attachments_task_id', 'attachments', ['task_id'])
    op.create_index('ix_attachments_user_id', 'attachments', ['user_id'])
    op.create_index('idx_attachments_org_task', 'attachments', ['org_id', 'task_id'])

    # 5. Time Logs
    op.create_table(
        'time_logs',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('org_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('organizations.id', ondelete='CASCADE'), nullable=False),
        sa.Column('task_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('tasks.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('duration_minutes', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('log_date', sa.Date(), nullable=False, server_default=sa.func.current_date()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.CheckConstraint('duration_minutes > 0', name='ck_time_log_duration_positive'),
    )
    op.create_index('ix_time_logs_org_id', 'time_logs', ['org_id'])
    op.create_index('ix_time_logs_task_id', 'time_logs', ['task_id'])
    op.create_index('ix_time_logs_user_id', 'time_logs', ['user_id'])
    op.create_index('idx_time_logs_org_task_date', 'time_logs', ['org_id', 'task_id', 'log_date'])
    op.create_index('idx_time_logs_org_user_date', 'time_logs', ['org_id', 'user_id', 'log_date'])

    # 6. Apply RLS on all Phase 3 tables
    for table in PHASE3_TABLES:
        op.execute(enable_rls_sql(table))


def downgrade() -> None:
    for table in reversed(PHASE3_TABLES):
        op.execute(disable_rls_sql(table))

    op.drop_table('time_logs')
    op.drop_table('attachments')
    op.drop_table('task_comments')
    op.drop_table('team_members')
    op.drop_table('teams')
