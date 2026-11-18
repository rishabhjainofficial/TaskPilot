import uuid
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import require_permission
from app.dependencies import get_current_user, get_current_org_id, get_tenant_db
from app.db.models.task import Task
from app.db.models.user import User
from app.tasks.schemas import (
    TaskCreateRequest,
    TaskUpdateRequest,
    TaskStatusUpdateRequest,
    TaskAssignRequest,
    SubtaskCreateRequest,
    TaskResponse,
    SubtaskResponse,
)
from app.tasks.service import TaskService

router = APIRouter(tags=["Tasks"])


def serialize_task_response(t: Task) -> TaskResponse:
    project_key = t.project.key if t.project else "TASK"
    return TaskResponse(
        id=t.id,
        org_id=t.org_id,
        project_id=t.project_id,
        parent_task_id=t.parent_task_id,
        task_number=t.task_number,
        task_code=f"{project_key}-{t.task_number}",
        title=t.title,
        description=t.description,
        priority=t.priority,
        status=t.status,
        created_by=t.created_by,
        assignee_id=t.assignee_id,
        due_date=t.due_date,
        estimated_hours=t.estimated_hours,
        position=t.position,
        ai_generated=t.ai_generated,
        created_at=t.created_at,
        subtasks=[
            SubtaskResponse(
                id=st.id,
                task_number=st.task_number,
                title=st.title,
                status=st.status,
                priority=st.priority,
                created_at=st.created_at,
            )
            for st in (t.subtasks or [])
        ],
    )


@router.get("/projects/{project_id}/tasks", response_model=List[TaskResponse])
async def list_project_tasks(
    project_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = TaskService(db, org_id)
    tasks = await service.list_project_tasks(project_id)
    return [serialize_task_response(t) for t in tasks]


@router.post("/projects/{project_id}/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    project_id: uuid.UUID,
    body: TaskCreateRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("task.create")),
):
    service = TaskService(db, org_id)
    task = await service.create_task(user.id, project_id, body)
    return serialize_task_response(task)


@router.get("/tasks/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = TaskService(db, org_id)
    task = await service.get_task(task_id)
    return serialize_task_response(task)


@router.patch("/tasks/{task_id}", response_model=TaskResponse)
async def update_task(
    task_id: uuid.UUID,
    body: TaskUpdateRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = TaskService(db, org_id)
    task = await service.update_task(user.id, task_id, body)
    return serialize_task_response(task)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("task.delete")),
):
    service = TaskService(db, org_id)
    await service.delete_task(user.id, task_id)


@router.post("/tasks/{task_id}/subtasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_subtask(
    task_id: uuid.UUID,
    body: SubtaskCreateRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("task.create_subtask")),
):
    service = TaskService(db, org_id)
    parent_task = await service.create_subtask(user.id, task_id, body)
    return serialize_task_response(parent_task)


@router.patch("/tasks/{task_id}/status", response_model=TaskResponse)
async def update_task_status(
    task_id: uuid.UUID,
    body: TaskStatusUpdateRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = TaskService(db, org_id)
    task = await service.update_task_status(user.id, task_id, body.status)
    return serialize_task_response(task)


@router.patch("/tasks/{task_id}/assign", response_model=TaskResponse)
async def assign_task(
    task_id: uuid.UUID,
    body: TaskAssignRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("task.assign")),
):
    service = TaskService(db, org_id)
    task = await service.assign_task(user.id, task_id, body.assignee_id)
    return serialize_task_response(task)
