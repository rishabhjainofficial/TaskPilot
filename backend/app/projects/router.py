import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_permission
from app.dependencies import get_current_user, get_current_org_id, get_tenant_db
from app.db.models.user import User
from app.projects.schemas import (
    ProjectCreateRequest,
    ProjectUpdateRequest,
    ProjectResponse,
    ProjectAssignRequest,
    ProjectAssignmentResponse,
)
from app.projects.service import ProjectService

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("", response_model=List[ProjectResponse])
async def list_projects(
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("project.manage")),
):
    service = ProjectService(db, org_id)
    projects = await service.list_projects()
    return [
        ProjectResponse(
            id=p.id,
            org_id=p.org_id,
            name=p.name,
            key=p.key,
            description=p.description,
            status=p.status,
            created_by=p.created_by,
            created_at=p.created_at,
        )
        for p in projects
    ]


@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
async def create_project(
    body: ProjectCreateRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("project.create")),
):
    service = ProjectService(db, org_id)
    project = await service.create_project(user.id, body)
    return ProjectResponse(
        id=project.id,
        org_id=project.org_id,
        name=project.name,
        key=project.key,
        description=project.description,
        status=project.status,
        created_by=project.created_by,
        created_at=project.created_at,
    )


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = ProjectService(db, org_id)
    project = await service.get_project(project_id)
    return ProjectResponse(
        id=project.id,
        org_id=project.org_id,
        name=project.name,
        key=project.key,
        description=project.description,
        status=project.status,
        created_by=project.created_by,
        created_at=project.created_at,
    )


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    body: ProjectUpdateRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("project.manage")),
):
    service = ProjectService(db, org_id)
    project = await service.update_project(user.id, project_id, body)
    return ProjectResponse(
        id=project.id,
        org_id=project.org_id,
        name=project.name,
        key=project.key,
        description=project.description,
        status=project.status,
        created_by=project.created_by,
        created_at=project.created_at,
    )


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_project(
    project_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("project.delete")),
):
    service = ProjectService(db, org_id)
    await service.delete_project(user.id, project_id)


@router.post("/{project_id}/assign")
async def assign_project(
    project_id: uuid.UUID,
    body: ProjectAssignRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("project.manage")),
):
    service = ProjectService(db, org_id)
    assignment = await service.assign_member(
        actor_id=user.id,
        project_id=project_id,
        user_id=body.user_id,
        team_id=body.team_id,
    )
    return {"status": "ok", "assignment_id": assignment.id}


@router.get("/{project_id}/assignments", response_model=List[ProjectAssignmentResponse])
async def list_project_assignments(
    project_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = ProjectService(db, org_id)
    return await service.list_assignments(project_id)


@router.delete("/{project_id}/assignments/{assignment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_project_assignment(
    project_id: uuid.UUID,
    assignment_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("project.manage")),
):
    service = ProjectService(db, org_id)
    await service.remove_assignment(user.id, project_id, assignment_id)

