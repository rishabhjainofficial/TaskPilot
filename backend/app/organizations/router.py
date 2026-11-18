import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.schemas import InviteMemberRequest
from app.auth.service import AuthService
from app.config import get_settings
from app.core.permissions import require_permission
from app.dependencies import get_current_user, get_current_org_id, get_tenant_db, get_db
from app.db.models.user import User
from app.organizations.schemas import OrgResponse, UpdateOrgRequest, OrgMemberResponse, UpdateMemberRoleRequest
from app.organizations.service import OrganizationService

settings = get_settings()
router = APIRouter(prefix="/org", tags=["Organizations"])


@router.get("", response_model=OrgResponse)
async def get_current_org(
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("org.settings")),
):
    service = OrganizationService(db, org_id)
    org = await service.get_org()
    return OrgResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        industry=org.industry,
        settings=org.settings,
        created_at=org.created_at,
    )


@router.patch("", response_model=OrgResponse)
async def update_org(
    body: UpdateOrgRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("org.settings")),
):
    service = OrganizationService(db, org_id)
    org = await service.update_org(user.id, body)
    return OrgResponse(
        id=org.id,
        name=org.name,
        slug=org.slug,
        industry=org.industry,
        settings=org.settings,
        created_at=org.created_at,
    )


@router.get("/members", response_model=List[OrgMemberResponse])
async def list_members(
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("org.members.manage")),
):
    service = OrganizationService(db, org_id)
    return await service.list_members()


@router.post("/members/invite", status_code=status.HTTP_201_CREATED)
async def invite_member(
    body: InviteMemberRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(require_permission("org.members.invite")),
):
    auth_service = AuthService(db)
    invitation, raw_token = await auth_service.create_invitation(
        org_id=org_id,
        inviter_id=user.id,
        email=body.email,
        role=body.role,
    )
    return {
        "status": "ok",
        "message": f"Invitation created for {body.email}",
        "invitation_id": invitation.id,
        "token": raw_token if settings.ENVIRONMENT in ("development", "test") else None,
        "expires_at": invitation.expires_at,
    }


@router.patch("/members/{membership_id}/role")
async def update_member_role(
    membership_id: uuid.UUID,
    body: UpdateMemberRoleRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("org.members.manage")),
):
    service = OrganizationService(db, org_id)
    mem = await service.update_member_role(user.id, membership_id, body.role)
    return {"status": "ok", "membership_id": mem.id, "new_role": mem.org_role}


@router.delete("/members/{membership_id}")
async def deactivate_member(
    membership_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("org.members.manage")),
):
    service = OrganizationService(db, org_id)
    await service.deactivate_member(user.id, membership_id)
    return {"status": "ok", "message": "Member deactivated successfully"}
