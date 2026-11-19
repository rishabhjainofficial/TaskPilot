import uuid
from typing import Optional, Set
from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PermissionDeniedError
from app.db.models.membership import Membership
from app.db.models.permission import Permission, RolePermission
from app.db.models.project_assignment import ProjectAssignment
from app.db.models.user import User

# In-memory permission cache structure for fast lookup after initial seed/load
_PERMISSION_CACHE: dict[str, Set[str]] = {}


async def load_role_permissions(db: AsyncSession) -> dict[str, Set[str]]:
    """Loads all role->permission mappings from the database."""
    stmt = (
        select(RolePermission.role, Permission.code)
        .join(Permission, RolePermission.permission_id == Permission.id)
    )
    result = await db.execute(stmt)
    mapping: dict[str, Set[str]] = {}
    for role, code in result.all():
        mapping.setdefault(role, set()).add(code)
    return mapping


async def get_user_org_membership(
    db: AsyncSession,
    user_id: uuid.UUID,
    org_id: uuid.UUID,
) -> Optional[Membership]:
    """Retrieves active membership of user in the given organization."""
    stmt = select(Membership).where(
        Membership.user_id == user_id,
        Membership.org_id == org_id,
        Membership.status == "active",
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def is_user_assigned_to_project(
    db: AsyncSession,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> bool:
    """Checks whether the user has a direct assignment or a team assignment to the project."""
    # Direct user assignment
    stmt_user = select(ProjectAssignment).where(
        ProjectAssignment.project_id == project_id,
        ProjectAssignment.user_id == user_id,
    )
    if (await db.execute(stmt_user)).scalar_one_or_none():
        return True

    # Team assignment
    from app.db.models.team_member import TeamMember
    stmt_team = (
        select(ProjectAssignment)
        .join(TeamMember, ProjectAssignment.team_id == TeamMember.team_id)
        .where(
            ProjectAssignment.project_id == project_id,
            TeamMember.user_id == user_id,
        )
    )
    return (await db.execute(stmt_team)).scalar_one_or_none() is not None


async def is_user_lead_of_project(
    db: AsyncSession,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
) -> bool:
    """Checks whether user is the designated lead of any team assigned to the project."""
    from app.db.models.team_member import TeamMember
    stmt = (
        select(ProjectAssignment)
        .join(TeamMember, ProjectAssignment.team_id == TeamMember.team_id)
        .where(
            ProjectAssignment.project_id == project_id,
            TeamMember.user_id == user_id,
            TeamMember.team_role == "lead",
        )
    )
    return (await db.execute(stmt)).scalar_one_or_none() is not None


async def has_permission(
    user: User,
    org_id: uuid.UUID,
    permission: str,
    db: AsyncSession,
    project_id: Optional[uuid.UUID] = None,
) -> bool:
    """
    Central permission check.
    1. If user is platform admin, they only have platform permissions, not tenant data by default.
    2. Check org role permissions from DB.
    3. If project-scoped permission and user is Team Lead of that project, grant lead capabilities.
    4. If manager, enforce assignment scoping on project.
    """
    if user.is_platform_admin and permission.startswith("platform."):
        return True

    membership = await get_user_org_membership(db, user.id, org_id)
    if not membership:
        return False

    # Owner has all org permissions except when specifically constrained
    if membership.org_role == "owner":
        return True

    # Check team lead permissions for project-scoped actions
    if project_id and permission in ("task.create", "task.delete", "task.assign", "task.update_any", "task.view_all"):
        if await is_user_lead_of_project(db, user.id, project_id):
            return True

    role_perms = await load_role_permissions(db)
    allowed_perms = role_perms.get(membership.org_role, set())

    if permission not in allowed_perms:
        return False

    # Manager assignment scoping for project/task actions
    if membership.org_role == "manager" and project_id:
        if permission in ("task.create", "task.delete", "task.assign", "task.update_any", "project.manage"):
            assigned = await is_user_assigned_to_project(db, user.id, project_id)
            if not assigned:
                return False

    return True


def require_permission(permission: str, project_id_param: Optional[str] = None):
    """
    FastAPI dependency factory enforcing a specific permission string.
    Ensures tenant and user contexts are set for RLS-compliant role verification.
    """
    from fastapi import Request
    from app.dependencies import get_current_user, get_current_org_id, get_db
    from app.db.session import set_tenant_context

    async def dependency(
        request: Request,
        user: User = Depends(get_current_user),
        org_id: uuid.UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        project_id = None
        if project_id_param:
            raw_proj = request.path_params.get(project_id_param)
            if raw_proj:
                try:
                    project_id = uuid.UUID(raw_proj)
                except ValueError:
                    pass
        await set_tenant_context(db, org_id=org_id, user_id=user.id)
        allowed = await has_permission(user, org_id, permission, db, project_id=project_id)
        if not allowed:
            raise PermissionDeniedError(permission)
        return user

    return dependency
