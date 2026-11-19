"""
PostgreSQL Row-Level Security (RLS) helpers.
Ensures both USING and WITH CHECK are enforced, along with FORCE ROW LEVEL SECURITY.
Includes specialized policies for bridge tables (memberships, invitations).
"""

RLS_ENABLED_TABLES = [
    "memberships",
    "invitations",
    "projects",
    "project_assignments",
    "tasks",
    "task_dependencies",
    "labels",
    "task_labels",
    "subscriptions",
    "ai_conversations",
    "ai_messages",
    "ai_proposals",
    "ai_usage",
    "teams",
    "team_members",
    "task_comments",
    "attachments",
    "time_logs",
    "project_documents",
    "notifications",
]


def enable_rls_sql(table_name: str) -> str:
    if table_name == "memberships":
        return f"""
        ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;
        ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY;

        DROP POLICY IF EXISTS tenant_isolation ON {table_name};
        CREATE POLICY tenant_isolation ON {table_name}
            USING (
                org_id = NULLIF(current_setting('app.current_org', true), '')::uuid
                OR user_id = NULLIF(current_setting('app.current_user_id', true), '')::uuid
            )
            WITH CHECK (
                org_id = NULLIF(current_setting('app.current_org', true), '')::uuid
            );
        """
    elif table_name == "invitations":
        return f"""
        ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;
        ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY;

        DROP POLICY IF EXISTS tenant_isolation ON {table_name};
        CREATE POLICY tenant_isolation ON {table_name}
            USING (
                org_id = NULLIF(current_setting('app.current_org', true), '')::uuid
                OR current_setting('app.invitation_lookup_mode', true) = 'token_redeem'
            )
            WITH CHECK (
                org_id = NULLIF(current_setting('app.current_org', true), '')::uuid
            );
        """
    else:
        return f"""
        ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY;
        ALTER TABLE {table_name} FORCE ROW LEVEL SECURITY;

        DROP POLICY IF EXISTS tenant_isolation ON {table_name};
        CREATE POLICY tenant_isolation ON {table_name}
            USING (org_id = NULLIF(current_setting('app.current_org', true), '')::uuid)
            WITH CHECK (org_id = NULLIF(current_setting('app.current_org', true), '')::uuid);
        """


def disable_rls_sql(table_name: str) -> str:
    return f"""
    DROP POLICY IF EXISTS tenant_isolation ON {table_name};
    ALTER TABLE {table_name} NO FORCE ROW LEVEL SECURITY;
    ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY;
    """
