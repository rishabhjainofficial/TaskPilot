import uuid
from typing import List, Optional
from sqlalchemy import select, update, delete, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit_event
from app.core.errors import AppError, NotFoundError
from app.db.models.membership import Membership
from app.db.models.team import Team
from app.db.models.team_member import TeamMember
from app.db.models.user import User
from app.teams.schemas import (
    TeamCreateRequest,
    TeamUpdateRequest,
    TeamMemberAddRequest,
    TeamMemberUpdateRequest,
    TeamResponse,
    TeamDetailResponse,
    TeamMemberResponse,
)


class TeamService:
    def __init__(self, db: AsyncSession, org_id: uuid.UUID):
        self.db = db
        self.org_id = org_id

    async def list_teams(self) -> List[TeamResponse]:
        stmt = (
            select(Team)
            .where(Team.org_id == self.org_id)
            .order_by(Team.name.asc())
        )
        teams = list((await self.db.execute(stmt)).scalars().all())

        responses: List[TeamResponse] = []
        for t in teams:
            # Count members
            count_stmt = (
                select(func.count(TeamMember.id))
                .where(TeamMember.team_id == t.id, TeamMember.org_id == self.org_id)
            )
            count = (await self.db.execute(count_stmt)).scalar_one() or 0

            # Find lead
            lead_stmt = (
                select(TeamMember, User)
                .join(User, TeamMember.user_id == User.id)
                .where(
                    TeamMember.team_id == t.id,
                    TeamMember.org_id == self.org_id,
                    TeamMember.team_role == "lead",
                )
            )
            lead_res = (await self.db.execute(lead_stmt)).first()
            lead_resp = None
            if lead_res:
                tm, u = lead_res
                lead_resp = TeamMemberResponse(
                    id=tm.id,
                    team_id=tm.team_id,
                    user_id=tm.user_id,
                    user_email=u.email,
                    user_full_name=u.full_name,
                    team_role=tm.team_role,
                    job_title=tm.job_title,
                    joined_at=tm.joined_at,
                )

            responses.append(
                TeamResponse(
                    id=t.id,
                    org_id=t.org_id,
                    name=t.name,
                    description=t.description,
                    created_at=t.created_at,
                    members_count=count,
                    lead=lead_resp,
                )
            )
        return responses

    async def get_team(self, team_id: uuid.UUID) -> TeamDetailResponse:
        stmt = select(Team).where(Team.id == team_id, Team.org_id == self.org_id)
        team = (await self.db.execute(stmt)).scalar_one_or_none()
        if not team:
            raise NotFoundError("Team", team_id)

        # Fetch members with User info
        mem_stmt = (
            select(TeamMember, User)
            .join(User, TeamMember.user_id == User.id)
            .where(TeamMember.team_id == team_id, TeamMember.org_id == self.org_id)
            .order_by(TeamMember.team_role.asc(), User.full_name.asc())
        )
        members_raw = (await self.db.execute(mem_stmt)).all()

        members = [
            TeamMemberResponse(
                id=tm.id,
                team_id=tm.team_id,
                user_id=tm.user_id,
                user_email=u.email,
                user_full_name=u.full_name,
                team_role=tm.team_role,
                job_title=tm.job_title,
                joined_at=tm.joined_at,
            )
            for tm, u in members_raw
        ]

        return TeamDetailResponse(
            id=team.id,
            org_id=team.org_id,
            name=team.name,
            description=team.description,
            created_at=team.created_at,
            members=members,
        )

    async def create_team(self, actor_id: uuid.UUID, req: TeamCreateRequest) -> Team:
        clean_name = req.name.strip()
        stmt = select(Team).where(Team.org_id == self.org_id, Team.name == clean_name)
        existing = (await self.db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise AppError(status_code=400, detail=f"Team '{clean_name}' already exists in this organization", code="TEAM_EXISTS")

        team = Team(
            org_id=self.org_id,
            name=clean_name,
            description=req.description.strip() if req.description else None,
        )
        self.db.add(team)
        await self.db.flush()

        await log_audit_event(
            self.db,
            user_id=actor_id,
            org_id=self.org_id,
            action="team.created",
            resource_type="team",
            resource_id=team.id,
            after_state={"name": team.name},
        )
        await self.db.commit()
        return team

    async def update_team(self, actor_id: uuid.UUID, team_id: uuid.UUID, req: TeamUpdateRequest) -> Team:
        stmt = select(Team).where(Team.id == team_id, Team.org_id == self.org_id)
        team = (await self.db.execute(stmt)).scalar_one_or_none()
        if not team:
            raise NotFoundError("Team", team_id)

        before_state = {"name": team.name, "description": team.description}
        if req.name is not None:
            team.name = req.name.strip()
        if req.description is not None:
            team.description = req.description.strip() if req.description else None

        await log_audit_event(
            self.db,
            user_id=actor_id,
            org_id=self.org_id,
            action="team.updated",
            resource_type="team",
            resource_id=team.id,
            before_state=before_state,
            after_state={"name": team.name, "description": team.description},
        )
        await self.db.commit()
        return team

    async def delete_team(self, actor_id: uuid.UUID, team_id: uuid.UUID) -> None:
        stmt = select(Team).where(Team.id == team_id, Team.org_id == self.org_id)
        team = (await self.db.execute(stmt)).scalar_one_or_none()
        if not team:
            raise NotFoundError("Team", team_id)

        await log_audit_event(
            self.db,
            user_id=actor_id,
            org_id=self.org_id,
            action="team.deleted",
            resource_type="team",
            resource_id=team.id,
            before_state={"name": team.name},
        )
        await self.db.delete(team)
        await self.db.commit()

    async def add_member(self, actor_id: uuid.UUID, team_id: uuid.UUID, req: TeamMemberAddRequest) -> TeamMember:
        # Check team exists
        stmt_t = select(Team).where(Team.id == team_id, Team.org_id == self.org_id)
        if not (await self.db.execute(stmt_t)).scalar_one_or_none():
            raise NotFoundError("Team", team_id)

        # Verify user is an active member of this organization
        stmt_m = select(Membership).where(
            Membership.user_id == req.user_id,
            Membership.org_id == self.org_id,
            Membership.status == "active",
        )
        if not (await self.db.execute(stmt_m)).scalar_one_or_none():
            raise AppError(status_code=400, detail="User is not an active member of this organization", code="USER_NOT_ORG_MEMBER")

        # Check if already in team
        stmt_tm = select(TeamMember).where(TeamMember.team_id == team_id, TeamMember.user_id == req.user_id)
        if (await self.db.execute(stmt_tm)).scalar_one_or_none():
            raise AppError(status_code=400, detail="User is already a member of this team", code="ALREADY_TEAM_MEMBER")

        # If designated as lead, atomically demote any existing lead on this team
        if req.team_role == "lead":
            demote_stmt = (
                update(TeamMember)
                .where(TeamMember.team_id == team_id, TeamMember.team_role == "lead")
                .values(team_role="member")
            )
            await self.db.execute(demote_stmt)
            await self.db.flush()

        member = TeamMember(
            org_id=self.org_id,
            team_id=team_id,
            user_id=req.user_id,
            team_role=req.team_role,
            job_title=req.job_title.strip() if req.job_title else None,
        )
        self.db.add(member)
        await self.db.flush()

        await log_audit_event(
            self.db,
            user_id=actor_id,
            org_id=self.org_id,
            action="team.member_added",
            resource_type="team",
            resource_id=team_id,
            after_state={"user_id": str(req.user_id), "team_role": req.team_role, "job_title": req.job_title},
        )
        await self.db.commit()
        return member

    async def update_member(
        self,
        actor_id: uuid.UUID,
        team_id: uuid.UUID,
        user_id: uuid.UUID,
        req: TeamMemberUpdateRequest,
    ) -> TeamMember:
        stmt = select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id,
            TeamMember.org_id == self.org_id,
        )
        member = (await self.db.execute(stmt)).scalar_one_or_none()
        if not member:
            raise NotFoundError("TeamMember", user_id)

        # Atomic lead promotion
        if req.team_role == "lead" and member.team_role != "lead":
            demote_stmt = (
                update(TeamMember)
                .where(TeamMember.team_id == team_id, TeamMember.team_role == "lead")
                .values(team_role="member")
            )
            await self.db.execute(demote_stmt)
            await self.db.flush()
            member.team_role = "lead"
        elif req.team_role is not None:
            member.team_role = req.team_role

        if req.job_title is not None:
            member.job_title = req.job_title.strip() if req.job_title else None

        await log_audit_event(
            self.db,
            user_id=actor_id,
            org_id=self.org_id,
            action="team.member_updated",
            resource_type="team",
            resource_id=team_id,
            after_state={"user_id": str(user_id), "team_role": member.team_role, "job_title": member.job_title},
        )
        await self.db.commit()
        return member

    async def remove_member(self, actor_id: uuid.UUID, team_id: uuid.UUID, user_id: uuid.UUID) -> None:
        stmt = select(TeamMember).where(
            TeamMember.team_id == team_id,
            TeamMember.user_id == user_id,
            TeamMember.org_id == self.org_id,
        )
        member = (await self.db.execute(stmt)).scalar_one_or_none()
        if not member:
            raise NotFoundError("TeamMember", user_id)

        await log_audit_event(
            self.db,
            user_id=actor_id,
            org_id=self.org_id,
            action="team.member_removed",
            resource_type="team",
            resource_id=team_id,
            before_state={"user_id": str(user_id)},
        )
        await self.db.delete(member)
        await self.db.commit()
