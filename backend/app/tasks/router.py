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
    TaskDependencyCreateRequest,
    TaskDependenciesResponse,
    LabelCreateRequest,
    LabelResponse,
)
from app.tasks.collaboration_schemas import (
    TaskCommentCreateRequest,
    TaskCommentResponse,
    TimeLogCreateRequest,
    TimeLogResponse,
    TimeLogListResponse,
    AttachmentUploadUrlRequest,
    AttachmentUploadUrlResponse,
    AttachmentConfirmRequest,
    AttachmentResponse,
)
from app.tasks.service import TaskService
from app.tasks.collaboration_service import TaskCollaborationService

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
    tasks = await service.list_project_tasks(project_id, user=user)
    return [serialize_task_response(t) for t in tasks]


@router.post("/projects/{project_id}/tasks", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
async def create_task(
    project_id: uuid.UUID,
    body: TaskCreateRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("task.create", project_id_param="project_id")),
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


# ---------------- Comments ----------------
@router.post("/tasks/{task_id}/comments", response_model=TaskCommentResponse, status_code=status.HTTP_201_CREATED)
async def add_task_comment(
    task_id: uuid.UUID,
    body: TaskCommentCreateRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("comment.create")),
):
    service = TaskCollaborationService(db, org_id)
    return await service.add_comment(user, task_id, body)


@router.get("/tasks/{task_id}/comments", response_model=List[TaskCommentResponse])
async def list_task_comments(
    task_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = TaskCollaborationService(db, org_id)
    return await service.list_comments(task_id)


@router.delete("/tasks/{task_id}/comments/{comment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_task_comment(
    task_id: uuid.UUID,
    comment_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = TaskCollaborationService(db, org_id)
    await service.delete_comment(user, comment_id)


# ---------------- Time Logs ----------------
@router.post("/tasks/{task_id}/time-logs", response_model=TimeLogResponse, status_code=status.HTTP_201_CREATED)
async def add_time_log(
    task_id: uuid.UUID,
    body: TimeLogCreateRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("timelog.create")),
):
    service = TaskCollaborationService(db, org_id)
    return await service.add_time_log(user, task_id, body)


@router.get("/tasks/{task_id}/time-logs", response_model=TimeLogListResponse)
async def list_time_logs(
    task_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = TaskCollaborationService(db, org_id)
    return await service.list_time_logs(task_id)


@router.delete("/tasks/{task_id}/time-logs/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_time_log(
    task_id: uuid.UUID,
    log_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = TaskCollaborationService(db, org_id)
    await service.delete_time_log(user, log_id)


# ---------------- Attachments ----------------
@router.post("/tasks/{task_id}/attachments/upload-url", response_model=AttachmentUploadUrlResponse)
async def get_attachment_upload_url(
    task_id: uuid.UUID,
    body: AttachmentUploadUrlRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("attachment.upload")),
):
    service = TaskCollaborationService(db, org_id)
    return await service.get_upload_url(task_id, body)


@router.post("/tasks/{task_id}/attachments/confirm", response_model=AttachmentResponse, status_code=status.HTTP_201_CREATED)
async def confirm_attachment(
    task_id: uuid.UUID,
    body: AttachmentConfirmRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("attachment.upload")),
):
    service = TaskCollaborationService(db, org_id)
    return await service.confirm_attachment(user, task_id, body)


@router.get("/tasks/{task_id}/attachments", response_model=List[AttachmentResponse])
async def list_attachments(
    task_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = TaskCollaborationService(db, org_id)
    return await service.list_attachments(task_id)


@router.get("/tasks/{task_id}/attachments/{attachment_id}/download")
async def get_attachment_download_url(
    task_id: uuid.UUID,
    attachment_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = TaskCollaborationService(db, org_id)
    url = await service.get_download_url(attachment_id)
    return {"status": "ok", "download_url": url}


@router.delete("/tasks/{task_id}/attachments/{attachment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_attachment(
    task_id: uuid.UUID,
    attachment_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = TaskCollaborationService(db, org_id)
    await service.delete_attachment(user, attachment_id)


# --- Dependencies Endpoints (Phase 5) ---

@router.post("/tasks/{task_id}/dependencies", status_code=status.HTTP_201_CREATED)
async def add_task_dependency(
    task_id: uuid.UUID,
    body: TaskDependencyCreateRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = TaskService(db, org_id)
    dep = await service.add_dependency(user.id, task_id, body.blocking_task_id)
    return {"status": "ok", "dependency_id": dep.id}


@router.get("/tasks/{task_id}/dependencies", response_model=TaskDependenciesResponse)
async def get_task_dependencies(
    task_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = TaskService(db, org_id)
    return await service.list_task_dependencies(task_id)


@router.delete("/tasks/{task_id}/dependencies/{dependency_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_task_dependency(
    task_id: uuid.UUID,
    dependency_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = TaskService(db, org_id)
    await service.remove_dependency(user.id, task_id, dependency_id)


@router.get("/projects/{project_id}/dependencies")
async def get_project_dependency_graph(
    project_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = TaskService(db, org_id)
    return await service.get_project_dependencies(project_id)


# --- Labels Endpoints (Phase 5) ---

@router.get("/labels", response_model=List[LabelResponse])
async def list_labels(
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = TaskService(db, org_id)
    labels = await service.list_labels()
    return [LabelResponse(id=l.id, org_id=l.org_id, name=l.name, color=l.color) for l in labels]


@router.post("/labels", response_model=LabelResponse, status_code=status.HTTP_201_CREATED)
async def create_label(
    body: LabelCreateRequest,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(require_permission("project.manage")),
):
    service = TaskService(db, org_id)
    label = await service.create_label(user.id, body.name, body.color)
    return LabelResponse(id=label.id, org_id=label.org_id, name=label.name, color=label.color)


@router.post("/tasks/{task_id}/labels/{label_id}")
async def attach_label(
    task_id: uuid.UUID,
    label_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = TaskService(db, org_id)
    tl = await service.attach_label(user.id, task_id, label_id)
    return {"status": "ok", "task_label_id": tl.id}


@router.delete("/tasks/{task_id}/labels/{label_id}", status_code=status.HTTP_204_NO_CONTENT)
async def detach_label(
    task_id: uuid.UUID,
    label_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
    db: AsyncSession = Depends(get_tenant_db),
    user: User = Depends(get_current_user),
):
    service = TaskService(db, org_id)
    await service.detach_label(user.id, task_id, label_id)

