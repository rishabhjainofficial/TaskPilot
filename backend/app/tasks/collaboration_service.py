import uuid
from datetime import date, datetime, timezone
from typing import List, Optional
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.billing.quotas import check_quota
from app.core.audit import log_audit_event
from app.core.errors import AppError, NotFoundError, PermissionDeniedError
from app.core.storage import storage_client
from app.db.models.attachment import Attachment
from app.db.models.membership import Membership
from app.db.models.task import Task
from app.db.models.task_comment import TaskComment
from app.db.models.time_log import TimeLog
from app.db.models.user import User
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


class TaskCollaborationService:
    def __init__(self, db: AsyncSession, org_id: uuid.UUID):
        self.db = db
        self.org_id = org_id

    async def _get_task(self, task_id: uuid.UUID) -> Task:
        stmt = select(Task).where(Task.id == task_id, Task.org_id == self.org_id)
        task = (await self.db.execute(stmt)).scalar_one_or_none()
        if not task:
            raise NotFoundError("Task", task_id)
        return task

    # ---------------- Comments ----------------
    async def add_comment(
        self,
        user: User,
        task_id: uuid.UUID,
        req: TaskCommentCreateRequest,
    ) -> TaskCommentResponse:
        task = await self._get_task(task_id)

        if req.parent_comment_id:
            stmt_parent = select(TaskComment).where(
                TaskComment.id == req.parent_comment_id,
                TaskComment.task_id == task_id,
                TaskComment.org_id == self.org_id,
            )
            if not (await self.db.execute(stmt_parent)).scalar_one_or_none():
                raise NotFoundError("Parent Comment", req.parent_comment_id)

        comment = TaskComment(
            org_id=self.org_id,
            task_id=task.id,
            user_id=user.id,
            content=req.content.strip(),
            parent_comment_id=req.parent_comment_id,
        )
        self.db.add(comment)
        await self.db.flush()

        await log_audit_event(
            self.db,
            user_id=user.id,
            org_id=self.org_id,
            action="task.comment_added",
            resource_type="task",
            resource_id=task.id,
        )
        await self.db.commit()

        return TaskCommentResponse(
            id=comment.id,
            task_id=comment.task_id,
            user_id=user.id,
            user_email=user.email,
            user_full_name=user.full_name,
            content=comment.content,
            parent_comment_id=comment.parent_comment_id,
            created_at=comment.created_at,
            replies=[],
        )

    async def list_comments(self, task_id: uuid.UUID) -> List[TaskCommentResponse]:
        await self._get_task(task_id)

        stmt = (
            select(TaskComment, User)
            .join(User, TaskComment.user_id == User.id)
            .where(TaskComment.task_id == task_id, TaskComment.org_id == self.org_id)
            .order_by(TaskComment.created_at.asc())
        )
        rows = (await self.db.execute(stmt)).all()

        nodes: dict[uuid.UUID, TaskCommentResponse] = {}
        top_level: List[TaskCommentResponse] = []

        for comment, user in rows:
            node = TaskCommentResponse(
                id=comment.id,
                task_id=comment.task_id,
                user_id=user.id,
                user_email=user.email,
                user_full_name=user.full_name,
                content=comment.content,
                parent_comment_id=comment.parent_comment_id,
                created_at=comment.created_at,
                replies=[],
            )
            nodes[comment.id] = node

        for comment_id, node in nodes.items():
            if node.parent_comment_id and node.parent_comment_id in nodes:
                nodes[node.parent_comment_id].replies.append(node)
            else:
                top_level.append(node)

        return top_level

    async def delete_comment(self, user: User, comment_id: uuid.UUID) -> None:
        stmt = select(TaskComment).where(TaskComment.id == comment_id, TaskComment.org_id == self.org_id)
        comment = (await self.db.execute(stmt)).scalar_one_or_none()
        if not comment:
            raise NotFoundError("Comment", comment_id)

        # Allow author, owner, or admin to delete
        if comment.user_id != user.id:
            mem_stmt = select(Membership.org_role).where(
                Membership.user_id == user.id,
                Membership.org_id == self.org_id,
                Membership.status == "active",
            )
            role = (await self.db.execute(mem_stmt)).scalar_one_or_none()
            if role not in ("owner", "admin"):
                raise PermissionDeniedError("Cannot delete another member's comment")

        await self.db.delete(comment)
        await self.db.commit()

    # ---------------- Time Logs ----------------
    async def add_time_log(
        self,
        user: User,
        task_id: uuid.UUID,
        req: TimeLogCreateRequest,
    ) -> TimeLogResponse:
        task = await self._get_task(task_id)

        log_date = req.log_date or date.today()
        time_log = TimeLog(
            org_id=self.org_id,
            task_id=task.id,
            user_id=user.id,
            duration_minutes=req.duration_minutes,
            description=req.description.strip() if req.description else None,
            log_date=log_date,
        )
        self.db.add(time_log)
        await self.db.flush()

        await log_audit_event(
            self.db,
            user_id=user.id,
            org_id=self.org_id,
            action="task.time_logged",
            resource_type="task",
            resource_id=task.id,
            after_state={"duration_minutes": req.duration_minutes, "log_date": str(log_date)},
        )
        await self.db.commit()

        return TimeLogResponse(
            id=time_log.id,
            task_id=time_log.task_id,
            user_id=user.id,
            user_email=user.email,
            user_full_name=user.full_name,
            duration_minutes=time_log.duration_minutes,
            description=time_log.description,
            log_date=time_log.log_date,
            created_at=time_log.created_at,
        )

    async def list_time_logs(self, task_id: uuid.UUID) -> TimeLogListResponse:
        await self._get_task(task_id)

        stmt = (
            select(TimeLog, User)
            .join(User, TimeLog.user_id == User.id)
            .where(TimeLog.task_id == task_id, TimeLog.org_id == self.org_id)
            .order_by(TimeLog.log_date.desc(), TimeLog.created_at.desc())
        )
        rows = (await self.db.execute(stmt)).all()

        total = 0
        logs = []
        for log, user in rows:
            total += log.duration_minutes
            logs.append(
                TimeLogResponse(
                    id=log.id,
                    task_id=log.task_id,
                    user_id=user.id,
                    user_email=user.email,
                    user_full_name=user.full_name,
                    duration_minutes=log.duration_minutes,
                    description=log.description,
                    log_date=log.log_date,
                    created_at=log.created_at,
                )
            )

        return TimeLogListResponse(
            task_id=task_id,
            total_duration_minutes=total,
            logs=logs,
        )

    async def delete_time_log(self, user: User, log_id: uuid.UUID) -> None:
        stmt = select(TimeLog).where(TimeLog.id == log_id, TimeLog.org_id == self.org_id)
        log = (await self.db.execute(stmt)).scalar_one_or_none()
        if not log:
            raise NotFoundError("TimeLog", log_id)

        if log.user_id != user.id:
            mem_stmt = select(Membership.org_role).where(
                Membership.user_id == user.id,
                Membership.org_id == self.org_id,
                Membership.status == "active",
            )
            role = (await self.db.execute(mem_stmt)).scalar_one_or_none()
            if role not in ("owner", "admin"):
                raise PermissionDeniedError("Cannot delete another member's time entry")

        await self.db.delete(log)
        await self.db.commit()

    # ---------------- Attachments ----------------
    async def get_upload_url(
        self,
        task_id: uuid.UUID,
        req: AttachmentUploadUrlRequest,
    ) -> AttachmentUploadUrlResponse:
        await check_quota(self.db, self.org_id, "storage_bytes", increment=req.size_bytes)
        task = await self._get_task(task_id)

        storage_key = storage_client.generate_storage_key(
            org_id=self.org_id,
            project_id=task.project_id,
            task_id=task.id,
            filename=req.filename,
        )

        upload_url = storage_client.generate_presigned_put_url(
            storage_key=storage_key,
            content_type=req.content_type,
        )

        return AttachmentUploadUrlResponse(
            storage_key=storage_key,
            upload_url=upload_url,
            filename=req.filename,
            content_type=req.content_type,
        )

    async def confirm_attachment(
        self,
        user: User,
        task_id: uuid.UUID,
        req: AttachmentConfirmRequest,
    ) -> AttachmentResponse:
        task = await self._get_task(task_id)

        # Enforce storage key prefix isolation
        expected_prefix = f"orgs/{self.org_id}/projects/{task.project_id}/tasks/{task.id}/"
        if not req.storage_key.startswith(expected_prefix):
            raise AppError(status_code=400, detail="Invalid storage key for this tenant and task", code="INVALID_STORAGE_KEY")

        attachment = Attachment(
            org_id=self.org_id,
            task_id=task.id,
            comment_id=req.comment_id,
            user_id=user.id,
            filename=req.filename.strip(),
            storage_key=req.storage_key,
            content_type=req.content_type,
            size_bytes=req.size_bytes,
        )
        self.db.add(attachment)
        await self.db.flush()

        await log_audit_event(
            self.db,
            user_id=user.id,
            org_id=self.org_id,
            action="attachment.uploaded",
            resource_type="task",
            resource_id=task.id,
            after_state={"filename": attachment.filename, "size_bytes": attachment.size_bytes},
        )
        await self.db.commit()

        return AttachmentResponse(
            id=attachment.id,
            task_id=attachment.task_id,
            user_id=user.id,
            user_email=user.email,
            user_full_name=user.full_name,
            filename=attachment.filename,
            storage_key=attachment.storage_key,
            content_type=attachment.content_type,
            size_bytes=attachment.size_bytes,
            created_at=attachment.created_at,
        )

    async def list_attachments(self, task_id: uuid.UUID) -> List[AttachmentResponse]:
        await self._get_task(task_id)

        stmt = (
            select(Attachment, User)
            .join(User, Attachment.user_id == User.id)
            .where(Attachment.task_id == task_id, Attachment.org_id == self.org_id)
            .order_by(Attachment.created_at.desc())
        )
        rows = (await self.db.execute(stmt)).all()

        return [
            AttachmentResponse(
                id=att.id,
                task_id=att.task_id,
                user_id=user.id,
                user_email=user.email,
                user_full_name=user.full_name,
                filename=att.filename,
                storage_key=att.storage_key,
                content_type=att.content_type,
                size_bytes=att.size_bytes,
                created_at=att.created_at,
            )
            for att, user in rows
        ]

    async def get_download_url(self, attachment_id: uuid.UUID) -> str:
        stmt = select(Attachment).where(Attachment.id == attachment_id, Attachment.org_id == self.org_id)
        attachment = (await self.db.execute(stmt)).scalar_one_or_none()
        if not attachment:
            raise NotFoundError("Attachment", attachment_id)

        return storage_client.generate_presigned_get_url(attachment.storage_key)

    async def delete_attachment(self, user: User, attachment_id: uuid.UUID) -> None:
        stmt = select(Attachment).where(Attachment.id == attachment_id, Attachment.org_id == self.org_id)
        attachment = (await self.db.execute(stmt)).scalar_one_or_none()
        if not attachment:
            raise NotFoundError("Attachment", attachment_id)

        if attachment.user_id != user.id:
            mem_stmt = select(Membership.org_role).where(
                Membership.user_id == user.id,
                Membership.org_id == self.org_id,
                Membership.status == "active",
            )
            role = (await self.db.execute(mem_stmt)).scalar_one_or_none()
            if role not in ("owner", "admin"):
                raise PermissionDeniedError("Cannot delete another member's attachment")

        await self.db.delete(attachment)
        await self.db.commit()
