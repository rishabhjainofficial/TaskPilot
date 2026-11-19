import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_permission
from app.dependencies import get_current_user, get_current_org_id, get_tenant_db
from app.db.models.user import User
from app.teams.schemas import (
    TeamCreateRequest,
    TeamUpdateRequest,
    TeamMemberAddRequest,
    TeamMemberUpdateRequest,
    TeamResponse,
    TeamDetailResponse,
)
from app.teams.service import TeamService

router = APIRouter(prefix="/teams", tags=["Teams"])


@router.get("", response_model=List[TeamResponse])
async def list_teams(
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = TeamService(db, org_id)
    return await service.list_teams()


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
async def create_team(
    body: TeamCreateRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("team.create")),
):
    service = TeamService(db, org_id)
    team = await service.create_team(user.id, body)
    return TeamResponse(
        id=team.id,
        org_id=team.org_id,
        name=team.name,
        description=team.description,
        created_at=team.created_at,
        members_count=0,
        lead=None,
    )


@router.get("/{team_id}", response_model=TeamDetailResponse)
async def get_team(
    team_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = TeamService(db, org_id)
    return await service.get_team(team_id)


@router.patch("/{team_id}", response_model=TeamResponse)
async def update_team(
    team_id: uuid.UUID,
    body: TeamUpdateRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("team.manage")),
):
    service = TeamService(db, org_id)
    team = await service.update_team(user.id, team_id, body)
    return TeamResponse(
        id=team.id,
        org_id=team.org_id,
        name=team.name,
        description=team.description,
        created_at=team.created_at,
    )


@router.delete("/{team_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_team(
    team_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("team.manage")),
):
    service = TeamService(db, org_id)
    await service.delete_team(user.id, team_id)


@router.post("/{team_id}/members", status_code=status.HTTP_201_CREATED)
async def add_team_member(
    team_id: uuid.UUID,
    body: TeamMemberAddRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("team.manage")),
):
    service = TeamService(db, org_id)
    member = await service.add_member(user.id, team_id, body)
    return {"status": "ok", "member_id": member.id, "team_role": member.team_role}


@router.patch("/{team_id}/members/{user_id}")
async def update_team_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    body: TeamMemberUpdateRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("team.manage")),
):
    service = TeamService(db, org_id)
    member = await service.update_member(user.id, team_id, user_id, body)
    return {"status": "ok", "team_role": member.team_role, "job_title": member.job_title}


@router.delete("/{team_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_team_member(
    team_id: uuid.UUID,
    user_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("team.manage")),
):
    service = TeamService(db, org_id)
    await service.remove_member(user.id, team_id, user_id)
