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
    """Checks whether the user has a direct assignment to the project."""
    stmt = select(ProjectAssignment).where(
        ProjectAssignment.project_id == project_id,
        ProjectAssignment.user_id == user_id,
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None


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
    3. If project-scoped permission and role requires project assignment, check it.
    """
    if user.is_platform_admin and permission.startswith("platform."):
        return True

    membership = await get_user_org_membership(db, user.id, org_id)
    if not membership:
        return False

    # Owner has all org permissions except when specifically constrained
    if membership.org_role == "owner":
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
    """
    from app.dependencies import get_current_user, get_current_org_id, get_db

    async def dependency(
        user: User = Depends(get_current_user),
        org_id: uuid.UUID = Depends(get_current_org_id),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        allowed = await has_permission(user, org_id, permission, db)
        if not allowed:
            raise PermissionDeniedError(permission)
        return user

    return dependency
