import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.audit import log_audit_event
from app.core.errors import AppError, NotFoundError
from app.db.models.project import Project
from app.db.models.project_assignment import ProjectAssignment
from app.projects.schemas import ProjectCreateRequest, ProjectUpdateRequest


class ProjectService:
    def __init__(self, db: AsyncSession, org_id: uuid.UUID):
        self.db = db
        self.org_id = org_id

    async def list_projects(self) -> List[Project]:
        stmt = (
            select(Project)
            .where(Project.org_id == self.org_id)
            .order_by(Project.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_project(self, project_id: uuid.UUID) -> Project:
        stmt = select(Project).where(Project.id == project_id, Project.org_id == self.org_id)
        project = (await self.db.execute(stmt)).scalar_one_or_none()
        if not project:
            raise NotFoundError("Project", project_id)
        return project

    async def create_project(self, user_id: uuid.UUID, req: ProjectCreateRequest) -> Project:
        # Check duplicate key in org
        clean_key = req.key.strip().upper()
        stmt = select(Project).where(Project.org_id == self.org_id, Project.key == clean_key)
        existing = (await self.db.execute(stmt)).scalar_one_or_none()
        if existing:
            raise AppError(status_code=400, detail=f"Project key '{clean_key}' is already in use in this organization", code="KEY_EXISTS")

        project = Project(
            org_id=self.org_id,
            name=req.name.strip(),
            key=clean_key,
            description=req.description.strip() if req.description else "",
            created_by=user_id,
        )
        self.db.add(project)
        await self.db.flush()

        # Creator automatically assigned to project
        assignment = ProjectAssignment(
            org_id=self.org_id,
            project_id=project.id,
            user_id=user_id,
            assigned_by=user_id,
        )
        self.db.add(assignment)

        await log_audit_event(
            self.db,
            user_id=user_id,
            org_id=self.org_id,
            action="project.created",
            resource_type="project",
            resource_id=project.id,
            after_state={"name": project.name, "key": project.key},
        )
        await self.db.commit()
        return project

    async def update_project(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        req: ProjectUpdateRequest,
    ) -> Project:
        project = await self.get_project(project_id)
        before_state = {"name": project.name, "description": project.description, "status": project.status}

        if req.name is not None:
            project.name = req.name.strip()
        if req.description is not None:
            project.description = req.description.strip()
        if req.status is not None:
            project.status = req.status

        await log_audit_event(
            self.db,
            user_id=user_id,
            org_id=self.org_id,
            action="project.updated",
            resource_type="project",
            resource_id=project.id,
            before_state=before_state,
            after_state={"name": project.name, "description": project.description, "status": project.status},
        )
        await self.db.commit()
        return project

    async def delete_project(self, user_id: uuid.UUID, project_id: uuid.UUID) -> None:
        project = await self.get_project(project_id)
        await log_audit_event(
            self.db,
            user_id=user_id,
            org_id=self.org_id,
            action="project.deleted",
            resource_type="project",
            resource_id=project.id,
            before_state={"name": project.name, "key": project.key},
        )
        await self.db.delete(project)
        await self.db.commit()

    async def assign_member(
        self,
        actor_id: uuid.UUID,
        project_id: uuid.UUID,
        user_id: Optional[uuid.UUID] = None,
        team_id: Optional[uuid.UUID] = None,
    ) -> ProjectAssignment:
        await self.get_project(project_id)

        if not user_id and not team_id:
            raise AppError(status_code=400, detail="Must assign either user_id or team_id")
        if user_id and team_id:
            raise AppError(status_code=400, detail="Cannot assign both user_id and team_id in one record")

        # Check existing
        stmt = select(ProjectAssignment).where(
            ProjectAssignment.project_id == project_id,
            ProjectAssignment.org_id == self.org_id,
        )
        if user_id:
            stmt = stmt.where(ProjectAssignment.user_id == user_id)
        if team_id:
            stmt = stmt.where(ProjectAssignment.team_id == team_id)

        existing = (await self.db.execute(stmt)).scalar_one_or_none()
        if existing:
            return existing

        assignment = ProjectAssignment(
            org_id=self.org_id,
            project_id=project_id,
            user_id=user_id,
            team_id=team_id,
            assigned_by=actor_id,
        )
        self.db.add(assignment)
        await self.db.commit()
        return assignment
