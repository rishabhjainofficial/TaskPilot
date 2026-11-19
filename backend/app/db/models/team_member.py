import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy import String, ForeignKey, DateTime, CheckConstraint, UniqueConstraint, Index, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, OrgScopedMixin


class TeamMember(Base, OrgScopedMixin):
    __tablename__ = "team_members"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    team_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("teams.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    team_role: Mapped[str] = mapped_column(String(20), default="member", nullable=False)
    job_title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    # Relationships
    team: Mapped["Team"] = relationship("Team", back_populates="members")
    user: Mapped["User"] = relationship("User")

    __table_args__ = (
        CheckConstraint("team_role IN ('lead', 'member')", name="ck_team_member_role"),
        UniqueConstraint("team_id", "user_id", name="uq_team_member_team_user"),
        Index(
            "idx_team_one_lead",
            "team_id",
            unique=True,
            postgresql_where=text("team_role = 'lead'"),
            sqlite_where=text("team_role = 'lead'"),
        ),
        Index("idx_team_members_org_user", "org_id", "user_id"),
    )
