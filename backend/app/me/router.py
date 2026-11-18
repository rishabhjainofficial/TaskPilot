import uuid
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import UserProfileResponse
from app.core.permissions import load_role_permissions
from app.dependencies import get_current_user, get_current_org_id, get_db
from app.db.models.membership import Membership
from app.db.models.organization import Organization
from app.db.models.user import User

router = APIRouter(prefix="/me", tags=["User Profile"])


@router.get("", response_model=UserProfileResponse)
async def get_me(
    user: User = Depends(get_current_user),
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
):
    # Fetch all active memberships with org details
    stmt = (
        select(Membership, Organization)
        .join(Organization, Membership.org_id == Organization.id)
        .where(Membership.user_id == user.id, Membership.status == "active")
    )
    results = (await db.execute(stmt)).all()

    org_list = []
    current_role = None
    for mem, org in results:
        org_list.append({
            "id": str(org.id),
            "name": org.name,
            "slug": org.slug,
            "role": mem.org_role,
        })
        if mem.org_id == org_id:
            current_role = mem.org_role

    # Calculate effective permissions
    permissions = []
    if current_role == "owner":
        # Owner gets all permissions
        role_perms = await load_role_permissions(db)
        all_perms = set()
        for perms in role_perms.values():
            all_perms.update(perms)
        permissions = sorted(list(all_perms))
    elif current_role:
        role_perms = await load_role_permissions(db)
        permissions = sorted(list(role_perms.get(current_role, set())))

    return UserProfileResponse(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        avatar_url=user.avatar_url,
        is_platform_admin=user.is_platform_admin,
        email_verified=user.email_verified,
        current_org_id=org_id,
        current_role=current_role,
        organizations=org_list,
        permissions=permissions,
    )
