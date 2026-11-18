import uuid
from typing import Optional, List
from sqlalchemy import String, Text, Integer, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, OrgScopedMixin


class Project(Base, TimestampMixin, OrgScopedMixin):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    key: Mapped[str] = mapped_column(String(10), nullable=False)  # e.g. TP
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)  # active, archived, completed
    task_seq: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # Auto-incrementing task counter
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)

    # Relationships
    organization: Mapped["Organization"] = relationship("Organization", back_populates="projects")
    creator: Mapped["User"] = relationship("User", foreign_keys=[created_by])
    tasks: Mapped[List["Task"]] = relationship("Task", back_populates="project", cascade="all, delete-orphan")
    assignments: Mapped[List["ProjectAssignment"]] = relationship("ProjectAssignment", back_populates="project", cascade="all, delete-orphan")

    __table_args__ = (
        UniqueConstraint("org_id", "key", name="uq_project_org_key"),
    )
