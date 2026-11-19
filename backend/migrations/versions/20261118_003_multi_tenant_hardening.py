"""multi_tenant_hardening

Revision ID: 003_multi_tenant_hardening
Revises: 002_ai_agent
Create Date: 2026-11-18 10:30:00

"""
from alembic import op
import sqlalchemy as sa
from app.db.rls import enable_rls_sql, disable_rls_sql

revision = '003_multi_tenant_hardening'
down_revision = '002_ai_agent'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Soft-delete support on organizations
    op.add_column('organizations', sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('idx_organizations_deleted_at', 'organizations', ['deleted_at'])

    # 2. Composite indexes for high-frequency multi-tenant queries (leftmost prefix = org_id)
    op.create_index('idx_ai_usage_org_created', 'ai_usage', ['org_id', 'created_at'])
    op.create_index('idx_tasks_org_project_status', 'tasks', ['org_id', 'project_id', 'status'])
    op.create_index('idx_tasks_org_created', 'tasks', ['org_id', 'created_at'])
    op.create_index('idx_tasks_org_assignee', 'tasks', ['org_id', 'assignee_id'])

    # 3. Re-apply specialized RLS policies on memberships and invitations
    op.execute(enable_rls_sql('memberships'))
    op.execute(enable_rls_sql('invitations'))


def downgrade() -> None:
    # Revert specialized policies
    op.execute(disable_rls_sql('invitations'))
    op.execute(disable_rls_sql('memberships'))

    # Drop indexes
    op.drop_index('idx_tasks_org_assignee', table_name='tasks')
    op.drop_index('idx_tasks_org_created', table_name='tasks')
    op.drop_index('idx_tasks_org_project_status', table_name='tasks')
    op.drop_index('idx_ai_usage_org_created', table_name='ai_usage')
    op.drop_index('idx_organizations_deleted_at', table_name='organizations')

    # Drop deleted_at
    op.drop_column('organizations', 'deleted_at')
