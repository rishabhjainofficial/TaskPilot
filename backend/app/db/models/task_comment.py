import uuid
from typing import Optional, List
from sqlalchemy import Text, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, OrgScopedMixin


class TaskComment(Base, TimestampMixin, OrgScopedMixin):
    __tablename__ = "task_comments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    parent_comment_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("task_comments.id", ondelete="CASCADE"), nullable=True, index=True)

    # Relationships
    task: Mapped["Task"] = relationship("Task")
    user: Mapped["User"] = relationship("User")
    replies: Mapped[List["TaskComment"]] = relationship(
        "TaskComment",
        back_populates="parent_comment",
        cascade="all, delete-orphan",
        primaryjoin="TaskComment.id == foreign(TaskComment.parent_comment_id)",
    )
    parent_comment: Mapped[Optional["TaskComment"]] = relationship(
        "TaskComment",
        back_populates="replies",
        remote_side=[id],
        primaryjoin="foreign(TaskComment.parent_comment_id) == TaskComment.id",
    )

    __table_args__ = (
        Index("idx_task_comments_org_task_created", "org_id", "task_id", "created_at"),
    )
