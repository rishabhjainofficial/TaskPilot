import uuid
from typing import List, Optional
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit import log_audit_event
from app.core.errors import AppError, NotFoundError
from app.db.models.project import Project
from app.db.models.task import Task
from app.tasks.schemas import TaskCreateRequest, TaskUpdateRequest, SubtaskCreateRequest


class TaskService:
    def __init__(self, db: AsyncSession, org_id: uuid.UUID):
        self.db = db
        self.org_id = org_id

    async def _get_next_task_number(self, project: Project) -> int:
        project.task_seq += 1
        return project.task_seq

    async def list_project_tasks(self, project_id: uuid.UUID) -> List[Task]:
        # First verify the project exists in this tenant
        stmt_proj = select(Project).where(Project.id == project_id, Project.org_id == self.org_id)
        proj = (await self.db.execute(stmt_proj)).scalar_one_or_none()
        if not proj:
            raise NotFoundError("Project", project_id)

        stmt = (
            select(Task)
            .where(
                Task.org_id == self.org_id,
                Task.project_id == project_id,
                Task.parent_task_id == None,  # Top-level tasks
            )
            .options(selectinload(Task.subtasks), selectinload(Task.project))
            .order_by(Task.position.asc(), Task.created_at.desc())
        )
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_task(self, task_id: uuid.UUID) -> Task:
        stmt = (
            select(Task)
            .where(Task.id == task_id, Task.org_id == self.org_id)
            .options(selectinload(Task.subtasks), selectinload(Task.project))
        )
        task = (await self.db.execute(stmt)).scalar_one_or_none()
        if not task:
            raise NotFoundError("Task", task_id)
        return task

    async def create_task(
        self,
        user_id: uuid.UUID,
        project_id: uuid.UUID,
        req: TaskCreateRequest,
    ) -> Task:
        stmt_proj = select(Project).where(Project.id == project_id, Project.org_id == self.org_id).with_for_update()
        project = (await self.db.execute(stmt_proj)).scalar_one_or_none()
        if not project:
            raise NotFoundError("Project", project_id)

        task_num = await self._get_next_task_number(project)

        task = Task(
            org_id=self.org_id,
            project_id=project_id,
            task_number=task_num,
            title=req.title.strip(),
            description=req.description or "",
            priority=req.priority or "medium",
            status=req.status or "todo",
            created_by=user_id,
            assignee_id=req.assignee_id,
            due_date=req.due_date,
            estimated_hours=req.estimated_hours,
        )
        self.db.add(task)
        await self.db.flush()

        # Add optional subtasks
        for st_req in req.subtasks:
            sub_num = await self._get_next_task_number(project)
            subtask = Task(
                org_id=self.org_id,
                project_id=project_id,
                parent_task_id=task.id,
                task_number=sub_num,
                title=st_req.title.strip(),
                priority=st_req.priority or "medium",
                status="todo",
                created_by=user_id,
                estimated_hours=st_req.estimated_hours,
            )
            self.db.add(subtask)

        await log_audit_event(
            self.db,
            user_id=user_id,
            org_id=self.org_id,
            action="task.created",
            resource_type="task",
            resource_id=task.id,
            after_state={"title": task.title, "number": task.task_number},
        )
        await self.db.commit()
        return await self.get_task(task.id)

    async def create_subtask(
        self,
        user_id: uuid.UUID,
        parent_task_id: uuid.UUID,
        req: SubtaskCreateRequest,
    ) -> Task:
        parent = await self.get_task(parent_task_id)

        stmt_proj = select(Project).where(Project.id == parent.project_id).with_for_update()
        project = (await self.db.execute(stmt_proj)).scalar_one()

        sub_num = await self._get_next_task_number(project)
        subtask = Task(
            org_id=self.org_id,
            project_id=parent.project_id,
            parent_task_id=parent.id,
            task_number=sub_num,
            title=req.title.strip(),
            priority=req.priority or "medium",
            status="todo",
            created_by=user_id,
            estimated_hours=req.estimated_hours,
        )
        self.db.add(subtask)

        # If parent was marked done, reset to todo because a new unfinished subtask was added
        if parent.status == "done":
            parent.status = "todo"

        await log_audit_event(
            self.db,
            user_id=user_id,
            org_id=self.org_id,
            action="subtask.created",
            resource_type="task",
            resource_id=subtask.id,
        )
        await self.db.commit()
        return await self.get_task(parent.id)

    async def update_task_status(
        self,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        new_status: str,
    ) -> Task:
        task = await self.get_task(task_id)
        old_status = task.status

        # If task has subtasks and user tries to set it to 'done'
        if task.subtasks and new_status == "done":
            incomplete = any(st.status != "done" for st in task.subtasks)
            if incomplete:
                raise AppError(
                    status_code=400,
                    detail="Cannot mark task as complete while incomplete subtasks remain. Please complete all subtasks first.",
                    code="INCOMPLETE_SUBTASKS"
                )

        task.status = new_status

        # If this is a subtask being updated, check if parent task auto-completes
        if task.parent_task_id:
            parent = await self.get_task(task.parent_task_id)
            if new_status == "done":
                # Check if all other sibling subtasks are done
                all_done = all(st.status == "done" for st in parent.subtasks if st.id != task.id)
                if all_done:
                    parent.status = "done"
            else:
                # Subtask reopened: parent must not be done
                if parent.status == "done":
                    parent.status = "todo"

        await log_audit_event(
            self.db,
            user_id=user_id,
            org_id=self.org_id,
            action="task.status_changed",
            resource_type="task",
            resource_id=task.id,
            before_state={"status": old_status},
            after_state={"status": new_status},
        )
        await self.db.commit()
        return await self.get_task(task.id)

    async def update_task(
        self,
        user_id: uuid.UUID,
        task_id: uuid.UUID,
        req: TaskUpdateRequest,
    ) -> Task:
        task = await self.get_task(task_id)

        if req.title is not None:
            task.title = req.title.strip()
        if req.description is not None:
            task.description = req.description.strip()
        if req.priority is not None:
            task.priority = req.priority
        if req.assignee_id is not None:
            task.assignee_id = req.assignee_id
        if req.due_date is not None:
            task.due_date = req.due_date
        if req.estimated_hours is not None:
            task.estimated_hours = req.estimated_hours

        if req.status is not None:
            return await self.update_task_status(user_id, task_id, req.status)

        await self.db.commit()
        return await self.get_task(task.id)

    async def assign_task(
        self,
        actor_id: uuid.UUID,
        task_id: uuid.UUID,
        assignee_id: Optional[uuid.UUID],
    ) -> Task:
        task = await self.get_task(task_id)
        old_assignee = str(task.assignee_id) if task.assignee_id else None
        task.assignee_id = assignee_id

        await log_audit_event(
            self.db,
            user_id=actor_id,
            org_id=self.org_id,
            action="task.assigned",
            resource_type="task",
            resource_id=task.id,
            before_state={"assignee_id": old_assignee},
            after_state={"assignee_id": str(assignee_id) if assignee_id else None},
        )
        await self.db.commit()
        return await self.get_task(task.id)

    async def delete_task(self, user_id: uuid.UUID, task_id: uuid.UUID) -> None:
        task = await self.get_task(task_id)
        await log_audit_event(
            self.db,
            user_id=user_id,
            org_id=self.org_id,
            action="task.deleted",
            resource_type="task",
            resource_id=task.id,
            before_state={"title": task.title},
        )
        await self.db.delete(task)
        await self.db.commit()
