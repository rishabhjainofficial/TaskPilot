import uuid
from datetime import datetime
from typing import Optional
from sqlalchemy import String, Integer, BigInteger, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, OrgScopedMixin


class Subscription(Base, TimestampMixin, OrgScopedMixin):
    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="CASCADE"), unique=True, nullable=False, index=True)
    plan: Mapped[str] = mapped_column(String(20), default="free", nullable=False)  # free, pro, business
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)  # active, past_due, canceled, trialing
    payment_provider: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    external_customer_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    external_subscription_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    seats_limit: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    projects_limit: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    ai_credits_monthly: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    storage_bytes_limit: Mapped[int] = mapped_column(BigInteger, default=104857600, nullable=False)  # 100MB
    doc_upload_limit: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    doc_size_limit_bytes: Mapped[int] = mapped_column(BigInteger, default=10485760, nullable=False)  # 10MB
    current_period_start: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_end: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    organization: Mapped["Organization"] = relationship("Organization", back_populates="subscription")
