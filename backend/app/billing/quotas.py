import uuid
from datetime import datetime, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.db.models.subscription import Subscription
from app.db.models.project import Project
from app.db.models.membership import Membership
from app.db.models.ai_usage import AIUsage
from app.db.models.attachment import Attachment


async def get_or_create_subscription(db: AsyncSession, org_id: uuid.UUID) -> Subscription:
    stmt = select(Subscription).where(Subscription.org_id == org_id)
    sub = (await db.execute(stmt)).scalar_one_or_none()
    if not sub:
        sub = Subscription(
            org_id=org_id,
            plan="free",
            status="active",
            seats_limit=10,
            projects_limit=5,
            ai_credits_monthly=50,
            storage_bytes_limit=104857600,  # 100 MB
        )
        db.add(sub)
        await db.flush()
    return sub


async def check_quota(
    db: AsyncSession,
    org_id: uuid.UUID,
    resource: str,
    increment: int = 1,
) -> None:
    """
    Enforces per-tenant quotas based on the organization's subscription plan.
    Supported resources: 'projects', 'seats', 'ai_credits', 'storage_bytes'.
    """
    sub = await get_or_create_subscription(db, org_id)

    if resource == "projects":
        stmt = select(func.count(Project.id)).where(Project.org_id == org_id)
        current = (await db.execute(stmt)).scalar_one() or 0
        if current + increment > sub.projects_limit:
            raise AppError(
                status_code=402,
                detail=f"Project quota reached ({current}/{sub.projects_limit}). Upgrade to Pro or Enterprise for more projects.",
                code="PROJECT_QUOTA_EXCEEDED",
            )

    elif resource == "seats":
        stmt = select(func.count(Membership.id)).where(
            Membership.org_id == org_id,
            Membership.status == "active",
        )
        current = (await db.execute(stmt)).scalar_one() or 0
        if current + increment > sub.seats_limit:
            raise AppError(
                status_code=402,
                detail=f"Member seat quota reached ({current}/{sub.seats_limit}). Upgrade your plan to invite more team members.",
                code="SEAT_QUOTA_EXCEEDED",
            )

    elif resource == "ai_credits":
        month_start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        stmt = select(func.count(AIUsage.id)).where(
            AIUsage.org_id == org_id,
            AIUsage.created_at >= month_start,
        )
        current = (await db.execute(stmt)).scalar_one() or 0
        if current + increment > sub.ai_credits_monthly:
            raise AppError(
                status_code=402,
                detail=f"Monthly AI credits exhausted ({current}/{sub.ai_credits_monthly}). Upgrade to Pro for 500 monthly credits.",
                code="AI_CREDITS_EXHAUSTED",
            )

    elif resource == "storage_bytes":
        stmt = select(func.coalesce(func.sum(Attachment.size_bytes), 0)).where(
            Attachment.org_id == org_id,
        )
        current = (await db.execute(stmt)).scalar_one() or 0
        if current + increment > sub.storage_bytes_limit:
            mb_used = round(current / (1024 * 1024), 1)
            mb_limit = round(sub.storage_bytes_limit / (1024 * 1024), 1)
            raise AppError(
                status_code=402,
                detail=f"Storage quota exceeded ({mb_used}MB / {mb_limit}MB). Upgrade your plan for additional cloud storage.",
                code="STORAGE_QUOTA_EXCEEDED",
            )
