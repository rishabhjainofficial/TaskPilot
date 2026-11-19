import uuid
from datetime import date
from typing import Optional
from sqlalchemy import Text, Integer, Date, ForeignKey, CheckConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, OrgScopedMixin


class TimeLog(Base, TimestampMixin, OrgScopedMixin):
    __tablename__ = "time_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    task_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    log_date: Mapped[date] = mapped_column(Date, default=date.today, nullable=False)

    # Relationships
    task: Mapped["Task"] = relationship("Task")
    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        CheckConstraint("duration_minutes > 0", name="ck_time_log_duration_positive"),
        Index("idx_time_logs_org_task_date", "org_id", "task_id", log_date.desc()),
        Index("idx_time_logs_org_user_date", "org_id", "user_id", log_date.desc()),
    )
