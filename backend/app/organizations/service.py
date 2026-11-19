import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit_event
from app.core.errors import AppError, NotFoundError
from app.db.models.membership import Membership
from app.db.models.organization import Organization
from app.db.models.task import Task
from app.db.models.user import User
from app.organizations.schemas import UpdateOrgRequest, OrgMemberResponse


class OrganizationService:
    def __init__(self, db: AsyncSession, org_id: uuid.UUID):
        self.db = db
        self.org_id = org_id

    async def get_org(self) -> Organization:
        stmt = select(Organization).where(Organization.id == self.org_id)
        org = (await self.db.execute(stmt)).scalar_one_or_none()
        if not org:
            raise NotFoundError("Organization", self.org_id)
        return org

    async def update_org(self, user_id: uuid.UUID, req: UpdateOrgRequest) -> Organization:
        org = await self.get_org()
        before_state = {"name": org.name, "industry": org.industry, "settings": org.settings}

        if req.name is not None:
            org.name = req.name.strip()
        if req.industry is not None:
            org.industry = req.industry.strip()
        if req.settings is not None:
            org.settings = req.settings

        await log_audit_event(
            self.db,
            user_id=user_id,
            org_id=self.org_id,
            action="organization.updated",
            resource_type="organization",
            resource_id=org.id,
            before_state=before_state,
            after_state={"name": org.name, "industry": org.industry, "settings": org.settings},
        )
        await self.db.commit()
        return org

    async def list_members(self) -> List[OrgMemberResponse]:
        stmt = (
            select(Membership, User)
            .join(User, Membership.user_id == User.id)
            .where(Membership.org_id == self.org_id, Membership.status == "active")
            .order_by(Membership.joined_at.asc())
        )
        results = (await self.db.execute(stmt)).all()
        return [
            OrgMemberResponse(
                id=mem.id,
                user_id=u.id,
                email=u.email,
                full_name=u.full_name,
                role=mem.org_role,
                status=mem.status,
                joined_at=mem.joined_at,
            )
            for mem, u in results
        ]

    async def update_member_role(
        self,
        actor_id: uuid.UUID,
        membership_id: uuid.UUID,
        new_role: str,
    ) -> Membership:
        stmt = select(Membership).where(Membership.id == membership_id, Membership.org_id == self.org_id)
        membership = (await self.db.execute(stmt)).scalar_one_or_none()
        if not membership:
            raise NotFoundError("Membership", membership_id)

        # Check last owner guardrail
        if membership.org_role == "owner" and new_role != "owner":
            owner_count_stmt = select(func.count(Membership.id)).where(
                Membership.org_id == self.org_id,
                Membership.org_role == "owner",
                Membership.status == "active",
            )
            count = (await self.db.execute(owner_count_stmt)).scalar_one()
            if count <= 1:
                raise AppError(status_code=400, detail="Cannot demote the last Owner of the organization", code="LAST_OWNER")

        old_role = membership.org_role
        membership.org_role = new_role

        await log_audit_event(
            self.db,
            user_id=actor_id,
            org_id=self.org_id,
            action="member.role_changed",
            resource_type="membership",
            resource_id=membership.id,
            before_state={"role": old_role},
            after_state={"role": new_role},
        )
        await self.db.commit()
        return membership

    async def deactivate_member(self, actor_id: uuid.UUID, membership_id: uuid.UUID) -> None:
        stmt = select(Membership).where(Membership.id == membership_id, Membership.org_id == self.org_id)
        membership = (await self.db.execute(stmt)).scalar_one_or_none()
        if not membership:
            raise NotFoundError("Membership", membership_id)

        # Guardrail: Last owner cannot be deactivated
        if membership.org_role == "owner":
            owner_count_stmt = select(func.count(Membership.id)).where(
                Membership.org_id == self.org_id,
                Membership.org_role == "owner",
                Membership.status == "active",
            )
            count = (await self.db.execute(owner_count_stmt)).scalar_one()
            if count <= 1:
                raise AppError(status_code=400, detail="Cannot deactivate the last Owner of the organization", code="LAST_OWNER")

        membership.status = "deactivated"
        membership.deactivated_at = datetime.now(timezone.utc)
        membership.deactivated_by = actor_id

        # Unassign any open tasks assigned to this user in this organization
        unassign_stmt = (
            update(Task)
            .where(Task.org_id == self.org_id, Task.assignee_id == membership.user_id)
            .values(assignee_id=None)
        )
        await self.db.execute(unassign_stmt)

        await log_audit_event(
            self.db,
            user_id=actor_id,
            org_id=self.org_id,
            action="member.deactivated",
            resource_type="membership",
            resource_id=membership.id,
        )
        await self.db.commit()

    async def soft_delete_org(self, user_id: uuid.UUID) -> Organization:
        org = await self.get_org()
        org.deleted_at = datetime.now(timezone.utc)

        await log_audit_event(
            self.db,
            user_id=user_id,
            org_id=self.org_id,
            action="organization.deleted",
            resource_type="organization",
            resource_id=org.id,
        )
        await self.db.commit()
        return org
