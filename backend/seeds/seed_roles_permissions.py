import asyncio
import uuid
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from app.db.models.permission import Permission, RolePermission
from app.db.session import AsyncSessionLocal

PERMISSIONS = [
    ("org.delete", "Delete entire organization"),
    ("org.billing", "Manage billing and subscription plans"),
    ("org.settings", "Update organization settings and details"),
    ("org.members.manage", "Manage, promote, and deactivate members"),
    ("org.members.invite", "Send email invitations to new members"),
    ("project.create", "Create new projects"),
    ("project.delete", "Delete projects"),
    ("project.manage", "Update project details and member assignments"),
    ("team.create", "Create teams within organization"),
    ("team.manage", "Manage team memberships and designations"),
    ("task.create", "Create top-level tasks"),
    ("task.delete", "Delete tasks"),
    ("task.assign", "Assign tasks to users or teams"),
    ("task.update_any", "Update status and details of any task"),
    ("task.update_own", "Update status and details of assigned tasks"),
    ("task.view_all", "View all tasks in project"),
    ("task.view_assigned", "View only assigned tasks"),
    ("task.create_subtask", "Add subtasks to existing tasks"),
    ("comment.create", "Post comments on tasks"),
    ("attachment.upload", "Attach documents and files to tasks"),
    ("timelog.create", "Log hours and time entries"),
]

ROLE_BUNDLES = {
    ("admin", "org"): [
        "org.settings", "org.members.manage", "org.members.invite",
        "project.create", "project.delete", "project.manage",
        "team.create", "team.manage",
        "task.create", "task.delete", "task.assign", "task.update_any", "task.view_all",
        "task.update_own", "task.view_assigned", "task.create_subtask",
        "comment.create", "attachment.upload", "timelog.create",
    ],
    ("manager", "org"): [
        "org.members.invite",
        "project.create", "project.manage",
        "team.create", "team.manage",
        "task.create", "task.delete", "task.assign", "task.update_any", "task.view_all",
        "task.update_own", "task.view_assigned", "task.create_subtask",
        "comment.create", "attachment.upload", "timelog.create",
    ],
    ("member", "org"): [
        "task.view_assigned", "task.update_own", "task.create_subtask",
        "comment.create", "attachment.upload", "timelog.create",
    ],
    ("lead", "team"): [
        "task.create", "task.delete", "task.assign", "task.update_any",
    ],
}


async def seed():
    async with AsyncSessionLocal() as session:
        print("🌱 Seeding permissions...")
        perm_map = {}
        for code, desc in PERMISSIONS:
            stmt = select(Permission).where(Permission.code == code)
            perm = (await session.execute(stmt)).scalar_one_or_none()
            if not perm:
                perm = Permission(code=code, description=desc)
                session.add(perm)
                await session.flush()
            perm_map[code] = perm.id

        print("🌱 Seeding role-permission bundles...")
        for (role, scope), perms in ROLE_BUNDLES.items():
            for code in perms:
                perm_id = perm_map[code]
                stmt = select(RolePermission).where(
                    RolePermission.role == role,
                    RolePermission.scope == scope,
                    RolePermission.permission_id == perm_id,
                )
                existing = (await session.execute(stmt)).scalar_one_or_none()
                if not existing:
                    rp = RolePermission(role=role, scope=scope, permission_id=perm_id)
                    session.add(rp)

        await session.commit()
        print("✅ Permissions and role mappings seeded successfully.")


if __name__ == "__main__":
    asyncio.run(seed())
